"""The processor conformance suite is complete, well formed and generated from its sources.

Checks that specification/conformance/<class>/ is exactly what tools/conformance/ generates;
that every case has a complete manifest, cites only registered requirement identifiers and
sections the pages define, and has exactly one expected artifact; that every description,
rule set and expected graph parses; that a Writer case gives a tree and states exactly one of
the bytes, an error category a Writer raises and the tree its stream parses back to, and that
every live serialisation requirement is cited by a Writer case, the symmetry requirement apart,
which the round-trip mode observes: its expectations file names every Physical Parser case that
states a tree, and the mode's comparison and verdicts are probed here; and that the coverage
section of the suite's page is current.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import rdflib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "conformance"))

import _build_conformance_page  # noqa: E402
import generate_inputs  # noqa: E402
import round_trip  # noqa: E402
from suite import (  # noqa: E402
    BASE_ENCODINGS,
    BLANKET,
    CATEGORIES,
    CLASSES,
    ENCODING_NAMESPACE,
    EXPECTED,
    FURTHER_ENCODINGS,
    LIMITS,
    PREFIX,
    ROUND_TRIP,
    SUITE,
    TREE,
    WRITER_CATEGORIES,
    feature_tokens,
    parse_hex,
)

REQUIRED = ("id", "class", "title", "description", "requirements", "sections")
MINIMUM_CASES = 150
#: The registry class of the serialisation requirements, and the feature token a Writer case requires.
WRITER = "writer"


def writer_problems(case_dir: Any, man: Any, writer_requirements: Any) -> list[str]:
    """The structural rules of a Writer case: a tree, exactly one of the bytes and an error category, the `writer`
    feature required, and at least one serialisation requirement cited."""
    where = f"{WRITER}/{case_dir.name}"
    problems = []
    if man.get("input") != TREE:
        problems.append(f"{where}: a Writer case's input is {TREE}")
    try:
        json.loads((case_dir / TREE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"{where}: {TREE} is not a JSON tree: {exc}")
    stated = [n for n in ("expected.hex", "expected-error.json", "expected.json") if (case_dir / n).is_file()]
    if len(stated) != 1:
        problems.append(
            f"{where}: a Writer case states exactly one of expected.hex, expected-error.json and expected.json "
            f"({stated})"
        )
    if (man.get("verify") == ROUND_TRIP) != (stated == ["expected.json"]):
        problems.append(f'{where}: expected.json belongs to a Writer case with "verify": "{ROUND_TRIP}", and only it')
    if man.get("verify") not in (None, ROUND_TRIP):
        problems.append(f"{where}: unknown verify {man['verify']!r}")
    if stated == ["expected-error.json"]:
        category = json.loads((case_dir / "expected-error.json").read_text(encoding="utf-8")).get("category")
        if category not in WRITER_CATEGORIES:
            problems.append(f"{where}: {category!r} is not a category a Writer raises ({WRITER_CATEGORIES})")
    if (case_dir / "expected.hex").is_file():
        try:
            parse_hex((case_dir / "expected.hex").read_text(encoding="ascii"))
        except ValueError as exc:
            problems.append(f"{where}: {exc}")
    if WRITER not in man.get("features", {}).get("requires", []):
        problems.append(f"{where}: a Writer case requires the feature {WRITER!r}")
    if not set(man.get("requirements", [])) & writer_requirements:
        problems.append(f"{where}: a Writer case cites at least one serialisation requirement")
    return problems


#: A registry entry shorter than this, or one that introduces the rules after it, cannot be read alone.
SHORT_REQUIREMENT = 60


def context_problems(registry: dict[str, Any]) -> list[str]:
    """Every live requirement that is a list head or a short sentence carries a `context` (the generator,
    tools/_requirement_ids.py, records what the head introduces, or the short sentence's surroundings)."""
    problems = []
    for rid, entry in registry.items():
        text = entry["text"].rstrip()
        head = text.endswith((":", "as follows."))
        if not entry.get("withdrawn") and (head or len(text) < SHORT_REQUIREMENT) and not entry.get("context"):
            problems.append(f"{rid}: a list head or short requirement without a context: {text[:70]!r}")
    return problems


def gating_problems(case_dir: Path, man: dict[str, Any], cls: str) -> list[str]:
    """The manifest members that gate a case on text encodings and that ask for a layout's cells."""
    problems = []
    registered = {ENCODING_NAMESPACE + name for name in BASE_ENCODINGS + FURTHER_ENCODINGS}
    for kind, iris in man.get("encodings", {}).items():
        if kind not in ("requires", "unclaimed"):
            problems.append(f"unknown encodings member {kind}")
        problems += [
            f"encodings names {iri!r}, which is no registered bddo:Encoding" for iri in iris if iri not in registered
        ]
    description = case_dir / "description.ttl"
    if description.is_file():
        text = description.read_text(encoding="utf-8")
        used = {ENCODING_NAMESPACE + name for name in FURTHER_ENCODINGS if re.search(rf"bddo:{name}\b", text)}
        missing = sorted(used - set(man.get("encodings", {}).get("requires", [])))
        if missing and cls == "physical-parser" and case_dir.name.startswith("pp-encoding-"):
            problems.append(f"uses {missing} and does not require it")
    if "cells" in man:
        cells = man["cells"]
        if cls != "physical-parser" or not (
            isinstance(cells, list) and cells and all(isinstance(c, str) for c in cells)
        ):
            problems.append("cells is a non-empty list of layout field keys of a Physical Parser case")
        elif (case_dir / "expected.json").is_file():
            tree = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
            problems += [
                f"cells names {c!r}, which is not an array in the expected tree"
                for c in cells
                if not isinstance(tree.get(c), list)
            ]
    return problems


def reference_encoding_problems() -> list[str]:
    """The reference implementation's capability statement lists text encodings that are registered, the five every
    Physical Parser decodes among them, and the Processing Model's note names exactly the further ones."""
    claims = json.loads((ROOT / "specification/reference-engine-claims.json").read_text(encoding="utf-8"))
    decoded = claims.get("encodings", {}).get("decoded")
    if not isinstance(decoded, list):
        return ["reference-engine-claims.json: no encodings.decoded list"]
    problems = [
        f"reference-engine-claims.json: {name!r} is no registered bddo:Encoding"
        for name in decoded
        if name not in BASE_ENCODINGS + FURTHER_ENCODINGS
    ]
    problems += [f"reference-engine-claims.json: {n} is not decoded" for n in BASE_ENCODINGS if n not in decoded]
    page = (ROOT / "specification/processing/index.html").read_text(encoding="utf-8")
    note = re.search(r'<span data-claim="encodings">(.*?)</span>', page, re.S)
    stated = set(re.findall(r"bddo:(\w+)", note.group(1))) if note else set()
    if stated != set(decoded) - set(BASE_ENCODINGS):
        problems.append(
            "processing/index.html#reference-implementation names other further encodings than the capability "
            f"statement: {sorted(stated ^ (set(decoded) - set(BASE_ENCODINGS)))}"
        )
    return problems


def round_trip_problems() -> list[str]:
    """The round-trip expectations name exactly the Physical Parser cases that state a tree, each with a known
    outcome, and the mode's comparison and verdicts hold on probes."""
    problems = []
    stated = round_trip.load_expectations()

    def derived(case_id: str, description: Path) -> str:
        return round_trip.expectation(case_id, description.read_bytes())[0]

    cases = {case_dir.name: case_dir for case_dir in round_trip.tree_cases()}
    for case_id in sorted(cases.keys() - stated.keys()):
        problems.append(f"{round_trip.EXPECTATIONS}: no entry for {case_id}, which states a tree")
    for case_id in sorted(stated.keys() - cases.keys()):
        problems.append(f"{round_trip.EXPECTATIONS}: names {case_id}, which is no Physical Parser case with a tree")
    for case_id, outcome in sorted(stated.items()):
        if outcome not in round_trip.OUTCOMES:
            problems.append(f"{round_trip.EXPECTATIONS}: {case_id} has the unknown outcome {outcome!r}")
        elif case_id in cases and outcome != derived(case_id, cases[case_id] / "description.ttl"):
            problems.append(f"{round_trip.EXPECTATIONS}: {case_id} is {outcome}, not what round_trip.py derives")
    if len(set(stated.values())) < len(round_trip.OUTCOMES):
        problems.append(f"{round_trip.EXPECTATIONS}: not every outcome of {round_trip.OUTCOMES} occurs")
    iso, judge = round_trip.isomorphism_problems, round_trip.judge
    tree = {"n": 3, "data": "0a0b", "items": [1.0, {"x": None}], "crc": 7}
    probes = (
        (iso(tree, json.loads(json.dumps(tree))) == [], "a tree is not isomorphic to itself"),
        (iso(tree, dict(tree, n=4)) != [], "a changed value went unnoticed"),
        (iso(tree, dict(tree, n=4), {"n"}) == [], "a recomputed derived value was compared"),
        (iso(tree, dict(tree, n=None), {"n"}) != [], "a recomputed value unbound in one tree went unnoticed"),
        (iso(tree, dict(tree, items=[1.0])) != [], "a shorter array went unnoticed"),
        (iso(tree, dict(tree, items=[1, {"x": None}])) != [], "an Integer for a Float went unnoticed"),
        (iso({"f": 0.0}, {"f": -0.0}) != [], "-0.0 was taken for 0.0"),
        (iso({"f": float("nan")}, {"f": float("nan")}) == [], "a NaN is not equal to a NaN"),
        (iso(tree, {k: v for k, v in tree.items() if k != "crc"}) != [], "a missing member went unnoticed"),
        (judge("round-trip", None, []) == ("PASS", ""), "an isomorphic round trip failed"),
        (judge("round-trip", None, ["$.n: 3 became 4"])[0] == "FAIL", "another tree passed"),
        (judge("round-trip", "Validation", None)[0] == "FAIL", "a refusal of a writable tree passed"),
        (judge("Unsupported", "Unsupported", None)[0] == "PASS", "the required refusal failed"),
        (judge("Unsupported", "Validation", None)[0] == "FAIL", "a refusal in another category passed"),
        (judge("Unsupported", None, [])[0] == "FAIL", "a stream where the rules refuse passed"),
        (judge("Validation", "Validation", None)[0] == "PASS", "the stated validation refusal failed"),
        (judge("Validation", None, [])[0] == "PASS", "an encoder that happens to fit failed"),
        (judge("Validation", None, ["x"])[0] == "FAIL", "another tree passed where a refusal was the alternative"),
    )
    return problems + [f"round_trip.py: {what}" for ok, what in probes if not ok]


def comparator_problems() -> list[str]:
    """The comparison rules this suite's newer case forms rest on: the sign of a zero, an error that is an equally
    conforming outcome of a Physical Parser case, a Writer case verified by round trip, and claimed encodings."""
    import tempfile

    import compare

    regex = SUITE / "physical-parser/pp-limit-regex-idle-iterations"
    trip = SUITE / WRITER / "w-codec-compressor-round-trip"
    claims = json.loads(
        (SUITE / "physical-parser/pp-claims-statement/expected-claims.json").read_text(encoding="utf-8")
    )
    stated = {"classes": ["Physical Parser"], "optionalFeatures": [], "codecs": claims["mustInclude"]["codecs"]}
    with tempfile.TemporaryDirectory() as tmp:

        def output(name: str, value: Any) -> Path:
            path = Path(tmp) / name
            path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
            return path

        tree = json.loads((regex / "expected.json").read_text(encoding="utf-8"))
        back = json.loads((trip / "expected.json").read_text(encoding="utf-8"))
        probes = (
            (compare.compare_tree({"f": 0.0}, {"f": -0.0}) != [], "-0.0 passed for 0.0"),
            (compare.compare_tree({"f": -0.0}, {"f": -0.0}) == [], "-0.0 failed for -0.0"),
            (compare.compare_case(regex, output("actual.json", tree)) == [], "the tree of an orError case failed"),
            (
                compare.compare_case(regex, output(compare.ERROR_FILE, {"category": "ResourceLimit"})) == [],
                "the orError category of a Physical Parser case failed",
            ),
            (
                compare.compare_case(regex, output(compare.ERROR_FILE, {"category": "Validation"})) != [],
                "another category passed for an orError case",
            ),
            (compare.compare_case(trip, output("actual.json", back)) == [], "a re-parsed tree failed its own case"),
            (
                compare.compare_case(trip, output("actual.json", dict(back, magic=0))) != [],
                "another re-parsed tree passed a case verified by round trip",
            ),
            (
                compare.compare_case(trip, output(compare.ERROR_FILE, {"category": "Unsupported"})) != [],
                "a refusal passed a case verified by round trip",
            ),
            (compare.compare_claims(claims, stated) == [], "a statement without encodings failed"),
            (
                compare.compare_claims(claims, dict(stated, encodings=[ENCODING_NAMESPACE + "shiftJis"])) == [],
                "a registered encoding failed",
            ),
            (
                compare.compare_claims(claims, dict(stated, encodings=[ENCODING_NAMESPACE + "klingon"])) != [],
                "an unregistered encoding passed",
            ),
            (compare.compare_claims(claims, dict(stated, encodings="shiftJis")) != [], "encodings as a string passed"),
        )
        return [f"compare.py: {what}" for ok, what in probes if not ok]


def runner_problems() -> list[str]:
    """The runner's round trips reach the verdicts the expectations call for, probed with a stand-in writer and
    parser (tools/conformance/stub_processor.py) that produce each outcome on demand."""
    import run_suite

    stub = f'"{Path(sys.executable).as_posix()}" "{(HERE / "conformance/stub_processor.py").as_posix()}"'
    write, parse = stub + " write {case} {out} {err}", stub + " parse {case} {out} {err}"
    claims = {"classes": ["Physical Parser"], "optionalFeatures": sorted(feature_tokens()), "codecs": []}
    parsers = SUITE / "physical-parser"

    def trip(case: str, expected: str, writer: str = write, parser: str = parse, stated: Any = claims) -> str:
        return run_suite.run_round_trip(parsers / case, writer, parser, stated, expected, 60)[0]

    def verified(writer: str, parser: str | None) -> str:
        case = SUITE / WRITER / "w-codec-compressor-round-trip"
        return run_suite.run_case(case, writer, claims, 60, parser=parser)[0]

    probes = (
        (trip("pp-bits-lsb-first", "round-trip") == "PASS", "a stream that parses back to the tree failed"),
        (trip("pp-bits-lsb-first", "round-trip", parser=parse + " --other-tree") == "FAIL", "another tree passed"),
        (
            trip("pp-bits-lsb-first", "round-trip", parser=parse + " --refuse Bounds") == "FAIL",
            "an unparsable stream passed",
        ),
        (
            trip("pp-bits-lsb-first", "round-trip", writer=write + " --refuse Validation") == "FAIL",
            "a refused tree passed",
        ),
        (
            trip("pp-kv-header", "Unsupported", writer=write + " --refuse Unsupported") == "PASS",
            "the required refusal failed",
        ),
        (trip("pp-kv-header", "Unsupported") == "FAIL", "a stream passed where the rules refuse"),
        (
            trip("pp-textnum-decimals", "Validation", writer=write + " --refuse Validation") == "PASS",
            "the stated refusal failed",
        ),
        (
            trip("pp-textnum-decimals", "Validation", writer=write + " --refuse Unsupported") == "FAIL",
            "another category passed",
        ),
        (
            trip("pp-bits-lsb-first", "round-trip", stated=dict(claims, optionalFeatures=[])) == "SKIP",
            "ran without the writer claim",
        ),
        (trip("pp-encoding-shift-jis-decodes", "round-trip") == "SKIP", "ran an encoding the claims do not list"),
        (verified(write, parse) == "PASS", "a Writer case verified by round trip failed"),
        (
            verified(write, parse + " --other-tree") == "FAIL",
            "a Writer case whose stream parses to another tree passed",
        ),
        (verified(write, None) == "SKIP", "a Writer case verified by round trip ran without a parser"),
    )
    return [f"run_suite.py: {what}" for ok, what in probes if not ok]


def section_ids(document: Any) -> Any:
    """The element ids of a page named as a case's section document (`processing`, `hel/index.html`)."""
    path = ROOT / "specification" / (document if "/" in document else f"{document}/index.html")
    if not path.is_file():
        return None
    return set(re.findall(r'\bid="([^"]+)"', path.read_text(encoding="utf-8")))


@dataclass
class Known:
    """What the cases are checked against: the live requirement identifiers, those of the serialisation rules, the
    feature tokens, and the element ids of the pages the cases name sections of (filled as pages are read)."""

    live: set[str]
    writer_requirements: set[str]
    features: set[str]
    pages: dict[str, Any] = field(default_factory=dict)


def member_problems(cls: str, man: dict[str, Any], known: Known) -> list[str]:
    """The optional manifest members that steer a run: limits, features, codecs, withdrawn claims and the flags of
    particular classes."""
    problems = []
    for limit in man.get("limits", {}):
        if limit not in LIMITS:
            problems.append(f"unknown limit {limit}")
    for kind, names in man.get("features", {}).items():
        if kind not in ("requires", "unclaimed"):
            problems.append(f"unknown features member {kind}")
        for name in names:
            if name not in known.features:
                problems.append(f"{name!r} is not a feature token of the Processing Model's optional features")
    for kind, iris in man.get("codecs", {}).items():
        if kind not in ("requires", "unclaimed"):
            problems.append(f"unknown codecs member {kind}")
        for iri in iris:
            if not iri.startswith("https://hexplain.io/ns/register/media-encoding#"):
                problems.append(f"codecs names {iri!r}, which is not a media-encoding register IRI")
    for kind, names in man.get("claims", {}).items():
        if kind != "withdraw":
            problems.append(f"unknown claims member {kind}")
        for name in names:
            if name not in known.features:
                problems.append(f"claims withdraws {name!r}, which is not a feature token")
    if "compareOntologyHeader" in man and (cls != "hdl-compiler" or not isinstance(man["compareOntologyHeader"], bool)):
        problems.append("compareOntologyHeader is a Boolean of an HDL Compiler case")
    if "base" in man and man["base"] is None and cls != "semantic-emitter":
        problems.append("only a Semantic Emitter case may leave the base to the processor")
    if man.get("parseMode", "lenient") not in ("lenient", "strict"):
        problems.append("parseMode is lenient or strict")
    for key in ("reportConformsToShapes",):
        if key in man and (cls != "conformance-evaluator" or not isinstance(man[key], bool)):
            problems.append(f"{key} is a Boolean of a Conformance Evaluator case")
    if man.get("reportForm", "json") not in ("json", "rdf"):
        problems.append("reportForm is json or rdf")
    if man.get("check") not in (None, "claims"):
        problems.append(f"unknown check {man['check']!r}")
    if man.get("orError") and man["orError"] not in CATEGORIES:
        problems.append(f"unknown orError category {man['orError']}")
    return problems


def case_problems(cls: str, case_dir: Path, man: dict[str, Any], known: Known) -> list[str]:
    """Everything wrong with one case: its manifest, the files it names, and its expected artifact."""
    where = f"{cls}/{case_dir.name}"
    problems = []
    for key in REQUIRED:
        if not man.get(key):
            problems.append(f"{where}: manifest lacks {key}")
    if man.get("id") != case_dir.name or man.get("class") != cls or not case_dir.name.startswith(PREFIX[cls] + "-"):
        problems.append(f"{where}: id, class and directory disagree")
    for rid in man.get("requirements", []):
        if rid not in known.live:
            problems.append(f"{where}: cites {rid}, which the requirement registry does not list")
    if man.get("requirements") and not set(man["requirements"]) - set(BLANKET):
        problems.append(f"{where}: cites only blanket requirements {man['requirements']}; cite the specific rule")
    for section in man.get("sections", []):
        document, _, anchor = section.partition("#")
        if document not in known.pages:
            known.pages[document] = section_ids(document)
        if known.pages[document] is None or anchor not in known.pages[document]:
            problems.append(f"{where}: section {section} does not exist")
    if cls == WRITER:
        problems += writer_problems(case_dir, man, known.writer_requirements)
    elif (case_dir / "expected.hex").is_file() or (case_dir / TREE).is_file() or "verify" in man:
        problems.append(f"{where}: {TREE}, expected.hex and verify belong to a Writer case")
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
    for name in ["description.ttl", "rules.ttl", "expected.ttl", "expected-report.ttl"] + list(
        man.get("registers", [])
    ):
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
    problems += [f"{where}: {p}" for p in member_problems(cls, man, known)]
    problems += [f"{where}: {p}" for p in gating_problems(case_dir, man, cls)]
    return problems


def main() -> int:
    problems = []
    wanted = generate_inputs.expected_tree()
    present = generate_inputs.on_disk()
    stale = sorted(p for p in wanted.keys() | present.keys() if wanted.get(p) != present.get(p))
    if stale:
        problems.append(
            f"{len(stale)} suite file(s) differ from tools/conformance/ (run python "
            f"tools/conformance/generate_inputs.py): {stale[:5]}"
        )

    registry = json.loads((SUITE / "requirements.json").read_text(encoding="utf-8"))["requirements"]
    live = {i for i, e in registry.items() if not e.get("withdrawn")}
    problems += context_problems(registry)
    counts = {cls: 0 for cls in CLASSES}
    writer_requirements = {i for i in live if registry[i]["cls"] == WRITER}
    known = Known(live, writer_requirements, set(feature_tokens()))
    writer_cited = set()
    for cls in CLASSES:
        for case_dir in sorted(p for p in (SUITE / cls).iterdir() if p.is_dir()):
            where = f"{cls}/{case_dir.name}"
            manifest_path = case_dir / "manifest.json"
            if not manifest_path.is_file():
                problems.append(f"{where}: no manifest.json")
                continue
            counts[cls] += 1
            man = json.loads(manifest_path.read_text(encoding="utf-8"))
            problems += case_problems(cls, case_dir, man, known)
            if cls == WRITER:
                writer_cited |= set(man.get("requirements", []))
    by_mode = set(_build_conformance_page.OBSERVED_BY_ROUND_TRIP)
    for rid in sorted(writer_requirements - writer_cited - by_mode):
        problems.append(f"{rid}: a live serialisation requirement no Writer case cites")
    for rid in sorted(by_mode & writer_cited):
        problems.append(f"{rid}: observed by the round-trip mode, which is its citation; no single case shows it")
    problems += round_trip_problems()
    problems += reference_encoding_problems()
    problems += comparator_problems()
    problems += runner_problems()
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
    print(
        f"PASS: {sum(counts.values())} conformance cases ({', '.join(f'{c} {n}' for c, n in counts.items())}) "
        f"cite {len(live)} registered requirements consistently"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
