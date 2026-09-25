"""Every normative requirement sentence carries one stable, registered identifier.

The processor conformance suite cites requirements by identifier, so an identifier may never
silently change meaning: a registered requirement whose text changes, or whose anchor
disappears, must be named in CHANGELOG.md (see tools/_requirement_ids.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _requirement_ids as ids  # noqa: E402


def self_test():
    entry = {"page": "specification/processing/index.html", "section": "x", "cls": "physical-parser",
             "level": "MUST", "text": "A MUST hold.", "sha256": "a"}
    changed = dict(entry, text="A MUST hold, now.", sha256="b")
    _, problems = ids.reconcile({"req-pm-x-1": changed}, {"req-pm-x-1": entry}, changelog="")
    assert problems, "a requirement whose text changed with no CHANGELOG entry went unnoticed"
    merged, problems = ids.reconcile({"req-pm-x-1": changed}, {"req-pm-x-1": entry}, changelog="req-pm-x-1")
    assert not problems and merged["req-pm-x-1"]["history"] == ["a"], "a recorded change must keep the old hash"
    _, problems = ids.reconcile({}, {"req-pm-x-1": entry}, changelog="")
    assert problems, "a requirement whose anchor disappeared went unnoticed"
    merged, problems = ids.reconcile({}, {"req-pm-x-1": entry}, changelog="req-pm-x-1")
    assert not problems and merged["req-pm-x-1"]["withdrawn"], "a recorded removal must stay registered, withdrawn"
    _, problems = ids.reconcile({"req-pm-x-1": entry}, {"req-pm-x-1": dict(entry, withdrawn=True)}, changelog="req-pm-x-1")
    assert problems, "a withdrawn identifier was reused"
    # Exact names only: req-pm-x-1 is not named by an entry for req-pm-x-10.
    _, problems = ids.reconcile({"req-pm-x-1": changed}, {"req-pm-x-1": entry}, changelog="req-pm-x-10 and req-pm-x-15")
    assert problems, "a CHANGELOG entry for req-pm-x-10 was read as naming req-pm-x-1"
    # Only the pending section counts: an old snapshot's mention records an old change.
    log = "\n".join(["# Changelog", "", "## Unreleased", "", "Nothing.", "", "## Snapshot 1", "",
                     "req-pm-x-1 changed.", ""])
    _, problems = ids.reconcile({"req-pm-x-1": changed}, {"req-pm-x-1": entry}, changelog=ids.pending_changes(log))
    assert problems, "a mention in an older snapshot's section excused a pending change"
    assert ids.names(ids.pending_changes(log.replace("Nothing.", "req-pm-x-1 again.")), "req-pm-x-1")
    page = "specification/processing/index.html"
    found = ids.sentences(page, '<section id="s"><p>The key words "MUST" and "SHOULD" apply. '
                                '<span class="req" id="req-pm-s-1"></span>A thing MUST hold. Nothing here.</p></section>')
    required = [s for s in found if s.is_requirement]
    assert [s.anchors for s in required] == [["req-pm-s-1"]], "the boilerplate sentence counted, or the anchor was lost"
    # An empty link reads as its target's title, and a superscript as a power.
    found = ids.sentences(page, '<section id="s"><h2>Sizes</h2><p><span class="req" id="req-pm-s-1"></span>'
                                'A count MUST stay below 2<sup>63</sup> (see <a href="#s"></a>).</p></section>')
    assert found[0].text == "A count MUST stay below 2^63 (see Sizes).", found[0].text


if __name__ == "__main__":
    self_test()
    # Every sentence-level rule names a registered requirement, and every shape a shape-backed
    # requirement names is a shape of the family: a renamed shape must not leave a dead link.
    import specgraph
    from rdflib import RDF, URIRef
    from rdflib.namespace import SH
    registry = ids.load_registry()["requirements"]
    family = specgraph.ontologies()
    shapes = set(family.subjects(RDF.type, SH.NodeShape))
    stale = [i for i in (*ids.CLASS_OVERRIDE, *ids.DESCRIPTION_AUDIENCE, *ids.SHAPE_BACKED)
             if i not in registry or registry[i].get("withdrawn")]
    missing = [(i, s) for i, names in ids.SHAPE_BACKED.items() for s in names if URIRef(s) not in shapes]
    if stale or missing:
        print(f"FAIL: rules name unregistered requirements {stale} or missing shapes {missing}")
        sys.exit(1)
    sys.exit(ids.main(["--check"]))
