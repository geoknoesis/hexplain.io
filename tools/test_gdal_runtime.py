"""Validate the published evidence denominator, provenance and non-inflated outcome counts.

The expected totals come from the evidence's own counts blocks and cross-references (status
counts against the result list, the documented datatype difference against its entry, the
retained TIFF rejections against the results), not from numbers retyped here.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "specification/coverage/gdal-tests"
CONTRACT_FIELDS = ["name", "implementation", "scope", "range", "evidence", "limits"]


def read(name: str) -> dict[str, Any]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def check_pixel_evidence(evidence: dict[str, Any], manifest: dict[str, Any], inventory: dict[str, Any]) -> None:
    digest = hashlib.sha256((EVIDENCE / "corpus-manifest.json").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    assert digest == evidence["manifest_sha256"]
    assert evidence["corpus_commit"] == manifest["commit"] == evidence["runtime"]["fixture_commit"]
    assert len(manifest["files"]) == evidence["corpus_files"]
    assert sum(f["bytes"] for f in manifest["files"]) == evidence["corpus_bytes"]
    assert len({f["path"] for f in manifest["files"]}) == len(manifest["files"])
    assert {r["key"] for r in evidence["inventory"]} == {r["key"] for r in inventory["drivers"]}
    # The counts block is the denominator; the result list must add up to it exactly.
    assert dict(Counter(r["status"] for r in evidence["all_results"])) == evidence["counts"]
    assert evidence["counts"].get("mismatch", 0) == 0
    assert evidence["encoder_checks"], "no encoder round trips recorded"
    assert all(x["status"] == "equal" for x in evidence["encoder_checks"])
    paths = {f["path"]: f for f in manifest["files"]}
    for row in evidence["inventory"]:
        assert dict(Counter(r["status"] for r in row["samples"])) == row["counts"]
        for sample in row["samples"]:
            assert sample["gdal_driver"] in row["runtime_drivers"]
            if sample["source"]:
                assert sample["source"] == paths[sample["path"]]


def check_extended_evidence(evidence: dict[str, Any], extended: dict[str, Any]) -> tuple[int, int]:
    assert extended["counts"] == evidence["counts"]
    # Every documented datatype difference is one explained entry, no more and no fewer.
    assert evidence["counts"].get("documented-type-difference", 0) == len(extended["datatype_difference"])
    for difference in extended["datatype_difference"]:
        assert difference["reason"] and difference["reference"] and len(difference["sha256"]) == 64, difference
        assert any(
            r["path"] == difference["path"] and r["status"] == "documented-type-difference"
            for r in evidence["all_results"]
        ), difference["path"]
    # Every GTiff rejection of the comparison is listed and assessed, no more and no fewer.
    assert sorted(r["path"] for r in extended["retained_tiff_rejections"]) == sorted(
        r["path"] for r in evidence["all_results"] if r["status"] == "hexplain-rejected" and r["gdal_driver"] == "GTiff"
    )
    tests = sum(t["tests"] for t in extended["tests"])
    assert extended["tests"] and all(t["tests"] >= 1 and t["name"] for t in extended["tests"]), extended["tests"]
    assert extended["contracts"], "no adapter contracts"
    assert all(c[k] for c in extended["contracts"] for k in CONTRACT_FIELDS)
    assert len({c["name"] for c in extended["contracts"]}) == len(extended["contracts"]), "duplicate contract names"
    # Public evidence integrity does not require access to proprietary implementation bytes.
    # The private engine release workflow separately verifies these hashes against its checkout.
    for name, digest in extended["sources"].items():
        assert name and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    return len(extended["contracts"]), tests


def main() -> int:
    evidence = read("evidence.json")
    manifest = read("corpus-manifest.json")
    inventory = json.loads((ROOT / "specification/coverage/gdal-drivers.json").read_text(encoding="utf-8"))
    check_pixel_evidence(evidence, manifest, inventory)
    print(
        f"PASS: {len(evidence['inventory'])} GDAL documentation entries, {len(evidence['all_results'])} probes, "
        f"{evidence['counts']['equal']} full-pixel matches, {len(evidence['encoder_checks'])} encoder round trips; "
        "non-passes remain explicit"
    )
    contracts, tests = check_extended_evidence(evidence, read("extended-evidence.json"))
    print(
        f"PASS: {contracts} scoped adapter contracts, {tests} retained tests and well-formed source hashes; "
        "implementation-byte verification belongs to private engine CI"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
