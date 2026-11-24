"""Run N3 rules over RDF with the EYE reasoner and collect what they derive.

EYE (https://eyereasoner.github.io/eye/) runs as a separate process. A native
installation is used when one is available: the ``EYE_COMMAND`` environment
variable, or ``eye`` on ``PATH``. Otherwise the WebAssembly build of EYE that is
published on npm as ``eyereasoner`` runs on Node.js; ``python run.py`` installs
it into ``reasoning/node_modules``. Both builds take the same arguments.

The input RDF is handed to EYE as N-Triples files of at most ``CHUNK_TRIPLES``
triples each, read with EYE's ``--turtle`` parser (about ten times faster than
its N3 parser). Splitting keeps every document small; EYE's N3 parser ran out of
stack on a single 838,000-triple document. Blank nodes are replaced by IRIs
first, because a blank node label only identifies the same node within one
document.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import heapq
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, BinaryIO

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF
from rdflib.term import Node

REASONING_DIR = Path(__file__).resolve().parent
EXAMPLES_DIR = REASONING_DIR / "examples"
BUNDLED_CLI = REASONING_DIR / "node_modules" / "eyereasoner" / "dist" / "bin" / "index.js"
CHUNK_TRIPLES = 100_000
INPUT_PREFIX = "reasoning_input"
SKOLEM_PREFIX = "urn:x-semantic-data-studio:bnode:"
LOG_LIMIT = 20_000

INSTALL_HINT = (
    "EYE is not available. Start the app with 'python run.py' to install the bundled "
    "reasoner (requires Node.js), or install EYE and put 'eye' on PATH or set EYE_COMMAND."
)

EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "id": "ontology-reasoning",
        "title": "Ontology reasoning",
        "summary": "RDFS and OWL rules (class hierarchies, domains and ranges, inverse "
        "properties, property chains) with axioms from the SOSA/SSN ontology.",
        "adds": "Sensor types, each sensor's observations, and what each sensor observes.",
        "features": ["rdfs:subClassOf", "owl:inverseOf", "owl:propertyChainAxiom"],
    },
    {
        "id": "salinity-classes",
        "title": "Classify readings",
        "summary": "Sorts readings into fresh, brackish, and saline with thresholds stored "
        "as facts, and flags values a sensor cannot produce.",
        "adds": "A class for every reading and a status for every sensor.",
        "features": ["math:lessThan", "log:notIncludes"],
    },
    {
        "id": "sensor-summary",
        "title": "Summarise each sensor",
        "summary": "Counts each sensor's readings and works out the lowest, highest, and "
        "mean value, and the first and last reading time.",
        "adds": "Seven summary facts per sensor.",
        "features": ["log:collectAllIn", "math:sum", "list:sort"],
    },
    {
        "id": "sudden-changes",
        "title": "Detect sudden changes",
        "summary": "Compares each reading with the same sensor's reading 15 minutes "
        "earlier and flags jumps larger than a threshold.",
        "adds": "Only the flagged readings and the size of each change.",
        "features": ["math:difference", "date-time arithmetic", "log:query"],
    },
)


class EyeError(RuntimeError):
    """EYE could not run, or it reported an error. ``log`` holds its diagnostics."""

    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


# --- Finding EYE ----------------------------------------------------------------------


@dataclass(frozen=True)
class Engine:
    """How to start EYE. ``kind`` is ``"native"`` or ``"bundled"``."""

    kind: str
    command: tuple[str, ...]

    @property
    def label(self) -> str:
        return "Native EYE" if self.kind == "native" else "Bundled EYE (WebAssembly)"


def _native(executable: str) -> Engine:
    command: tuple[str, ...] = (executable,)
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat"}:
        command = (os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", executable)
    return Engine("native", command)


def find_engine() -> Engine | None:
    """Native EYE when configured or on PATH, otherwise the bundled build, else None."""
    configured = os.getenv("EYE_COMMAND", "").strip()
    if configured:
        return _native(configured)
    native = shutil.which("eye")
    if native:
        return _native(native)
    node = shutil.which("node")
    if node and BUNDLED_CLI.is_file():
        return Engine("bundled", (node, str(BUNDLED_CLI)))
    return None


_VERSIONS: dict[tuple[str, ...], str] = {}
VERSION_PATTERN = re.compile(r"EYE v[\w.\-]+(?: \([^)]*\))?")


def engine_version(engine: Engine) -> str:
    """EYE's version banner, such as ``EYE v11.24.8 (2026-09-07)``."""
    cached = _VERSIONS.get(engine.command)
    if cached:
        return cached
    try:
        completed = subprocess.run(
            [*engine.command, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EyeError(f"EYE could not start: {error}") from error
    output = f"{completed.stdout}\n{completed.stderr}"
    match = VERSION_PATTERN.search(output)
    if not match:
        raise EyeError("EYE started but did not report its version.", output.strip()[:LOG_LIMIT])
    _VERSIONS[engine.command] = match.group(0)
    return match.group(0)


def status() -> dict[str, Any]:
    """Whether EYE can run, which build is used, and its version."""
    engine = find_engine()
    if engine is None:
        return {"ready": False, "engine": None, "label": None, "version": None, "detail": INSTALL_HINT}
    try:
        version = engine_version(engine)
    except EyeError as error:
        return {
            "ready": False,
            "engine": engine.kind,
            "label": engine.label,
            "version": None,
            "detail": str(error),
        }
    return {"ready": True, "engine": engine.kind, "label": engine.label, "version": version, "detail": ""}


# --- Reading N3 rules -----------------------------------------------------------------


def _string_end(text: str, start: int, quote: str) -> int:
    index = start
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text.startswith(quote, index):
            return index + len(quote)
        if len(quote) == 1 and text[index] == "\n":
            return index
        index += 1
    return len(text)


def strip_comments(text: str, *, keep_strings: bool = True) -> str:
    """Remove ``#`` comments, keeping IRIs (which may contain ``#``) intact.

    With ``keep_strings=False`` string literals are emptied as well, so that text
    inside them cannot be mistaken for syntax.
    """
    parts: list[str] = []
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        if char == "#":
            newline = text.find("\n", index)
            index = length if newline == -1 else newline
            continue
        end = index + 1
        if char == "<":
            close = text.find(">", index + 1)
            if close != -1 and not any(c.isspace() for c in text[index + 1 : close]):
                end = close + 1
        elif char in "\"'":
            quote = char * 3 if text.startswith(char * 3, index) else char
            end = _string_end(text, index + len(quote), quote)
            if not keep_strings:
                parts.append(quote * 2)
                index = end
                continue
        parts.append(text[index:end])
        index = end
    return "".join(parts)


RULE_PATTERN = re.compile(r"=>|<=|\blog:implies\b|log#implies>")
QUERY_PATTERN = re.compile(
    r"\}\s*(?:log:query|<http://www\.w3\.org/2000/10/swap/log#query>|=\^)\s*\{"
)
PREFIX_PATTERN = re.compile(r"(?im)^\s*(?:@prefix|prefix)\s+([A-Za-z][\w.\-]*):\s*<([^>\s]*)>")


def uses_query(rules_text: str) -> bool:
    """True when the document has a log:query, so EYE outputs only its answers."""
    return bool(QUERY_PATTERN.search(strip_comments(rules_text, keep_strings=False)))


def contains_rules(rules_text: str) -> bool:
    """True when the document has at least one rule or log:query."""
    plain = strip_comments(rules_text, keep_strings=False)
    return bool(RULE_PATTERN.search(plain) or QUERY_PATTERN.search(plain))


def declared_prefixes(rules_text: str) -> list[tuple[str, URIRef]]:
    """Prefixes declared in N3 text, used to keep the output readable."""
    return [
        (prefix, URIRef(namespace))
        for prefix, namespace in PREFIX_PATTERN.findall(strip_comments(rules_text))
        if namespace
    ]


# --- Input and output -----------------------------------------------------------------


class _ChunkWriter:
    """A binary stream that spreads N-Triples lines over numbered files."""

    def __init__(self, directory: Path, prefix: str, lines_per_file: int):
        self.directory = directory
        self.prefix = prefix
        self.lines_per_file = max(1, lines_per_file)
        self.names: list[str] = []
        self._handle: BinaryIO | None = None
        self._lines = 0

    def write(self, data: bytes) -> int:
        start = 0
        while start < len(data):
            if self._handle is None or self._lines >= self.lines_per_file:
                self._next_file()
            assert self._handle is not None
            newline = data.find(b"\n", start)
            end = len(data) if newline == -1 else newline + 1
            self._handle.write(data[start:end])
            if newline != -1:
                self._lines += 1
            start = end
        return len(data)

    def _next_file(self) -> None:
        self.close()
        name = f"{self.prefix}_{len(self.names):03d}.nt"
        self._handle = (self.directory / name).open("wb")
        self.names.append(name)
        self._lines = 0

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def _skolem(term: Node) -> Node:
    return URIRef(f"{SKOLEM_PREFIX}{term}") if isinstance(term, BNode) else term


def _unskolem(term: Node) -> Node:
    if isinstance(term, URIRef) and term.startswith(SKOLEM_PREFIX):
        return BNode(term[len(SKOLEM_PREFIX) :])
    return term


def write_input(data: Graph, directory: Path, *, chunk_triples: int = CHUNK_TRIPLES) -> list[str]:
    """Write ``data`` as N-Triples files in ``directory`` and return their names."""
    source = data
    if any(isinstance(term, BNode) for s, _p, o in data for term in (s, o)):
        source = Graph()
        for s, p, o in data:
            source.add((_skolem(s), p, _skolem(o)))
    writer = _ChunkWriter(directory, INPUT_PREFIX, chunk_triples)
    try:
        source.serialize(destination=writer, format="nt", encoding="utf-8")
    finally:
        writer.close()
    return writer.names


def is_rdf_triple(triple: tuple[Node, Node, Node]) -> bool:
    """N3 also allows formulas, variables, and literal subjects, which RDF does not."""
    subject, predicate, obj = triple
    return (
        isinstance(subject, (URIRef, BNode))
        and isinstance(predicate, URIRef)
        and isinstance(obj, (URIRef, BNode, Literal))
    )


def parse_output(text: str) -> tuple[Graph, int]:
    """Parse EYE's N3 output into RDF; also return how many N3-only statements were left out."""
    parsed = Graph()
    if text.strip():
        try:
            parsed.parse(data=text, format="n3")
        except Exception as error:
            raise EyeError(f"EYE's output could not be read as RDF: {error}", text[:LOG_LIMIT]) from error
    graph = Graph()
    skipped = 0
    for s, p, o in parsed:
        triple = (_unskolem(s), p, _unskolem(o))
        if is_rdf_triple(triple):
            graph.add(triple)
        else:
            skipped += 1
    return graph, skipped


ERROR_PATTERN = re.compile(r"\*\* ERROR \*\* (\S+) \*\* (.*)")
WARNING_PATTERN = re.compile(r"\*\* WARNING \*\*.*")
STATS_PATTERN = re.compile(
    r"in=(\d+) out=(\d+) ent=(\d+) step=(\d+) brake=(\d+) inf=(\d+) sec=([\d.]+)"
)


def parse_stats(text: str) -> dict[str, float]:
    """EYE's closing statistics line: triples in and out, rule firings, inferences, time."""
    match = STATS_PATTERN.search(text)
    if not match:
        return {}
    keys = ("input_triples", "output_triples", "entailments", "steps", "brakes", "inferences")
    stats: dict[str, float] = {key: int(value) for key, value in zip(keys, match.groups())}
    stats["seconds"] = float(match.group(7))
    return stats


def _source(where: str, rules_name: str) -> str:
    if where == rules_name or where.endswith("/" + rules_name):
        return "the N3 rules"
    if INPUT_PREFIX in where:
        return "the input RDF"
    return "its input"


def describe_problem(stdout: str, stderr: str, returncode: int, rules_name: str, engine: Engine) -> str | None:
    """A readable explanation when EYE failed, otherwise None.

    The bundled build always exits with code 0, so errors are read from the log.
    """
    if "inference_fuse" in stderr or "# inference fuse" in stdout:
        return (
            "An inference fuse fired: a rule concluded false, which means the data "
            "contradicts the rules. The technical log shows the rule and the facts involved."
        )
    for line in stderr.splitlines():
        match = ERROR_PATTERN.search(line)
        if not match:
            continue
        where, detail = match.groups()
        source = _source(where, rules_name)
        if "invalid_document" in detail:
            line_number = re.search(r"after_line\((\d+)\)", detail)
            position = f" after line {line_number.group(1)}" if line_number else ""
            return f"EYE could not parse {source}: there is a syntax error{position}."
        if "resource_error" in detail or "stack_overflow" in detail:
            advice = " Install native EYE for large datasets." if engine.kind == "bundled" else ""
            return f"EYE ran out of memory while processing {source}.{advice}"
        if "existence_error" in detail:
            return f"EYE could not read {source}."
        return f"EYE reported an error: {detail.strip()[:300]}"
    if returncode != 0:
        if "memory" in f"{stdout}\n{stderr}".lower():
            return "EYE ran out of memory. Install native EYE for large datasets."
        return f"EYE stopped with exit code {returncode}."
    return None


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


@dataclass
class Outcome:
    graph: Graph
    query_mode: bool
    skipped_statements: int
    engine: Engine
    version: str | None
    log: str
    warnings: list[str]
    stats: dict[str, float]
    seconds: float


def reason(
    directory: Path,
    data: Graph,
    rules_name: str,
    *,
    timeout: int,
    chunk_triples: int = CHUNK_TRIPLES,
) -> Outcome:
    """Run the rules in ``directory / rules_name`` over ``data``.

    The result holds the RDF triples EYE derived: every new triple, or only the
    answers when the rules contain a log:query.
    """
    engine = find_engine()
    if engine is None:
        raise EyeError(INSTALL_HINT)
    try:
        version: str | None = engine_version(engine)
    except EyeError:
        version = None  # the run below reports the actual problem
    rules_text = (directory / rules_name).read_text(encoding="utf-8")
    query_mode = uses_query(rules_text)
    names = write_input(data, directory, chunk_triples=chunk_triples)
    arguments = ["--nope", *(part for name in names for part in ("--turtle", name)), rules_name]
    if not query_mode:
        arguments.append("--pass-only-new")

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [*engine.command, *arguments],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except OSError as error:
        raise EyeError(f"EYE could not start: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise EyeError(
            f"EYE did not finish within {timeout} seconds. Rules that keep creating new "
            "facts (for example a new blank node each time they fire) never finish. "
            "For large data, raise PIPELINE_COMMAND_TIMEOUT or install native EYE.",
            _text(error.stderr)[-LOG_LIMIT:],
        ) from error
    finally:
        for name in names:
            (directory / name).unlink(missing_ok=True)
    seconds = round(time.perf_counter() - started, 2)

    log = completed.stderr.strip()
    problem = describe_problem(completed.stdout, completed.stderr, completed.returncode, rules_name, engine)
    if problem:
        details = log
        if completed.stdout.strip():
            details = f"{details}\n\n{completed.stdout.strip()}"
        raise EyeError(problem, details[:LOG_LIMIT])

    graph, skipped = parse_output(completed.stdout)
    return Outcome(
        graph=graph,
        query_mode=query_mode,
        skipped_statements=skipped,
        engine=engine,
        version=version,
        log=log[:LOG_LIMIT],
        warnings=[match.group(0) for match in WARNING_PATTERN.finditer(completed.stderr)][:10],
        stats=parse_stats(completed.stderr) or parse_stats(completed.stdout),
        seconds=seconds,
    )


# --- Describing results ---------------------------------------------------------------


def _term(term: Node) -> dict[str, Any]:
    if isinstance(term, Literal):
        return {
            "type": "literal",
            "value": str(term),
            "datatype": str(term.datatype) if term.datatype else None,
            "language": term.language,
        }
    if isinstance(term, BNode):
        return {"type": "blank", "value": f"_:{term}"}
    return {"type": "iri", "value": str(term)}


def summarise(graph: Graph, *, top: int = 12, sample_size: int = 40) -> dict[str, Any]:
    """What the derived triples say: classes assigned, properties added, and a sample.

    The sample takes a few triples from every class and property, so one large
    group (such as an inverse property on every observation) cannot crowd out
    the rest.
    """
    classes: Counter[str] = Counter()
    properties: Counter[str] = Counter()
    groups: dict[tuple[int, str], list[tuple[Node, Node, Node]]] = defaultdict(list)
    for triple in graph:
        _subject, predicate, obj = triple
        if predicate == RDF.type:
            classes[str(obj)] += 1
            groups[(0, str(obj))].append(triple)
        else:
            properties[str(predicate)] += 1
            groups[(1, str(predicate))].append(triple)

    ordered = sorted(groups.items(), key=lambda item: (item[0][0], -len(item[1]), item[0][1]))
    per_group = max(1, sample_size // len(ordered)) if ordered else 0
    sample: list[dict[str, Any]] = []
    for _key, triples in ordered:
        for subject, predicate, obj in heapq.nsmallest(
            per_group, triples, key=lambda triple: (triple[0].n3(), triple[2].n3())
        ):
            sample.append({"subject": _term(subject), "predicate": str(predicate), "object": _term(obj)})
    return {
        "classes": [{"iri": iri, "count": count} for iri, count in classes.most_common(top)],
        "class_count": len(classes),
        "properties": [{"iri": iri, "count": count} for iri, count in properties.most_common(top)],
        "property_count": len(properties),
        "sample": sample[:sample_size],
    }


# --- Examples -------------------------------------------------------------------------


def list_examples() -> list[dict[str, Any]]:
    """The example rule sets in ``reasoning/examples``, with their N3 text."""
    return [
        {
            **example,
            "file_name": f"{example['id']}.n3",
            "rules": (EXAMPLES_DIR / f"{example['id']}.n3").read_text(encoding="utf-8"),
        }
        for example in EXAMPLES
    ]


def find_example(example_id: str | None) -> dict[str, Any] | None:
    return next((item for item in list_examples() if item["id"] == example_id), None)
