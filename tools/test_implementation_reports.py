"""Implementation reports follow the published format and cover the suite they name.

An implementation report (specification/conformance/index.html#implementation-reports) is the evidence that an
implementation passes the processor conformance suite: one JSON file per run, case id to PASS, FAIL or SKIP with the
error category the implementation reported, naming the build (revision), the environment and the claims it ran with.
tools/conformance/report.py builds one from a run and checks it; this gate checks the checker on a report built from
the suite on disk, then every report published under specification/conformance/reports/, each at the file name its
names and suite digest require.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "conformance"))

import report  # noqa: E402

ENVIRONMENT = {"os": "probe OS 1.0", "jvm": "none", "toolchain": "probe 1.0"}


def self_test() -> int:
    cases = report.suite_cases()
    results = [
        {"case": c, "class": cls, "status": "SKIP", "category": None, "detail": "not run"} for c, cls in cases.items()
    ]
    good = report.build(
        results,
        {"name": "probe", "version": "0", "revision": "0123abcd"},
        {"classes": [], "optionalFeatures": []},
        date="2026-01-01T00:00:00Z",
        environment=ENVIRONMENT,
    )
    assert report.check(good) == [], report.check(good)
    assert report.check(good, path="reports/probe/0-" + good["suite"]["digest"][:12] + ".json") == []
    for mutate, what in (
        (lambda r: r["results"].pop(), "a missing case"),
        (lambda r: r["suite"].update(digest="not-a-sha256"), "an invalid suite digest"),
        (lambda r: r["suite"].update(cases=0), "an incorrect suite case count"),
        (lambda r: r["suite"].update(cases=True), "a boolean suite case count"),
        (lambda r: r["counts"].update(PASS=False), "a boolean status count"),
        (lambda r: r["results"][0].update(category="Parse"), "an unknown category"),
        (lambda r: r["results"][0].update(status="PASSED"), "an unknown status"),
        (lambda r: r["results"][0].update(detail=""), "a skip without a reason"),
        (lambda r: r.update(format="x"), "a wrong format"),
        (lambda r: r["implementation"].pop("version"), "an unversioned implementation"),
        (lambda r: r["implementation"].pop("revision"), "a report without a revision"),
        (lambda r: r["implementation"].update(revision="main"), "a revision that is not a commit"),
        (lambda r: r.pop("formatVersion"), "a version-1 report of the current suite"),
        (lambda r: r.pop("run"), "missing run provenance"),
        (lambda r: r.update(run=[]), "non-object run provenance"),
        (lambda r: r["run"].pop("date"), "a missing run date"),
        (lambda r: r["run"].update(date="2026-02-30T00:00:00Z"), "an impossible run date"),
        (lambda r: r["run"].update(date="2026-01-01T00:00:00"), "a run date without a timezone"),
        (lambda r: r["run"].update(date="2026-01-01T00:00:00+01:00"), "a non-UTC run date"),
        (lambda r: r["run"].update(date=42), "a run date that is not a string"),
        (lambda r: r["run"].pop("runner"), "a missing runner"),
        (lambda r: r["run"].update(runner="  "), "an empty runner"),
        (lambda r: r["run"].update(runner=[]), "a runner that is not a string"),
        (lambda r: r["environment"].update(jvm=""), "an environment without a jvm"),
        (lambda r: r["claims"].update(classes=["x"]), "a claims digest of other claims"),
    ):
        bad = copy.deepcopy(good)
        mutate(bad)
        assert report.check(bad), f"the report check no longer notices {what}"
    assert report.check(good, path="reports/probe/0.json"), "a report at the wrong file name went unnoticed"
    # A version-1 report stays published for an earlier suite only.
    legacy = copy.deepcopy(good)
    legacy.pop("formatVersion")
    legacy.pop("environment")
    legacy.pop("claimsDigest")
    legacy["implementation"].pop("revision")
    legacy["suite"]["digest"] = "0" * 64
    assert report.check(legacy), "unknown historical coverage was accepted"
    assert report.check(legacy, allow_historical=True) == []
    malformed = copy.deepcopy(legacy)
    malformed["suite"]["digest"] = "not-a-sha256"
    assert report.check(malformed, allow_historical=True)
    duplicate = copy.deepcopy(legacy)
    duplicate["results"][1] = copy.deepcopy(duplicate["results"][0])
    assert report.check(duplicate, allow_historical=True)
    skipped = copy.deepcopy(good)
    skipped["claims"]["classes"] = ["Physical Parser"]
    skipped["claimsDigest"] = report.claims_digest(skipped["claims"])
    assert any("applicable case" in problem for problem in report.check(skipped))

    completed = report.complete(copy.deepcopy(legacy), "0123abcd", ENVIRONMENT)
    assert completed["formatVersion"] == 2 and report.check(completed, allow_historical=True) == [], (
        "complete() left the report unchecked"
    )
    for date in ("2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00.123Z"):
        valid = copy.deepcopy(good)
        valid["run"]["date"] = date
        assert report.check(valid) == []
    file_problems(good)
    return len(cases)


def file_problems(good: report.Report) -> None:
    """Rejected completion and interrupted replacement preserve the report's exact original bytes."""
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        path = root / "report.json"
        original = json.dumps(good, indent=3).encode("utf-8")
        path.write_bytes(original)
        with contextlib.redirect_stdout(io.StringIO()):
            assert (
                report.main(
                    ["--complete", str(path), "--revision", "also-invalid", "--os", "probe", "--toolchain", "probe"]
                )
                == 1
            )
        assert path.read_bytes() == original
        missing_run = copy.deepcopy(good)
        missing_run.pop("run")
        assert report.write_validated(path, missing_run)
        assert path.read_bytes() == original
        with patch.object(report.os, "replace", side_effect=OSError("replacement blocked")):
            assert report.write_validated(path, good)
        assert path.read_bytes() == original
        assert not list(root.glob(".report-*.tmp"))
        path.chmod(0o444)
        try:
            with patch.object(report.os, "replace", side_effect=OSError("replacement blocked")):
                assert report.write_validated(path, good)
            assert path.read_bytes() == original
            assert not list(root.glob(".report-*.tmp"))
        finally:
            path.chmod(0o644)
        with contextlib.redirect_stdout(io.StringIO()):
            assert (
                report.main(["--complete", str(path), "--revision", "abcdef0", "--os", "probe", "--toolchain", "probe"])
                == 0
            )
        completed = json.loads(path.read_text(encoding="utf-8"))
        assert completed["implementation"]["revision"] == "abcdef0"
        assert completed["results"] == good["results"] and completed["run"] == good["run"]
        assert report.check(completed) == []
        assert not list(root.glob(".report-*.tmp"))


def main() -> int:
    n = self_test()
    problems = []
    published = report.published()
    for path, data in published:
        problems += [
            f"{path.relative_to(report.SUITE).as_posix()}: {p}"
            for p in report.check(data, path=path, allow_historical=True)
        ]
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(
        f"PASS: the report check holds on a {n}-case suite; {len(published)} published report(s) follow the format "
        "(historical coverage is unverified without its suite)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
