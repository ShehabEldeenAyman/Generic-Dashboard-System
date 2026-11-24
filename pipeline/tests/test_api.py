"""API and module behaviour that the workflow tests do not cover: edge cases and failures."""

import json
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
import pytest
import requests
from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery

from pipeline import generic_pipeline
from pipeline import playground_server
from pipeline.run_store import RunStore
from query_agent import operations, orchestration
from SHACL import shacl_engine
from triple_store_ingestion import ingest

PEOPLE = """
    @prefix ex: <https://example.org/> .
    ex:alice a ex:Person ; ex:name "Alice" .
    ex:bob a ex:Person ; ex:name "Bob" .
"""

NAME_REQUIRED = """
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <https://example.org/> .
    ex:PersonShape a sh:NodeShape ; sh:targetClass ex:Person ;
        sh:property [ sh:path ex:name ; sh:minCount 1 ] .
"""


@pytest.fixture
def store(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    return run_store


@pytest.fixture
def client(store):
    return TestClient(playground_server.app)


def upload(client, name, content, media_type="text/csv"):
    return client.post("/api/runs", files={"file": (name, content, media_type)}).json()


def mapped_run(store, data=PEOPLE):
    state = store.create("people.csv", "people.csv")
    state["stages"]["upload"] = {"status": "success", "artifacts": []}
    state["stages"]["rml"] = {"status": "success", "artifacts": [], "details": {"rdf_triples": 4}}
    store.save(state)
    (store.run_dir(state["id"]) / "mapped.ttl").write_text(data, encoding="utf-8")
    return state


class Response:
    """A stand-in for a requests response."""

    def __init__(self, status_code=200, content_type="application/sparql-results+json", body=b""):
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = {"Content-Type": content_type}
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text(self):
        return self._body.decode()

    def json(self):
        return json.loads(self._body)

    def iter_content(self, chunk_size=1):
        yield self._body


# --- Service status ----------------------------------------------------------------------


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "service": "semantic-data-studio"}


