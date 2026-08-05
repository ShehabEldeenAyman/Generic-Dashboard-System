---
type: "query"
date: "2026-08-05T13:01:26.206727+00:00"
question: "i am still trying to test the system. if i test the system on the excel file attached. How do i use the rml mapping provided below. my main issue is with the directory of the file that will be mapped."
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_rml_mapping()", "xlsx_preview()", "xlsx_to_csv()", "create_run()", "App()"]
---

# Q: i am still trying to test the system. if i test the system on the excel file attached. How do i use the rml mapping provided below. my main issue is with the directory of the file that will be mapped.

## Answer

Expanded from original query via graph vocab: [xlsx, csv, rml, mapping, source, filename, path, upload, run, preview, file]. The generic upload flow stores an uploaded data.xlsx in an isolated run and prepares data.csv beside the RML mapping; RMLMapper runs with that run directory as its working directory. Use rml:source data.csv, not a local path, ../data, or {target_file_path}. The supplied mapping is a Python-template artifact, so change {{DateTime}} to {DateTime}. For this workbook, the active result sheet has a three-row header and separate Datum/Tijd columns, while the current converter uses the first non-empty row as its only header. Therefore DateTime and the old combined conductivity header do not exist in generated data.csv; the workbook must first be flattened or the generic importer must gain header/date-time normalization before the supplied mapping can work correctly.

## Outcome

- Signal: useful

## Source Nodes

- run_rml_mapping()
- xlsx_preview()
- xlsx_to_csv()
- create_run()
- App()