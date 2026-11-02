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
import contextlib
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from applicability import skip_reason
from suite import CATEGORIES, CLASSES, SUITE

FORMAT = "https://hexplain.io/specification/conformance/#implementation-reports"
FORMAT_VERSION = 2
STATUSES = ("PASS", "FAIL", "SKIP")
REPORTS = SUITE / "reports"
#: A Git commit hash, or <system>:<identifier> for another version-control system.
REVISION = re.compile(r"^(?:[0-9a-fA-F]{7,40}|[a-z][a-z0-9+.-]*:[^\s]+)$")
ENVIRONMENT = ("os", "jvm", "toolchain")
#: An implementation report, as parsed JSON.
Report = dict[str, Any]


def suite_cases(suite: Path | str = SUITE) -> dict[str, str]:
    """{case id: class} of every case of the suite on disk."""
    return {p.parent.name: cls for cls in CLASSES for p in sorted((Path(suite) / cls).glob("*/manifest.json"))}


def suite_digest(suite: Path | str = SUITE) -> str:
    """SHA-256 over every case file of the suite, by relative path, so a report names the exact suite it ran."""
    h = hashlib.sha256()
    for cls in CLASSES:
        for path in sorted((Path(suite) / cls).rglob("*")):
            if path.is_file():
                h.update(path.relative_to(suite).as_posix().encode("utf-8") + b"\0")
                with path.open("rb") as stream:
                    h.update(hashlib.file_digest(stream, "sha256").digest())
    return h.hexdigest()


def claims_digest(claims: object) -> str:
    """SHA-256 of the claims statement's canonical JSON: keys sorted, no whitespace, non-ASCII unescaped, UTF-8."""
    canonical = json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def safe_name(text: str) -> str:
    return re.sub(r"[^a-z0-9.-]", "-", str(text).lower())


def report_path(report: Report) -> str:
    """The path, relative to specification/conformance/, a report is published at."""
    impl = report.get("implementation", {})
    digest = str(report.get("suite", {}).get("digest", ""))[:12]
    return f"reports/{safe_name(impl.get('name', ''))}/{safe_name(impl.get('version', ''))}-{digest}.json"


