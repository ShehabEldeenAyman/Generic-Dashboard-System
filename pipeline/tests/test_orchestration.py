"""Tests for agent orchestration: running SPARQL agents and keeping their CONSTRUCT outputs."""

import json

from fastapi.testclient import TestClient
import pytest

from pipeline import playground_server
from query_agent import orchestration
from triple_store_ingestion import ingest

BASE = orchestration.OUTPUT_BASE
PUBLISHED = "https://example.org/graphs/waterinfo-sample"
SELECT_JSON = {
    "head": {"vars": ["sensor"]},
    "results": {"bindings": [{"sensor": {"type": "uri", "value": "https://example.org/A"}}]},
}
CONSTRUCTED = (
    '<https://example.org/r1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://example.org/Alert> .\n'
    '<https://example.org/r1> <https://example.org/value> "20000"^^<http://www.w3.org/2001/XMLSchema#integer> .\n'
)


class FakeResponse:
    def __init__(self, status_code=200, content_type="application/sparql-results+json", body=b""):
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = {"Content-Type": content_type}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text(self):
        return self._body.decode("utf-8")

    def json(self):
        return json.loads(self._body)

    def iter_content(self, chunk_size=1):
        for start in range(0, len(self._body), 7):
            yield self._body[start : start + 7]


@pytest.fixture
def fuseki(monkeypatch):
    """Record what reaches Fuseki and answer with a prepared response."""
    calls = {"posts": [], "puts": [], "deleted": []}
    state = {"response": FakeResponse(body=json.dumps(SELECT_JSON).encode()), "graphs": [PUBLISHED]}

    def post(url, data=None, headers=None, stream=False, timeout=None):
        calls["posts"].append({"url": url, "data": data, "headers": headers})
        return state["response"]

    def put(url, params=None, data=None, headers=None, timeout=None):
        calls["puts"].append({"graph": params["graph"], "body": data.read(), "headers": headers})
        return FakeResponse(status_code=201)

    def delete_graph(graph_uri):
        calls["deleted"].append(graph_uri)
        return True

    monkeypatch.setattr(ingest.requests, "post", post)
    monkeypatch.setattr(ingest.requests, "put", put)
    monkeypatch.setattr(ingest, "list_graph_names", lambda: list(state["graphs"]))
    monkeypatch.setattr(ingest, "delete_graph", delete_graph)
    return calls, state


def test_output_graphs_are_named_from_validated_ids():
    assert orchestration.output_graph("env123", "agent456") == f"{BASE}env123/agent456"
    for environment_id, agent_id in [("ENV123", "agent456"), ("env123", "a/b/cd"), ("env", "agent456")]:
        with pytest.raises(orchestration.OrchestrationError, match="lowercase letters or digits"):
            orchestration.output_graph(environment_id, agent_id)


def test_sources_become_the_default_graph_and_all_graphs_stay_reachable(fuseki):
    calls, state = fuseki
    state["graphs"] = [PUBLISHED, f"{BASE}env123/agent111"]

    result = orchestration.run_agent(
        "SELECT ?sensor WHERE { ?r a <https://example.org/Alert> }",
        [f"{BASE}env123/agent111", PUBLISHED, PUBLISHED],
        "env123",
        "agent222",
    )

    data = calls["posts"][0]["data"]
    assert [value for key, value in data if key == "default-graph-uri"] == [f"{BASE}env123/agent111", PUBLISHED]
    assert [value for key, value in data if key == "named-graph-uri"] == [PUBLISHED, f"{BASE}env123/agent111"]
    assert result["type"] == "select"
    assert result["rows"][0]["sensor"]["value"] == "https://example.org/A"
    assert result["sources"] == [f"{BASE}env123/agent111", PUBLISHED]
    assert not calls["puts"]


def test_without_sources_the_query_uses_fusekis_own_dataset(fuseki):
    calls, _state = fuseki
    orchestration.run_agent("ASK { GRAPH ?g { ?s ?p ?o } }", [], "env123", "agent222")
    assert [key for key, _value in calls["posts"][0]["data"]] == ["query"]


