"""An optional strict profile: a closed shape per description class, and a term lint of engine profiles.

The family's shapes are open, as SHACL shapes normally are: a Field may carry any extra
property. That is the right default for the specification, and the wrong one for a profile
author who wants to know that `bddo:sizeFromFeild`, an aspect property put directly on a Field
instead of behind hexplain:mapsToProperty, or a Field's `bddo:dataType` written on a Struct, is
not doing anything. The strict profile, specification/validation/test/strict-profile-shapes.ttl,
closes each class of the physical, core and layout vocabularies (bddo:Field, bddo:Struct,
bddo:DataType, bddo:TreeDocument, bddo:KeyValueHeader, bddo:DelimitedTable, dlv:Dimension, ...)
over ITS OWN properties plus the documentation annotations -- not over one union of every
property -- so a property is accepted only on the classes the family's shapes apply it to.

A class's properties are read from the family's shapes: the paths of the property shapes of a
node shape that targets the class (or restricts its focus nodes to it with sh:class), at the
node level only, the properties such a shape targets the subjects of, and those of its
superclasses. EXTRA lists the few properties no shape constrains yet, with the class they
belong to. Each closed shape is activated by its class AND by the subjects of the properties
only that class (and its sub- or superclasses) uses, so omitting rdf:type does not bypass it.
A node of a subclass (a bddo:TreeDocument is a bddo:Struct) is checked by the subclass's shape,
not closed again over the superclass's smaller set. The file is generated (run with --write after
adding a property) and is NOT part of the family: a processor applies it only when asked to.

When HEXPLAIN_TOOLS names a checkout of the reference engine, every Turtle file under it (outside
build directories) that describes a format -- one that uses the bddo namespace, found by its
content, not its file name -- is also linted, read-only: every Hexplain term it uses must be
defined by the family (as tools/test_known_terms.py does for this repository's data), and it must
conform to the strict profile. Without HEXPLAIN_TOOLS that part is not run, and the gate says so;
it does not report SKIP, because the strict profile's own checks still run.
"""
import os
import sys
from collections import defaultdict
from pathlib import Path

from pyshacl import validate
from rdflib import OWL, RDF, RDFS, BNode, Graph, Namespace, URIRef
from rdflib.collection import Collection

import specgraph
from test_known_terms import owned_namespaces, unknown_terms

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "specification/validation/test/strict-profile-shapes.ttl"
SH = Namespace("http://www.w3.org/ns/shacl#")
BDDO = "https://hexplain.io/ns/bddo#"
CORE = "https://hexplain.io/ns/core#"
DLV = "https://hexplain.io/ns/dlv#"
NAMESPACES = [BDDO, CORE, DLV]
ANNOTATIONS = [RDF.type, RDFS.label, RDFS.comment, RDFS.seeAlso, RDFS.isDefinedBy, OWL.deprecated,
               URIRef("http://www.w3.org/2004/02/skos/core#definition"),
               URIRef("http://www.w3.org/2004/02/skos/core#scopeNote"),
               URIRef("http://www.w3.org/2004/02/skos/core#note"),
               URIRef("http://www.w3.org/2004/02/skos/core#editorialNote"),
               URIRef("http://www.w3.org/2004/02/skos/core#historyNote"),
               URIRef("http://www.w3.org/2004/02/skos/core#changeNote"),
               URIRef("http://purl.org/dc/terms/description"), URIRef("http://purl.org/dc/terms/source")]
PREFIX = "https://hexplain.io/ns/validation/strict#"
# Properties no family shape constrains on a class yet, with the class the vocabulary text puts
# them on. Every entry is a property the physical or core vocabulary defines for that class.
EXTRA = {
    BDDO + "Field": ["endianness", "hasConditionalEndianness", "hasEndianness", "hasFixedValue", "numericBase",
                     "repeatCount", "repeatCountFromExpression", "repeatCountFromField", "repeatUntil",
                     "keyIsCaseInsensitive", CORE + "isEncodedWith", CORE + "hasEncodingStep"],
    BDDO + "Struct": ["hasConditionalEndianness", "hasEndianness", "usesStruct"],
    BDDO + "KeyValueHeader": ["keyIsCaseInsensitive"],
    CORE + "RegisterBinding": [CORE + "forProperty", CORE + "register"],
}


