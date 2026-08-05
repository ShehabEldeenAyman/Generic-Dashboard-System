from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest
from rdflib import Graph, URIRef

from pipeline import generic_pipeline
from pipeline import playground_server
from pipeline.run_store import RunStore


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


def test_graph_name_is_converted_to_a_safe_named_graph_uri():
    uri = generic_pipeline.graph_name_to_uri("Quarterly products")
    assert uri == "https://example.org/graphs/Quarterly%20products"
    assert generic_pipeline.graph_name_to_uri("https://data.example/graphs/items") == (
        "https://data.example/graphs/items"
    )


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
