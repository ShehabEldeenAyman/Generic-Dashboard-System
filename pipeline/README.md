# Generic Pipeline API

`playground_server.py` exposes run-scoped FastAPI endpoints for the eight-stage semantic workflow. `generic_pipeline.py` contains explicit-path transformation operations, while `run_store.py` persists run metadata and artifact references.

The API does not read historical repository datasets. `POST /api/runs` accepts a CSV upload and creates the input artifact used by all later stages.

Start the API from the repository root:

```powershell
python -m uvicorn pipeline.playground_server:app --reload --port 8000
```

OpenAPI documentation is served at `http://localhost:8000/docs`.

SHACL violations return a `nonconformant` stage result with the complete validation report. They do not crash the API and do not prevent the next stage from being run.