def _iri(name, default=BDDO):
    return URIRef(name if name.startswith("https://") else default + name)


def _node_level(g, shape):
    """The shape and the shapes its logical combinators name, without entering property shapes."""
    out, stack = [], [shape]
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


def _paths(g, shape):
    found = set()
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


def _focus_classes(g, shape):
    classes = set(g.objects(shape, SH.targetClass))
    for node in _node_level(g, shape):
        classes |= set(g.objects(node, SH["class"]))
    return classes


def vocabulary(family):
    """(properties, class -> own properties, class -> superclasses, class -> subclasses)."""
    props = {p for t in (RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)
             for p in family.subjects(RDF.type, t) if any(str(p).startswith(n) for n in NAMESPACES)}
    own = defaultdict(set)
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
    for cls, names in EXTRA.items():
        own[URIRef(cls)] |= {_iri(n) for n in names}
    missing = {p for names in EXTRA.values() for p in map(_iri, names)} - props
    assert not missing, f"EXTRA names properties the family does not define: {sorted(missing)}"
    supers = {c: set(family.transitive_objects(c, RDFS.subClassOf)) - {c} for c in own}
    subs = {c: {d for d in own if c in supers[d]} for c in own}
    return props, own, supers, subs


def allowed(own, supers, cls):
    return set(own[cls]).union(*(own.get(s, set()) for s in supers[cls]))


def characteristic(own, supers, subs, cls):
    """Properties of the class that no class outside its own line of descent uses."""
    line = {cls} | supers[cls] | subs[cls]
    others = set().union(*(allowed(own, supers, d) for d in own if d not in line))
    return sorted(allowed(own, supers, cls) - others, key=str)


def render(family):
    props, own, supers, subs = vocabulary(family)
    out = ["# Generated by tools/test_strict_profile.py --write from the specification family. Do not edit.",
           "# An OPTIONAL strict profile: each class of the physical, core and layout vocabularies is closed",
           "# over its own properties (read from the family's shapes) plus documentation annotations. It is not",
           "# part of the family; apply it only to catch misspelt or misplaced properties in a profile.",
           "@prefix sh: <http://www.w3.org/ns/shacl#> .",
           f"@prefix strict: <{PREFIX}> .", ""]
    for cls in sorted(own, key=str):
        ns, local = str(cls).rsplit("#", 1)
        prefix = {BDDO: "bddo", CORE: "hexplain", DLV: "dlv"}[ns + "#"]
        names = sorted(allowed(own, supers, cls), key=str) + ANNOTATIONS
        targets = characteristic(own, supers, subs, cls)
        closed = ("[ sh:closed true ;\n          sh:ignoredProperties (\n            " +
                  "\n            ".join(p.n3() for p in names) + "\n          ) ]")
        # A node of a subclass, or one using a property only a subclass has, is left to that
        # subclass's own closed shape.
        escapes = [f"[ sh:class {s.n3()} ]" for s in sorted(subs[cls], key=str)]
        extra = sorted(set().union(*(allowed(own, supers, s) for s in subs[cls])) - allowed(own, supers, cls), key=str)
        # An UNTYPED node using a subclass's own property is that subclass's; a node typed with
        # this class itself is not, and is closed here.
        escapes += [f"[ sh:not [ sh:class {cls.n3()} ] ; sh:property [ sh:path {p.n3()} ; sh:minCount 1 ] ]" for p in extra]
        out += [f"strict:Closed{local}Shape a sh:NodeShape ;",
                f"    sh:targetClass {cls.n3()} ;"]
        if targets:
            out.append("    sh:targetSubjectsOf " + " ,\n        ".join(p.n3() for p in targets) + " ;")
        out.append(f"    sh:message \"A {prefix}:{local} carries only the properties the family's shapes apply to it and "
                   "documentation annotations; map a semantic property with hexplain:mapsToProperty.\" ;")
        if escapes:
            out.append("    sh:or ( " + "\n            ".join(escapes + [closed]) + " ) .")
        else:
            out.append("    sh:closed true ;\n    sh:ignoredProperties (\n        " +
                       "\n        ".join(p.n3() for p in names) + "\n    ) .")
        out.append("")
    return "\n".join(out)


