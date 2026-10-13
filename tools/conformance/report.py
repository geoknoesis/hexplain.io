"""The implementation report: one JSON file per run of an implementation over the processor conformance suite.

specification/conformance/index.html#implementation-reports defines the format (version 2); this module builds a
report from a run (run_suite.py --json), completes one a runner wrote without its revision and environment, and
checks one against the suite it names. A report is published as
specification/conformance/reports/<implementation>/<version>-<suite digest, 12 hex digits>.json, so the reports of
earlier suites are kept beside the current one.

    python tools/conformance/report.py --complete report.json --revision <commit> --os "..." --jvm "..." --toolchain
"..."
    python tools/conformance/report.py --path report.json        # the path the report is published at
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from suite import CATEGORIES, CLASSES, SUITE

FORMAT = "https://hexplain.io/specification/conformance/#implementation-reports"
FORMAT_VERSION = 2
STATUSES = ("PASS", "FAIL", "SKIP")
REPORTS = SUITE / "reports"
#: A Git commit hash, or <system>:<identifier> for another version-control system.
REVISION = re.compile(r"^(?:[0-9a-f]{7,40}|[a-z][a-z0-9+.-]*:[^\s]+)$")
#: A version that names no fixed build: admissible only because the revision does.
PRERELEASE = re.compile(r"snapshot|dev|rc|alpha|beta|\+", re.I)
ENVIRONMENT = ("os", "jvm", "toolchain")


def suite_cases(suite: Any = SUITE) -> dict[str, Any]:
    """{case id: class} of every case of the suite on disk."""
    return {p.parent.name: cls for cls in CLASSES for p in sorted((Path(suite) / cls).glob("*/manifest.json"))}


def suite_digest(suite: Any = SUITE) -> Any:
    """SHA-256 over every case file of the suite, by relative path, so a report names the exact suite it ran."""
    h = hashlib.sha256()
    for cls in CLASSES:
        for path in sorted((Path(suite) / cls).rglob("*")):
            if path.is_file():
                h.update(path.relative_to(suite).as_posix().encode("utf-8") + b"\0")
                h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def claims_digest(claims: Any) -> Any:
    """SHA-256 of the claims statement's canonical JSON: keys sorted, no whitespace, non-ASCII unescaped, UTF-8."""
    canonical = json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def safe_name(text: str) -> Any:
    return re.sub(r"[^a-z0-9.-]", "-", str(text).lower())


def report_path(report: Any) -> str:
    """The path, relative to specification/conformance/, a report is published at."""
    impl = report.get("implementation", {})
    digest = str(report.get("suite", {}).get("digest", ""))[:12]
    return f"reports/{safe_name(impl.get('name', ''))}/{safe_name(impl.get('version', ''))}-{digest}.json"


def build(
    results: Any, implementation: Any, claims: Any, suite: Any = SUITE, date: Any = None, environment: Any = None
) -> dict[str, Any]:
    counts = {s: sum(1 for r in results if r["status"] == s) for s in STATUSES}
    return {
        "format": FORMAT,
        "formatVersion": FORMAT_VERSION,
        "implementation": implementation,
        "environment": environment or {},
        "claims": claims,
        "claimsDigest": claims_digest(claims),
        "suite": {"digest": suite_digest(suite), "cases": len(suite_cases(suite))},
        "run": {
            "date": date or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "runner": "tools/conformance/run_suite.py",
        },
        "counts": counts,
        "results": results,
    }


def complete(report: Any, revision: Any, environment: Any) -> Any:
    """[report] with the revision, environment, claims digest and format version a runner left out, in place."""
    report.setdefault("implementation", {})["revision"] = revision
    report["environment"] = dict(environment)
    if "claims" in report:
        report["claimsDigest"] = claims_digest(report["claims"])
    report["formatVersion"] = FORMAT_VERSION
    ordered = {}
    for key in (
        "format",
        "formatVersion",
        "implementation",
        "environment",
        "claims",
        "claimsDigest",
        "suite",
        "run",
        "counts",
        "results",
    ):
        if key in report:
            ordered[key] = report[key]
    ordered.update({k: v for k, v in report.items() if k not in ordered})
    report.clear()
    report.update(ordered)
    return report


