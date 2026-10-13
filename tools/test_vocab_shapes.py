"""Run the BDDO + DLV + core SHACL shapes over every vocabulary fixture.

Convention: specification/<mod>/test/<feature>-valid.ttl must conform;
specification/<mod>/test/<feature>-invalid.ttl must NOT.

Failing "somehow" is not evidence: a fixture written to trip one shape can fail on an
unrelated typo and pass forever. Each -invalid file therefore declares what it must trip,
one comment line per expected SHACL result:

    # expect: <focus node> <node shape> [<constraint component>]

using CURIEs bound by the fixture's own @prefix lines (plus sh:). A line is satisfied by a
result whose sh:focusNode is that node and whose sh:sourceShape is the named node shape or
a property shape nested under it, and -- when given -- whose sh:sourceConstraintComponent
matches. Every expect line must be satisfied, and every -invalid fixture needs at least one.
Further results are allowed: a bad value can legitimately trip more than one shape. A
fixture that also carries the line

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

load = specgraph.load
ROOT = specgraph.ROOT


def ontologies_for(fixture_path: str) -> list[str]:
    """The modules a fixture is validated with: the ones it is written in terms of, and its own.

    A fixture targets aspect properties with hexplain:mapsToProperty and names register concepts
    (a codec in an encoding pipeline, a part role); when the term's home ontology is missing the
    shape reports the FIXTURE as broken. So the context is every family module one of the
    fixture's own IRIs belongs to, with everything those modules import
    (``specgraph.modules_used_by``) -- a new aspect or register is context the moment a fixture
    mentions it. The rest of the family is left out: it never mentions the fixture's terms, and
    loading all forty modules as data and as shapes for each of 150 fixtures was nine tenths of
    this gate's time and memory.

    A fixture lives in a `test/` directory beside the module it exercises, at either
    depth: specification/<mod>/test/ (bddo, dlv, conf, req) or
    specification/<group>/<mod>/test/ (aspect/bundle, profiles/nitf). Resolve against
    the module directory itself rather than assuming a depth, and load every .ttl
    beside it -- some modules keep their SHACL in the vocabulary file (bddo.ttl),
    others in a sibling shapes.ttl (conf, req).
    """
    mod_dir = (ROOT / fixture_path).parent.parent
    beside = {extra.relative_to(ROOT).as_posix() for extra in mod_dir.glob("*.ttl")}
    return sorted(set(specgraph.modules_used_by(load([fixture_path]))) | beside)


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
def shapes_for(ont: tuple[str, ...]) -> Graph:
    """One graph per distinct module set, reused by every fixture with that context; never modified.

    It is the shapes graph of a fixture and, with the fixture's own triples added to a copy, the
    ontology context of its data graph.
    """
    return load(list(ont))


SH = Namespace("http://www.w3.org/ns/shacl#")
EXPECT = re.compile(r"^#\s*expect:\s*(\S+)\s+(\S+)(?:\s+(\S+))?\s*$", re.M)


def expectations(path: Path) -> list[Any]:
    """The (focus, shape, component) triples an -invalid fixture declares, as IRIs."""
    text = (ROOT / path).read_text(encoding="utf-8")
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

    return [(iri(f), iri(s), iri(c) if c else None) for f, s, c in EXPECT.findall(text)]


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


def unmet(report: Graph, shapes: Graph, expected: bool) -> Any:
    """Expect lines no result satisfies."""
    results = [
        (report.value(r, SH.focusNode), report.value(r, SH.sourceShape), report.value(r, SH.sourceConstraintComponent))
        for r in report.subjects(SH.resultSeverity, None)
    ]
    missing = []
    for focus, shape, component in expected:
        family = _nested(shapes, shape)
        if not any(f == focus and s in family and (component is None or c == component) for f, s, c in results):
            missing.append((focus, shape, component))
    return missing


EXPECT_ONLY = re.compile(r"^#\s*expect-only\s*$", re.M)


def unexpected(report: Graph, shapes: Graph, expected: bool) -> Any:
    """Results that no expect line accounts for (only checked under # expect-only)."""
    out = []
    for r in report.subjects(SH.resultSeverity, None):
        f, s, c = (
            report.value(r, SH.focusNode),
            report.value(r, SH.sourceShape),
            report.value(r, SH.sourceConstraintComponent),
        )
        if not any(
            f == focus and s in _nested(shapes, shape) and (component is None or c == component)
            for focus, shape, component in expected
        ):
            out.append((f, s, c, report.value(r, SH.resultMessage)))
    return out


def check(path: str) -> str | None:
    """Validate one fixture, returning a failure description or None."""
    should_conform = path.endswith("-valid.ttl")
    ont = ontologies_for(path)
    shapes = shapes_for(tuple(ont))
    data = shapes + load([path])
    conforms, report_graph, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    if should_conform:
        return None if conforms else f"{path}: expected to conform, but did not:\n{report}"
    expected = expectations(path)
    if not expected:
        return f"{path}: an -invalid fixture must declare '# expect: <focus> <shape> [<component>]'"
    if conforms:
        return f"{path}: expected SHACL violation, but it conformed"
    missing = unmet(report_graph, shapes, expected)
    if missing:
        listed = "\n  ".join(" ".join(str(x) for x in m if x is not None) for m in missing)
        return f"{path}: expected results not reported:\n  {listed}\n{report}"
    if EXPECT_ONLY.search((ROOT / path).read_text(encoding="utf-8")):
        extra = unexpected(report_graph, shapes, expected)
        if extra:
            listed = "\n  ".join(" ".join(str(x) for x in m if x is not None) for m in extra)
            return f"{path}: # expect-only, but these results were not expected:\n  {listed}"
    return None


def main() -> int:
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
