"""Write or check the optional strict profile, specification/validation/test/strict-profile-shapes.ttl.

The profile closes each class of the physical, core and layout vocabularies (bddo:Field,
bddo:Struct, bddo:DataType, bddo:TreeDocument, bddo:KeyValueHeader, bddo:DelimitedTable,
dlv:Dimension, ...) over ITS OWN properties plus the documentation annotations -- not over one
union of every property -- so a property is accepted only on the classes the family's shapes
apply it to.

A class's properties are read from the family's shapes: the paths of the property shapes of a
node shape that targets the class (or restricts its focus nodes to it with sh:class), at the
node level only, the properties such a shape targets the subjects of, and those of its
superclasses. EXTRA lists the few properties no shape constrains yet, with the class they
belong to. Each closed shape is activated by its class AND by the subjects of the properties
only that class (and its sub- or superclasses) uses, so omitting rdf:type does not bypass it.
A node of a subclass (a bddo:TreeDocument is a bddo:Struct) is checked by the subclass's shape,
not closed again over the superclass's smaller set.

``--write`` regenerates the file (after adding a property); ``--check`` exits 1 when it is not
byte-for-byte what the family renders to. The gate ``tools/test_strict_profile.py`` checks the
same, probes the profile and lints engine profiles; it writes nothing.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import specgraph
from rdflib import OWL, RDF, RDFS, BNode, Graph, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.term import Node

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "specification/validation/test/strict-profile-shapes.ttl"
SH = Namespace("http://www.w3.org/ns/shacl#")
BDDO = "https://hexplain.io/ns/bddo#"
CORE = "https://hexplain.io/ns/core#"
DLV = "https://hexplain.io/ns/dlv#"
NAMESPACES = [BDDO, CORE, DLV]
ANNOTATIONS = [
    RDF.type,
    RDFS.label,
    RDFS.comment,
    RDFS.seeAlso,
    RDFS.isDefinedBy,
    OWL.deprecated,
    URIRef("http://www.w3.org/2004/02/skos/core#definition"),
    URIRef("http://www.w3.org/2004/02/skos/core#scopeNote"),
    URIRef("http://www.w3.org/2004/02/skos/core#note"),
    URIRef("http://www.w3.org/2004/02/skos/core#editorialNote"),
    URIRef("http://www.w3.org/2004/02/skos/core#historyNote"),
    URIRef("http://www.w3.org/2004/02/skos/core#changeNote"),
    URIRef("http://purl.org/dc/terms/description"),
    URIRef("http://purl.org/dc/terms/source"),
]
PREFIX = "https://hexplain.io/ns/validation/strict#"
# Properties no family shape constrains on a class yet, with the class the vocabulary text puts
# them on. Every entry is a property the physical or core vocabulary defines for that class.
EXTRA = {
    BDDO + "Field": [
        "endianness",
        "hasConditionalEndianness",
        "hasEndianness",
        "hasFixedValue",
        "numericBase",
        "repeatCount",
        "repeatCountFromExpression",
        "repeatCountFromField",
        "repeatUntil",
        "keyIsCaseInsensitive",
        CORE + "isEncodedWith",
        CORE + "hasEncodingStep",
        "hasArgument",
    ],
    BDDO + "Struct": ["hasConditionalEndianness", "hasEndianness", "usesStruct", "hasParameter"],
    # bddo:ArgumentListShape and bddo:ParameterisedStructShape target the subjects of the property,
    # not a class, so the classes the vocabulary text puts them on are named here.
    BDDO + "DataTypeRule": ["hasArgument"],
    BDDO + "DispatchArm": ["hasArgument"],
    BDDO + "KeyValueHeader": ["keyIsCaseInsensitive"],
    CORE + "RegisterBinding": [CORE + "forProperty", CORE + "register"],
    # hexplain:CodecSelectionShape targets the subjects of hexplain:codecFromExpression and
    # hexplain:codecCandidates, not a class; both are properties of hexplain:EncodingStep.
    CORE + "EncodingStep": [CORE + "codecCandidates"],
}


def _iri(name: str, default: str = BDDO) -> URIRef:
    return URIRef(name if name.startswith("https://") else default + name)


def _node_level(g: Graph, shape: Node) -> list[Node]:
    """The shape and the shapes its logical combinators name, without entering property shapes."""
    out: list[Node] = []
    stack: list[Node] = [shape]
    while stack:
        node = stack.pop()
        if node in out:
            continue
        out.append(node)
        for combinator in (SH["or"], SH["and"], SH.xone):
            for head in g.objects(node, combinator):
                stack.extend(Collection(g, head))
        stack.extend(g.objects(node, SH["not"]))
    return out


def _paths(g: Graph, shape: Node) -> set[Node]:
    found: set[Node] = set()
    for node in _node_level(g, shape):
        for pshape in g.objects(node, SH.property):
            path = g.value(pshape, SH.path)
            if isinstance(path, URIRef):
                found.add(path)
            elif isinstance(path, BNode) and (path, RDF.first, None) in g:
                first = next(iter(Collection(g, path)), None)
                if isinstance(first, URIRef):
                    found.add(first)
    return found


def _focus_classes(g: Graph, shape: Node) -> set[Node]:
    classes = set(g.objects(shape, SH.targetClass))
    for node in _node_level(g, shape):
        classes |= set(g.objects(node, SH["class"]))
    return classes


#: class -> a set of properties or of related classes.
ClassSets = dict[Node, set[Node]]


def vocabulary(family: Graph) -> tuple[set[Node], ClassSets, ClassSets, ClassSets]:
    """(properties, class -> own properties, class -> superclasses, class -> subclasses)."""
    props = {
        p
        for t in (RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
        for p in family.subjects(RDF.type, t)
        if any(str(p).startswith(n) for n in NAMESPACES)
    }
    own: defaultdict[Node, set[Node]] = defaultdict(set)
    for shape in set(family.subjects(RDF.type, SH.NodeShape)):
        used = (_paths(family, shape) | set(family.objects(shape, SH.targetSubjectsOf))) & props
        for cls in _focus_classes(family, shape):
            if any(str(cls).startswith(n) for n in NAMESPACES):
                own[cls] |= used
    # What the family's own instances of a class carry (bddo's primitive data types state
    # bddo:encoding) is a property of that class too.
    for cls in list(own):
        for instance in family.subjects(RDF.type, cls):
            own[cls] |= set(family.predicates(instance, None)) & props
    for extra_class, names in EXTRA.items():
        own[URIRef(extra_class)] |= {_iri(n) for n in names}
    missing = {p for names in EXTRA.values() for p in map(_iri, names)} - props
    assert not missing, f"EXTRA names properties the family does not define: {sorted(missing)}"
    supers = {c: {s for s in family.transitive_objects(c, RDFS.subClassOf) if s is not None} - {c} for c in own}
    subs = {c: {d for d in own if c in supers[d]} for c in own}
    return props, own, supers, subs


def allowed(own: ClassSets, supers: ClassSets, cls: Node) -> set[Node]:
    """The properties a class accepts: its own plus those of its superclasses."""
    return set(own[cls]).union(*(own.get(s, set()) for s in supers[cls]))


def characteristic(own: ClassSets, supers: ClassSets, subs: ClassSets, cls: Node) -> list[Node]:
    """Properties of the class that no class outside its own line of descent uses."""
    line = {cls} | supers[cls] | subs[cls]
    others = set().union(*(allowed(own, supers, d) for d in own if d not in line))
    return sorted(allowed(own, supers, cls) - others, key=str)


def render(family: Graph) -> str:
    props, own, supers, subs = vocabulary(family)
    out = [
        "# Generated by python tools/_build_strict_profile.py --write from the specification family. Do not edit.",
        "# An OPTIONAL strict profile: each class of the physical, core and layout vocabularies is closed",
        "# over its own properties (read from the family's shapes) plus documentation annotations. It is not",
        "# part of the family; apply it only to catch misspelt or misplaced properties in a profile.",
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        f"@prefix strict: <{PREFIX}> .",
        "",
    ]
    for cls in sorted(own, key=str):
        ns, local = str(cls).rsplit("#", 1)
        prefix = {BDDO: "bddo", CORE: "hexplain", DLV: "dlv"}[ns + "#"]
        names = sorted(allowed(own, supers, cls), key=str) + ANNOTATIONS
        targets = characteristic(own, supers, subs, cls)
        closed = (
            "[ sh:closed true ;\n          sh:ignoredProperties (\n            "
            + "\n            ".join(p.n3() for p in names)
            + "\n          ) ]"
        )
        # A node of a subclass, or one using a property only a subclass has, is left to that
        # subclass's own closed shape.
        escapes = [f"[ sh:class {s.n3()} ]" for s in sorted(subs[cls], key=str)]
        extra = sorted(set().union(*(allowed(own, supers, s) for s in subs[cls])) - allowed(own, supers, cls), key=str)
        # An UNTYPED node using a subclass's own property is that subclass's; a node typed with
        # this class itself is not, and is closed here.
        escapes += [
            f"[ sh:not [ sh:class {cls.n3()} ] ; sh:property [ sh:path {p.n3()} ; sh:minCount 1 ] ]" for p in extra
        ]
        out += [f"strict:Closed{local}Shape a sh:NodeShape ;", f"    sh:targetClass {cls.n3()} ;"]
        if targets:
            out.append("    sh:targetSubjectsOf " + " ,\n        ".join(p.n3() for p in targets) + " ;")
        out.append(
            f"    sh:message \"A {prefix}:{local} carries only the properties the family's shapes apply to it and "
            'documentation annotations; map a semantic property with hexplain:mapsToProperty." ;'
        )
        if escapes:
            out.append("    sh:or ( " + "\n            ".join(escapes + [closed]) + " ) .")
        else:
            out.append(
                "    sh:closed true ;\n    sh:ignoredProperties (\n        "
                + "\n        ".join(p.n3() for p in names)
                + "\n    ) ."
            )
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate the strict profile from the family")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the profile is not what --write produces")
    args = parser.parse_args(argv)
    expected = render(specgraph.ontologies())
    relative = TARGET.relative_to(ROOT).as_posix()
    if args.write:
        TARGET.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {relative}")
        return 0
    if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != expected:
        print(f"STALE: {relative} is not what the family renders to; run this builder with --write")
        return 1
    print(f"CURRENT: {relative} is what the family renders to")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
