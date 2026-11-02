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
from concurrent.futures import ProcessPoolExecutor

import specgraph
from _fixture_expectations import SH, parse_expectations, verdict
from _gate_runner import gate_workers
from pyshacl import validate
from rdflib import Graph

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
    """One shapes graph per distinct module set, reused by every fixture of that module.

    Only ever a shapes graph: pySHACL writes axioms of its own into it (see
    ``specgraph.context_and_shapes``), so a fixture's data graph is parsed separately.
    """
    return load(list(ont))


def check(path: str) -> str | None:
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

    def judge(name: str, text: str) -> str:
        """The verdict on one probe, "" when it behaves."""
        report = validate(Graph().parse(data=text, format="turtle"), shacl_graph=shapes, inference="none")[1]
        return verdict(name, text, report, shapes) or ""

    assert parse_expectations(line + " sh:Warning\n" + warned, "t")[0].severity == SH.Warning
    assert parse_expectations("# expect: ex:a ex:S sh:Info\n" + warned, "t")[0][2:] == (None, SH.Info)
    assert parse_expectations(line + "\n" + warned, "t")[0].severity == SH.Violation
    assert judge("w-valid.ttl", line + " sh:Warning\n" + warned) == ""
    assert "undeclared" in judge("w-valid.ttl", warned)
    assert "cannot expect a Violation" in judge("w-valid.ttl", line + "\n" + warned)
    assert "only results are warnings" in judge("w-invalid.ttl", line + " sh:Warning\n" + warned)
    assert "none was reported" in judge("w-invalid.ttl", line + "\n" + warned)
    assert judge("b-invalid.ttl", line + "\n" + broken) == ""
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
