"""Tests for N3 reasoning with the EYE reasoner (native or the bundled WebAssembly build)."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from pipeline import generic_pipeline
from pipeline import playground_server
from pipeline.run_store import RunStore
from reasoning import eye_engine

EX = Namespace("https://example.org/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")
SSN = Namespace("http://www.w3.org/ns/ssn/")
WQ = Namespace("http://example.com/water-quality#")

needs_eye = pytest.mark.skipif(
    eye_engine.find_engine() is None,
    reason="EYE is required: install native EYE, or Node.js and the bundled reasoner (npm ci in reasoning/).",
)

LAMP_DATA = """
    @prefix ex: <https://example.org/> .
    ex:desk ex:has ex:lamp .
    ex:lamp a ex:Lamp .
"""

LAMP_RULES = """
    @prefix ex: <https://example.org/> .
    # A commented-out rule must not run: { ?x a ex:Lamp } => { ?x a ex:Broken } .
    { ?x a ex:Lamp } => { ?x a ex:Light ; ex:illuminates true } .
"""

# Two readings per sensor A and B and three for C, 15 minutes apart unless noted.
SENSOR_DATA = """
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix ex: <https://example.org/> .

    ex:a1 a sosa:Observation ; sosa:madeBySensor ex:A ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "0.0E0"^^xsd:double ; sosa:resultTime "2025-01-01T00:00:00Z"^^xsd:dateTime .
    ex:a2 a sosa:Observation ; sosa:madeBySensor ex:A ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "2.0E4"^^xsd:double ; sosa:resultTime "2025-01-01T00:15:00Z"^^xsd:dateTime .
    ex:b1 a sosa:Observation ; sosa:madeBySensor ex:B ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "1.2E3"^^xsd:double ; sosa:resultTime "2025-01-01T00:00:00Z"^^xsd:dateTime .
    ex:b2 a sosa:Observation ; sosa:madeBySensor ex:B ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "7.0E3"^^xsd:double ; sosa:resultTime "2025-01-01T00:15:00Z"^^xsd:dateTime .
    ex:b3 a sosa:Observation ; sosa:madeBySensor ex:B ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "9.0E4"^^xsd:double ; sosa:resultTime "2025-01-01T00:45:00Z"^^xsd:dateTime .
    ex:c1 a sosa:Observation ; sosa:madeBySensor ex:C ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "3.0E3"^^xsd:double ; sosa:resultTime "2025-01-01T00:00:00Z"^^xsd:dateTime .
    ex:c2 a sosa:Observation ; sosa:madeBySensor ex:C ; sosa:observedProperty ex:Conductivity ;
        sosa:hasSimpleResult "4.0E3"^^xsd:double ; sosa:resultTime "2025-01-01T00:15:00Z"^^xsd:dateTime .
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _example_rules(example_id: str) -> str:
    return eye_engine.find_example(example_id)["rules"]


# --- Reading rules and output (no EYE needed) -------------------------------------------


def test_contains_rules_ignores_comments_and_strings():
    assert eye_engine.contains_rules("{ ?x a :A } => { ?x a :B } .")
    assert eye_engine.contains_rules("{ ?x a :B } <= { ?x a :A } .")
    assert eye_engine.contains_rules("{ ?x a :A } log:query { ?x a :A } .")
    assert not eye_engine.contains_rules("# { ?x a :A } => { ?x a :B } .\n:a :b :c .")
    assert not eye_engine.contains_rules(':a :says "x => y" .')


def test_uses_query_only_counts_log_query_statements():
    assert eye_engine.uses_query("{ ?x a :A }\n  log:query\n{ ?x a :A } .")
    assert eye_engine.uses_query("{ ?x a :A } <http://www.w3.org/2000/10/swap/log#query> { ?x a :A } .")
    assert not eye_engine.uses_query("# { ?x a :A } log:query { ?x a :A } .\n{ ?x a :A } => { ?x a :B } .")
    assert not eye_engine.uses_query("{ ?x a :A } => { ?x a :B } .")


def test_strip_comments_keeps_hashes_in_iris_and_strings():
    text = '@prefix ex: <https://e.org/a#b> . # note\n"x # y" ex:p \'z\' . # tail\n{ ?a <= ?b }'
    assert eye_engine.strip_comments(text) == '@prefix ex: <https://e.org/a#b> . \n"x # y" ex:p \'z\' . \n{ ?a <= ?b }'
    assert eye_engine.strip_comments('"a => b" # c', keep_strings=False) == '"" '


