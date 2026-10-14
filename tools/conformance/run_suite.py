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
specification/conformance/writer/round-trip-expectations.json states for the case. Both templates are required, and
the claims must claim `writer`.

A case applies when every optional feature and codec it requires is claimed and none it expects unclaimed is; the
claims come
from --claims (a JSON claims statement: {"classes": [...], "optionalFeatures": [tokens]} or {token: {"claimed": bool}},
"codecs": [codec IRIs] and "encodings": [IRIs of the further bddo:Encoding individuals it decodes]). A case that
names text encodings ("encodings": {"requires": [...]}) applies when the statement lists each; the five encodings
every Physical Parser decodes are claimed by every statement.
The template is split into arguments as a POSIX shell would split it, and run without a shell. A case that withdraws
features ("claims": {"withdraw": [...]}) runs only when the template has a {withdraw} placeholder, and a case that
asks for a layout's cells ("cells": [...]) only when it has a {cells} placeholder.
Every case that does not apply is reported as SKIP with its reason. The exit status is 1 when any case fails.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare  # noqa: E402
import report  # noqa: E402
import round_trip  # noqa: E402
from suite import BASE_ENCODINGS, CLASSES, ENCODING_NAMESPACE, ROUND_TRIP, SUITE  # noqa: E402

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


def claimed_features(claims: Claims) -> set[str]:
    value = claims.get("optionalFeatures", {})
    if isinstance(value, dict):
        return {k for k, v in value.items() if (v.get("claimed") if isinstance(v, dict) else v)}
    return set(value)


def claimed_codecs(claims: Claims) -> set[str]:
    """The codec IRIs a claims statement lists: its "codecs" member is an array of IRIs."""
    value = claims.get("codecs", [])
    return set(value) if isinstance(value, list) else set()


def claimed_encodings(claims: Claims) -> set[str]:
    """The text encodings a claims statement states: the five every Physical Parser decodes, and the further ones
    its "encodings" member lists, an array of bddo:Encoding IRIs. A statement without the member lists none."""
    value = claims.get("encodings", [])
    listed = set(value) if isinstance(value, list) else set()
    return listed | {ENCODING_NAMESPACE + name for name in BASE_ENCODINGS}


def fill(template: str, values: dict[str, Any]) -> list[str]:
    """The command as an argument list: the template is split like a POSIX shell line first, then each placeholder is
    replaced inside its argument, so a path with a space stays one argument and nothing is interpreted by a shell."""

    def one(arg: str) -> str:
        return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), arg)

    return [one(arg) for arg in shlex.split(template)]


def skip_reason(manifest: Manifest, claims: Claims | None, template: str) -> str | None:
    """Why a case does not apply to the implementation the claims describe, or None when it does."""
    return (
        _feature_skip(manifest, claims)
        or _codec_skip(manifest, claims)
        or _encoding_skip(manifest, claims)
        or _template_skip(manifest, template)
    )


def _feature_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """Why the optional features the case requires or checks the refusal of rule it out, or None."""
    features = claimed_features(claims) if claims is not None else None
    wanted = manifest.get("features", {})
    if wanted.get("requires"):
        if features is None:
            return f"requires {wanted['requires']}, and no --claims statement says which features are claimed"
        missing = [f for f in wanted["requires"] if f not in features]
        if missing:
            return f"requires unclaimed feature(s) {missing}"
    if wanted.get("unclaimed"):
        if features is None:
            return "checks the refusal of an unclaimed feature, and no --claims statement is given"
        present = [f for f in wanted["unclaimed"] if f in features]
        if present:
            return f"checks the refusal of {present}, which the implementation claims"
    return None


def _codec_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """Why the codecs the case requires or checks the refusal of rule it out, or None."""
    codecs = manifest.get("codecs", {})
    if not codecs:
        return None
    if claims is None:
        return "names codecs, and no --claims statement says which codecs are claimed"
    listed = claimed_codecs(claims)
    missing = [c for c in codecs.get("requires", []) if c not in listed]
    if missing:
        return f"requires codec(s) {missing} the implementation does not list"
    present = [c for c in codecs.get("unclaimed", []) if c in listed]
    if present:
        return f"checks the refusal of codec(s) {present}, which the implementation lists"
    return None


