"""What an -invalid vocabulary fixture declares it must trip, and the SHACL results that satisfy it.

An -invalid fixture states one comment line per expected SHACL result (tools/test_vocab_shapes.py
gives the convention):

    # expect: <focus node> <node shape> [<constraint component>]

in CURIEs bound by the fixture's own @prefix lines (plus sh:), and may add ``# expect-only``, under
which every result must satisfy one of its expect lines.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from rdflib import Graph, Namespace, URIRef
from rdflib.term import Node

SH = Namespace("http://www.w3.org/ns/shacl#")
EXPECT = re.compile(r"^#\s*expect:\s*(\S+)\s+(\S+)(?:\s+(\S+))?\s*$", re.M)
EXPECT_ONLY = re.compile(r"^#\s*expect-only\s*$", re.M)


class Expected(NamedTuple):
    """One expect line: the focus node, the node shape, and the constraint component when it names one."""

    focus: URIRef
    shape: URIRef
    component: URIRef | None


class Result(NamedTuple):
    """One SHACL result of a report, as far as an expect line can account for it."""

    focus: Node | None
    shape: Node | None
    component: Node | None
    message: Node | None


def expectations(path: Path) -> list[Expected]:
    """The expect lines of the fixture at [path], their CURIEs resolved to IRIs."""
    text = path.read_text(encoding="utf-8")
    prefixes = Graph().parse(data=text, format="turtle").namespace_manager
    bound = dict(prefixes.namespaces())
    bound.setdefault("sh", URIRef(str(SH)))

    def iri(curie: str) -> URIRef:
        if curie.startswith("<") and curie.endswith(">"):
            return URIRef(curie[1:-1])
        prefix, _, local = curie.partition(":")
        if prefix not in bound:
            raise ValueError(f"{path}: expect line uses unbound prefix '{prefix}:'")
        return URIRef(str(bound[prefix]) + local)

    return [Expected(iri(f), iri(s), iri(c) if c else None) for f, s, c in EXPECT.findall(text)]


def expect_only(path: Path) -> bool:
    """Whether the fixture at [path] allows no result beyond its expect lines."""
    return EXPECT_ONLY.search(path.read_text(encoding="utf-8")) is not None


def nested(shapes: Graph, node: Node, seen: set[Node] | None = None) -> set[Node]:
    """A node shape and every shape reachable from it through blank-node constraint structure."""
    seen = set() if seen is None else seen
    if node in seen:
        return seen
    seen.add(node)
    for _p, o in shapes.predicate_objects(node):
        if not isinstance(o, URIRef):
            nested(shapes, o, seen)
    return seen


def results(report: Graph) -> list[Result]:
    """Every result of a validation report."""
    return [
        Result(
            report.value(r, SH.focusNode),
            report.value(r, SH.sourceShape),
            report.value(r, SH.sourceConstraintComponent),
            report.value(r, SH.resultMessage),
        )
        for r in report.subjects(SH.resultSeverity, None)
    ]


def satisfies(result: Result, expected: Expected, shapes: Graph) -> bool:
    """Whether [result] is the one [expected] declares: its focus node, a shape under the named node shape, and the
    constraint component when the line names one."""
    return (
        result.focus == expected.focus
        and result.shape in nested(shapes, expected.shape)
        and (expected.component is None or result.component == expected.component)
    )


def unmet(report: Graph, shapes: Graph, expected: list[Expected]) -> list[Expected]:
    """Expect lines no result satisfies."""
    found = results(report)
    return [e for e in expected if not any(satisfies(r, e, shapes) for r in found)]


def unexpected(report: Graph, shapes: Graph, expected: list[Expected]) -> list[Result]:
    """Results that no expect line accounts for (only checked under # expect-only)."""
    return [r for r in results(report) if not any(satisfies(r, e, shapes) for e in expected)]
