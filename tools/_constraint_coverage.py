"""Measure evaluated constraint components, not term mentions or inferred coverage.

pySHACL evaluation tracing is diagnostic evidence; conformance and report paths
are still checked against the independently retained corpus expectations.

The corpora are measured as independent tasks across a process pool (tools/_coverage_corpora.py).
The ledger does not depend on how many workers ran or in what order they finished: tasks are
listed in a fixed order, results are merged in that order, and every list is sorted before it is
written.

On disk the ledger is one JSON document, stored compactly (:func:`serialise`): the header on the
first line, then one obligation per line, with each obligation's cases given as indices into
the header's ``case_names`` rather than spelled out -- a case that exercises four hundred
obligations is named once, not four hundred times. :func:`read_ledger` returns it with the names
back in place, which is the form every consumer here works with.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import pyshacl
import specgraph
from _coverage_corpora import (
    FAMILY_CONTRACTS,
    FIELDS,
    OUT,
    PROCEDURAL,
    ROOT,
    SECURITY_PROFILE,
    SH,
    Key,
    fixture_paths,
    initialise,
    run_task,
    tasks,
    trace,
)
from _gate_runner import gate_workers
from _validation_result import matching_result
from pyshacl import validate
from pyshacl.constraints import ALL_CONSTRAINT_COMPONENTS
from rdflib import RDF, BNode, Graph, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.term import Node

LEDGER = OUT / "constraint-coverage.json"
SCOPE = (
    "Integrated pySHACL component evaluations in current shared corpora, vocabulary fixtures and procedural "
    "geospatial/video/numeric gates. Each case is validated in the context of the modules its own terms belong "
    "to, so an evaluation recorded for a case is one the case's data caused. Nested branch failures may occur "
    "within conforming graphs; two-sided evaluation is not independent semantic review or proof that each "
    "parameter is necessary. Empty-value passes are recorded separately and count as positive evidence only for "
    "cardinality components, where zero is a meaningful input. Rules and custom targets are not constraint "
    "components."
)

#: One obligation of the ledger, keyed in the inventory by (shape, component).
Obligation = dict[str, Any]


def two_sided(row: Obligation) -> bool:
    """Whether an obligation was seen both to reject and to accept."""
    # Zero is an actual cardinality input: maxCount 0 cannot pass on nonempty values.
    # Empty datatype/class/node checks still provide no positive value witness.
    cardinality = row["component"] in {str(SH.MinCountConstraintComponent), str(SH.MaxCountConstraintComponent)}
    return bool(row["failed"] and (row["passed"] or (cardinality and row["empty_value_passes"])))


def canonical(path: str) -> Graph:
    """One file as a graph whose blank-node labels depend on its content and path alone."""
    # Read as text and give every file the same repo-relative base: a CRLF working
    # copy otherwise alters multi-line literal content, and a filesystem base URI
    # would vary by checkout location. Both make measured evidence machine-bound.
    source = Graph().parse(data=(ROOT / path).read_text(encoding="utf-8"), format="turtle", publicID="file:///" + path)
    prefix = hashlib.sha256(path.encode()).hexdigest()[:16]

    def term(t: Node) -> Node:
        return BNode(prefix + "_" + str(t)) if isinstance(t, BNode) else t

    g = Graph()
    for s, p, o in to_canonical_graph(source):
        g.add((term(s), term(p), term(o)))
    return g


def stable_value(g: Graph, value: Node, depth: int = 0) -> str:
    """Identify a parameter value by content.

    Canonical blank-node labels are rdflib run identities, not content: recording
    them binds the ledger to one interpreter build, so evidence measured on one
    machine cannot validate on another. Nested values are folded into a digest of
    the reachable subgraph instead.
    """
    if not isinstance(value, BNode):
        return str(value)
    if depth >= 32:
        return "bnode:depth-limit"
    parts = sorted((str(pred), stable_value(g, obj, depth + 1)) for pred, obj in g.predicate_objects(value))
    return "bnode:" + hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def _owners(g: Graph, node: Node) -> list[str]:
    """The named node shapes a (possibly nested, blank) shape node belongs to."""
    pending, visited, owners = [node], set(), set()
    while pending:
        parent = pending.pop()
        if parent in visited:
            continue
        visited.add(parent)
        if isinstance(parent, URIRef) and (parent, RDF.type, SH.NodeShape) in g:
            owners.add(str(parent))
        if isinstance(parent, BNode):
            pending.extend(g.subjects(None, parent))
    return sorted(owners)


def _obligation(path: str, g: Graph, node: Node, key: Key) -> Obligation:
    digest = hashlib.sha256((path + "|" + key[0] + "|" + key[1]).encode()).hexdigest()
    return dict(
        id=digest,
        source=path,
        shape=key[0],
        component=key[1],
        parameters={},
        path=str(g.value(node, SH.path) or ""),
        owners=_owners(g, node),
        passed=[],
        failed=[],
        empty_value_passes=[],
    )


def inventory() -> tuple[dict[str, Graph], dict[Key, Obligation]]:
    """The canonical graph of every measured file, and every constraint obligation they state."""
    graphs = {p: canonical(p) for p in [*specgraph.ontology_paths(), SECURITY_PROFILE]}
    rows: dict[Key, Obligation] = {}
    for path, g in graphs.items():
        for cls in ALL_CONSTRAINT_COMPONENTS:
            for param in cls.constraint_parameters():
                for node, value in g.subject_objects(param):
                    # Multiple parameters of one component constitute one obligation.
                    key = (str(node), str(cls.shacl_constraint_component))
                    if key not in rows:
                        rows[key] = _obligation(path, g, node, key)
                    values = rows[key]["parameters"].setdefault(str(param), [])
                    text = stable_value(g, value)
                    if text not in values:
                        values.append(text)
                        values.sort()
    return graphs, rows


def _text_digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_text(encoding="utf-8").encode()).hexdigest()


def _summary(rows: list[Obligation], cases: int) -> dict[str, int]:
    return dict(
        cases=cases,
        components=len(rows),
        two_sided=sum(r["two_sided_evaluation"] for r in rows),
        never_evaluated=sum(not (r["passed"] or r["failed"] or r["empty_value_passes"]) for r in rows),
    )


def _close(rows: dict[Key, Obligation]) -> list[Obligation]:
    """Sort each obligation's case lists, decide two-sidedness, and order the obligations by id."""
    for row in rows.values():
        for name in FIELDS:
            row[name] = sorted(set(row[name]))
        row["two_sided_evaluation"] = two_sided(row)
    return sorted(rows.values(), key=lambda r: r["id"])


