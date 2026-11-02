"""specification/req/requirements.ttl is the family's node shapes, restated: no more and no less.

The module was written once from the shapes of three modules and then maintained by hand, so it
covered 81 of the family's 179 node shapes and nothing noticed when a shape changed under its
requirement. It is now generated (tools/_build_shape_requirements.py), and this gate holds the
published file to the shapes without trusting the generator's own bookkeeping:

* the file is what the generator renders now (no drift);
* shapes and requirements are in bijection: every named sh:NodeShape of every family module is
  named by dcterms:references of exactly one reqs:ShapeRequirement, and every requirement names
  exactly one such shape;
* each statement is the shape's documented definition (its skos:definition, else its
  rdfs:comment), so a shape whose contract changes changes its requirement;
* each identifier is req-shape-<prefix>-<ShapeLocalName> and each source the publishing module's
  label, neither carrying a version: (req:fromStandard, req:requirementId) is the requirement's
  identity and must survive a version bump;
* each req:discrepancyType is the one the shape's constraints give.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import _build_shape_requirements as builder
from _family import canonical_files
from _reference import load, stated_definition
from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specification"
SH = Namespace("http://www.w3.org/ns/shacl#")
REQ = Namespace("https://hexplain.io/ns/req#")
REQS = Namespace("https://hexplain.io/ns/req/requirements#")
REFERENCES = URIRef("http://purl.org/dc/terms/references")
VERSION = re.compile(r"\d+\.\d+")


def family_shapes() -> dict[URIRef, tuple[Graph, Graph, str]]:
    """Named node shape -> (its module as authored, the module with its documentation, the module's label)."""
    found = {}
    for rel in canonical_files(SPEC):
        if rel == builder.TARGET:
            continue
        path = Path("specification") / rel
        own, documented = load([path], base=True), load([path])
        ontology = next(iter(own.subjects(RDF.type, OWL.Ontology)))
        label = str(
            next(o for o in own.objects(ontology, RDFS.label) if isinstance(o, Literal) and o.language in ("en", None))
        )
        for shape in set(own.subjects(RDF.type, SH.NodeShape)):
            if isinstance(shape, URIRef):
                assert shape not in found, f"{shape} is declared by two modules"
                found[shape] = (own, documented, label)
    return found


def requirement_problems(g: Graph, requirement: Any, shapes: dict[URIRef, Any], prefixes: dict[str, str]) -> list[str]:
    """What is wrong with one requirement, given the shape it must restate."""
    name = str(requirement).rsplit("#", 1)[-1]
    referenced = list(g.objects(requirement, REFERENCES))
    if len(referenced) != 1 or not isinstance(referenced[0], URIRef) or referenced[0] not in shapes:
        return [f"{name}: dcterms:references must name exactly one node shape of the family, not {referenced}"]
    shape = referenced[0]
    own, documented, label = shapes[shape]
    namespace, local = str(shape).rsplit("#", 1)
    expected = {
        REQ.requirementId: f"req-shape-{prefixes[namespace + '#']}-{local}",
        REQ.fromStandard: label,
        REQ.statement: str(stated_definition(documented, shape)),
        REQ.discrepancyType: builder.classification(own, shape),
    }
    found = []
    for predicate, value in expected.items():
        stated = [o if isinstance(o, URIRef) else str(o) for o in g.objects(requirement, predicate)]
        if stated != [value]:
            found.append(f"{name}: {predicate.n3(g.namespace_manager)} is {stated}, the shape gives {value!r}")
    if name != expected[REQ.requirementId]:
        found.append(f"{name}: the IRI's local name differs from its identifier {expected[REQ.requirementId]}")
    for predicate in (REQ.requirementId, REQ.fromStandard):
        if any(VERSION.search(str(o)) for o in g.objects(requirement, predicate)):
            found.append(f"{name}: {predicate.n3(g.namespace_manager)} carries a version; identity must not")
    return found


def problems(g: Graph, shapes: dict[URIRef, Any], prefixes: dict[str, str]) -> list[str]:
    found = []
    requirements = sorted(set(g.subjects(RDF.type, REQS.ShapeRequirement)), key=str)
    covered: dict[Any, int] = {}
    for requirement in requirements:
        found += requirement_problems(g, requirement, shapes, prefixes)
        for shape in g.objects(requirement, REFERENCES):
            covered[shape] = covered.get(shape, 0) + 1
    found += [f"{shape} has no shape requirement" for shape in sorted(set(shapes) - set(covered))]
    found += [f"{shape} has {n} shape requirements" for shape, n in sorted(covered.items()) if n > 1]
    return found


PROBE = """
@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <https://hexplain.io/ns/x#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://hexplain.io/ns/x> a owl:Ontology ; rdfs:label "Example Vocabulary"@en .
ex:ValueShape a sh:NodeShape ; rdfs:comment "An integer."@en ;
    sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:int ] ) .
ex:PlainShape a sh:NodeShape ; rdfs:comment "Counts."@en ;
    sh:property [ sh:path ex:a ; sh:datatype xsd:string ; sh:maxCount 1 ; sh:not [ sh:pattern "^x" ] ] .
ex:ChoiceShape a sh:NodeShape ; rdfs:comment "One of two."@en ;
    sh:xone ( [ sh:property [ sh:path ex:a ; sh:minCount 1 ] ] [ sh:property [ sh:path ex:b ; sh:minCount 1 ] ] ) .
ex:PairShape a sh:NodeShape ; rdfs:comment "Ordered."@en ;
    sh:property [ sh:path ex:a ; sh:lessThan ex:b ] .
ex:QueryShape a sh:NodeShape ; rdfs:comment "Queried."@en ; sh:sparql [ sh:select "SELECT $this WHERE { }" ] .
"""


def self_test() -> None:
    probe = Graph().parse(data=PROBE, format="turtle")
    ex = Namespace("https://hexplain.io/ns/x#")
    kinds = {
        name: builder.classification(probe, ex[name + "Shape"])
        for name in ("Value", "Plain", "Choice", "Pair", "Query")
    }
    assert kinds == {
        "Value": REQ.Syntactic,
        "Plain": REQ.Syntactic,
        "Choice": REQ.Semantic,
        "Pair": REQ.Semantic,
        "Query": REQ.Semantic,
    }, kinds
    shapes = {ex.ValueShape: (probe, probe, "Example Vocabulary"), ex.ChoiceShape: (probe, probe, "Example Vocabulary")}
    prefixes = {str(ex): "ex"}
    g = Graph().parse(
        format="turtle",
        data="""
        @prefix req: <https://hexplain.io/ns/req#> . @prefix reqs: <https://hexplain.io/ns/req/requirements#> .
        @prefix dcterms: <http://purl.org/dc/terms/> . @prefix ex: <https://hexplain.io/ns/x#> .
        reqs:req-shape-ex-ValueShape a reqs:ShapeRequirement ; req:requirementId "req-shape-ex-ValueShape" ;
            req:fromStandard "Example Vocabulary" ; req:statement "An integer."@en ;
            req:discrepancyType req:Syntactic ; dcterms:references ex:ValueShape .""",
    )
    assert problems(g, shapes, prefixes) == [f"{ex.ChoiceShape} has no shape requirement"], problems(
        g, shapes, prefixes
    )
    g.parse(
        format="turtle",
        data="""
        @prefix req: <https://hexplain.io/ns/req#> . @prefix reqs: <https://hexplain.io/ns/req/requirements#> .
        @prefix dcterms: <http://purl.org/dc/terms/> . @prefix ex: <https://hexplain.io/ns/x#> .
        reqs:req-shape-ChoiceShape a reqs:ShapeRequirement ; req:requirementId "req-shape-ex-ChoiceShape" ;
            req:fromStandard "Example Vocabulary 1.3" ; req:statement "Stale text."@en ;
            req:discrepancyType req:Syntactic ; dcterms:references ex:ChoiceShape .
        reqs:req-shape-ex-Gone a reqs:ShapeRequirement ; dcterms:references ex:GoneShape .""",
    )
    found = problems(g, shapes, prefixes)
    assert len(found) == 6, found
    for needle in ("req:fromStandard is", "req:statement is", "req:discrepancyType is", "local name", "a version"):
        assert any(needle in row for row in found), (needle, found)
    assert any("must name exactly one node shape" in row for row in found), found


def main() -> int:
    self_test()
    shapes = family_shapes()
    g = Graph().parse(data=(SPEC / builder.TARGET).read_text(encoding="utf-8"), format="turtle")
    found = problems(g, shapes, builder.namespaces())
    try:
        builder.run()
    except AssertionError as stale:
        found.append(str(stale))
    if found:
        print(
            "FAIL:\n  " + "\n  ".join(found[:60]) + (f"\n  ... and {len(found) - 60} more" if len(found) > 60 else "")
        )
        return 1
    print(
        f"PASS: {len(shapes)} node shapes of the family and {len(shapes)} shape requirements are in bijection; "
        "every statement, source, identifier and discrepancy type follows its shape"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
