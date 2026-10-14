"""The registered character encodings are listed once: every shape's copy equals the individuals.

bddo:encoding is an open set with a registered core. Shapes name that core by IRI, so that a
description validates against the shapes alone, without the vocabulary loaded; the list is
therefore written into the shapes, and a list written in several places drifts: adding an
encoding individual without extending every sh:in would refuse it on one shape and accept it on
the next. The lists are expanded from one authoring pattern, and this gate checks the result in
the canonical Turtle, whatever produced it:

* every sh:in that lists a registered encoding lists exactly the bddo:Encoding individuals the
  vocabulary declares (the profile-minted bddo:CustomEncoding class has none of its own here);
* the charset names bddo:CustomEncodingCharsetShape advises against re-minting are exactly the
  bddo:ianaCharset values of those individuals;
* the byte-order-ambiguous charset names it advises against are the four the vocabulary's
  comments name: UTF-16, UTF-32, ISO-10646-UCS-2 and UCS-2;
* both advisory property shapes are sh:Warning, so neither can make a description invalid.
"""

from __future__ import annotations

import re
from pathlib import Path

from rdflib import RDF, Graph, Namespace, URIRef
from rdflib.collection import Collection

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "specification/bddo/bddo.ttl"
SH = Namespace("http://www.w3.org/ns/shacl#")
BDDO = Namespace("https://hexplain.io/ns/bddo#")
AMBIGUOUS = {"UTF-16", "UTF-32", "ISO-10646-UCS-2", "UCS-2"}
ALTERNATION = re.compile(r"^\^\(([^()]+)\)\$$")


def registered(g: Graph) -> set[URIRef]:
    """The encodings the vocabulary itself declares: the individuals typed bddo:Encoding."""
    return {s for s in g.subjects(RDF.type, BDDO.Encoding) if isinstance(s, URIRef)}


def encoding_lists(g: Graph, individuals: set[URIRef]) -> list[set[URIRef]]:
    """Every sh:in list that names at least one registered encoding."""
    lists = [{m for m in Collection(g, lst) if isinstance(m, URIRef)} for lst in g.objects(None, SH["in"])]
    return [members for members in lists if members & individuals]


def advised_names(g: Graph) -> list[tuple[set[str], URIRef | None]]:
    """The charset-name alternations of bddo:CustomEncodingCharsetShape, with each one's severity."""
    rows: list[tuple[set[str], URIRef | None]] = []
    for pshape in g.objects(BDDO.CustomEncodingCharsetShape, SH.property):
        for negated in g.objects(pshape, SH["not"]):
            pattern = ALTERNATION.match(str(g.value(negated, SH.pattern) or ""))
            assert pattern, f"unreadable charset pattern: {g.value(negated, SH.pattern)}"
            assert str(g.value(negated, SH.flags)) == "i", "charset names are compared ignoring case"
            severity = g.value(pshape, SH.severity)
            rows.append((set(pattern[1].split("|")), severity if isinstance(severity, URIRef) else None))
    return rows


def problems(g: Graph) -> list[str]:
    found = []
    individuals = registered(g)
    lists = encoding_lists(g, individuals)
    if len(lists) < 3:
        found.append(f"expected the registered encodings in at least three sh:in lists, found {len(lists)}")
    for members in lists:
        if members != individuals:
            missing = sorted(str(x).rsplit("#", 1)[-1] for x in individuals - members)
            extra = sorted(str(x).rsplit("#", 1)[-1] for x in members - individuals)
            found.append(f"an sh:in list of encodings differs from the individuals: missing {missing}, extra {extra}")
    charsets = {str(o) for s in individuals for o in g.objects(s, BDDO.ianaCharset)}
    advised = advised_names(g)
    if sorted(map(sorted, (names for names, _ in advised))) != sorted(map(sorted, (charsets, AMBIGUOUS))):
        found.append(
            "bddo:CustomEncodingCharsetShape advises against "
            f"{sorted(sorted(names) for names, _ in advised)}; expected the registered charsets "
            f"{sorted(charsets)} and the ambiguous names {sorted(AMBIGUOUS)}"
        )
    found += ["an advisory charset check is not sh:Warning" for _names, severity in advised if severity != SH.Warning]
    return found


def self_test() -> None:
    probe = Graph().parse(
        format="turtle",
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix bddo: <https://hexplain.io/ns/bddo#> .
        bddo:a a bddo:Encoding ; bddo:ianaCharset "A" . bddo:b a bddo:Encoding ; bddo:ianaCharset "B" .
        bddo:S sh:property [ sh:in ( bddo:a bddo:b ) ] , [ sh:in ( bddo:a ) ] ; sh:not [ sh:in ( bddo:b bddo:a ) ] .
        bddo:CustomEncodingCharsetShape
            sh:property [ sh:severity sh:Warning ; sh:not [ sh:pattern "^(A)$" ; sh:flags "i" ] ] ,
                [ sh:not [ sh:pattern "^(UTF-16|UTF-32|ISO-10646-UCS-2|UCS-2)$" ; sh:flags "i" ] ] .""",
    )
    found = problems(probe)
    assert len(found) == 3, found
    assert "missing ['b']" in found[0] and "advises against" in found[1] and "not sh:Warning" in found[2], found


def main() -> int:
    self_test()
    g = Graph().parse(data=MODULE.read_text(encoding="utf-8"), format="turtle")
    found = problems(g)
    if found:
        print("FAIL:\n  " + "\n  ".join(found))
        return 1
    print(
        f"PASS: {len(registered(g))} registered encodings, listed identically by "
        f"{len(encoding_lists(g, registered(g)))} shapes; the charset advice matches them"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
