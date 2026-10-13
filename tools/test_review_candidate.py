"""Reject stale scope, altered package bytes and non-reproducible review artifacts.

The archive is not tracked: the tracked review-manifest.json pins its SHA-256 and every entry's
size and hash, and this gate rebuilds the archive from the tree and checks it against that
record. A local or CI copy of the archive, when present, must be byte-identical too.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

from _review_candidate import ARCHIVE, OUT, build


def main() -> int:
    manifest, audit, binary = build()
    actual = json.loads((OUT / "review-manifest.json").read_text(encoding="utf-8"))
    # Review decisions may be added without changing the frozen artifact inventory.
    # This validates record completeness only, never the identity/independence of a signer.
    review_fields = {"status", "reviewer", "reviewed_at", "decision", "module_reviews"}
    assert {k: v for k, v in actual.items() if k not in review_fields} == {
        k: v for k, v in manifest.items() if k not in review_fields
    }, "Review candidate metadata is stale; regenerate the pending package with `python tools/_review_candidate.py`"
    assert [(m["module"], m["resources"]) for m in actual["module_reviews"]] == [
        (m["module"], m["resources"]) for m in manifest["module_reviews"]
    ]
    if actual["decision"] is None:
        assert actual["status"] == "awaiting independent review"
    else:
        assert actual["decision"] in ("accepted", "rejected", "changes requested")
        assert isinstance(actual["reviewer"], str) and actual["reviewer"].strip()
        assert actual["reviewed_at"]
        assert all(m["status"] != "unreviewed" for m in actual["module_reviews"])
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
    print(
        f"PASS: reproducible {len(actual['files'])}-file review candidate, {actual['resources']} resources, "
        f"archive pinned by manifest; review decision: {actual['decision'] or 'pending'} "
        "(identity is not authenticated by this gate)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
