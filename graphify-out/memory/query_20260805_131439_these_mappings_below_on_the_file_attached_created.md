---
type: "query"
date: "2026-08-05T13:14:39.241836+00:00"
question: "these mappings below on the file attached created an rdf file with zero triples. why is that? fix it"
contributor: "graphify"
outcome: "useful"
source_nodes: ["XlsxTablePlan", "_xlsx_table_plan()", "xlsx_preview()", "xlsx_to_csv()", "run_rml_mapping()", "test_normalized_multirow_xlsx_runs_with_user_mapping()"]
---

# Q: these mappings below on the file attached created an rdf file with zero triples. why is that? fix it

## Answer

Expanded from original query via graph vocab: [xlsx, csv, header, date, time, rml, mapping, source, upload, preview, triples, normalize]. The zero triples occurred because the old XLSX converter used only the first non-empty worksheet row as CSV headers. The attached workbook has three metadata/header rows and separate date/time fields, so DateTime and the composite conductivity reference did not exist; without DateTime the subject template produced no subjects. The generic converter now detects multi-row headers, joins fragments with ' | ', merges adjacent date/time values including text-formatted times into DateTime, excludes metadata rows from data, and rejects zero-triple RML output with available-column diagnostics. The exact attachment and supplied mapping now produce 209,165 RDF triples from 35,033 rows. Full suite: 16 passed, 1 EYE-dependent skipped.

## Outcome

- Signal: useful

## Source Nodes

- XlsxTablePlan
- _xlsx_table_plan()
- xlsx_preview()
- xlsx_to_csv()
- run_rml_mapping()
- test_normalized_multirow_xlsx_runs_with_user_mapping()