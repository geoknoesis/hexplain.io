"""One integer value shape, spelt once: every module's copy equals the shared template.

Shapes are validated module by module, so each module that ranges a property over integers
carries its own <prefix>:IntegerValueShape. specification/shared-patterns/integer-value-shape.json
lists those modules and integer-value-shape.ttl.template is the one spelling; this gate renders the
template per listed module and requires the result verbatim in the module's canonical Turtle.
A family module that declares an IntegerValueShape
without being listed, or declares it twice, fails.

The shape is also the ONLY spelling of the family: a canonical module that writes the union out
again (an sh:or whose every branch is one sh:datatype of an XSD integer type) fails, whatever the
subset or the order. Such a copy accepted a different set of datatypes than its neighbours
(xsd:integer or xsd:positiveInteger here, seven of the eleven there), so the same count was valid
on one property and refused on the next. A property that takes an integer says
`sh:node <prefix>:IntegerValueShape`, with its own bounds.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from _family import canonical_files
from rdflib import Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import XSD

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "specification/shared-patterns/integer-value-shape.json"
DECLARATION = re.compile(r"^\S*:IntegerValueShape a sh:NodeShape", re.M)
SH = Namespace("http://www.w3.org/ns/shacl#")
INTEGER_FAMILY = {
    XSD.integer,
    XSD.positiveInteger,
    XSD.nonNegativeInteger,
    XSD.negativeInteger,
    XSD.nonPositiveInteger,
    XSD.int,
    XSD.long,
    XSD.short,
    XSD.byte,
    XSD.unsignedInt,
    XSD.unsignedLong,
    XSD.unsignedShort,
    XSD.unsignedByte,
}


def inline_unions(g: Graph) -> list[str]:
    """Every integer-family union a graph spells out anywhere but in an IntegerValueShape."""
    found = []
    for owner, union in g.subject_objects(SH["or"]):
        if isinstance(owner, URIRef) and str(owner).endswith("#IntegerValueShape"):
            continue
        branches = list(Collection(g, union))
        datatypes = [g.value(b, SH.datatype) for b in branches if len(list(g.predicate_objects(b))) == 1]
        if len(branches) > 1 and len(datatypes) == len(branches) and set(datatypes) <= INTEGER_FAMILY:
            path = g.value(owner, SH.path)
            where = path.n3(g.namespace_manager) if path is not None else owner.n3(g.namespace_manager)
            found.append(f"{where}: sh:or of {', '.join(sorted(d.n3(g.namespace_manager) for d in datatypes))}")
    return sorted(found)


def rendered(template: str, prefix: str, ontology: str) -> str:
    body = "\n".join(line for line in template.splitlines() if not line.startswith("#")).strip() + "\n"
    if body.count("@PREFIX@") != 1 or body.count("@ONTOLOGY@") != 1:
        raise ValueError("the template names the prefix and the ontology exactly once each")
    return body.replace("@PREFIX@", prefix).replace("@ONTOLOGY@", ontology)


def problems() -> tuple[list[str], int]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    template = (ROOT / contract["template"]).read_text(encoding="utf-8")
    found, listed = [], set()
    for row in contract["copies"]:
        listed.add(row["file"])
        text = (ROOT / row["file"]).read_text(encoding="utf-8")
        if rendered(template, row["prefix"], row["ontology"]) not in text:
            found.append(f"{row['file']}: {row['prefix']}:IntegerValueShape differs from the shared template")
        if len(DECLARATION.findall(text)) != 1:
            found.append(f"{row['file']}: IntegerValueShape is declared {len(DECLARATION.findall(text))} times")
    if contract["master"] not in listed:
        found.append("the master module is not among the copies")
    family = canonical_files(ROOT / "specification")
    for rel in family:
        path = "specification/" + rel
        if path not in listed and DECLARATION.search((ROOT / path).read_text(encoding="utf-8")):
            found.append(f"{path}: declares an IntegerValueShape but is not listed in {CONTRACT.name}")
        graph = Graph().parse(data=(ROOT / path).read_text(encoding="utf-8"), format="turtle")
        found += [
            f"{path}: inline integer-family union on {row}; use sh:node IntegerValueShape"
            for row in inline_unions(graph)
        ]
    return found, len(listed)


def self_test() -> None:
    template = "# comment\n@PREFIX@:IntegerValueShape a sh:NodeShape ;\n    rdfs:isDefinedBy <@ONTOLOGY@> .\n"
    assert rendered(template, "x", "urn:x") == "x:IntegerValueShape a sh:NodeShape ;\n    rdfs:isDefinedBy <urn:x> .\n"
    assert DECLARATION.search("x:IntegerValueShape a sh:NodeShape ;")
    assert not DECLARATION.search("    sh:node x:IntegerValueShape ;")
    probe = Graph().parse(
        format="turtle",
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix ex: <urn:ex#> .
        ex:IntegerValueShape sh:or ( [ sh:datatype xsd:integer ] [ sh:datatype xsd:int ] ) .
        ex:S sh:property [ sh:path ex:count ;
                sh:or ( [ sh:datatype xsd:positiveInteger ] [ sh:datatype xsd:integer ] ) ] ;
            sh:property [ sh:path ex:rate ; sh:or ( [ sh:datatype xsd:decimal ] [ sh:datatype xsd:integer ] ) ] ;
            sh:property [ sh:path ex:n ; sh:node ex:IntegerValueShape ] .""",
    )
    assert inline_unions(probe) == ["ex:count: sh:or of xsd:integer, xsd:positiveInteger"], inline_unions(probe)


def main() -> int:
    self_test()
    found, count = problems()
    if found:
        print("FAIL:\n  " + "\n  ".join(found))
        return 1
    print(f"PASS: {count} modules carry the one IntegerValueShape, each equal to the shared template")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