SKIPPED_DIRS = {"build", "build-root", ".gradle", "node_modules", "out", ".git"}


def _tracked(root):
    """The Turtle files git tracks under [root], or every one when it is not a git checkout."""
    import subprocess
    try:
        listed = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "*.ttl"], capture_output=True,
                                check=True).stdout.decode("utf-8").split("\x00")
        return sorted(root / name for name in listed if name)
    except (OSError, subprocess.CalledProcessError):
        return sorted(root.rglob("*.ttl"))


def engine_profiles(root, family_ontologies):
    """Every tracked Turtle file of the engine checkout that describes a format, parsed.

    Found by content, not by name: a file that uses the bddo namespace describes a format, whatever
    it is called (core/src/test/resources/nitf/nitf.ttl is one). A copy of a family module (a file
    that declares one of the family's ontologies, as the engine's bundled bddo.ttl does) is the
    vocabulary, not a description of a format, and is left to the family's own gates.
    """
    for path in _tracked(root):
        if set(path.parts) & SKIPPED_DIRS or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if BDDO not in text:
            continue
        try:
            g = Graph().parse(data=text, format="turtle")
        except Exception as exc:  # a profile that is not Turtle is the engine's concern
            yield path, exc
            continue
        if set(g.subjects(RDF.type, OWL.Ontology)) & family_ontologies:
            continue
        yield path, g


def main():
    family = specgraph.ontologies()
    expected = render(family)
    if "--write" in sys.argv:
        TARGET.write_text(expected, encoding="utf-8", newline="\n")
    if TARGET.read_text(encoding="utf-8") != expected:
        print("FAIL: strict-profile-shapes.ttl is stale; run python tools/test_strict_profile.py --write")
        sys.exit(1)
    strict = Graph().parse(data=expected, format="turtle")
    shapes = set(strict.subjects(RDF.type, SH.NodeShape))
    probe = Graph().parse(format="turtle", data="""@prefix bddo: <https://hexplain.io/ns/bddo#> .
        @prefix araster: <https://hexplain.io/ns/aspect/raster#> .
        <urn:f> a bddo:Field ; bddo:dataType bddo:uint8 ; araster:width 3 .
        <urn:g> a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:size 1 .
        <urn:s> a bddo:Struct ; bddo:hasField ( <urn:g> ) ; bddo:dataType bddo:uint8 .
        <urn:t> a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ) .""")
    ok, report, _ = validate(probe, shacl_graph=strict, inference="none")
    focus = set(report.objects(None, SH.focusNode))
    assert not ok and focus == {URIRef("urn:f"), URIRef("urn:s")}, \
        f"the strict profile must reject an aspect property on a Field and a Field property on a Struct, and accept the rest: {focus}"
    failures = []
    engine = os.environ.get("HEXPLAIN_TOOLS")
    checked = 0
    if engine:
        root = Path(engine)
        if not root.is_dir():
            print(f"FAIL: HEXPLAIN_TOOLS={engine} is not a directory")
            sys.exit(1)
        known = set(family.subjects())
        namespaces = owned_namespaces(family)
        for path, g in engine_profiles(root, set(family.subjects(RDF.type, OWL.Ontology))):
            if isinstance(g, Exception):
                failures.append(f"{path}: does not parse ({g.__class__.__name__})")
                continue
            checked += 1
            for iri in unknown_terms(g, known, namespaces):
                failures.append(f"{path}: {iri} is not defined by any family module")
            conforms, _, detail = validate(g, shacl_graph=strict, inference="none")
            if not conforms:
                failures.append(f"{path}: does not conform to the strict profile:\n{detail[:1500]}")
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    tail = (f"; {checked} engine format descriptions under HEXPLAIN_TOOLS use only family terms and conform to it"
            if engine else "; engine profiles not linted (set HEXPLAIN_TOOLS to an engine checkout to lint them)")
    print(f"PASS: strict profile closes {len(shapes)} classes, each over its own properties, and is current{tail}")


if __name__ == "__main__":
    main()
