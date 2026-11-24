"""API for Semantic Data Studio.

Run with: ``python run.py`` (or ``python -m uvicorn pipeline.playground_server:app --reload``).
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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import generic_pipeline as pipeline
from pipeline.run_store import RunStore
from query_agent import operations
from reasoning import eye_engine
from triple_store_ingestion import ingest


MAX_UPLOAD_BYTES = int(
    os.getenv("MAX_UPLOAD_BYTES", os.getenv("MAX_CSV_UPLOAD_BYTES", str(50 * 1024 * 1024)))
)
RUN_STORE = RunStore()


def configured_origins() -> list[str]:
    value = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


app = FastAPI(
    title="Semantic Data Studio API",
    description=(
        "Map tabular data to RDF, check it with SHACL, infer new facts with the EYE reasoner, "
        "publish it to Fuseki, and query the triple store."
    ),
    version="2.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


class RmlRequest(BaseModel):
    mapping: str = Field(min_length=1, max_length=2_000_000)
    source_name: str | None = Field(default=None, max_length=300)


class ShaclRequest(BaseModel):
    shapes: str = Field(min_length=1, max_length=2_000_000)
    source_name: str | None = Field(default=None, max_length=300)


class ReasoningRequest(BaseModel):
    rules: str = Field(min_length=1, max_length=2_000_000)
    source_name: str | None = Field(default=None, max_length=300)
    example_id: str | None = Field(default=None, max_length=100)


class IngestRequest(BaseModel):
    graph_name: str = Field(min_length=1, max_length=2_000)
    mode: Literal["replace", "append"] = "replace"


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000_000)


class OperationRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


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


STAGE_LABELS = {
    "upload": "data upload",
    "rml": "RML mapping",
    "rules": "SHACL rules",
    "reasoning": "EYE reasoning",
}


def require_stage(state: dict[str, Any], stage: str) -> None:
    result = state.get("stages", {}).get(stage)
    if not result or result.get("status") not in {"success", "nonconformant"}:
        raise HTTPException(409, f"Complete the {STAGE_LABELS.get(stage, stage)} first.")


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
        state = RUN_STORE.finish_stage(state, stage, "error", str(error), log=error.log)
    except Exception as error:  # keep a failed tool from taking down the API
        state = RUN_STORE.finish_stage(
            state, stage, "error", f"The operation could not complete: {error}"
        )
    return public_state(state)


def source_path(state: dict[str, Any]) -> Path:
    relative_path = state.get("source", {}).get("relative_path")
    if not relative_path:
        raise pipeline.PipelineError("The uploaded tabular source artifact is missing.")
    return RUN_STORE.resolve_relative(state["id"], relative_path)


def reasoning_input(state: dict[str, Any], directory: Path) -> tuple[Path, str]:
    """The RDF EYE reasons over: SHACL-enriched when rules ran, otherwise mapped."""
    rules = state.get("stages", {}).get("rules") or {}
    if rules.get("status") == "success":
        enriched_path = directory / "enriched.ttl"
        if not enriched_path.is_file():
            raise pipeline.PipelineError("The enriched RDF is missing. Run the SHACL rules again.")
        return enriched_path, "enriched RDF"
    return directory / "mapped.ttl", "mapped RDF"


def current_rdf(state: dict[str, Any], directory: Path) -> tuple[Path, str]:
    """The dataset's current RDF: reasoned, else SHACL-enriched, else mapped."""
    reasoning = state.get("stages", {}).get("reasoning") or {}
    if reasoning.get("status") == "success":
        reasoned_path = directory / "reasoned.ttl"
        if not reasoned_path.is_file():
            raise pipeline.PipelineError("The reasoned RDF is missing. Run the reasoner again.")
        return reasoned_path, "reasoned RDF"
    return reasoning_input(state, directory)


def source_note(source_name: str | None) -> str:
    return f"uploaded file {source_name}" if source_name else "pasted text"


def rules_note(request: ReasoningRequest) -> str:
    example = eye_engine.find_example(request.example_id)
    if example:
        edited = request.rules.strip() != example["rules"].strip()
        return f"example “{example['title']}”{' (edited)' if edited else ''}"
    return source_note(request.source_name)


# --- Service status -------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "semantic-data-studio"}


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
        "default_graph_base": pipeline.DEFAULT_GRAPH_BASE,
        "rdf_formats": list(pipeline.RDF_EXPORT_FORMATS),
    }


