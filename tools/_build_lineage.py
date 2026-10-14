"""Write or check releases/lineage.json, the version lineage of the pinned snapshots.

The lineage records every snapshot under releases/ with the commit that added it and its
archive's SHA-256, and every module's versions in the order the snapshots froze them, with the
stated owl:priorVersion corrected where releases/ERRATA.md says so; versions in the working tree
only are marked unreleased. ``--write`` regenerates it (after a snapshot or a new version IRI);
``--check`` exits 1 when it is stale. The gate ``tools/test_version_immutability.py`` checks
the same and that the prior versions chain; it writes nothing.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import specgraph
from rdflib import OWL, RDF, Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"

#: Where a graph was read (a release identifier or the working tree), its path and the graph.
Source = tuple[str, str, Graph]


def snapshot_graphs() -> Iterator[Source]:
    """(release, path, graph) for every Turtle file of every snapshot."""
    for manifest_path in sorted(RELEASES.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(manifest_path.parent / manifest["archive"]) as archive:
            for item in manifest["files"]:
                if item["path"].endswith(".ttl"):
                    data = archive.read(item["path"]).decode("utf-8")
                    yield manifest["releaseId"], item["path"], Graph().parse(data=data, format="turtle")


def working_graphs() -> Iterator[Source]:
    for path in specgraph.ontology_paths():
        yield "working tree", path, Graph().parse(data=(ROOT / path).read_text(encoding="utf-8"), format="turtle")


LINEAGE = RELEASES / "lineage.json"
#: Frozen versions whose stated owl:priorVersion is wrong (ERRATA.md E3, E4): version IRI ->
#: (erratum, the predecessor to read instead, or None when the version is its module's first).
CORRECTED_PRIORS: dict[str, tuple[str | None, str | None]] = {
    "https://hexplain.io/ns/aspect/raster/1.1": ("E3", None),
    "https://hexplain.io/ns/aspect/spatialref/1.1": ("E3", None),
    "https://hexplain.io/ns/aspect/geometry/1.1": ("E3", None),
    "https://hexplain.io/ns/aspect/bundle/1.1": ("E4", "https://hexplain.io/ns/aspect/bundle/1.0"),
    "https://hexplain.io/ns/aspect/bundle/1.2": ("E4", "https://hexplain.io/ns/aspect/bundle/1.1"),
    "https://hexplain.io/ns/dlv/1.1": ("E4", "https://hexplain.io/ns/dlv/1.0"),
    "https://hexplain.io/ns/aspect/networkflow/1.1": ("E4", "https://hexplain.io/ns/aspect/networkflow/1.0"),
    "https://hexplain.io/ns/net/1.1": ("E4", "https://hexplain.io/ns/net/1.0"),
    "https://hexplain.io/ns/register/geometry-type/1.1": ("E4", "https://hexplain.io/ns/register/geometry-type/1.0"),
}


def git(*args: str) -> bytes | None:
    import subprocess

    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def snapshot_commit(release: str) -> str | None:
    """The commit that added the snapshot's manifest, or None without git history."""
    out = git("log", "--diff-filter=A", "--format=%H", "--", f"releases/{release}/manifest.json")
    return out.decode().split()[-1] if out and out.split() else None


def lineage(sources: Iterable[Source]) -> dict[str, Any]:
    """Snapshots with their commits, and every module's versions in ``sources`` in the order they were frozen."""
    snapshots: list[dict[str, Any]] = []
    modules: defaultdict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for manifest_path in sorted(RELEASES.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        release = manifest["releaseId"]
        snapshots.append({"id": release, "commit": snapshot_commit(release), "archiveSha256": manifest["sha256"]})
    for where, _, g in sources:
        for ontology in g.subjects(RDF.type, OWL.Ontology):
            version = g.value(ontology, OWL.versionIRI)
            if not isinstance(version, URIRef):
                continue
            entry = modules[str(ontology)].setdefault(
                str(version),
                {
                    "versionIri": str(version),
                    "versionInfo": str(g.value(ontology, OWL.versionInfo) or ""),
                    "statedPriorVersion": str(g.value(ontology, OWL.priorVersion) or "") or None,
                    "snapshots": [],
                },
            )
            if where != "working tree" and where not in entry["snapshots"]:
                entry["snapshots"].append(where)
    return {
        "schemaVersion": 1,
        "description": "Snapshots with the commit that added each, and every module version in the order the "
        "snapshots froze "
        "it; priorVersion is the stated owl:priorVersion, corrected where releases/ERRATA.md says so. Versions "
        "with unreleased true are in the working tree only.",
        "snapshots": snapshots,
        "modules": _chains(modules),
    }


def _chains(modules: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Each module's versions in the order the snapshots froze them, with corrected prior versions."""
    out = {}
    for ontology, versions_ in sorted(modules.items()):
        chain, previous = [], None
        for version in sorted(
            versions_.values(),
            key=lambda v: (
                v["snapshots"][0] if v["snapshots"] else "~",
                [int(n) for n in v["versionIri"].rsplit("/", 1)[-1].split(".") if n.isdigit()],
            ),
        ):
            erratum, corrected = CORRECTED_PRIORS.get(version["versionIri"], (None, version["statedPriorVersion"]))
            version["priorVersion"] = corrected
            if erratum:
                version["erratum"] = erratum
            version["unreleased"] = not version["snapshots"]
            if previous and corrected != previous:
                version["note"] = f"frozen after {previous}, but names {corrected} as its prior version"
            chain.append(version)
            previous = version["versionIri"]
        out[ontology] = chain
    return out


def render(computed: dict[str, Any]) -> str:
    """The file's text for a computed lineage."""
    return json.dumps(computed, indent=1, ensure_ascii=False) + "\n"


def is_current(computed: dict[str, Any]) -> bool:
    """Whether the stored lineage is ``computed``; reconciles ``computed``'s unknown commits with it.

    A snapshot's commit exists only once the snapshot is committed, and a shallow clone has none:
    an unknown commit on either side is not staleness.
    """
    stored = json.loads(LINEAGE.read_text(encoding="utf-8")) if LINEAGE.is_file() else None
    if stored is not None:
        known = {s["id"]: s["commit"] for s in stored["snapshots"]}
        for snapshot in computed["snapshots"]:
            if snapshot["commit"] is None or known.get(snapshot["id"], "") is None:
                snapshot["commit"] = known.get(snapshot["id"])
    return bool(stored == computed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate releases/lineage.json")
    mode.add_argument("--check", action="store_true", help="Exit 1 if releases/lineage.json is stale")
    args = parser.parse_args(argv)
    computed = lineage([*snapshot_graphs(), *working_graphs()])
    if args.write:
        LINEAGE.write_text(render(computed), encoding="utf-8", newline="\n")
        print(f"Wrote {len(computed['modules'])} module lineages to releases/lineage.json")
        return 0
    if not is_current(computed):
        print("STALE: releases/lineage.json is not what the snapshots and working tree give; run this with --write")
        return 1
    print(f"CURRENT: releases/lineage.json holds {len(computed['snapshots'])} snapshots")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