def measure(workers: int | None = None) -> dict[str, Any]:
    """Trace every corpus across ``workers`` processes and assemble the ledger."""
    graphs, rows = inventory()
    planned = tasks()
    workers = workers or gate_workers()
    print(f"Measuring {len(planned)} corpus tasks across {workers} worker(s)", flush=True)
    cases, started = 0, time.monotonic()
    with ProcessPoolExecutor(max_workers=workers, initializer=initialise, initargs=(graphs, list(rows))) as pool:
        # map() yields in task order whatever order the workers finish in.
        for done, (booked, calls) in enumerate(pool.map(run_task, planned), 1):
            for shape, component, name, case in booked:
                rows[(shape, component)][name].append(case)
            cases += calls
            if done % 10 == 0 or done == len(planned):
                elapsed = time.monotonic() - started
                print(f"Traced {cases} validation calls ({done}/{len(planned)} tasks, {elapsed:.0f}s)", flush=True)
    result = _close(rows)
    corpus_paths = sorted(
        set(fixture_paths())
        | {p.relative_to(ROOT).as_posix() for p in (OUT / "test").glob("*competency.tsv")}
        | set(PROCEDURAL)
        | {FAMILY_CONTRACTS}
    )
    return dict(
        scope=SCOPE,
        validator=pyshacl.__version__,
        corpus_hashes={p: _text_digest(p) for p in corpus_paths},
        sources={p: _text_digest(p) for p in graphs},
        summary=_summary(result, cases),
        complete=all(r["two_sided_evaluation"] for r in result),
        constraints=result,
    )


def _reuse(evidence: dict[str, Any]) -> tuple[dict[str, Graph], dict[Key, Obligation]]:
    """The inventory with the retained ledger's evaluations, once every input is shown unchanged."""
    assert evidence["validator"] == pyshacl.__version__, "Changed validator requires full measurement"
    for collection in ["sources", "corpus_hashes"]:
        for path, digest in evidence[collection].items():
            assert _text_digest(path) == digest, ("Changed input requires full measurement", path)
    graphs, inventory_rows = inventory()
    assert set(graphs) == set(evidence["sources"])
    previous = {r["id"]: r for r in evidence["constraints"]}
    assert set(previous) == {r["id"] for r in inventory_rows.values()}
    for row in inventory_rows.values():
        old = previous[row["id"]]
        for name in ["source", "shape", "component", "parameters", "path", "owners"]:
            assert row[name] == old[name]
        for name in FIELDS:
            row[name] = list(old[name])
    return graphs, inventory_rows


