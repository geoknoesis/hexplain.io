"""Adversarial RDF-value tests: lexical form is not numeric value or term identity."""

from __future__ import annotations

import specgraph
from pyshacl import validate
from rdflib import RDF, BNode, Graph, Literal, Namespace, URIRef

A = Namespace("https://hexplain.io/ns/aspect/raster#")
S = Namespace("https://hexplain.io/ns/aspect/spatialref#")
X = Namespace("http://www.w3.org/2001/XMLSchema#")
SH = Namespace("http://www.w3.org/ns/shacl#")


class Probe:
    """Counts validation calls and collects the verdicts that disagree with the expectation."""

    def __init__(self, ontology: Graph, shapes: Graph) -> None:
        self.ontology = ontology
        self.shapes = shapes
        self.failures: list[str] = []
        self.count = 0

    def check(self, name: str, graph: Graph, expected: bool, shapes: Graph | None = None) -> None:
        self.count += 1
        actual = bool(validate(self.ontology + graph, shacl_graph=shapes or self.shapes, advanced=True)[0])
        if actual != expected:
            self.failures.append(f"{name}: expected {expected}, got {actual}")


def coefficient_vector(head: BNode, cells: int = 20) -> Graph:
    """A rational-polynomial coefficient list of ``cells`` equal double literals."""
    g = Graph()
    g.add((URIRef("urn:rpc"), S.lineNumerator, head))
    cell = head
    for i in range(cells):
        g.add((cell, RDF.first, Literal("1.0", datatype=X.double, normalize=False)))
        next_cell = BNode() if i < cells - 1 else RDF.nil
        g.add((cell, RDF.rest, next_cell))
        cell = next_cell
    return g


def main() -> int:
    probe = Probe(specgraph.ontologies(), specgraph.shapes())
    for lexical, expected in [
        ("1e309", False),
        ("-1e309", False),
        ("NaN", False),
        ("INF", False),
        ("1.7976931348623157e308", True),
        ("-0.0", True),
    ]:
        g = Graph()
        g.add((URIRef("urn:band"), A.sampleScale, Literal(lexical, datatype=X.double, normalize=False)))
        probe.check("calibration " + lexical, g, expected)

    g = Graph().parse(
        data="""@prefix a:<https://hexplain.io/ns/aspect/raster#>. @prefix x:<http://www.w3.org/2001/XMLSchema#>.
<urn:g> a:hasBand <urn:b>,<urn:c>. <urn:b> a:bandIndex 1. <urn:c> a:bandIndex "1"^^x:unsignedInt.""",
        format="turtle",
    )
    probe.check("equal band indices with different integer datatypes", g, False)

    # Two equal-valued but distinct double literals are still TWO rdf:first values.
    head = BNode()
    g = coefficient_vector(head)
    # Apply the vector shape directly through a small local target wrapper.
    wrapper = URIRef("urn:vector-test")
    local = probe.shapes + Graph()
    local.add((wrapper, RDF.type, SH.NodeShape))
    local.add((wrapper, SH.targetNode, head))
    local.add((wrapper, SH.node, S.CoefficientVectorShape))
    probe.check("valid 20-cell coefficient vector", g, True, local)
    g.add((head, RDF.first, Literal("1.00", datatype=X.double, normalize=False)))
    probe.check("duplicate equal-valued rdf:first", g, False, local)

    assert not probe.failures, "\n".join(probe.failures)
    print(f"PASS: {probe.count} lexical numeric and RDF term-identity boundary cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
