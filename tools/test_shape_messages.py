"""Every property shape whose results a validator reports carries its own sh:message.

Without sh:message a SHACL result says only which constraint component failed ("MinCount",
"Datatype") on which path; 59% of the family's property shapes gave nothing more, so a profile
author had to read the shapes graph to learn what was wanted. This gate requires an sh:message on
every REPORTED property shape: the object of sh:property on a named shape, on a targeted blank
node shape, or on such a property shape in turn.

A property shape nested inside sh:not, sh:or, sh:and, sh:xone, sh:node or sh:qualifiedValueShape
is exempt. SHACL reports a logical or node constraint as ONE result of the enclosing shape, with
the enclosing shape's message; the nested shape's own message is never shown, so requiring one
there would only add text nobody reads.

It also rejects a message that names a SPARQL result variable ({?x}) on a property shape: only a
SPARQL-based constraint binds such variables, so on a property shape the placeholder is printed
literally.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from _family import canonical_files
from rdflib import Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
SH = Namespace("http://www.w3.org/ns/shacl#")
TARGETS = (SH.targetClass, SH.targetSubjectsOf, SH.targetObjectsOf, SH.targetNode, SH.target)
PLACEHOLDER = re.compile(r"\{[?$][A-Za-z_]\w*\}")


def reported(g: Graph, pshape: Any, seen: frozenset[Any] | set[Any] = frozenset()) -> bool:
    """True when a validator reports [pshape]'s results with [pshape] as their source shape."""
    if pshape in seen:
        return False
    for owner in g.subjects(SH.property, pshape):
        if isinstance(owner, URIRef) or any((owner, t, None) in g for t in TARGETS):
            return True
        if (owner, SH.path, None) in g and reported(g, owner, seen | {pshape}):
            return True
    return False


def problems(g: Graph, where: Any) -> Any:
    found = []
    for pshape in sorted(set(g.objects(None, SH.property)), key=str):
        if not reported(g, pshape):
            continue
        path = g.value(pshape, SH.path)
        label = path.n3(g.namespace_manager) if path is not None else str(pshape)
        owners = ", ".join(sorted(o.n3(g.namespace_manager) for o in g.subjects(SH.property, pshape)))
        messages = list(g.objects(pshape, SH.message))
        if not messages:
            found.append(f"{where}: the property shape on {label} of {owners} has no sh:message")
        for message in messages:
            if PLACEHOLDER.search(str(message)):
                found.append(
                    f"{where}: the property shape on {label} of {owners} prints a SPARQL placeholder: {message}"
                )
    return found


def self_test() -> None:
    g = Graph().parse(
        format="turtle",
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <urn:ex:> .
        ex:S a sh:NodeShape ; sh:targetClass ex:C ;
            sh:property [ sh:path ex:a ; sh:minCount 1 ] ;
            sh:property [ sh:path ex:b ; sh:minCount 1 ; sh:message "ex:b is required." ] ;
            sh:property [ sh:path ex:c ; sh:maxCount 1 ; sh:message "{?value} is one too many." ] ;
            sh:not [ sh:property [ sh:path ex:d ; sh:minCount 1 ] ] .""",
    )
    found = problems(g, "probe")
    assert len(found) == 2 and "ex:a" in found[0] + found[1] and "placeholder" in found[0] + found[1], found
    negation_self_test()


def negation_self_test() -> None:
    """sh:not of a conjunction forbids the conjuncts together; one conjunct is simply negated."""
    from _shape_text import value_phrase

    g = Graph().parse(
        format="turtle",
        data="""
        @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <urn:ex:> .
        ex:Two sh:not [ sh:class ex:Custom ; sh:in ( ex:a ex:b ex:c ) ] .
        ex:One sh:nodeKind sh:IRI ; sh:not [ sh:class ex:Field ] .
        ex:Three sh:not [ sh:class ex:C ; sh:in ( ex:a ex:b ) ; sh:minLength 2 ] .""",
    )
    prefixes = {"ex": "urn:ex:"}
    ex = "urn:ex:"
    two = value_phrase(g, URIRef(ex + "Two"), prefixes)
    assert two == "not both an instance of ex:Custom and one of ex:a, ex:b or ex:c", two
    one = value_phrase(g, URIRef(ex + "One"), prefixes)
    assert one == "an IRI that is not an instance of ex:Field", one
    three = value_phrase(g, URIRef(ex + "Three"), prefixes)
    assert three.startswith("not all of an instance of ex:C, ") and three.endswith("and either ex:a or ex:b"), three


def main() -> int:
    self_test()
    files = canonical_files(ROOT / "specification")
    found, total = [], 0
    for rel in files:
        g = Graph().parse(data=(ROOT / "specification" / rel).read_text(encoding="utf-8"), format="turtle")
        total += sum(1 for p in set(g.objects(None, SH.property)) if reported(g, p))
        found += problems(g, rel)
    if found:
        print("FAIL: reported property shapes without a usable sh:message:\n  " + "\n  ".join(found))
        return 1
    print(f"PASS: all {total} reported property shapes in {len(files)} modules carry an sh:message")
    return 0


if __name__ == "__main__":
    sys.exit(main())
