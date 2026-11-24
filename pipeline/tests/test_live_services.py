"""The API against real services: a throwaway Fuseki, RMLMapper, and EYE.

Skipped when Java or Fuseki is missing (see conftest.py); the pipeline test also
needs pipeline/rmlmapper.jar and EYE.
"""

import shutil

from fastapi.testclient import TestClient
import pytest
import requests
from rdflib import Graph

from pipeline import generic_pipeline
from pipeline import playground_server
from pipeline.run_store import RunStore
from pipeline.tests.conftest import TEST_DATA
from query_agent import orchestration
from reasoning import eye_engine

pytestmark = pytest.mark.live

GRAPH = "https://example.org/graphs/waterinfo-sample"
TYPE_RULE = """
    @prefix sh:   <http://www.w3.org/ns/shacl#> .
    @prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix sosa: <http://www.w3.org/ns/sosa/> .
    @prefix ex:   <https://example.org/rules#> .
    ex:CheckRule a sh:NodeShape ;
        sh:targetClass sosa:Observation ;
        sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate rdf:type ; sh:object ex:CheckedObservation ] .
"""

needs_tools = pytest.mark.skipif(
    not (generic_pipeline.RML_MAPPER_JAR.is_file() and shutil.which("java") and eye_engine.find_engine()),
    reason="Needs Java, pipeline/rmlmapper.jar, and EYE (native or bundled).",
)


@pytest.fixture
def client(live_fuseki, tmp_path, monkeypatch):
    monkeypatch.setattr(playground_server, "RUN_STORE", RunStore(tmp_path / "runs"))
    return TestClient(playground_server.app)


