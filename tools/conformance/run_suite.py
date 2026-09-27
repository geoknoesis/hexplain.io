"""Run the processor conformance suite against an implementation's command line, and report pass/fail per case.

    python tools/conformance/run_suite.py --claims claims.json \\
        --pp-cmd "java -jar my.jar parse {description} {root} {input} --out {out} --error {err}" \\
        --hc-cmd "my-hdl {input} -o {out}" ...

Each class runs with its own command template (--pp-cmd, --se-cmd, --bp-cmd, --hc-cmd, --ce-cmd); a class with no
template is skipped. The runner fills the template for each case, runs it in a fresh temporary directory, and compares
what it wrote with the case's expected artifact (compare.py). Placeholders, each replaced by a path or a value inside
the argument that holds it:

  {case}        the case directory              {manifest}   its manifest.json
  {description} description.ttl                 {input}      the input (input.bin, or the manifest's input: input.hx)
  {root}        the root struct IRI             {base}       the base IRI, empty when the processor is to choose one
  {rules}       rules.ttl (Conformance Evaluator)             {mode}       lenient or strict
  {version}     the input's format version, or empty          {instant}    the evaluation instant, or empty
  {limits}      the lowered limits as JSON      {withdraw}   the feature tokens to run without, comma-separated
  {out}         where to write the output       {err}        where to write {"category": ...} on an error
  {reported}    where to write the base IRI the processor chose (a case with no base)

Output, by class and outcome: the parsed tree as canonical JSON; the instance, asset or compiled graph as Turtle or
N-Triples; a conformance run as the JSON summary or, for a case with "reportForm": "rdf", as a conf: RDF report; an
error as {"category": "<Processing Model category>"} written to {err}, the command exiting non-zero. For the HDL
Compiler the runner also reads diagnostics from standard error in the form file:line:column: SEVERITY: message.

A case applies when every optional feature it requires is claimed and none it expects unclaimed is; the claims come
from --claims (a JSON claims statement: {"classes": [...], "optionalFeatures": [tokens]} or {token: {"claimed": bool}}).
The template is split into arguments as a POSIX shell would split it, and run without a shell. A case that withdraws
features ("claims": {"withdraw": [...]}) runs only when the template has a {withdraw} placeholder.
Every case that does not apply is reported as SKIP with its reason. The exit status is 1 when any case fails.
"""
import argparse
import fnmatch
import json
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compare  # noqa: E402
import report  # noqa: E402
from suite import CLASSES, SUITE  # noqa: E402

FLAGS = {"physical-parser": "pp", "semantic-emitter": "se", "bundle-processor": "bp", "hdl-compiler": "hc",
         "conformance-evaluator": "ce"}
DIAGNOSTIC = re.compile(r":(\d+):(\d+):\s*(ERROR|WARNING|INFO)\b", re.I)


def claimed_features(claims):
    value = claims.get("optionalFeatures", {})
    if isinstance(value, dict):
        return {k for k, v in value.items() if (v.get("claimed") if isinstance(v, dict) else v)}
    return set(value)


def fill(template, values):
    """The command as an argument list: the template is split like a POSIX shell line first, then each placeholder is
    replaced inside its argument, so a path with a space stays one argument and nothing is interpreted by a shell."""
    def one(arg):
        return re.sub(r"\{(\w+)\}", lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), arg)
    return [one(arg) for arg in shlex.split(template)]


