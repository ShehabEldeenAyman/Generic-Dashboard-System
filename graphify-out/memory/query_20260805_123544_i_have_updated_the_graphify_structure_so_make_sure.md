---
type: "query"
date: "2026-08-05T12:35:44.614612+00:00"
question: "i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well"
contributor: "graphify"
outcome: "useful"
source_nodes: ["CsvPreview()", "csv_preview()", "create_run()", "xlsx_preview()", "tabular_preview()", "xlsx_to_csv()", "test_upload_xlsx_creates_preview_and_rml_csv_source()"]
---

# Q: i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well

## Answer

Expanded from the updated graph vocabulary via [xlsx, csv, upload, preview, parse, file, input, data]. Traced App.jsx, create_run(), safe_filename(), csv_preview(), and RunStore. Added XLSX upload and active-sheet preview, retained the original workbook, generated a run-local CSV for RMLMapper, exposed the exact mapping source name in the UI, added XLSX artifact preview and tests. Full suite: 13 passed, 1 EYE-dependent skip; frontend lint/build and browser upload verification passed.

## Outcome

- Signal: useful

## Source Nodes

- CsvPreview()
- csv_preview()
- create_run()
- xlsx_preview()
- tabular_preview()
- xlsx_to_csv()
- test_upload_xlsx_creates_preview_and_rml_csv_source()