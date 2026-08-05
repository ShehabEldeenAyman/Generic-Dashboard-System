---
type: "query"
date: "2026-08-03T15:25:41.021512+00:00"
question: "Make the dashboard generic and remove Gent-Terneuzen traces from the active UI while implementing the eight-stage uploaded-data pipeline."
contributor: "graphify"
outcome: "useful"
source_nodes: ["RunStore", "create_run()", "run_rml_mapping()", "run_shacl_validation()", "run_reasoner()", "run_rdf2tss()", "run_rdf2ldes()", "download_artifact()"]
---

# Q: Make the dashboard generic and remove Gent-Terneuzen traces from the active UI while implementing the eight-stage uploaded-data pipeline.

## Answer

Replaced the active dashboard and API with a run-scoped generic semantic pipeline: CSV preview, user RML, named Fuseki graph, SHACL-in report, N3 reasoning, RDF2TSS, SHACL-out report, RDF2LDES ZIP. Active source and production bundle contain no old use-case terms. Verification: 11 passed, 1 EYE-dependent skip; frontend lint/build passed.

## Outcome

- Signal: useful

## Source Nodes

- RunStore
- create_run()
- run_rml_mapping()
- run_shacl_validation()
- run_reasoner()
- run_rdf2tss()
- run_rdf2ldes()
- download_artifact()