def test_declared_prefixes_reads_turtle_and_sparql_style():
    prefixes = eye_engine.declared_prefixes(
        "@prefix wq: <http://example.com/water-quality#> .\nPREFIX ex: <https://example.org/>\n# @prefix no: <https://no/>"
    )
    assert prefixes == [("wq", URIRef("http://example.com/water-quality#")), ("ex", URIRef("https://example.org/"))]


def test_parse_output_keeps_rdf_and_counts_n3_only_statements():
    graph, skipped = eye_engine.parse_output(
        """
        @prefix ex: <https://example.org/> .
        ex:a ex:p ex:b .
        ex:a ex:says { ex:b ex:p ex:c } .
        "a literal" ex:p ex:b .
        """
    )
    assert set(graph) == {(EX.a, EX.p, EX.b)}
    assert skipped == 2


def test_parse_output_restores_skolemised_blank_nodes():
    graph, _ = eye_engine.parse_output(
        f"<{eye_engine.SKOLEM_PREFIX}n1> <https://example.org/p> <https://example.org/b> ."
    )
    assert set(graph) == {(BNode("n1"), EX.p, EX.b)}


def test_describe_problem_explains_eye_errors():
    engine = eye_engine.Engine("bundled", ("node", "eye.js"))

    def problem(stderr, stdout="", returncode=0):
        return eye_engine.describe_problem(stdout, stderr, returncode, "reasoning_rules.n3", engine)

    assert problem("** ERROR ** file:///reasoning_rules.n3 ** invalid_document(after_line(3))") == (
        "EYE could not parse the N3 rules: there is a syntax error after line 3."
    )
    memory = problem(
        "GET file:///reasoning_input_000.nt ** ERROR ** file:///reasoning_input_000.nt ** "
        "error(resource_error(stack),stack_overflow{depth:9543})"
    )
    assert memory.startswith("EYE ran out of memory while processing the input RDF.")
    assert "native EYE" in memory
    assert "inference fuse" in problem("** ERROR ** eam ** inference_fuse(")
    assert problem("", returncode=3) == "EYE stopped with exit code 3."
    assert problem("GET file:///reasoning_rules.n3 SC=2", stdout="ex:a ex:b ex:c .") is None


def test_parse_stats_reads_the_closing_line():
    stats = eye_engine.parse_stats(
        "2026-11-24T19:56:41.336Z in=5997 out=1004 ent=3006 step=8006 brake=4 inf=6985673 sec=0.782 inf/sec=8933086"
    )
    assert stats == {
        "input_triples": 5997, "output_triples": 1004, "entailments": 3006, "steps": 8006,
        "brakes": 4, "inferences": 6985673, "seconds": 0.782,
    }
    assert eye_engine.parse_stats("no statistics") == {}


