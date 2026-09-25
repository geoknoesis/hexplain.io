"""Generated usage notes claim only what is true of the term they are attached to.

Most skos:scopeNote values are generated (tools/_reference.py, written by
_build_term_reference.py --enrich) from a module sentence and a sentence about the term's kind.
727 of 902 were one shared template, and several said false things: "subclass links below" on
classes with no subclass link, "applicable SHACL paths are listed below" on properties no shape
uses, "No automatic target" on a shape with a SPARQL target, and the core module's "use when
linking a physical format description to semantic RDF output" on the register-lifecycle terms.
This gate checks each claim a template can make against the family graph, and that the modules
whose terms have notes of their own (core, conf, req, bundle) carry no module sentence on a term.
"""
import sys
from collections import Counter

from rdflib import OWL, RDF, RDFS, URIRef

import specgraph
from _reference import PATH_NOTE, SCOPE, SH, SKOS, SUBCLASS_NOTE, TERM_SCOPED, kind

CLAIMS = {
    "subclass links below": lambda g, t: (t, RDFS.subClassOf, None) in g or (None, RDFS.subClassOf, t) in g,
    "Applicable SHACL paths and their focus-node scopes are listed below":
        lambda g, t: any((None, p, t) in g for p in (SH.path, SH.targetSubjectsOf, SH.targetObjectsOf)),
    "No shape of the family constrains it":
        lambda g, t: not any((None, p, t) in g for p in (SH.path, SH.targetSubjectsOf, SH.targetObjectsOf)),
    "No automatic target": lambda g, t: not any((t, p, None) in g for p in
                                                (SH.targetClass, SH.targetSubjectsOf, SH.targetObjectsOf,
                                                 SH.targetNode, SH.target)),
    "Use this IRI as a controlled value": lambda g, t: kind(g, t) == "Named individual",
    "Assert this class on a resource": lambda g, t: (t, RDF.type, OWL.Class) in g,
    "Use it as a predicate": lambda g, t: "property" in kind(g, t).lower(),
}


def problems(g):
    found = []
    for t, note in g.subject_objects(SKOS.scopeNote):
        if not isinstance(t, URIRef) or not str(t).startswith("https://hexplain.io/ns/"):
            continue
        text = str(note)
        for claim, holds in CLAIMS.items():
            if claim in text and not holds(g, t):
                found.append(f"{t}: its scope note says '{claim}', which is false of it")
        module = str(t).split("#")[0].removesuffix("/shapes").rsplit("/", 1)[-1]
        if module in TERM_SCOPED and "#" in str(t) and SCOPE[module] in text:
            found.append(f"{t}: carries the {module} module sentence instead of a note of its own")
    return found


def self_test():
    from rdflib import Graph
    g = Graph().parse(format="turtle", data=f"""
        @prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix sh: <http://www.w3.org/ns/shacl#> .
        <https://hexplain.io/ns/x#C> a owl:Class ; skos:scopeNote "Assert this class on a resource.{SUBCLASS_NOTE}" .
        <https://hexplain.io/ns/x#p> a owl:ObjectProperty ; skos:scopeNote "Use it as a predicate.{PATH_NOTE}" .
        <https://hexplain.io/ns/x#S> a sh:NodeShape ; sh:target [ ] ; skos:scopeNote "Validation activation: No automatic target." .""")
    assert len(problems(g)) == 3, problems(g)


def main():
    self_test()
    g = specgraph.ontologies()
    found = problems(g)
    if found:
        print("FAIL: scope notes whose claims are false:\n  " + "\n  ".join(found[:60]))
        return 1
    notes = Counter(str(o) for t, o in g.subject_objects(SKOS.scopeNote)
                    if isinstance(t, URIRef) and str(t).startswith("https://hexplain.io/ns/"))
    shared = sum(n for n in notes.values() if n > 1)
    print(f"PASS: {sum(notes.values())} scope notes make only true claims ({len(notes)} distinct; "
          f"{shared} share their text with another term)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
