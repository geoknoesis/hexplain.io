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
    page = "specification/processing/index.html"
    found = ids.sentences(page, '<section id="s"><p>The key words "MUST" and "SHOULD" apply. '
                                '<span class="req" id="req-pm-s-1"></span>A thing MUST hold. Nothing here.</p></section>')
    required = [s for s in found if s.is_requirement]
    assert [s.anchors for s in required] == [["req-pm-s-1"]], "the boilerplate sentence counted, or the anchor was lost"


if __name__ == "__main__":
    self_test()
    sys.exit(ids.main(["--check"]))
