"""A shape activated by one property must also be activated by the others it constrains.

`sh:targetSubjectsOf adv:artist` selects only nodes that HAVE an artist, so every other
constraint in that shape silently applied to nothing when the artist was absent: `adv:album
42` on a tag without an artist validated. For each node shape targeting the subjects of a
property, every other property of the same module that the shape constrains must be a
target too (or the shape is scoped by class and the property is another module's, whose own
range shape then applies). Conditional-presence rules are exempt by construction: a property
shape whose only constraints are sh:minCount, sh:maxCount 0 or sh:hasValue states what the
TRIGGER implies, and must not fire on its own.

The same bypass exists for a shape targeted by class alone: omitting rdf:type from a node
skips every constraint of the shape. So every class-targeted shape must also be activated by
a property (sh:targetSubjectsOf / sh:targetObjectsOf) or appear in CLASS_ONLY below with the
reason property activation is not used. The list is a ratchet: a new class-only shape fails
the gate until it gains a property target or a stated reason.
"""
import sys

from rdflib import Graph, Namespace, URIRef

import specgraph

SH = Namespace("http://www.w3.org/ns/shacl#")
NEUTRAL = {SH.path, SH.message, SH.severity, SH.name, SH.description, SH.order, SH.group}

# (shape, property) pairs a subjects-of shape constrains without being activated by, because
# another class uses the same property and activating on it would apply this shape there.
SHARED = {
    ("https://hexplain.io/ns/conf#ConstraintShape", "https://hexplain.io/ns/conf#satisfies"):
        "conf:ParseAttribution also cites requirements with conf:satisfies",
    ("https://hexplain.io/ns/aspect/bundle#AssetShape", "https://hexplain.io/ns/aspect/bundle#hasPart"):
        "abnd:hasPart is also used outside assets (layout competency: unrelated hasPart stays out of scope)",
}

_BDDO_TYPED = ("a bddo description is read by a loader that selects structs, fields, data types and rules "
               "by their rdf:type, so an untyped node is not part of the description at all; the shape's "
               "properties (bddo:hasField, bddo:dataType, sizes, offsets) are shared by several of these "
               "classes, so property activation would apply the wrong shape")
_LAYOUT_TYPED = "DLV layout nodes and rules are selected by rdf:type through their owning list; the list members carry no distinguishing property"
CLASS_ONLY = {
    "https://hexplain.io/ns/archive#ArchiveShape": "an archive's properties are shared with generic packaging metadata",
    "https://hexplain.io/ns/aspect/bundle#LiftByCarriedAspectRule": "a SHACL rule, not a constraint: it derives facets only for typed assets",
    "https://hexplain.io/ns/aspect/bundle#RequiredPartsShape": "joins through dcterms:conformsTo, which non-asset resources also use",
    "https://hexplain.io/ns/aspect/raster#ArrayDimensionShape": "dimension properties are shared with DLV dimensions",
    "https://hexplain.io/ns/bddo#DisjointKindsShape": "it checks the types themselves: an untyped node has nothing to contradict",
    "https://hexplain.io/ns/conf#ParseAttributionTargetShape": "conf:errorCategory and conf:satisfies are shared with conf:Parse findings and constraints",
    "https://hexplain.io/ns/core#ClassMappingRuleShape": "hexplain:condition and hexplain:semanticClass are shared with mapping rules",
    "https://hexplain.io/ns/core#MappingRuleShape": "hexplain:condition is shared with class mapping rules",
    "https://hexplain.io/ns/fn#NativeFunctionShape": "function descriptions are published by this family only, always typed hxf:Function",
    "https://hexplain.io/ns/geo#VectorShape": "vector-dataset properties are shared with the geometry aspect",
    "https://hexplain.io/ns/image#ImageShape": "image-header properties are shared with the raster aspect",
}
for _local in ["AsciiNumericWidthShape", "DataTypeRuleShape", "DataTypeShape", "DelimitedRecordsShape",
               "DelimitedTableShape", "DerivedFieldShape", "DispatchKeyUniquenessShape", "DispatchTableShape",
               "EndiannessRuleShape", "EnumValueShape", "EnumerationShape", "FieldOffsetShape",
               "FieldRepetitionShape", "FieldShape", "FieldSizingShape", "GroupedRecordsShape", "KeyPathShape",
               "KeyValueHeaderShape", "RecordGroupingShape", "SeekScopeShape", "StructShape", "StructSizingShape",
               "TreeDocumentShape", "TypeSelectionExclusivityShape", "VariableLengthFieldShape", "VarintWidthShape"]:
    CLASS_ONLY["https://hexplain.io/ns/bddo#" + _local] = _BDDO_TYPED
for _local in ["CellDataTypeRuleShape", "ChunkedLayoutShape", "DataLayoutShape", "DimensionOrderRuleShape",
               "DimensionShape"]:
    CLASS_ONLY["https://hexplain.io/ns/dlv#" + _local] = _LAYOUT_TYPED
PROPERTY_TARGETS = (SH.targetSubjectsOf, SH.targetObjectsOf, SH.target, SH.targetNode)


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
            if (str(shape), str(path)) in SHARED:
                continue
            if _module(path) in modules:
                out.append(f"{shape} constrains {path} but is not activated by it")
    return out


def class_only(g):
    """Class-targeted shapes with no property activation and no stated reason, and stale reasons."""
    out = []
    only = {s for s in set(g.subjects(SH.targetClass, None))
            if not any((s, p, None) in g for p in PROPERTY_TARGETS)}
    for shape in sorted(only):
        if str(shape) not in CLASS_ONLY:
            out.append(f"{shape} is activated only by sh:targetClass; omitting rdf:type bypasses it")
    for name in sorted(set(CLASS_ONLY) - {str(s) for s in only}):
        out.append(f"CLASS_ONLY lists {name}, which is no longer class-only (remove the entry)")
    return out


def main():
    self_test = Graph().parse(format="turtle", data="""
        @prefix ex: <https://example.org/m#> . @prefix sh: <http://www.w3.org/ns/shacl#> .
        ex:S sh:targetSubjectsOf ex:a ; sh:property [ sh:path ex:a ] , [ sh:path ex:b ; sh:maxCount 1 ] ,
             [ sh:path ex:c ; sh:minCount 1 ] , [ sh:path ex:d ; sh:maxCount 0 ] .""")
    found = gaps(self_test)
    assert found == ["https://example.org/m#S constrains https://example.org/m#b but is not activated by it"], found
    family = specgraph.ontologies()
    found = gaps(family) + class_only(family)
    if found:
        print("FAIL: shapes whose constraints are bypassed when the triggering property is absent:\n  "
              + "\n  ".join(found))
        sys.exit(1)
    print(f"PASS: every subjects-of shape is activated by each same-module property it constrains; "
          f"{len(CLASS_ONLY)} class-only shapes state why property activation is not used")


if __name__ == "__main__":
    main()
