"""Every XSD-ranged datatype property has an activated, compatible sh:datatype constraint.

An rdfs:range is an inference axiom: RDFS reads `hexplain:byteLength "abc"` as a claim about
"abc", not as an error. Without a matching SHACL datatype the family's shapes accepted
`bddo:size 3.5`, `hexplain:byteOffset -5` and `asref:epsgCode 4326.7` -- 58 properties had a
range and nothing enforcing it. This gate fails when a property with an XSD range lacks a
shape that (a) targets the subjects of that property and (b) restricts its values to a
datatype compatible with the range, or when any shape admits an incompatible datatype.
The negative fixtures under specification/*/test/range-*-invalid.ttl prove the constraints
reject the values that used to pass.
"""
import sys

from rdflib import Graph

import specgraph
from _range_datatypes import problems


def _self_test():
    """The detector must notice a missing and an incompatible datatype, or it proves nothing."""
    g = Graph().parse(format="turtle", data="""
        @prefix ex: <https://example.org/> . @prefix sh: <http://www.w3.org/ns/shacl#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        ex:good rdfs:range xsd:positiveInteger . ex:none rdfs:range xsd:string . ex:wrong rdfs:range xsd:integer .
        ex:S a sh:NodeShape ; sh:targetSubjectsOf ex:good, ex:wrong ;
          sh:property [ sh:path ex:good ; sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:long ] ) ] ;
          sh:property [ sh:path ex:wrong ; sh:datatype xsd:decimal ] .""")
    found = problems(g)
    assert not any(p.startswith("https://example.org/good") for p in found), found
    assert any(p.startswith("https://example.org/none") for p in found), found
    assert any(p.startswith("https://example.org/wrong") and "incompatible" in p for p in found), found


def main():
    _self_test()
    g = specgraph.ontologies()
    found = problems(g)
    if found:
        print("FAIL: XSD ranges without an enforcing SHACL datatype:\n  " + "\n  ".join(found))
        sys.exit(1)
    from _range_datatypes import xsd_ranged
    print(f"PASS: {len(xsd_ranged(g))} XSD-ranged properties are datatype-checked wherever they are used")


if __name__ == "__main__":
    main()
