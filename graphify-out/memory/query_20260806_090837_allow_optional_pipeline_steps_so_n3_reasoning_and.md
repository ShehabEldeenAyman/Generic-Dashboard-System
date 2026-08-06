---
type: "query"
date: "2026-08-06T09:08:37.133697+00:00"
question: "Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages"
contributor: "graphify"
outcome: "useful"
source_nodes: ["rdf2tss_stage", "require_stage", "begin_stage", "App"]
---

# Q: Allow optional pipeline steps so N3 reasoning and SHACL validation do not lock future stages

## Answer

Expanded from graph vocabulary via [pipeline, stage, stages, reason, reasoner, rdf, tss, shacl, require, frontend]. Replaced the linear prerequisite chain with artifact-based dependencies, made SHACL and N3 stages optional, let RDF2TSS use reasoned RDF when available or mapped RDF otherwise, and prevented optional stages from invalidating unrelated downstream results.

## Outcome

- Signal: useful

## Source Nodes

- rdf2tss_stage
- require_stage
- begin_stage
- App