"""A published version IRI names one graph: every snapshot, and the working tree, agree on it.

An owl:versionIRI is the identifier a consumer pins. Two snapshots that freeze different content
under one version IRI make that pin meaningless, and a working-tree module that changes its
content without a new version IRI will be frozen under a name that already means something else.
This gate parses every Turtle file of every snapshot under releases/ and of the family, groups
the ontologies by owl:versionIRI, and requires the graphs of one version IRI to be isomorphic
(comments and whitespace do not count; blank nodes are compared by structure).

Two version IRIs were frozen with different content before this gate existed, and frozen
snapshots are never rewritten; they are listed in KNOWN_VIOLATIONS with the snapshots involved
and the erratum that records them (releases/ERRATA.md). The list may only shrink: a new
violation fails, and so does a listed one that no longer occurs or that spreads to a snapshot
not listed.
"""
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from rdflib import OWL, RDF, Graph, URIRef
from rdflib.compare import isomorphic, to_isomorphic

import specgraph

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
ERRATA = "releases/ERRATA.md"
#: version IRI -> (the snapshots whose content differs from the earliest one, erratum anchor)
KNOWN_VIOLATIONS = {
    "https://hexplain.io/ns/bddo/1.0": ({"2026-09-08.1", "2026-09-08.2"}, "E1"),
    "https://hexplain.io/ns/aspect/bundle/1.2": ({"2026-09-08.1", "2026-09-08.2"}, "E2"),
}


