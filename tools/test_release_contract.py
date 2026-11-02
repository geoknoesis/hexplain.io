"""Verify archive integrity; historical compatibility replay is explicitly opt-in."""

import argparse
import base64
import hashlib
import json
import zipfile
from pathlib import Path

import specgraph
from _instance_corpus import check_corpus
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef
from test_family_contract import case_failure

ROOT = Path(__file__).resolve().parents[1]
#: Validation outcomes of archived cases that a later, recorded change altered.
COMPATIBILITY = ROOT / "releases/compatibility.json"


SH = Namespace("http://www.w3.org/ns/shacl#")
#: Retained TSV corpora and the shape files each is validated with.
CORPORA = [
    ("layout-competency.tsv", ["specification/dlv/dlv.ttl", "specification/aspect/bundle/bundle.ttl"]),
    ("security-competency.tsv", ["specification/validation/test/security-profile.ttl"]),
    ("geometry-competency.tsv", ["specification/aspect/geometry/geometry.ttl"]),
    ("network-competency.tsv", ["specification/npv/net.ttl"]),
    ("spatialref-competency.tsv", ["specification/aspect/spatialref/spatialref.ttl"]),
    ("core-mapping-competency.tsv", ["specification/hexplain/core.ttl"]),
    (
        "conformance-competency.tsv",
        [
            "specification/conf/conf.ttl",
            "specification/conf/shapes.ttl",
            "specification/req/req.ttl",
            "specification/req/shapes.ttl",
            "specification/fn/fn.ttl",
        ],
    ),
]


def _verify_archive(path: Path) -> tuple[dict[str, str], Graph]:
    """Check a snapshot's archive against its manifest; return its files and the graph of its Turtle."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["releaseId"] == path.parent.name
    archive = path.parent / manifest["archive"]
    assert archive.parent == path.parent and archive.name == "hexplain-spec.zip"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["sha256"], archive
    files = {}
    family = Graph()
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        assert sorted(z.namelist()) == sorted(f["path"] for f in manifest["files"])
        for item in manifest["files"]:
            data = z.read(item["path"])
            assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
            files[item["path"]] = data.decode("utf-8")
            if item["path"].endswith(".ttl"):
                family.parse(data=data, format="turtle")
    return files, family


#: One retained case whose outcome differs: (release, corpus or contract file, case name).
Divergence = tuple[str, str, str]


def _corpus_failure(shapes: Graph, line: str) -> tuple[str, str, str] | None:
    """Validate one TSV corpus row: (name, reason, report) when it fails, else None.

    With SHACL Advanced Features, as the coverage ledger measures these rows: a shape whose focus nodes a SPARQL
    target selects (req:RequirementIdentityShape) is otherwise never applied.
    """
    name, expected, result_path, encoded = line.split("\t")
    ok, report, detail = validate(
        Graph().parse(data=base64.b64decode(encoded).decode(), format="turtle"),
        shacl_graph=shapes,
        inference="none",
        advanced=True,
    )
    if bool(ok) != (expected == "true"):
        return name, f"expected conforms={expected}", detail
    if result_path and URIRef(result_path) not in report.objects(None, SH.resultPath):
        return name, f"missing result path {result_path}", detail
    return None


def _corpus_failures(files: dict[str, str], shape_files: dict[str, str]) -> tuple[int, list[tuple[str, str, str, str]]]:
    """Every retained TSV corpus of a snapshot against the shapes in ``shape_files``: (cases, failures)."""
    cases, failures = 0, []
    for corpus_name, shape_paths in CORPORA:
        corpus_path = "specification/validation/test/" + corpus_name
        if corpus_path not in files:
            continue  # Older immutable releases predate these suites.
        shapes = Graph()
        for shape_path in shape_paths:
            shapes.parse(data=shape_files[shape_path], format="turtle")
        for line in files[corpus_path].splitlines():
            if not line or line.startswith("#"):
                continue
            cases += 1
            failed = _corpus_failure(shapes, line)
            if failed is not None:
                failures.append((corpus_name, *failed))
    return cases, failures


def _contract_failures(
    files: dict[str, str], shape_files: dict[str, str]
) -> tuple[int, list[tuple[str, str, str, str]]]:
    """A snapshot's retained family contracts against the modules in ``shape_files``: (cases, failures)."""
    family_path = "specification/validation/test/family-contracts.json"
    if family_path not in files:
        return 0, []
    retained = json.loads(files[family_path])
    modules: dict[str, Graph] = {}
    failures = []
    for row in retained:
        module = row["module"]
        if module not in modules:
            modules[module] = Graph().parse(data=shape_files[module], format="turtle")
        failed = case_failure(modules[module], row)
        if failed is not None:
            failures.append(("family-contracts.json", row["name"], *failed))
    return len(retained), failures


