"""SHACL validation and rule execution on top of pySHACL.

Validation checks SHACL Core and SHACL-SPARQL constraints (``sh:sparql``) against
the data as given; any ``sh:rule`` in the shapes graph is ignored there, so rules
never run twice. ``apply_rules`` materialises ``sh:rule`` output (``sh:TripleRule``
and ``sh:SPARQLRule``) as a new graph, in one pass ordered by ``sh:order``.
"""

from __future__ import annotations

import time
from typing import Any

import pyshacl
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
from rdflib.term import Node

SH = Namespace("http://www.w3.org/ns/shacl#")
SEVERITY_ORDER = {"Violation": 0, "Warning": 1, "Info": 2}
DEFAULT_RESULT_LIMIT = 500


def _local_name(term: Node | None) -> str:
    if term is None:
        return ""
    text = str(term)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _display(term: Node | None) -> str | None:
    if term is None:
        return None
    if isinstance(term, BNode):
        return "(blank node)"
    if isinstance(term, Literal):
        return str(term)
    return str(term)


def _path_display(graph: Graph, path: Node | None) -> str | None:
    if path is None:
        return None
    if isinstance(path, URIRef):
        return str(path)
    inverse = graph.value(path, SH.inversePath)
    if isinstance(inverse, URIRef):
        return f"^{inverse}"
    return "(complex property path)"


def shapes_summary(shapes: Graph) -> dict[str, int]:
    """Count the shapes, constraints, and rules a shapes graph declares."""
    node_shapes = set(shapes.subjects(RDF.type, SH.NodeShape))
    property_shapes = set(shapes.subjects(RDF.type, SH.PropertyShape)) | set(
        shapes.objects(None, SH.property)
    )
    return {
        "node_shapes": len(node_shapes),
        "property_shapes": len(property_shapes),
        "sparql_constraints": len(set(shapes.objects(None, SH.sparql))),
        "rules": len(set(shapes.objects(None, SH.rule))),
    }


def validate(
    data: Graph,
    shapes: Graph,
    *,
    result_limit: int = DEFAULT_RESULT_LIMIT,
) -> dict[str, Any]:
    """Validate ``data`` and return a structured, display-ready report."""
    constraints = Graph()
    for triple in shapes:
        if triple[1] != SH.rule:
            constraints.add(triple)
    started = time.perf_counter()
    conforms, results_graph, report_text = pyshacl.validate(
        data,
        shacl_graph=constraints,
        advanced=True,
        abort_on_first=False,
        meta_shacl=False,
    )
    duration = round(time.perf_counter() - started, 2)

    results: list[dict[str, Any]] = []
    for node in results_graph.subjects(RDF.type, SH.ValidationResult):
        severity = _local_name(results_graph.value(node, SH.resultSeverity)) or "Violation"
        messages = sorted(str(message) for message in results_graph.objects(node, SH.resultMessage))
        component = _local_name(results_graph.value(node, SH.sourceConstraintComponent))
        source_shape = results_graph.value(node, SH.sourceShape)
        results.append(
            {
                "severity": severity,
                "focus_node": _display(results_graph.value(node, SH.focusNode)),
                "path": _path_display(results_graph, results_graph.value(node, SH.resultPath)),
                "value": _display(results_graph.value(node, SH.value)),
                "message": " / ".join(messages),
                "constraint": component.removesuffix("ConstraintComponent"),
                "source_shape": str(source_shape) if isinstance(source_shape, URIRef) else None,
            }
        )

    results.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(item["severity"], 9),
            item["focus_node"] or "",
            item["path"] or "",
        )
    )
    severity_counts = {name: 0 for name in SEVERITY_ORDER}
    for item in results:
        severity_counts[item["severity"]] = severity_counts.get(item["severity"], 0) + 1

    return {
        "conforms": bool(conforms),
        "total_results": len(results),
        "severity_counts": severity_counts,
        "results": results[:result_limit],
        "truncated": len(results) > result_limit,
        "report_text": report_text,
        "duration_seconds": duration,
    }


def apply_rules(data: Graph, shapes: Graph) -> Graph:
    """Return a copy of ``data`` expanded with every triple the SHACL rules infer."""
    expanded = pyshacl.shacl_rules(
        data,
        shacl_graph=shapes,
        advanced=True,
        inplace=False,
    )
    result = Graph()
    for prefix, namespace in data.namespaces():
        result.bind(prefix, namespace, override=False)
    # pySHACL may return a quad-aware graph; triples() yields plain triples either way.
    for triple in expanded.triples((None, None, None)):
        result.add(triple)
    return result