def snapshot_graphs():
    """(release, path, graph) for every Turtle file of every snapshot."""
    for manifest_path in sorted(RELEASES.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(manifest_path.parent / manifest["archive"]) as archive:
            for item in manifest["files"]:
                if item["path"].endswith(".ttl"):
                    data = archive.read(item["path"]).decode("utf-8")
                    yield manifest["releaseId"], item["path"], Graph().parse(data=data, format="turtle")


def working_graphs():
    for path in specgraph.ontology_paths():
        yield "working tree", path, Graph().parse(data=(ROOT / path).read_text(encoding="utf-8"), format="turtle")


def versions(sources):
    """version IRI -> [(where, path, graph)]"""
    out = defaultdict(list)
    for where, path, g in sources:
        for ontology in g.subjects(RDF.type, OWL.Ontology):
            version = g.value(ontology, OWL.versionIRI)
            if isinstance(version, URIRef):
                out[str(version)].append((where, path, g))
    return out


def differing(entries):
    """The places whose graph differs from the first place's (the earliest snapshot)."""
    first = to_isomorphic(entries[0][2])
    return {where for where, _, g in entries[1:] if not isomorphic(first, g)}


def check(by_version, known):
    problems, seen = [], set()
    for version, entries in sorted(by_version.items()):
        diff = differing(entries)
        if not diff:
            continue
        snapshots = {w for w in diff if w != "working tree"}
        if "working tree" in diff:
            problems.append(f"{version}: the working tree changes the content of a version a snapshot froze "
                            f"({entries[0][0]}); give the module a new owl:versionIRI and owl:priorVersion")
        if snapshots:
            allowed, erratum = known.get(version, (set(), None))
            if snapshots != allowed:
                problems.append(f"{version}: snapshots {sorted(snapshots)} freeze content different from "
                                f"{entries[0][0]}" + (f" (the erratum lists {sorted(allowed)})" if erratum else ""))
            seen.add(version)
    for version in known:
        if version not in seen:
            problems.append(f"{version}: listed as a known violation, but every snapshot now agrees; remove it")
    return problems


def self_test():
    a = Graph().parse(format="turtle", data="<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ; "
                      "<http://www.w3.org/2002/07/owl#versionIRI> <urn:o/1> . <urn:t> <urn:p> 1 .")
    b = Graph().parse(format="turtle", data="# another comment\n<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ;\n"
                      "   <http://www.w3.org/2002/07/owl#versionIRI> <urn:o/1> .\n<urn:t> <urn:p> 1 .")
    c = Graph().parse(format="turtle", data="<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ; "
                      "<http://www.w3.org/2002/07/owl#versionIRI> <urn:o/1> . <urn:t> <urn:p> 2 .")
    assert not check(versions([("s1", "x", a), ("s2", "x", b)]), {}), "comments and layout changed the verdict"
    assert check(versions([("s1", "x", a), ("s2", "x", c)]), {}), "changed content under one version IRI passed"
    assert check(versions([("s1", "x", a), ("working tree", "x", c)]), {}), "an unversioned working-tree change passed"
    assert check(versions([("s1", "x", a), ("s2", "x", b)]), {"urn:o/1": ({"s2"}, "E0")}), "a stale allowance passed"


LINEAGE = RELEASES / "lineage.json"
#: Frozen versions whose stated owl:priorVersion is wrong (ERRATA.md E3, E4): version IRI ->
#: (erratum, the predecessor to read instead, or None when the version is its module's first).
CORRECTED_PRIORS = {
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


def _git(*args):
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def snapshot_commit(release):
    """The commit that added the snapshot's manifest, or None without git history."""
    out = _git("log", "--diff-filter=A", "--format=%H", "--", f"releases/{release}/manifest.json")
    return out.decode().split()[-1] if out and out.split() else None


def lineage():
    """Snapshots with their commits, and every module's versions in the order they were frozen."""
    snapshots, modules = [], defaultdict(dict)
    for manifest_path in sorted(RELEASES.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        release = manifest["releaseId"]
        snapshots.append({"id": release, "commit": snapshot_commit(release), "archiveSha256": manifest["sha256"]})
    for where, _, g in [*snapshot_graphs(), *working_graphs()]:
        for ontology in g.subjects(RDF.type, OWL.Ontology):
            version = g.value(ontology, OWL.versionIRI)
            if not isinstance(version, URIRef):
                continue
            entry = modules[str(ontology)].setdefault(str(version), {
                "versionIri": str(version), "versionInfo": str(g.value(ontology, OWL.versionInfo) or ""),
                "statedPriorVersion": str(g.value(ontology, OWL.priorVersion) or "") or None, "snapshots": []})
            if where != "working tree" and where not in entry["snapshots"]:
                entry["snapshots"].append(where)
    out = {}
    for ontology, versions_ in sorted(modules.items()):
        chain, previous = [], None
        for version in sorted(versions_.values(), key=lambda v: (v["snapshots"][0] if v["snapshots"] else "~",
                                                                  [int(n) for n in v["versionIri"].rsplit("/", 1)[-1].split(".") if n.isdigit()])):
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
    return {"schemaVersion": 1,
            "description": "Snapshots with the commit that added each, and every module version in the order the snapshots froze it; priorVersion is the stated owl:priorVersion, corrected where releases/ERRATA.md says so. Versions with unreleased true are in the working tree only.",
            "snapshots": snapshots, "modules": out}


def check_lineage(write):
    computed = lineage()
    expected = json.dumps(computed, indent=1, ensure_ascii=False) + "\n"
    if write:
        LINEAGE.write_text(expected, encoding="utf-8", newline="\n")
    stored = json.loads(LINEAGE.read_text(encoding="utf-8")) if LINEAGE.is_file() else None
    if stored is not None:
        # A snapshot's commit exists only once the snapshot is committed, and a shallow clone has
        # none: an unknown commit on either side is not staleness.
        known = {s["id"]: s["commit"] for s in stored["snapshots"]}
        for snapshot in computed["snapshots"]:
            if snapshot["commit"] is None or known.get(snapshot["id"], "") is None:
                snapshot["commit"] = known.get(snapshot["id"])
    if stored != computed:
        return ["releases/lineage.json is stale; run python tools/test_version_immutability.py --write"]
    problems = []
    for snapshot in json.loads(expected)["snapshots"]:
        if snapshot["commit"] is None:
            continue    # no git history: the commit cannot be checked, and lineage() recorded none
        recorded = _git("show", f"{snapshot['commit']}:releases/{snapshot['id']}/manifest.json")
        if recorded is None or json.loads(recorded)["sha256"] != snapshot["archiveSha256"]:
            problems.append(f"snapshot {snapshot['id']}: commit {snapshot['commit']} does not hold its manifest")
    for chain in json.loads(expected)["modules"].values():
        released = [v for v in chain if not v["unreleased"]]
        for earlier, later in zip(released, released[1:], strict=False):
            if later["priorVersion"] != earlier["versionIri"]:
                problems.append(f"{later['versionIri']}: its prior version is {later['priorVersion']}, but the version "
                                f"frozen before it is {earlier['versionIri']}; record the correction in {ERRATA}")
        pending = [v for v in chain if v["unreleased"]]
        if pending and released and pending[0]["priorVersion"] != released[-1]["versionIri"]:
            problems.append(f"{pending[0]['versionIri']}: names {pending[0]['priorVersion']} as its prior version; "
                            f"the latest frozen version is {released[-1]['versionIri']}")
    return problems


def main():
    self_test()
    if not (ROOT / ERRATA).is_file():
        print(f"FAIL: {ERRATA} is missing; it records the known violations")
        return 1
    errata = (ROOT / ERRATA).read_text(encoding="utf-8")
    missing = [anchor for _, anchor in KNOWN_VIOLATIONS.values() if f"## {anchor}" not in errata]
    if missing:
        print(f"FAIL: {ERRATA} has no entry {missing}")
        return 1
    by_version = versions([*snapshot_graphs(), *working_graphs()])
    problems = check(by_version, KNOWN_VIOLATIONS) + check_lineage("--write" in sys.argv)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    snapshots = len(list(RELEASES.glob("*/manifest.json")))
    print(f"PASS: {len(by_version)} version IRIs across {snapshots} snapshots and the working tree each name one "
          f"graph ({len(KNOWN_VIOLATIONS)} frozen violations recorded in {ERRATA})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
