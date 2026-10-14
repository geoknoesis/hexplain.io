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

ROOT = Path(__file__).resolve().parents[1]


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


def _replay_corpora(path: Path, files: dict[str, str]) -> int:
    """Replay the snapshot's TSV corpora against its own shapes and the current ones; return the case count."""
    cases = 0
    for corpus_name, shape_paths in CORPORA:
        corpus_path = "specification/validation/test/" + corpus_name
        if corpus_path not in files:
            continue  # Older immutable releases predate these suites.
        for archived in [True, False]:
            selected = Graph()
            for shape_path in shape_paths:
                selected.parse(
                    data=files[shape_path] if archived else (ROOT / shape_path).read_text(encoding="utf-8"),
                    format="turtle",
                )
            for row in files[corpus_path].splitlines():
                if not row or row.startswith("#"):
                    continue
                name, expected, result_path, encoded = row.split("\t")
                ok, report, detail = validate(
                    Graph().parse(data=base64.b64decode(encoded).decode(), format="turtle"),
                    shacl_graph=selected,
                    inference="none",
                    advanced=False,
                )
                assert bool(ok) == (expected == "true"), (path, name, archived, detail)
                if result_path:
                    assert URIRef(result_path) in report.objects(None, SH.resultPath), (name, detail)
        cases += sum(bool(row) and not row.startswith("#") for row in files[corpus_path].splitlines())
    return cases


def _replay_family_contracts(path: Path, files: dict[str, str]) -> int:
    """Replay the snapshot's retained family contracts, archived and current; return the case count."""
    family_path = "specification/validation/test/family-contracts.json"
    if family_path not in files:
        return 0
    retained = json.loads(files[family_path])
    for archived in [True, False]:
        selected: dict[str, Graph] = {}
        for row in retained:
            module = row["module"]
            if module not in selected:
                selected[module] = Graph().parse(
                    data=files[module] if archived else (ROOT / module).read_text(encoding="utf-8"),
                    format="turtle",
                )
            case_shapes = selected[module]
            if row.get("targetShape"):
                case_shapes = Graph() + case_shapes
                case_shapes.add((URIRef(row["targetShape"]), SH.targetNode, URIRef(row["targetNode"])))
            ok, report, detail = validate(
                Graph().parse(data=row["data"], format="turtle"), shacl_graph=case_shapes, inference="none"
            )
            assert bool(ok) == row["expected"], (path, row["name"], archived, detail)
            if row["path"]:
                assert URIRef(row["path"]) in report.objects(None, SH.resultPath), (row["name"], detail)
            if row.get("expectedShape"):
                assert URIRef(row["expectedShape"]) in report.objects(None, SH.sourceShape), (
                    row["name"],
                    detail,
                )
    return len(retained)


def main() -> int:
    current_files = {p: (ROOT / p).read_text(encoding="utf-8") for p in specgraph.ontology_paths()}
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", help="Replay only this existing release identifier")
    parser.add_argument(
        "--replay-history", action="store_true", help="Optional historical compatibility audit; not a prerelease gate"
    )
    args = parser.parse_args()
    releases = sorted((ROOT / "releases").glob("*/manifest.json"))
    if args.release:
        releases = [p for p in releases if p.parent.name == args.release]
    assert releases, "No pinned specification snapshot"
    cases = 0
    for path in releases:
        files, _ = _verify_archive(path)
        if not args.replay_history:
            continue
        corpus = files["specification/validation/test/competency.tsv"]
        archived_count = check_corpus(files, corpus)
        assert check_corpus(current_files, corpus) == archived_count
        cases += archived_count
        cases += _replay_corpora(path, files)
        cases += _replay_family_contracts(path, files)
    print(
        f"PASS: {len(releases)} immutable snapshots verified; historical compatibility replay "
        + (f"{cases} cases" if args.replay_history else "not requested (prerelease)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