class _Current(dict[str, str]):
    """The working tree's family files, and any other file read on demand by repository-relative path."""

    def __missing__(self, key: str) -> str:
        self[key] = (ROOT / key).read_text(encoding="utf-8")
        return self[key]


def recorded() -> set[Divergence]:
    """The divergences releases/compatibility.json records, each under the change that caused it."""
    record = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    found: set[Divergence] = set()
    for change in record["changes"]:
        assert change.get("changelog") and change.get("summary"), (
            f"{change.get('id')}: a change cites its CHANGELOG section"
        )
        for source, names in change["cases"].items():
            for name, releases in names.items():
                for release in releases:
                    assert (release, source, name) not in found, f"{release} {source} {name!r} is recorded twice"
                    found.add((release, source, name))
    return found


def replay(path: Path, files: dict[str, str], current: dict[str, str]) -> tuple[int, set[Divergence], list[str]]:
    """Replay one snapshot: its cases against its own shapes must all hold (else a problem); against the current
    shapes, each case that no longer holds is a divergence. Returns (cases, divergences, problems)."""
    release = path.parent.name
    problems = []
    corpus = files["specification/validation/test/competency.tsv"]
    count = check_corpus(files, corpus)
    if check_corpus(current, corpus) != count:
        problems.append(f"{release}: the instance corpus counts differently against the current family")
    cases, divergences = count, set()
    for collect in (_corpus_failures, _contract_failures):
        total, own = collect(files, files)
        cases += total
        problems += [
            f"{release}: {source} {name!r} fails against the snapshot's own shapes: {why}"
            for source, name, why, _ in own
        ]
        _, now = collect(files, current)
        divergences |= {(release, source, name) for source, name, _, _ in now}
    return cases, divergences, problems


def compare(observed: set[Divergence], expected: set[Divergence], releases: set[str]) -> list[str]:
    """Divergences the record does not explain, and recorded ones that no longer occur, for the replayed releases."""
    expected = {d for d in expected if d[0] in releases}
    problems = [
        f"{r}: {s} {n!r} no longer holds against the current shapes; record its change in releases/compatibility.json"
        for r, s, n in sorted(observed - expected)
    ]
    problems += [
        f"{r}: {s} {n!r} is recorded as diverging but holds; remove it" for r, s, n in sorted(expected - observed)
    ]
    return problems


def self_test() -> None:
    """The comparison reports an unexplained divergence and a stale record, and nothing when they agree."""
    seen = {("r", "a.tsv", "x")}
    assert compare(seen, seen, {"r"}) == []
    assert "record its change" in compare(seen, set(), {"r"})[0]
    assert "remove it" in compare(set(), seen, {"r"})[0]
    assert compare(set(), seen, {"other"}) == []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", help="Replay only this existing release identifier")
    parser.add_argument(
        "--replay-history", action="store_true", help="Optional historical compatibility audit; not a prerelease gate"
    )
    args = parser.parse_args()
    self_test()
    releases = sorted((ROOT / "releases").glob("*/manifest.json"))
    if args.release:
        releases = [p for p in releases if p.parent.name == args.release]
    assert releases, "No pinned specification snapshot"
    cases = 0
    observed: set[Divergence] = set()
    problems: list[str] = []
    current = _Current({p: (ROOT / p).read_text(encoding="utf-8") for p in specgraph.ontology_paths()})
    for path in releases:
        files, _ = _verify_archive(path)
        if not args.replay_history:
            continue
        count, divergences, found = replay(path, files, current)
        cases, observed, problems = cases + count, observed | divergences, problems + found
    if args.replay_history:
        problems += compare(observed, recorded(), {p.parent.name for p in releases})
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(
        f"PASS: {len(releases)} immutable snapshots verified; historical compatibility replay "
        + (
            f"{cases} cases, {len(observed)} recorded divergences from the current shapes"
            if args.replay_history
            else "not requested (prerelease)"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
