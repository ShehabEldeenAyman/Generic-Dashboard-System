# Testing

Semantic Data Studio has four test suites. They range from fast checks of single functions to the whole dashboard driven in a real browser against a real triple store.

**Contents:** [Quick start](#quick-start) · [The test suites](#the-test-suites) · [What the live and browser tests need](#what-the-live-and-browser-tests-need) · [How they run](#how-they-run) · [Choosing tests](#choosing-tests) · [Writing new tests](#writing-new-tests)

## Quick start

From the repository folder:

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium        # once, for the browser tests (or use Google Chrome)
(cd frontend && npm run build)               # the browser tests use the built dashboard

python -m pytest                             # every Python test that can run on this machine
python -m pytest -m "not live and not e2e"   # the fast tests only
cd frontend && npm test                      # the frontend tests
```

Tests whose tools are missing are skipped rather than failed. `python -m pytest -rs` lists what was skipped and why.

On the development machine, 136 Python tests pass in about 75 seconds; the 126 fast tests take about 5 seconds. The 28 frontend tests take under a second. With only the bundled EYE, 132 pass and the 4 tests that compare native and bundled EYE are skipped.

## The test suites

| File | Suite | What it checks |
| --- | --- | --- |
| `pipeline/tests/test_api.py` | Backend | Service status (health, configuration, Fuseki offline). Uploads: size limit, delimiters, encodings, empty files, broken workbooks, safe file names. Every stage refuses to run before its prerequisite, and explains failures (mapping that is not Turtle, missing RMLMapper, rules without `sh:rule`, publishing errors). Downloads, paging, artifacts, and that files stay inside their dataset folder. Every built-in query operation builds valid SPARQL and escapes search text. Errors from the Fuseki client and agent edge cases. |
| `pipeline/tests/test_generic_pipeline.py` | Backend | Uploads (CSV, Excel with multi-row headings and date and time columns), RML mapping with RMLMapper, SHACL validation and rules, publishing (replace and add), downloads in four formats, and the operations API. |
| `pipeline/tests/test_reasoning.py` | Backend | EYE: reading rules, explaining errors (syntax, inference fuse, memory), parsing output, chunked input with blank nodes, choosing native or bundled EYE, the facts each example derives, the API, and native and bundled EYE deriving the same facts. |
| `pipeline/tests/test_orchestration.py` | Backend | Running agents: chosen graphs become the query's default graph while every graph stays reachable with `GRAPH`, CONSTRUCT output replaces the agent's graph, empty output, an agent reading its own output, clean-up, and API errors. |
| `pipeline/tests/test_run_launcher.py` | Backend | `run.py`: missing packages, missing npm, when the dashboard is rebuilt, when the bundled EYE is installed, the commands it starts, and development mode. |
| `pipeline/tests/test_live_services.py` | Live | The sample data through the whole pipeline against a real Fuseki, RMLMapper, and EYE: mapping, validation, SHACL rules, reasoning, publishing (replace and add), every query operation, and downloads in four formats. Also Fuseki rejecting bad queries and updates, graph names with spaces, and agents chaining through their output graphs. |
| `pipeline/tests/test_e2e_browser.py` | Browser | Navigation, the Services panel, and every empty state. Every view at phone width and in dark mode. Upload checks and removing a dataset. The pipeline from upload to query, including downloads, paging through the RDF, publishing, query operations, the SPARQL editor, and CSV export. Every reasoning example and the error messages. Agent orchestration: environments, ticking outputs, inserting references, stale agents and Run all, renaming, surviving a reload, errors, loop prevention, clean-up when deleting, and the example environment. |
| `frontend/tests/orchestration.test.js` | Frontend | Agent and reference ids, recognising the query form, references (comments, unknown references, renaming), dependencies, run order and loop detection, stale, edited, and waiting agents, new names, the example environment, and browser storage. |
| `frontend/tests/format.test.js` | Frontend | Numbers and sizes, short IRIs, recognising agent output graphs, the current RDF, CSV export, and relative times. |

## What the live and browser tests need

- **Java 21 or newer** and **Apache Jena Fuseki**. The tests look for `fuseki-server.jar` through the `FUSEKI_JAR` environment variable (the file) or `FUSEKI_HOME` (the unzipped folder), and otherwise in `~/Downloads/apache-jena-fuseki-*`, `~/apache-jena-fuseki-*`, and `/opt/apache-jena-fuseki*`.
- **RMLMapper** (`pipeline/rmlmapper.jar`) and **EYE** (native or bundled) for the pipeline tests.
- For the browser tests, also:
  - **Playwright**: `pip install playwright`, then `python -m playwright install chromium`. A local Google Chrome is used when it is installed.
  - **A built dashboard** in `frontend/dist`: run `npm run build` in `frontend/`, or start `python run.py` once.

## How they run

- **Their own Fuseki.** The first live or browser test starts an in-memory Fuseki on a free port, and every test empties it before it starts. The Fuseki you use on port 3030 and the app on port 8000 are never touched.
- **Live tests** call the API inside the test process, pointed at that Fuseki.
- **Browser tests** start the app on another free port, with its own storage folder. Every test gets a fresh browser profile, so no environments or datasets leak between tests. An error in the browser console fails the test, except for errors the test causes on purpose.

## Choosing tests

| Command | Runs |
| --- | --- |
| `python -m pytest -m "not live and not e2e"` | Only the fast tests |
| `python -m pytest -m live` | Only the live tests |
| `python -m pytest -m e2e` | Only the browser tests |
| `python -m pytest -k orchestration` | Every test with "orchestration" in its name |
| `python -m pytest -rs` | Everything, and lists the skipped tests with the reason |

When native EYE is installed, the tests use it, and the tests comparing native and bundled EYE run too. To test the bundled build on its own, leave native EYE off the `PATH` for that run, for example `PATH=$(echo $PATH | sed "s#$HOME/.local/bin:##g") python -m pytest`.

## Writing new tests

- **Backend tests** use `TestClient(playground_server.app)` with a `RunStore` in a temporary folder; see the `store` and `client` fixtures in `test_api.py`.
- **Tests that need Fuseki** use the `live_fuseki` fixture, which points the app at the empty throwaway Fuseki, or `clean_fuseki` for just its URL. Mark the module with `pytestmark = pytest.mark.live`.
- **Browser tests** use the `session` fixture (`session.page`, `session.view`, `session.open(view)`), and are marked `e2e`. Two things to know:
  - Every workspace stays in the page, hidden when not shown, so look things up within `session.view`, the visible workspace.
  - Playwright locators are evaluated when used: `cards.last` points at whichever card is last at that moment. Use `cards.nth(position)` for a fixed card.
- **Frontend tests** use Node's built-in test runner (`node:test`); add files named `*.test.js` to `frontend/tests/`.
