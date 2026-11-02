"""Run the processor conformance suite against an implementation's command line, and report pass/fail per case.

    python tools/conformance/run_suite.py --claims claims.json \
        --pp-cmd "java -jar my.jar parse {description} {root} {input} --out {out} --error {err}" \
        --hc-cmd "my-hdl {input} -o {out}" ...

Each class runs with its own command template (--pp-cmd, --se-cmd, --bp-cmd, --hc-cmd, --ce-cmd, and --w-cmd for the
Writer cases); a class with no template is skipped. The runner fills the template for each case, runs it in a fresh
temporary directory, and compares what it wrote with the case's expected artifact (compare.py). Placeholders, each
replaced by a path or a value inside the argument that holds it:

  {case}        the case directory              {manifest}   its manifest.json
  {description} description.ttl                 {input}      the input (input.bin, or the manifest's input: input.hx,
                                                             or tree.json, the logical tree of a Writer case)
  {root}        the root struct IRI             {base}       the base IRI, empty when the processor is to choose one
  {rules}       rules.ttl (Conformance Evaluator)             {mode}       lenient or strict
  {version}     the input's format version, or empty          {instant}    the evaluation instant, or empty
  {limits}      the lowered limits as JSON      {withdraw}   the feature tokens to run without, comma-separated
  {cells}       the layout fields whose cells the tree is to hold in place of their bytes, comma-separated
  {out}         where to write the output       {err}        where to write {"category": ...} on an error
  {reported}    where to write the base IRI the processor chose (a case with no base)

Output, by class and outcome: the parsed tree as canonical JSON; the instance, asset or compiled graph as Turtle or
N-Triples; a conformance run as the JSON summary or, for a case with "reportForm": "rdf", as a conf: RDF report; an
error as {"category": "<Processing Model category>"} written to {err}, the command exiting non-zero. For the HDL
Compiler the runner also reads diagnostics from standard error in the form file:line:column: SEVERITY: message.

A Writer case runs the other way: the command is given {description}, {root} and the tree ({input}, tree.json, in
the canonical JSON form of a parsed tree) and writes the serialised stream to {out}, as the bytes themselves, or an
error category to {err}. The bytes compare exactly with the case's expected.hex. A Writer case that states
"verify": "round-trip" (a compressor, whose bytes are its encoder's own) is checked by parsing the written stream
with --pp-cmd and comparing the tree with the case's expected.json; without --pp-cmd it is skipped.

--round-trip runs the symmetry requirement instead of the cases (round_trip.py): every Physical Parser case that
states a tree is written with --w-cmd ({input} is the case's expected.json) and what was written is parsed with
--pp-cmd ({input} is the written stream); the two trees must be isomorphic, or the writer must refuse as
specification/conformance/writer/round-trip-expectations.json states for the case. A case whose manifest allows an
error outcome (`orError`) also passes when the writer or the parser refuses with that category. Both templates are
required, and the claims must claim `writer`.

A case applies when every optional feature and codec it requires is claimed and none it expects unclaimed is; the
claims come
from --claims (a JSON claims statement: {"classes": [...], "optionalFeatures": [tokens]} or {token: {"claimed": bool}},
"codecs": [codec IRIs] and "encodings": [IRIs of the further bddo:Encoding individuals it decodes]). A case that
names text encodings ("encodings": {"requires": [...]}) applies when the statement lists each; the five encodings
every Physical Parser decodes are claimed by every statement.
The template is split into arguments as a POSIX shell would split it (on Windows: on unquoted white space, a
backslash being a path separator and the quotes around an argument removed), and run without a shell. An
implementation whose error names are not the Processing Model's categories gives --category-map, a JSON file mapping
its names to them; a name that maps to no category is recorded as no category, with the name in the result's detail.
An implementation report (--json) needs --claims: its results are checked against them. A case that withdraws
features ("claims": {"withdraw": [...]}) runs only when the template has a {withdraw} placeholder, and a case that
asks for a layout's cells ("cells": [...]) only when it has a {cells} placeholder.
Every case that does not apply is reported as SKIP with its reason. The exit status is 1 when any case fails.
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import fnmatch
import json
import math
import os
import platform
import queue
import re
import shlex
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare  # noqa: E402
import report  # noqa: E402
import round_trip  # noqa: E402
from applicability import claimed_features, skip_reason  # noqa: E402
from comparison_worker import artifact_problem  # noqa: E402
from processor_process import execute  # noqa: E402
from suite import CATEGORIES, CLASSES, ROUND_TRIP, SUITE, strict_json  # noqa: E402

FLAGS = {
    "physical-parser": "pp",
    "semantic-emitter": "se",
    "bundle-processor": "bp",
    "hdl-compiler": "hc",
    "conformance-evaluator": "ce",
    "writer": "w",
}
DIAGNOSTIC = re.compile(r":(\d+):(\d+):\s*(ERROR|WARNING|INFO)\b", re.I)
#: A case's manifest and an implementation's claims statement, as parsed JSON.
Manifest = dict[str, Any]
Claims = dict[str, Any]
#: One case's result, as the implementation report lists it.
Result = dict[str, Any]


def split_template(template: str, posix: bool | None = None) -> list[str]:
    """A command template's arguments. On POSIX the template is split as a POSIX shell would split it. On Windows
    (posix False) a backslash is a path separator, not an escape -- POSIX splitting would turn C:\\tools\\p.exe into
    C:toolsp.exe -- so the template is split on unquoted white space and the quotes around an argument removed."""
    if posix is None:
        posix = os.name != "nt"
    if posix:
        return shlex.split(template)
    out = []
    for arg in shlex.split(template, posix=False):
        if len(arg) >= 2 and arg[0] == arg[-1] and arg[0] in "\"'":
            arg = arg[1:-1]
        out.append(arg)
    return out


def fill(template: str, values: dict[str, Any], posix: bool | None = None) -> list[str]:
    """The command as an argument list: the template is split into arguments first (split_template), then each
    placeholder is replaced inside its argument, so a path with a space stays one argument and nothing is
    interpreted by a shell."""

    def one(arg: str) -> str:
        return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), arg)

    return [one(arg) for arg in split_template(template, posix)]


def placeholders(case_dir: Path, manifest: Manifest, tmp: Path, ext: str) -> dict[str, Any]:
    """The values of a command template's placeholders for one case, its outputs under [tmp]."""
    return {
        "case": case_dir,
        "manifest": case_dir / "manifest.json",
        "description": case_dir / "description.ttl",
        "input": case_dir / manifest.get("input", "input.bin"),
        "root": manifest.get("root", ""),
        "base": manifest.get("base") or "",
        "rules": case_dir / manifest.get("rules", "rules.ttl"),
        "mode": manifest.get("parseMode", "lenient"),
        "version": manifest.get("fileVersion", ""),
        "instant": manifest.get("evaluationInstant", ""),
        "limits": json.dumps(manifest.get("limits", {})),
        "withdraw": ",".join(manifest.get("claims", {}).get("withdraw", [])),
        "cells": ",".join(manifest.get("cells", [])),
        "out": tmp / ("actual" + ext),
        "err": tmp / compare.ERROR_FILE,
        "reported": tmp / "reported-base.txt",
    }


