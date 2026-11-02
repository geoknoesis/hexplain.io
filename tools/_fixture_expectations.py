"""What a vocabulary fixture declares about its SHACL results, and the verdict on a report.

A fixture states one comment line per result it must produce (tools/test_vocab_shapes.py gives
the convention):

    # expect: <focus node> <node shape> [<constraint component>] [<severity>]

in CURIEs bound by the fixture's own @prefix lines (plus sh:). The severity is sh:Violation when
the line states none. An -invalid fixture may add ``# expect-only``, under which every result
must satisfy one of its expect lines; a -valid fixture always declares every result it produces.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from rdflib import Graph, Namespace, URIRef
from rdflib.term import Node

SH = Namespace("http://www.w3.org/ns/shacl#")
EXPECT = re.compile(r"^#[ \t]*expect:[ \t]*(\S+)[ \t]+(\S+)((?:[ \t]+\S+){0,2})[ \t]*$", re.M)
EXPECT_ONLY = re.compile(r"^#\s*expect-only\s*$", re.M)
SEVERITIES = (SH.Violation, SH.Warning, SH.Info)


class Expected(NamedTuple):
    """One expect line: the focus node, the node shape, the constraint component when it names one, and the
    severity (sh:Violation when it names none)."""

    focus: URIRef
    shape: URIRef
    component: URIRef | None
    severity: URIRef


class Result(NamedTuple):
    """One SHACL result of a report, as far as an expect line can account for it."""

    focus: Node | None
    shape: Node | None
    component: Node | None
    severity: Node
    message: Node | None


def parse_expectations(text: str, path: str) -> list[Expected]:
    """The expect lines of a fixture's [text], their CURIEs resolved to IRIs; [path] names it in errors."""
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

    rows = []
    for focus, shape, rest in EXPECT.findall(text):
        component: URIRef | None = None
        severity = URIRef(SH.Violation)
        stated = [iri(token) for token in rest.split()]
        for term in stated:
            if term in SEVERITIES:
                severity = term
            elif component is None:
                component = term
            else:
                raise ValueError(f"{path}: expect line names two constraint components: {focus} {shape}{rest}")
        if len(stated) == 2 and component is None:
            raise ValueError(f"{path}: expect line names two severities: {focus} {shape}{rest}")
        rows.append(Expected(iri(focus), iri(shape), component, severity))
    return rows


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
            severity,
            report.value(r, SH.resultMessage),
        )
        for r, severity in report.subject_objects(SH.resultSeverity)
    ]


def satisfies(result: Result, expected: Expected, shapes: Graph) -> bool:
    """Whether [result] is the one [expected] declares: its focus node and severity, a shape under the named node
    shape, and the constraint component when the line names one."""
    return (
        result.focus == expected.focus
        and result.severity == expected.severity
        and result.shape in nested(shapes, expected.shape)
        and (expected.component is None or result.component == expected.component)
    )


def unmet(report: Graph, shapes: Graph, expected: list[Expected]) -> list[Expected]:
    """Expect lines no result satisfies."""
    found = results(report)
    return [e for e in expected if not any(satisfies(r, e, shapes) for r in found)]


def unexpected(report: Graph, shapes: Graph, expected: list[Expected]) -> list[Result]:
    """Results that no expect line accounts for."""
    return [r for r in results(report) if not any(satisfies(r, e, shapes) for e in expected)]


def _listed(rows: list[Expected] | list[Result]) -> str:
    return "\n  ".join(" ".join(str(x) for x in row if x is not None) for row in rows)


def _valid_verdict(path: str, expected: list[Expected], report_graph: Graph, shapes: Graph, report: str) -> str | None:
    """A -valid fixture: no Violation, every declared advisory result, and nothing undeclared."""
    if any(e.severity == SH.Violation for e in expected):
        return f"{path}: a -valid fixture cannot expect a Violation; expect sh:Warning or sh:Info, or rename it"
    violations = [r for r in results(report_graph) if r.severity == SH.Violation]
    if violations:
        return f"{path}: expected to be valid, but validation reported a Violation:\n  {_listed(violations)}\n{report}"
    missing = unmet(report_graph, shapes, expected)
    if missing:
        return f"{path}: expected advisory results not reported:\n  {_listed(missing)}\n{report}"
    extra = unexpected(report_graph, shapes, expected)
    if extra:
        return f"{path}: a -valid fixture declares every result it produces; undeclared:\n  {_listed(extra)}"
    return None


def verdict(path: str, text: str, report_graph: Graph, shapes: Graph, report: str = "") -> str | None:
    """Judge one fixture's validation report against its name and its expect lines; None when it behaves."""
    expected = parse_expectations(text, path)
    if path.endswith("-valid.ttl"):
        return _valid_verdict(path, expected, report_graph, shapes, report)
    if not any(e.severity == SH.Violation for e in expected):
        return (
            f"{path}: an -invalid fixture must declare '# expect: <focus> <shape> [<component>]' for a Violation; "
            "a file whose only results are warnings is a valid description"
        )
    if not any(r.severity == SH.Violation for r in results(report_graph)):
        return f"{path}: expected a SHACL Violation, but none was reported"
    missing = unmet(report_graph, shapes, expected)
    if missing:
        return f"{path}: expected results not reported:\n  {_listed(missing)}\n{report}"
    if EXPECT_ONLY.search(text):
        extra = unexpected(report_graph, shapes, expected)
        if extra:
            return f"{path}: # expect-only, but these results were not expected:\n  {_listed(extra)}"
    return None
