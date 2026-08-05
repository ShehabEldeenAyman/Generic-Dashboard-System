# Graph Report - .  (2026-08-05)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 620 nodes · 940 edges · 84 communities (57 shown, 27 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `28f33963`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- playground_server.py
- server.py
- generic_pipeline.py
- URIRef
- dependencies
- devDependencies
- pipeline_core.py
- EdgeDeepLearning.jsx
- main
- App.jsx
- main.py
- pipeline.py
- MapCard.jsx
- RDF2LDES_YMD_SPARQL_FOR_TSS.py
- BrowseData.jsx
- main
- clean_result_sheet
- ingest.py
- main
- Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map
- Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before.
- Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined.
- chronosCard.jsx
- machineLearningCard.jsx
- UseCasePage.jsx
- Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis.
- Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download.
- Q: Make the dashboard generic and remove Gent-Terneuzen traces from the active UI while implementing the eight-stage uploaded-data pipeline.
- Q: i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well
- Lag analytics workspace
- Codex Repository Context
- fetch.py
- test.py
- preprocess.py
- QueryCard.jsx
- main
- generate_timeseries_mapping
- LDESChart.jsx
- LDESTSSChart.jsx
- SQLChart.jsx
- TTLChart.jsx
- frontend/README.md
- python.worker.js
- pipeline/README.md
- README.md
- DataFrame
- DataFrame
- RuntimeError
- BaseModel
- get
- post
- get
- RuntimeError
- BaseModel
- get
- post