def _version_problems(report, historical):
    """The format-version-2 members: required of every report of the current suite; a version-1 report (one that
    predates revision, environment and claimsDigest) stays published only for a suite that is no longer current."""
    problems = []
    version = report.get("formatVersion")
    if version is None:
        if not historical:
            problems.append(
                "a report of the current suite carries formatVersion 2 with its revision, environment "
                "and claimsDigest; a version-1 report stays published only for an earlier suite"
            )
        return problems
    if version != FORMAT_VERSION:
        problems.append(f"formatVersion is {version!r}, not {FORMAT_VERSION}")
    impl = report.get("implementation") if isinstance(report.get("implementation"), dict) else {}
    revision = impl.get("revision")
    if not isinstance(revision, str) or not REVISION.match(revision):
        problems.append(
            "implementation.revision must be a Git commit hash (7 to 40 hex digits) or <system>:<identifier>"
        )
        if isinstance(impl.get("version"), str) and PRERELEASE.search(impl["version"]):
            problems.append(
                f"version {impl['version']!r} names no fixed build and is not admissible without a revision"
            )
    env = report.get("environment")
    if not isinstance(env, dict) or not all(isinstance(env.get(k), str) and env.get(k).strip() for k in ENVIRONMENT):
        problems.append("environment must state os, jvm (or none) and toolchain, each a non-empty string")
    if isinstance(report.get("claims"), dict) and report.get("claimsDigest") != claims_digest(report["claims"]):
        problems.append("claimsDigest is not the SHA-256 of the claims statement's canonical JSON")
    return problems


def check(report: Any, suite: Any = SUITE, path: Any = None) -> Any:
    """The problems of a report, [] when it follows the format and covers the suite it names.

    [path], when given, is where the report is published (any path ending in reports/<implementation>/<file>.json):
    its file name must be the one the report's names and suite digest require.
    """
    problems = []
    if report.get("format") != FORMAT:
        problems.append(f"format is {report.get('format')!r}, not {FORMAT}")
    impl = report.get("implementation")
    if not isinstance(impl, dict) or not all(isinstance(impl.get(k), str) and impl.get(k) for k in ("name", "version")):
        problems.append("implementation must name the implementation and its version")
    if not isinstance(report.get("claims"), dict):
        problems.append("claims must be the implementation's claims statement")
    current = report.get("suite", {}).get("digest") == suite_digest(suite)
    problems += _version_problems(report, historical=not current)
    cases = suite_cases(suite)
    if current:
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
        if current and case in cases and r.get("class") != cases[case]:
            problems.append(f"{case}: class {r.get('class')!r}, the suite says {cases[case]}")
        if r.get("category") not in (None,) + CATEGORIES:
            problems.append(f"{case}: category {r.get('category')!r} is not a Processing Model category")
        if r.get("status") in ("FAIL", "SKIP") and not r.get("detail"):
            problems.append(f"{case}: a {r.get('status')} result states why (detail)")
    counts = report.get("counts", {})
    for s in STATUSES:
        if counts.get(s) != sum(1 for r in report.get("results", []) if r.get("status") == s):
            problems.append(f"counts.{s} does not match the results")
    if path is not None:
        want = report_path(report)
        got = Path(path).as_posix()
        if not got.endswith(want):
            problems.append(f"published at {Path(path).name}, but the report's names and suite digest require {want}")
    return problems


def published() -> list[Any]:
    """Every published report, as (path, report)."""
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(REPORTS.glob("*/*.json"))]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--complete", metavar="FILE", help="add the revision, environment and claims digest to this report")
    ap.add_argument("--path", metavar="FILE", help="print the path this report is published at")
    ap.add_argument("--revision")
    ap.add_argument("--os")
    ap.add_argument("--jvm", default="none")
    ap.add_argument("--toolchain")
    args = ap.parse_args(argv)
    if args.path:
        print(report_path(json.loads(Path(args.path).read_text(encoding="utf-8"))))
        return 0
    if not args.complete:
        ap.error("--complete FILE or --path FILE")
    if not (args.revision and args.os and args.toolchain):
        ap.error("--complete needs --revision, --os and --toolchain (and --jvm for a JVM implementation)")
    path = Path(args.complete)
    report = json.loads(path.read_text(encoding="utf-8"))
    complete(report, args.revision, {"os": args.os, "jvm": args.jvm, "toolchain": args.toolchain})
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    problems = [p for p in check(report) if not p.startswith("cases ")]
    print("\n".join(problems) if problems else f"completed {path}; publish it as {report_path(report)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
