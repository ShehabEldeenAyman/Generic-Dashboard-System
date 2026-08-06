<div align="center">

# Semantic Pipeline Studio

### Turn tabular data into validated, queryable, and publishable linked data

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![RDF](https://img.shields.io/badge/RDF-Semantic_Web-5B4B8A)](https://www.w3.org/RDF/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A generic, web-based workspace for converting CSV and Excel data to RDF, validating and enriching it, querying it in Apache Jena Fuseki, and packaging it as an LDES.

</div>

---

## Overview

Semantic Pipeline Studio provides one guided interface for a complete semantic-data workflow. Users bring their own tabular data and semantic contracts—the RML mapping, SHACL shapes, N3 rules, graph name, and LDES settings—while the application manages each run and exposes its generated artifacts.

The system is domain-independent. It does not assume a particular dataset or business use case, and uploaded data is stored in an isolated, run-scoped workspace suitable for a cloud deployment model.

## Pipeline at a glance

```mermaid
flowchart LR
    A["CSV or XLSX upload"] --> B["RML mapping"]
    B --> C["RDF preview and download"]
    C --> D["Fuseki named graph"]
    D --> E["SPARQL workspace"]
    B -. optional .-> F["SHACL input validation"]
    B -. optional .-> G["N3 reasoning"]
    B --> H["RDF to TSS"]
    G -. when available .-> H
    H --> I["TSS download"]
    H -. optional .-> J["SHACL output validation"]
    B --> K["RDF to LDES"]
    H --> K
    K --> L["LDES ZIP download"]
```

Optional stages do not block later processing. RDF2TSS uses reasoned RDF when a successful reasoning result exists and otherwise uses the mapped RDF directly. LDES generation can start from either mapped RDF or TSS RDF.

## Features

### 1. Tabular data input

- Upload `.csv` or `.xlsx` files from the browser.
- Inspect parsed columns, rows, and workbook metadata immediately after upload.
- Normalize the active Excel worksheet into a run-scoped CSV source for RMLMapper.
- Combine supported multi-row Excel headings and date/time columns during normalization.
- Clear a selected file before uploading or delete the active run and start over.

### 2. User-provided RML mapping

- Paste a complete RML mapping into the built-in code editor.
- See the exact prepared CSV filename that must be used as `rml:source`.
- Validate the mapping syntax and execute it with RMLMapper.
- Receive readable stage errors without taking down the application.

### 3. Mapped RDF preview and download

- Preview Turtle output between mapping and ingestion.
- Browse RDF by subject, with at most 100 instances per page.
- Move through the full result using previous and next controls.
- Download the complete mapped RDF artifact at any time.

### 4. Apache Jena Fuseki ingestion

- Choose a name or full IRI for the target named graph.
- Clear the target graph before every ingestion to prevent stale or duplicate data.
- Upload the mapped RDF through Fuseki's Graph Store Protocol.
- Keep graph selection explicit rather than silently treating a named graph as the default graph.

### 5. SPARQL query workspace

- Write and run read-only SPARQL queries against Fuseki.
- Select the intended named graph explicitly with `GRAPH <...>` in the query.
- Display `SELECT` results as a table, `ASK` results as a Boolean, and graph-query results as text.
- Cap large responses on the server to keep the interface responsive.

### 6. SHACL input validation

- Paste a SHACL shape and validate the mapped RDF.
- View and download the full SHACL validation report.
- Treat non-conformance as a reportable result—not a system failure—so later stages remain available.

### 7. Optional N3 reasoning

- Paste user-defined N3 rules and execute them with the EYE reasoner.
- Materialize inferred statements alongside the mapped RDF.
- Report inferred and total triple counts.
- Skip reasoning entirely when it is not needed.

### 8. RDF to TSS transformation

- Convert compatible SOSA/QUDT observations into Time Series Snippets.
- Prefer successfully reasoned RDF automatically, with mapped RDF as the fallback.
- Report sensor and output triple counts.
- Preview and download the generated TSS Turtle file.

### 9. SHACL output validation

- Validate generated TSS data against a user-provided output shape.
- Surface non-conformance and the complete validation report without blocking LDES generation.

### 10. RDF or TSS to LDES

- Generate an LDES from either the original mapped RDF or the generated TSS data.
- Configure the stream name and public base URL.
- Build date-based TREE fragments and indexes in a complete folder hierarchy.
- Preview the root TriG index and download the entire LDES directory as a ZIP archive.

## Run and artifact model

Each upload creates an isolated run with its own state, source files, semantic inputs, logs, and generated outputs. Stage failures are recorded on that run and returned to the interface as structured feedback rather than crashing the API.

Artifacts are first-class outputs. Depending on the stages executed, a run can expose:

- the normalized CSV source;
- the submitted RML mapping and mapped RDF;
- SHACL shapes and validation reports;
- N3 rules and reasoned RDF;
- TSS RDF;
- the LDES root index and complete ZIP package.

Deleting an active run removes its uploaded and generated files. Data previously sent to Fuseki is managed separately through its named-graph lifecycle.

## Architecture

```mermaid
flowchart TB
    UI["React + Vite dashboard"] --> API["FastAPI pipeline API"]
    API --> STORE["Run-scoped artifact store"]
    API --> RML["RMLMapper"]
    API --> SHACL["pySHACL"]
    API --> EYE["EYE N3 reasoner"]
    API --> FUSEKI["Apache Jena Fuseki"]
    API --> TSS["RDF2TSS transformer"]
    API --> LDES["RDF2LDES generator"]
    FUSEKI --> API
```

| Layer | Responsibility |
| --- | --- |
| React frontend | Guided pipeline, editors, previews, result tables, status feedback, and downloads |
| FastAPI backend | Run lifecycle, validation, stage orchestration, error isolation, and artifact delivery |
| RMLMapper | User-controlled tabular-to-RDF mapping |
| Apache Jena Fuseki | Named-graph storage and SPARQL query execution |
| pySHACL | Input RDF and TSS conformance validation |
| EYE | Optional N3 rule execution and inference materialization |
| RDF2TSS | Conversion of compatible semantic observations to Time Series Snippets |
| RDF2LDES | TREE/LDES hierarchy generation and ZIP packaging |

## API surface

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | API health check |
| `GET /api/config` | Fuseki and local tool readiness |
| `POST /api/runs` | Create a run from a CSV or XLSX upload |
| `GET /api/runs/{run_id}` | Retrieve current run state |
| `DELETE /api/runs/{run_id}` | Delete a run and its files |
| `POST /api/runs/{run_id}/stages/rml` | Run the supplied RML mapping |
| `GET /api/runs/{run_id}/rdf-preview` | Retrieve a paginated mapped-RDF preview |
| `POST /api/runs/{run_id}/stages/ingest` | Clear and replace a Fuseki named graph |
| `POST /api/runs/{run_id}/sparql` | Execute a SPARQL query |
| `POST /api/runs/{run_id}/stages/shacl-in` | Validate mapped RDF |
| `POST /api/runs/{run_id}/stages/reason` | Apply N3 reasoning rules |
| `POST /api/runs/{run_id}/stages/rdf2tss` | Generate TSS RDF |
| `POST /api/runs/{run_id}/stages/shacl-out` | Validate TSS RDF |
| `POST /api/runs/{run_id}/stages/rdf2ldes` | Generate and package an LDES |
| `GET /api/runs/{run_id}/artifacts/{artifact_id}` | Download a generated artifact |

## Repository structure

```text
.
├── frontend/                    # React dashboard and Vite configuration
├── pipeline/                    # FastAPI API, orchestration, run store, and tests
├── RDF2TSS_V2/                  # RDF-to-TSS transformation
├── RDF2LDES/                    # TSS/RDF-to-LDES generation
├── SHACL/                       # SHACL validation adapter
├── triple_store_ingestion/      # Fuseki graph-store and query client
├── test-data/                   # Preserved sample data and semantic contracts
├── graphify-out/                # Current code-topology graph and report
├── requirements.txt             # Backend runtime dependencies
└── LICENSE                      # MIT license
```

## Sample assets

The preserved `test-data/` directory contains a representative Excel workbook, CSV source, RML mapping, SPARQL query, and input/output SHACL shapes. These files are useful for exercising the pipeline and as references for the expected semantic inputs.

## Current compatibility contract

RDF2TSS and RDF2LDES currently use the project's existing semantic queries. Mapped RDF intended for these stages must therefore provide the SOSA observation structure, sensor, timestamp, simple result, observed property, and QUDT unit expected by those queries. Making these transformation queries user-configurable is intentionally left for a later iteration.

For Excel uploads, the active worksheet is used. RMLMapper receives the normalized CSV artifact rather than the original workbook, and the dashboard displays its exact logical-source filename.

## Project status

The functional pipeline and dashboard are in place. Installation, local development, and cloud-deployment instructions will be added in a dedicated documentation pass.

## License

This project is available under the [MIT License](LICENSE).