def invoke(template: str, values: dict[str, Any], tmp: Path, timeout: float) -> tuple[Path | None, str]:
    """Run one filled command. (the file it wrote, "") -- {err} when it reported an error, else {out} -- or
    (None, why) when it wrote neither or timed out."""
    out, err = values["out"], values["err"]
    for stale in (out, err):
        stale.unlink(missing_ok=True)
    values.pop("stderr", None)
    try:
        code, stderr, failure = execute(fill(template, values), tmp, timeout)
    except (OSError, ValueError) as exc:
        return None, f"could not run the command: {exc}"
    if failure:
        return None, failure
    for artifact in (out, err, values["reported"]):
        problem = artifact_problem(artifact)
        if problem:
            return None, problem
    values["stderr"] = stderr
    values["exit_code"] = code
    if err.is_file() and out.is_file():
        return None, "the command wrote both output and error artifacts"
    if err.is_file():
        return (err, "") if code != 0 else (None, "the command reported an error but exited zero")
    # An HDL compiler may report its error solely through stderr diagnostics, leaving {out} absent or empty.
    if code != 0 and DIAGNOSTIC.search(stderr) and (not out.is_file() or out.stat().st_size == 0):
        return None, "diagnostics only"
    if out.is_file():
        return (out, "") if code == 0 else (None, f"the command wrote output but exited {code}")
    return None, f"the command wrote neither {out.name} nor {err.name} (exit {code}): " + stderr.strip()[:300]


