"""Implementation reports follow the published format and cover the suite they name.

An implementation report (specification/conformance/index.html#implementation-reports) is the evidence that an
implementation passes the processor conformance suite: one JSON file per run, case id to PASS, FAIL or SKIP with the
error category the implementation reported, naming the build (revision), the environment and the claims it ran with.
tools/conformance/report.py builds one from a run and checks it; this gate checks the checker on a report built from
the suite on disk, then every report published under specification/conformance/reports/, each at the file name its
names and suite digest require.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

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
        (lambda r: r["results"][0].update(category="Parse"), "an unknown category"),
        (lambda r: r["results"][0].update(status="PASSED"), "an unknown status"),
        (lambda r: r["results"][0].update(detail=""), "a skip without a reason"),
        (lambda r: r.update(format="x"), "a wrong format"),
        (lambda r: r["implementation"].pop("version"), "an unversioned implementation"),
        (lambda r: r["implementation"].pop("revision"), "a report without a revision"),
        (lambda r: r["implementation"].update(revision="main"), "a revision that is not a commit"),
        (lambda r: r.pop("formatVersion"), "a version-1 report of the current suite"),
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
    assert report.check(legacy) == [], report.check(legacy)
    completed = report.complete(copy.deepcopy(legacy), "0123abcd", ENVIRONMENT)
    assert completed["formatVersion"] == 2 and report.check(completed) == [], "complete() left the report unchecked"
    return len(cases)


def main() -> int:
    n = self_test()
    problems = []
    published = report.published()
    for path, data in published:
        problems += [f"{path.relative_to(report.SUITE).as_posix()}: {p}" for p in report.check(data, path=path)]
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(f"PASS: the report check holds on a {n}-case suite; {len(published)} published report(s) follow the format")
    return 0


if __name__ == "__main__":
    sys.exit(main())