## God Nodes (most connected - your core abstractions)
1. `RunStore` - 26 edges
2. `PipelineError` - 22 edges
3. `execute_stage()` - 18 edges
4. `main()` - 16 edges
5. `create_run()` - 14 edges
6. `_xlsx_table_plan()` - 13 edges
7. `FusekiClient` - 11 edges
8. `setup_environment()` - 11 edges
9. `generate_ldes()` - 9 edges
10. `main()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_qudt_conversion_micro_to_milli_si_per_centimetre()` --calls--> `convert_qudt_value()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → automating_aligments/automated_alignments.py
- `test_legacy_fuseki_graph_is_normalized_to_milli_si_per_centimetre()` --calls--> `normalize_fuseki_observations()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → lag_analytics_workspace/fuseki.py
- `test_legacy_reader_prefers_new_correct_value_after_pipeline_rerun()` --calls--> `normalize_fuseki_observations()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → lag_analytics_workspace/fuseki.py
- `test_shacl_violation_returns_a_report_without_raising()` --calls--> `run_shacl_validation()`  [EXTRACTED]
  pipeline/tests/test_generic_pipeline.py → pipeline/generic_pipeline.py
- `test_rdf2ldes_generates_a_downloadable_zip()` --calls--> `run_rdf2ldes()`  [EXTRACTED]
  pipeline/tests/test_generic_pipeline.py → pipeline/generic_pipeline.py

## Import Cycles
- None detected.

## Communities (84 total, 27 thin omitted)

### Community 0 - "playground_server.py"
Cohesion: 0.08
Nodes (50): BaseModel, delete, FileResponse, get, configuration(), create_run(), delete_run(), download_artifact() (+42 more)

### Community 1 - "server.py"
Cohesion: 0.07
Nodes (49): deep_learning(), describe_data(), _feature_matrix(), lag_analysis(), machine_learning(), matrix_profile(), _number(), prepare_observations() (+41 more)

### Community 2 - "generic_pipeline.py"
Cohesion: 0.12
Nodes (45): date, _cell_text(), _combined_datetime(), CommandResult, csv_preview(), _date_part(), eye_command(), graph_name_to_uri() (+37 more)

### Community 3 - "URIRef"
Cohesion: 0.10
Nodes (31): _conversion(), convert_qudt_value(), main(), Normalize observation values between QUDT units., Convert via the common SI reference represented by QUDT metadata., Compatibility entry point using the corrected batch implementation., Convert every SOSA observation to NEW_UNIT and serialize once.      Previous cod, transform_unit() (+23 more)

### Community 4 - "dependencies"
Cohesion: 0.06
Nodes (33): buffer, dependencies, buffer, echarts, echarts-for-react, ldes-client, leaflet, @pola-rs/browser (+25 more)

### Community 5 - "devDependencies"
Cohesion: 0.06
Nodes (30): devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, @types/react, @types/react-dom (+22 more)

### Community 6 - "pipeline_core.py"
Cohesion: 0.14
Nodes (23): data_path(), ldes_artifacts(), pipeline_working_directory(), Reusable, observable stages for the canal data pipelines.  The functions in this, Run EYE and save inferred triples next to the source RDF file., Return a useful, bounded preview of a generated LDES tree.      A full run can c, Make pipeline collaborators importable without the forecasting server., Support legacy collaborators that resolve paths relative to pipeline/. (+15 more)

### Community 7 - "EdgeDeepLearning.jsx"
Cohesion: 0.14
Nodes (18): DataVisualization(), getSensorDataCache(), PREFIXES, sensorDataRegistry, buildAverageSeries(), buildForecastTimestamps(), extractSensorData(), ldesState (+10 more)

### Community 8 - "main"
Cohesion: 0.23
Nodes (16): comparison_visualization(), comparisonforecast(), datapreparation(), ensemble(), ensemble_visualization(), featureengineering(), identify_unique_sensors(), lightGBM_forecast_bias() (+8 more)

### Community 9 - "App.jsx"
Cohesion: 0.18
Nodes (7): App(), ArtifactPreview(), completedStatuses, requestJson(), stageDefinitions, statusLabel(), StatusPill()

### Community 10 - "main.py"
Cohesion: 0.26
Nodes (11): chronos2forecast_visualization(), comparison_visualization(), ensemble_visualization(), lifespan(), lightGBM_visualization(), plot_sensor_data(), random_forest_visualization(), SVR_visualization() (+3 more)

### Community 11 - "pipeline.py"
Cohesion: 0.29
Nodes (9): main(), setup_environment(), step_1_fetch_data(), step_1_pre_process_waterlink(), step_2_preprocess(), step_2_rml_mapping_waterlink(), step_3_rml_mapping(), step_4_ingest_virtuoso() (+1 more)

### Community 12 - "MapCard.jsx"
Cohesion: 0.18
Nodes (3): headStyles, innerStyles, styles

### Community 13 - "RDF2LDES_YMD_SPARQL_FOR_TSS.py"
Cohesion: 0.38
Nodes (9): create_base_graph(), create_ldes_files(), delete_ldes_files(), delete_log(), divide_data(), load_graph(), main(), process_graph() (+1 more)

### Community 14 - "BrowseData.jsx"
Cohesion: 0.20
Nodes (3): headStyles, innerStyles, tableStyles

### Community 15 - "main"
Cohesion: 0.33
Nodes (8): create_sensor_set(), create_tss(), load_graph(), main(), Loads a Turtle file into an RDFLib Graph., Identifies unique sensors within the graph using a SPARQL query., Transforms sensor observations into the Time Series Snippets (TSS) format., save_graph()

### Community 17 - "clean_result_sheet"
Cohesion: 0.32
Nodes (7): build_combined_header(), clean_result_sheet(), combine_datetime(), Cleans the 'result' tab of data.xlsx.  Assumed raw layout (1-indexed rows/cols, Combine a date value and a time value into a single ISO-8601 string,     e.g. ', Combine the description / attribute name / unit of measure (rows 1, 2, 3)     i, Reads `sheet_name` from `input_path`, merges the Datum/Tijd columns into     a

### Community 18 - "ingest.py"
Cohesion: 0.25
Nodes (7): delete_graph(), get_query_url(), Apache Jena Fuseki graph-store client used by the pipeline., Resolve Fuseki's read-only SPARQL query endpoint from the data endpoint., Upload a Turtle file into a named graph and report an actionable result., Remove a named graph from Fuseki's Graph Store Protocol endpoint., upload_graph()

### Community 20 - "main"
Cohesion: 0.40
Nodes (4): main(), build_lstm_autoencoder(), create_sequences(), dataset : (n_samples, 1) scaled array     Returns       X : (samples, time_ste

### Community 21 - "Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map, Source Nodes

### Community 22 - "Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before., Source Nodes

### Community 23 - "Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined., Source Nodes

### Community 26 - "UseCasePage.jsx"
Cohesion: 0.40
Nodes (3): applications, canalPath, stations

### Community 27 - "Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis., Source Nodes

### Community 28 - "Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download., Source Nodes

### Community 29 - "Q: Make the dashboard generic and remove Gent-Terneuzen traces from the active UI while implementing the eight-stage uploaded-data pipeline."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Make the dashboard generic and remove Gent-Terneuzen traces from the active UI while implementing the eight-stage uploaded-data pipeline., Source Nodes

### Community 30 - "Q: i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: i have updated the graphify structure so make sure to check the new one out before doing anything. I have tried to test the system, module 1 data input only supports the upload of csv files, I want it to also support xlsx files as well, Source Nodes

### Community 31 - "Lag analytics workspace"
Cohesion: 0.40
Nodes (4): Conductivity units, Fuseki configuration, Lag analytics workspace, Start

### Community 32 - "Codex Repository Context"
Cohesion: 0.50
Nodes (3): Codex Repository Context, Instructions for Codex, System Architecture & Topology

## Knowledge Gaps
- **91 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+86 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `App()` (4× useful, score=3.800753128)
- `create_run()` (3× useful, score=2.956372331)
- `xlsx_preview()` (2× useful, score=1.999405502) _(code changed — re-verify)_
- `xlsx_to_csv()` (2× useful, score=1.999405502) _(code changed — re-verify)_
- `run_rml_mapping()` (2× useful, score=1.956875643) _(code changed — re-verify)_
- `RunStore` (2× useful, score=1.956645244)
- `step_6_RDF2LDES()` (2× useful, score=1.909518086)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_iri()` connect `server.py` to `URIRef`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `create_ldes_files()` connect `RDF2LDES_YMD_SPARQL_FOR_TSS.py` to `URIRef`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `RunStore` (e.g. with `IngestRequest` and `LdesRequest`) actually correct?**
  _`RunStore` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _91 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `playground_server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08065268065268065 - nodes in this community are weakly interconnected._
- **Should `server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07486338797814207 - nodes in this community are weakly interconnected._
- **Should `generic_pipeline.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11702127659574468 - nodes in this community are weakly interconnected._