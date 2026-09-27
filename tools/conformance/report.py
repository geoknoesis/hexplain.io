"""The implementation report: one JSON file per run of an implementation over the processor conformance suite.

specification/conformance/index.html#implementation-reports defines the format; this module builds a report from a
run (run_suite.py --json) and checks one against the suite it names. A report is published as
specification/conformance/reports/<implementation>/<version>.json.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from suite import CATEGORIES, CLASSES, SUITE

FORMAT = "https://hexplain.io/specification/conformance/#implementation-reports"
STATUSES = ("PASS", "FAIL", "SKIP")
REPORTS = SUITE / "reports"


def suite_cases(suite=SUITE):
    """{case id: class} of every case of the suite on disk."""
    return {p.parent.name: cls for cls in CLASSES for p in sorted((Path(suite) / cls).glob("*/manifest.json"))}


def suite_digest(suite=SUITE):
    """SHA-256 over every case file of the suite, by relative path, so a report names the exact suite it ran."""
    h = hashlib.sha256()
    for cls in CLASSES:
        for path in sorted((Path(suite) / cls).rglob("*")):
            if path.is_file():
                h.update(path.relative_to(suite).as_posix().encode("utf-8") + b"\0")
                h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def build(results, implementation, claims, suite=SUITE, date=None):
    counts = {s: sum(1 for r in results if r["status"] == s) for s in STATUSES}
    return {
        "format": FORMAT,
        "implementation": implementation,
        "claims": claims,
        "suite": {"digest": suite_digest(suite), "cases": len(suite_cases(suite))},
        "run": {"date": date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "runner": "tools/conformance/run_suite.py"},
        "counts": counts,
        "results": results,
    }


def check(report, suite=SUITE):
    """The problems of a report, [] when it follows the format and covers the suite it names."""
    problems = []
    if report.get("format") != FORMAT:
        problems.append(f"format is {report.get('format')!r}, not {FORMAT}")
    impl = report.get("implementation")
    if not isinstance(impl, dict) or not all(isinstance(impl.get(k), str) and impl.get(k) for k in ("name", "version")):
        problems.append("implementation must name the implementation and its version")
    if not isinstance(report.get("claims"), dict):
        problems.append("claims must be the implementation's claims statement")
    cases = suite_cases(suite)
    if report.get("suite", {}).get("digest") == suite_digest(suite):
        seen = {}
        for r in report.get("results", []):
            seen[r.get("case")] = seen.get(r.get("case"), 0) + 1
        missing = sorted(set(cases) - set(seen))
        extra = sorted(c for c in seen if c not in cases)
        twice = sorted(c for c, n in seen.items() if n > 1)
        for label, ids in (("missing", missing), ("not in the suite", extra), ("listed twice", twice)):
            if ids:
                problems.append(f"cases {label}: {', '.join(ids[:10])}")
    for r in report.get("results", []):
        case = r.get("case")
        if r.get("status") not in STATUSES:
            problems.append(f"{case}: status {r.get('status')!r}")
        if case in cases and r.get("class") != cases[case]:
            problems.append(f"{case}: class {r.get('class')!r}, the suite says {cases[case]}")
        if r.get("category") not in (None,) + CATEGORIES:
            problems.append(f"{case}: category {r.get('category')!r} is not a Processing Model category")
        if r.get("status") in ("FAIL", "SKIP") and not r.get("detail"):
            problems.append(f"{case}: a {r.get('status')} result states why (detail)")
    counts = report.get("counts", {})
    for s in STATUSES:
        if counts.get(s) != sum(1 for r in report.get("results", []) if r.get("status") == s):
            problems.append(f"counts.{s} does not match the results")
    return problems


def published():
    """Every published report, as (path, report)."""
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(REPORTS.glob("*/*.json"))]
