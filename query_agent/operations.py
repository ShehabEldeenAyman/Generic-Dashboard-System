"""Named, parameterised read-only operations over the Fuseki triple store.

Each operation turns validated parameters into a SPARQL query. The catalog is
served by the API (``GET /api/store/operations``) in a tool-like shape, so the
same operations can be run from the dashboard today and registered as tools for
an AI agent later without changing the query logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Callable

from triple_store_ingestion import ingest


class OperationError(ValueError):
    """Raised when an operation or its parameters are invalid."""


@dataclass(frozen=True)
class Parameter:
    name: str
    label: str
    kind: str  # "graph", "iri", "text", or "integer"
    description: str
    required: bool = True
    default: Any = None
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class Operation:
    id: str
    title: str
    description: str
    category: str
    parameters: tuple[Parameter, ...]
    build: Callable[[dict[str, Any]], str] = field(repr=False)

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "parameters": [
                {key: value for key, value in asdict(parameter).items() if value is not None}
                for parameter in self.parameters
            ],
        }


_IRI_FORBIDDEN = re.compile(r'[\s<>"{}|^`\\]')


def sparql_iri(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", text) or _IRI_FORBIDDEN.search(text):
        raise OperationError(f"{label} must be a complete IRI, such as https://example.org/graphs/data.")
    return f"<{text}>"


def sparql_string(value: Any) -> str:
    text = str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


GRAPH = Parameter("graph", "Named graph", "graph", "The named graph to inspect.")
LIMIT = Parameter(
    "limit", "Maximum rows", "integer", "Upper bound on returned rows.",
    required=False, default=50, minimum=1, maximum=1000,
)

RDFS_PREFIX = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"


def _graph_overview(p: dict[str, Any]) -> str:
    graph = p["graph"]
    return f"""SELECT ?triples ?entities ?properties ?types
WHERE {{
  {{ SELECT (COUNT(*) AS ?triples) (COUNT(DISTINCT ?s) AS ?entities) (COUNT(DISTINCT ?p) AS ?properties)
    WHERE {{ GRAPH {graph} {{ ?s ?p ?o }} }} }}
  {{ SELECT (COUNT(DISTINCT ?type) AS ?types)
    WHERE {{ GRAPH {graph} {{ ?entity a ?type }} }} }}
}}"""


def _entity_types(p: dict[str, Any]) -> str:
    return f"""SELECT ?type (COUNT(DISTINCT ?entity) AS ?entities)
WHERE {{ GRAPH {p["graph"]} {{ ?entity a ?type }} }}
GROUP BY ?type
ORDER BY DESC(?entities)
LIMIT {p["limit"]}"""


def _property_usage(p: dict[str, Any]) -> str:
    return f"""SELECT ?property (COUNT(*) AS ?uses) (COUNT(DISTINCT ?subject) AS ?entities)
WHERE {{ GRAPH {p["graph"]} {{ ?subject ?property ?value }} }}
GROUP BY ?property
ORDER BY DESC(?uses)
LIMIT {p["limit"]}"""


def _find_entities(p: dict[str, Any]) -> str:
    return f"""{RDFS_PREFIX}SELECT ?entity ?label
WHERE {{
  GRAPH {p["graph"]} {{
    ?entity a {p["type"]} .
    OPTIONAL {{ ?entity rdfs:label ?label }}
  }}
}}
ORDER BY ?entity
LIMIT {p["limit"]}"""


def _describe_entity(p: dict[str, Any]) -> str:
    return f"""SELECT ?property ?value
WHERE {{ GRAPH {p["graph"]} {{ {p["entity"]} ?property ?value }} }}
ORDER BY ?property ?value
LIMIT {p["limit"]}"""


def _search_text(p: dict[str, Any]) -> str:
    return f"""SELECT ?entity ?property ?value
WHERE {{
  GRAPH {p["graph"]} {{
    ?entity ?property ?value .
    FILTER(isLiteral(?value) && CONTAINS(LCASE(STR(?value)), LCASE({p["text"]})))
  }}
}}
LIMIT {p["limit"]}"""


def _sample_triples(p: dict[str, Any]) -> str:
    return f"""SELECT ?subject ?predicate ?object
