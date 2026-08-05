---
type: "query"
date: "2026-08-03T14:44:23.672597+00:00"
question: "Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download."
contributor: "graphify"
outcome: "useful"
source_nodes: ["App()", "run_stage()", "stage_result()", "_rml_mapping()", "upload_graph()", "validate_shacl()", "step_5_5_reasoner()", "step_5_rdf2tss()", "step_6_RDF2LDES()"]
---

# Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download.

## Answer

Expanded from original query via graph vocab: [frontend, upload, preview, rml, mapping, fuseki, ingestion, shacl, reasoner, rdftss, rdf, ldes]. The current architecture is React App -> fixed FastAPI use-case catalog/run_stage -> stage_result -> pipeline_core -> RMLMapper, pySHACL, EYE, Fuseki, RDF2TSS and RDF2LDES. Reuse the UI stage/artifact patterns and transformation kernels, but replace fixed canal orchestration with run-scoped stages and object-backed artifacts. Current gaps are no CSV upload, no user semantic text inputs, no ZIP download, fixed graph/use cases, process-global results, local data paths, os.chdir, and mutable RDF2LDES globals. Cloud target should use a run ID, object storage, durable job state, isolated workers, configurable Fuseki, and temporary per-job materialization. SHACL nonconformance must be a completed validation result with a report, not a system error. No source deletion was performed.

## Outcome

- Signal: useful

## Source Nodes

- App()
- run_stage()
- stage_result()
- _rml_mapping()
- upload_graph()
- validate_shacl()
- step_5_5_reasoner()
- step_5_rdf2tss()
- step_6_RDF2LDES()