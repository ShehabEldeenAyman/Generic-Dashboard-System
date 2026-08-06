"""Cloud-oriented API for the generic semantic data pipeline.

Run with: ``python -m uvicorn pipeline.playground_server:app --reload --port 8000``
"""

from __future__ import annotations

from copy import deepcopy
import mimetypes
import os
from pathlib import Path
from typing import Any, Callable, Literal

import requests
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from pipeline import generic_pipeline as pipeline
from pipeline.run_store import RunStore
from triple_store_ingestion import ingest


MAX_UPLOAD_BYTES = int(
    os.getenv("MAX_UPLOAD_BYTES", os.getenv("MAX_CSV_UPLOAD_BYTES", str(50 * 1024 * 1024)))
)
RUN_STORE = RunStore()


def configured_origins() -> list[str]:
    value = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(
    title="Semantic Pipeline API",
    description="Run-scoped CSV/XLSX to RDF, TSS, and LDES processing.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


class RmlRequest(BaseModel):
    mapping: str = Field(min_length=1, max_length=2_000_000)


class IngestRequest(BaseModel):
    graph_name: str = Field(min_length=1, max_length=2_000)


class SparqlRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000_000)


class ShaclRequest(BaseModel):
    shapes: str = Field(min_length=1, max_length=2_000_000)


class ReasonRequest(BaseModel):
    rules: str = Field(min_length=1, max_length=2_000_000)


class LdesRequest(BaseModel):
    stream_name: str = Field(default="dataset", min_length=1, max_length=200)
    base_url: str | None = Field(default=None, max_length=2_000)
    source: Literal["rdf", "tss"] = "tss"


def load_run(run_id: str) -> dict[str, Any]:
    try:
        return RUN_STORE.load(run_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(state)
    for artifact in result.get("artifacts", []):
        base = f"/api/runs/{result['id']}/artifacts/{artifact['id']}"
        artifact["download_url"] = base
        artifact["preview_url"] = f"{base}/preview"
        artifact.pop("relative_path", None)
    return result


def require_stage(state: dict[str, Any], stage: str) -> None:
    result = state.get("stages", {}).get(stage)
    if not result or result.get("status") not in {"success", "nonconformant"}:
        label = stage.replace("_", " ").upper()
        raise HTTPException(409, f"Complete the {label} stage first.")


StageOperation = Callable[[dict[str, Any], Path], dict[str, Any]]


def execute_stage(
    run_id: str,
    stage: str,
    prerequisite: str,
    operation: StageOperation,
) -> dict[str, Any]:
    state = load_run(run_id)
    require_stage(state, prerequisite)
    state = RUN_STORE.begin_stage(state, stage)
    run_directory = RUN_STORE.run_dir(run_id)

    try:
        outcome = operation(state, run_directory)
        status = outcome.pop("status", "success")
        message = outcome.pop("message")
        log = outcome.pop("log", "")
        artifacts = outcome.pop("artifacts", [])
        state_updates = outcome.pop("state_updates", {})
        state.update(state_updates)
        artifact_ids: list[str] = []
        for item in artifacts:
            artifact = RUN_STORE.add_artifact(
                state,
                stage,
                item["path"],
                name=item.get("name"),
                kind=item.get("kind"),
            )
            artifact_ids.append(artifact["id"])
        state = RUN_STORE.finish_stage(
            state,
            stage,
            status,
            message,
            details=outcome,
            log=log,
            artifact_ids=artifact_ids,
        )
    except pipeline.PipelineError as error:
        state = RUN_STORE.finish_stage(
            state,
            stage,
            "error",
            str(error),
            log=error.log,
        )
    except Exception as error:  # keep a failed tool from taking down the API
        state = RUN_STORE.finish_stage(
            state,
            stage,
            "error",
            f"The stage could not complete: {error}",
        )
    return public_state(state)


def source_path(state: dict[str, Any]) -> Path:
    relative_path = state.get("source", {}).get("relative_path")
    if not relative_path:
        raise pipeline.PipelineError("The uploaded tabular source artifact is missing.")
    return RUN_STORE.resolve_relative(state["id"], relative_path)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "semantic-pipeline"}