# --- Datasets (runs) ------------------------------------------------------------------


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
            "mapping_source": source_note(request.source_name),
            "mapping_triples": result["mapping_triples"],
            "rdf_triples": result["rdf_triples"],
            "log": result["log"],
            "artifacts": [
                {"path": result["mapping_path"], "name": "RML mapping", "kind": "ttl"},
                {"path": result["output_path"], "name": "Mapped RDF", "kind": "ttl"},
            ],
        }

    return execute_stage(run_id, "rml", "upload", operation)


@app.post("/api/runs/{run_id}/stages/shacl-rules")
def shacl_rules_stage(run_id: str, request: ShaclRequest) -> dict[str, Any]:
    def operation(_state: dict[str, Any], directory: Path) -> dict[str, Any]:
        result = pipeline.run_shacl_rules(directory, directory / "mapped.ttl", request.shapes)
        return {
            "message": f"SHACL rules inferred {result['inferred_triples']:,} new triples.",
            "shapes_source": source_note(request.source_name),
            "shapes": result["shapes"],
            "input_triples": result["input_triples"],
            "inferred_triples": result["inferred_triples"],
            "total_triples": result["total_triples"],
            "artifacts": [
                {"path": result["shapes_path"], "name": "SHACL rules", "kind": "ttl"},
                {"path": result["output_path"], "name": "Enriched RDF", "kind": "ttl"},
            ],
        }

    return execute_stage(run_id, "rules", "rml", operation)


@app.post("/api/runs/{run_id}/stages/reasoning")
def reasoning_stage(run_id: str, request: ReasoningRequest) -> dict[str, Any]:
    def operation(state: dict[str, Any], directory: Path) -> dict[str, Any]:
        input_path, input_label = reasoning_input(state, directory)
        result = pipeline.run_eye_reasoning(directory, input_path, request.rules)
        count = result["inferred_triples"]
        noun = "triple" if count == 1 else "triples"
        if count:
            message = f"EYE inferred {count:,} new {noun} from the {input_label}."
        elif result["output_mode"] == "query":
            message = f"EYE ran the rules, but the query found no new facts in the {input_label}."
        else:
            message = f"EYE ran the rules, but they did not infer any new facts from the {input_label}."
        return {
            "message": message,
            "rules_source": rules_note(request),
            "input_rdf": input_label,
            **{
                key: result[key]
                for key in (
                    "input_triples", "derived_triples", "inferred_triples", "total_triples",
                    "skipped_statements", "output_mode", "engine", "engine_label", "eye_version",
                    "eye_stats", "eye_seconds", "warnings", "summary", "duration_seconds",
                )
            },
            "log": result["log"],
            "artifacts": [
                {"path": result["rules_path"], "name": "N3 rules", "kind": "n3"},
                {"path": result["inferred_path"], "name": "Inferred triples", "kind": "ttl"},
                {"path": result["output_path"], "name": "Reasoned RDF", "kind": "ttl"},
            ],
        }

    return execute_stage(run_id, "reasoning", "rml", operation)


@app.get("/api/reasoning/examples")
def reasoning_examples() -> dict[str, Any]:
    return {"examples": eye_engine.list_examples()}


@app.post("/api/runs/{run_id}/stages/shacl")
def shacl_validation_stage(run_id: str, request: ShaclRequest) -> dict[str, Any]:
    def operation(state: dict[str, Any], directory: Path) -> dict[str, Any]:
        input_path, input_label = current_rdf(state, directory)
        result = pipeline.run_shacl_validation(directory, input_path, request.shapes)
        counts = result["severity_counts"]
        if result["conforms"]:
            message = f"The {input_label} conforms to the SHACL shapes."
        else:
            message = (
                f"Found {counts.get('Violation', 0):,} violations, {counts.get('Warning', 0):,} "
                f"warnings, and {counts.get('Info', 0):,} notes in the {input_label}."
            )
        return {
            "status": "success" if result["conforms"] else "nonconformant",
            "message": message,
            "shapes_source": source_note(request.source_name),
            "input_rdf": input_label,
            "conforms": result["conforms"],
            "data_triples": result["data_triples"],
            "shapes": result["shapes"],
            "severity_counts": counts,
            "total_results": result["total_results"],
            "results": result["results"],
            "truncated": result["truncated"],
            "duration_seconds": result["duration_seconds"],
            "artifacts": [
                {"path": result["shapes_path"], "name": "SHACL shapes", "kind": "ttl"},
                {"path": result["report_path"], "name": "Validation report", "kind": "txt"},
            ],
        }

    return execute_stage(run_id, "shacl", "rml", operation)


