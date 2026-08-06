"""Apache Jena Fuseki graph-store client used by the pipeline."""

import os

import requests


FUSEKI_DATA_URL = os.getenv("FUSEKI_DATA_URL", "http://localhost:3030/dataset/data")
MAX_QUERY_ROWS = max(1, int(os.getenv("SPARQL_RESULT_ROW_LIMIT", "1000")))
MAX_GRAPH_RESULT_CHARACTERS = max(
    1, int(os.getenv("SPARQL_GRAPH_RESULT_CHARACTER_LIMIT", "200000"))
)


class FusekiError(RuntimeError):
    """Raised when Fuseki cannot complete a graph or query operation."""


def get_query_url():
    """Resolve Fuseki's read-only SPARQL query endpoint from the data endpoint."""
    configured = os.getenv("FUSEKI_QUERY_URL")
    if configured:
        return configured
    return FUSEKI_DATA_URL.rsplit("/data", 1)[0] + "/query"


def upload_graph(ttl_data_path, graph_uri):
    """Replace a named graph with a Turtle file through Graph Store Protocol."""
    try:
        with open(ttl_data_path, "rb") as source:
            response = requests.put(
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
        raise FusekiError(f"Fuseki query failed with HTTP {response.status_code}: {detail}")

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip()
    if content_type == "application/sparql-results+json":
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

    text = response.text
    return {
        "type": "graph",
        "content_type": content_type or "text/plain",
        "text": text[:MAX_GRAPH_RESULT_CHARACTERS],
        "truncated": len(text) > MAX_GRAPH_RESULT_CHARACTERS,
    }