def run_case(case_dir, template, claims, timeout, keep=None, observed=None):
    """(status, detail) for one case: PASS, FAIL or SKIP. When the implementation reports an error, its category is
    stored in `observed["category"]` for the implementation report."""
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    features = claimed_features(claims) if claims is not None else None
    if manifest.get("check") == "claims":
        if claims is None:
            return "SKIP", "no --claims statement given"
        problems = compare.compare_claims(json.loads((case_dir / "expected-claims.json").read_text(encoding="utf-8")), claims)
        return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")
    wanted = manifest.get("features", {})
    if wanted.get("requires"):
        if features is None:
            return "SKIP", f"requires {wanted['requires']}, and no --claims statement says which features are claimed"
        missing = [f for f in wanted["requires"] if f not in features]
        if missing:
            return "SKIP", f"requires unclaimed feature(s) {missing}"
    if wanted.get("unclaimed"):
        if features is None:
            return "SKIP", "checks the refusal of an unclaimed feature, and no --claims statement is given"
        present = [f for f in wanted["unclaimed"] if f in features]
        if present:
            return "SKIP", f"checks the refusal of {present}, which the implementation claims"
    withdraw = manifest.get("claims", {}).get("withdraw", [])
    if withdraw and "{withdraw}" not in template:
        return "SKIP", f"runs without {withdraw}; the command template has no {{withdraw}} placeholder"
    with tempfile.TemporaryDirectory(dir=keep) as tmp:
        tmp = Path(tmp)
        name = compare.expected_artifact(case_dir)
        ext = ".ttl" if name.endswith(".ttl") else ".json"
        out, err, reported = tmp / ("actual" + ext), tmp / "error.json", tmp / "reported-base.txt"
        values = {"case": case_dir, "manifest": case_dir / "manifest.json", "description": case_dir / "description.ttl",
                  "input": case_dir / manifest.get("input", "input.bin"), "root": manifest.get("root", ""),
                  "base": manifest.get("base") or "", "rules": case_dir / manifest.get("rules", "rules.ttl"),
                  "mode": manifest.get("parseMode", "lenient"), "version": manifest.get("fileVersion", ""),
                  "instant": manifest.get("evaluationInstant", ""), "limits": json.dumps(manifest.get("limits", {})),
                  "withdraw": ",".join(withdraw), "out": out, "err": err, "reported": reported}
        command = fill(template, values)
        try:
            proc = subprocess.run(command, cwd=tmp, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return "FAIL", f"timed out after {timeout}s"
        if manifest["class"] == "hdl-compiler" and name == "expected-error.json":
            diags = [{"severity": m.group(3).upper(), "line": int(m.group(1))} for m in DIAGNOSTIC.finditer(proc.stderr)]
            if err.is_file():
                diags += json.loads(err.read_text(encoding="utf-8")).get("diagnostics", [])
            actual = tmp / "diagnostics.json"
            actual.write_text(json.dumps({"diagnostics": diags, "output": out.is_file() and out.stat().st_size > 0}),
                              encoding="utf-8")
        elif err.is_file():
            actual = err
            if observed is not None:
                try:
                    observed["category"] = json.loads(err.read_text(encoding="utf-8")).get("category")
                except (ValueError, AttributeError):
                    observed["category"] = None
        elif out.is_file():
            actual = out
        else:
            return "FAIL", f"the command wrote neither {out.name} nor {err.name} (exit {proc.returncode}): {proc.stderr.strip()[:300]}"
        base = reported.read_text(encoding="utf-8").strip() if reported.is_file() else None
        if "base" in manifest and manifest["base"] is None and not base and actual == out:
            return "FAIL", "the case gives no base and the processor reported none"
        try:
            problems = compare.compare_case(case_dir, actual, reported_base=base)
        except Exception as exc:  # noqa: BLE001 -- an unreadable output is a failure of the case, not of the runner
            problems = [f"the output could not be compared: {exc}"]
        return ("FAIL", "; ".join(problems)) if problems else ("PASS", "")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for cls, flag in FLAGS.items():
        ap.add_argument(f"--{flag}-cmd", help=f"command template for the {cls} cases")
    ap.add_argument("--suite", default=str(SUITE), help="the suite directory (specification/conformance)")
    ap.add_argument("--claims", help="the implementation's claims statement (JSON)")
    ap.add_argument("--case", action="append", default=[], help="run only cases whose id matches this glob (repeatable)")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--json", help="write the implementation report (specification/conformance/index.html"
                                   "#implementation-reports) to this file")
    ap.add_argument("--implementation", default="unnamed", help="the implementation's name, for the report")
    ap.add_argument("--implementation-version", default="unknown", help="the implementation's version, for the report")
    ap.add_argument("--check-report", metavar="FILE", help="check an implementation report against the suite and exit")
    args = ap.parse_args(argv)
    if args.check_report:
        problems = report.check(json.loads(Path(args.check_report).read_text(encoding="utf-8")), Path(args.suite))
        print("\n".join(problems) if problems else "the report follows the format and covers the suite")
        return 1 if problems else 0
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8")) if args.claims else None
    results, counts = [], {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for cls in CLASSES:
        template = getattr(args, f"{FLAGS[cls]}_cmd")
        for case_dir in sorted(p for p in (Path(args.suite) / cls).iterdir() if (p / "manifest.json").is_file()):
            if args.case and not any(fnmatch.fnmatch(case_dir.name, g) for g in args.case):
                continue
            observed = {}
            if template is None:
                status, detail = "SKIP", f"no --{FLAGS[cls]}-cmd"
            else:
                status, detail = run_case(case_dir, template, claims, args.timeout, observed=observed)
            counts[status] += 1
            results.append({"case": case_dir.name, "class": cls, "status": status,
                            "category": observed.get("category"), "detail": detail})
            print(f"{status} {case_dir.name}" + (f"  {detail}" if detail and status != "PASS" else ""))
    print(f"{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    if args.json:
        built = report.build(results, {"name": args.implementation, "version": args.implementation_version},
                             claims or {}, Path(args.suite))
        Path(args.json).write_text(json.dumps(built, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
