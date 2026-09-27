"""Every individual of a family class is declared an OWL named individual.

104 resources typed with a family class -- the bddo:DataType primitives, the dlv:Axis values, the
hxf functions, the conf and req closed sets, the register lifecycle statuses -- were not declared
owl:NamedIndividual, so an OWL 2 DL tool could not tell them from punned classes and dropped them
from its individual view. Every family resource whose rdf:type is a family owl:Class must also be
declared owl:NamedIndividual. SKOS concepts in the registers are exempt: they are concepts, typed
skos:Concept, not ontology individuals.

Names are not checked: existing individuals keep their published IRIs whatever their case, and
specification/ontology-design (Naming) states the convention for new ones.
"""
import sys

from rdflib import OWL, RDF, Namespace, URIRef

import specgraph

SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
HX = "https://hexplain.io/ns/"


def problems(g):
    classes = {c for c in g.subjects(RDF.type, OWL.Class) if str(c).startswith(HX)}
    found = set()
    for term, cls in g.subject_objects(RDF.type):
        if (isinstance(term, URIRef) and str(term).startswith(HX) and cls in classes
                and (term, RDF.type, SKOS.Concept) not in g and (term, RDF.type, OWL.NamedIndividual) not in g):
            found.add(f"{term} is typed {cls} but not declared owl:NamedIndividual")
    return sorted(found)


def self_test():
    from rdflib import Graph
    g = Graph().parse(format="turtle", data="""
        @prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix x: <https://hexplain.io/ns/x#> .
        x:C a owl:Class . x:i a x:C . x:j a x:C , owl:NamedIndividual . x:k a x:C , skos:Concept .""")
    assert problems(g) == [f"{HX}x#i is typed {HX}x#C but not declared owl:NamedIndividual"], problems(g)


def main():
    self_test()
    g = specgraph.ontologies()
    found = problems(g)
    if found:
        more = f"\n  ... and {len(found) - 80} more" if len(found) > 80 else ""
        print("FAIL:\n  " + "\n  ".join(found[:80]) + more)
        return 1
    count = sum(1 for t in set(g.subjects(RDF.type, OWL.NamedIndividual)) if str(t).startswith(HX))
    print(f"PASS: all {count} individuals of family classes are declared owl:NamedIndividual")
    return 0


if __name__ == "__main__":
    sys.exit(main())
