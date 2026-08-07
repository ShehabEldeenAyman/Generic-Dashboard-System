# Graph Report - Generic Dashboard System  (2026-08-07)

## Corpus Check
- 25 files · ~17,583 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 344 nodes · 661 edges · 21 communities
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `25218375`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- generic_pipeline.py
- RDF2TSS_V2.py
- playground_server.py
- Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?
- devDependencies
- delete_run
- __init__.py
- RunStore
- App.jsx
- RDF2TSS_V2.py
- RDFTSS2LDES.py
- Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file
- ingest.py
- Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query
- Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages
- Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?
- Codex Repository Context
- eslint.config.js

## God Nodes (most connected - your core abstractions)
1. `RunStore` - 35 edges
2. `PipelineError` - 27 edges
3. `execute_stage()` - 19 edges
4. `Semantic Pipeline Studio` - 17 edges
5. `create_run()` - 14 edges
6. `_xlsx_table_plan()` - 13 edges
7. `run_unit_alignment()` - 12 edges
8. `Features` - 12 edges
9. `transform_unit_optimized()` - 11 edges
10. `run_rml_mapping()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `test_ingest_graph_aborts_when_named_graph_cannot_be_cleared()` --indirect_call--> `upload_graph()`  [INFERRED]
  pipeline/tests/test_generic_pipeline.py → triple_store_ingestion/ingest.py
- `run_shacl_validation()` --calls--> `validate_shacl()`  [EXTRACTED]
  pipeline/generic_pipeline.py → SHACL/SHACL_validate.py
- `run_unit_alignment()` --calls--> `conversion_family()`  [EXTRACTED]
  pipeline/generic_pipeline.py → automating_alignments/automated_alignments.py
- `test_known_water_measurement_conversions()` --calls--> `convert_qudt_value()`  [EXTRACTED]
  pipeline/tests/test_generic_pipeline.py → automating_alignments/automated_alignments.py
- `run_unit_alignment()` --calls--> `transform_unit_optimized()`  [EXTRACTED]
  pipeline/generic_pipeline.py → automating_alignments/automated_alignments.py

## Import Cycles
- None detected.

## Communities (21 total, 0 thin omitted)

### Community 0 - "generic_pipeline.py"
Cohesion: 0.12
Nodes (46): date, _cell_text(), _combined_datetime(), CommandResult, csv_preview(), _date_part(), eye_command(), graph_name_to_uri() (+38 more)

### Community 1 - "RDF2TSS_V2.py"
Cohesion: 0.15
Nodes (37): BaseModel, FileResponse, get, alignment_stage(), AlignmentRequest, configuration(), download_artifact(), execute_stage() (+29 more)

### Community 2 - "playground_server.py"
Cohesion: 0.05
Nodes (40): 10. SHACL output validation, 11. RDF or TSS to LDES, 1. Install the backend dependencies, 1. Run Fuseki, 1. Tabular data input, 2. Add RMLMapper, 2. Run the backend API, 2. User-provided RML mapping (+32 more)

### Community 3 - "Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?"
Cohesion: 0.06
Nodes (33): eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, dependencies, react, react-dom, devDependencies (+25 more)

### Community 4 - "devDependencies"
Cohesion: 0.10
Nodes (28): delete, create_run(), delete_run(), Any, Path, Run-scoped state and artifact storage for the generic semantic pipeline.  The de, Delete one UUID-scoped run directory and every artifact it owns., Persist pipeline metadata next to isolated run artifacts. (+20 more)

### Community 6 - "delete_run"
Cohesion: 0.14
Nodes (10): alignmentUnitExamples, App(), ArtifactPreview(), completedStatuses, RdfPreview(), requestJson(), stageDefinitions, stagePrerequisites (+2 more)

### Community 7 - "__init__.py"
Cohesion: 0.20
Nodes (13): create_base_graph(), create_ldes_files(), delete_log(), divide_data(), extract_observations(), load_graph(), main(), Group observations by (year, month, day) and write one file per day. (+5 more)

### Community 8 - "RunStore"
Cohesion: 0.31
Nodes (13): create_base_graph(), create_ldes_files(), delete_ldes_files(), delete_log(), divide_data(), generate_ldes(), load_graph(), main() (+5 more)

### Community 9 - "App.jsx"
Cohesion: 0.16
Nodes (13): test_ingest_graph_aborts_when_named_graph_cannot_be_cleared(), delete_graph(), FusekiError, get_query_url(), RuntimeError, query_graph(), Apache Jena Fuseki graph-store client used by the pipeline., Raised when Fuseki cannot complete a graph or query operation. (+5 more)

### Community 10 - "RDF2TSS_V2.py"
Cohesion: 0.13
Nodes (22): _conversion(), conversion_family(), convert_qudt_value(), main(), URIRef, Normalize observation values between QUDT units., Compatibility entry point using the corrected batch implementation., Convert every SOSA observation to NEW_UNIT and serialize once.      Previous cod (+14 more)

### Community 11 - "RDFTSS2LDES.py"
Cohesion: 0.23
Nodes (13): Graph, test_normalized_multirow_xlsx_runs_with_user_mapping(), test_user_supplied_n3_rules_create_reasoned_rdf(), test_user_supplied_rml_mapping_runs_against_uploaded_filename(), create_sensor_set(), create_tss(), load_graph(), main() (+5 more)

### Community 12 - "Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well, Source Nodes

### Community 13 - "ingest.py"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Can you add a button to clear/delete the uploaded file (csv or xlsx) so user can easily reupload the right file, Source Nodes

### Community 14 - "Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Add a SPARQL query form for the ingested Fuseki graph and always clear the named graph before ingestion, Source Nodes

### Community 15 - "Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query, Source Nodes

### Community 16 - "Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages, Source Nodes

### Community 17 - "Codex Repository Context"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?, Source Nodes

### Community 18 - "eslint.config.js"
Cohesion: 0.50
Nodes (3): Codex Repository Context, Instructions for Codex, System Architecture & Topology

## Knowledge Gaps
- **78 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RunStore` connect `devDependencies` to `RDF2TSS_V2.py`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `test_ingest_graph_aborts_when_named_graph_cannot_be_cleared()` connect `App.jsx` to `generic_pipeline.py`, `devDependencies`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `load_graph()` connect `RunStore` to `RDFTSS2LDES.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `RunStore` (e.g. with `AlignmentRequest` and `IngestRequest`) actually correct?**
  _`RunStore` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _78 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `generic_pipeline.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11510204081632654 - nodes in this community are weakly interconnected._
- **Should `RDF2TSS_V2.py` be split into smaller, more focused modules?**
  _Cohesion score 0.145748987854251 - nodes in this community are weakly interconnected._