def test_write_input_splits_n_triples_and_skolemises_blank_nodes(tmp_path):
    graph = Graph()
    node = BNode("reading")
    graph.add((EX.s, EX.has, node))
    graph.add((node, EX.value, Literal(5)))
    graph.add((EX.s, RDF.type, EX.Sensor))

    names = eye_engine.write_input(graph, tmp_path, chunk_triples=2)

    assert names == ["reasoning_input_000.nt", "reasoning_input_001.nt"]
    lines = [line for name in names for line in (tmp_path / name).read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 3
    assert not any("_:" in line for line in lines)
    assert sum(f"<{eye_engine.SKOLEM_PREFIX}reading>" in line for line in lines) == 2


def test_summarise_counts_classes_and_properties_and_samples_every_group():
    graph = Graph()
    for index in range(30):
        graph.add((EX[f"reading{index}"], RDF.type, EX.Reading))
    graph.add((EX.sensor, RDF.type, EX.Sensor))
    graph.add((EX.sensor, EX.readingCount, Literal(30)))

    summary = eye_engine.summarise(graph, sample_size=6)

    assert summary["classes"] == [
        {"iri": str(EX.Reading), "count": 30},
        {"iri": str(EX.Sensor), "count": 1},
    ]
    assert summary["properties"] == [{"iri": str(EX.readingCount), "count": 1}]
    assert len(summary["sample"]) == 4
    assert {row["object"]["value"] for row in summary["sample"]} >= {str(EX.Sensor), "30"}
    count_row = next(row for row in summary["sample"] if row["predicate"] == str(EX.readingCount))
    assert count_row["object"] == {
        "type": "literal", "value": "30", "datatype": str(XSD.integer), "language": None,
    }


def test_find_engine_prefers_native_eye(monkeypatch):
    monkeypatch.setenv("EYE_COMMAND", "/opt/eye/bin/eye")
    assert eye_engine.find_engine() == eye_engine.Engine("native", ("/opt/eye/bin/eye",))

    monkeypatch.delenv("EYE_COMMAND")
    monkeypatch.setattr(eye_engine.shutil, "which", lambda name: {"eye": "/usr/local/bin/eye"}.get(name))
    assert eye_engine.find_engine() == eye_engine.Engine("native", ("/usr/local/bin/eye",))

    monkeypatch.setattr(eye_engine.shutil, "which", lambda name: {"node": "/usr/bin/node"}.get(name))
    monkeypatch.setattr(eye_engine, "BUNDLED_CLI", Path(__file__))
    assert eye_engine.find_engine() == eye_engine.Engine("bundled", ("/usr/bin/node", __file__))

    monkeypatch.setattr(eye_engine.shutil, "which", lambda name: None)
    assert eye_engine.find_engine() is None
    assert eye_engine.status()["ready"] is False
    assert "python run.py" in eye_engine.status()["detail"]


def test_rules_without_any_rule_are_rejected(tmp_path):
    data_path = _write(tmp_path / "mapped.ttl", LAMP_DATA)
    with pytest.raises(generic_pipeline.PipelineError, match="No N3 rules found"):
        generic_pipeline.run_eye_reasoning(tmp_path, data_path, "@prefix ex: <https://example.org/> . ex:a ex:b ex:c .")


def test_examples_catalog_matches_the_example_files():
    examples = eye_engine.list_examples()
    files = {path.name for path in eye_engine.EXAMPLES_DIR.glob("*.n3")}
    assert {example["file_name"] for example in examples} == files
    for example in examples:
        assert example["title"] and example["summary"] and example["features"]
        assert eye_engine.contains_rules(example["rules"])
    assert eye_engine.uses_query(_example_rules("sudden-changes"))
    assert not eye_engine.uses_query(_example_rules("salinity-classes"))


# --- Running EYE ------------------------------------------------------------------------


@needs_eye
def test_reasoning_adds_inferred_triples_to_the_data(tmp_path):
    data_path = _write(tmp_path / "mapped.ttl", LAMP_DATA)

    result = generic_pipeline.run_eye_reasoning(tmp_path, data_path, LAMP_RULES)

    inferred = Graph().parse(result["inferred_path"], format="turtle")
    reasoned = Graph().parse(result["output_path"], format="turtle")
    assert set(inferred) == {
        (EX.lamp, RDF.type, EX.Light),
        (EX.lamp, EX.illuminates, Literal(True)),
    }
    assert result["inferred_triples"] == 2
    assert result["total_triples"] == result["input_triples"] + 2 == len(reasoned)
    assert (EX.lamp, RDF.type, EX.Broken) not in reasoned
    assert result["output_mode"] == "derivations"
    assert result["eye_version"].startswith("EYE v")
    assert result["summary"]["classes"] == [{"iri": str(EX.Light), "count": 1}]
    assert result["eye_stats"]["output_triples"] == 2
    assert not list(tmp_path.glob("reasoning_input_*"))


@needs_eye
def test_reasoning_reports_syntax_errors_with_their_position(tmp_path):
    data_path = _write(tmp_path / "mapped.ttl", LAMP_DATA)
    rules = "@prefix ex: <https://example.org/> .\n\n{ ?x a ex:Lamp  => { ?x a ex:Light } .\n"
    with pytest.raises(generic_pipeline.PipelineError, match="syntax error after line") as error:
        generic_pipeline.run_eye_reasoning(tmp_path, data_path, rules)
    assert "invalid_document" in error.value.log


@needs_eye
def test_reasoning_reports_an_inference_fuse(tmp_path):
    data_path = _write(tmp_path / "mapped.ttl", LAMP_DATA)
    rules = "@prefix ex: <https://example.org/> .\n{ ?x a ex:Lamp } => false .\n"
    with pytest.raises(generic_pipeline.PipelineError, match="inference fuse"):
        generic_pipeline.run_eye_reasoning(tmp_path, data_path, rules)


@needs_eye
def test_log_query_outputs_only_its_answers(tmp_path):
    data_path = _write(tmp_path / "mapped.ttl", LAMP_DATA)
    rules = """
        @prefix ex: <https://example.org/> .
        @prefix log: <http://www.w3.org/2000/10/swap/log#> .
        { ?x a ex:Lamp } => { ?x ex:helper true } .
        { ?x ex:helper true } => { ?x a ex:Light } .
        { ?x a ex:Light } log:query { ?x a ex:Light } .
    """

    result = generic_pipeline.run_eye_reasoning(tmp_path, data_path, rules)

    assert result["output_mode"] == "query"
    assert set(Graph().parse(result["inferred_path"], format="turtle")) == {(EX.lamp, RDF.type, EX.Light)}


@needs_eye
def test_blank_nodes_keep_their_identity_across_input_files(tmp_path):
    data = Graph()
    reading = BNode()
    data.add((EX.sensor, EX.made, reading))
    data.add((reading, EX.value, Literal(5)))
    _write(tmp_path / "rules.n3", """
        @prefix ex: <https://example.org/> .
        { ?s ex:made ?r . ?r ex:value ?v } => { ?s ex:lastValue ?v . ?r a ex:Checked } .
    """)

    outcome = eye_engine.reason(tmp_path, data, "rules.n3", timeout=120, chunk_triples=1)

    assert set(outcome.graph) == {
        (EX.sensor, EX.lastValue, Literal(5)),
        (reading, RDF.type, EX.Checked),
    }


def _native_engine():
    command = os.getenv("EYE_COMMAND") or shutil.which("eye")
    return eye_engine._native(command) if command else None


def _bundled_engine():
    node = shutil.which("node")
    if node and eye_engine.BUNDLED_CLI.is_file():
        return eye_engine.Engine("bundled", (node, str(eye_engine.BUNDLED_CLI)))
    return None


def _by_value(graph):
    return {(s, p, o.toPython() if isinstance(o, Literal) else o) for s, p, o in graph}


@needs_eye
def test_native_eye_command_is_used_when_configured(tmp_path, monkeypatch):
    engine = eye_engine.find_engine()
    if engine.kind == "native":
        command = engine.command[-1]
    elif os.name != "nt":
        # Stand in for a native installation with a script that forwards to the bundled build.
        command = tmp_path / "eye"
        command.write_text(f'#!/bin/sh\nexec "{engine.command[0]}" "{engine.command[1]}" "$@"\n', encoding="utf-8")
        command.chmod(0o755)
    else:
        pytest.skip("Needs native EYE, or a POSIX shell for the stand-in script.")
    monkeypatch.setenv("EYE_COMMAND", str(command))
    work = tmp_path / "run"
    work.mkdir()
    data_path = _write(work / "mapped.ttl", LAMP_DATA)

    result = generic_pipeline.run_eye_reasoning(work, data_path, LAMP_RULES)

    assert result["engine"] == "native"
    assert result["inferred_triples"] == 2
    assert eye_engine.status()["engine"] == "native"


@pytest.mark.skipif(
    not (_native_engine() and _bundled_engine()),
    reason="Needs both native EYE and the bundled build.",
)
@pytest.mark.parametrize("example_id", [example["id"] for example in eye_engine.EXAMPLES])
def test_native_and_bundled_eye_derive_the_same_facts(tmp_path, monkeypatch, example_id):
    data = Graph().parse(data=SENSOR_DATA, format="turtle")
    _write(tmp_path / "rules.n3", _example_rules(example_id))
    derived = {}
    for engine in (_native_engine(), _bundled_engine()):
        monkeypatch.setattr(eye_engine, "find_engine", lambda engine=engine: engine)
        derived[engine.kind] = eye_engine.reason(tmp_path, data, "rules.n3", timeout=120).graph
    assert derived["native"]
    assert _by_value(derived["native"]) == _by_value(derived["bundled"])


@needs_eye
def test_ontology_example(tmp_path):
    inferred = _run_example(tmp_path, "ontology-reasoning")
    assert (EX.A, SOSA.madeObservation, EX.a1) in inferred
    assert (EX.A, RDF.type, SOSA.Sensor) in inferred
    assert (EX.A, RDF.type, SSN.System) in inferred
    assert (EX.A, SOSA.observes, EX.Conductivity) in inferred
    assert (EX.Conductivity, RDF.type, SSN.Property) in inferred
    assert not any(isinstance(s, Literal) for s, _p, _o in inferred)


@needs_eye
def test_salinity_example_classifies_readings_and_uses_negation(tmp_path):
    inferred = _run_example(tmp_path, "salinity-classes")
    assert (EX.b1, RDF.type, WQ.FreshReading) in inferred
    assert (EX.b2, RDF.type, WQ.BrackishReading) in inferred
    assert (EX.a2, RDF.type, WQ.SalineReading) in inferred
    assert (EX.a1, RDF.type, WQ.ImplausibleReading) in inferred
    assert (EX.b3, RDF.type, WQ.ImplausibleReading) in inferred
    assert set(inferred.subjects(RDF.type, WQ.PlausibleSensor)) == {EX.C}
    assert set(inferred.subjects(RDF.type, WQ.SensorWithSalineReadings)) == {EX.A}
    assert set(inferred.predicates()) == {RDF.type}


@needs_eye
def test_sensor_summary_example(tmp_path):
    inferred = _run_example(tmp_path, "sensor-summary")
    assert inferred.value(EX.B, WQ.readingCount).toPython() == 3
    assert inferred.value(EX.B, WQ.minimumValue).toPython() == 1200
    assert inferred.value(EX.B, WQ.maximumValue).toPython() == 90000
    assert float(inferred.value(EX.B, WQ.meanValue).toPython()) == pytest.approx(32733.33)
    assert inferred.value(EX.C, WQ.firstReading).toPython() == datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert inferred.value(EX.C, WQ.lastReading).toPython() == datetime(2025, 1, 1, 0, 15, tzinfo=timezone.utc)


@needs_eye
def test_sudden_changes_example_outputs_only_the_flags(tmp_path):
    inferred = _run_example(tmp_path, "sudden-changes")
    assert set(inferred.subjects(RDF.type, WQ.SuddenChange)) == {EX.a2, EX.b2}
    assert inferred.value(EX.a2, WQ.changeFromPrevious).toPython() == 20000
    assert inferred.value(EX.b2, WQ.changeFromPrevious).toPython() == 5800
    assert set(inferred.predicates()) == {RDF.type, WQ.changeFromPrevious}


def _run_example(tmp_path: Path, example_id: str) -> Graph:
    data_path = _write(tmp_path / "mapped.ttl", SENSOR_DATA)
    result = generic_pipeline.run_eye_reasoning(tmp_path, data_path, _example_rules(example_id))
    return Graph().parse(result["inferred_path"], format="turtle")


# --- API and stage bookkeeping ------------------------------------------------------------


def _mapped_run(tmp_path, monkeypatch, data=SENSOR_DATA):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("sensors.csv", "sensors.csv")
    state["stages"]["upload"] = {"status": "success", "artifacts": []}
    state["stages"]["rml"] = {"status": "success", "artifacts": [], "details": {"rdf_triples": 35}}
    run_store.save(state)
    _write(run_store.run_dir(state["id"]) / "mapped.ttl", data)
    return run_store, state, TestClient(playground_server.app)


def test_examples_endpoint_lists_every_example_with_its_rules(tmp_path, monkeypatch):
    _run_store, _state, client = _mapped_run(tmp_path, monkeypatch)
    examples = client.get("/api/reasoning/examples").json()["examples"]
    assert [example["id"] for example in examples] == [example["id"] for example in eye_engine.EXAMPLES]
    assert all("=>" in example["rules"] for example in examples)


def test_reasoning_requires_a_mapping(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("sensors.csv", "sensors.csv")
    client = TestClient(playground_server.app)
    response = client.post(f"/api/runs/{state['id']}/stages/reasoning", json={"rules": LAMP_RULES})
    assert response.status_code == 409
    assert response.json()["detail"] == "Complete the RML mapping first."


@needs_eye
def test_reasoned_rdf_becomes_the_current_rdf(tmp_path, monkeypatch):
    _run_store, state, client = _mapped_run(tmp_path, monkeypatch)
    run_id = state["id"]
    rules = _example_rules("salinity-classes")

    reasoned = client.post(
        f"/api/runs/{run_id}/stages/reasoning", json={"rules": rules, "example_id": "salinity-classes"}
    ).json()
    stage = reasoned["stages"]["reasoning"]
    download = client.get(f"/api/runs/{run_id}/rdf")
    preview = client.get(f"/api/runs/{run_id}/rdf-preview").json()
    validated = client.post(
        f"/api/runs/{run_id}/stages/shacl",
        json={"shapes": """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix sosa: <http://www.w3.org/ns/sosa/> .
            @prefix wq: <http://example.com/water-quality#> .
            wq:SensorShape a sh:NodeShape ; sh:targetClass sosa:Sensor ;
                sh:class wq:PlausibleSensor ; sh:message "Sensor has implausible readings." .
        """},
    ).json()

    assert stage["status"] == "success", stage
    assert stage["message"] == "EYE inferred 12 new triples from the mapped RDF."
    assert stage["details"]["rules_source"] == "example “Classify readings”"
    assert stage["details"]["input_rdf"] == "mapped RDF"
    assert stage["details"]["summary"]["class_count"] == 7
    assert [artifact["name"] for artifact in reasoned["artifacts"]] == ["N3 rules", "Inferred triples", "Reasoned RDF"]
    assert 'filename="sensors-reasoned.ttl"' in download.headers["content-disposition"]
    assert preview["source"] == "reasoned RDF"
    assert validated["stages"]["shacl"]["details"]["input_rdf"] == "reasoned RDF"
    assert validated["stages"]["shacl"]["details"]["severity_counts"]["Violation"] == 2

    edited = client.post(
        f"/api/runs/{run_id}/stages/reasoning",
        json={"rules": rules + "\n# tweaked\n", "example_id": "salinity-classes"},
    ).json()
    assert edited["stages"]["reasoning"]["details"]["rules_source"] == "example “Classify readings” (edited)"
    assert "shacl" not in edited["stages"]

    rules_stage = client.post(
        f"/api/runs/{run_id}/stages/shacl-rules",
        json={"shapes": """
            @prefix sh: <http://www.w3.org/ns/shacl#> .
            @prefix sosa: <http://www.w3.org/ns/sosa/> .
            @prefix ex: <https://example.org/> .
            ex:Rules a sh:NodeShape ; sh:targetClass sosa:Observation ;
                sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate ex:checked ; sh:object true ] .
        """},
    ).json()
    assert rules_stage["stages"]["rules"]["status"] == "success"
    assert "reasoning" not in rules_stage["stages"]

    again = client.post(f"/api/runs/{run_id}/stages/reasoning", json={"rules": rules}).json()
    assert again["stages"]["reasoning"]["details"]["input_rdf"] == "enriched RDF"
    assert again["stages"]["reasoning"]["details"]["rules_source"] == "pasted text"


@needs_eye
def test_failed_reasoning_falls_back_to_the_previous_rdf(tmp_path, monkeypatch):
    _run_store, state, client = _mapped_run(tmp_path, monkeypatch)
    run_id = state["id"]

    failed = client.post(
        f"/api/runs/{run_id}/stages/reasoning",
        json={"rules": "{ ?x a <https://example.org/A> => { ?x a <https://example.org/B> } .", "source_name": "bad.n3"},
    ).json()

    assert failed["stages"]["reasoning"]["status"] == "error"
    assert "syntax error" in failed["stages"]["reasoning"]["message"]
    assert failed["stages"]["reasoning"]["log"]
    download = client.get(f"/api/runs/{run_id}/rdf")
    assert 'filename="sensors-mapped.ttl"' in download.headers["content-disposition"]


def test_rerunning_steps_clears_reasoning_that_depends_on_them(tmp_path):
    run_store = RunStore(tmp_path / "runs")
    state = run_store.create("items.csv", "items.csv")
    state["stages"] = {
        stage: {"status": "success", "artifacts": []}
        for stage in ("upload", "rml", "rules", "reasoning", "shacl", "ingest")
    }
    state["graph"] = {"name": "items", "uri": "https://example.org/graphs/items"}
    run_store.save(state)

    state = run_store.begin_stage(state, "reasoning")
    assert set(state["stages"]) == {"upload", "rml", "rules", "reasoning"}
    assert state["graph"] is None

    state = run_store.begin_stage(state, "rules")
    assert set(state["stages"]) == {"upload", "rml", "rules"}
