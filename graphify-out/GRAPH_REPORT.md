# Graph Report - Generic Dashboard System  (2026-08-06)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 281 nodes · 539 edges · 20 communities
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 10 edges (avg confidence: 0.62)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `93495874`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generic_pipeline.py
- RDF2TSS_V2.py
- playground_server.py
- Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?
- devDependencies
- Codex Repository Context
- delete_run
- RunStore
- App.jsx
- RDFTSS2LDES.py
- ingest.py
- Excel upload feature memory
- Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file
- Q: Add a SPARQL query form for the ingested Fuseki graph and always clear the named graph before ingestion
- Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query
- Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages
- Semantic Pipeline Studio

## God Nodes (most connected - your core abstractions)
1. `RunStore` - 33 edges
2. `PipelineError` - 24 edges
3. `execute_stage()` - 18 edges
4. `create_run()` - 14 edges
5. `_xlsx_table_plan()` - 13 edges
6. `Semantic Pipeline Studio` - 13 edges
7. `Features` - 11 edges
8. `generate_ldes()` - 9 edges
9. `xlsx_preview()` - 9 edges
10. `xlsx_to_csv()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_ingest_graph_aborts_when_named_graph_cannot_be_cleared()` --indirect_call--> `upload_graph()`  [INFERRED]
  pipeline/tests/test_generic_pipeline.py → triple_store_ingestion/ingest.py
- `run_shacl_validation()` --calls--> `validate_shacl()`  [EXTRACTED]
  pipeline/generic_pipeline.py → SHACL/SHACL_validate.py
- `test_ingest_graph_clears_named_graph_before_upload()` --calls--> `ingest_graph()`  [EXTRACTED]
  pipeline/tests/test_generic_pipeline.py → pipeline/generic_pipeline.py
- `test_shacl_violation_returns_a_report_without_raising()` --calls--> `run_shacl_validation()`  [EXTRACTED]
  pipeline/tests/test_generic_pipeline.py → pipeline/generic_pipeline.py
- `test_rdf2tss_api_uses_mapped_rdf_when_reasoning_is_skipped()` --indirect_call--> `run_rdf2tss()`  [INFERRED]
  pipeline/tests/test_generic_pipeline.py → pipeline/generic_pipeline.py

## Import Cycles
- None detected.

## Communities (20 total, 0 thin omitted)

### Community 0 - "generic_pipeline.py"
Cohesion: 0.10
Nodes (50): date, _cell_text(), _combined_datetime(), CommandResult, csv_preview(), _date_part(), eye_command(), graph_name_to_uri() (+42 more)

### Community 1 - "RDF2TSS_V2.py"
Cohesion: 0.33
Nodes (8): create_sensor_set(), create_tss(), load_graph(), main(), Loads a Turtle file into an RDFLib Graph., Identifies unique sensors within the graph using a SPARQL query., Transforms sensor observations into the Time Series Snippets (TSS) format., save_graph()

### Community 2 - "playground_server.py"
Cohesion: 0.16
Nodes (33): BaseModel, FileResponse, get, configuration(), download_artifact(), execute_stage(), get_run(), health() (+25 more)

### Community 3 - "Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?, Source Nodes

### Community 4 - "devDependencies"
Cohesion: 0.06
Nodes (33): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, dependencies, react, react-dom, devDependencies (+25 more)

### Community 5 - "Codex Repository Context"
Cohesion: 0.50
Nodes (3): Codex Repository Context, Instructions for Codex, System Architecture & Topology

### Community 6 - "delete_run"
Cohesion: 0.67
Nodes (3): delete, delete_run(), Response

### Community 8 - "RunStore"
Cohesion: 0.11
Nodes (24): create_run(), Any, Path, Run-scoped state and artifact storage for the generic semantic pipeline.  The de, Delete one UUID-scoped run directory and every artifact it owns., Persist pipeline metadata next to isolated run artifacts., RunStore, utc_now() (+16 more)

### Community 9 - "App.jsx"
Cohesion: 0.15
Nodes (9): App(), ArtifactPreview(), completedStatuses, RdfPreview(), requestJson(), stageDefinitions, stagePrerequisites, statusLabel() (+1 more)

### Community 11 - "RDFTSS2LDES.py"
Cohesion: 0.31
Nodes (13): create_base_graph(), create_ldes_files(), delete_ldes_files(), delete_log(), divide_data(), generate_ldes(), load_graph(), main() (+5 more)

### Community 13 - "ingest.py"
Cohesion: 0.16
Nodes (13): test_ingest_graph_aborts_when_named_graph_cannot_be_cleared(), delete_graph(), FusekiError, get_query_url(), RuntimeError, query_graph(), Apache Jena Fuseki graph-store client used by the pipeline., Raised when Fuseki cannot complete a graph or query operation. (+5 more)

### Community 31 - "Excel upload feature memory"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well, Source Nodes

### Community 32 - "Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file, Source Nodes

### Community 36 - "Q: Add a SPARQL query form for the ingested Fuseki graph and always clear the named graph before ingestion"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Add a SPARQL query form for the ingested Fuseki graph and always clear the named graph before ingestion, Source Nodes

### Community 37 - "Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query, Source Nodes

### Community 38 - "Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages, Source Nodes

### Community 74 - "Semantic Pipeline Studio"
Cohesion: 0.08
Nodes (23): 10. RDF or TSS to LDES, 1. Tabular data input, 2. User-provided RML mapping, 3. Mapped RDF preview and download, 4. Apache Jena Fuseki ingestion, 5. SPARQL query workspace, 6. SHACL input validation, 7. Optional N3 reasoning (+15 more)

## Knowledge Gaps
- **63 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `test_ingest_graph_aborts_when_named_graph_cannot_be_cleared()` connect `ingest.py` to `RunStore`, `generic_pipeline.py`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `RunStore` connect `RunStore` to `playground_server.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `RunStore` (e.g. with `IngestRequest` and `LdesRequest`) actually correct?**
  _`RunStore` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _63 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `generic_pipeline.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10482180293501048 - nodes in this community are weakly interconnected._
- **Should `devDependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.058823529411764705 - nodes in this community are weakly interconnected._
- **Should `RunStore` be split into smaller, more focused modules?**
  _Cohesion score 0.10931174089068826 - nodes in this community are weakly interconnected._
