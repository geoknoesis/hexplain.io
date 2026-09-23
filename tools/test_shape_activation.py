"""A shape activated by one property must also be activated by the others it constrains.

`sh:targetSubjectsOf adv:artist` selects only nodes that HAVE an artist, so every other
constraint in that shape silently applied to nothing when the artist was absent: `adv:album
42` on a tag without an artist validated. For each node shape targeting the subjects of a
property, every other property of the same module that the shape constrains must be a
target too (or the shape is scoped by class and the property is another module's, whose own
range shape then applies). Conditional-presence rules are exempt by construction: a property
shape whose only constraints are sh:minCount, sh:maxCount 0 or sh:hasValue states what the
TRIGGER implies, and must not fire on its own.
"""
import sys

from rdflib import Graph, Namespace, URIRef

import specgraph

SH = Namespace("http://www.w3.org/ns/shacl#")
NEUTRAL = {SH.path, SH.message, SH.severity, SH.name, SH.description, SH.order, SH.group}


def _conditional(g, pshape):
    """True when the property shape only states what the triggering property implies."""
    for p, o in g.predicate_objects(pshape):
        if p in NEUTRAL or p == SH.minCount or p == SH.hasValue:
            continue
        if p == SH.maxCount and int(o) == 0:
            continue
        return False
    return True


def _module(term):
    return str(term).rsplit("#", 1)[0]


def gaps(g):
    out = []
    for shape in sorted(set(g.subjects(SH.targetSubjectsOf, None))):
        targets = set(g.objects(shape, SH.targetSubjectsOf))
        modules = {_module(t) for t in targets} | {_module(shape)}
        for pshape in g.objects(shape, SH.property):
            path = g.value(pshape, SH.path)
            if not isinstance(path, URIRef) or path in targets or _conditional(g, pshape):
                continue
            if _module(path) in modules:
                out.append(f"{shape} constrains {path} but is not activated by it")
    return out


def main():
    self_test = Graph().parse(format="turtle", data="""
        @prefix ex: <https://example.org/m#> . @prefix sh: <http://www.w3.org/ns/shacl#> .
        ex:S sh:targetSubjectsOf ex:a ; sh:property [ sh:path ex:a ] , [ sh:path ex:b ; sh:maxCount 1 ] ,
             [ sh:path ex:c ; sh:minCount 1 ] , [ sh:path ex:d ; sh:maxCount 0 ] .""")
    found = gaps(self_test)
    assert found == ["https://example.org/m#S constrains https://example.org/m#b but is not activated by it"], found
    found = gaps(specgraph.ontologies())
    if found:
        print("FAIL: shapes whose constraints are bypassed when the triggering property is absent:\n  "
              + "\n  ".join(found))
        sys.exit(1)
    print("PASS: every subjects-of shape is activated by each same-module property it constrains")


if __name__ == "__main__":
    main()
