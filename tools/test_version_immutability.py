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

The gate also requires releases/lineage.json to be current and every module's frozen versions to
name their predecessors. It only checks: the lineage is written by
``python tools/_build_lineage.py --write``.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from collections.abc import Iterable

from _build_lineage import RELEASES, ROOT, Source, git, is_current, lineage, render, snapshot_graphs, working_graphs
from rdflib import OWL, RDF, Graph, URIRef
from rdflib.compare import isomorphic, to_isomorphic

ERRATA = "releases/ERRATA.md"
#: version IRI -> (the snapshots whose content differs from the earliest one, erratum anchor)
KNOWN_VIOLATIONS = {
    "https://hexplain.io/ns/bddo/1.0": ({"2026-09-08.1", "2026-09-08.2"}, "E1"),
    "https://hexplain.io/ns/aspect/bundle/1.2": ({"2026-09-08.1", "2026-09-08.2"}, "E2"),
}


def versions(sources: Iterable[Source]) -> defaultdict[str, list[Source]]:
    """version IRI -> [(where, path, graph)]"""
    out: defaultdict[str, list[Source]] = defaultdict(list)
    for where, path, g in sources:
        for ontology in g.subjects(RDF.type, OWL.Ontology):
            version = g.value(ontology, OWL.versionIRI)
            if isinstance(version, URIRef):
                out[str(version)].append((where, path, g))
    return out


def differing(entries: list[Source]) -> set[str]:
    """The places whose graph differs from the first place's (the earliest snapshot)."""
    first = to_isomorphic(entries[0][2])
    return {where for where, _, g in entries[1:] if not isomorphic(first, g)}


def check(by_version: dict[str, list[Source]], known: dict[str, tuple[set[str], str]]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for version, entries in sorted(by_version.items()):
        diff = differing(entries)
        if not diff:
            continue
        snapshots = {w for w in diff if w != "working tree"}
        if "working tree" in diff:
            problems.append(
                f"{version}: the working tree changes the content of a version a snapshot froze "
                f"({entries[0][0]}); give the module a new owl:versionIRI and owl:priorVersion"
            )
        if snapshots:
            allowed, erratum = known.get(version, (set(), None))
            if snapshots != allowed:
                problems.append(
                    f"{version}: snapshots {sorted(snapshots)} freeze content different from "
                    f"{entries[0][0]}" + (f" (the erratum lists {sorted(allowed)})" if erratum else "")
                )
            seen.add(version)
    for version in known:
        if version not in seen:
            problems.append(f"{version}: listed as a known violation, but every snapshot now agrees; remove it")
    return problems


def self_test() -> None:
    a = Graph().parse(
        format="turtle",
        data="<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ; "
        "<http://www.w3.org/2002/07/owl#versionIRI> <urn:o/1> . <urn:t> <urn:p> 1 .",
    )
    b = Graph().parse(
        format="turtle",
        data="# another comment\n<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ;\n"
        "   <http://www.w3.org/2002/07/owl#versionIRI> <urn:o/1> .\n<urn:t> <urn:p> 1 .",
    )
    c = Graph().parse(
        format="turtle",
        data="<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ; "
        "<http://www.w3.org/2002/07/owl#versionIRI> <urn:o/1> . <urn:t> <urn:p> 2 .",
    )
    assert not check(versions([("s1", "x", a), ("s2", "x", b)]), {}), "comments and layout changed the verdict"
    assert check(versions([("s1", "x", a), ("s2", "x", c)]), {}), "changed content under one version IRI passed"
    assert check(versions([("s1", "x", a), ("working tree", "x", c)]), {}), "an unversioned working-tree change passed"
    assert check(versions([("s1", "x", a), ("s2", "x", b)]), {"urn:o/1": ({"s2"}, "E0")}), "a stale allowance passed"


def check_lineage(sources: Iterable[Source]) -> list[str]:
    """Whether releases/lineage.json is current, and whether every module's prior versions chain."""
    computed = lineage(sources)
    expected = render(computed)
    if not is_current(computed):
        return ["releases/lineage.json is stale; run python tools/_build_lineage.py --write"]
    problems = []
    for snapshot in json.loads(expected)["snapshots"]:
        if snapshot["commit"] is None:
            continue  # no git history: the commit cannot be checked, and lineage() recorded none
        recorded = git("show", f"{snapshot['commit']}:releases/{snapshot['id']}/manifest.json")
        if recorded is None or json.loads(recorded)["sha256"] != snapshot["archiveSha256"]:
            problems.append(f"snapshot {snapshot['id']}: commit {snapshot['commit']} does not hold its manifest")
    for chain in json.loads(expected)["modules"].values():
        released = [v for v in chain if not v["unreleased"]]
        for earlier, later in zip(released, released[1:], strict=False):
            if later["priorVersion"] != earlier["versionIri"]:
                problems.append(
                    f"{later['versionIri']}: its prior version is {later['priorVersion']}, but the version "
                    f"frozen before it is {earlier['versionIri']}; record the correction in {ERRATA}"
                )
        pending = [v for v in chain if v["unreleased"]]
        if pending and released and pending[0]["priorVersion"] != released[-1]["versionIri"]:
            problems.append(
                f"{pending[0]['versionIri']}: names {pending[0]['priorVersion']} as its prior version; "
                f"the latest frozen version is {released[-1]['versionIri']}"
            )
    return problems


def main() -> int:
    # The old `--write` habit must not look like a pass that regenerated something.
    assert len(sys.argv) == 1, (
        "this gate takes no arguments and writes nothing; releases/lineage.json is written by "
        "`python tools/_build_lineage.py --write`"
    )
    self_test()
    if not (ROOT / ERRATA).is_file():
        print(f"FAIL: {ERRATA} is missing; it records the known violations")
        return 1
    errata = (ROOT / ERRATA).read_text(encoding="utf-8")
    missing = [anchor for _, anchor in KNOWN_VIOLATIONS.values() if f"## {anchor}" not in errata]
    if missing:
        print(f"FAIL: {ERRATA} has no entry {missing}")
        return 1
    sources = [*snapshot_graphs(), *working_graphs()]
    by_version = versions(sources)
    problems = check(by_version, KNOWN_VIOLATIONS) + check_lineage(sources)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    snapshots = len(list(RELEASES.glob("*/manifest.json")))
    print(
        f"PASS: {len(by_version)} version IRIs across {snapshots} snapshots and the working tree each name one "
        f"graph ({len(KNOWN_VIOLATIONS)} frozen violations recorded in {ERRATA})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
