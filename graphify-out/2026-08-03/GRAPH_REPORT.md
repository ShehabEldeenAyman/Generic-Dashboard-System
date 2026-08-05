# Graph Report - Generic Dashboard System  (2026-08-03)

## Corpus Check
- 87 files · ~487,553 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 905 nodes · 1435 edges · 111 communities (84 shown, 27 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 49 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `82e1c2d6`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- dependencies
- devDependencies
- EdgeDeepLearning.jsx
- App.jsx
- pipeline_core.py
- timeseriesforecasting.py
- pipeline.py
- MapCard.jsx
- RDFTSS2LDES.py
- RDF2LDES_YMD_SPARQL_FOR_TSS.py
- BrowseData.jsx
- RDF2TSS_V2.py
- preprocess_waterlink.py
- start_preprocessing.py
- RDF2TSS_per_day_V1.py
- main
- chronosCard.jsx
- machineLearningCard.jsx
- ingest.py
- test.py
- QueryCard.jsx
- preprocess.py
- LDESTSSChart.jsx
- SQLChart.jsx
- preprocess2.py
- RML_generator.py
- contexual_matrix_profile.py
- fetch_water_link.py
- pyodidetest.jsx
- python.worker.js
- GraphCard.jsx
- eslint.config.js
- vite.config.js
- pipeline/__init__.py
- Codex Repository Context
- QueryCard.jsx
- LDESChart.jsx
- TTLChart.jsx
- SHACL_validate.py
- vite.config.js
- pipeline/__init__.py
- server.py
- pipeline/README.md
- main
- RDF2LDES_YMD_SPARQL_FOR_TSS.py
- package.json
- main
- clean_result_sheet
- ingest.py
- devDependencies
- devDependencies
- main
- Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map
- Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before.
- Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined.
- Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis.
- Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download.
- Codex Repository Context
- fetch.py
- test.py
- preprocess.py
- eslint-plugin-react-hooks
- globals
- @types/react
- @types/react-dom
- vite
- @vitejs/plugin-react
- main
- generate_timeseries_mapping
- DataFrame
- DataFrame
- RuntimeError
- BaseModel
- get
- post
- get

## God Nodes (most connected - your core abstractions)
1. `RunStore` - 21 edges
2. `PipelineError` - 18 edges
3. `execute_stage()` - 18 edges
4. `main()` - 16 edges
5. `main()` - 16 edges
6. `stage_result()` - 14 edges
7. `create_run()` - 13 edges
8. `FusekiClient` - 12 edges
9. `FusekiClient` - 12 edges
10. `setup_environment()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `test_qudt_conversion_micro_to_milli_si_per_centimetre()` --calls--> `convert_qudt_value()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → automating_aligments/automated_alignments.py
- `test_qudt_conversion_micro_to_milli_si_per_centimetre()` --calls--> `convert_qudt_value()`  [EXTRACTED]
  lag_analytics_workspace/tests/test_analysis.py → automating_aligments/automated_alignments.py
- `run_shacl_validation()` --calls--> `validate_shacl()`  [EXTRACTED]
  pipeline/generic_pipeline.py → SHACL/SHACL_validate.py
- `test_legacy_fuseki_graph_is_normalized_to_milli_si_per_centimetre()` --calls--> `normalize_fuseki_observations()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → lag_analytics_workspace/fuseki.py
- `test_legacy_reader_prefers_new_correct_value_after_pipeline_rerun()` --calls--> `normalize_fuseki_observations()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → lag_analytics_workspace/fuseki.py

## Import Cycles
- None detected.

## Communities (111 total, 27 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.11
Nodes (4): FastAPI, ensemble_visualization(), lifespan(), xgboost_visualization()

### Community 1 - "dependencies"
Cohesion: 0.09
Nodes (48): deep_learning(), describe_data(), _feature_matrix(), lag_analysis(), machine_learning(), matrix_profile(), _number(), prepare_observations() (+40 more)

### Community 2 - "devDependencies"
Cohesion: 0.05
Nodes (50): buffer, dependencies, buffer, echarts, echarts-for-react, ldes-client, leaflet, @pola-rs/browser (+42 more)

### Community 3 - "EdgeDeepLearning.jsx"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 4 - "App.jsx"
Cohesion: 0.07
Nodes (49): deep_learning(), describe_data(), _feature_matrix(), lag_analysis(), machine_learning(), matrix_profile(), _number(), prepare_observations() (+41 more)

### Community 5 - "pipeline_core.py"
Cohesion: 0.13
Nodes (24): data_path(), ldes_artifacts(), pipeline_working_directory(), Reusable, observable stages for the canal data pipelines.  The functions in this, Run EYE and save inferred triples next to the source RDF file., Return a useful, bounded preview of a generated LDES tree.      A full run can c, Make pipeline collaborators importable without the forecasting server., Support legacy collaborators that resolve paths relative to pipeline/. (+16 more)

### Community 6 - "timeseriesforecasting.py"
Cohesion: 0.08
Nodes (18): ApiError(), App(), artifactLabel(), ArtifactPreview(), completedStatuses, DataBrowser(), fallbackUseCases, icon() (+10 more)

### Community 7 - "pipeline.py"
Cohesion: 0.14
Nodes (18): DataVisualization(), getSensorDataCache(), PREFIXES, sensorDataRegistry, buildAverageSeries(), buildForecastTimestamps(), extractSensorData(), ldesState (+10 more)

### Community 8 - "MapCard.jsx"
Cohesion: 0.09
Nodes (52): FileResponse, active_calls(), artifact(), artifact_summary(), configuration(), create_run(), download_artifact(), execute_stage() (+44 more)

### Community 9 - "RDFTSS2LDES.py"
Cohesion: 0.23
Nodes (16): comparison_visualization(), comparisonforecast(), datapreparation(), ensemble(), ensemble_visualization(), featureengineering(), identify_unique_sensors(), lightGBM_forecast_bias() (+8 more)

### Community 10 - "RDF2LDES_YMD_SPARQL_FOR_TSS.py"
Cohesion: 0.13
Nodes (18): main(), setup_environment(), step_1_fetch_data(), step_1_pre_process_waterlink(), step_2_preprocess(), step_2_rml_mapping_waterlink(), step_3_rml_mapping(), step_4_ingest_virtuoso() (+10 more)

### Community 11 - "BrowseData.jsx"
Cohesion: 0.07
Nodes (41): _conversion(), convert_qudt_value(), main(), Normalize observation values between QUDT units., Convert via the common SI reference represented by QUDT metadata., Compatibility entry point using the corrected batch implementation., Convert every SOSA observation to NEW_UNIT and serialize once.      Previous cod, transform_unit() (+33 more)

### Community 12 - "RDF2TSS_V2.py"
Cohesion: 0.18
Nodes (3): headStyles, innerStyles, styles

### Community 13 - "preprocess_waterlink.py"
Cohesion: 0.14
Nodes (23): data_path(), ldes_artifacts(), pipeline_working_directory(), Reusable, observable stages for the canal data pipelines.  The functions in this, Run EYE and save inferred triples next to the source RDF file., Return a useful, bounded preview of a generated LDES tree.      A full run can c, Make pipeline collaborators importable without the forecasting server., Support legacy collaborators that resolve paths relative to pipeline/. (+15 more)

### Community 14 - "start_preprocessing.py"
Cohesion: 0.38
Nodes (9): create_base_graph(), create_ldes_files(), delete_ldes_files(), delete_log(), divide_data(), load_graph(), main(), process_graph() (+1 more)

### Community 15 - "RDF2TSS_per_day_V1.py"
Cohesion: 0.20
Nodes (3): headStyles, innerStyles, tableStyles

### Community 16 - "main"
Cohesion: 0.33
Nodes (8): create_sensor_set(), create_tss(), load_graph(), main(), Loads a Turtle file into an RDFLib Graph., Identifies unique sensors within the graph using a SPARQL query., Transforms sensor observations into the Time Series Snippets (TSS) format., save_graph()

### Community 17 - "chronosCard.jsx"
Cohesion: 0.32
Nodes (7): build_combined_header(), clean_result_sheet(), combine_datetime(), Cleans the 'result' tab of data.xlsx.  Assumed raw layout (1-indexed rows/cols, Combine a date value and a time value into a single ISO-8601 string,     e.g. ', Combine the description / attribute name / unit of measure (rows 1, 2, 3)     i, Reads `sheet_name` from `input_path`, merges the Datum/Tijd columns into     a

### Community 18 - "machineLearningCard.jsx"
Cohesion: 0.25
Nodes (7): delete_graph(), get_query_url(), Apache Jena Fuseki graph-store client used by the pipeline., Resolve Fuseki's read-only SPARQL query endpoint from the data endpoint., Upload a Turtle file into a named graph and report an actionable result., Remove a named graph from Fuseki's Graph Store Protocol endpoint., upload_graph()

### Community 19 - "ingest.py"
Cohesion: 0.60
Nodes (5): CreateSensorSet(), CreateTSS(), LoadGraph(), main(), SaveGraph()

### Community 20 - "test.py"
Cohesion: 0.40
Nodes (4): main(), build_lstm_autoencoder(), create_sequences(), dataset : (n_samples, 1) scaled array     Returns       X : (samples, time_ste

### Community 23 - "LDESTSSChart.jsx"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map, Source Nodes

### Community 24 - "SQLChart.jsx"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before., Source Nodes

### Community 25 - "preprocess2.py"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined., Source Nodes

### Community 26 - "RML_generator.py"
Cohesion: 0.50
Nodes (3): Codex Repository Context, Instructions for Codex, System Architecture & Topology

### Community 30 - "python.worker.js"
Cohesion: 0.40
Nodes (4): Conductivity units, Fuseki configuration, Lag analytics workspace, Start

### Community 50 - "pipeline/__init__.py"
Cohesion: 0.33
Nodes (5): Deployment configuration, Generic Semantic Pipeline, Gent-Terneuzen canal, Start locally, Workflow

### Community 52 - "server.py"
Cohesion: 0.13
Nodes (29): validate_shacl(), CommandResult, csv_preview(), eye_command(), graph_name_to_uri(), ingest_graph(), normalise_stream_name(), parse_turtle() (+21 more)

### Community 58 - "pipeline/README.md"
Cohesion: 0.16
Nodes (16): chronos2forecast_visualization(), comparison_visualization(), ensemble_visualization(), lifespan(), lightGBM_visualization(), plot_sensor_data(), random_forest_visualization(), SVR_visualization() (+8 more)

### Community 59 - "main"
Cohesion: 0.23
Nodes (16): comparison_visualization(), comparisonforecast(), datapreparation(), ensemble(), ensemble_visualization(), featureengineering(), identify_unique_sensors(), lightGBM_forecast_bias() (+8 more)

### Community 60 - "RDF2LDES_YMD_SPARQL_FOR_TSS.py"
Cohesion: 0.38
Nodes (9): create_base_graph(), create_ldes_files(), delete_ldes_files(), delete_log(), divide_data(), load_graph(), main(), process_graph() (+1 more)

### Community 61 - "package.json"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 62 - "main"
Cohesion: 0.33
Nodes (8): create_sensor_set(), create_tss(), load_graph(), main(), Loads a Turtle file into an RDFLib Graph., Identifies unique sensors within the graph using a SPARQL query., Transforms sensor observations into the Time Series Snippets (TSS) format., save_graph()

### Community 63 - "clean_result_sheet"
Cohesion: 0.32
Nodes (7): build_combined_header(), clean_result_sheet(), combine_datetime(), Cleans the 'result' tab of data.xlsx.  Assumed raw layout (1-indexed rows/cols, Combine a date value and a time value into a single ISO-8601 string,     e.g. ', Combine the description / attribute name / unit of measure (rows 1, 2, 3)     i, Reads `sheet_name` from `input_path`, merges the Datum/Tijd columns into     a

### Community 64 - "ingest.py"
Cohesion: 0.25
Nodes (7): delete_graph(), get_query_url(), Apache Jena Fuseki graph-store client used by the pipeline., Resolve Fuseki's read-only SPARQL query endpoint from the data endpoint., Upload a Turtle file into a named graph and report an actionable result., Remove a named graph from Fuseki's Graph Store Protocol endpoint., upload_graph()

### Community 65 - "devDependencies"
Cohesion: 0.29
Nodes (7): devDependencies, eslint, eslint-plugin-react-refresh, eslint, eslint-plugin-react-refresh, eslint, eslint-plugin-react-refresh

### Community 66 - "devDependencies"
Cohesion: 0.29
Nodes (7): @eslint/js, vite-plugin-node-polyfills, @eslint/js, devDependencies, @eslint/js, vite-plugin-node-polyfills, vite-plugin-node-polyfills

### Community 69 - "main"
Cohesion: 0.40
Nodes (4): main(), build_lstm_autoencoder(), create_sequences(), dataset : (n_samples, 1) scaled array     Returns       X : (samples, time_ste

### Community 70 - "Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map, Source Nodes

### Community 71 - "Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before., Source Nodes

### Community 72 - "Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined., Source Nodes

### Community 73 - "Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis., Source Nodes

### Community 74 - "Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download., Source Nodes

### Community 75 - "Codex Repository Context"
Cohesion: 0.50
Nodes (3): Codex Repository Context, Instructions for Codex, System Architecture & Topology

### Community 79 - "eslint-plugin-react-hooks"
Cohesion: 0.67
Nodes (3): eslint-plugin-react-hooks, eslint-plugin-react-hooks, eslint-plugin-react-hooks

### Community 80 - "globals"
Cohesion: 0.67
Nodes (3): globals, globals, globals

### Community 81 - "@types/react"
Cohesion: 0.67
Nodes (3): @types/react, @types/react, @types/react

### Community 82 - "@types/react-dom"
Cohesion: 0.67
Nodes (3): @types/react-dom, @types/react-dom, @types/react-dom

### Community 83 - "vite"
Cohesion: 0.67
Nodes (3): vite, vite, vite

### Community 84 - "@vitejs/plugin-react"
Cohesion: 0.67
Nodes (3): @vitejs/plugin-react, @vitejs/plugin-react, @vitejs/plugin-react

## Knowledge Gaps
- **84 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `App()` (3× useful, score=2.927879513)
- `stage_result()` (2× useful, score=1.996333302)
- `step_6_RDF2LDES()` (2× useful, score=1.996126259)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `stage_result()` connect `pipeline_core.py` to `MapCard.jsx`, `BrowseData.jsx`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `create_ldes_files()` connect `RDF2LDES_YMD_SPARQL_FOR_TSS.py` to `BrowseData.jsx`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._
- **Why does `RunStore` connect `MapCard.jsx` to `server.py`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `RunStore` (e.g. with `IngestRequest` and `LdesRequest`) actually correct?**
  _`RunStore` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `URIRef` (e.g. with `create_ldes_files()` and `CreateTSS()`) actually correct?**
  _`URIRef` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _84 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11231884057971014 - nodes in this community are weakly interconnected._