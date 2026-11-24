"""Agent orchestration: SPARQL agents that build on each other's results.

An *environment* groups *agents*; an agent is a SPARQL query plus the graphs it
reads from. The dashboard keeps environments and agents (in the browser); this
module runs one agent at a time:

- The chosen source graphs are passed to Fuseki as the query's default graph,
  merged, so a query needs no ``FROM`` or ``GRAPH`` to read them. Every graph in
  the store is passed as a named graph as well, so ``GRAPH <...>`` blocks keep
  working alongside the chosen sources.
- A CONSTRUCT or DESCRIBE result is stored in the agent's own *output graph*,
  ``<base>/orchestration/<environment>/<agent>``, replacing what was there.
  Other agents can then read it. The app never writes anywhere else, and agent
  queries go to Fuseki's read-only query endpoint.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any

from rdflib import BNode, Graph, Literal

from query_agent.operations import OperationError, sparql_iri
from triple_store_ingestion import ingest

GRAPH_BASE = os.getenv("FUSEKI_GRAPH_BASE", "https://example.org/graphs/")
OUTPUT_BASE = f"{GRAPH_BASE.rstrip('/')}/orchestration/"
ID_PATTERN = re.compile(r"^[a-z0-9]{6,32}$")
MAX_SOURCES = 50
PREVIEW_TRIPLES = 20
QUERY_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_COMMAND_TIMEOUT", "300"))


class OrchestrationError(OperationError):
    """An agent request that cannot run as given."""


def _checked_id(value: str, label: str) -> str:
    if not ID_PATTERN.match(value or ""):
        raise OrchestrationError(f"The {label} id must be 6 to 32 lowercase letters or digits.")
    return value


def environment_prefix(environment_id: str) -> str:
    return f"{OUTPUT_BASE}{_checked_id(environment_id, 'environment')}/"


def output_graph(environment_id: str, agent_id: str) -> str:
    """The graph that holds an agent's CONSTRUCT or DESCRIBE output."""
    return f"{environment_prefix(environment_id)}{_checked_id(agent_id, 'agent')}"


def checked_sources(sources: list[str]) -> list[str]:
    if len(sources) > MAX_SOURCES:
        raise OrchestrationError(f"An agent can read from at most {MAX_SOURCES} graphs.")
    unique: list[str] = []
    for source in sources:
        iri = sparql_iri(source, "Every source graph")[1:-1]
        if iri not in unique:
            unique.append(iri)
    return unique


def _term(term: Any) -> dict[str, Any]:
    """A term in the shape of SPARQL JSON results, so the dashboard renders it like query rows."""
    if isinstance(term, Literal):
        value: dict[str, Any] = {"type": "literal", "value": str(term)}
        if term.language:
            value["xml:lang"] = term.language
        elif term.datatype:
            value["datatype"] = str(term.datatype)
        return value
    if isinstance(term, BNode):
        return {"type": "bnode", "value": str(term)}
    return {"type": "uri", "value": str(term)}


def preview(path: Path, limit: int = PREVIEW_TRIPLES) -> dict[str, Any]:
    """The first triples of an N-Triples file, as a three-column result table."""
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip() and not line.lstrip().startswith("#"):
                lines.append(line)
                if len(lines) >= limit:
                    break
    graph = Graph()
    if lines:
        graph.parse(data="".join(lines), format="nt")
    triples = sorted(graph, key=lambda triple: tuple(term.n3() for term in triple))
    return {
        "variables": ["subject", "predicate", "object"],
        "rows": [
            {"subject": _term(s), "predicate": _term(p), "object": _term(o)}
            for s, p, o in triples
        ],
    }


def run_agent(query: str, sources: list[str], environment_id: str, agent_id: str) -> dict[str, Any]:
    """Run one agent. A CONSTRUCT or DESCRIBE result replaces the agent's output graph."""
    graph_uri = output_graph(environment_id, agent_id)
    sources = checked_sources(sources)
    if not query.strip():
        raise OrchestrationError("Write a SPARQL query before running the agent.")
    if graph_uri in sources:
        raise OrchestrationError("An agent cannot read its own output.")

    started = time.perf_counter()
    named_graphs = ingest.list_graph_names() if sources else []
    with tempfile.TemporaryDirectory(prefix="agent-") as directory:
        path = Path(directory) / "output.nt"
        result = ingest.run_query(
            query,
            graph_destination=path,
            default_graphs=sources,
            named_graphs=named_graphs,
            timeout=QUERY_TIMEOUT_SECONDS,
        )
        if result["type"] == "graph":
            ingest.put_graph(path, graph_uri)
            result["output_graph"] = graph_uri
            result["preview"] = preview(path)
    result["sources"] = sources
    result["duration_seconds"] = round(time.perf_counter() - started, 2)
    return result


def drop_outputs(environment_id: str, agent_id: str | None = None) -> dict[str, Any]:
    """Delete the output graph of one agent, or of every agent in an environment."""
    if agent_id:
        targets = [output_graph(environment_id, agent_id)]
    else:
        prefix = environment_prefix(environment_id)
        targets = [graph for graph in ingest.list_graph_names() if graph.startswith(prefix)]
    return {"dropped": [graph for graph in targets if ingest.delete_graph(graph)]}
