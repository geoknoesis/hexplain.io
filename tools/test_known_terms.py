"""Example and fixture data may only use Hexplain terms the family defines.

A typo in a fixture is silent: `bddo:sizeFromFeild` is just another predicate to RDF and to
SHACL, so a fixture meant to exercise size resolution validated while exercising nothing.
Every IRI in a namespace owned by a family module that appears in any non-vocabulary Turtle
file under specification/ (fixtures, examples, validation data) must be defined -- that is,
be the subject of a statement -- in the family's canonical graph. Deprecated terms count as
defined; they are declared precisely so that older data still resolves.
"""
import json
import pathlib
import sys

from rdflib import Graph, Literal, URIRef

import specgraph

ROOT = pathlib.Path(__file__).resolve().parents[1]
VANN_URI = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")


def owned_namespaces(g):
    return sorted({str(o) for o in g.objects(None, VANN_URI)}, key=len, reverse=True)


def unknown_terms(data, known, namespaces):
    found = set()
    for triple in data:
        for term in triple:
            if isinstance(term, Literal) or not isinstance(term, URIRef):
                continue
            iri = str(term)
            if any(iri.startswith(ns) and len(iri) > len(ns) for ns in namespaces) and term not in known:
                found.add(iri)
    return sorted(found)


def data_files():
    family = {(ROOT / "specification" / f).resolve()
              for f in json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]}
    return sorted(p for p in (ROOT / "specification").rglob("*.ttl") if p.resolve() not in family)


def main():
    vocabulary = specgraph.ontologies()
    known = set(vocabulary.subjects())
    namespaces = owned_namespaces(vocabulary)
    probe = Graph().parse(format="turtle", data="""@prefix bddo: <https://hexplain.io/ns/bddo#> .
        <urn:x> bddo:sizeFromFeild <urn:y> ; bddo:size 1 .""")
    assert unknown_terms(probe, known, namespaces) == ["https://hexplain.io/ns/bddo#sizeFromFeild"], \
        "the lint no longer notices a misspelled BDDO predicate"
    failures = []
    files = data_files()
    for path in files:
        g = Graph().parse(data=path.read_text(encoding="utf-8"), format="turtle")
        for iri in unknown_terms(g, known, namespaces):
            failures.append(f"{path.relative_to(ROOT).as_posix()}: {iri} is not defined by any family module")
    if failures:
        print("FAIL: undefined Hexplain terms in data:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: {len(files)} example/fixture files use only terms defined in {len(namespaces)} family namespaces")


if __name__ == "__main__":
    main()