WHERE {{ GRAPH {p["graph"]} {{ ?subject ?predicate ?object }} }}
LIMIT {p["limit"]}"""


OPERATIONS: dict[str, Operation] = {
    operation.id: operation
    for operation in (
        Operation(
            "graph_overview", "Graph overview",
            "Count triples, entities, properties, and entity types in a graph.",
            "Explore", (GRAPH,), _graph_overview,
        ),
        Operation(
            "entity_types", "Entity types",
            "List the types (classes) in a graph with how many entities each has.",
            "Explore", (GRAPH, LIMIT), _entity_types,
        ),
        Operation(
            "property_usage", "Property usage",
            "Show which properties are used most and on how many entities.",
            "Explore", (GRAPH, LIMIT), _property_usage,
        ),
        Operation(
            "find_entities", "Find entities by type",
            "List entities of one type, with their labels when available.",
            "Lookup",
            (GRAPH, Parameter("type", "Entity type IRI", "iri", "The rdf:type to match."), LIMIT),
            _find_entities,
        ),
        Operation(
            "describe_entity", "Describe an entity",
            "Show every property and value recorded for one entity.",
            "Lookup",
            (GRAPH, Parameter("entity", "Entity IRI", "iri", "The entity to describe."), LIMIT),
            _describe_entity,
        ),
        Operation(
            "search_text", "Search text values",
            "Find entities whose text values contain a word or phrase (case-insensitive).",
            "Lookup",
            (GRAPH, Parameter("text", "Search text", "text", "The word or phrase to look for."), LIMIT),
            _search_text,
        ),
        Operation(
            "sample_triples", "Sample records",
            "Return a sample of raw subject–predicate–object statements.",
            "Explore", (GRAPH, LIMIT), _sample_triples,
        ),
    )
}


def catalog() -> list[dict[str, Any]]:
    return [operation.describe() for operation in OPERATIONS.values()]


def _validated_parameters(operation: Operation, raw: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for parameter in operation.parameters:
        value = raw.get(parameter.name)
        if value is None or (isinstance(value, str) and not value.strip()):
            if parameter.required:
                raise OperationError(f"{parameter.label} is required.")
            value = parameter.default
        if parameter.kind in {"graph", "iri"}:
            values[parameter.name] = sparql_iri(value, parameter.label)
        elif parameter.kind == "integer":
            try:
                number = int(value)
            except (TypeError, ValueError) as error:
                raise OperationError(f"{parameter.label} must be a whole number.") from error
            if parameter.minimum is not None and number < parameter.minimum:
                raise OperationError(f"{parameter.label} must be at least {parameter.minimum}.")
            if parameter.maximum is not None and number > parameter.maximum:
                raise OperationError(f"{parameter.label} must be at most {parameter.maximum}.")
            values[parameter.name] = number
        else:
            text = str(value).strip()
            if len(text) > 500:
                raise OperationError(f"{parameter.label} must be at most 500 characters.")
            values[parameter.name] = sparql_string(text)
    return values


def build_query(operation_id: str, raw_parameters: dict[str, Any]) -> str:
    operation = OPERATIONS.get(operation_id)
    if operation is None:
        raise OperationError(f"Unknown operation: {operation_id}")
    return operation.build(_validated_parameters(operation, raw_parameters or {}))


def run_operation(operation_id: str, raw_parameters: dict[str, Any]) -> dict[str, Any]:
    query = build_query(operation_id, raw_parameters)
    return {"operation": operation_id, "query": query, "result": ingest.query_graph(query)}


def list_graphs() -> dict[str, Any]:
    """Return every named graph with its triple count, plus the default graph size."""
    named = ingest.query_graph(
        "SELECT ?graph (COUNT(*) AS ?triples) WHERE { GRAPH ?graph { ?s ?p ?o } } "
        "GROUP BY ?graph ORDER BY ?graph"
    )
    default = ingest.query_graph("SELECT (COUNT(*) AS ?triples) WHERE { ?s ?p ?o }")

    def count(binding: dict[str, Any]) -> int:
        try:
            return int(binding.get("triples", {}).get("value", 0))
        except (TypeError, ValueError):
            return 0

    graphs = [
        {"uri": row["graph"]["value"], "triples": count(row)}
        for row in named.get("rows", [])
        if row.get("graph", {}).get("value")
    ]
    default_rows = default.get("rows", [])
    return {
        "graphs": graphs,
        "default_graph_triples": count(default_rows[0]) if default_rows else 0,
    }
