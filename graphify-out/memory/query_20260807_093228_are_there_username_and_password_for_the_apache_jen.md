---
type: "query"
date: "2026-08-07T09:32:28.990464+00:00"
question: "are there username and password for the apache jenna fuseki connection?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ingest.py", "upload_graph()", "delete_graph()", "query_graph()"]
---

# Q: are there username and password for the apache jenna fuseki connection?

## Answer

Expanded from original query via vocab: [fuseki, endpoint, data, query, upload, graph]. The current client has no username/password configuration and sends unauthenticated requests. Only FUSEKI_DATA_URL and FUSEKI_QUERY_URL are configurable. A protected Fuseki deployment would require adding credential environment variables and authentication to upload, delete, query, and health-check requests.

## Outcome

- Signal: useful

## Source Nodes

- ingest.py
- upload_graph()
- delete_graph()
- query_graph()