def count_triples(fuseki, graph):
    response = requests.post(
        f"{fuseki}/query",
        data={"query": f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    return int(response.json()["results"]["bindings"][0]["n"]["value"])


@needs_tools
def test_the_whole_pipeline_on_the_sample_data(client, live_fuseki):
    sample = (TEST_DATA / "waterinfo-sample.csv").read_bytes()
    state = client.post("/api/runs", files={"file": ("waterinfo-sample.csv", sample, "text/csv")}).json()
    run_id = state["id"]
    assert state["source"]["preview"]["total_rows"] == 5374

    mapping = (TEST_DATA / "rml.ttl.txt").read_text(encoding="utf-8").replace('"data.csv"', '"waterinfo-sample.csv"')
    rml = client.post(f"/api/runs/{run_id}/stages/rml", json={"mapping": mapping}).json()["stages"]["rml"]
    assert rml["status"] == "success", rml
    assert rml["details"]["rdf_triples"] == 32244

    shapes = (TEST_DATA / "SHACL_in.ttl").read_text(encoding="utf-8")
    validation = client.post(f"/api/runs/{run_id}/stages/shacl", json={"shapes": shapes}).json()["stages"]["shacl"]
    assert validation["status"] == "success", validation["message"]

    rules = client.post(f"/api/runs/{run_id}/stages/shacl-rules", json={"shapes": TYPE_RULE}).json()["stages"]["rules"]
    assert rules["details"]["inferred_triples"] == 5374

    salinity = eye_engine.find_example("salinity-classes")["rules"]
    reasoning = client.post(
        f"/api/runs/{run_id}/stages/reasoning", json={"rules": salinity, "example_id": "salinity-classes"}
    ).json()["stages"]["reasoning"]
    assert reasoning["status"] == "success", reasoning["message"]
    assert reasoning["details"]["input_rdf"] == "enriched RDF"
    assert reasoning["details"]["inferred_triples"] == 5386
    total = 32244 + 5374 + 5386
    assert reasoning["details"]["total_triples"] == total

    revalidated = client.post(f"/api/runs/{run_id}/stages/shacl", json={"shapes": shapes}).json()["stages"]["shacl"]
    assert revalidated["status"] == "success"
    assert revalidated["details"]["input_rdf"] == "reasoned RDF"

    published = client.post(f"/api/runs/{run_id}/stages/ingest", json={"graph_name": "waterinfo-sample"}).json()
    assert published["stages"]["ingest"]["status"] == "success", published["stages"]["ingest"]["message"]
    assert published["graph"]["uri"] == GRAPH
    assert count_triples(live_fuseki, GRAPH) == total
    assert client.get("/api/store/graphs").json()["graphs"] == [{"uri": GRAPH, "triples": total}]

    appended = client.post(f"/api/runs/{run_id}/stages/ingest", json={"graph_name": "waterinfo-sample", "mode": "append"}).json()
    assert appended["stages"]["ingest"]["details"]["mode"] == "append"
    assert count_triples(live_fuseki, GRAPH) == total  # the same triples again add nothing

    types = client.post("/api/store/operations/entity_types", json={"parameters": {"graph": GRAPH, "limit": 20}}).json()
    counts = {row["type"]["value"].rsplit("#", 1)[-1].rsplit("/", 1)[-1]: int(row["entities"]["value"]) for row in types["result"]["rows"]}
    assert counts["Observation"] == 5374
    assert counts["CheckedObservation"] == 5374
    assert (counts["BrackishReading"], counts["SalineReading"]) == (2741, 2633)

    for operation, parameters in [
        ("graph_overview", {}),
        ("property_usage", {}),
        ("find_entities", {"type": "http://www.w3.org/ns/sosa/Sensor"}),
        ("describe_entity", {"entity": "http://example.com/waterinfo/289435042"}),
        ("search_text", {"text": "2025-09-01T00:00"}),
        ("sample_triples", {"limit": 5}),
    ]:
        response = client.post(f"/api/store/operations/{operation}", json={"parameters": {"graph": GRAPH, **parameters}})
        assert response.status_code == 200, (operation, response.text)
        assert response.json()["result"]["row_count"] > 0, operation

    ask = client.post("/api/store/query", json={
        "query": f"PREFIX wq: <http://example.com/water-quality#> ASK {{ GRAPH <{GRAPH}> {{ ?s a wq:PlausibleSensor }} }}",
    }).json()
    assert ask == {"type": "ask", "boolean": True}

    for rdf_format, parser in [("turtle", "turtle"), ("ntriples", "nt"), ("jsonld", "json-ld"), ("xml", "xml")]:
        response = client.get(f"/api/runs/{run_id}/rdf", params={"format": rdf_format})
        assert "waterinfo-sample-reasoned" in response.headers["content-disposition"]
        assert len(Graph().parse(data=response.content, format=parser)) == total, rdf_format

    assert client.delete(f"/api/runs/{run_id}").status_code == 204
    assert client.get(f"/api/runs/{run_id}").status_code == 404
    assert count_triples(live_fuseki, GRAPH) == total  # published graphs stay in Fuseki


def test_fuseki_rejects_bad_queries_and_updates(client):
    syntax = client.post("/api/store/query", json={"query": "SELECT ?s WHERE { ?s ?p }"})
    assert syntax.status_code == 400
    assert "Parse error" in syntax.json()["detail"] or "Encountered" in syntax.json()["detail"]
    update = client.post("/api/store/query", json={"query": "INSERT DATA { <urn:a:b> <urn:a:c> <urn:a:d> }"})
    assert update.status_code == 400


def test_publishing_a_graph_whose_name_has_spaces(client, live_fuseki, tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "other-runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("people.csv", "people.csv")
    state["stages"].update({"upload": {"status": "success", "artifacts": []}, "rml": {"status": "success", "artifacts": []}})
    run_store.save(state)
    (run_store.run_dir(state["id"]) / "mapped.ttl").write_text(
        "@prefix ex: <https://example.org/> . ex:alice ex:name \"Alice\" .", encoding="utf-8"
    )

    result = client.post(f"/api/runs/{state['id']}/stages/ingest", json={"graph_name": "people 2026"}).json()

    uri = f"{generic_pipeline.DEFAULT_GRAPH_BASE.rstrip('/')}/people%202026"
    assert result["graph"]["uri"] == uri
    assert count_triples(live_fuseki, uri) == 1


def test_agents_chain_through_output_graphs(client, live_fuseki):
    data = """
        @prefix ex: <https://example.org/> .
        ex:r1 ex:value 20000 ; ex:sensor ex:A .
        ex:r2 ex:value 3000 ; ex:sensor ex:B .
        ex:r3 ex:value 18000 ; ex:sensor ex:A .
    """
    put = requests.put(f"{live_fuseki}/data", params={"graph": GRAPH}, data=data.encode(),
                       headers={"Content-Type": "text/turtle"}, timeout=30)
    assert put.status_code in (200, 201)
    output = f"{orchestration.OUTPUT_BASE}env123/high111"

    def run(agent_id, query, sources):
        response = client.post("/api/orchestration/run", json={
            "environment_id": "env123", "agent_id": agent_id, "query": query, "sources": sources,
        })
        assert response.status_code == 200, response.text
        return response.json()

    high = run("high111", "PREFIX ex: <https://example.org/> "
               "CONSTRUCT { ?r a ex:High ; ex:sensor ?s } WHERE { ?r ex:value ?v ; ex:sensor ?s FILTER(?v >= 15000) }", [GRAPH])
    assert (high["type"], high["triples"], high["output_graph"]) == ("graph", 4, output)
    assert count_triples(live_fuseki, output) == 4

    per_sensor = run("count222", "PREFIX ex: <https://example.org/> "
                     "SELECT ?s (COUNT(?r) AS ?n) WHERE { ?r a ex:High ; ex:sensor ?s } GROUP BY ?s", [output])
    assert [(row["s"]["value"], row["n"]["value"]) for row in per_sensor["rows"]] == [("https://example.org/A", "2")]

    combined = run("join333", "PREFIX ex: <https://example.org/> "
                   "SELECT ?r ?v WHERE { ?r a ex:High ; ex:value ?v } ORDER BY ?r", [output, GRAPH])
    assert [row["v"]["value"] for row in combined["rows"]] == ["20000", "18000"]

    # Ticked sources and GRAPH blocks work together.
    mixed = run("mixed444", "PREFIX ex: <https://example.org/> "
                f"SELECT ?r WHERE {{ GRAPH <{GRAPH}> {{ ?r ex:value ?v }} FILTER NOT EXISTS {{ ?r a ex:High }} }}", [output])
    assert [row["r"]["value"] for row in mixed["rows"]] == ["https://example.org/r2"]

    emptied = run("high111", "PREFIX ex: <https://example.org/> CONSTRUCT { ?r a ex:High } WHERE { ?r ex:value 1 }", [GRAPH])
    assert emptied["triples"] == 0
    assert count_triples(live_fuseki, output) == 0

    run("high111", "PREFIX ex: <https://example.org/> CONSTRUCT { ?r a ex:High } WHERE { ?r ex:value ?v }", [GRAPH])
    assert client.delete("/api/orchestration/environments/env123/outputs").json() == {"dropped": [output]}
    assert count_triples(live_fuseki, output) == 0
    assert count_triples(live_fuseki, GRAPH) == 6  # the original graph is untouched
