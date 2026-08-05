---
type: "query"
date: "2026-08-05T12:47:04.457510+00:00"
question: "Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file"
contributor: "graphify"
outcome: "useful"
source_nodes: ["UploadStage()", "RunStore", "delete_run()", ".delete()", "test_delete_run_removes_uploaded_file_and_artifacts()"]
---

# Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file

## Answer

Expanded via current graph vocabulary: [upload, file, delete, remove, run, store, source, artifacts]. Added pre-upload Clear selection with native file-input reset, an inline confirm/cancel Delete file and start over action, DELETE /api/runs/{run_id}, and UUID-scoped RunStore deletion of the upload plus all run artifacts. Existing Fuseki graphs are intentionally retained. Verified with 14 passing tests, frontend lint/build, and a live clear-reselect-upload-delete-reupload browser flow.

## Outcome

- Signal: useful

## Source Nodes

- UploadStage()
- RunStore
- delete_run()
- .delete()
- test_delete_run_removes_uploaded_file_and_artifacts()