#: An implementation's error names mapped to the Processing Model's categories (--category-map).
CategoryMap = dict[str, str]


def raw_category(path: Path) -> object:
    """The "category" member of the error artifact at [path], as written; None when it is unreadable."""
    try:
        payload = strict_json(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return payload.get("category") if isinstance(payload, dict) else None


def category_of(path: Path, category_map: CategoryMap | None = None) -> str | None:
    """The Processing Model category the error artifact at [path] names, through [category_map]; None when it names
    none (the report records only a category of the Processing Model)."""
    raw = raw_category(path)
    if not isinstance(raw, str):
        return None
    mapped = (category_map or {}).get(raw, raw)
    return mapped if mapped in CATEGORIES else None


def observe_category(path: Path, observed: dict[str, Any] | None, category_map: CategoryMap | None) -> str | None:
    """Record the category of the error artifact at [path] in [observed]: the Processing Model category it maps to,
    or None, with the name the processor used kept as `unmapped` for the result's detail."""
    category = category_of(path, category_map)
    if observed is not None:
        observed["category"] = category
        raw = raw_category(path)
        if category is None and raw is not None:
            observed["unmapped"] = raw
    return category


def result_detail(detail: str, observed: dict[str, Any]) -> str:
    """[detail], noting an error name that maps to no Processing Model category."""
    if "unmapped" not in observed:
        return detail
    note = f"the processor's error category {observed['unmapped']!r:.200} is not a Processing Model category"
    return f"{detail}; {note}" if detail else note


def parse_back(
    case_dir: Path, manifest: Manifest, stream: Path, template: str, tmp: Path, timeout: float
) -> tuple[Path | None, str]:
    """Parse [stream] with the parser under test, by the case's description, root and limits: (the file holding
    the tree or the error, "") or (None, why)."""
    back = tmp / "back"
    back.mkdir(exist_ok=True)
    values = placeholders(case_dir, manifest, back, ".json")
    values["input"] = stream
    return invoke(template, values, back, timeout)


def hdl_diagnostics(values: dict[str, Any], tmp: Path) -> Path:
    """The diagnostics an HDL Compiler reported, on standard error and in {err}, as one file the comparator reads."""
    out, err = values["out"], values["err"]
    diags = [
        {"severity": m.group(3).upper(), "line": int(m.group(1))} for m in DIAGNOSTIC.finditer(values.get("stderr", ""))
    ]
    if err.is_file():
        try:
            reported = strict_json(err.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            reported = {}  # An unreadable error artifact contributes no diagnostics.
        listed = reported.get("diagnostics", []) if isinstance(reported, dict) else []
        diags += listed if isinstance(listed, list) else []
    actual = tmp / "diagnostics.json"
    actual.write_text(
        json.dumps({"diagnostics": diags, "output": out.is_file() and out.stat().st_size > 0}),
        encoding="utf-8",
        newline="\n",
    )
    return actual


def invalid_success(name: str, actual: Path | None, values: dict[str, Any]) -> str | None:
    """An error-shaped body cannot change a successful process/artifact into an error outcome."""
    if actual is None or actual != values["out"]:
        return None
    if name == "expected-error.json":
        return "the case requires an error, but the processor reported successful output"
    if name == "expected-report.json":
        try:
            payload = strict_json(actual.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None  # The comparison reports an unreadable report.
        if isinstance(payload, dict) and "category" in payload:
            return "an evaluator error must use the error artifact and a nonzero exit"
    return None


def _run_case(
    case_dir: Path,
    template: str,
    claims: Claims | None,
    timeout: float,
    keep: str | None = None,
    observed: dict[str, Any] | None = None,
    parser: str | None = None,
    category_map: CategoryMap | None = None,
) -> tuple[str, str]:
    """(status, detail) for one case: PASS, FAIL or SKIP. When the implementation reports an error, its category is
    stored in `observed["category"]` for the implementation report (through [category_map], which maps the
    implementation's error names to the Processing Model's categories). [parser] is the Physical Parser template,
    which a Writer case verified by round trip parses the written stream with."""
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("check") == "claims":
        if claims is None:
            return "SKIP", "no --claims statement given"
        problems = compare.compare_claims(
            json.loads((case_dir / "expected-claims.json").read_text(encoding="utf-8")), claims
        )
        return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")
    applicability = skip_reason(manifest, claims, "{withdraw} {cells}")
    if applicability is not None:
        return "SKIP", applicability
    # The run, not the claims, rules these out: an applicable case then fails, as one with no command does.
    limitation = skip_reason(manifest, claims, template)
    verified = manifest.get("verify") == ROUND_TRIP
    if limitation is None and verified and parser is None:
        limitation = "is verified by parsing the written stream back, and no --pp-cmd is given"
    if limitation is not None:
        return ("SKIP", limitation) if claims is None else ("FAIL", "applicable case " + limitation)
    with tempfile.TemporaryDirectory(dir=keep) as scratch:
        tmp = Path(scratch)
        name = compare.expected_artifact(case_dir)
        ext = ".bin" if manifest["class"] == "writer" else ".ttl" if name.endswith(".ttl") else ".json"
        values = placeholders(case_dir, manifest, tmp, ext)
        actual, why = invoke(template, values, tmp, timeout)
        failure = invalid_success(name, actual, values)
        if failure:
            return "FAIL", failure
        if (
            manifest["class"] == "hdl-compiler"
            and name == "expected-error.json"
            and (actual is not None or why == "diagnostics only")
        ):
            if values["exit_code"] == 0:
                return "FAIL", "the compiler error case exited zero"
            actual = hdl_diagnostics(values, tmp)
        if actual is None:
            return "FAIL", why
        if actual == values["out"] and verified:
            assert parser is not None, "a case verified by round trip is skipped without a parser"
            actual, why = parse_back(case_dir, manifest, actual, parser, tmp, timeout)
            if actual is None:
                return "FAIL", "parsing the written stream back: " + why
        if actual.name == compare.ERROR_FILE:
            observe_category(actual, observed, category_map)
        base = reported_base(manifest, values["reported"])
        if "base" in manifest and manifest["base"] is None and not base and actual == values["out"]:
            return "FAIL", "the case gives no base and the processor reported none"
        problems = bounded_comparison("case", case_dir, actual, timeout, base, category_map)
        return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")


def reported_base(manifest: Manifest, reported: Path) -> str | None:
    """The base the comparator reads as the placeholder: the one the processor reported, only for a case whose
    manifest leaves the base to the processor (null or absent). Where the manifest gives the base, the expected
    graph is minted under it and a reported base is ignored: rewriting that base to the placeholder would fail a
    correct graph."""
    if manifest.get("base") or not reported.is_file():
        return None
    return reported.read_text(encoding="utf-8").strip() or None


class ComparisonWorker:
    """One long-lived comparison process: rdflib and the comparator load once, not once per case. A request that
    overruns its deadline, a reply beyond its bound or a dead worker discards the process; the next request starts
    a fresh one. The worker is recycled after RECYCLE requests so no comparison inherits unbounded state."""

    RECYCLE = 500
    MAX_REPLY_CHARS = 64_000  # The worker returns at most 20 problems of 2000 characters.

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proc: subprocess.Popen[str] | None = None
        self.script: Path | None = None
        self.replies: queue.Queue[str | None] = queue.Queue()
        self.served = 0

    def _start(self, script: Path) -> subprocess.Popen[str]:
        self.replies = queue.Queue()
        proc = subprocess.Popen(
            [sys.executable, str(script), "--serve"],
            cwd=script.parent,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        replies, stream = self.replies, proc.stdout
        assert stream is not None

        def read() -> None:
            try:
                for line in iter(lambda: stream.readline(self.MAX_REPLY_CHARS + 1), ""):
                    replies.put(line)
            except (OSError, ValueError):
                pass
            finally:
                replies.put(None)

        threading.Thread(target=read, daemon=True).start()
        self.proc, self.script, self.served = proc, script, 0
        return proc

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None:
            return
        with contextlib.suppress(OSError):
            proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
        for pipe in (proc.stdin, proc.stdout):
            with contextlib.suppress(OSError):
                if pipe is not None:
                    pipe.close()

    def request(self, script: Path, payload: dict[str, Any], timeout: float) -> tuple[list[str] | None, str]:
        """(the problems, "") or (None, why the comparison failed)."""
        with self.lock:
            if self.proc is not None and (
                self.script != script or self.served >= self.RECYCLE or self.proc.poll() is not None
            ):
                self.stop()
            try:
                proc = self.proc or self._start(script)
                assert proc.stdin is not None
                proc.stdin.write(json.dumps(payload) + "\n")
                proc.stdin.flush()
            except OSError as exc:
                self.stop()
                return None, f"could not reach the comparison worker: {exc}"
            self.served += 1
            try:
                line = self.replies.get(timeout=timeout)
            except queue.Empty:
                self.stop()
                return None, f"timed out after {timeout}s"
            if line is None or not line.endswith("\n"):
                self.stop()
                return None, "the comparison worker exited" if line is None else "the reply exceeded its bound"
            try:
                problems = strict_json(line)
            except ValueError:
                problems = None
            if not isinstance(problems, list) or not all(isinstance(p, str) for p in problems):
                self.stop()
                return None, "the comparison worker sent a malformed reply"
            return problems, ""


COMPARISONS = ComparisonWorker()
atexit.register(COMPARISONS.stop)


def bounded_comparison(
    mode: str,
    case: Path,
    actual: Path,
    timeout: float,
    base: str | None = None,
    category_map: CategoryMap | None = None,
) -> list[str]:
    """Compare in a separate, deadline-bound process so parsing and matching cannot stall the suite."""
    payload: dict[str, Any] = {
        "mode": mode,
        "case": str(case.resolve()),
        "actual": str(actual.resolve()),
        "base": base or "",
        "categories": category_map or {},
    }
    problems, why = COMPARISONS.request(HERE / "comparison_worker.py", payload, timeout)
    return ["comparison failed: " + why] if problems is None else problems


def run_case(
    case_dir: Path,
    template: str,
    claims: Claims | None,
    timeout: float,
    keep: str | None = None,
    observed: dict[str, Any] | None = None,
    parser: str | None = None,
    category_map: CategoryMap | None = None,
) -> tuple[str, str]:
    """Keep unreadable processor artifacts local to this case, so the run still produces a report."""
    try:
        return _run_case(case_dir, template, claims, timeout, keep, observed, parser, category_map)
    except Exception as exc:  # noqa: BLE001 -- a broken case must not discard the rest of the report
        return "FAIL", f"the case could not be evaluated: {exc}"


def allowed_refusal(manifest: dict[str, Any], category: str | None) -> bool:
    """Whether [category] is the error outcome the case's manifest allows in place of its tree (`orError`)."""
    return category is not None and category == manifest.get("orError")


def _run_round_trip(
    case_dir: Path,
    writer: str,
    parser: str,
    claims: Claims | None,
    expected: str,
    timeout: float,
    observed: dict[str, Any] | None = None,
    category_map: CategoryMap | None = None,
) -> tuple[str, str]:
    """(status, detail) of the round trip of one Physical Parser case's tree: written with [writer], parsed back
    with [parser], and judged against [expected], the case's entry in round-trip-expectations.json. A case whose
    manifest allows an error outcome (`orError`) passes, with no symmetry to check, when the writer or the parser
    refuses with that category: the case lets a processor refuse the tree's expressions that way."""
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    writer_manifest = {k: v for k, v in manifest.items() if k != "cells"}
    skip = skip_reason(writer_manifest, claims, writer) or skip_reason(manifest, claims, parser)
    if skip is None and "writer" not in (claimed_features(claims) if claims is not None else ()):
        skip = "the claims statement does not claim the feature 'writer'"
    if skip is not None:
        return "SKIP", skip
    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        values = placeholders(case_dir, manifest, tmp, ".bin")
        logical_tree = case_dir / "round-trip-tree.json"
        values["input"] = (
            logical_tree if manifest.get("cells") and logical_tree.is_file() else case_dir / "expected.json"
        )
        written, why = invoke(writer, values, tmp, timeout)
        if written is None:
            return "FAIL", "writing the tree: " + why
        if written.name == compare.ERROR_FILE:
            refusal = observe_category(written, observed, category_map)
            if allowed_refusal(manifest, refusal):
                return "PASS", f"the writer refused with {refusal}, which the case allows"
            return round_trip.judge(expected, refusal or "an unnamed category", None)
        back, why = parse_back(case_dir, manifest, written, parser, tmp, timeout)
        if back is None:
            return "FAIL", "the written stream does not parse: " + why
        if back.name == compare.ERROR_FILE:
            refusal = observe_category(back, observed, category_map)
            if allowed_refusal(manifest, refusal):
                return "PASS", f"the parser refused the written stream with {refusal}, which the case allows"
            return "FAIL", f"the written stream does not parse: {refusal}"
        problems = bounded_comparison("round-trip", case_dir, back, timeout)
        return round_trip.judge(expected, None, problems)


def run_round_trip(
    case_dir: Path,
    writer: str,
    parser: str,
    claims: Claims | None,
    expected: str,
    timeout: float,
    observed: dict[str, Any] | None = None,
    category_map: CategoryMap | None = None,
) -> tuple[str, str]:
    """Keep malformed round-trip artifacts from aborting subsequent cases."""
    try:
        return _run_round_trip(case_dir, writer, parser, claims, expected, timeout, observed, category_map)
    except Exception as exc:  # noqa: BLE001 -- a broken case must not discard the rest of the report
        return "FAIL", f"the round trip could not be evaluated: {exc}"


def round_trip_results(args: argparse.Namespace, claims: Claims | None) -> list[Result]:
    """Run the round-trip mode over the Physical Parser cases that state a tree."""
    expectations = round_trip.load_expectations(Path(args.suite))
    results = []
    for case_dir in round_trip.tree_cases(Path(args.suite)):
        if args.case and not any(fnmatch.fnmatch(case_dir.name, g) for g in args.case):
            continue
        observed: dict[str, Any] = {}
        expected = expectations.get(case_dir.name)
        if expected is None:
            status, detail = "FAIL", f"{round_trip.EXPECTATIONS} has no entry for the case"
        else:
            status, detail = run_round_trip(
                case_dir,
                args.w_cmd,
                args.pp_cmd,
                claims,
                expected,
                args.timeout,
                observed=observed,
                category_map=category_map(args),
            )
        detail = result_detail(detail, observed)
        results.append(
            {
                "case": case_dir.name,
                "class": "round-trip",
                "status": status,
                "category": observed.get("category"),
                "detail": detail,
            }
        )
        print(f"{status} {case_dir.name}" + (f"  {detail}" if detail and status != "PASS" else ""))
    return results


def case_results(args: argparse.Namespace, claims: Claims | None) -> list[Result]:
    """Run the cases of every class that has a command template."""
    results = []
    for cls in CLASSES:
        template = getattr(args, f"{FLAGS[cls]}_cmd")
        for case_dir in sorted(p for p in (Path(args.suite) / cls).iterdir() if (p / "manifest.json").is_file()):
            if args.case and not any(fnmatch.fnmatch(case_dir.name, g) for g in args.case):
                continue
            observed: dict[str, Any] = {}
            if template is None:
                manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
                reason = skip_reason(manifest, claims, "{withdraw} {cells}")
                if reason:
                    status, detail = "SKIP", reason
                elif claims is None:
                    status, detail = "SKIP", f"no --{FLAGS[cls]}-cmd and no claims statement"
                else:
                    status, detail = "FAIL", f"applicable case has no --{FLAGS[cls]}-cmd"
            else:
                status, detail = run_case(
                    case_dir,
                    template,
                    claims,
                    args.timeout,
                    observed=observed,
                    parser=args.pp_cmd,
                    category_map=category_map(args),
                )
            detail = result_detail(detail, observed)
            results.append(
                {
                    "case": case_dir.name,
                    "class": cls,
                    "status": status,
                    "category": observed.get("category"),
                    "detail": detail,
                }
            )
            print(f"{status} {case_dir.name}" + (f"  {detail}" if detail and status != "PASS" else ""))
    return results


def category_map(args: argparse.Namespace) -> CategoryMap | None:
    """The --category-map file, read once: {the implementation's error name: Processing Model category}."""
    if not getattr(args, "category_map", None):
        return None
    if not hasattr(args, "category_map_value"):
        value = strict_json(Path(args.category_map).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise ValueError("--category-map must be a JSON object mapping error names to category names")
        args.category_map_value = value
    mapping: CategoryMap = args.category_map_value
    return mapping


def report_metadata(args: argparse.Namespace) -> tuple[dict[str, str], dict[str, str]]:
    implementation = {
        "name": args.implementation,
        "version": args.implementation_version,
        "revision": args.implementation_revision,
    }
    environment = {"os": args.os or platform.platform(), "jvm": args.jvm, "toolchain": args.toolchain}
    return implementation, environment


def check_report_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if not args.json:
        return
    if args.case:
        parser.error("--json requires the whole suite; --case produces a partial run, not an implementation report")
    if not (args.implementation_revision and args.toolchain):
        parser.error("--json needs --implementation-revision and --toolchain: a report names the build it ran")
    if not args.claims:
        # The report is checked against the claims it ran with: without a statement no case's applicability, and
        # so no result, can be verified.
        parser.error("--json needs --claims: a report states the claims statement its results are checked against")
    implementation, environment = report_metadata(args)
    problems = report.metadata_problems(implementation, environment)
    if problems:
        parser.error("; ".join(problems))


def write_report(args: argparse.Namespace, results: list[Result], claims: Claims | None) -> bool:
    implementation, environment = report_metadata(args)
    built = report.build(results, implementation, claims or {}, Path(args.suite), environment=environment)
    problems = report.write_validated(Path(args.json), built, Path(args.suite))
    if problems:
        print("report not written: " + "; ".join(problems))
        return False
    print(f"report written to {args.json}; publish it as {report.report_path(built)}")
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for cls, flag in FLAGS.items():
        ap.add_argument(f"--{flag}-cmd", help=f"command template for the {cls} cases")
    ap.add_argument("--suite", default=str(SUITE), help="the suite directory (specification/conformance)")
    ap.add_argument("--claims", help="the implementation's claims statement (JSON)")
    ap.add_argument(
        "--case", action="append", default=[], help="run only cases whose id matches this glob (repeatable)"
    )
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument(
        "--json",
        help="write the implementation report (specification/conformance/index.html"
        "#implementation-reports) to this file",
    )
    ap.add_argument("--implementation", default="unnamed", help="the implementation's name, for the report")
    ap.add_argument("--implementation-version", default="unknown", help="the implementation's version, for the report")
    ap.add_argument(
        "--implementation-revision",
        help="the version-control identity of the build run (a Git commit hash), required for the report",
    )
    ap.add_argument("--os", help="the operating system of the run (default: as the platform reports it)")
    ap.add_argument("--jvm", default="none", help="the Java runtime of a JVM implementation, else none")
    ap.add_argument("--toolchain", help="the build tool and compiler that produced the build, required for the report")
    ap.add_argument(
        "--category-map",
        metavar="FILE",
        help="JSON file mapping the implementation's error names to the Processing Model's categories",
    )
    ap.add_argument("--check-report", metavar="FILE", help="check an implementation report against the suite and exit")
    ap.add_argument(
        "--round-trip",
        action="store_true",
        help="run the symmetry requirement over the Physical Parser cases' trees (needs --w-cmd and --pp-cmd)",
    )
    args = ap.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        ap.error("--timeout must be positive and finite")
    try:
        category_map(args)
    except (OSError, ValueError) as exc:
        ap.error(f"--category-map: {exc}")
    if args.check_report:
        problems = report.check(
            strict_json(Path(args.check_report).read_text(encoding="utf-8")), Path(args.suite), path=args.check_report
        )
        print("\n".join(problems) if problems else "the report follows the format and covers the suite")
        return 1 if problems else 0
    check_report_args(args, ap)
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8")) if args.claims else None
    if args.round_trip:
        if not (args.w_cmd and args.pp_cmd):
            ap.error("--round-trip needs --w-cmd (the writer) and --pp-cmd (the parser that reads its stream back)")
        if args.json:
            ap.error("--round-trip writes no implementation report: a report is of the cases")
        results = round_trip_results(args, claims)
    else:
        results = case_results(args, claims)
    counts = report.result_counts(results)
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    if args.json and not write_report(args, results, claims):
        return 1
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