def _appended(retained: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The authored cases the retained corpus lacks, once every retained case is shown unchanged."""
    from _family_contract_cases import cases as authored_cases
    from rdflib.compare import isomorphic

    generated = authored_cases()
    by_name = {r["name"]: r for r in generated}
    assert len(by_name) == len(generated)
    assert len({r["name"] for r in retained}) == len(retained)
    for old in retained:
        new = by_name[old["name"]]
        assert {k: v for k, v in old.items() if k != "data"} == {k: v for k, v in new.items() if k != "data"}, (
            "Changed expectation requires full measurement"
        )
        assert isomorphic(
            Graph().parse(data=old["data"], format="turtle"), Graph().parse(data=new["data"], format="turtle")
        ), "Changed case requires full measurement"
    old_names = {r["name"] for r in retained}
    additions = [r for r in generated if r["name"] not in old_names]
    assert additions, "No appended cases to measure"
    return additions


def extend_family() -> dict[str, Any]:
    """Reuse evidence only for byte-identical inputs and append-only authored cases."""
    evidence = read_ledger()
    graphs, inventory_rows = _reuse(evidence)
    corpus_path = ROOT / FAMILY_CONTRACTS
    retained = json.loads(corpus_path.read_text(encoding="utf-8"))
    additions = _appended(retained)
    current = [""]
    with trace(inventory_rows, current):
        for row in additions:
            current[0] = "family-contracts:" + row["name"]
            selected = graphs[row["module"]]
            if row.get("targetShape"):
                selected = Graph() + selected
                selected.add((URIRef(row["targetShape"]), SH.targetNode, URIRef(row["targetNode"])))
            ok, report, detail = validate(
                Graph().parse(data=row["data"], format="turtle"), shacl_graph=selected, inference="none", advanced=True
            )
            assert bool(ok) == row["expected"], (row["name"], detail)
            assert matching_result(report, row["path"], row.get("expectedShape", ""), row.get("severity", "")), (
                row["name"],
                detail,
            )
    evidence["constraints"] = _close(inventory_rows)
    evidence["summary"] = _summary(evidence["constraints"], evidence["summary"]["cases"] + len(additions))
    evidence["complete"] = all(r["two_sided_evaluation"] for r in evidence["constraints"])
    # Preserve old serialization as well as semantics. A partial write is detected by the hash gate.
    corpus_text = json.dumps(retained + additions, indent=2) + "\n"
    evidence["corpus_hashes"][FAMILY_CONTRACTS] = hashlib.sha256(corpus_text.encode()).hexdigest()
    evidence.setdefault("append_only_measurements", []).append(
        dict(added_cases=len(additions), previous_cases=evidence["summary"]["cases"] - len(additions))
    )
    corpus_path.write_text(corpus_text, encoding="utf-8", newline="\n")
    return evidence


def serialise(evidence: dict[str, Any]) -> str:
    """The ledger as compact JSON: the header on the first line, then one obligation per line.

    Deterministic for a given ledger: keys in insertion order, no optional whitespace, case names
    sorted and each obligation's cases written as ascending indices into them.
    """
    names = sorted({case for row in evidence["constraints"] for name in FIELDS for case in row[name]})
    index = {name: position for position, name in enumerate(names)}
    head = {key: value for key, value in evidence.items() if key not in ("constraints", "case_names")}
    head["case_names"] = names
    opening = json.dumps(head, separators=(",", ":"))[:-1] + ',"constraints":['
    rows = [
        json.dumps({**row, **{name: [index[case] for case in row[name]] for name in FIELDS}}, separators=(",", ":"))
        for row in evidence["constraints"]
    ]
    return opening + "\n" + ",\n".join(rows) + "\n]}\n"


def read_ledger(path: Path = LEDGER) -> dict[str, Any]:
    """The ledger with every obligation's cases as names; ``case_names`` is folded back in and dropped."""
    stored: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    names = stored.pop("case_names")
    for row in stored["constraints"]:
        for name in FIELDS:
            row[name] = [names[position] for position in row[name]]
    return stored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--extend-family",
        action="store_true",
        help="Measure only family-contract cases appended since the retained ledger; every other input must be "
        "byte-identical",
    )
    parser.add_argument("--workers", type=int, default=None, help="Worker processes (default: the gate worker count)")
    args = parser.parse_args(argv)
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be at least 1")
    result = extend_family() if args.extend_family else measure(args.workers)
    LEDGER.write_text(serialise(result), encoding="utf-8", newline="\n")
    print(json.dumps(result["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
