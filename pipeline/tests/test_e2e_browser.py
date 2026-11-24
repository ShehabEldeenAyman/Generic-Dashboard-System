"""The dashboard in a real browser, against the app and a throwaway Fuseki.

Needs Playwright (pip install playwright, then: python -m playwright install chromium,
or a local Google Chrome), a built frontend (npm run build in frontend/), and the
Fuseki download that conftest.py looks for. The pipeline tests also need
pipeline/rmlmapper.jar and EYE.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

import pytest
import requests

from pipeline import generic_pipeline
from pipeline.tests.conftest import ROOT, TEST_DATA, free_port, stop, wait_until_up
from reasoning import eye_engine

pytestmark = pytest.mark.e2e
sync_api = pytest.importorskip("playwright.sync_api", reason="Needs Playwright: pip install playwright")
expect = sync_api.expect

GRAPH = "https://example.org/graphs/waterinfo-sample"
OUTPUTS = "https://example.org/graphs/orchestration/"
MAPPING = (TEST_DATA / "rml.ttl.txt").read_text(encoding="utf-8").replace('"data.csv"', '"waterinfo-sample.csv"')
SHAPES = (TEST_DATA / "SHACL_in.ttl").read_text(encoding="utf-8")
TYPE_RULE = """@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix ex:   <https://example.org/rules#> .
ex:CheckRule a sh:NodeShape ; sh:targetClass sosa:Observation ;
    sh:rule [ a sh:TripleRule ; sh:subject sh:this ; sh:predicate rdf:type ; sh:object ex:CheckedObservation ] ."""

has_mapper = generic_pipeline.RML_MAPPER_JAR.is_file() and bool(shutil.which("java"))
needs_mapper = pytest.mark.skipif(not has_mapper, reason="Needs Java and pipeline/rmlmapper.jar.")
needs_eye = pytest.mark.skipif(eye_engine.find_engine() is None, reason="Needs EYE (native or bundled).")


@pytest.fixture(scope="module")
def app(fuseki, tmp_path_factory):
    """The dashboard and API, served by the app on a free port."""
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        pytest.skip("Build the frontend first: npm run build in frontend/ (or start python run.py once).")
    port = free_port()
    environment = {
        **os.environ,
        "FUSEKI_DATA_URL": f"{fuseki}/data",
        "PIPELINE_STORAGE_DIR": str(tmp_path_factory.mktemp("runs")),
    }
    environment.pop("FUSEKI_QUERY_URL", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "pipeline.playground_server:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        wait_until_up(f"{url}/api/health")
        yield url
    finally:
        stop(process)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(channel="chrome")
        except Exception:
            try:
                launched = playwright.chromium.launch()
            except Exception as error:
                pytest.skip(f"No browser for Playwright ({error}). Run: python -m playwright install chromium")
        yield launched
        launched.close()


class Session:
    """One browser page with a fresh storage, plus helpers to reach the visible workspace."""

    def __init__(self, browser, url):
        self.url = url
        self.context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        self.page = self.context.new_page()
        self.view = self.page.locator("main > div:not([hidden])")
        self.errors: list[str] = []
        self.dialogs: list[str] = []
        self.closed = False
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("console", lambda message: message.type == "error" and self.errors.append(message.text))
        self.page.on("dialog", lambda dialog: (self.dialogs.append(dialog.message), dialog.accept()))

    def open(self, view="overview"):
        self.page.goto(f"{self.url}/#/{view}")

    def go(self, view):
        self.page.evaluate(f"window.location.hash = '/{view}'")

    def close(self, expected_errors=0):
        unexpected = [error for error in self.errors if "status of 400" not in error]
        assert not unexpected, unexpected
        assert len(self.errors) == expected_errors, self.errors
        self.context.close()
        self.closed = True


@pytest.fixture
def session(app, browser, clean_fuseki):
    created = Session(browser, app)
    yield created
    if not created.closed:
        created.context.close()


def mapped_dataset(app_url: str, publish: bool = False) -> str:
    """Upload and map the sample through the API; optionally publish it as GRAPH."""
    with (TEST_DATA / "waterinfo-sample.csv").open("rb") as sample:
        run = requests.post(f"{app_url}/api/runs", files={"file": ("waterinfo-sample.csv", sample, "text/csv")}, timeout=60).json()
    mapped = requests.post(f"{app_url}/api/runs/{run['id']}/stages/rml", json={"mapping": MAPPING}, timeout=300).json()
    assert mapped["stages"]["rml"]["status"] == "success", mapped["stages"]["rml"]
    if publish:
        published = requests.post(f"{app_url}/api/runs/{run['id']}/stages/ingest", json={"graph_name": "waterinfo-sample"}, timeout=300).json()
        assert published["stages"]["ingest"]["status"] == "success"
    return run["id"]


def use_dataset(session: Session, run_id: str) -> None:
    session.page.add_init_script(f"localStorage.setItem('semantic-data-studio.dataset', '{run_id}')")


# --- Navigation and layout ---------------------------------------------------------------


def test_navigation_services_and_empty_states(session):
    session.open()
    page, view = session.page, session.view
    nav = page.locator(".nav-item")
    expect(nav).to_have_count(8)
    expect(page.locator(".service", has_text="Fuseki")).to_contain_text("Connected")
    expect(page.locator(".service", has_text="Java")).to_contain_text("Found" if shutil.which("java") else "Missing")
    expect(page.locator(".service", has_text="RMLMapper")).to_contain_text("Ready" if has_mapper else "Missing")
    expect(page.locator(".service", has_text="EYE reasoner")).to_contain_text("Ready" if eye_engine.find_engine() else "Missing")
    expect(view.get_by_role("heading", name="Turn spreadsheets into a trusted knowledge graph")).to_be_visible()

    for item, heading, empty in [
        ("data", "Bring your own data", "Supported formats"),
        ("mapping", "Map data to RDF", "Upload a dataset first"),
        ("quality", "Check and enrich your data", "Generate RDF first"),
        ("reasoning", "Infer new facts", "Generate RDF first"),
        ("graph", "Download and publish RDF", "Generate RDF first"),
        ("query", "Ask the knowledge graph", "No named graphs yet"),
        ("orchestration", "Chain SPARQL agents", "Create an agent environment"),
    ]:
        page.click(f".nav-item[href='#/{item}']")
        expect(view.get_by_role("heading", name=heading, exact=True)).to_be_visible()
        expect(view.get_by_text(empty).first).to_be_visible()
        expect(page.locator(f".nav-item[href='#/{item}']")).to_have_attribute("aria-current", "page")

    session.open("no-such-view")
    expect(view.get_by_role("heading", name="Turn spreadsheets into a trusted knowledge graph")).to_be_visible()
    session.close()


def test_every_view_fits_a_phone_and_dark_mode_applies(session):
    page = session.page
    page.set_viewport_size({"width": 390, "height": 844})
    for item in ("overview", "data", "mapping", "quality", "reasoning", "graph", "query", "orchestration"):
        session.open(item)
        page.wait_for_timeout(150)
        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 0, (item, overflow)
    light = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.emulate_media(color_scheme="dark")
    dark = page.evaluate("getComputedStyle(document.body).backgroundColor")
    assert light != dark, (light, dark)
    session.close()


# --- Data --------------------------------------------------------------------------------


def test_upload_checks_the_file_and_the_dataset_can_be_removed(session, app, tmp_path):
    session.open("data")
    view = session.view
    old_excel = tmp_path / "old.xls"
    old_excel.write_bytes(b"not really excel")
    view.locator(".dropzone input[type=file]").set_input_files(str(old_excel))
    expect(view.get_by_text(".xls files are not supported")).to_be_visible()
    expect(view.get_by_role("button", name="Upload and preview")).to_be_disabled()

    view.locator(".dropzone input[type=file]").set_input_files(str(TEST_DATA / "waterinfo-sample.csv"))
    expect(view.locator(".field-error")).to_have_count(0)
    view.get_by_role("button", name="Upload and preview").click()
    expect(view.get_by_role("heading", name="waterinfo-sample.csv")).to_be_visible(timeout=60000)
    expect(view.locator(".kpi", has_text="Rows")).to_contain_text("5,374")
    expect(view.locator(".kpi", has_text="Columns")).to_contain_text("30")
    expect(view.locator(".source-name")).to_contain_text("waterinfo-sample.csv")
    run_id = session.page.evaluate("localStorage.getItem('semantic-data-studio.dataset')")
    assert requests.get(f"{app}/api/runs/{run_id}", timeout=30).status_code == 200

    view.get_by_role("button", name="Remove dataset").first.click()
    view.locator(".notice").get_by_role("button", name="Remove dataset").click()
    expect(view.get_by_role("heading", name="Bring your own data")).to_be_visible()
    assert requests.get(f"{app}/api/runs/{run_id}", timeout=30).status_code == 404
    session.close()


# --- The pipeline ------------------------------------------------------------------------


@needs_mapper
@needs_eye
def test_pipeline_from_upload_to_query(session, app, clean_fuseki):
    page, view = session.page, session.view
    session.open("data")
    view.locator(".dropzone input[type=file]").set_input_files(str(TEST_DATA / "waterinfo-sample.csv"))
    view.get_by_role("button", name="Upload and preview").click()
    expect(view.get_by_role("heading", name="waterinfo-sample.csv")).to_be_visible(timeout=60000)

    session.go("mapping")
    view.locator("#rml-source").fill(MAPPING)
    view.get_by_role("button", name="Generate RDF").click()
    expect(view.get_by_text("RML mapping created 32,244 RDF triples.")).to_be_visible(timeout=120000)

    session.go("quality")
    view.locator("#shacl-source").fill(SHAPES)
    view.get_by_role("button", name="Validate data").click()
    expect(view.get_by_text("The mapped RDF conforms to the SHACL shapes.")).to_be_visible(timeout=180000)
    view.locator("#shacl-source").fill(TYPE_RULE)
    view.get_by_role("button", name="Apply rules").click()
    expect(view.get_by_text("SHACL rules inferred 5,374 new triples.")).to_be_visible(timeout=180000)

    session.go("reasoning")
    expect(view.locator(".fact-list").first).to_contain_text("Enriched RDF")
    view.locator(".example-item").filter(has_text="Classify readings").get_by_role("button").click()
    view.get_by_role("button", name="Run reasoner").click()
    expect(view.get_by_text("EYE inferred 5,386 new triples from the enriched RDF.")).to_be_visible(timeout=180000)

    session.go("quality")
    expect(view.locator(".fact-list").first).to_contain_text("Reasoned RDF")
    view.locator("#shacl-source").fill(SHAPES)
    view.get_by_role("button", name="Validate data").click()
    expect(view.get_by_text("The reasoned RDF conforms to the SHACL shapes.")).to_be_visible(timeout=180000)

    session.go("graph")
    expect(view.locator(".kpi", has_text="Current RDF")).to_contain_text("Reasoned")
    expect(view.locator(".kpi").filter(has=page.get_by_text("Triples", exact=True))).to_contain_text("43,004")
    for label, extension in [("Turtle", "ttl"), ("N-Triples", "nt"), ("JSON-LD", "jsonld"), ("RDF/XML", "rdf")]:
        view.locator(".segmented").first.get_by_role("radio", name=label).click()
        link = view.get_by_role("link", name=f"Download {label}")
        response = page.request.get(app + link.get_attribute("href"))
        assert response.ok, label
        assert f'filename="waterinfo-sample-reasoned.{extension}"' in response.headers["content-disposition"]
    browse = view.locator(".card", has_text="Browse RDF")
    expect(browse).to_contain_text("5,378 entities", timeout=60000)
    browse.get_by_role("button", name="Next").click()
    expect(browse).to_contain_text("Entities 11–20 of 5,378")
    view.locator("#graph-name").fill("waterinfo-sample")
    view.get_by_role("button", name="Publish").click()
    expect(view.get_by_text(f"Replaced {GRAPH} with the reasoned RDF.")).to_be_visible(timeout=120000)

    view.get_by_role("button", name="Query this graph").click()
    expect(view.get_by_role("heading", name="Ask the knowledge graph")).to_be_visible()
    expect(view.locator(".graph-item.active")).to_contain_text("waterinfo-sample")
    view.locator(".operation-item").filter(has=page.get_by_text("Entity types", exact=True)).click()
    view.get_by_role("button", name="Run operation").click()
    results = view.locator(".card").filter(has=page.get_by_role("heading", name="Entity types", exact=True))
    expect(results.locator("table")).to_contain_text("BrackishReading", timeout=60000)
    expect(results.locator("table")).to_contain_text("CheckedObservation")
    view.get_by_role("radio", name="SPARQL editor").click()
    view.get_by_role("button", name="Run query").click()
    sparql = view.locator(".card").filter(has=page.get_by_role("heading", name="SPARQL query", exact=True))
    expect(sparql).to_contain_text("100 rows", timeout=60000)
    with page.expect_download() as download:
        sparql.get_by_role("button", name="Export CSV").click()
    assert download.value.suggested_filename == "sparql-query.csv"

    session.go("overview")
    expect(view.locator(".kpi", has_text="RDF triples")).to_contain_text("incl. 10,760 inferred")
    expect(view.locator(".kpi", has_text="Published graph")).to_contain_text("waterinfo-sa")
    for activity in ("Dataset uploaded", "RDF generated", "SHACL rules applied", "Facts inferred with EYE", "Data validated", "Published to Fuseki"):
        expect(view.locator(".timeline")).to_contain_text(activity)
    session.close()


@needs_mapper
@needs_eye
def test_reasoning_examples_and_errors(session, app):
    use_dataset(session, mapped_dataset(app))
    session.open("reasoning")
    view = session.view
    examples = view.locator(".example-item")
    expect(examples).to_have_count(4)
    card = view.locator(".card").filter(has=session.page.get_by_role("heading", name="Inferences", exact=True))
    for title, message, extra in [
        ("Ontology reasoning", "EYE inferred 5,388 new triples from the mapped RDF.", "madeObservation"),
        ("Classify readings", "EYE inferred 5,386 new triples from the mapped RDF.", "BrackishReading"),
        ("Summarise each sensor", "EYE inferred 28 new triples from the mapped RDF.", "readingCount"),
        ("Detect sudden changes", "EYE inferred 122 new triples from the mapped RDF.", "Answers to the log:query"),
    ]:
        examples.filter(has_text=title).get_by_role("button").click()
        view.get_by_role("button", name="Run reasoner").click()
        expect(view.get_by_text(message)).to_be_visible(timeout=180000)
        expect(card).to_contain_text(extra)

    editor = view.locator("#n3-rules")
    editor.fill("@prefix ex: <https://example.org/> .\n{ ?x a ex:A  => { ?x a ex:B } .")
    view.get_by_role("button", name="Run reasoner").click()
    expect(view.get_by_text("EYE could not parse the N3 rules: there is a syntax error after line 1.")).to_be_visible(timeout=60000)
    session.go("graph")
    expect(view.locator(".kpi", has_text="Current RDF")).to_contain_text("Mapped")

    session.go("reasoning")
    examples.filter(has_text="Summarise each sensor").get_by_role("button").click()
    assert session.dialogs and session.dialogs[-1].startswith("Replace the rules in the editor")
    expect(editor).to_have_value(re.compile("wq:readingCount"))
    session.close()


# --- Agent orchestration -----------------------------------------------------------------


def output_graphs(app_url):
    graphs = requests.get(f"{app_url}/api/store/graphs", timeout=30).json()["graphs"]
    return {graph["uri"]: graph["triples"] for graph in graphs if graph["uri"].startswith(OUTPUTS)}


@needs_mapper
def test_agent_orchestration(session, app):
    mapped_dataset(app, publish=True)
    page, view = session.page, session.view
    session.open("orchestration")
    expect(view.get_by_role("button", name="Try an example")).to_be_enabled()
    view.get_by_role("button", name="New environment").first.click()
    name = view.get_by_label("Environment name")
    name.fill("Salinity study")
    name.press("Enter")
    expect(view.locator(".graph-item.active")).to_contain_text("Salinity study")

    cards = view.locator("section.agent-card")

    def add_agent(title, query):
        position = cards.count()
        view.get_by_role("button", name="Add agent").first.click()
        card = cards.nth(position)  # a fixed position: cards.last would follow later agents
        expect(card).to_be_visible()
        card.get_by_label("Agent name").fill(title)
        card.get_by_label("Agent name").press("Enter")
        card.get_by_label(re.compile("SPARQL query of")).fill(query)
        return card

    def run(card, status):
        card.get_by_role("button", name="Run", exact=True).click()
        expect(card.locator(".agent-head")).to_contain_text(status, timeout=120000)

    a1 = add_agent("High readings", "PREFIX sosa: <http://www.w3.org/ns/sosa/>\nPREFIX ex: <https://example.org/orchestration#>\n"
                   "CONSTRUCT { ?r a ex:HighReading ; ex:sensor ?s ; ex:value ?v ; ex:time ?t }\n"
                   "WHERE { ?r sosa:madeBySensor ?s ; sosa:hasSimpleResult ?v ; sosa:resultTime ?t . FILTER(?v >= 15000) }")
    expect(a1.get_by_role("checkbox", name=re.compile("waterinfo-sample"))).to_be_checked()
    run(a1, "10,532 triples saved")
    assert list(output_graphs(app).values()) == [10532]

    a1.get_by_role("button", name="New agent reading this output").click()
    a2 = cards.nth(1)
    expect(a2.get_by_role("checkbox", name=re.compile("Output of “High readings”"))).to_be_checked()
    a2.get_by_label("Agent name").fill("Per sensor")
    a2.get_by_label("Agent name").press("Enter")
    a2.get_by_label(re.compile("SPARQL query of")).fill(
        "PREFIX ex: <https://example.org/orchestration#>\n"
        "SELECT ?s (COUNT(?r) AS ?n) WHERE { ?r a ex:HighReading ; ex:sensor ?s } GROUP BY ?s")
    run(a2, "4 rows")

    a3 = add_agent("Below threshold", "PREFIX sosa: <http://www.w3.org/ns/sosa/>\nPREFIX ex: <https://example.org/orchestration#>\n"
                   "SELECT (COUNT(?r) AS ?below) WHERE {\n  GRAPH ")
    a3.get_by_role("checkbox", name=re.compile("Output of “High readings”")).uncheck()
    editor = a3.get_by_label(re.compile("SPARQL query of"))
    editor.press("Control+End")
    a3.get_by_label("Insert a graph reference").select_option(label="waterinfo-sample")
    editor.press("Control+End")
    editor.press_sequentially(" { ?r a sosa:Observation }\n  FILTER NOT EXISTS { GRAPH ")
    a3.get_by_label("Insert a graph reference").select_option(label="Output of “High readings”")
    editor.press("Control+End")
    editor.press_sequentially(" { ?r a ex:HighReading } }\n}")
    expect(editor).to_have_value(re.compile(r"GRAPH <agent:high-readings> \{ \?r a ex:HighReading \}"))
    run(a3, "1 row")
    expect(a3.locator("table tbody")).to_contain_text("2741")

    a1.get_by_role("button", name="Run", exact=True).click()
    expect(a2.locator(".agent-head")).to_contain_text("Stale", timeout=120000)
    expect(a3.locator(".agent-head")).to_contain_text("Stale")
    view.get_by_role("button", name="Run all").click()
    expect(view.get_by_text(re.compile(r"Running agent \d of 3"))).to_have_count(0, timeout=180000)
    expect(view.locator(".agent-head", has_text="Stale")).to_have_count(0)

    a1.get_by_label("Agent name").fill("Peak readings")
    a1.get_by_label("Agent name").press("Enter")
    expect(editor).to_have_value(re.compile(r"<agent:peak-readings>"))
    expect(a3.locator(".agent-head")).to_contain_text("1 row")

    page.reload()
    expect(cards).to_have_count(3)
    expect(cards.nth(0).locator(".agent-head")).to_contain_text("10,532 triples saved")

    a4 = add_agent("Broken", "SELECT * WHERE { ?s ?p }")
    run(a4, "Failed")
    expect(a4.locator(".notice-danger")).to_contain_text("Parse error")
    a4.get_by_label(re.compile("SPARQL query of")).fill("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 5")
    a4.get_by_role("checkbox", name=re.compile("Output of “Peak readings”")).check()
    run(a4, "5 triples saved")
    expect(cards.nth(0).get_by_role("checkbox", name=re.compile("Output of “Broken”"))).to_be_disabled()
    assert len(output_graphs(app)) == 2
    a4.get_by_role("button", name=re.compile("Delete the agent")).click()
    expect(cards).to_have_count(3)
    assert len(output_graphs(app)) == 1

    session.go("query")
    expect(view.get_by_text("Agent outputs (temporary)")).to_be_visible()

    session.go("orchestration")
    view.get_by_role("button", name="New environment").first.click()
    view.get_by_role("button", name="Load the example environment").click()
    expect(cards).to_have_count(3)
    view.get_by_role("button", name="Run all").click()
    expect(view.get_by_text(re.compile(r"Running agent \d of 3"))).to_have_count(0, timeout=180000)
    for index, status in enumerate(("10,532 triples saved", "4 rows", "1 row")):
        expect(cards.nth(index).locator(".agent-head")).to_contain_text(status)
    view.get_by_role("button", name="Delete", exact=True).click()
    expect(view.locator(".graph-item", has_text="High conductivity example")).to_have_count(0)
    assert len(output_graphs(app)) == 1  # only the Salinity study output remains
    session.close(expected_errors=1)  # the deliberate syntax error answers HTTP 400