def result_counts(results: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count known statuses in one pass; validation reports malformed statuses separately."""
    counts = dict.fromkeys(STATUSES, 0)
    for result in results:
        status = result.get("status")
        if isinstance(status, str) and status in counts:
            counts[status] += 1
    return counts


def build(
    results: list[dict[str, Any]],
    implementation: dict[str, Any],
    claims: object,
    suite: Path | str = SUITE,
    date: str | None = None,
    environment: dict[str, str] | None = None,
) -> Report:
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
        "counts": result_counts(results),
        "results": results,
    }


def complete(report: Report, revision: str, environment: dict[str, str]) -> Report:
    """[report] with the revision, environment, claims digest and format version a runner left out, in place."""
    report.setdefault("implementation", {})["revision"] = revision
    report["environment"] = dict(environment)
    if "claims" in report:
        report["claimsDigest"] = claims_digest(report["claims"])
    report["formatVersion"] = FORMAT_VERSION
    ordered: Report = {}
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


def metadata_problems(implementation: dict[str, Any], environment: dict[str, Any]) -> list[str]:
    """Validate caller-supplied report metadata before a processor run or any report write."""
    problems = []
    if not all(isinstance(implementation.get(k), str) and implementation[k].strip() for k in ("name", "version")):
        problems.append("implementation must name the implementation and its version with nonempty strings")
    revision = implementation.get("revision")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        problems.append(
            "implementation.revision must be a Git commit hash (7 to 40 hex digits) or <system>:<identifier>"
        )
    if not all(isinstance(environment.get(k), str) and environment[k].strip() for k in ENVIRONMENT):
        problems.append("environment must state os, jvm (or none) and toolchain, each a non-empty string")
    return problems


def _run_problems(report: Report) -> list[str]:
    """Every report names its runner and an actual ISO 8601 UTC instant."""
    run = report.get("run")
    if not isinstance(run, dict):
        return ["run must be an object with date and runner"]
    problems = []
    runner = run.get("runner")
    if not isinstance(runner, str) or not runner.strip():
        problems.append("run.runner must be a nonempty string")
    date = run.get("date")
    try:
        if not isinstance(date, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", date
        ):
            raise ValueError("not an ISO 8601 UTC timestamp")
        datetime.fromisoformat(date)
    except ValueError:
        problems.append("run.date must be a valid ISO 8601 UTC timestamp")
    return problems


def _version_problems(report: Report, historical: bool) -> list[str]:
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
    stated = report.get("implementation")
    impl = stated if isinstance(stated, dict) else {}
    env = report.get("environment")
    problems += metadata_problems(impl, env if isinstance(env, dict) else {})
    if isinstance(report.get("claims"), dict) and report.get("claimsDigest") != claims_digest(report["claims"]):
        problems.append("claimsDigest is not the SHA-256 of the claims statement's canonical JSON")
    return problems


def _structure_problems(report: Report) -> list[str]:
    """Validate container types before using nested values, for current and historical reports alike."""
    if not isinstance(report, dict):
        return ["the report must be an object"]
    for key in ("implementation", "claims", "suite", "counts"):
        if not isinstance(report.get(key), dict):
            return [f"{key} must be an object"]
    results = report.get("results")
    if not isinstance(results, list) or not all(isinstance(r, dict) for r in results):
        return ["results must be an array of objects"]
    digest = report["suite"].get("digest")
    problems = []
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        problems.append("suite.digest must be a lowercase SHA-256 digest (64 hexadecimal digits)")
    count = report["suite"].get("cases")
    if type(count) is not int or count < 1 or count != len(results):
        problems.append("suite.cases must be positive and equal the number of results")
    ids = [r.get("case") for r in results]
    if not all(isinstance(case, str) and case for case in ids):
        problems.append("each result must name a nonempty case identifier")
    elif len(set(ids)) != len(ids):
        problems.append("results must not repeat case identifiers")
    for status in STATUSES:
        value = report["counts"].get(status)
        if type(value) is not int or value < 0:
            problems.append(f"counts.{status} must be a nonnegative integer")
    return problems


def _skip_problems(result: dict[str, Any], claims: dict[str, Any], suite: Path | str) -> list[str]:
    """A current-suite SKIP needs an applicability reason, not merely an absent command."""
    if result.get("status") != "SKIP" or result.get("class") not in CLASSES:
        return []
    manifest = Path(suite) / result["class"] / result["case"] / "manifest.json"
    if not manifest.is_file():
        return []  # Coverage validation reports unknown cases.
    try:
        # Every placeholder is supplied: a template's limits are the run's, not an applicability reason.
        reason = skip_reason(json.loads(manifest.read_text(encoding="utf-8")), claims, "{withdraw} {cells}")
    except (TypeError, ValueError, AttributeError) as exc:
        return [f"{result['case']}: invalid applicability claims: {exc}"]
    return [] if reason else [f"{result['case']}: an applicable case must PASS or FAIL, not SKIP"]


def check(
    report: Report, suite: Path | str = SUITE, path: Path | str | None = None, *, allow_historical: bool = False
) -> list[str]:
    """The problems of a report, [] when it follows the format and covers the suite it names.

    [path], when given, is where the report is published (any path ending in reports/<implementation>/<file>.json):
    its file name must be the one the report's names and suite digest require.
    Historical coverage requires supplying that suite. allow_historical=True checks only the
    structure of superseded reports for archive retention; it does not verify their coverage.
    """
    problems = _structure_problems(report)
    if problems:
        return problems
    problems += _run_problems(report)
    if problems:
        return problems
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
    if not current and not allow_historical:
        problems.append("suite digest differs from the supplied suite; historical coverage is unverified")
    if current:
        problems += _coverage_problems(report, cases)
    for r in report.get("results", []):
        problems += _result_problems(r, cases if current else None)
        if current:
            problems += _skip_problems(r, report["claims"], suite)
    counts = report.get("counts", {})
    observed_counts = result_counts(report["results"])
    for s in STATUSES:
        if counts.get(s) != observed_counts[s]:
            problems.append(f"counts.{s} does not match the results")
    if path is not None:
        want = report_path(report)
        got = Path(path).as_posix()
        if not got.endswith(want):
            problems.append(f"published at {Path(path).name}, but the report's names and suite digest require {want}")
    return problems


def _coverage_problems(report: Report, cases: dict[str, str]) -> list[str]:
    """The cases of the suite a report of it misses, lists that are not in it, or lists twice."""
    problems = []
    seen: dict[Any, int] = {}
    for r in report.get("results", []):
        seen[r.get("case")] = seen.get(r.get("case"), 0) + 1
    missing = sorted(set(cases) - set(seen))
    extra = sorted(c for c in seen if c not in cases)
    twice = sorted(c for c, n in seen.items() if n > 1)
    for label, ids in (("missing", missing), ("not in the suite", extra), ("listed twice", twice)):
        if ids:
            problems.append(f"cases {label}: {', '.join(ids[:10])}")
    return problems


def _result_problems(r: dict[str, Any], cases: dict[str, str] | None) -> list[str]:
    """The problems of one result: its status, category and detail, and, against the [cases] of the suite the
    report names when that suite is current, its class."""
    problems = []
    case = r.get("case")
    if r.get("class") not in CLASSES:
        problems.append(f"{case}: unknown class {r.get('class')!r}")
    if r.get("status") not in STATUSES:
        problems.append(f"{case}: status {r.get('status')!r}")
    if cases is not None and case in cases and r.get("class") != cases[case]:
        problems.append(f"{case}: class {r.get('class')!r}, the suite says {cases[case]}")
    if r.get("category") not in (None,) + CATEGORIES:
        problems.append(f"{case}: category {r.get('category')!r} is not a Processing Model category")
    if r.get("status") in ("FAIL", "SKIP") and not r.get("detail"):
        problems.append(f"{case}: a {r.get('status')} result states why (detail)")
    return problems


def write_validated(path: Path, report: Report, suite: Path | str = SUITE) -> list[str]:
    """Validate, serialize and atomically replace a report; every failure preserves the existing file."""
    problems = check(report, suite)
    if problems:
        return problems
    temporary: Path | None = None
    try:
        payload = json.dumps(report, indent=1, ensure_ascii=False, allow_nan=False) + "\n"
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".report-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    except (OSError, ValueError, TypeError) as exc:
        return [f"could not write the report: {exc}"]
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                # A failed replacement may leave a read-only staged file on Windows.
                temporary.chmod(stat.S_IREAD | stat.S_IWRITE)
                temporary.unlink(missing_ok=True)
    return []


def complete_file(path: Path, revision: str, environment: dict[str, str], suite: Path | str) -> int:
    """Stage metadata in memory and preserve the original bytes unless the complete report validates."""
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
        complete(candidate, revision, environment)
        problems = write_validated(path, candidate, suite)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        problems = [f"could not complete the report: {exc}"]
    print("\n".join(problems) if problems else f"completed {path}; publish it as {report_path(candidate)}")
    return 1 if problems else 0


def published() -> list[tuple[Path, Report]]:
    """Every published report, as (path, report)."""
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(REPORTS.glob("*/*.json"))]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--complete", metavar="FILE", help="add the revision, environment and claims digest to this report")
    ap.add_argument("--path", metavar="FILE", help="print the path this report is published at")
    ap.add_argument("--suite", default=str(SUITE), help="the matching suite to validate before replacing the report")
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
    return complete_file(
        Path(args.complete),
        args.revision,
        {"os": args.os, "jvm": args.jvm, "toolchain": args.toolchain},
        Path(args.suite),
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
