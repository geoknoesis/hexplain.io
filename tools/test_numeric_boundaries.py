"""Adversarial RDF-value tests: lexical form is not numeric value or term identity.

The cases are raster and spatial-reference statements, so they are validated in the context of
those modules (and what they import) rather than the whole family: the modules' triples with the
case's own are the data graph, and their shapes the shapes graph.
"""

from __future__ import annotations

from dataclasses import dataclass

import specgraph
from _cases import PREFIXES, prefix_block
from pyshacl import validate
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

A = Namespace(PREFIXES["raster"])
S = Namespace(PREFIXES["spatialref"])
X = Namespace(PREFIXES["xsd"])
SH = Namespace(PREFIXES["sh"])
#: The node shape a coefficient-vector case is aimed at through a local target wrapper.
WRAPPER = URIRef("urn:vector-test")


@dataclass(frozen=True)
class Case:
    """One data graph and its verdict; ``target`` aims the coefficient-vector shape at a node."""

    name: str
    graph: Graph
    expected: bool
    target: BNode | None = None


def calibration(lexical: str) -> Graph:
    """A band whose sample scale is the double written exactly as ``lexical``."""
    g = Graph()
    g.add((URIRef("urn:band"), A.sampleScale, Literal(lexical, datatype=X.double, normalize=False)))
    return g


def coefficient_vector(head: BNode, cells: int = 20) -> Graph:
    """A rational-polynomial coefficient list of ``cells`` equal double literals."""
    g = Graph()
    g.add((URIRef("urn:rpc"), S.lineNumerator, head))
    cell: BNode | URIRef = head
    for i in range(cells):
        g.add((cell, RDF.first, Literal("1.0", datatype=X.double, normalize=False)))
        next_cell: BNode | URIRef = BNode() if i < cells - 1 else RDF.nil
        g.add((cell, RDF.rest, next_cell))
        cell = next_cell
    return g


def cases() -> list[Case]:
    """Every boundary case, in authored order."""
    rows = [
        Case("calibration " + lexical, calibration(lexical), expected)
        for lexical, expected in [
            ("1e309", False),
            ("-1e309", False),
            ("NaN", False),
            ("INF", False),
            ("1.7976931348623157e308", True),
            ("-0.0", True),
        ]
    ]
    indices = Graph().parse(
        data=prefix_block({"a": "raster", "x": "xsd"})
        + '<urn:g> a:hasBand <urn:b>,<urn:c>. <urn:b> a:bandIndex 1. <urn:c> a:bandIndex "1"^^x:unsignedInt.',
        format="turtle",
    )
    rows.append(Case("equal band indices with different integer datatypes", indices, False))
    head = BNode()
    rows.append(Case("valid 20-cell coefficient vector", coefficient_vector(head), True, head))
    # Two equal-valued but distinct double literals are still TWO rdf:first values.
    doubled = coefficient_vector(head)
    doubled.add((head, RDF.first, Literal("1.00", datatype=X.double, normalize=False)))
    rows.append(Case("duplicate equal-valued rdf:first", doubled, False, head))
    return rows


def targeted(shapes: Graph, node: BNode) -> Graph:
    """``shapes`` plus a wrapper that applies the coefficient-vector shape directly to ``node``."""
    local = shapes + Graph()
    local.add((WRAPPER, RDF.type, SH.NodeShape))
    local.add((WRAPPER, SH.targetNode, node))
    local.add((WRAPPER, SH.node, S.CoefficientVectorShape))
    return local


def main() -> int:
    rows = cases()
    context, shapes = specgraph.context_and_shapes(specgraph.modules_used_by(*(case.graph for case in rows)))
    failures = []
    for case in rows:
        aimed = shapes if case.target is None else targeted(shapes, case.target)
        actual = bool(validate(context + case.graph, shacl_graph=aimed, advanced=True)[0])
        if actual != case.expected:
            failures.append(f"{case.name}: expected {case.expected}, got {actual}")
    assert not failures, "\n".join(failures)
    print(f"PASS: {len(rows)} lexical numeric and RDF term-identity boundary cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
