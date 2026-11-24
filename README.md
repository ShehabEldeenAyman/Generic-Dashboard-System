<div align="center">

# 🧭 Semantic Data Studio

**Turn spreadsheets into a validated, queryable knowledge graph, all in one dashboard.**

Upload a CSV or Excel file, map it to RDF with RML, check and enrich it with SHACL,<br>
infer new facts with N3 rules and the EYE reasoner, publish it to Apache Jena Fuseki,<br>
and explore it with ready-made queries, SPARQL, or chains of SPARQL agents.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Apache Jena Fuseki](https://img.shields.io/badge/Apache_Jena-Fuseki-D22128?logo=apache&logoColor=white)](https://jena.apache.org/documentation/fuseki2/)
[![SHACL](https://img.shields.io/badge/W3C-SHACL-005A9C)](https://www.w3.org/TR/shacl/)
[![EYE](https://img.shields.io/badge/EYE-N3_reasoner-7C3AED)](https://eyereasoner.github.io/eye/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<img src="docs/images/overview.png" alt="Semantic Data Studio overview page with dataset, triples, data quality, published graph and triple store tiles" width="900">

[Features](#-features) · [Formats](#-supported-data-formats) · [Reasoning](#-reasoning-with-eye) · [Orchestration](#-agent-orchestration) · [Installation](#-installation) · [Quick tour](#-quick-tour) · [Agent API](#-query--agent-api) · [Troubleshooting](#-troubleshooting)

</div>

---

## ✨ Features

| | Workspace | What you can do |
| :---: | --- | --- |
| 📊 | **Overview** | See the dataset size, RDF triple count, data quality, published graph, and triple-store status at a glance, with quick actions and recent activity. |
| 📁 | **Data** | Upload `.csv` or `.xlsx` files ([details](#-supported-data-formats)). Preview rows, columns, and the file name your mapping should reference. Multi-row Excel headers and split date/time columns are merged automatically. |
| 🔀 | **Mapping** | **Paste** an RML mapping or **upload** a mapping file, then generate RDF with RMLMapper. Column names and the logical-source name are shown next to the editor. |
| 🛡️ | **Data quality** | **Paste** or **upload** SHACL shapes. **Validate** against SHACL Core and SPARQL-based constraints, with a searchable table of violations, warnings, and notes. **Apply rules** (`sh:TripleRule`, `sh:SPARQLRule`) to enrich the data with inferred facts. |
| 💡 | **Reasoning** | **Paste** or **upload** N3 rules, or start from one of four **examples**. The **EYE reasoner** adds the facts the rules imply and shows which classes and properties it inferred, with a sample. A `log:query` limits what is added. See the [reasoning guide](docs/reasoning.md). |
| 🗄️ | **Knowledge graph** | **Download** the RDF as Turtle, N-Triples, JSON-LD, or RDF/XML. **Publish** it to a Fuseki named graph, replacing or adding to its content. Browse it entity by entity. |
| 🤖 | **Query & Agent** | Query **any graph** in Fuseki, no upload needed. Use ready-made operations (overview, entity types, property usage, search, and more) or write SPARQL, then export results as CSV. The operations are also exposed as an API that AI agents can call as tools. |
| 🧩 | **Agent orchestration** | Create **environments** of **agents** (SPARQL queries). A CONSTRUCT agent saves its result as a **temporary graph** that other agents can read, by ticking it or inserting a reference, so you never type its name. Agents that depend on a re-run agent are marked **stale**, and **Run all** runs them in order. See the [orchestration guide](docs/orchestration.md). |

You can open the workspaces in any order. Each one says what it needs before it can run.

<table>
  <tr>
    <td width="50%"><img src="docs/images/data-quality.png" alt="Data quality workspace showing SHACL validation results with severity filters"><p align="center"><b>Data quality:</b> SHACL validation results</p></td>
    <td width="50%"><img src="docs/images/query-agent.png" alt="Query and Agent workspace with graph list, operations and a results table"><p align="center"><b>Query &amp; Agent:</b> operations on the triple store</p></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/images/reasoning.png" alt="Reasoning workspace with the facts EYE inferred: classes assigned and a sample of inferred triples"><p align="center"><b>Reasoning:</b> facts inferred by EYE</p></td>
    <td width="50%"><img src="docs/images/knowledge-graph.png" alt="Knowledge graph workspace with download formats, Fuseki publishing and an RDF browser"><p align="center"><b>Knowledge graph:</b> download, publish, and browse RDF</p></td>
  </tr>
  <tr>
    <td colspan="2"><img src="docs/images/orchestration.png" alt="Agent orchestration workspace with an environment of three agents; the first CONSTRUCT agent saved 10,532 triples to its output graph"><p align="center"><b>Agent orchestration:</b> SPARQL agents that build on each other's results</p></td>
  </tr>
</table>

## 🔄 How it works

```mermaid
flowchart LR
    A["📁 CSV / XLSX"] --> B["🔀 RML mapping"]
    B --> R["Mapped RDF"]
    R -. optional .-> S["✨ SHACL rules"]
    S --> E["Enriched RDF"]
    R -. optional .-> N["💡 EYE reasoning"]
    E -. optional .-> N
    N --> X["Reasoned RDF"]
    R --> C(("Current RDF"))
    E --> C
    X --> C
    C --> V["🛡️ SHACL validation"]
    C --> D["⬇️ Download"]
    C --> F["🗄️ Fuseki named graph"]
    F --> Q["🤖 Query & Agent"]
```

The **current RDF** is the reasoned RDF when EYE has run, otherwise the enriched RDF when SHACL rules have run, and otherwise the mapped RDF. EYE reasons over the enriched RDF when there is one. Validation, downloads, publishing, and the RDF browser all use the current RDF.


## 📁 Supported data formats

The **Upload a dataset** option accepts **CSV (`.csv`)** and **Excel (`.xlsx`)** files up to **50 MB** (configurable with `MAX_UPLOAD_BYTES`).

| Format | How it's read |
| --- | --- |
| **`.csv`** | The delimiter is detected automatically (comma, semicolon, tab, or pipe). UTF-8 encoding, with Latin-1 as a fallback. The first row must hold the column names. For tab-separated files, rename `.tsv` to `.csv`. |
| **`.xlsx`** | Only the **active worksheet** is used. Headings spread over several rows are merged into one column name (for example `Ambient temperature \| SENSOR_A \| degC`). A date column directly followed by a time column becomes one `DateTime` column. Formulas use their last calculated values. The sheet is converted to CSV for RMLMapper, so your mapping references `<name>.csv`. |

> [!NOTE]
> Older Excel files (`.xls`), macro-enabled workbooks (`.xlsm`), OpenDocument spreadsheets (`.ods`), JSON, and XML are **not supported**. Save them as `.xlsx` or `.csv` first.

## 💡 Reasoning with EYE

The **Reasoning** workspace runs [Notation3 (N3)](https://w3c.github.io/N3/spec/) rules with the [EYE reasoner](https://eyereasoner.github.io/eye/) and adds the facts they imply to your data: new classes, links, summaries, or quality flags. You can paste rules, upload an `.n3` file, or load one of the examples in [`reasoning/examples/`](reasoning/examples):

| Example | What it shows | New triples on the sample data |
| --- | --- | ---: |
| **Ontology reasoning** | RDFS and OWL rules with axioms from the SOSA/SSN ontology | 5,388 |
| **Classify readings** | Thresholds stored as facts, numeric comparisons, and scoped negation | 5,386 |
| **Summarise each sensor** | Aggregation with `log:collectAllIn` | 28 |
| **Detect sudden changes** | Date-time arithmetic, and `log:query` to add only selected facts | 122 |

EYE works out of the box: `python run.py` installs the WebAssembly build of EYE (npm package [`eyereasoner`](https://www.npmjs.com/package/eyereasoner)), which runs on Node.js. For large datasets you can install native EYE; the app uses it automatically when `eye` is on your `PATH`.

📖 The [reasoning guide](docs/reasoning.md) covers writing rules, each example in detail, validating inferred facts, performance, and installing native EYE.

## 🧩 Agent orchestration

An **environment** holds **agents**, and every agent is a SPARQL query. Press **New** to create an environment, then **Add agent**:

- **A CONSTRUCT agent saves its result** as a temporary graph in Fuseki, its *output graph*. Every run replaces it. SELECT and ASK agents show their results.
- **Other agents read it without typing its name.** Tick it under **Reads from**, next to your original graphs; ticked graphs are combined, so the query needs no `FROM` or `GRAPH`. Or pick it from **Insert reference**, which adds a short reference such as `<agent:high-readings>` for queries that treat graphs separately.
- **Chains stay consistent.** When an agent runs again, the agents that read its output are marked **stale**. **Run all** runs every agent after the agents it reads from, and agents cannot read from each other in a loop.
- **Environments are saved in your browser**; output graphs live in Fuseki. Deleting an agent or an environment removes its output graphs.

Press **Try an example** for three agents on the sample data: a CONSTRUCT agent saves the high conductivity readings, one agent counts them per sensor by reading that output, and one compares it with the original graph.

📖 The [orchestration guide](docs/orchestration.md) explains both ways of reading graphs, the statuses, where everything is stored, and the API.

---

## 🚀 Installation

Semantic Data Studio has four parts: this application (a Python backend plus a React frontend), **RMLMapper** for the mapping step, **Apache Jena Fuseki** as the triple store, and the **EYE reasoner** for N3 rules. You install RMLMapper and Fuseki separately; both are free downloads. EYE is installed for you.

### Prerequisites

| Software | Version | Needed for | Check with |
| --- | --- | --- | --- |
| [Python](https://www.python.org/downloads/) | 3.10 or newer | Backend | `python --version` |
| [Node.js](https://nodejs.org/) (includes npm) | 20.19+ or 22.12+ | Building the dashboard and running the bundled EYE reasoner | `node --version` |
| [Java](https://adoptium.net/) | 21 or newer | Running RMLMapper and Fuseki | `java -version` |
| [RMLMapper](https://github.com/RMLio/rmlmapper-java/releases) | latest release | Mapping tabular data to RDF | see step 3 |
| [Apache Jena Fuseki](https://jena.apache.org/download/) | latest release | Storing and querying RDF | see step 4 |
| [EYE reasoner](https://eyereasoner.github.io/eye/) | installed for you (native EYE optional) | Reasoning with N3 rules | see step 5 |

### 1. Get the code

```bash
git clone https://github.com/ShehabEldeenAyman/Generic-Dashboard-System.git
cd Generic-Dashboard-System
git checkout December-2026-Demo
```

### 2. Install the Python dependencies

```bash
pip install -r requirements.txt
```

> [!TIP]
> To keep the project's packages separate from the rest of your system, create a virtual environment first:
> `python -m venv .venv`, then `source .venv/bin/activate` (macOS/Linux) or `.\.venv\Scripts\Activate.ps1` (Windows).

You don't need to install the frontend dependencies by hand. `run.py` runs `npm install` the first time it starts.

### 3. Download and add RMLMapper

> [!IMPORTANT]
> The mapping step needs RMLMapper. It isn't included in the repository because of its size.

1. Open the [RMLMapper releases page](https://github.com/RMLio/rmlmapper-java/releases) and pick the latest release.
2. Under **Assets**, download the file ending in **`-all.jar`** (for example `rmlmapper-8.x.x-r…-all.jar`). This version bundles everything RMLMapper needs.
3. Rename it to **`rmlmapper.jar`** and move it into this repository's **`pipeline/`** folder:

   ```text
   Generic-Dashboard-System/
   └── pipeline/
       └── rmlmapper.jar   ← here
   ```

   On macOS or Linux, once the download has finished:

   ```bash
   mv ~/Downloads/rmlmapper-*-all.jar pipeline/rmlmapper.jar
   ```

The JAR is ignored by Git. To keep it somewhere else, set the `RML_MAPPER_JAR` environment variable to its full path.

### 4. Install and start Apache Jena Fuseki

> [!IMPORTANT]
> Publishing and querying need a running Fuseki server with a dataset named **`dataset`**.

1. Go to the [Apache Jena download page](https://jena.apache.org/download/).
2. Download **`apache-jena-fuseki-<version>.zip`** (or `.tar.gz`).
   Don't download `apache-jena-<version>`; that archive only has command-line tools, not the server.
3. Unzip it anywhere, for example in your home folder.
4. Open a **new terminal**, go into the unzipped folder, and start Fuseki:

   **macOS / Linux**
   ```bash
   cd ~/apache-jena-fuseki-<version>
   ./fuseki-server --update --mem /dataset
   ```

   **Windows (PowerShell)**
   ```powershell
   cd $HOME\apache-jena-fuseki-<version>
   .\fuseki-server.bat --update --mem /dataset
   ```

5. Leave this terminal open; closing it stops Fuseki. Fuseki's own web interface is at <http://localhost:3030>.

`--mem` keeps data in memory, so it's erased when Fuseki stops. To keep your data between restarts, use persistent storage instead:

```bash
./fuseki-server --update --tdb2 --loc=databases/dataset /dataset
```

### 5. The EYE reasoner (installed for you)

There is nothing to do for the Reasoning workspace. The first time `python run.py` starts, it installs the WebAssembly build of EYE (npm package [`eyereasoner`](https://www.npmjs.com/package/eyereasoner)) into `reasoning/node_modules`. It runs on the Node.js you installed for the dashboard. If you start the backend without `run.py`, run `npm ci` in the `reasoning` folder once.

> [!TIP]
> For large datasets, install **native EYE** instead:
>
> 1. Install [SWI-Prolog](https://www.swi-prolog.org/Download.html): `brew install swi-prolog` on macOS, `sudo apt install swi-prolog` on Ubuntu, or the installer on Windows. Without administrator rights: `conda create -n eye-swipl -c conda-forge swi-prolog`.
> 2. Download the source code of the [latest EYE release](https://github.com/eyereasoner/eye/releases/latest), unzip it, and run `./install.sh --prefix=$HOME/.local` in it while `swipl` is on your `PATH`. This creates `$HOME/.local/bin/eye`; make sure that folder is on your `PATH`. On Windows, run `install.cmd` and add `C:\Program Files\eye\bin` to your `PATH`.
> 3. Check that `eye --version` works. The app then uses native EYE automatically. To use an `eye` that is not on your `PATH`, set `EYE_COMMAND` to its full path.
>
> More in [Installing native EYE](docs/reasoning.md#installing-native-eye), including what to do when `swipl` is not on your `PATH`.

### 6. Run Semantic Data Studio

In another terminal, from the repository folder:

```bash
python run.py
```

Then open **<http://localhost:8000>**.

The first start installs the EYE reasoner and builds the dashboard, which takes a moment. After that it only rebuilds when the frontend code changes.

### ✅ Check your setup

The **Services** panel at the bottom of the sidebar should show:

| Service | Expected | If not |
| --- | --- | --- |
| Fuseki | 🟢 Connected | Start Fuseki (step 4), then click the refresh icon in the panel. |
| RMLMapper | 🟢 Ready | Check that the file is exactly `pipeline/rmlmapper.jar` (step 3). |
| Java | 🟢 Found | Install Java 21+ and make sure `java` is on your `PATH`. |
| EYE reasoner | 🟢 Ready | Start the app with `python run.py` so it can install the reasoner (step 5). Hover over the status to see why it is missing. |

### `run.py` options

| Command | What it does |
| --- | --- |
| `python run.py` | Installs the EYE reasoner and builds the dashboard if needed, then serves the dashboard and API on port 8000. |
| `python run.py --dev` | Development mode: auto-reloading backend on port 8000 and Vite dev server on <http://localhost:5173>. Ctrl+C stops both. |
| `python run.py --rebuild` | Forces a fresh dashboard build. |
| `python run.py --port 9000` | Uses another port. |
| `python run.py --host 0.0.0.0` | Makes the dashboard reachable from other machines on your network. |

---

## 🧪 Quick tour

The `test-data/` folder has everything you need for a first run:

1. **Data:** upload `test-data/waterinfo-sample.csv`: two weeks of conductivity readings from four sensors (5,374 rows).
2. **Mapping:** open `test-data/rml.ttl.txt`, change `rml:source "data.csv"` to `rml:source "waterinfo-sample.csv"`, then paste the mapping or upload the edited file. Click **Generate RDF** (32,244 triples).
3. **Data quality:** upload `test-data/SHACL_in.ttl` and click **Validate data**. The mapped RDF conforms.
4. **Reasoning:** click **Use** next to **Classify readings**, then **Run reasoner**. EYE adds 5,386 triples: a salinity class for every reading and a status for every sensor. Try the other examples as well.
5. **Data quality:** click **Validate data** again. It now checks the reasoned RDF.
6. **Knowledge graph:** download the RDF in your preferred format, or enter a graph name such as `waterinfo-sample` and click **Publish**.
7. **Query & Agent:** pick the graph and run **Entity types**. The classes EYE inferred are listed next to the observations. You can also switch to the SPARQL editor.
8. **Agent orchestration:** press **Try an example**, then **Run all**. The first agent saves 10,532 triples of high readings as a temporary graph, and the other two agents build on it.

> [!NOTE]
> The file name in `rml:source` must match the name shown on the Data page exactly. Uploading `sample.xlsx` gives `sample.csv`, because Excel files are converted to CSV for RMLMapper. Use the file name only, not a path. Column names in `rr:template` and `rml:reference` must also match the headers exactly.

`test-data/waterinfo.csv` is the full export (139,645 rows, 837,870 triples once mapped). Use it to try larger data: validation and reasoning then take minutes rather than seconds.

---

## 🤖 Query & Agent API

The operations in the Query & Agent workspace are published as a catalog with typed parameters, so an AI agent can register each one as a tool. Parameters are validated and escaped on the server, and every operation is read-only.

```bash
# Discover the available operations
curl http://localhost:8000/api/store/operations

# Run one
curl -X POST http://localhost:8000/api/store/operations/entity_types \
  -H "Content-Type: application/json" \
  -d '{"parameters": {"graph": "https://example.org/graphs/waterinfo", "limit": 10}}'
```

<details>
<summary><b>Full API reference</b></summary>

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Health check |
| `GET /api/config` | Fuseki connection and tool readiness |
| `POST /api/runs` | Create a dataset from a CSV or XLSX upload |
| `GET /api/runs/{id}` · `DELETE /api/runs/{id}` | Read or remove a dataset |
| `POST /api/runs/{id}/stages/rml` | Run an RML mapping (`mapping`, optional `source_name`) |
| `POST /api/runs/{id}/stages/shacl` | Validate the current RDF (`shapes`, optional `source_name`) |
| `POST /api/runs/{id}/stages/shacl-rules` | Apply SHACL rules and create enriched RDF |
| `POST /api/runs/{id}/stages/reasoning` | Run N3 rules with EYE and create reasoned RDF (`rules`, optional `source_name`, `example_id`) |
| `GET /api/reasoning/examples` | Example N3 rule sets, with their text |
| `POST /api/runs/{id}/stages/ingest` | Publish to a named graph (`graph_name`, `mode`: `replace` or `append`) |
| `GET /api/runs/{id}/rdf?format=` | Download the current RDF (`turtle`, `ntriples`, `jsonld`, `xml`) |
| `GET /api/runs/{id}/rdf-preview` | Page through the current RDF by entity |
| `GET /api/runs/{id}/artifacts/{artifact_id}` | Download a stored file (mapping, shapes, report) |
| `GET /api/store/graphs` | Named graphs in Fuseki with triple counts |
| `POST /api/store/query` | Run a read-only SPARQL query |
| `GET /api/store/operations` | Operations catalog |
| `POST /api/store/operations/{id}` | Run an operation |
| `POST /api/orchestration/run` | Run an agent over chosen graphs; CONSTRUCT output replaces its output graph (`environment_id`, `agent_id`, `query`, `sources`) |
| `DELETE /api/orchestration/environments/{id}/outputs` | Remove an environment's output graphs (optional `agent_id`) |

Interactive documentation is at <http://localhost:8000/docs> while the app is running.

</details>

---

## ⚙️ Configuration

All settings are optional environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `FUSEKI_DATA_URL` | `http://localhost:3030/dataset/data` | Fuseki Graph Store endpoint |
| `FUSEKI_QUERY_URL` | derived from the data URL | Fuseki SPARQL endpoint |
| `FUSEKI_GRAPH_BASE` | `https://example.org/graphs/` | Base IRI for short graph names and agent output graphs |
| `RML_MAPPER_JAR` | `pipeline/rmlmapper.jar` | Location of RMLMapper |
| `EYE_COMMAND` | `eye` on `PATH`, else the bundled build | Command that starts native EYE |
| `PIPELINE_STORAGE_DIR` | system temp folder | Where uploaded and generated files are kept |
| `MAX_UPLOAD_BYTES` | 50 MB | Upload size limit |
| `PIPELINE_COMMAND_TIMEOUT` | `300` | Time limit for RMLMapper and EYE, in seconds |
| `SPARQL_RESULT_ROW_LIMIT` | `1000` | Maximum rows returned per query |

---

## 🩺 Troubleshooting

<details>
<summary><b><code>ModuleNotFoundError: No module named 'fastapi'</code></b></summary>

The Python running `run.py` doesn't have the requirements installed. Run `pip install -r requirements.txt` with that same Python. If you use a virtual environment, activate it first. `run.py` lists any missing packages before it starts.
</details>

<details>
<summary><b>Fuseki shows "Offline"</b></summary>

Make sure Fuseki is running in its own terminal and was started with the dataset name `/dataset` on port 3030. Then click the refresh icon in the sidebar's Services panel. For a different host, port, or dataset name, set `FUSEKI_DATA_URL`.
</details>

<details>
<summary><b>"Please upload a .csv or .xlsx file"</b></summary>

Only `.csv` and `.xlsx` files are accepted. Save `.xls`, `.xlsm`, or `.ods` workbooks as `.xlsx` (in Excel: *File → Save As → Excel Workbook*), and rename tab-separated `.tsv` files to `.csv`. See [Supported data formats](#-supported-data-formats).
</details>

<details>
<summary><b>RMLMapper shows "Missing"</b></summary>

The file must be at `pipeline/rmlmapper.jar` with exactly that name. Download the `-all.jar` asset, not the source code. The dashboard picks it up when you refresh the page.
</details>

<details>
<summary><b>"RMLMapper produced zero triples"</b></summary>

Usually `rml:source` doesn't match the file name shown on the Data page, or a column name in the mapping doesn't match the CSV header. Both are case-sensitive.
</details>

<details>
<summary><b>EYE reasoner shows "Missing"</b></summary>

The bundled reasoner needs Node.js and the npm package in `reasoning/node_modules`. Start the app with `python run.py`, which installs it, or run `npm ci` in the `reasoning` folder. Then click the refresh icon in the Services panel. If you set `EYE_COMMAND`, check that it points to a working `eye`.
</details>

<details>
<summary><b>Reasoning fails: syntax error, inference fuse, or out of memory</b></summary>

The message says what went wrong, and **Technical log** shows EYE's own output. A syntax error names the line after which EYE stopped reading. An inference fuse means a rule with the conclusion `false` matched your data. For memory or time limits on large data, install native EYE. See [Troubleshooting](docs/reasoning.md#troubleshooting) in the reasoning guide.
</details>

<details>
<summary><b><code>UnsupportedClassVersionError</code> or Java errors</b></summary>

Your Java is too old. Install Java 21 or newer and check with `java -version`.
</details>

<details>
<summary><b><code>npm was not found on PATH</code></b></summary>

Install Node.js, which includes npm. If you installed it with nvm, open a new terminal so it's on your `PATH`, then run `python run.py` again.
</details>

<details>
<summary><b>Validation or rules are slow on large files</b></summary>

pySHACL runs SPARQL-based constraints and rules once per targeted record, so they take a few seconds per thousand records. SHACL Core constraints (cardinality, datatypes, patterns) are much faster. Rules run once, in `sh:order`. Validation doesn't re-run them, so apply rules first when your constraints depend on inferred facts.
</details>

---

## 🗂️ Project structure

```text
Generic-Dashboard-System/
├── run.py                       # One-command launcher
├── requirements.txt             # Python dependencies
├── frontend/                    # React + Vite dashboard
│   └── src/
│       ├── views/               # Overview, Data, Mapping, Data quality, Reasoning, Knowledge graph, Query & Agent, Agent orchestration
│       ├── orchestration.js     # Environments and agents kept in the browser
│       └── components/          # Shared UI, paste-or-upload input, query results
├── pipeline/
│   ├── playground_server.py     # FastAPI app; also serves the built dashboard
│   ├── generic_pipeline.py      # Parsing, RMLMapper, SHACL actions, RDF export, ingestion
│   ├── run_store.py             # Dataset state and files
│   ├── rmlmapper.jar            # ← you add this (step 3)
│   └── tests/
├── SHACL/shacl_engine.py        # SHACL validation and rules
├── reasoning/
│   ├── eye_engine.py            # Runs EYE (native or bundled) and reads its output
│   ├── examples/                # Example N3 rule sets
│   └── package.json             # Bundled EYE (npm package eyereasoner)
├── query_agent/
│   ├── operations.py            # Query operations catalog
│   └── orchestration.py         # Runs agents and keeps their output graphs
├── triple_store_ingestion/      # Fuseki client
├── docs/
│   ├── reasoning.md             # Reasoning guide
│   ├── orchestration.md         # Agent orchestration guide
│   └── images/                  # Screenshots
└── test-data/                   # Sample data, mapping, and shapes
```

## 🧪 Running the tests

```bash
pip install pytest
python -m pytest pipeline/tests
```

Tests that run RMLMapper are skipped automatically when Java or `pipeline/rmlmapper.jar` is missing. Tests that run EYE are skipped when neither native EYE nor the bundled reasoner is available.

## 📄 License

Released under the [MIT License](LICENSE).
