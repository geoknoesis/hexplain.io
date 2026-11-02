"""Module-scoped positive/value/cardinality contracts, also consumed by Jena.

Each case validates one small data graph against one module's shapes and is independent of
every other case, so the cases are checked across worker processes. Verdicts, result paths
and source shapes are collected and reported in authored order, which keeps a failure
message identical to the sequential form regardless of completion order.

The gate only checks. The retained snapshot (family-contracts.json) is written by
``python tools/_build_family_contracts.py --write``; here the authored cases are compared with
it as graphs, since RDF blank-node identifiers and Turtle spelling are immaterial.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from _build_family_contracts import RETAINED
from _family_contract_cases import cases
from _gate_runner import gate_workers
from _validation_result import matching_result
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef
from rdflib.compare import isomorphic

ROOT = Path(__file__).resolve().parents[1]
SH = Namespace("http://www.w3.org/ns/shacl#")

# Cases per task. Large enough to amortise parsing a module's shapes, small enough that the
# few very expensive cases spread across workers instead of serialising behind one another.
CHUNK = 24


#: An authored case as the retained file holds it.
Row = dict[str, Any]
#: One module's chunk of cases, each with its position in authored order.
Task = tuple[str, list[tuple[int, Row]]]
#: A failed case: (authored index, name, reason, validation report).
Failure = tuple[int, str, str, str]


def case_failure(shapes: Graph, row: Row) -> tuple[str, str] | None:
    """Validate one retained case against its module's ``shapes``: (reason, report) when it fails, else None.

    tools/test_release_contract.py replays archived cases with this same function, so a snapshot's cases are judged
    as the gate judged them when the snapshot was cut.
    """
    selected = shapes
    if row.get("targetShape"):
        selected = Graph() + shapes
        selected.add((URIRef(row["targetShape"]), SH.targetNode, URIRef(row["targetNode"])))
    # allow_warnings distinguishes advisory results from violations: pySHACL otherwise reports
    # conforms=false for a warning-only report, which would make sh:severity unobservable and
    # every advisory constraint indistinguishable from an error. advanced=True, as the coverage
    # ledger measures these same cases: a shape whose focus nodes a SPARQL target selects
    # (sh:target, SHACL Advanced Features) is otherwise never applied.
    ok, report, detail = validate(
        Graph().parse(data=row["data"], format="turtle"),
        shacl_graph=selected,
        inference="none",
        advanced=True,
        allow_warnings=bool(row.get("allowWarnings")),
    )
    if bool(ok) != row["expected"]:
        return f"expected conforms={row['expected']}", detail
    if not matching_result(report, row["path"], row.get("expectedShape", ""), row.get("severity", "")):
        return "no single validation result matches the expected path, source shape and severity", detail
    return None


def check(task: Task) -> list[Failure]:
    """Validate one module's chunk, returning (index, name, reason, report) for each failure."""
    module, items = task
    shapes = Graph().parse(ROOT / module)
    failures: list[Failure] = []
    for index, row in items:
        failed = case_failure(shapes, row)
        if failed is not None:
            failures.append((index, row["name"], *failed))
    return failures


def tasks(rows: list[Row]) -> Iterator[Task]:
    """The cases grouped by module and cut into chunks, in authored order."""
    grouped: dict[str, list[tuple[int, Row]]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault(row["module"], []).append((index, row))
    for module, items in grouped.items():
        for start in range(0, len(items), CHUNK):
            yield module, items[start : start + CHUNK]


def compare_retained(rows: list[Row]) -> None:
    """The retained snapshot holds exactly the authored cases, compared field by field and graph by graph."""
    relative = RETAINED.relative_to(ROOT).as_posix()
    retained = json.loads(RETAINED.read_text(encoding="utf-8"))
    stale = (
        f"{relative} differs from the authored cases; review the change, then run "
        "`python tools/_build_family_contracts.py --write` and `python tools/_constraint_coverage.py`"
    )
    assert len(rows) == len(retained), stale
    for a, b in zip(rows, retained, strict=True):
        assert {k: v for k, v in a.items() if k != "data"} == {k: v for k, v in b.items() if k != "data"}, stale
        assert isomorphic(
            Graph().parse(data=a["data"], format="turtle"), Graph().parse(data=b["data"], format="turtle")
        ), stale


def acceptance_mutations(rows: list[Row]) -> None:
    """New counterexamples must detect independently removed constraints."""
    probes = [
        ("acceptance EncryptedRegion cipher missing", SH.minCount),
        ("acceptance EncryptedRegion cipher duplicate", SH.maxCount),
        ("acceptance acquisition hasPlatform untyped", SH["class"]),
        ("acceptance signal zero", SH.minExclusive),
        ("acceptance time negative", SH.minInclusive),
    ]
    by_name = {row["name"]: row for row in rows}
    for name, predicate in probes:
        row = by_name[name]
        shapes = Graph().parse(ROOT / row["module"])
        assert case_failure(shapes, row) is None, name
        properties = list(shapes.subjects(SH.path, URIRef(row["path"])))
        assert any((prop, predicate, None) in shapes for prop in properties), name
        for prop in properties:
            shapes.remove((prop, predicate, None))
        assert case_failure(shapes, row) is not None, f"Counterexample missed removed constraint: {name}"


def diagnostic_regressions() -> None:
    report = Graph().parse(
        data="""@prefix sh:<http://www.w3.org/ns/shacl#>.
    <urn:a> sh:resultPath <urn:wanted>; sh:sourceShape <urn:other>; sh:resultSeverity sh:Warning.
    <urn:b> sh:resultPath <urn:other>; sh:sourceShape <urn:wanted>; sh:resultSeverity sh:Violation.
    """,
        format="turtle",
    )
    assert not matching_result(report, "urn:wanted", "urn:wanted")
    assert not matching_result(report, "urn:wanted", severity=str(SH.Violation))
    assert matching_result(report, "urn:wanted", "urn:other", str(SH.Warning))


def main() -> int:
    # The old `--write` habit must not look like a pass that regenerated something.
    assert len(sys.argv) == 1, (
        "this gate takes no arguments and writes nothing; the retained file is written by "
        "`python tools/_build_family_contracts.py --write`"
    )
    diagnostic_regressions()
    rows = cases()
    acceptance_mutations(rows)
    assert len({row["name"] for row in rows}) == len(rows), "Case names must be unique evidence identifiers"

    queue = list(tasks(rows))
    parallel = gate_workers()
    failures: list[Failure] = []
    completed = 0
    print(f"Validating {len(rows)} family contracts in {len(queue)} tasks across {parallel} worker(s)", flush=True)
    with ProcessPoolExecutor(max_workers=parallel) as pool:
        for result in pool.map(check, queue):
            failures.extend(result)
            completed += 1
            if completed % 10 == 0:
                print(f"Completed {completed}/{len(queue)} family-contract tasks", flush=True)
    failures.sort()
    assert not failures, "Family contract failures:\n" + "\n".join(
        f"  {name}: {reason}\n{detail}" for _, name, reason, detail in failures[:5]
    )
    compare_retained(rows)
    print(f"PASS: {len(rows)} authored module contracts with result-path assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
