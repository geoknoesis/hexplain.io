"""Range contracts: every XSD rdfs:range, both ways, wherever the property is used.

Expectations come from the ontology's rdfs:range axioms and the XSD value spaces, not from the
shapes: a value of the range's datatype family inside its bounds must conform, and a value of
an unrelated datatype, one below the lower bound or one above the upper bound must not. The
shapes are consulted only to route each case to the module file whose shape activates it.
Each case is a single triple on an otherwise empty subject, so it also proves that activation
does not depend on the subject's type.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from _cases import row
from _family import canonical_files
from rdflib import RDFS, Graph, URIRef
from rdflib.term import Node

ROOT = Path(__file__).resolve().parents[1]
XSD = "http://www.w3.org/2001/XMLSchema#"
FAMILY = [
    "integer",
    "positiveInteger",
    "nonNegativeInteger",
    "int",
    "long",
    "unsignedInt",
    "unsignedLong",
    "short",
    "unsignedShort",
    "byte",
    "unsignedByte",
]
INTEGER_RANGES = set(FAMILY) | {"negativeInteger", "nonPositiveInteger"}
BOUNDS = {
    "positiveInteger": (1, None),
    "nonNegativeInteger": (0, None),
    "negativeInteger": (None, -1),
    "nonPositiveInteger": (None, 0),
    "unsignedLong": (0, 18446744073709551615),
    "unsignedInt": (0, 4294967295),
    "unsignedShort": (0, 65535),
    "unsignedByte": (0, 255),
    "long": (-9223372036854775808, 9223372036854775807),
    "int": (-2147483648, 2147483647),
    "short": (-32768, 32767),
    "byte": (-128, 127),
}
# A conforming value and a value of an unrelated datatype, per non-integer range.
LITERALS = {
    "decimal": ("1.5", '"1.5"'),
    "double": (f'"1.5"^^<{XSD}double>', "1.5"),
    "float": (f'"1.5"^^<{XSD}float>', "1.5"),
    "string": ('"text"', "1"),
    "boolean": ("true", '"true"'),
    "hexBinary": (f'"00"^^<{XSD}hexBinary>', '"00"'),
    "dateTime": (f'"2026-09-08T00:00:00Z"^^<{XSD}dateTime>', '"2026-09-08"'),
    "date": (f'"2026-09-08"^^<{XSD}date>', f'"2026-09-08T00:00:00Z"^^<{XSD}dateTime>'),
    "anyURI": (f'"https://example.org/"^^<{XSD}anyURI>', "1"),
    "language": (f'"en"^^<{XSD}language>', "1"),
}
SUBJECT = "<urn:range-contract:f>"
#: Conforming values of the non-XSD members of a union range.
UNION_LITERALS = {
    "http://www.opengis.net/ont/geosparql#wktLiteral": '"POINT(1 2)"^^<http://www.opengis.net/ont/geosparql#wktLiteral>',
}


#: ``add(name, module, property, value, expected)``: record one single-triple case.
Add = Callable[[str, str, Node, object, bool], None]


def _routes() -> tuple[dict[Node, str], set[tuple[Node | None, str]]]:
    """property -> module file whose subjects-of shape states its datatype."""
    from _range_datatypes import SH, allowed_datatypes

    files = canonical_files(ROOT / "specification")
    routes: dict[Node, str] = {}
    narrowed: set[tuple[Node | None, str]] = set()
    for rel in files:
        g = Graph().parse(data=(ROOT / "specification" / rel).read_text(encoding="utf-8"), format="turtle")
        for shape, prop in g.subject_objects(SH.targetSubjectsOf):
            # Only the range shapes: properties that other shapes also constrain are witnessed by
            # those shapes' own authored cases, and may legitimately narrow the range further.
            if not str(shape).endswith("#RangeDatatypeShape"):
                continue
            for pshape in g.objects(shape, SH.property):
                if g.value(pshape, SH.path) == prop and allowed_datatypes(g, pshape) is not None:
                    routes.setdefault(prop, "specification/" + rel)
        # A property another shape restricts to particular values or datatypes may be narrower
        # than its range (bddo:numericBase is one of 8, 10 or 16): the range's rejections still
        # hold for it, but an arbitrary in-range value is not necessarily accepted.
        narrowing = [
            SH[c] for c in ("in", "hasValue", "datatype", "or", "xone", "and", "node", "class", "pattern", "not")
        ]
        # Only this file's shapes matter: a case is validated against its module alone.
        for pshape in set(g.objects(None, SH.property)):
            if any(str(o).endswith("#RangeDatatypeShape") for o in g.subjects(SH.property, pshape)):
                continue
            if any((pshape, c, None) in g for c in narrowing):
                narrowed.add((g.value(pshape, SH.path), "specification/" + rel))
    return routes, narrowed


def _union_cases(g: Graph, add: Add, label: str, module: str, prop: Node, members: list[Node]) -> None:
    """A union range: a value of each member conforms, a value of none does not."""
    names = [str(m)[len(XSD) :] if str(m).startswith(XSD) else str(m) for m in members]
    for name in names:
        good = LITERALS[name][0] if name in LITERALS else UNION_LITERALS[name]
        add(
            f"{label} accepts "
            f"{g.namespace_manager.normalizeUri(URIRef(XSD + name) if name in LITERALS else URIRef(name))}",
            module,
            prop,
            good,
            True,
        )
    # The first member's usual counter-example (a decimal for xsd:double), which no member admits.
    add(
        f"{label} rejects another datatype",
        module,
        prop,
        LITERALS[names[0]][1] if names[0] in LITERALS else "1",
        False,
    )


def _integer_cases(add: Add, label: str, module: str, prop: Node, kind: str) -> bool:
    """An integer range: in-range, wrong-kind and out-of-bounds values; True when 1 lies in the range."""
    low, high = BOUNDS.get(kind, (None, None))
    admits_one = (low is None or low <= 1) and (high is None or high >= 1)
    add(f"{label} accepts an integer", module, prop, 1 if admits_one else low, True)
    add(f"{label} rejects a string", module, prop, '"x"', False)
    add(f"{label} rejects a decimal", module, prop, "1.5", False)
    if low is not None:
        add(f"{label} rejects {low - 1}", module, prop, low - 1, False)
    if high is not None:
        add(f"{label} rejects {high + 1}", module, prop, high + 1, False)
    return admits_one


def _literal_cases(add: Add, label: str, module: str, prop: Node, kind: str) -> bool:
    """A non-integer range: its own datatype and an unrelated one; True when integers are values of it."""
    good, bad = LITERALS[kind]
    add(f"{label} accepts xsd:{kind}", module, prop, good, True)
    add(f"{label} rejects another datatype", module, prop, bad, False)
    if kind != "decimal":
        return False
    add(f"{label} accepts an integer", module, prop, 2, True)
    return True


def cases() -> list[dict[str, Any]]:
    """Every range case, property by property in the order of the ontology's rdfs:range axioms."""
    import specgraph

    g = specgraph.ontologies()
    routes, narrowed = _routes()
    rows: list[dict[str, Any]] = []

    def add(name: str, module: str, prop: Node, value: object, expected: bool) -> None:
        if expected and (prop, module) in narrowed:
            return
        rows.append(
            row("range " + name, module, f"{SUBJECT} <{prop}> {value} .", expected, "" if expected else str(prop))
        )

    witnessed: set[str] = set()
    from _range_datatypes import union_members

    for prop, range_ in sorted(g.subject_objects(RDFS.range)):
        members = union_members(g, range_)
        if prop not in routes:
            continue
        module, label = routes[prop], g.namespace_manager.normalizeUri(str(prop))
        if len(members) > 1 and all(str(m) in UNION_LITERALS or str(m).startswith(XSD) for m in members):
            _union_cases(g, add, label, module, prop, members)
            continue
        if not str(range_).startswith(XSD):
            continue
        kind = str(range_)[len(XSD) :]
        # Each integer-family alternative once per module, on the first property that admits integers.
        integers = False
        if kind in INTEGER_RANGES:
            integers = _integer_cases(add, label, module, prop, kind)
        elif kind in LITERALS:
            integers = _literal_cases(add, label, module, prop, kind)
        if integers and module not in witnessed and (prop, module) not in narrowed:
            witnessed.add(module)
            for datatype in FAMILY:
                add(f"{label} accepts xsd:{datatype}", module, prop, f'"1"^^<{XSD}{datatype}>', True)
    return rows
