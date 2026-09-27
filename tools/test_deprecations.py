"""Every deprecated term says what to use instead, or why nothing replaces it.

owl:deprecated true tells a reader to stop using a term; on its own it does not say what to do
instead. Ten of the family's twenty-two deprecated terms said nothing more. Each deprecated term
must now name its replacement with dcterms:isReplacedBy -- a family term that is not itself
deprecated -- or, where no single term replaces it, explain in a skos:historyNote what happened
and what a description should do.
"""
import sys

from rdflib import OWL, Literal, Namespace, URIRef

import specgraph

DCTERMS = Namespace("http://purl.org/dc/terms/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def problems(g):
    found = []
    for term in sorted(set(g.subjects(OWL.deprecated, Literal(True))), key=str):
        if not isinstance(term, URIRef) or not str(term).startswith("https://hexplain.io/ns/"):
            continue
        replacements = list(g.objects(term, DCTERMS.isReplacedBy))
        notes = [n for n in g.objects(term, SKOS.historyNote) if str(n).strip()]
        if not replacements and not notes:
            found.append(f"{term}: deprecated with neither dcterms:isReplacedBy nor a skos:historyNote saying why none exists")
        for r in replacements:
            if r == term:
                found.append(f"{term}: replaced by itself")
            elif (r, OWL.deprecated, Literal(True)) in g:
                found.append(f"{term}: its replacement {r} is itself deprecated")
            elif str(r).startswith("https://hexplain.io/ns/") and not any(True for _ in g.predicate_objects(r)):
                found.append(f"{term}: its replacement {r} is not defined by the family")
    return found


def self_test():
    from rdflib import Graph
    g = Graph().parse(format="turtle", data="""
        @prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix dcterms: <http://purl.org/dc/terms/> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix x: <https://hexplain.io/ns/x#> .
        x:a owl:deprecated true .
        x:b owl:deprecated true ; skos:historyNote "Split into x:c and x:d; no single replacement." .
        x:e owl:deprecated true ; dcterms:isReplacedBy x:a .
        x:f owl:deprecated true ; dcterms:isReplacedBy x:c . x:c a owl:Class .""")
    found = problems(g)
    assert len(found) == 2 and any("x#a" in f for f in found) and any("x#e" in f for f in found), found


def main():
    self_test()
    g = specgraph.ontologies()
    found = problems(g)
    if found:
        print("FAIL:\n  " + "\n  ".join(found))
        return 1
    count = sum(1 for t in set(g.subjects(OWL.deprecated, Literal(True))) if str(t).startswith("https://hexplain.io/ns/"))
    print(f"PASS: all {count} deprecated family terms name a current replacement or explain why none exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())