def _encoding_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """Why the text encodings the case requires or checks the refusal of rule it out, or None."""
    encodings = manifest.get("encodings", {})
    if not encodings:
        return None
    if claims is None:
        return "names text encodings, and no --claims statement says which encodings are supported"
    listed = claimed_encodings(claims)
    missing = [e for e in encodings.get("requires", []) if e not in listed]
    if missing:
        return f"requires text encoding(s) {missing} the implementation does not list"
    present = [e for e in encodings.get("unclaimed", []) if e in listed]
    if present:
        return f"checks the refusal of text encoding(s) {present}, which the implementation lists"
    return None


def _template_skip(manifest: Manifest, template: str) -> str | None:
    """Why the command template lacks a placeholder the case needs, or None."""
    withdraw = manifest.get("claims", {}).get("withdraw", [])
    if withdraw and "{withdraw}" not in template:
        return f"runs without {withdraw}; the command template has no {{withdraw}} placeholder"
    if manifest.get("cells") and "{cells}" not in template:
        return f"asks for the cells of {manifest['cells']}; the command template has no {{cells}} placeholder"
    return None


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
    try:
        proc = subprocess.run(fill(template, values), cwd=tmp, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s"
    values["stderr"] = proc.stderr
    if err.is_file():
        return err, ""
    if out.is_file():
        return out, ""
    return None, f"the command wrote neither {out.name} nor {err.name} (exit {proc.returncode}): " + (
        proc.stderr.strip()[:300]
    )


def category_of(path: Path) -> str | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("category")
    except (ValueError, AttributeError):
        return None


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
        diags += json.loads(err.read_text(encoding="utf-8")).get("diagnostics", [])
    actual = tmp / "diagnostics.json"
    actual.write_text(
        json.dumps({"diagnostics": diags, "output": out.is_file() and out.stat().st_size > 0}),
        encoding="utf-8",
        newline="\n",
    )
    return actual


def run_case(
    case_dir: Path,
    template: str,
    claims: Claims | None,
    timeout: float,
    keep: str | None = None,
    observed: dict[str, Any] | None = None,
    parser: str | None = None,
) -> tuple[str, str]:
    """(status, detail) for one case: PASS, FAIL or SKIP. When the implementation reports an error, its category is
    stored in `observed["category"]` for the implementation report. [parser] is the Physical Parser template, which a
    Writer case verified by round trip parses the written stream with."""
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("check") == "claims":
        if claims is None:
            return "SKIP", "no --claims statement given"
        problems = compare.compare_claims(
            json.loads((case_dir / "expected-claims.json").read_text(encoding="utf-8")), claims
        )
        return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")
    skip = skip_reason(manifest, claims, template)
    verified = manifest.get("verify") == ROUND_TRIP
    if skip is None and verified and parser is None:
        skip = "is verified by parsing the written stream back, and no --pp-cmd is given"
    if skip is not None:
        return "SKIP", skip
    with tempfile.TemporaryDirectory(dir=keep) as scratch:
        tmp = Path(scratch)
        name = compare.expected_artifact(case_dir)
        ext = ".bin" if manifest["class"] == "writer" else ".ttl" if name.endswith(".ttl") else ".json"
        values = placeholders(case_dir, manifest, tmp, ext)
        actual, why = invoke(template, values, tmp, timeout)
        if manifest["class"] == "hdl-compiler" and name == "expected-error.json" and "stderr" in values:
            actual = hdl_diagnostics(values, tmp)
        if actual is None:
            return "FAIL", why
        if actual == values["out"] and verified:
            assert parser is not None, "a case verified by round trip is skipped without a parser"
            actual, why = parse_back(case_dir, manifest, actual, parser, tmp, timeout)
            if actual is None:
                return "FAIL", "parsing the written stream back: " + why
        if actual.name == compare.ERROR_FILE and observed is not None:
            observed["category"] = category_of(actual)
        reported = values["reported"]
        base = reported.read_text(encoding="utf-8").strip() if reported.is_file() else None
        if "base" in manifest and manifest["base"] is None and not base and actual == values["out"]:
            return "FAIL", "the case gives no base and the processor reported none"
        try:
            problems = compare.compare_case(case_dir, actual, reported_base=base)
        except Exception as exc:  # noqa: BLE001 -- an unreadable output is a failure of the case, not of the runner
            problems = [f"the output could not be compared: {exc}"]
        return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")


def run_round_trip(
    case_dir: Path,
    writer: str,
    parser: str,
    claims: Claims | None,
    expected: str,
    timeout: float,
    observed: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """(status, detail) of the round trip of one Physical Parser case's tree: written with [writer], parsed back
    with [parser], and judged against [expected], the case's entry in round-trip-expectations.json."""
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    skip = skip_reason(manifest, claims, writer) or skip_reason(manifest, claims, parser)
    if skip is None and "writer" not in (claimed_features(claims) if claims is not None else ()):
        skip = "the claims statement does not claim the feature 'writer'"
    if skip is not None:
        return "SKIP", skip
    with tempfile.TemporaryDirectory() as scratch:
        tmp = Path(scratch)
        values = placeholders(case_dir, manifest, tmp, ".bin")
        values["input"] = case_dir / "expected.json"
        written, why = invoke(writer, values, tmp, timeout)
        if written is None:
            return "FAIL", "writing the tree: " + why
        if written.name == compare.ERROR_FILE:
            refusal = category_of(written)
            if observed is not None:
                observed["category"] = refusal
            return round_trip.judge(expected, refusal or "an unnamed category", None)
        back, why = parse_back(case_dir, manifest, written, parser, tmp, timeout)
        if back is None:
            return "FAIL", "the written stream does not parse: " + why
        if back.name == compare.ERROR_FILE:
            return "FAIL", f"the written stream does not parse: {category_of(back)}"
        tree = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
        exempt = round_trip.recomputed_keys(case_dir / "description.ttl")
        problems = round_trip.isomorphism_problems(tree, json.loads(back.read_text(encoding="utf-8")), exempt)
        return round_trip.judge(expected, None, problems)


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
                case_dir, args.w_cmd, args.pp_cmd, claims, expected, args.timeout, observed=observed
            )
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
                status, detail = "SKIP", f"no --{FLAGS[cls]}-cmd"
            else:
                status, detail = run_case(
                    case_dir, template, claims, args.timeout, observed=observed, parser=args.pp_cmd
                )
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
    ap.add_argument("--check-report", metavar="FILE", help="check an implementation report against the suite and exit")
    ap.add_argument(
        "--round-trip",
        action="store_true",
        help="run the symmetry requirement over the Physical Parser cases' trees (needs --w-cmd and --pp-cmd)",
    )
    args = ap.parse_args(argv)
    if args.check_report:
        problems = report.check(
            json.loads(Path(args.check_report).read_text(encoding="utf-8")), Path(args.suite), path=args.check_report
        )
        print("\n".join(problems) if problems else "the report follows the format and covers the suite")
        return 1 if problems else 0
    if args.json and not (args.implementation_revision and args.toolchain):
        ap.error("--json needs --implementation-revision and --toolchain: a report names the build it ran")
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8")) if args.claims else None
    if args.round_trip:
        if not (args.w_cmd and args.pp_cmd):
            ap.error("--round-trip needs --w-cmd (the writer) and --pp-cmd (the parser that reads its stream back)")
        if args.json:
            ap.error("--round-trip writes no implementation report: a report is of the cases")
        results = round_trip_results(args, claims)
    else:
        results = case_results(args, claims)
    counts = {status: sum(1 for r in results if r["status"] == status) for status in ("PASS", "FAIL", "SKIP")}
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    if args.json:
        import platform

        implementation = {
            "name": args.implementation,
            "version": args.implementation_version,
            "revision": args.implementation_revision,
        }
        environment = {"os": args.os or platform.platform(), "jvm": args.jvm, "toolchain": args.toolchain}
        built = report.build(results, implementation, claims or {}, Path(args.suite), environment=environment)
        Path(args.json).write_text(
            json.dumps(built, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"report written to {args.json}; publish it as {report.report_path(built)}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
