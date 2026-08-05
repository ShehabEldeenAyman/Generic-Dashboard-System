"""Run-scoped state and artifact storage for the generic semantic pipeline.

The default filesystem backend is intentionally rooted outside the repository.
Cloud deployments can point ``PIPELINE_STORAGE_DIR`` at a persistent volume;
the API never assumes that input data was bundled with the application.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any
from uuid import UUID, uuid4


STAGE_ORDER = (
    "upload",
    "rml",
    "ingest",
    "shacl_in",
    "reason",
    "rdf2tss",
    "shacl_out",
    "rdf2ldes",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    """Persist pipeline metadata next to isolated run artifacts."""

    def __init__(self, root: str | Path | None = None):
        configured = root or os.getenv("PIPELINE_STORAGE_DIR")
        default_root = Path(tempfile.gettempdir()) / "semantic-pipeline-runs"
        self.root = Path(configured or default_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _normalise_id(self, run_id: str) -> str:
        try:
            return str(UUID(run_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise KeyError("Run not found.") from error

    def run_dir(self, run_id: str) -> Path:
        normalised = self._normalise_id(run_id)
        directory = (self.root / normalised).resolve()
        if directory.parent != self.root:
            raise KeyError("Run not found.")
        return directory

    def create(self, original_filename: str, stored_filename: str) -> dict[str, Any]:
        with self._lock:
            run_id = str(uuid4())
            directory = self.run_dir(run_id)
            directory.mkdir(parents=True, exist_ok=False)
            now = utc_now()
            state: dict[str, Any] = {
                "id": run_id,
                "created_at": now,
                "updated_at": now,
                "source": {
                    "original_filename": original_filename,
                    "stored_filename": stored_filename,
                },
                "graph": None,
                "stages": {},
                "artifacts": [],
            }
            self.save(state)
            return state

    def load(self, run_id: str) -> dict[str, Any]:
        state_path = self.run_dir(run_id) / "run.json"
        if not state_path.is_file():
            raise KeyError("Run not found.")
        with self._lock:
            return json.loads(state_path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state["updated_at"] = utc_now()
            directory = self.run_dir(state["id"])
            directory.mkdir(parents=True, exist_ok=True)
            state_path = directory / "run.json"
            temporary = directory / "run.json.tmp"
            temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
            temporary.replace(state_path)
            return state

    def resolve_relative(self, run_id: str, relative_path: str) -> Path:
        directory = self.run_dir(run_id)
        target = (directory / relative_path).resolve()
        if target != directory and directory not in target.parents:
            raise KeyError("Artifact not found.")
        return target

    def begin_stage(self, state: dict[str, Any], stage: str) -> dict[str, Any]:
        if stage not in STAGE_ORDER:
            raise KeyError(f"Unknown stage: {stage}")
        stage_index = STAGE_ORDER.index(stage)
        invalidated = set(STAGE_ORDER[stage_index:])
        if "ingest" in invalidated:
            state["graph"] = None
        state["stages"] = {
            key: value for key, value in state.get("stages", {}).items() if key not in invalidated
        }
        state["artifacts"] = [
            item for item in state.get("artifacts", []) if item.get("stage") not in invalidated
        ]
        state["stages"][stage] = {
            "status": "running",
            "message": "Stage is running.",
            "started_at": utc_now(),
            "artifacts": [],
        }
        return self.save(state)

    def finish_stage(
        self,
        state: dict[str, Any],
        stage: str,
        status: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        log: str = "",
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        state["stages"][stage] = {
            "status": status,
            "message": message,
            "completed_at": utc_now(),
            "details": details or {},
            "log": log,
            "artifacts": artifact_ids or [],
        }
        return self.save(state)

    def add_artifact(
        self,
        state: dict[str, Any],
        stage: str,
        path: str | Path,
        *,
        name: str | None = None,
        kind: str | None = None,
    ) -> dict[str, Any]:
        directory = self.run_dir(state["id"])
        target = Path(path).resolve()
        if directory not in target.parents:
            raise ValueError("Artifacts must be stored inside their run directory.")
        relative_path = target.relative_to(directory).as_posix()
        artifact = {
            "id": uuid4().hex,
            "stage": stage,
            "name": name or target.name,
            "kind": kind or target.suffix.lower().lstrip(".") or "file",
            "relative_path": relative_path,
            "size": target.stat().st_size if target.is_file() else 0,
            "created_at": utc_now(),
        }
        state.setdefault("artifacts", []).append(artifact)
        return artifact

    def artifact(self, run_id: str, artifact_id: str) -> tuple[dict[str, Any], Path]:
        state = self.load(run_id)
        artifact = next(
            (item for item in state.get("artifacts", []) if item.get("id") == artifact_id),
            None,
        )
        if artifact is None:
            raise KeyError("Artifact not found.")
        path = self.resolve_relative(run_id, artifact["relative_path"])
        if not path.is_file():
            raise KeyError("Artifact not found.")
        return artifact, path
