---
type: "query"
date: "2026-08-06T08:48:54.459973+00:00"
question: "Remove the default graph constraint from SPARQL queries so users define target graphs in the query"
contributor: "graphify"
outcome: "useful"
source_nodes: ["query_graph", "run_sparql_query", "SparqlWorkspace"]
---

# Q: Remove the default graph constraint from SPARQL queries so users define target graphs in the query

## Answer

Expanded from graph vocabulary via [sparql, query, graph, fuseki, dataset, default, ingest, result]. Removed the Fuseki default-graph-uri parameter, kept the ingested graph URI only as a UI reference, and changed the editor template to require an explicit GRAPH IRI clause.

## Outcome

- Signal: useful

## Source Nodes

- query_graph
- run_sparql_query
- SparqlWorkspace