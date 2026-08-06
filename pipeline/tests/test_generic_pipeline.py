from io import BytesIO
from datetime import datetime
from pathlib import Path
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
    worksheet.append([None, None, "Conductivity dokwater + spui ABF"])
    worksheet.append(
        ["Datum", "Tijd", "ZHINDS10_WINCC_INDUSS_02_AT9103-B_FEED_CONDUCTIVITY"]
    )
    worksheet.append(["eenheid", None, "µs/cm"])
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
    value_column = (
        "Conductivity dokwater + spui ABF | "
        "ZHINDS10_WINCC_INDUSS_02_AT9103-B_FEED_CONDUCTIVITY | µs/cm"
    )
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
        lambda path, graph_uri: calls.append(("upload", graph_uri, path)) or True,
    )

    result = generic_pipeline.ingest_graph(rdf_path, "replacement graph")

    graph_uri = "https://example.org/graphs/replacement%20graph"
    assert calls == [("clear", graph_uri), ("upload", graph_uri, str(rdf_path))]
    assert result == {"graph_uri": graph_uri, "graph_cleared": True}


def test_ingest_graph_aborts_when_named_graph_cannot_be_cleared(tmp_path, monkeypatch):
    rdf_path = tmp_path / "mapped.ttl"
    rdf_path.write_text("<https://example.org/s> <https://example.org/p> <https://example.org/o> .")
    upload_called = False

    monkeypatch.setattr(generic_pipeline.ingest, "delete_graph", lambda _graph_uri: False)

    def upload_graph(_path, _graph_uri):
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


def test_sparql_api_queries_the_graph_saved_for_the_run(tmp_path, monkeypatch):
    run_store = RunStore(tmp_path / "runs")
    monkeypatch.setattr(playground_server, "RUN_STORE", run_store)
    state = run_store.create("items.csv", "items.csv")
    state["stages"]["ingest"] = {"status": "success"}
    state["graph"] = {
        "name": "items",
        "uri": "https://example.org/graphs/items",
    }
    run_store.save(state)
    captured = {}

    def run_query(query, graph_uri):
        captured.update({"query": query, "graph_uri": graph_uri})
        return {
            "type": "ask",
            "boolean": True,
            "graph_uri": graph_uri,
        }

    monkeypatch.setattr(generic_pipeline, "run_sparql_query", run_query)
    client = TestClient(playground_server.app)

    response = client.post(
        f"/api/runs/{state['id']}/sparql",
        json={"query": "ASK { ?subject ?predicate ?object }"},
    )

    assert response.status_code == 200
    assert response.json()["boolean"] is True
    assert captured == {
        "query": "ASK { ?subject ?predicate ?object }",
        "graph_uri": "https://example.org/graphs/items",
    }


def test_shacl_violation_returns_a_report_without_raising(tmp_path):
    data_path = tmp_path / "mapped.ttl"
    data_path.write_text(
        """
        @prefix ex: <https://example.org/> .
        ex:item ex:name "Example" .
        """,
        encoding="utf-8",
    )
    shapes = """
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix ex: <https://example.org/> .
        ex:ItemShape a sh:NodeShape ;
            sh:targetNode ex:item ;
            sh:property [ sh:path ex:price ; sh:minCount 1 ] .
    """

    result = generic_pipeline.run_shacl_validation(
        tmp_path, data_path, shapes, prefix="shacl_in"
    )

    assert result["conforms"] is False
    assert "Constraint Violation" in result["report"]
    assert result["report_path"].is_file()


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
    worksheet.append([None, None, "Conductivity dokwater + spui ABF"])
    worksheet.append(
        ["Datum", "Tijd", "ZHINDS10_WINCC_INDUSS_02_AT9103-B_FEED_CONDUCTIVITY"]
    )
    worksheet.append(["eenheid", None, "µs/cm"])
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
            rr:template "http://example.com/observations/111111111/{DateTime}" ;
            rr:class sosa:Observation
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:madeBySensor ;
            rr:objectMap [ rr:constant <http://example.com/waterlink/111111111> ; rr:termType rr:IRI ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:resultTime ;
            rr:objectMap [ rml:reference "DateTime" ; rr:datatype xsd:dateTime ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:hasSimpleResult ;
            rr:objectMap [
              rml:reference "Conductivity dokwater + spui ABF | ZHINDS10_WINCC_INDUSS_02_AT9103-B_FEED_CONDUCTIVITY | µs/cm" ;
              rr:datatype xsd:double
            ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate sosa:observedProperty ;
            rr:objectMap [ rr:constant quantitykind:ElectricConductivity ; rr:termType rr:IRI ]
          ] ;
          rr:predicateObjectMap [
            rr:predicate qudt:hasUnit ;
            rr:objectMap [ rr:constant unit:MicroS-PER-CentiM ; rr:termType rr:IRI ]
          ] .
    """

    result = generic_pipeline.run_rml_mapping(tmp_path, source_csv, mapping)

    graph = Graph().parse(result["output_path"], format="turtle")
    assert result["rdf_triples"] == 6
    assert (
        URIRef("http://example.com/observations/111111111/2025-01-01T00%3A00%3A00"),
        URIRef("http://www.w3.org/ns/sosa/hasSimpleResult"),
        None,
    ) in graph


@pytest.mark.skipif(
    not generic_pipeline.tool_status()["eye"],
    reason="A working EYE installation is required for the integration test.",
)
def test_user_supplied_n3_rules_create_reasoned_rdf(tmp_path):
    data = tmp_path / "mapped.ttl"
    data.write_text(
        '@prefix ex: <https://example.org/> . ex:item ex:category "lamp" .',
        encoding="utf-8",
    )
    rules = """
        @prefix ex: <https://example.org/> .
        { ?item ex:category "lamp" . } => { ?item ex:illuminates true . } .
    """

    result = generic_pipeline.run_reasoner(tmp_path, data, rules)
    graph = Graph().parse(result["output_path"], format="turtle")

    assert result["inferred_triples"] >= 1
    assert (URIRef("https://example.org/item"), URIRef("https://example.org/illuminates"), None) in graph


def test_rdf2ldes_generates_a_downloadable_zip(tmp_path):
    tss_path = tmp_path / "timeseries.ttl"
    tss_path.write_text(
        '''
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sosa: <http://www.w3.org/ns/sosa/> .
        @prefix tss: <https://w3id.org/tss#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

        <https://example.org/snippet> a tss:Snippet ;
            tss:about _:template ;
            tss:from "2026-01-02T00:00:00+00:00"^^xsd:dateTime ;
            tss:until "2026-01-02T23:59:59+00:00"^^xsd:dateTime ;
            tss:pointType sosa:Observation ;
            tss:points "[{\\"id\\": \\"https://example.org/reading/1\\", \\"time\\": \\"2026-01-02T12:00:00+00:00\\", \\"value\\": 42.0}]"^^rdf:JSON .

        _:template a tss:PointTemplate ;
            sosa:madeBySensor <https://example.org/sensor/1> ;
            sosa:observedProperty <https://example.org/property/temperature> .
        ''',
        encoding="utf-8",
    )

    result = generic_pipeline.run_rdf2ldes(
        tmp_path,
        tss_path,
        "example-stream",
        "https://data.example/ldes/",
    )

    assert result["zip_path"].is_file()
    assert result["trig_file_count"] >= 4
    assert result["fragment_count"] == 1
    assert any(path.name == "readings.trig" for path in Path(result["output_directory"]).rglob("*.trig"))
