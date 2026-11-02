"""Reject stale scope, altered package bytes and non-reproducible review artifacts.

The archive is not tracked: the tracked review-manifest.json pins its SHA-256 and every entry's
size and hash, and this gate rebuilds the archive from the tree and checks it against that
record. A local or CI copy of the archive, when present, must be byte-identical too.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from _review_acceptance import problems as acceptance_problems
from _review_candidate import ARCHIVE, OUT, build


def check_extracted(binary: bytes, deadline: float) -> None:
    """The shipped conformance tooling must run with only the extracted package and locked dependencies."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        with zipfile.ZipFile(io.BytesIO(binary)) as archive:
            for entry in archive.infolist():
                assert (root / entry.filename).resolve().is_relative_to(root.resolve())
            archive.extractall(root)
        environment = dict(os.environ, PYTHONUTF8="1")
        environment.pop("PYTHONPATH", None)
        for script in ("test_conformance_suite.py", "test_implementation_reports.py"):
            remaining = deadline - time.monotonic()
            assert remaining > 0, "Review-candidate gate exhausted its shared deadline"
            result = subprocess.run(
                [sys.executable, "-I", str(root / "tools" / script)],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=remaining,
            )
            assert result.returncode == 0, f"extracted {script} failed:\n{result.stdout}\n{result.stderr}"


def acceptance_regressions(manifest: dict[str, Any]) -> None:
    import copy

    valid = copy.deepcopy(manifest)
    valid.update(
        status="accepted",
        decision="accepted",
        reviewer="Example independent reviewer",
        reviewed_at="2026-10-16T12:00:00Z",
    )
    for module in valid["module_reviews"]:
        module["status"] = "accepted"
        module["disposition"] = "Reviewed; no unresolved findings."
    valid.update(
        organization="Example organization",
        conflicts="none declared",
        reviewed_scope="All module rows",
        independence_attested=True,
        reviewed_archive_sha256=valid["archive_sha256"],
        findings=[],
    )
    assert not acceptance_problems(valid)
    for record in (valid, manifest):
        malformed_modules: tuple[object, ...] = (None, [], {}, [None], ["module"])
        for modules in malformed_modules:
            assert acceptance_problems(dict(record, module_reviews=modules)), modules
        for digest in (None, "", "not-a-hash", "A" * 64):
            assert acceptance_problems(dict(record, archive_sha256=digest, reviewed_archive_sha256=digest)), digest
        missing_hashes = dict(record)
        missing_hashes.pop("archive_sha256", None)
        missing_hashes.pop("reviewed_archive_sha256", None)
        assert acceptance_problems(missing_hashes), "two absent hashes must never identify an accepted artifact"
    for key, value in (
        ("reviewed_at", "not a date"),
        ("reviewed_at", True),
        ("reviewed_at", "2026-10-16"),
        ("reviewer", " "),
        ("independence_attested", False),
        ("reviewed_archive_sha256", "0" * 64),
        ("findings", None),
        ("status", "awaiting independent review"),
    ):
        bad = dict(valid, **{key: value})
        assert acceptance_problems(bad), (key, value)
    for status in (None, "done", "unreviewed", "rejected"):
        bad = copy.deepcopy(valid)
        bad["module_reviews"][0]["status"] = status
        assert acceptance_problems(bad), status


def finding_regressions() -> None:
    from _review_acceptance import finding_problems

    finding = dict(
        id="R-1",
        severity="P2",
        affected_iris=["urn:review:term"],
        counterexample="example",
        expected_result="expected",
        disposition="corrected",
        regression_evidence="probe",
        compatibility_impact="none",
        status="resolved",
    )
    assert not finding_problems([finding], True)
    for bad in (
        [{key: True for key in finding}],
        [dict(finding, affected_iris="urn:review:term")],
        [dict(finding, affected_iris=["relative"])],
        [dict(finding, status="open")],
        [finding, finding],
    ):
        assert finding_problems(bad, True), bad


