"""Apache Jena Fuseki graph-store client used by the pipeline."""

import os
from pathlib import Path

import requests


FUSEKI_DATA_URL = os.getenv("FUSEKI_DATA_URL", "http://localhost:3030/dataset/data")
MAX_QUERY_ROWS = max(1, int(os.getenv("SPARQL_RESULT_ROW_LIMIT", "1000")))
MAX_GRAPH_RESULT_CHARACTERS = max(
    1, int(os.getenv("SPARQL_GRAPH_RESULT_CHARACTER_LIMIT", "200000"))
)


class FusekiError(RuntimeError):
    """Raised when Fuseki cannot complete a graph or query operation.

    ``status_code`` is Fuseki's HTTP status when it answered, else ``None``.
    """

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def get_query_url():
    """Resolve Fuseki's read-only SPARQL query endpoint from the data endpoint."""
    configured = os.getenv("FUSEKI_QUERY_URL")
    if configured:
        return configured
    return FUSEKI_DATA_URL.rsplit("/data", 1)[0] + "/query"


def upload_graph(ttl_data_path, graph_uri, replace=True):
    """Load a Turtle file into a named graph through Graph Store Protocol.

    ``replace=True`` uses PUT (the graph's content is replaced); ``replace=False``
    uses POST (triples are added to whatever the graph already holds).
    """
    send = requests.put if replace else requests.post
    try:
        with open(ttl_data_path, "rb") as source:
            response = send(
                FUSEKI_DATA_URL,
                params={"graph": graph_uri},
                data=source,
                headers={"Content-Type": "text/turtle"},
                timeout=60,
            )
        if response.status_code in (200, 201, 204):
            print(f"Uploaded {ttl_data_path} to Fuseki graph {graph_uri}")
            return True
        print(f"Fuseki upload failed ({response.status_code}): {response.text}")
    except FileNotFoundError:
        print(f"Turtle file not found: {ttl_data_path}")
    except requests.RequestException as error:
        print(f"Fuseki upload request failed: {error}")
    return False


def delete_graph(graph_uri):
    """Remove a named graph from Fuseki's Graph Store Protocol endpoint."""
    try:
        response = requests.delete(FUSEKI_DATA_URL, params={"graph": graph_uri}, timeout=30)
        if response.status_code in (200, 204):
            print(f"Deleted Fuseki graph {graph_uri}")
            return True
        if response.status_code == 404:
            print(f"Fuseki graph {graph_uri} was already empty")
            return True
        print(f"Fuseki graph deletion failed ({response.status_code}): {response.text}")
    except requests.RequestException as error:
        print(f"Fuseki graph deletion request failed: {error}")
    return False


def _select_or_ask(response):
    """Parse a SPARQL JSON response into a SELECT table or an ASK answer."""
    try:
        payload = response.json()
    except ValueError as error:
        raise FusekiError("Fuseki returned invalid SPARQL JSON.") from error

    if "boolean" in payload:
        return {"type": "ask", "boolean": bool(payload["boolean"])}

    bindings = payload.get("results", {}).get("bindings")
    if not isinstance(bindings, list):
        raise FusekiError("Fuseki returned JSON without SPARQL result bindings.")
    variables = payload.get("head", {}).get("vars", [])
    rows = bindings[:MAX_QUERY_ROWS]
    return {
        "type": "select",
        "variables": variables,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(bindings) > len(rows),
    }


def _error_detail(response):
    return response.text.strip()[:2_000] or "Fuseki did not provide an error message."


def list_graph_names():
    """The IRIs of the named graphs that hold data."""
    result = query_graph("SELECT ?graph WHERE { GRAPH ?graph { } }")
    return [
        row["graph"]["value"]
        for row in result.get("rows", [])
        if row.get("graph", {}).get("type") == "uri"
    ]


def run_query(query, *, graph_destination, default_graphs=(), named_graphs=(), timeout=300):
    """Run a read-only query over the chosen graphs.

    ``default_graphs`` form the graph the query's patterns match (merged), and
    ``named_graphs`` the graphs its ``GRAPH`` blocks can reach. Without either,
    Fuseki's own dataset is used. SELECT and ASK results come back parsed. A
    CONSTRUCT or DESCRIBE result is written in full to ``graph_destination`` as
    N-Triples, and the result reports how many triples it holds.
    """
    data = [("query", query)]
    data += [("default-graph-uri", graph) for graph in default_graphs]
    data += [("named-graph-uri", graph) for graph in named_graphs]
    try:
        with requests.post(
            get_query_url(),
            data=data,
            headers={"Accept": "application/sparql-results+json, application/n-triples;q=0.9"},
            stream=True,
            timeout=timeout,
        ) as response:
            if not response.ok:
                raise FusekiError(
                    f"Fuseki query failed with HTTP {response.status_code}: {_error_detail(response)}",
                    response.status_code,
                )
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
            if content_type == "application/sparql-results+json":
                return _select_or_ask(response)
            if content_type not in {"application/n-triples", "text/plain"}:
                raise FusekiError(f"Fuseki answered with an unexpected content type: {content_type or 'none'}.")
            destination = Path(graph_destination)
            with destination.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    handle.write(chunk)
    except requests.RequestException as error:
        raise FusekiError(f"Fuseki query request failed: {error}") from error

    with destination.open("rb") as handle:
        triples = sum(1 for line in handle if line.strip() and not line.lstrip().startswith(b"#"))
    return {"type": "graph", "triples": triples}


def put_graph(path, graph_uri, content_type="application/n-triples"):
    """Replace a named graph's content with an RDF file. Raises ``FusekiError``."""
    try:
        with open(path, "rb") as source:
            response = requests.put(
                FUSEKI_DATA_URL,
                params={"graph": graph_uri},
                data=source,
                headers={"Content-Type": content_type},
                timeout=300,
            )
    except requests.RequestException as error:
        raise FusekiError(f"Fuseki upload request failed: {error}") from error
    if response.status_code not in (200, 201, 204):
        raise FusekiError(
            f"Fuseki could not store graph {graph_uri} (HTTP {response.status_code}): {_error_detail(response)}",
            response.status_code,
        )


def query_graph(query):
    """Run a read-only SPARQL query without overriding Fuseki's query dataset."""
    try:
        response = requests.post(
            get_query_url(),
            data={"query": query},
            headers={
                "Accept": (
                    "application/sparql-results+json, "
                    "text/turtle;q=0.9, application/ld+json;q=0.8"
                )
            },
            timeout=60,
        )
    except requests.RequestException as error:
        raise FusekiError(f"Fuseki query request failed: {error}") from error

    if not response.ok:
        detail = response.text.strip()[:2_000] or "Fuseki did not provide an error message."
        raise FusekiError(
            f"Fuseki query failed with HTTP {response.status_code}: {detail}", response.status_code
        )

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
    if content_type == "application/sparql-results+json":
        return _select_or_ask(response)

    text = response.text
    return {
        "type": "graph",
        "content_type": content_type or "text/plain",
        "text": text[:MAX_GRAPH_RESULT_CHARACTERS],
        "truncated": len(text) > MAX_GRAPH_RESULT_CHARACTERS,
    }