@app.post("/api/runs/{run_id}/stages/ingest")
def ingest_stage(run_id: str, request: IngestRequest) -> dict[str, Any]:
    def operation(state: dict[str, Any], directory: Path) -> dict[str, Any]:
        input_path, input_label = current_rdf(state, directory)
        result = pipeline.ingest_graph(input_path, request.graph_name, request.mode)
        verb = "Replaced" if request.mode == "replace" else "Appended to"
        return {
            "message": f"{verb} {result['graph_uri']} with the {input_label}.",
            "graph_uri": result["graph_uri"],
            "mode": result["mode"],
            "input_rdf": input_label,
            "state_updates": {
                "graph": {"name": request.graph_name, "uri": result["graph_uri"]}
            },
        }

    return execute_stage(run_id, "ingest", "rml", operation)


@app.get("/api/runs/{run_id}/rdf")
def download_rdf(
    run_id: str,
    rdf_format: Literal["turtle", "ntriples", "jsonld", "xml"] = Query(default="turtle", alias="format"),
) -> Response:
    state = load_run(run_id)
    require_stage(state, "rml")
    directory = RUN_STORE.run_dir(run_id)
    try:
        path, label = current_rdf(state, directory)
        content, media_type, extension = pipeline.export_rdf(path, rdf_format)
    except pipeline.PipelineError as error:
        raise HTTPException(400, str(error)) from error
    stem = Path(state["source"]["stored_filename"]).stem or "dataset"
    suffix = {"reasoned RDF": "reasoned", "enriched RDF": "enriched"}.get(label, "mapped")
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{stem}-{suffix}.{extension}"'},
    )


@app.get("/api/runs/{run_id}/rdf-preview")
def rdf_preview(
    run_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=10),
) -> dict[str, Any]:
    state = load_run(run_id)
    require_stage(state, "rml")
    directory = RUN_STORE.run_dir(run_id)
    try:
        path, label = current_rdf(state, directory)
        preview = pipeline.rdf_instance_preview(path, offset=offset, limit=limit)
    except pipeline.PipelineError as error:
        raise HTTPException(400, str(error)) from error
    return {**preview, "source": label}


# --- Triple store: direct query and agent-ready operations ----------------------------


def store_call(function: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return function()
    except operations.OperationError as error:
        raise HTTPException(400, str(error)) from error
    except ingest.FusekiError as error:
        # A query Fuseki rejects (syntax error, update keywords) is the caller's mistake.
        status = 400 if error.status_code == 400 else 502
        raise HTTPException(status, str(error)) from error


@app.get("/api/store/graphs")
def store_graphs() -> dict[str, Any]:
    return store_call(operations.list_graphs)


@app.post("/api/store/query")
def store_query(request: QueryRequest) -> dict[str, Any]:
    query = request.query.strip()
    if not query:
        raise HTTPException(400, "Enter a SPARQL query before running it.")
    return store_call(lambda: ingest.query_graph(query))


@app.get("/api/store/operations")
def store_operations() -> dict[str, Any]:
    return {"operations": operations.catalog()}


@app.post("/api/store/operations/{operation_id}")
def run_store_operation(operation_id: str, request: OperationRequest) -> dict[str, Any]:
    if operation_id not in operations.OPERATIONS:
        raise HTTPException(404, f"Unknown operation: {operation_id}")
    return store_call(lambda: operations.run_operation(operation_id, request.parameters))


# --- Artifacts ------------------------------------------------------------------------


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
    text = path.read_text(encoding="utf-8", errors="replace")
    response["text"] = text[:100_000]
    response["truncated"] = len(text) > 100_000
    return response


# Serve the built React app (``npm run build``) from the same origin as the API.
# Mounted last so every /api route above takes precedence.
FRONTEND_DIST = Path(
    os.getenv("FRONTEND_DIST", str(Path(__file__).resolve().parents[1] / "frontend" / "dist"))
)
if (FRONTEND_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
