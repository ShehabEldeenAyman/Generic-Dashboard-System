---
type: "query"
date: "2026-08-06T08:32:49.463825+00:00"
question: "Add a SPARQL query form for the ingested Fuseki graph and always clear the named graph before ingestion"
contributor: "graphify"
outcome: "useful"
source_nodes: ["query_graph", "run_sparql_query", "ingest_graph", "SparqlWorkspace", "App"]
---

# Q: Add a SPARQL query form for the ingested Fuseki graph and always clear the named graph before ingestion

## Answer

Implemented a post-ingestion SPARQL workspace scoped to the run's named graph, added SELECT/ASK/graph result handling, and enforced DELETE-before-PUT ingestion with abort-on-clear-failure semantics.

## Outcome

- Signal: useful

## Source Nodes

- query_graph
- run_sparql_query
- ingest_graph
- SparqlWorkspace
- App