"""Run the BDDO + DLV + core SHACL shapes over every vocabulary fixture.

Convention: specification/<mod>/test/<feature>-valid.ttl must be VALID;
specification/<mod>/test/<feature>-invalid.ttl must NOT.

A description is valid when validation yields no result of severity sh:Violation; sh:Warning
and sh:Info results do not make it invalid. pySHACL's own `conforms` is false for any result, so
the gate reads the severities of the report itself.

Failing "somehow" is not evidence: a fixture written to trip one shape can fail on an
unrelated typo and pass forever. Each -invalid file therefore declares what it must trip,
one comment line per expected SHACL result:

    # expect: <focus node> <node shape> [<constraint component>] [<severity>]

using CURIEs bound by the fixture's own @prefix lines (plus sh:). A line is satisfied by a
result whose sh:focusNode is that node and whose sh:sourceShape is the named node shape or
a property shape nested under it, whose sh:resultSeverity is the stated one -- sh:Violation
when the line states none, else sh:Warning or sh:Info -- and, when given, whose
sh:sourceConstraintComponent matches. Every expect line must be satisfied, and every -invalid
fixture needs at least one that expects a Violation: a file whose only results are advisory is a
valid description and belongs in a -valid fixture. Further results are allowed in an -invalid
fixture: a bad value can legitimately trip more than one shape.

A -valid fixture declares the advisory results it must produce the same way (a line there never
expects a Violation), and it produces no result it does not declare: "valid, and warned about
exactly this" is then asserted, not assumed.

An -invalid fixture that also carries the line

    # expect-only

allows none: every result must satisfy one of its expect lines, so a shape that starts
reporting something else on that fixture (a new target, a broken message) fails the gate
instead of hiding behind the expected result.
"""

from __future__ import annotations

import functools
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import specgraph
from _gate_runner import gate_workers
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

# Every vocabulary, aspect and register in the family. A fixture targets aspect properties
# with hexplain:mapsToProperty and names register concepts (a codec in an encoding pipeline,
# a part role); when the term's home ontology is missing the shape reports the FIXTURE as
# broken. specgraph globs, so a new aspect or register is context here the moment it lands.
CORE = specgraph.ontology_paths()

load = specgraph.load
ROOT = specgraph.ROOT


def ontologies_for(fixture_path: Any) -> Any:
    """Core vocabularies plus the owning module's own vocabulary and shapes.

    A fixture lives in a `test/` directory beside the module it exercises, at either
    depth: specification/<mod>/test/ (bddo, dlv, conf, req) or
    specification/<group>/<mod>/test/ (aspect/bundle, profiles/nitf). Resolve against
    the module directory itself rather than assuming a depth, and load every .ttl
    beside it -- some modules keep their SHACL in the vocabulary file (bddo.ttl),
    others in a sibling shapes.ttl (conf, req).
    """
    mod_dir = (ROOT / fixture_path).parent.parent
    paths = list(CORE)
    for extra in sorted(mod_dir.glob("*.ttl")):
        s = extra.relative_to(ROOT).as_posix()
        if s not in paths:
            paths.append(s)
    return paths


# Two depths: specification/<mod>/test/ and specification/<group>/<mod>/test/. The
# one-level glob silently skipped every aspect and profile fixture -- they were written,
# committed and never run.
_PATTERNS = ("specification/*/test/", "specification/*/*/test/")


def fixture_paths() -> list[str]:
    """Every -valid and -invalid fixture, as repository-relative paths in a stable order."""
    return sorted(
        f for pat in _PATTERNS for suffix in ("*-valid.ttl", "*-invalid.ttl") for f in specgraph.glob(pat + suffix)
    )


@functools.cache
def shapes_for(ont: Any) -> Any:
    """One shapes graph per distinct ontology set, reused by every fixture of that module."""
    return load(list(ont))


SH = Namespace("http://www.w3.org/ns/shacl#")
EXPECT = re.compile(r"^#[ \t]*expect:[ \t]*(\S+)[ \t]+(\S+)((?:[ \t]+\S+){0,2})[ \t]*$", re.M)
SEVERITIES = (SH.Violation, SH.Warning, SH.Info)


def expectations(path: Path) -> list[Any]:
    """The (focus, shape, component, severity) tuples a fixture declares, as IRIs."""
    return parse_expectations((ROOT / path).read_text(encoding="utf-8"), str(path))


def parse_expectations(text: str, path: str) -> list[Any]:
    """Read the expect lines of a fixture's text; the severity defaults to sh:Violation."""
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
        component, severity = None, SH.Violation
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
        rows.append((iri(focus), iri(shape), component, severity))
    return rows


def _nested(shapes, node, seen=None):
    """A node shape and every shape reachable from it through blank-node constraint structure."""
    seen = set() if seen is None else seen
    if node in seen:
        return seen
    seen.add(node)
    for _p, o in shapes.predicate_objects(node):
        if not isinstance(o, URIRef):
            _nested(shapes, o, seen)
    return seen


def results_of(report: Graph) -> list[Any]:
    """Every validation result as (focus, source shape, component, severity, message)."""
    return [
        (
            report.value(r, SH.focusNode),
            report.value(r, SH.sourceShape),
            report.value(r, SH.sourceConstraintComponent),
            severity,
            report.value(r, SH.resultMessage),
        )
        for r, severity in report.subject_objects(SH.resultSeverity)
    ]


def satisfies(result: Any, expectation: Any, shapes: Graph) -> bool:
    """Whether one result is the one an expect line describes."""
    f, s, c, severity, _message = result
    focus, shape, component, wanted = expectation
    return f == focus and severity == wanted and s in _nested(shapes, shape) and component in (None, c)


