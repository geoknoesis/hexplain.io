"""The processor conformance suite is complete, well formed and generated from its sources.

Checks that specification/conformance/<class>/ is exactly what tools/conformance/ generates;
that every case has a complete manifest, cites only registered requirement identifiers and
sections the pages define, and has exactly one expected artifact; that every description,
rule set and expected graph parses; and that the coverage section of the suite's page is current.
"""
import json
import re
import sys
from pathlib import Path

import rdflib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "conformance"))

import _build_conformance_page  # noqa: E402
import generate_inputs  # noqa: E402
from suite import BLANKET, CATEGORIES, CLASSES, EXPECTED, LIMITS, PREFIX, SUITE, feature_tokens  # noqa: E402

REQUIRED = ("id", "class", "title", "description", "requirements", "sections")
MINIMUM_CASES = 150


def section_ids(document):
    """The element ids of a page named as a case's section document (`processing`, `hel/index.html`)."""
    path = ROOT / "specification" / (document if "/" in document else f"{document}/index.html")
    if not path.is_file():
        return None
    return set(re.findall(r'\bid="([^"]+)"', path.read_text(encoding="utf-8")))


def main():
    problems = []
    wanted = generate_inputs.expected_tree()
    present = generate_inputs.on_disk()
    stale = sorted(p for p in wanted.keys() | present.keys() if wanted.get(p) != present.get(p))
    if stale:
        problems.append(f"{len(stale)} suite file(s) differ from tools/conformance/ (run python "
                        f"tools/conformance/generate_inputs.py): {stale[:5]}")

    registry = json.loads((SUITE / "requirements.json").read_text(encoding="utf-8"))["requirements"]
    live = {i for i, e in registry.items() if not e.get("withdrawn")}
    features = set(feature_tokens())
    pages = {}
    counts = {cls: 0 for cls in CLASSES}
    for cls in CLASSES:
        for case_dir in sorted(p for p in (SUITE / cls).iterdir() if p.is_dir()):
            where = f"{cls}/{case_dir.name}"
            manifest_path = case_dir / "manifest.json"
            if not manifest_path.is_file():
                problems.append(f"{where}: no manifest.json")
                continue
            counts[cls] += 1
            man = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key in REQUIRED:
                if not man.get(key):
                    problems.append(f"{where}: manifest lacks {key}")
            if man.get("id") != case_dir.name or man.get("class") != cls or not case_dir.name.startswith(PREFIX[cls] + "-"):
                problems.append(f"{where}: id, class and directory disagree")
            for rid in man.get("requirements", []):
                if rid not in live:
                    problems.append(f"{where}: cites {rid}, which the requirement registry does not list")
            if man.get("requirements") and not set(man["requirements"]) - set(BLANKET):
                problems.append(f"{where}: cites only blanket requirements {man['requirements']}; cite the specific rule")
            for section in man.get("sections", []):
                document, _, anchor = section.partition("#")
                if document not in pages:
                    pages[document] = section_ids(document)
                if pages[document] is None or anchor not in pages[document]:
                    problems.append(f"{where}: section {section} does not exist")
            expected = [name for name in EXPECTED if (case_dir / name).is_file()]
            if len(expected) != 1:
                problems.append(f"{where}: {len(expected)} expected artifacts, want exactly one ({expected})")
            files = [man.get("input"), man.get("rules")] + [p.get("file") for p in man.get("parts", [])]
            files += list(man.get("registers", []))
            if cls != "hdl-compiler" and "check" not in man:
                files.append("description.ttl")
            for name in filter(None, files):
                if not (case_dir / name).is_file():
                    problems.append(f"{where}: manifest names {name}, which does not exist")
            for name in ["description.ttl", "rules.ttl", "expected.ttl", "expected-report.ttl"] + list(man.get("registers", [])):
                if (case_dir / name).is_file():
                    try:
                        rdflib.Graph().parse(case_dir / name, format="turtle")
                    except Exception as exc:  # noqa: BLE001 -- any parse failure is the finding
                        problems.append(f"{where}: {name} does not parse: {exc}")
            for name in ("expected.json", "expected-error.json", "expected-report.json"):
                if (case_dir / name).is_file():
                    try:
                        value = json.loads((case_dir / name).read_text(encoding="utf-8"))
                    except ValueError as exc:
                        problems.append(f"{where}: {name} is not JSON: {exc}")
                        continue
                    if name == "expected-error.json" and cls != "hdl-compiler" and value.get("category") not in CATEGORIES:
                        problems.append(f"{where}: unknown error category {value.get('category')!r}")
                    if name == "expected-error.json" and cls == "hdl-compiler" and value.get("severity") != "ERROR":
                        problems.append(f"{where}: an HDL Compiler error names severity ERROR")
            for limit in man.get("limits", {}):
                if limit not in LIMITS:
                    problems.append(f"{where}: unknown limit {limit}")
            for kind, names in man.get("features", {}).items():
                if kind not in ("requires", "unclaimed"):
                    problems.append(f"{where}: unknown features member {kind}")
                for name in names:
                    if name not in features:
                        problems.append(f"{where}: {name!r} is not a feature token of the Processing Model's optional features")
            for kind, names in man.get("claims", {}).items():
                if kind != "withdraw":
                    problems.append(f"{where}: unknown claims member {kind}")
                for name in names:
                    if name not in features:
                        problems.append(f"{where}: claims withdraws {name!r}, which is not a feature token")
            if "compareOntologyHeader" in man and (cls != "hdl-compiler" or not isinstance(man["compareOntologyHeader"], bool)):
                problems.append(f"{where}: compareOntologyHeader is a Boolean of an HDL Compiler case")
            if "base" in man and man["base"] is None and cls != "semantic-emitter":
                problems.append(f"{where}: only a Semantic Emitter case may leave the base to the processor")
            if man.get("parseMode", "lenient") not in ("lenient", "strict"):
                problems.append(f"{where}: parseMode is lenient or strict")
            for key in ("reportConformsToShapes",):
                if key in man and (cls != "conformance-evaluator" or not isinstance(man[key], bool)):
                    problems.append(f"{where}: {key} is a Boolean of a Conformance Evaluator case")
            if man.get("reportForm", "json") not in ("json", "rdf"):
                problems.append(f"{where}: reportForm is json or rdf")
            if man.get("check") not in (None, "claims"):
                problems.append(f"{where}: unknown check {man['check']!r}")
            if man.get("orError") and man["orError"] not in CATEGORIES:
                problems.append(f"{where}: unknown orError category {man['orError']}")
    for cls, n in counts.items():
        if not n:
            problems.append(f"no {cls} cases")
    if sum(counts.values()) < MINIMUM_CASES:
        problems.append(f"only {sum(counts.values())} cases; the suite holds at least {MINIMUM_CASES}")
    if _build_conformance_page.main(["--check"]):
        problems.append("the coverage section or coverage.json is stale (run python tools/_build_conformance_page.py)")
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems[:60]))
        return 1
    print(f"PASS: {sum(counts.values())} conformance cases ({', '.join(f'{c} {n}' for c, n in counts.items())}) "
          f"cite {len(live)} registered requirements consistently")
    return 0


if __name__ == "__main__":
    sys.exit(main())
