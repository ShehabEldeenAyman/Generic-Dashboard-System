---
type: "query"
date: "2026-08-06T09:36:50.609969+00:00"
question: "Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["rdf_instance_preview", "mapped_rdf_preview", "run_rdf2ldes", "generate_ldes", "App.jsx"]
---

# Q: Where should RDF preview, artifact downloads, and source-selectable LDES be implemented?

## Answer

Add subject-paginated mapped RDF preview to generic_pipeline and playground_server, expose preview/download controls in App.jsx, and pass an rdf-or-tss source_kind through run_rdf2ldes into RDFTSS2LDES.

## Outcome

- Signal: useful

## Source Nodes

- rdf_instance_preview
- mapped_rdf_preview
- run_rdf2ldes
- generate_ldes
- App.jsx