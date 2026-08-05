---
type: "query"
date: "2026-08-05T14:40:55.368141+00:00"
question: "The supplied RML mapping fails for waterinfo.csv with: Exception in thread main java.lang.Error: Cannot find data.csv"
contributor: "graphify"
outcome: "useful"
source_nodes: ["safe_filename()", "create_run()", "source_path()", "run_rml_mapping()", "csv_preview()"]
---

# Q: The supplied RML mapping fails for waterinfo.csv with: Exception in thread main java.lang.Error: Cannot find data.csv

## Answer

Expanded from original query via graph vocab: [csv, rml, mapping, source, filename, upload, run, path, file, safe]. CSV uploads retain their sanitized basename. The uploaded file is waterinfo.csv, but the mapping asks RMLMapper to open data.csv in the isolated run directory, so Java fails before reading records. Change rml:source to waterinfo.csv (or copy the exact RML source name displayed by Stage 2). The inspected CSV has the referenced Timestamp, Value, ts_id, and unixtimestamp columns, so those mappings are valid. Use an absolute subject template http://example.com/observations/{ts_id}/{unixtimestamp} for portability.

## Outcome

- Signal: useful

## Source Nodes

- safe_filename()
- create_run()
- source_path()
- run_rml_mapping()
- csv_preview()