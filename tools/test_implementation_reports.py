"""Implementation reports follow the published format and cover the suite they name.

An implementation report (specification/conformance/index.html#implementation-reports) is the evidence that an
implementation passes the processor conformance suite: one JSON file per run, case id to PASS, FAIL or SKIP with the
error category the implementation reported. tools/conformance/report.py builds one from a run and checks it; this gate
checks the checker on a report built from the suite on disk, then every report published under
specification/conformance/reports/.
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conformance"))

import report  # noqa: E402


def self_test():
    cases = report.suite_cases()
    results = [{"case": c, "class": cls, "status": "SKIP", "category": None, "detail": "not run"}
               for c, cls in cases.items()]
    good = report.build(results, {"name": "probe", "version": "0"}, {"classes": [], "optionalFeatures": []},
                        date="2026-01-01T00:00:00Z")
    assert report.check(good) == [], report.check(good)
    for mutate, what in ((lambda r: r["results"].pop(), "a missing case"),
                         (lambda r: r["results"][0].update(category="Parse"), "an unknown category"),
                         (lambda r: r["results"][0].update(status="PASSED"), "an unknown status"),
                         (lambda r: r["results"][0].update(detail=""), "a skip without a reason"),
                         (lambda r: r.update(format="x"), "a wrong format"),
                         (lambda r: r["implementation"].pop("version"), "an unversioned implementation")):
        bad = copy.deepcopy(good)
        mutate(bad)
        assert report.check(bad), f"the report check no longer notices {what}"
    return len(cases)


def main():
    n = self_test()
    problems = []
    published = report.published()
    for path, data in published:
        problems += [f"{path.relative_to(report.SUITE).as_posix()}: {p}" for p in report.check(data)]
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(f"PASS: the report check holds on a {n}-case suite; {len(published)} published report(s) follow the format")
    return 0


if __name__ == "__main__":
    sys.exit(main())
