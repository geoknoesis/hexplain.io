"""Which SHACL constraints enforce each XSD rdfs:range, shared by the gate and its fixtures.

An rdfs:range of xsd:positiveInteger says what a value IS, but a validator only rejects
`bddo:size 3.5` if some activated shape states a datatype. This module answers, for every
datatype property with an XSD range, whether a shape targeting the subjects of that property
constrains its values to a compatible datatype -- activation by subjects-of, so the check
does not depend on the subject having been typed.
"""
from rdflib import RDFS, Namespace, URIRef
from rdflib.collection import Collection

SH = Namespace("http://www.w3.org/ns/shacl#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")

# The integer family Turtle and the engine actually emit: a bare `3` is xsd:integer, while
# lifted wire values keep their sized datatype. A positive/non-negative range is then a
# numeric bound, not a demand for the exact derived datatype.
INTEGERS = frozenset(XSD[n] for n in (
    "integer", "nonNegativeInteger", "positiveInteger", "nonPositiveInteger", "negativeInteger",
    "int", "long", "short", "byte", "unsignedLong", "unsignedInt", "unsignedShort", "unsignedByte"))


def compatible(range_):
    """Datatypes a literal may carry and still be a value of `range_`."""
    if range_ in INTEGERS:
        return INTEGERS
    if range_ == XSD.decimal:
        return INTEGERS | {XSD.decimal}
    if range_ in (XSD.double, XSD.float):
        return frozenset({XSD.double, XSD.float})
    return frozenset({range_})


def _members(g, node):
    return list(Collection(g, node)) if node is not None else []


def allowed_datatypes(g, shape, seen=frozenset()):
    """The datatypes a shape admits, or None when it does not constrain the datatype."""
    if shape in seen:
        return None
    seen = seen | {shape}
    found = []
    direct = set(g.objects(shape, SH.datatype))
    if direct:
        found.append(frozenset(direct))
    for node in g.objects(shape, SH.node):
        sub = allowed_datatypes(g, node, seen)
        if sub is not None:
            found.append(sub)
    for alt in (SH["or"], SH.xone):
        for lst in g.objects(shape, alt):
            branches = [allowed_datatypes(g, m, seen) for m in _members(g, lst)]
            if branches and all(b is not None for b in branches):
                found.append(frozenset().union(*branches))
    for lst in g.objects(shape, SH["and"]):
        for m in _members(g, lst):
            sub = allowed_datatypes(g, m, seen)
            if sub is not None:
                found.append(sub)
    if not found:
        return None
    result = found[0]
    for other in found[1:]:
        result = result & other
    return result


def xsd_ranged(g):
    """(property, range) for every property whose rdfs:range is an XSD datatype."""
    return sorted((p, r) for p, r in g.subject_objects(RDFS.range)
                  if isinstance(r, URIRef) and str(r).startswith(str(XSD)))


def problems(g):
    """Human-readable gaps; empty when every XSD range is enforced where the property is used."""
    out = []
    for prop, range_ in xsd_ranged(g):
        ok = compatible(range_)
        enforced = False
        for pshape in g.subjects(SH.path, prop):
            admitted = allowed_datatypes(g, pshape)
            if admitted is None:
                continue
            if not admitted <= ok:
                out.append(f"{prop}: a shape admits {sorted(map(str, admitted - ok))}, "
                           f"incompatible with rdfs:range {range_}")
                continue
            owners = set(g.subjects(SH.property, pshape))
            if any((owner, SH.targetSubjectsOf, prop) in g for owner in owners):
                enforced = True
        if not enforced:
            out.append(f"{prop}: rdfs:range {range_} but no shape targeting its subjects "
                       f"constrains its datatype")
    return out