def tracked_regressions() -> None:
    """Only files git tracks are packaged: an untracked file left in a packaged directory changes nothing."""
    from unittest.mock import patch

    import _review_candidate

    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        (root / "tools/sub").mkdir(parents=True)
        for name in ("tools/kept.py", "tools/sub/nested.py", "tools/notes.txt", "tools/stray.py"):
            (root / name).write_text("x\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        add = ["git", "-C", str(root), "add", "tools/kept.py", "tools/sub/nested.py", "tools/notes.txt"]
        subprocess.run(add, check=True)
        with patch.object(_review_candidate, "ROOT", root):
            assert _review_candidate.tracked_files("tools", "*.py") == {"tools/kept.py", "tools/sub/nested.py"}
            assert _review_candidate.tracked_files("tools", recursive=False) == {"tools/kept.py", "tools/notes.txt"}


def main() -> int:
    tracked_regressions()
    gates = json.loads((Path(__file__).parent / "gates.json").read_text(encoding="utf-8"))["gates"]
    budget = next(gate["timeout"] for gate in gates if gate["name"] == "test_review_candidate")
    deadline = time.monotonic() + budget
    manifest, audit, binary = build()
    actual = json.loads((OUT / "review-manifest.json").read_text(encoding="utf-8"))
    instructions = (OUT / "review-instructions.md").read_text(encoding="utf-8")
    table = instructions.split("| Module |", 1)[1].split("\n## Evidence boundaries", 1)[0]
    rows = [line.split("|")[1:3] for line in table.splitlines() if line.startswith("| specification/")]
    assert [(module.strip(), int(count)) for module, count in rows] == [
        (m["module"], m["resources"]) for m in manifest["module_reviews"]
    ], "Independent review instructions omit modules or contain stale resource counts"
    # Review decisions may be added without changing the frozen artifact inventory.
    # This validates record completeness only, never the identity/independence of a signer.
    review_fields = {
        "status",
        "reviewer",
        "reviewed_at",
        "decision",
        "module_reviews",
        "organization",
        "conflicts",
        "reviewed_scope",
        "independence_attested",
        "reviewed_archive_sha256",
        "findings",
    }
    assert {k: v for k, v in actual.items() if k not in review_fields} == {
        k: v for k, v in manifest.items() if k not in review_fields
    }, "Review candidate metadata is stale; regenerate the pending package with `python tools/_review_candidate.py`"
    assert [(m["module"], m["resources"]) for m in actual["module_reviews"]] == [
        (m["module"], m["resources"]) for m in manifest["module_reviews"]
    ]
    assert not acceptance_problems(actual), acceptance_problems(actual)
    acceptance_regressions(manifest)
    finding_regressions()
    assert json.loads((OUT / "constraint-inventory.json").read_text(encoding="utf-8")) == audit
    assert actual["archive"] == ARCHIVE and actual["archive_tracked"] is False
    assert hashlib.sha256(binary).hexdigest() == actual["archive_sha256"], "Archive differs from the pinned digest"
    with zipfile.ZipFile(io.BytesIO(binary)) as z:
        assert all(item.create_system == 3 for item in z.infolist()), (
            "Archive creator metadata must be platform-independent"
        )
        assert len(z.namelist()) == len(set(z.namelist())) == len(actual["files"])
        for item in actual["files"]:
            data = z.read(item["path"])
            assert len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["sha256"], item["path"]
    local = OUT / ARCHIVE
    if local.is_file():
        assert local.read_bytes() == binary, "The local archive copy differs from the tree; rerun --archive-only"
    assert build()[2] == binary, "Candidate build is not deterministic"
    check_extracted(binary, deadline)
    print(
        f"PASS: reproducible {len(actual['files'])}-file review candidate, {actual['resources']} resources, "
        f"archive pinned by manifest; review decision: {actual['decision'] or 'pending'} "
        "(identity is not authenticated by this gate)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