def test_config_explains_why_fuseki_is_offline(client, monkeypatch):
    def unreachable(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(playground_server.requests, "get", unreachable)
    config = client.get("/api/config").json()
    assert config["fuseki"]["connected"] is False
    assert "connection refused" in config["fuseki"]["detail"]
    assert config["rdf_formats"] == ["turtle", "ntriples", "jsonld", "xml"]
    assert config["max_upload_bytes"] == playground_server.MAX_UPLOAD_BYTES
    assert set(config["tools"]) >= {"java", "rml_mapper", "eye"}


def test_config_reports_an_unhealthy_fuseki(client, monkeypatch):
    monkeypatch.setattr(playground_server.requests, "get", lambda *a, **k: Response(status_code=503))
    fuseki = client.get("/api/config").json()["fuseki"]
    assert fuseki["connected"] is False
    assert fuseki["detail"] == "Fuseki returned HTTP 503."


# --- Uploads -----------------------------------------------------------------------------


def test_upload_over_the_limit_fails_and_leaves_no_file(client, store, monkeypatch):
    monkeypatch.setattr(playground_server, "MAX_UPLOAD_BYTES", 10)
    state = upload(client, "big.csv", b"a,b\n" + b"1,2\n" * 50)
    assert state["stages"]["upload"]["status"] == "error"
    assert "exceeds" in state["stages"]["upload"]["message"]
    assert not (store.run_dir(state["id"]) / "big.csv").exists()


@pytest.mark.parametrize(("content", "delimiter"), [
    (b"sku;price\nA-1;10\n", ";"),
    (b"sku\tprice\nA-1\t10\n", "tab"),
    (b"sku|price\nA-1|10\n", "|"),
])
def test_upload_detects_the_delimiter(client, content, delimiter):
    preview = upload(client, "items.csv", content)["source"]["preview"]
    assert preview["delimiter"] == delimiter
    assert preview["columns"] == ["sku", "price"]
    assert preview["rows"] == [{"sku": "A-1", "price": "10"}]


def test_upload_falls_back_to_latin1(client):
    preview = upload(client, "places.csv", "name,city\nRené,Liège\n".encode("latin-1"))["source"]["preview"]
    assert preview["encoding"] == "latin-1"
    assert preview["rows"] == [{"name": "René", "city": "Liège"}]


def test_upload_of_an_empty_csv_fails(client):
    state = upload(client, "empty.csv", b"")
    assert state["stages"]["upload"]["status"] == "error"
    assert "empty" in state["stages"]["upload"]["message"]


def test_upload_of_a_broken_workbook_fails(client):
    state = upload(client, "broken.xlsx", b"this is not a zip file", "application/octet-stream")
    assert state["stages"]["upload"]["status"] == "error"
    assert "could not be opened" in state["stages"]["upload"]["message"]


def test_uploaded_file_names_are_made_safe():
    assert generic_pipeline.safe_filename("../../etc/my data (1).csv") == "my_data_1_.csv"
    assert generic_pipeline.safe_filename("Résumé.xlsx") == "R_sum_.xlsx"
    with pytest.raises(generic_pipeline.PipelineError, match=r"\.csv or \.xlsx"):
        generic_pipeline.safe_filename("notes.txt")


def test_unknown_and_malformed_run_ids_are_not_found(client):
    assert client.get(f"/api/runs/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/runs/not-a-uuid").status_code == 404
    assert client.delete(f"/api/runs/{uuid.uuid4()}").status_code == 404


# --- Stage prerequisites and failures ----------------------------------------------------


def test_every_stage_needs_its_prerequisite(client, store):
    state = store.create("people.csv", "people.csv")
    run_id = state["id"]
    assert client.post(f"/api/runs/{run_id}/stages/rml", json={"mapping": "x"}).json()["detail"] == "Complete the data upload first."
    for stage, body in [
        ("shacl", {"shapes": NAME_REQUIRED}),
        ("shacl-rules", {"shapes": NAME_REQUIRED}),
        ("reasoning", {"rules": "{ ?s ?p ?o } => { ?s ?p ?o } ."}),
        ("ingest", {"graph_name": "people"}),
    ]:
        response = client.post(f"/api/runs/{run_id}/stages/{stage}", json=body)
        assert response.status_code == 409, stage
        assert response.json()["detail"] == "Complete the RML mapping first."


def test_mapping_that_is_not_turtle_fails_the_stage(client, store):
    state = upload(client, "items.csv", b"sku,price\nA-1,10\n")
    result = client.post(f"/api/runs/{state['id']}/stages/rml", json={"mapping": "this is not turtle"}).json()
    assert result["stages"]["rml"]["status"] == "error"
    assert "not valid Turtle" in result["stages"]["rml"]["message"]


def test_missing_rmlmapper_is_explained(client, monkeypatch):
    monkeypatch.setattr(generic_pipeline, "RML_MAPPER_JAR", Path("/nonexistent/rmlmapper.jar"))
    state = upload(client, "items.csv", b"sku,price\nA-1,10\n")
    mapping = "@prefix rr: <http://www.w3.org/ns/r2rml#> . <#M> a rr:TriplesMap ."
    result = client.post(f"/api/runs/{state['id']}/stages/rml", json={"mapping": mapping}).json()
    assert result["stages"]["rml"]["status"] == "error"
    assert "RMLMapper is not available" in result["stages"]["rml"]["message"]


def test_validation_that_passes_reports_conformance(client, store):
    state = mapped_run(store)
    result = client.post(f"/api/runs/{state['id']}/stages/shacl", json={"shapes": NAME_REQUIRED}).json()
    stage = result["stages"]["shacl"]
    assert stage["status"] == "success"
    assert stage["message"] == "The mapped RDF conforms to the SHACL shapes."
    assert stage["details"]["shapes_source"] == "pasted text"
    assert [artifact["name"] for artifact in result["artifacts"]] == ["SHACL shapes", "Validation report"]


def test_applying_rules_without_rules_fails_the_stage(client, store):
    state = mapped_run(store)
    result = client.post(
        f"/api/runs/{state['id']}/stages/shacl-rules", json={"shapes": NAME_REQUIRED, "source_name": "shapes.ttl"}
    ).json()
    assert result["stages"]["rules"]["status"] == "error"
    assert "sh:rule" in result["stages"]["rules"]["message"]


def test_publishing_rejects_an_unknown_mode_and_reports_fuseki_failures(client, store, monkeypatch):
    state = mapped_run(store)
    url = f"/api/runs/{state['id']}/stages/ingest"
    assert client.post(url, json={"graph_name": "people", "mode": "merge"}).status_code == 422

    monkeypatch.setattr(generic_pipeline.ingest, "delete_graph", lambda graph: True)
    monkeypatch.setattr(generic_pipeline.ingest, "upload_graph", lambda path, graph, replace=True: False)
    result = client.post(url, json={"graph_name": "people"}).json()
    assert result["stages"]["ingest"]["status"] == "error"
    assert "Fuseki ingestion failed" in result["stages"]["ingest"]["message"]
    assert result["graph"] is None


# --- Downloads, previews, and artifacts --------------------------------------------------


def test_downloads_and_previews_validate_their_parameters(client, store):
    state = mapped_run(store)
    run_id = state["id"]
    assert client.get(f"/api/runs/{run_id}/rdf", params={"format": "csv"}).status_code == 422
    assert client.get(f"/api/runs/{run_id}/rdf-preview", params={"limit": 0}).status_code == 422
    assert client.get(f"/api/runs/{run_id}/rdf-preview", params={"limit": 11}).status_code == 422
    beyond = client.get(f"/api/runs/{run_id}/rdf-preview", params={"offset": 99}).json()
    assert beyond["returned_instances"] == 0
    assert beyond["has_next"] is False and beyond["has_previous"] is True


def test_artifacts_can_be_downloaded_and_previewed(client, store):
    state = upload(client, "items.csv", b"sku,price\nA-1,10\n")
    artifact = state["artifacts"][0]
    assert client.get(artifact["download_url"]).content == b"sku,price\nA-1,10\n"
    preview = client.get(artifact["preview_url"]).json()
    assert preview["table"]["rows"] == [{"sku": "A-1", "price": "10"}]

    state = mapped_run(store)
    validated = client.post(f"/api/runs/{state['id']}/stages/shacl", json={"shapes": NAME_REQUIRED}).json()
    report = next(item for item in validated["artifacts"] if item["kind"] == "txt")
    assert client.get(report["preview_url"]).json()["text"].startswith("Validation Report")

    assert client.get(f"/api/runs/{state['id']}/artifacts/{'0' * 32}").status_code == 404
    assert client.get(f"/api/runs/{uuid.uuid4()}/artifacts/{report['id']}").status_code == 404


def test_run_store_keeps_files_inside_their_run(store):
    state = store.create("items.csv", "items.csv")
    with pytest.raises(KeyError):
        store.resolve_relative(state["id"], "../outside.txt")
    with pytest.raises(KeyError):
        store.begin_stage(state, "unknown")
    outside = store.root.parent / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        store.add_artifact(state, "upload", outside)


# --- Helpers -----------------------------------------------------------------------------


def test_graph_names_are_checked():
    assert generic_pipeline.graph_name_to_uri("sales 2026") == f"{generic_pipeline.DEFAULT_GRAPH_BASE.rstrip('/')}/sales%202026"
    with pytest.raises(generic_pipeline.PipelineError, match="Enter a graph name"):
        generic_pipeline.graph_name_to_uri("   ")
    with pytest.raises(generic_pipeline.PipelineError, match="whitespace"):
        generic_pipeline.graph_name_to_uri("https://example.org/my graph")


def test_rdf_helpers_report_problems(tmp_path):
    with pytest.raises(generic_pipeline.PipelineError, match="is missing"):
        generic_pipeline.load_rdf(tmp_path / "missing.ttl")
    data = tmp_path / "data.ttl"
    data.write_text(PEOPLE, encoding="utf-8")
    with pytest.raises(generic_pipeline.PipelineError, match="Unsupported RDF format"):
        generic_pipeline.export_rdf(data, "csv")
    content, media_type, extension = generic_pipeline.export_rdf(data, "ntriples")
    assert (media_type, extension) == ("application/n-triples", "nt")
    assert len(Graph().parse(data=content, format="nt")) == 4


def test_validation_results_are_ordered_and_capped():
    data = Graph().parse(data="""
        @prefix ex: <https://example.org/> .
        ex:a a ex:Person . ex:b a ex:Person . ex:c a ex:Person ; ex:age -1 .
    """, format="turtle")
    shapes = Graph().parse(data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <https://example.org/> .
        ex:S a sh:NodeShape ; sh:targetClass ex:Person ;
            sh:property [ sh:path ex:name ; sh:minCount 1 ; sh:severity sh:Warning ] ;
            sh:property [ sh:path ex:age ; sh:minInclusive 0 ] .
    """, format="turtle")

    result = shacl_engine.validate(data, shapes, result_limit=2)

    assert result["total_results"] == 4
    assert result["severity_counts"] == {"Violation": 1, "Warning": 3, "Info": 0}
    assert result["truncated"] is True and len(result["results"]) == 2
    assert result["results"][0]["severity"] == "Violation"
    assert shacl_engine.shapes_summary(shapes) == {"node_shapes": 1, "property_shapes": 2, "sparql_constraints": 0, "rules": 0}


# --- Built-in query operations -----------------------------------------------------------

SAMPLE_PARAMETERS = {
    "graph": "https://example.org/graphs/people",
    "type": "https://example.org/Person",
    "entity": "https://example.org/alice",
    "text": 'say "hello") } DROP ALL { ',
    "limit": 25,
}


@pytest.mark.parametrize("operation_id", list(operations.OPERATIONS))
def test_every_operation_builds_valid_sparql(operation_id):
    operation = operations.OPERATIONS[operation_id]
    parameters = {parameter.name: SAMPLE_PARAMETERS[parameter.name] for parameter in operation.parameters}
    query = operations.build_query(operation_id, parameters)
    prepareQuery(query)
    if "text" in parameters:
        assert 'LCASE("say \\"hello\\") } DROP ALL {")' in query  # trimmed, and still one string literal


@pytest.mark.parametrize(("parameters", "message"), [
    ({}, "Named graph is required"),
    ({"graph": "not an iri"}, "complete IRI"),
    ({"graph": SAMPLE_PARAMETERS["graph"], "limit": 0}, "at least 1"),
    ({"graph": SAMPLE_PARAMETERS["graph"], "limit": 1001}, "at most 1000"),
    ({"graph": SAMPLE_PARAMETERS["graph"], "limit": "many"}, "whole number"),
])
def test_operation_parameters_are_validated(parameters, message):
    with pytest.raises(operations.OperationError, match=message):
        operations.build_query("entity_types", parameters)


def test_search_text_is_escaped_and_limited():
    query = operations.build_query("search_text", {"graph": SAMPLE_PARAMETERS["graph"], "text": 'a"b\\c'})
    assert 'LCASE("a\\"b\\\\c")' in query
    prepareQuery(query)
    with pytest.raises(operations.OperationError, match="500 characters"):
        operations.build_query("search_text", {"graph": SAMPLE_PARAMETERS["graph"], "text": "x" * 501})


def test_unknown_operations_are_not_found(client):
    assert client.post("/api/store/operations/drop_everything", json={"parameters": {}}).status_code == 404
    assert client.post("/api/store/query", json={"query": "   "}).status_code == 400


# --- Fuseki client -----------------------------------------------------------------------


def test_graph_names_skip_blank_node_graphs(monkeypatch):
    rows = [{"graph": {"type": "uri", "value": "https://example.org/g"}}, {"graph": {"type": "bnode", "value": "b0"}}]
    monkeypatch.setattr(ingest, "query_graph", lambda query: {"rows": rows})
    assert ingest.list_graph_names() == ["https://example.org/g"]


def test_query_results_are_capped(monkeypatch):
    bindings = [{"s": {"type": "uri", "value": f"https://example.org/{index}"}} for index in range(5)]
    body = {"head": {"vars": ["s"]}, "results": {"bindings": bindings}}
    monkeypatch.setattr(ingest, "MAX_QUERY_ROWS", 3)
    monkeypatch.setattr(ingest.requests, "post", lambda *a, **k: Response(body=body))
    result = ingest.query_graph("SELECT ?s WHERE { ?s ?p ?o }")
    assert (result["row_count"], result["truncated"]) == (3, True)


def test_run_query_rejects_unexpected_answers(monkeypatch, tmp_path):
    destination = tmp_path / "out.nt"
    monkeypatch.setattr(ingest.requests, "post", lambda *a, **k: Response(content_type="text/html", body=b"<html>"))
    with pytest.raises(ingest.FusekiError, match="unexpected content type"):
        ingest.run_query("SELECT * {}", graph_destination=destination)

    monkeypatch.setattr(ingest.requests, "post", lambda *a, **k: Response(status_code=400, content_type="text/plain", body=b"Parse error"))
    with pytest.raises(ingest.FusekiError) as error:
        ingest.run_query("SELECT", graph_destination=destination)
    assert error.value.status_code == 400

    def unreachable(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(ingest.requests, "post", unreachable)
    with pytest.raises(ingest.FusekiError, match="request failed"):
        ingest.run_query("SELECT * {}", graph_destination=destination)


def test_put_graph_reports_failures(monkeypatch, tmp_path):
    path = tmp_path / "g.nt"
    path.write_bytes(b"")
    monkeypatch.setattr(ingest.requests, "put", lambda *a, **k: Response(status_code=500, content_type="text/plain", body=b"disk full"))
    with pytest.raises(ingest.FusekiError, match="disk full") as error:
        ingest.put_graph(path, "https://example.org/g")
    assert error.value.status_code == 500


# --- Agent orchestration edge cases ------------------------------------------------------


def test_agents_can_ask_and_describe(monkeypatch):
    stored = []
    monkeypatch.setattr(ingest, "list_graph_names", lambda: [])
    monkeypatch.setattr(ingest, "put_graph", lambda path, graph: stored.append((graph, Path(path).read_bytes())))

    monkeypatch.setattr(ingest.requests, "post", lambda *a, **k: Response(body={"head": {}, "boolean": True}))
    assert orchestration.run_agent("ASK {}", [], "env123", "agent111")["type"] == "ask"

    triple = b"<https://example.org/a> <https://example.org/p> <https://example.org/b> .\n"
    monkeypatch.setattr(ingest.requests, "post", lambda *a, **k: Response(content_type="application/n-triples", body=triple))
    described = orchestration.run_agent("DESCRIBE <https://example.org/a>", [], "env123", "agent111")
    assert described["type"] == "graph" and described["triples"] == 1
    assert stored == [(f"{orchestration.OUTPUT_BASE}env123/agent111", triple)]


def test_agents_read_from_at_most_fifty_graphs():
    sources = [f"https://example.org/graphs/{index}" for index in range(51)]
    with pytest.raises(orchestration.OrchestrationError, match="at most 50"):
        orchestration.run_agent("SELECT * {}", sources, "env123", "agent111")


def test_unreachable_fuseki_is_a_bad_gateway_for_agents(client, monkeypatch):
    def unreachable(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(ingest.requests, "post", unreachable)
    response = client.post("/api/orchestration/run", json={
        "environment_id": "env123", "agent_id": "agent111", "query": "SELECT * {}", "sources": [],
    })
    assert response.status_code == 502
    assert "request failed" in response.json()["detail"]
