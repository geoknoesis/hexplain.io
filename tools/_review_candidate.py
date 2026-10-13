"""Rebuild a deterministic review package; never manufactures reviewer acceptance.

The package is a ZIP of the canonical ontologies, shapes, generated documentation, fixtures and
gate tools. Its manifest (review-manifest.json: the archive's SHA-256 and every entry's size and
hash) and the constraint inventory are tracked; the archive itself is not, since it only repeats
22 MB of files the tree already holds. ``--archive-only`` rebuilds the archive from the tree,
checks it against the tracked manifest and writes it beside the manifest, which is how the
validate workflow produces the downloadable artifact a reviewer receives.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import specgraph
from rdflib import Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "specification/ontology-review"
ARCHIVE = "ontology-review-candidate.zip"
SH = Namespace("http://www.w3.org/ns/shacl#")


def text_bytes(path: str) -> bytes:
    """A tracked text file's bytes with the platform newline normalised away."""
    return (ROOT / path).read_text(encoding="utf-8").encode("utf-8")


def _shape_inventory(modules: list[dict[str, Any]], trace: dict[str, Any]) -> dict[str, Any]:
    refs = {r["iri"]: r for r in trace["resources"]}
    requirements = []
    for path in sorted(specgraph.ontology_paths()):
        graph = Graph().parse(data=text_bytes(path), format="turtle")
        for shape in sorted(set(graph.subjects(None, SH.NodeShape)), key=str):
            if not isinstance(shape, URIRef):
                continue
            paths = sorted(
                {
                    str(p)
                    for prop in graph.objects(shape, SH.property)
                    for p in graph.objects(prop, SH.path)
                    if isinstance(p, URIRef)
                }
            )
            requirements.append(
                dict(
                    shape=str(shape),
                    source=path,
                    targets=sorted(
                        str(o)
                        for pred in [SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf]
                        for o in graph.objects(shape, pred)
                    ),
                    direct_property_paths=paths,
                    candidate_cases=sorted(
                        {
                            c
                            for p in paths
                            for c in refs.get(p, {}).get("positive", []) + refs.get(p, {}).get("negative", [])
                        }
                    ),
                    review_status="needs constraint-level review",
                )
            )
    return dict(
        scope=(
            "Named node-shape inventory. Direct path references are discovery aids, not proof of activation or "
            "constraint coverage. Nested paths, SPARQL and ontology axioms require manual review."
        ),
        resources=trace["summary"]["resources"],
        shapes=requirements,
    )


def _payload_paths(modules: list[dict[str, Any]]) -> set[str]:
    paths = set(specgraph.ontology_paths())
    paths.update(
        p.relative_to(ROOT).as_posix() for p in (ROOT / "specification/validation/test").glob("*") if p.is_file()
    )
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "tools").glob("*.py"))
    paths.update(m["page"] for m in modules)
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / "authoring/specification").rglob("*") if p.is_file())
    paths.update(
        [
            "specification/print.css",
            "specification/shared-patterns/index.html",
            "specification/processing/index.html",
            "specification/hel/index.html",
            "specification/coverage/writer-tests/index.html",
            "specification/evidence/2026-09-05/simplification/baseline.json",
            "specification/evidence/2026-09-05/simplification/baseline.zip",
            "specification/evidence/2026-09-05/simplification/equivalence-matrix.json",
            "requirements.txt",
            "requirements-browser.txt",
            "specification/family.json",
            "specification/coverage/profile-catalog.json",
            "specification/reference/manifest.json",
            "specification/validation/competency-trace.json",
            "specification/validation/constraint-coverage.json",
            "specification/ontology-review/review-instructions.md",
            "specification/ontology-review/governance.md",
            "specification/ontology-review/candidate-migration.md",
            "specification/coverage/gdal-tests/vector-semantic-candidate.json",
            "tools/gates.json",
        ]
    )
    return paths


def build() -> tuple[dict[str, Any], dict[str, Any], bytes]:
    """The manifest, the constraint inventory and the archive bytes, all from the current tree."""
    modules = json.loads(text_bytes("specification/reference/manifest.json"))
    trace = json.loads(text_bytes("specification/validation/competency-trace.json"))
    audit = _shape_inventory(modules, trace)
    payload = {}
    for path in sorted(_payload_paths(modules)):
        payload[path] = (ROOT / path).read_bytes() if path.endswith(".zip") else text_bytes(path)
    payload["specification/ontology-review/constraint-inventory.json"] = (json.dumps(audit, indent=2) + "\n").encode()
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, data in sorted(payload.items()):
            info = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    binary = content.getvalue()
    manifest = dict(
        status="awaiting independent review",
        reviewer=None,
        reviewed_at=None,
        decision=None,
        resources=sum(m["terms"] for m in modules),
        modules=len(modules),
        hash_policy=(
            "SHA-256 of exact archive entry bytes; source UTF-8 text normalized to LF before packaging. "
            "Historical release archives are unchanged."
        ),
        archive=ARCHIVE,
        archive_sha256=hashlib.sha256(binary).hexdigest(),
        archive_tracked=False,
        archive_note=(
            "The archive is rebuilt from the tree by `python tools/_review_candidate.py --archive-only` and "
            "retained as a workflow artifact; its bytes are pinned by archive_sha256 and the entry hashes below."
        ),
        scope=(
            "Canonical ontologies, shapes, generated module documentation, validation fixtures and offline gate "
            "tools. Not a signed release or independent acceptance."
        ),
        module_reviews=[dict(module=m["module"], resources=m["terms"], status="unreviewed") for m in modules],
        files=[dict(path=p, bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for p, b in sorted(payload.items())],
    )
    return manifest, audit, binary


def write_archive(binary: bytes) -> Path:
    """Write the archive beside the manifest after checking it is the one the manifest pins."""
    tracked = json.loads((OUT / "review-manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(binary).hexdigest()
    if digest != tracked["archive_sha256"]:
        raise SystemExit(
            f"The tree no longer matches review-manifest.json (archive {digest[:12]} vs pinned "
            f"{tracked['archive_sha256'][:12]}); rebuild the candidate with `python tools/_review_candidate.py`."
        )
    target = OUT / tracked["archive"]
    target.write_bytes(binary)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--archive-only",
        action="store_true",
        help="Rebuild only the (untracked) archive and check it against the tracked manifest; never touch the manifest",
    )
    args = parser.parse_args()
    manifest, audit, binary = build()
    if args.archive_only:
        target = write_archive(binary)
        print(f"Wrote {target.relative_to(ROOT).as_posix()} ({len(binary)} bytes), matching review-manifest.json")
        return 0
    old = json.loads((OUT / "review-manifest.json").read_text(encoding="utf-8"))
    if old.get("reviewer") or old.get("decision"):
        raise SystemExit("Preserve the attributable review before creating a different candidate.")
    (OUT / "review-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT / "constraint-inventory.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8", newline="\n")
    (OUT / ARCHIVE).write_bytes(binary)
    print(f"Prepared {manifest['resources']} resources, {len(manifest['files'])} files; independent acceptance pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
