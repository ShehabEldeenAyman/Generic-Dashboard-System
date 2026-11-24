from io import BytesIO
from datetime import datetime
import shutil

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from rdflib import Graph, URIRef

from pipeline import generic_pipeline
from pipeline import playground_server
from pipeline.run_store import RunStore
from triple_store_ingestion import ingest as fuseki_ingest


def test_upload_csv_creates_run_and_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(playground_server, "RUN_STORE", RunStore(tmp_path / "runs"))
    client = TestClient(playground_server.app)

    response = client.post(
        "/api/runs",
        files={"file": ("inventory.csv", b"sku,price\nA-1,10\nB-2,20\n", "text/csv")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stages"]["upload"]["status"] == "success"
    assert payload["source"]["stored_filename"] == "inventory.csv"
    assert payload["source"]["preview"]["columns"] == ["sku", "price"]
    assert payload["source"]["preview"]["total_rows"] == 2
    assert "relative_path" not in payload["artifacts"][0]


def test_upload_xlsx_creates_preview_and_rml_csv_source(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    client = TestClient(playground_server.app)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Inventory"
    worksheet.append(["sku", "price", "available"])
    worksheet.append(["A-1", 10.5, True])
    worksheet.append(["B-2", 20, False])
    workbook.create_sheet("Notes").append(["This sheet is not active"])
    content = BytesIO()
    workbook.save(content)
    workbook.close()

    response = client.post(
        "/api/runs",
        files={
            "file": (
                "inventory.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stages"]["upload"]["status"] == "success"
    assert payload["source"]["stored_filename"] == "inventory.xlsx"
    assert payload["source"]["mapping_source_filename"] == "inventory.csv"
    assert payload["source"]["preview"]["format"] == "xlsx"
    assert payload["source"]["preview"]["sheet_name"] == "Inventory"
    assert payload["source"]["preview"]["columns"] == ["sku", "price", "available"]
    assert payload["source"]["preview"]["rows"][0] == {
        "sku": "A-1",
        "price": "10.5",
        "available": "True",
    }
    assert {artifact["kind"] for artifact in payload["artifacts"]} == {"xlsx", "csv"}

    saved = run_store.load(payload["id"])
    mapping_source = run_store.resolve_relative(payload["id"], saved["source"]["relative_path"])
    assert mapping_source.name == "inventory.csv"
    assert mapping_source.read_text(encoding="utf-8").splitlines() == [
        "sku,price,available",
        "A-1,10.5,True",
        "B-2,20,False",
    ]

    workbook_artifact = next(item for item in payload["artifacts"] if item["kind"] == "xlsx")
    preview_response = client.get(workbook_artifact["preview_url"])
    assert preview_response.status_code == 200
    assert preview_response.json()["table"]["sheet_name"] == "Inventory"


def test_upload_xlsx_normalizes_multirow_headers_and_date_time(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    client = TestClient(playground_server.app)

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Measurements"
    worksheet.append([None, None, "Ambient temperature"])
    worksheet.append(["Date", "Time", "SENSOR_A_TEMPERATURE"])
    worksheet.append(["unit", None, "degC"])
    worksheet.append([datetime(2025, 1, 1), "00:00:00", 4.679602775605543])
    worksheet.append([datetime(2025, 1, 1), "00:15:00", 4.023384243091742])
    content = BytesIO()
    workbook.save(content)
    workbook.close()

    response = client.post(
        "/api/runs",
        files={
            "file": (
                "data.xlsx",
                content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    value_column = "Ambient temperature | SENSOR_A_TEMPERATURE | degC"
    assert payload["source"]["preview"]["columns"] == ["DateTime", value_column]
    assert payload["source"]["preview"]["header_row_count"] == 3
    assert payload["source"]["preview"]["data_start_row"] == 4
    assert payload["source"]["preview"]["rows"] == [
        {"DateTime": "2025-01-01T00:00:00", value_column: "4.679602775605543"},
        {"DateTime": "2025-01-01T00:15:00", value_column: "4.023384243091742"},
    ]

    saved = run_store.load(payload["id"])
    mapping_source = run_store.resolve_relative(payload["id"], saved["source"]["relative_path"])
    assert mapping_source.read_text(encoding="utf-8").splitlines() == [
        f"DateTime,{value_column}",
        "2025-01-01T00:00:00,4.679602775605543",
        "2025-01-01T00:15:00,4.023384243091742",
    ]


def test_upload_rejects_unsupported_tabular_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(playground_server, "RUN_STORE", RunStore(tmp_path / "runs"))
    client = TestClient(playground_server.app)

    response = client.post(
        "/api/runs",
        files={"file": ("inventory.xls", b"legacy workbook", "application/vnd.ms-excel")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Please upload a .csv or .xlsx file."


def test_delete_run_removes_uploaded_file_and_artifacts(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    client = TestClient(playground_server.app)
    upload = client.post(
        "/api/runs",
        files={"file": ("inventory.csv", b"sku,price\nA-1,10\n", "text/csv")},
    )
    run_id = upload.json()["id"]
    run_directory = run_store.run_dir(run_id)
    assert run_directory.is_dir()

    response = client.delete(f"/api/runs/{run_id}")

    assert response.status_code == 204
    assert response.content == b""
    assert not run_directory.exists()
    assert client.get(f"/api/runs/{run_id}").status_code == 404


def test_graph_name_is_converted_to_a_safe_named_graph_uri():
    uri = generic_pipeline.graph_name_to_uri("Quarterly products")
    assert uri == "https://example.org/graphs/Quarterly%20products"
    assert generic_pipeline.graph_name_to_uri("https://data.example/graphs/items") == (
        "https://data.example/graphs/items"
    )


def test_ingest_graph_clears_named_graph_before_upload(tmp_path, monkeypatch):
    rdf_path = tmp_path / "mapped.ttl"
    rdf_path.write_text("<https://example.org/s> <https://example.org/p> <https://example.org/o> .")
    calls = []

    monkeypatch.setattr(
        generic_pipeline.ingest,
        "delete_graph",
        lambda graph_uri: calls.append(("clear", graph_uri)) or True,
    )
    monkeypatch.setattr(
        generic_pipeline.ingest,
        "upload_graph",
        lambda path, graph_uri, replace=True: calls.append(("upload", graph_uri, path, replace)) or True,
    )

    result = generic_pipeline.ingest_graph(rdf_path, "replacement graph")

    graph_uri = "https://example.org/graphs/replacement%20graph"
    assert calls == [("clear", graph_uri), ("upload", graph_uri, str(rdf_path), True)]
    assert result == {"graph_uri": graph_uri, "mode": "replace", "graph_cleared": True}


def test_ingest_graph_aborts_when_named_graph_cannot_be_cleared(tmp_path, monkeypatch):
    rdf_path = tmp_path / "mapped.ttl"
    rdf_path.write_text("<https://example.org/s> <https://example.org/p> <https://example.org/o> .")
    upload_called = False

    monkeypatch.setattr(generic_pipeline.ingest, "delete_graph", lambda _graph_uri: False)

    def upload_graph(_path, _graph_uri, replace=True):
        nonlocal upload_called
        upload_called = True
        return True

    monkeypatch.setattr(generic_pipeline.ingest, "upload_graph", upload_graph)

    with pytest.raises(generic_pipeline.PipelineError, match="No data was uploaded"):
        generic_pipeline.ingest_graph(rdf_path, "replacement graph")
    assert upload_called is False


def test_fuseki_query_leaves_named_graph_selection_to_query(monkeypatch):
    captured = {}

    class Response:
        ok = True
        status_code = 200
        text = ""
        headers = {"Content-Type": "application/sparql-results+json; charset=utf-8"}

        @staticmethod
        def json():
            return {
                "head": {"vars": ["subject"]},
                "results": {
                    "bindings": [
                        {"subject": {"type": "uri", "value": "https://example.org/item"}}
                    ]
                },
            }

    def post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr(fuseki_ingest.requests, "post", post)

    query = """
        SELECT ?subject
        WHERE {
          GRAPH <https://example.org/graphs/items> {
            ?subject ?predicate ?object
          }
        }
    """
    result = fuseki_ingest.query_graph(query)

    assert captured["data"] == {"query": query}
    assert "default-graph-uri" not in captured["data"]
    assert result["type"] == "select"
    assert result["variables"] == ["subject"]
    assert result["rows"][0]["subject"]["value"] == "https://example.org/item"


def test_mapped_rdf_preview_paginates_by_subject(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("items.csv", "items.csv")
    state["stages"]["rml"] = {"status": "success"}
    run_store.save(state)
    mapped_path = run_store.run_dir(state["id"]) / "mapped.ttl"
    graph = Graph()
    predicate = URIRef("https://example.org/value")
    for index in range(205):
        graph.add((URIRef(f"https://example.org/item/{index:03d}"), predicate, URIRef(f"urn:value:{index}")))
    graph.serialize(destination=mapped_path, format="turtle")
    client = TestClient(playground_server.app)

    first = client.get(f"/api/runs/{state['id']}/rdf-preview?offset=0&limit=10")
    last = client.get(f"/api/runs/{state['id']}/rdf-preview?offset=200&limit=10")

    assert first.status_code == 200
    assert first.json()["returned_instances"] == 10
    assert first.json()["total_instances"] == 205
    assert first.json()["has_previous"] is False
    assert first.json()["has_next"] is True
    assert last.json()["returned_instances"] == 5
    assert last.json()["has_previous"] is True
    assert last.json()["has_next"] is False
    assert "item/204" in last.json()["text"]


@pytest.mark.skipif(
    not generic_pipeline.RML_MAPPER_JAR.is_file() or not shutil.which("java"),
    reason="RMLMapper and Java are required for the integration test.",
)
def test_user_supplied_rml_mapping_runs_against_uploaded_filename(tmp_path):
    source = tmp_path / "inventory.csv"
    source.write_text("id,name\n1,Desk lamp\n", encoding="utf-8")
    mapping = """
        @prefix ex: <https://example.org/> .
        @prefix ql: <http://semweb.mmlab.be/ns/ql#> .
        @prefix rml: <http://semweb.mmlab.be/ns/rml#> .
        @prefix rr: <http://www.w3.org/ns/r2rml#> .

        <#Items> a rr:TriplesMap ;
          rml:logicalSource [ rml:source "inventory.csv" ; rml:referenceFormulation ql:CSV ] ;
          rr:subjectMap [ rr:template "https://example.org/items/{id}" ; rr:class ex:Item ] ;
          rr:predicateObjectMap [ rr:predicate ex:name ; rr:objectMap [ rml:reference "name" ] ] .
    """

    result = generic_pipeline.run_rml_mapping(tmp_path, source, mapping)

    graph = Graph().parse(result["output_path"], format="turtle")
    assert (URIRef("https://example.org/items/1"), None, None) in graph


@pytest.mark.skipif(
    not generic_pipeline.RML_MAPPER_JAR.is_file() or not shutil.which("java"),
    reason="RMLMapper and Java are required for the integration test.",
)
def test_normalized_multirow_xlsx_runs_with_user_mapping(tmp_path):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Measurements"
    worksheet.append([None, None, "Ambient temperature"])
    worksheet.append(["Date", "Time", "SENSOR_A_TEMPERATURE"])
    worksheet.append(["unit", None, "degC"])
    worksheet.append([datetime(2025, 1, 1), "00:00:00", 4.679602775605543])
    source_xlsx = tmp_path / "data.xlsx"
    source_csv = tmp_path / "data.csv"
    workbook.save(source_xlsx)
    workbook.close()

    preview = generic_pipeline.xlsx_preview(source_xlsx)
    generic_pipeline.xlsx_to_csv(source_xlsx, source_csv, preview)
    mapping = """
        @base <http://example.com/observations/> .
        @prefix rr: <http://www.w3.org/ns/r2rml#> .
        @prefix rml: <http://semweb.mmlab.be/ns/rml#> .
        @prefix ql: <http://semweb.mmlab.be/ns/ql#> .
        @prefix sosa: <http://www.w3.org/ns/sosa/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix qudt: <http://qudt.org/schema/qudt/> .
        @prefix unit: <http://qudt.org/vocab/unit/> .
        @prefix quantitykind: <https://qudt.org/vocab/quantitykind/> .

        <#SensorMapping> a rr:TriplesMap ;
          rml:logicalSource [
            rml:source "data.csv" ;
            rml:referenceFormulation ql:CSV
          ] ;
          rr:subjectMap [
            rr:template "https://example.org/observations/temperature-1/{DateTime}" ;
            rr:class sosa:Observation
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:madeBySensor ;
            rr:objectMap [ rr:constant <https://example.org/sensors/temperature-1> ; rr:termType rr:IRI ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:resultTime ;
            rr:objectMap [ rml:reference "DateTime" ; rr:datatype xsd:dateTime ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:hasSimpleResult ;
            rr:objectMap [
              rml:reference "Ambient temperature | SENSOR_A_TEMPERATURE | degC" ;
              rr:datatype xsd:double
            ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:observedProperty ;
            rr:objectMap [ rr:constant quantitykind:Temperature ; rr:termType rr:IRI ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate qudt:hasUnit ;
            rr:objectMap [ rr:constant unit:DEG_C ; rr:termType rr:IRI ]
          ] .
    """

    result = generic_pipeline.run_rml_mapping(tmp_path, source_csv, mapping)

    graph = Graph().parse(result["output_path"], format="turtle")
    assert result["rdf_triples"] == 6
    assert (
        URIRef("https://example.org/observations/temperature-1/2025-01-01T00%3A00%3A00"),
        URIRef("http://www.w3.org/ns/sosa/hasSimpleResult"),
        None,
    ) in graph


# --- Ingestion modes ---------------------------------------------------------------------


def test_ingest_graph_append_mode_does_not_clear_the_graph(tmp_path, monkeypatch):
    rdf_path = tmp_path / "mapped.ttl"
    rdf_path.write_text("<https://example.org/s> <https://example.org/p> <https://example.org/o> .")
    calls = []
    monkeypatch.setattr(
        generic_pipeline.ingest, "delete_graph", lambda graph_uri: calls.append("clear") or True
    )
    monkeypatch.setattr(
        generic_pipeline.ingest,
        "upload_graph",
        lambda path, graph_uri, replace=True: calls.append(("upload", replace)) or True,
    )

    result = generic_pipeline.ingest_graph(rdf_path, "items", mode="append")

    assert calls == [("upload", False)]
    assert result["mode"] == "append"
    assert result["graph_cleared"] is False


def test_upload_graph_uses_put_to_replace_and_post_to_append(tmp_path, monkeypatch):
    rdf_path = tmp_path / "mapped.ttl"
    rdf_path.write_text("<https://example.org/s> <https://example.org/p> <https://example.org/o> .")
    methods = []

    class Response:
        status_code = 204
        text = ""

    monkeypatch.setattr(fuseki_ingest.requests, "put", lambda *a, **k: methods.append("PUT") or Response())
    monkeypatch.setattr(fuseki_ingest.requests, "post", lambda *a, **k: methods.append("POST") or Response())

    assert fuseki_ingest.upload_graph(str(rdf_path), "https://example.org/g", replace=True)
    assert fuseki_ingest.upload_graph(str(rdf_path), "https://example.org/g", replace=False)
    assert methods == ["PUT", "POST"]


# --- SHACL validation and rules ----------------------------------------------------------

SHACL_DATA = """
    @prefix ex: <https://example.org/> .
    ex:alice a ex:Person ; ex:age 200 ; ex:name "Alice" .
    ex:bob a ex:Person .
"""

SHACL_SHAPES = """
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <https://example.org/> .
    ex:PersonShape a sh:NodeShape ;
        sh:targetClass ex:Person ;
        sh:property [
            sh:path ex:age ; sh:minCount 1 ; sh:maxInclusive 150 ;
            sh:message "Age is missing or implausible."
        ] ;
        sh:property [ sh:path ex:name ; sh:minCount 1 ; sh:severity sh:Warning ] ;
        sh:sparql [
            sh:message "Every person needs a registration."  ;
            sh:select "SELECT $this WHERE { FILTER NOT EXISTS { $this <https://example.org/registered> ?r } }"
        ] .
"""

SHACL_RULES = """
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    @prefix ex: <https://example.org/> .
    ex:PersonRules a sh:NodeShape ;
        sh:targetClass ex:Person ;
        sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate ex:registered ; sh:object true ] ;
        sh:rule [ a sh:SPARQLRule ; sh:construct "CONSTRUCT { $this a <https://example.org/Agent> } WHERE { }" ] .
"""


def test_shacl_validation_returns_structured_results_with_sparql_constraints(tmp_path):
    data_path = tmp_path / "mapped.ttl"
    data_path.write_text(SHACL_DATA, encoding="utf-8")

    result = generic_pipeline.run_shacl_validation(tmp_path, data_path, SHACL_SHAPES)

    assert result["conforms"] is False
    assert result["severity_counts"] == {"Violation": 4, "Warning": 1, "Info": 0}
    assert result["shapes"] == {
        "node_shapes": 1, "property_shapes": 2, "sparql_constraints": 1, "rules": 0,
    }
    first = result["results"][0]
    assert first["severity"] == "Violation"
    assert {item["constraint"] for item in result["results"]} >= {"MaxInclusive", "MinCount", "SPARQL"}
    implausible = next(item for item in result["results"] if item["constraint"] == "MaxInclusive")
    assert implausible == {
        "severity": "Violation",
        "focus_node": "https://example.org/alice",
        "path": "https://example.org/age",
        "value": "200",
        "message": "Age is missing or implausible.",
        "constraint": "MaxInclusive",
        "source_shape": None,
    }
    assert result["report_path"].read_text(encoding="utf-8").startswith("Validation Report")


def test_shacl_validation_rejects_invalid_shapes(tmp_path):
    data_path = tmp_path / "mapped.ttl"
    data_path.write_text(SHACL_DATA, encoding="utf-8")
    with pytest.raises(generic_pipeline.PipelineError, match="not valid Turtle"):
        generic_pipeline.run_shacl_validation(tmp_path, data_path, "this is not turtle")


def test_shacl_rules_materialise_inferred_triples(tmp_path):
    data_path = tmp_path / "mapped.ttl"
    data_path.write_text(SHACL_DATA, encoding="utf-8")

    result = generic_pipeline.run_shacl_rules(tmp_path, data_path, SHACL_RULES)

    enriched = Graph().parse(result["output_path"], format="turtle")
    assert result["inferred_triples"] == 4
    assert result["total_triples"] == result["input_triples"] + 4 == len(enriched)
    assert (URIRef("https://example.org/bob"), URIRef("https://example.org/registered"), None) in enriched
    assert Graph().parse(data_path, format="turtle").__len__() == result["input_triples"]


def test_shacl_rules_require_at_least_one_rule(tmp_path):
    data_path = tmp_path / "mapped.ttl"
    data_path.write_text(SHACL_DATA, encoding="utf-8")
    with pytest.raises(generic_pipeline.PipelineError, match="sh:rule"):
        generic_pipeline.run_shacl_rules(tmp_path, data_path, SHACL_SHAPES)


def _mapped_run(tmp_path, monkeypatch, data=SHACL_DATA):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("people.csv", "people.csv")
    state["stages"]["upload"] = {"status": "success", "artifacts": []}
    state["stages"]["rml"] = {"status": "success", "artifacts": []}
    run_store.save(state)
    (run_store.run_dir(state["id"]) / "mapped.ttl").write_text(data, encoding="utf-8")
    return run_store, state, TestClient(playground_server.app)


def test_rules_enrich_the_rdf_used_by_validation_and_ingestion(tmp_path, monkeypatch):
    run_store, state, client = _mapped_run(tmp_path, monkeypatch)
    run_id = state["id"]
    sparql_only = SHACL_SHAPES.split("sh:property [\n            sh:path ex:age")[0] + """
        sh:sparql [
            sh:message "Every person needs a registration." ;
            sh:select "SELECT $this WHERE { FILTER NOT EXISTS { $this <https://example.org/registered> ?r } }"
        ] .
    """

    before = client.post(f"/api/runs/{run_id}/stages/shacl", json={"shapes": sparql_only}).json()
    rules = client.post(
        f"/api/runs/{run_id}/stages/shacl-rules",
        json={"shapes": SHACL_RULES, "source_name": "rules.ttl"},
    ).json()
    after = client.post(f"/api/runs/{run_id}/stages/shacl", json={"shapes": sparql_only}).json()

    captured = {}

    def ingest_graph(path, graph_name, mode):
        captured.update({"path": path.name, "graph_name": graph_name, "mode": mode})
        return {"graph_uri": "https://example.org/graphs/people", "mode": mode, "graph_cleared": True}

    monkeypatch.setattr(generic_pipeline, "ingest_graph", ingest_graph)
    ingested = client.post(
        f"/api/runs/{run_id}/stages/ingest", json={"graph_name": "people", "mode": "replace"}
    ).json()

    assert before["stages"]["shacl"]["status"] == "nonconformant"
    assert before["stages"]["shacl"]["details"]["severity_counts"]["Violation"] == 2
    assert rules["stages"]["rules"]["status"] == "success"
    assert rules["stages"]["rules"]["details"]["inferred_triples"] == 4
    assert rules["stages"]["rules"]["details"]["shapes_source"] == "uploaded file rules.ttl"
    assert "shacl" not in rules["stages"]
    assert after["stages"]["shacl"]["status"] == "success"
    assert after["stages"]["shacl"]["details"]["input_rdf"] == "enriched RDF"
    assert captured == {"path": "enriched.ttl", "graph_name": "people", "mode": "replace"}
    assert ingested["graph"]["uri"] == "https://example.org/graphs/people"


def test_rerunning_operations_clears_only_derived_results(tmp_path):
    run_store = RunStore(tmp_path / "runs")
    state = run_store.create("items.csv", "items.csv")
    state["stages"] = {
        stage: {"status": "success", "artifacts": []}
        for stage in ("upload", "rml", "rules", "shacl", "ingest")
    }
    state["graph"] = {"name": "items", "uri": "https://example.org/graphs/items"}
    run_store.save(state)

    state = run_store.begin_stage(state, "shacl")
    assert set(state["stages"]) == {"upload", "rml", "rules", "shacl", "ingest"}
    assert state["graph"] is not None

    state = run_store.begin_stage(state, "rules")
    assert set(state["stages"]) == {"upload", "rml", "rules"}
    assert state["graph"] is None


# --- RDF download ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rdf_format", "parser", "extension"),
    [("turtle", "turtle", "ttl"), ("ntriples", "nt", "nt"), ("jsonld", "json-ld", "jsonld"), ("xml", "xml", "rdf")],
)
def test_download_current_rdf_in_each_format(tmp_path, monkeypatch, rdf_format, parser, extension):
    _run_store, state, client = _mapped_run(tmp_path, monkeypatch)

    response = client.get(f"/api/runs/{state['id']}/rdf", params={"format": rdf_format})

    assert response.status_code == 200
    assert f'filename="people-mapped.{extension}"' in response.headers["content-disposition"]
    graph = Graph().parse(data=response.content, format=parser)
    assert len(graph) == len(Graph().parse(data=SHACL_DATA, format="turtle"))


def test_download_rdf_requires_a_mapping(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("people.csv", "people.csv")
    client = TestClient(playground_server.app)
    assert client.get(f"/api/runs/{state['id']}/rdf").status_code == 409


# --- Triple store query and operations ---------------------------------------------------


def test_operations_build_safe_queries():
    from query_agent import operations

    query = operations.build_query(
        "search_text",
        {"graph": "https://example.org/graphs/items", "text": 'Desk "lamp"\\', "limit": 5},
    )
    assert 'LCASE("Desk \\"lamp\\"\\\\")' in query
    assert "GRAPH <https://example.org/graphs/items>" in query
    assert query.rstrip().endswith("LIMIT 5")

    for bad_graph in ("not an iri", "https://example.org/g> } DROP ALL {", ""):
        with pytest.raises(operations.OperationError):
            operations.build_query("sample_triples", {"graph": bad_graph})
    with pytest.raises(operations.OperationError, match="at most 1000"):
        operations.build_query("sample_triples", {"graph": "https://example.org/g", "limit": 5000})


def test_store_operations_api_lists_and_runs_operations(monkeypatch):
    from query_agent import operations

    captured = {}

    def query_graph(query):
        captured["query"] = query
        return {"type": "select", "variables": ["type", "entities"], "rows": [], "row_count": 0, "truncated": False}

    monkeypatch.setattr(operations.ingest, "query_graph", query_graph)
    client = TestClient(playground_server.app)

    catalog = client.get("/api/store/operations").json()["operations"]
    response = client.post(
        "/api/store/operations/entity_types",
        json={"parameters": {"graph": "https://example.org/graphs/items"}},
    )

    assert {item["id"] for item in catalog} >= {"graph_overview", "entity_types", "search_text"}
    assert response.status_code == 200
    assert response.json()["query"] == captured["query"]
    assert "LIMIT 50" in captured["query"]
    assert client.post("/api/store/operations/nope", json={}).status_code == 404
    assert client.post(
        "/api/store/operations/entity_types", json={"parameters": {}}
    ).status_code == 400


def test_store_graphs_lists_named_graphs(monkeypatch):
    from query_agent import operations

    def query_graph(query):
        if "GRAPH ?graph" in query:
            rows = [{"graph": {"type": "uri", "value": "https://example.org/graphs/a"},
                     "triples": {"type": "literal", "value": "42"}}]
        else:
            rows = [{"triples": {"type": "literal", "value": "3"}}]
        return {"type": "select", "variables": [], "rows": rows, "row_count": len(rows), "truncated": False}

    monkeypatch.setattr(operations.ingest, "query_graph", query_graph)
    client = TestClient(playground_server.app)

    assert client.get("/api/store/graphs").json() == {
        "graphs": [{"uri": "https://example.org/graphs/a", "triples": 42}],
        "default_graph_triples": 3,
    }


def test_store_query_reports_fuseki_failures_as_bad_gateway(monkeypatch):
    def query_graph(_query):
        raise fuseki_ingest.FusekiError("Fuseki query request failed: connection refused")

    monkeypatch.setattr(playground_server.ingest, "query_graph", query_graph)
    client = TestClient(playground_server.app)

    response = client.post("/api/store/query", json={"query": "ASK {}"})
    assert response.status_code == 502
    assert "connection refused" in response.json()["detail"]
    assert client.post("/api/store/query", json={"query": "   "}).status_code == 400


def test_store_query_reports_rejected_queries_as_bad_request(monkeypatch):
    def query_graph(_query):
        raise fuseki_ingest.FusekiError("Fuseki query failed with HTTP 400: Parse error", 400)

    monkeypatch.setattr(playground_server.ingest, "query_graph", query_graph)
    response = TestClient(playground_server.app).post("/api/store/query", json={"query": "DROP ALL"})
    assert response.status_code == 400
