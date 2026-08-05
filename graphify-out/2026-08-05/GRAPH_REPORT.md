# Graph Report - Generic Dashboard System  (2026-08-05)

## Corpus Check
- 88 files · ~302,409 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 588 nodes · 882 edges · 79 communities (56 shown, 23 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 36 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ab7c4132`
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
- preprocess2.py
- pyodidetest.jsx
- python.worker.js
- GraphCard.jsx
- RML_generator_waterlink.py
- pipeline/__init__.py
- Codex Repository Context
- QueryCard.jsx
- LDESTSSChart.jsx
- SQLChart.jsx
- TTLChart.jsx
- sample instructions.md
- analysis.py
- Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined.
- pipeline/README.md
- package.json
- main
- clean_result_sheet
- ingest.py
- devDependencies
- vite
- generate_timeseries_mapping
- contexual_matrix_profile.py
- fetch_water_link_data
- chronos2forecast
- comparisonforecast
- ensemble
- RandomForest.py

## God Nodes (most connected - your core abstractions)
1. `RunStore` - 23 edges
2. `PipelineError` - 21 edges
3. `execute_stage()` - 18 edges
4. `main()` - 16 edges
5. `create_run()` - 14 edges
6. `FusekiClient` - 11 edges
7. `setup_environment()` - 11 edges
8. `generate_ldes()` - 9 edges
9. `main()` - 9 edges
10. `AnalysisRequest` - 9 edges

## Surprising Connections (you probably didn't know these)
- `test_qudt_conversion_micro_to_milli_si_per_centimetre()` --calls--> `convert_qudt_value()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → automating_aligments/automated_alignments.py
- `run_shacl_validation()` --calls--> `validate_shacl()`  [EXTRACTED]
  pipeline/generic_pipeline.py → SHACL/SHACL_validate.py
- `test_legacy_fuseki_graph_is_normalized_to_milli_si_per_centimetre()` --calls--> `normalize_fuseki_observations()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → lag_analytics_workspace/fuseki.py
- `test_legacy_reader_prefers_new_correct_value_after_pipeline_rerun()` --calls--> `normalize_fuseki_observations()`  [INFERRED]
  lag_analytics_workspace/tests/test_analysis.py → lag_analytics_workspace/fuseki.py
- `test_shacl_violation_returns_a_report_without_raising()` --calls--> `run_shacl_validation()`  [EXTRACTED]
  pipeline/tests/test_generic_pipeline.py → pipeline/generic_pipeline.py

## Import Cycles
- None detected.

## Communities (79 total, 23 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.07
Nodes (49): deep_learning(), describe_data(), _feature_matrix(), lag_analysis(), machine_learning(), matrix_profile(), _number(), prepare_observations() (+41 more)

### Community 1 - "dependencies"
Cohesion: 0.10
Nodes (42): FileResponse, configuration(), download_artifact(), execute_stage(), get_run(), health(), ingest_stage(), IngestRequest (+34 more)

### Community 2 - "devDependencies"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Now using this document provided, can you add new subsection to the website explaining what is the usecase and what is the goal maybe add nice figure or an interactive map, Source Nodes

### Community 3 - "EdgeDeepLearning.jsx"
Cohesion: 0.26
Nodes (11): chronos2forecast_visualization(), comparison_visualization(), ensemble_visualization(), lifespan(), lightGBM_visualization(), plot_sensor_data(), random_forest_visualization(), SVR_visualization() (+3 more)

### Community 4 - "App.jsx"
Cohesion: 0.06
Nodes (33): buffer, dependencies, buffer, echarts, echarts-for-react, ldes-client, leaflet, @pola-rs/browser (+25 more)

### Community 5 - "pipeline_core.py"
Cohesion: 0.14
Nodes (23): data_path(), ldes_artifacts(), pipeline_working_directory(), Reusable, observable stages for the canal data pipelines.  The functions in this, Run EYE and save inferred triples next to the source RDF file., Return a useful, bounded preview of a generated LDES tree.      A full run can c, Make pipeline collaborators importable without the forecasting server., Support legacy collaborators that resolve paths relative to pipeline/. (+15 more)

### Community 6 - "timeseriesforecasting.py"
Cohesion: 0.17
Nodes (29): validate_shacl(), _cell_text(), CommandResult, csv_preview(), eye_command(), graph_name_to_uri(), ingest_graph(), normalise_stream_name() (+21 more)

### Community 7 - "pipeline.py"
Cohesion: 0.60
Nodes (5): CreateSensorSet(), CreateTSS(), LoadGraph(), main(), SaveGraph()

### Community 8 - "MapCard.jsx"
Cohesion: 0.29
Nodes (9): main(), setup_environment(), step_1_fetch_data(), step_1_pre_process_waterlink(), step_2_preprocess(), step_2_rml_mapping_waterlink(), step_3_rml_mapping(), step_4_ingest_virtuoso() (+1 more)

### Community 9 - "RDFTSS2LDES.py"
Cohesion: 0.14
Nodes (18): DataVisualization(), getSensorDataCache(), PREFIXES, sensorDataRegistry, buildAverageSeries(), buildForecastTimestamps(), extractSensorData(), ldesState (+10 more)

### Community 10 - "RDF2LDES_YMD_SPARQL_FOR_TSS.py"
Cohesion: 0.23
Nodes (16): comparison_visualization(), comparisonforecast(), datapreparation(), ensemble(), ensemble_visualization(), featureengineering(), identify_unique_sensors(), lightGBM_forecast_bias() (+8 more)

### Community 11 - "BrowseData.jsx"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: examine waterlink and waterinfo pipelines, you will see that I have added a new feature which is RDF2LDES. can you integrate this new feature in the frontend similar to all the other features of the pipeline that you integrated before., Source Nodes

### Community 12 - "RDF2TSS_V2.py"
Cohesion: 0.33
Nodes (8): create_sensor_set(), create_tss(), load_graph(), main(), Loads a Turtle file into an RDFLib Graph., Identifies unique sensors within the graph using a SPARQL query., Transforms sensor observations into the Time Series Snippets (TSS) format., save_graph()

### Community 13 - "preprocess_waterlink.py"
Cohesion: 0.18
Nodes (7): App(), ArtifactPreview(), completedStatuses, requestJson(), stageDefinitions, statusLabel(), StatusPill()

### Community 14 - "start_preprocessing.py"
Cohesion: 0.11
Nodes (29): _conversion(), convert_qudt_value(), main(), Normalize observation values between QUDT units., Convert via the common SI reference represented by QUDT metadata., Compatibility entry point using the corrected batch implementation., Convert every SOSA observation to NEW_UNIT and serialize once.      Previous cod, transform_unit() (+21 more)

### Community 15 - "RDF2TSS_per_day_V1.py"
Cohesion: 0.32
Nodes (7): build_combined_header(), clean_result_sheet(), combine_datetime(), Cleans the 'result' tab of data.xlsx.  Assumed raw layout (1-indexed rows/cols, Combine a date value and a time value into a single ISO-8601 string,     e.g. ', Combine the description / attribute name / unit of measure (rows 1, 2, 3)     i, Reads `sheet_name` from `input_path`, merges the Datum/Tijd columns into     a

### Community 16 - "main"
Cohesion: 0.25
Nodes (7): delete_graph(), get_query_url(), Apache Jena Fuseki graph-store client used by the pipeline., Resolve Fuseki's read-only SPARQL query endpoint from the data endpoint., Upload a Turtle file into a named graph and report an actionable result., Remove a named graph from Fuseki's Graph Store Protocol endpoint., upload_graph()

### Community 17 - "chronosCard.jsx"
Cohesion: 0.40
Nodes (4): main(), build_lstm_autoencoder(), create_sequences(), dataset : (n_samples, 1) scaled array     Returns       X : (samples, time_ste

### Community 18 - "machineLearningCard.jsx"
Cohesion: 0.18
Nodes (3): headStyles, innerStyles, styles

### Community 19 - "ingest.py"
Cohesion: 0.38
Nodes (9): create_base_graph(), create_ldes_files(), delete_ldes_files(), delete_log(), divide_data(), load_graph(), main(), process_graph() (+1 more)

### Community 20 - "test.py"
Cohesion: 0.06
Nodes (30): devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, @types/react, @types/react-dom (+22 more)

### Community 21 - "QueryCard.jsx"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: can you recheck the system, I tried using the front end testing the water-link use case. I ran step 1 just fine. in step 2 i got attention needed: name '_rml_mapping' is not defined., Source Nodes

### Community 22 - "preprocess.py"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Make the dashboard generic and remove Gent-Terneuzen traces from the active UI while implementing the eight-stage uploaded-data pipeline., Source Nodes

### Community 23 - "LDESTSSChart.jsx"
Cohesion: 0.20
Nodes (3): headStyles, innerStyles, tableStyles

### Community 25 - "preprocess2.py"
Cohesion: 0.50
Nodes (3): Codex Repository Context, Instructions for Codex, System Architecture & Topology

### Community 32 - "RML_generator_waterlink.py"
Cohesion: 0.40
Nodes (3): applications, canalPath, stations

### Community 36 - "pipeline/__init__.py"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: User reported Indusii target values far higher than the four Waterinfo sensors and asked to fix suspected unit conversion before analysis., Source Nodes

### Community 37 - "Codex Repository Context"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Examine the current repository and look at the graphify structure. We need to build a generic cloud-deployed system based on the existing pipeline and frontend, not the Gent-Terneuzen use case, with CSV upload/preview, user RML mapping, named-graph Fuseki ingestion, user SHACL-in validation, user N3 reasoning, existing RDF2TSS assumptions, user SHACL-out validation, and existing RDF2LDES assumptions plus ZIP download., Source Nodes

### Community 38 - "QueryCard.jsx"
Cohesion: 0.40
Nodes (4): Conductivity units, Fuseki configuration, Lag analytics workspace, Start

## Knowledge Gaps
- **88 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+83 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `App()` (3× useful, score=2.802610066) _(code changed — re-verify)_

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_iri()` connect `main.py` to `start_preprocessing.py`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `test_user_supplied_n3_rules_create_reasoned_rdf()` connect `start_preprocessing.py` to `dependencies`, `timeseriesforecasting.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `test_user_supplied_rml_mapping_runs_against_uploaded_filename()` connect `start_preprocessing.py` to `dependencies`, `timeseriesforecasting.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `RunStore` (e.g. with `IngestRequest` and `LdesRequest`) actually correct?**
  _`RunStore` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _88 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07486338797814207 - nodes in this community are weakly interconnected._
- **Should `dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._