@app.get("/api/config")
def configuration() -> dict[str, Any]:
    connected = False
    detail = ""
    try:
        response = requests.get(
            ingest.get_query_url(),
            params={"query": "ASK {}"},
            headers={"Accept": "application/sparql-results+json"},
            timeout=5,
        )
        connected = response.ok
        if not response.ok:
            detail = f"Fuseki returned HTTP {response.status_code}."
    except requests.RequestException as error:
        detail = str(error)
    return {
        "fuseki": {
            "connected": connected,
            "data_endpoint": ingest.FUSEKI_DATA_URL,
            "query_endpoint": ingest.get_query_url(),
            "detail": detail,
        },
        "tools": pipeline.tool_status(),
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "storage": "run-scoped",
    }


@app.post("/api/runs")
async def create_run(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        stored_filename = pipeline.safe_filename(file.filename)
    except pipeline.PipelineError as error:
        raise HTTPException(400, str(error)) from error

    state = RUN_STORE.create(file.filename or stored_filename, stored_filename)
    state = RUN_STORE.begin_stage(state, "upload")
    target = RUN_STORE.run_dir(state["id"]) / stored_filename
    generated_paths: list[Path] = [target]
    size = 0
    try:
        with target.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise pipeline.PipelineError(
                        f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit."
                    )
                destination.write(chunk)
        preview = pipeline.tabular_preview(target)
        upload_artifact = RUN_STORE.add_artifact(
            state,
            "upload",
            target,
            name=stored_filename,
            kind=target.suffix.lower().lstrip("."),
        )
        source_path = target
        artifact_ids = [upload_artifact["id"]]
        if target.suffix.lower() == ".xlsx":
            source_path = target.with_suffix(".csv")
            pipeline.xlsx_to_csv(target, source_path, preview)
            generated_paths.append(source_path)
            source_artifact = RUN_STORE.add_artifact(
                state,
                "upload",
                source_path,
                name=f"RML source · {source_path.name}",
                kind="csv",
            )
            artifact_ids.append(source_artifact["id"])
        state["source"].update(
            {
                "relative_path": source_path.relative_to(RUN_STORE.run_dir(state["id"])).as_posix(),
                "size": size,
                "preview": preview,
                "format": preview["format"],
                "mapping_source_filename": source_path.name,
                "artifact_id": upload_artifact["id"],
            }
        )
        state = RUN_STORE.finish_stage(
            state,
            "upload",
            "success",
            f"Uploaded and parsed {stored_filename}.",
            details={
                "columns": len(preview["columns"]),
                "rows": preview["total_rows"],
                "format": preview["format"],
                **({"encoding": preview["encoding"], "delimiter": preview["delimiter"]} if preview["format"] == "csv" else {"sheet_name": preview["sheet_name"]}),
            },
            artifact_ids=artifact_ids,
        )
    except pipeline.PipelineError as error:
        for generated_path in generated_paths:
            if generated_path.exists():
                generated_path.unlink()
        state = RUN_STORE.finish_stage(state, "upload", "error", str(error), log=error.log)
    finally:
        await file.close()
    return public_state(state)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    return public_state(load_run(run_id))


@app.delete("/api/runs/{run_id}", status_code=204)
def delete_run(run_id: str) -> Response:
    try:
        RUN_STORE.delete(run_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    return Response(status_code=204)


@app.post("/api/runs/{run_id}/stages/rml")
def rml_mapping(run_id: str, request: RmlRequest) -> dict[str, Any]:
    def operation(state: dict[str, Any], directory: Path) -> dict[str, Any]:
        result = pipeline.run_rml_mapping(directory, source_path(state), request.mapping)
        return {
            "message": f"RML mapping created {result['rdf_triples']:,} RDF triples.",
            "mapping_triples": result["mapping_triples"],
            "rdf_triples": result["rdf_triples"],
            "log": result["log"],
            "artifacts": [
                {"path": result["mapping_path"], "name": "RML mapping", "kind": "ttl"},
                {"path": result["output_path"], "name": "Mapped RDF", "kind": "ttl"},
            ],
        }

    return execute_stage(run_id, "rml", "upload", operation)


@app.get("/api/runs/{run_id}/rdf-preview")
def mapped_rdf_preview(
    run_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=10),
) -> dict[str, Any]:
    state = load_run(run_id)
    require_stage(state, "rml")
    try:
        return pipeline.rdf_instance_preview(
            RUN_STORE.run_dir(run_id) / "mapped.ttl",
            offset=offset,
            limit=limit,
        )
    except pipeline.PipelineError as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/runs/{run_id}/stages/ingest")
def ingest_stage(run_id: str, request: IngestRequest) -> dict[str, Any]:
    def operation(_state: dict[str, Any], directory: Path) -> dict[str, Any]:
        result = pipeline.ingest_graph(directory / "mapped.ttl", request.graph_name)
        return {
            "message": f"Cleared and ingested the mapped RDF into {result['graph_uri']}.",
            "graph_uri": result["graph_uri"],
            "graph_cleared": result["graph_cleared"],
            "state_updates": {
                "graph": {"name": request.graph_name, "uri": result["graph_uri"]}
            },
        }

    return execute_stage(run_id, "ingest", "rml", operation)


@app.post("/api/runs/{run_id}/sparql")
def sparql_query(run_id: str, request: SparqlRequest) -> dict[str, Any]:
    state = load_run(run_id)
    require_stage(state, "ingest")
    graph_uri = (state.get("graph") or {}).get("uri", "")
    try:
        return pipeline.run_sparql_query(request.query, graph_uri)
    except pipeline.PipelineError as error:
        raise HTTPException(400, str(error)) from error


@app.post("/api/runs/{run_id}/stages/shacl-in")
def shacl_in_stage(run_id: str, request: ShaclRequest) -> dict[str, Any]:
    def operation(_state: dict[str, Any], directory: Path) -> dict[str, Any]:
        result = pipeline.run_shacl_validation(
            directory, directory / "mapped.ttl", request.shapes, prefix="shacl_in"
        )
        conforms = bool(result["conforms"])
        return {
            "status": "success" if conforms else "nonconformant",
            "message": "The mapped RDF conforms to the SHACL shape." if conforms else "The mapped RDF does not conform. Review the report; the pipeline remains available.",
            "conforms": conforms,
            "report": result["report"],
            "duration_seconds": result["duration_seconds"],
            "artifacts": [
                {"path": result["shapes_path"], "name": "SHACL input shape", "kind": "ttl"},
                {"path": result["report_path"], "name": "SHACL input report", "kind": "txt"},
            ],
        }

    return execute_stage(run_id, "shacl_in", "rml", operation)


@app.post("/api/runs/{run_id}/stages/reason")
def reason_stage(run_id: str, request: ReasonRequest) -> dict[str, Any]:
    def operation(_state: dict[str, Any], directory: Path) -> dict[str, Any]:
        result = pipeline.run_reasoner(directory, directory / "mapped.ttl", request.rules)
        return {
            "message": f"Reasoning added {result['inferred_triples']:,} inferred triples.",
            "inferred_triples": result["inferred_triples"],
            "total_triples": result["total_triples"],
            "log": result["log"],
            "artifacts": [
                {"path": result["rules_path"], "name": "N3 rules", "kind": "n3"},
                {"path": result["output_path"], "name": "Reasoned RDF", "kind": "ttl"},
            ],
        }

    return execute_stage(run_id, "reason", "rml", operation)


@app.post("/api/runs/{run_id}/stages/rdf2tss")
def rdf2tss_stage(run_id: str) -> dict[str, Any]:
    def operation(state: dict[str, Any], directory: Path) -> dict[str, Any]:
        reason_status = (state.get("stages", {}).get("reason") or {}).get("status")
        reasoned_path = directory / "reasoned.ttl"
        use_reasoned_rdf = reason_status == "success" and reasoned_path.is_file()
        input_path = reasoned_path if use_reasoned_rdf else directory / "mapped.ttl"
        input_label = "reasoned RDF" if use_reasoned_rdf else "mapped RDF"
        result = pipeline.run_rdf2tss(directory, input_path)
        return {
            "message": f"Created TSS data for {result['sensor_count']:,} sensors from {input_label}.",
            "sensor_count": result["sensor_count"],
            "tss_triples": result["tss_triples"],
            "input_rdf": input_path.name,
            "artifacts": [
                {"path": result["output_path"], "name": "TSS RDF", "kind": "ttl"}
            ],
        }

    return execute_stage(run_id, "rdf2tss", "rml", operation)


@app.post("/api/runs/{run_id}/stages/shacl-out")
def shacl_out_stage(run_id: str, request: ShaclRequest) -> dict[str, Any]:
    def operation(_state: dict[str, Any], directory: Path) -> dict[str, Any]:
        result = pipeline.run_shacl_validation(
            directory, directory / "timeseries.ttl", request.shapes, prefix="shacl_out"
        )
        conforms = bool(result["conforms"])
        return {
            "status": "success" if conforms else "nonconformant",
            "message": "The TSS output conforms to the SHACL shape." if conforms else "The TSS output does not conform. Review the report; LDES generation remains available.",
            "conforms": conforms,
            "report": result["report"],
            "duration_seconds": result["duration_seconds"],
            "artifacts": [
                {"path": result["shapes_path"], "name": "SHACL output shape", "kind": "ttl"},
                {"path": result["report_path"], "name": "SHACL output report", "kind": "txt"},
            ],
        }

    return execute_stage(run_id, "shacl_out", "rdf2tss", operation)


@app.post("/api/runs/{run_id}/stages/rdf2ldes")
def rdf2ldes_stage(run_id: str, request: LdesRequest) -> dict[str, Any]:
    def operation(_state: dict[str, Any], directory: Path) -> dict[str, Any]:
        source_path = directory / ("mapped.ttl" if request.source == "rdf" else "timeseries.ttl")
        source_label = "mapped RDF" if request.source == "rdf" else "TSS RDF"
        result = pipeline.run_rdf2ldes(
            directory,
            source_path,
            request.stream_name,
            request.base_url,
            source_kind=request.source,
        )
        root_indexes = sorted(
            path for path in result["output_directory"].glob("*.trig") if path.is_file()
        )
        artifacts = [
            {"path": result["zip_path"], "name": f"{result['stream_name']} LDES ZIP", "kind": "zip"}
        ]
        if root_indexes:
            artifacts.append({"path": root_indexes[0], "name": "LDES root index", "kind": "trig"})
        return {
            "message": f"Generated {result['trig_file_count']:,} LDES files from {source_label} and packaged them as ZIP.",
            "stream_name": result["stream_name"],
            "base_url": result["base_url"],
            "source": request.source,
            "source_file": result["source_file"],
            "trig_file_count": result["trig_file_count"],
            "fragment_count": result["fragment_count"],
            "index_count": result["index_count"],
            "artifacts": artifacts,
        }

    prerequisite = "rml" if request.source == "rdf" else "rdf2tss"
    return execute_stage(run_id, "rdf2ldes", prerequisite, operation)


@app.get("/api/runs/{run_id}/artifacts/{artifact_id}")
def download_artifact(run_id: str, artifact_id: str) -> FileResponse:
    try:
        artifact, path = RUN_STORE.artifact(run_id, artifact_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/api/runs/{run_id}/artifacts/{artifact_id}/preview")
def preview_artifact(run_id: str, artifact_id: str) -> dict[str, Any]:
    try:
        artifact, path = RUN_STORE.artifact(run_id, artifact_id)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    response: dict[str, Any] = {"artifact": public_state({"id": run_id, "artifacts": [artifact]})["artifacts"][0]}
    if path.suffix.lower() in {".csv", ".xlsx"}:
        response["table"] = pipeline.tabular_preview(path)
        return response
    if path.suffix.lower() == ".zip":
        response["message"] = "Download the ZIP to inspect the complete LDES folder."
        return response
    text = path.read_text(encoding="utf-8", errors="replace")
    response["text"] = text[:100_000]
    response["truncated"] = len(text) > 100_000
    return response