def unmet(report: Graph, shapes: Graph, expected: list[Any]) -> Any:
    """Expect lines no result satisfies."""
    results = results_of(report)
    return [e for e in expected if not any(satisfies(r, e, shapes) for r in results)]


EXPECT_ONLY = re.compile(r"^#\s*expect-only\s*$", re.M)


def unexpected(report: Graph, shapes: Graph, expected: list[Any]) -> Any:
    """Results that no expect line accounts for."""
    return [r for r in results_of(report) if not any(satisfies(r, e, shapes) for e in expected)]


def _listed(rows: list[Any]) -> str:
    return "\n  ".join(" ".join(str(x) for x in row if x is not None) for row in rows)


def verdict(path: str, text: str, report_graph: Graph, shapes: Graph, report: str = "") -> str | None:
    """Judge one fixture's validation report against its name and its expect lines."""
    expected = parse_expectations(text, path)
    violations = [r for r in results_of(report_graph) if r[3] == SH.Violation]
    missing = unmet(report_graph, shapes, expected)
    if path.endswith("-valid.ttl"):
        if any(e[3] == SH.Violation for e in expected):
            return f"{path}: a -valid fixture cannot expect a Violation; expect sh:Warning or sh:Info, or rename it"
        if violations:
            return f"{path}: expected to be valid, but validation reported a Violation:\n  {_listed(violations)}\n{report}"
        if missing:
            return f"{path}: expected advisory results not reported:\n  {_listed(missing)}\n{report}"
        extra = unexpected(report_graph, shapes, expected)
        if extra:
            return f"{path}: a -valid fixture declares every result it produces; undeclared:\n  {_listed(extra)}"
        return None
    if not any(e[3] == SH.Violation for e in expected):
        return (
            f"{path}: an -invalid fixture must declare '# expect: <focus> <shape> [<component>]' for a Violation; "
            "a file whose only results are warnings is a valid description"
        )
    if not violations:
        return f"{path}: expected a SHACL Violation, but none was reported"
    if missing:
        return f"{path}: expected results not reported:\n  {_listed(missing)}\n{report}"
    if EXPECT_ONLY.search(text):
        extra = unexpected(report_graph, shapes, expected)
        if extra:
            return f"{path}: # expect-only, but these results were not expected:\n  {_listed(extra)}"
    return None


def check(path: str) -> Any:
    """Validate one fixture, returning a failure description or None."""
    ont = ontologies_for(path)
    data = load(ont + [path])
    shapes = shapes_for(tuple(ont))
    _conforms, report_graph, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    return verdict(path, (ROOT / path).read_text(encoding="utf-8"), report_graph, shapes, report)


def self_test() -> None:
    """The verdict follows severities: a warning never makes a fixture invalid, and is never silent."""
    shapes = Graph().parse(
        format="turtle",
        data="""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <urn:ex#> .
        ex:S a sh:NodeShape ; sh:targetClass ex:C ;
            sh:property [ sh:path ex:must ; sh:minCount 1 ; sh:message "required" ] ;
            sh:property [ sh:path ex:advised ; sh:minCount 1 ; sh:severity sh:Warning ; sh:message "advised" ] .""",
    )
    head = "@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <urn:ex#> .\n"
    warned = head + "ex:a a ex:C ; ex:must 1 .\n"
    broken = head + "ex:a a ex:C ; ex:advised 1 .\n"
    line = "# expect: ex:a ex:S sh:MinCountConstraintComponent"

    def judge(name: str, text: str) -> str | None:
        report = validate(Graph().parse(data=text, format="turtle"), shacl_graph=shapes, inference="none")[1]
        return verdict(name, text, report, shapes)

    assert parse_expectations(line + " sh:Warning\n" + warned, "t")[0][3] == SH.Warning
    assert parse_expectations("# expect: ex:a ex:S sh:Info\n" + warned, "t")[0][2:] == (None, SH.Info)
    assert parse_expectations(line + "\n" + warned, "t")[0][3] == SH.Violation
    assert judge("w-valid.ttl", line + " sh:Warning\n" + warned) is None
    assert "undeclared" in judge("w-valid.ttl", warned)
    assert "cannot expect a Violation" in judge("w-valid.ttl", line + "\n" + warned)
    assert "only results are warnings" in judge("w-invalid.ttl", line + " sh:Warning\n" + warned)
    assert "none was reported" in judge("w-invalid.ttl", line + "\n" + warned)
    assert judge("b-invalid.ttl", line + "\n" + broken) is None
    assert "reported a Violation" in judge("b-valid.ttl", broken)
    assert "not reported" in judge("b-invalid.ttl", line + "\n" + line + " sh:Warning\n" + broken)


def main() -> int:
    self_test()
    fixtures = fixture_paths()
    if not fixtures:
        print("FAIL: no fixtures found under specification/")
        return 1
    parallel = gate_workers()
    print(f"Validating {len(fixtures)} vocabulary fixtures across {parallel} worker(s)", flush=True)
    # Fixtures sharing an ontology set are adjacent, so each worker reuses its cached shapes.
    if parallel == 1:
        results = [check(path) for path in fixtures]
    else:
        with ProcessPoolExecutor(max_workers=parallel) as pool:
            results = list(pool.map(check, fixtures, chunksize=2))
    failures = [failure for failure in results if failure]
    if failures:
        print("FAIL:\n" + "\n".join(failures))
        return 1
    print(f"PASS: {len(fixtures)} vocabulary fixtures behave as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
