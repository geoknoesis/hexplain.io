"""Every human-readable annotation of a family term is a literal tagged @en.

A review counted 710 rdfs:label values that were plain literals beside 277 tagged @en, and
rdfs:comment untagged throughout while every generated skos:definition was @en. A consumer asking
for English labels (FILTER(lang(?l) = "en")) silently lost two thirds of them. rdfs:label,
rdfs:comment, skos:prefLabel, skos:altLabel, skos:definition, skos:scopeNote, skos:note,
skos:historyNote, skos:changeNote and skos:example of every family term are now tagged @en.
skos:notation and sh:message are not prose annotations and are not checked.
"""
import sys

from rdflib import RDFS, Literal, Namespace, URIRef

import specgraph

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
PROSE = (RDFS.label, RDFS.comment, SKOS.prefLabel, SKOS.altLabel, SKOS.definition, SKOS.scopeNote,
         SKOS.note, SKOS.historyNote, SKOS.changeNote, SKOS.example)
HX = "https://hexplain.io/ns/"


def problems(g):
    found = []
    for predicate in PROSE:
        for term, value in g.subject_objects(predicate):
            if isinstance(term, URIRef) and str(term).startswith(HX) and isinstance(value, Literal) and value.language != "en":
                found.append(f"{term} {predicate.n3(g.namespace_manager)} {value.n3()[:60]} is not tagged @en")
    return sorted(found)


def self_test():
    from rdflib import Graph
    g = Graph().parse(format="turtle", data="""
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix x: <https://hexplain.io/ns/x#> .
        x:i rdfs:label "i"@en ; rdfs:comment "plain" . x:j rdfs:label "j"@de . <urn:other> rdfs:label "not ours" .""")
    assert len(problems(g)) == 2, problems(g)


def main():
    self_test()
    g = specgraph.ontologies()
    found = problems(g)
    if found:
        more = f"\n  ... and {len(found) - 80} more" if len(found) > 80 else ""
        print("FAIL:\n  " + "\n  ".join(found[:80]) + more)
        return 1
    count = sum(1 for p in PROSE for t, _ in g.subject_objects(p) if isinstance(t, URIRef) and str(t).startswith(HX))
    print(f"PASS: all {count} prose annotations of family terms are tagged @en")
    return 0


if __name__ == "__main__":
    sys.exit(main())