def test_construct_output_replaces_the_agents_output_graph(fuseki):
    calls, state = fuseki
    state["response"] = FakeResponse(content_type="application/n-triples", body=CONSTRUCTED.encode())

    result = orchestration.run_agent("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }", [PUBLISHED], "env123", "agent111")

    assert result["type"] == "graph"
    assert result["triples"] == 2
    assert result["output_graph"] == f"{BASE}env123/agent111"
    assert calls["puts"] == [{
        "graph": f"{BASE}env123/agent111",
        "body": CONSTRUCTED.encode(),
        "headers": {"Content-Type": "application/n-triples"},
    }]
    assert result["preview"]["variables"] == ["subject", "predicate", "object"]
    values = {row["object"]["value"] for row in result["preview"]["rows"]}
    assert values == {"https://example.org/Alert", "20000"}
    literal = next(row["object"] for row in result["preview"]["rows"] if row["object"]["type"] == "literal")
    assert literal["datatype"] == "http://www.w3.org/2001/XMLSchema#integer"


def test_an_empty_construct_result_empties_the_output_graph(fuseki):
    calls, state = fuseki
    state["response"] = FakeResponse(content_type="application/n-triples", body=b"")
    result = orchestration.run_agent("CONSTRUCT { ?s ?p ?o } WHERE { FILTER(false) }", [], "env123", "agent111")
    assert result["triples"] == 0
    assert calls["puts"][0]["body"] == b""


def test_an_agent_cannot_read_its_own_output(fuseki):
    with pytest.raises(orchestration.OrchestrationError, match="its own output"):
        orchestration.run_agent("SELECT * WHERE { ?s ?p ?o }", [f"{BASE}env123/agent111"], "env123", "agent111")


def test_drop_outputs_only_touches_the_environments_graphs(fuseki):
    calls, state = fuseki
    state["graphs"] = [PUBLISHED, f"{BASE}env123/agent111", f"{BASE}env123/agent222", f"{BASE}env999/agent111"]

    assert orchestration.drop_outputs("env123") == {"dropped": [f"{BASE}env123/agent111", f"{BASE}env123/agent222"]}
    assert orchestration.drop_outputs("env123", "agent333") == {"dropped": [f"{BASE}env123/agent333"]}
    assert calls["deleted"] == [f"{BASE}env123/agent111", f"{BASE}env123/agent222", f"{BASE}env123/agent333"]


def test_run_endpoint_returns_results_and_maps_errors(fuseki):
    calls, state = fuseki
    client = TestClient(playground_server.app)
    body = {"environment_id": "env123", "agent_id": "agent222", "query": "SELECT * WHERE { ?s ?p ?o }", "sources": [PUBLISHED]}

    assert client.post("/api/orchestration/run", json=body).json()["type"] == "select"

    bad_source = client.post("/api/orchestration/run", json={**body, "sources": ["not a graph"]})
    assert bad_source.status_code == 400
    assert "complete IRI" in bad_source.json()["detail"]

    bad_id = client.post("/api/orchestration/run", json={**body, "agent_id": "Agent 2"})
    assert bad_id.status_code == 400

    state["response"] = FakeResponse(status_code=400, content_type="text/plain", body=b"Parse error: line 1")
    syntax = client.post("/api/orchestration/run", json=body)
    assert syntax.status_code == 400
    assert "Parse error" in syntax.json()["detail"]

    state["response"] = FakeResponse(status_code=500, content_type="text/plain", body=b"boom")
    assert client.post("/api/orchestration/run", json=body).status_code == 502


def test_drop_endpoint_and_config(fuseki):
    calls, state = fuseki
    state["graphs"] = [f"{BASE}env123/agent111"]
    client = TestClient(playground_server.app)

    response = client.delete("/api/orchestration/environments/env123/outputs")
    assert response.json() == {"dropped": [f"{BASE}env123/agent111"]}
    assert client.delete("/api/orchestration/environments/BAD/outputs").status_code == 400
    assert client.get("/api/config").json()["orchestration_graph_base"] == BASE
