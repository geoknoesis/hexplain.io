"""Generate the coverage section of specification/conformance/index.html and coverage.json.

Coverage is read from the case manifests on disk and the requirement registry: a requirement is
covered when at least one case cites its ID. Run after regenerating the suite:

    python tools/conformance/generate_inputs.py
    python tools/_build_conformance_page.py            # rewrite the generated section
    python tools/_build_conformance_page.py --check    # exit 1 when it is stale
"""
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "specification/conformance"
PAGE = SUITE / "index.html"
COVERAGE = SUITE / "coverage.json"
BEGIN, END = "<!-- BEGIN GENERATED COVERAGE -->", "<!-- END GENERATED COVERAGE -->"
CASE_CLASSES = ("physical-parser", "semantic-emitter", "bundle-processor", "hdl-compiler", "conformance-evaluator")
REQUIREMENT_CLASSES = (("physical-parser", "Physical Parser (Processing Model)"),
                       ("hel", "HEL"),
                       ("semantic-emitter", "Semantic Emitter (Processing Model)"),
                       ("bundle-processor", "Bundle Processor (Processing Model)"),
                       ("conformance-evaluator", "Conformance Evaluator (Processing Model, conf, req)"),
                       ("hdl-compiler", "HDL Compiler"))
PAGE_LINKS = {"specification/processing/index.html": "../processing/index.html",
              "specification/hel/index.html": "../hel/index.html",
              "specification/hdl/index.html": "../hdl/index.html",
              "specification/conf/index.html": "../conf/index.html",
              "specification/req/index.html": "../req/index.html",
              "specification/bddo/index.html": "../bddo/index.html",
              "specification/dlv/index.html": "../dlv/index.html",
              "specification/hexplain/index.html": "../hexplain/index.html",
              "specification/aspect/bundle/index.html": "../aspect/bundle/index.html",
              "specification/aspect/geometry/index.html": "../aspect/geometry/index.html",
              "specification/aspect/raster/index.html": "../aspect/raster/index.html",
              "specification/aspect/spatialref/index.html": "../aspect/spatialref/index.html"}


def manifests():
    out = []
    for cls in CASE_CLASSES:
        for path in sorted((SUITE / cls).glob("*/manifest.json")):
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def registry():
    return json.loads((SUITE / "requirements.json").read_text(encoding="utf-8"))["requirements"]


#: Requirements every case may cite without saying anything specific (tools/conformance/suite.py BLANKET): they are
#: left out of the coverage figures, since citing them shows nothing about which rule a case exercises.
BLANKET = ("req-pm-conformance-1", "req-pm-introduction-1", "req-hdl-conformance-section-1", "req-hel-conformance-1",
           "req-ce-conf-conformance-1")
#: The processor conformance classes, and the requirement classes of the registry whose MUSTs each must meet.
PROCESSOR_CLASSES = (("Physical Parser", ("physical-parser", "hel")), ("Semantic Emitter", ("semantic-emitter",)),
                     ("Bundle Processor", ("bundle-processor",)), ("HDL Compiler", ("hdl-compiler",)),
                     ("Conformance Evaluator", ("conformance-evaluator",)))


#: Processor MUSTs that no case of this suite can observe, and why. Each is still a requirement: it is met by the
#: evidence named, or checked only by inspection. The build fails when an entry is withdrawn, is not a processor MUST,
#: or is cited by a case (then it is testable after all, and the entry is stale).
NOT_SUITE_TESTABLE = {
    "req-bddo-conformance-1": "Binds a SHACL validator of description graphs, not a processor of streams; the family's "
                              "shape gates (test_shapes, test_vocab_shapes) apply it.",
    "req-core-punning-1": "Whether a processor relies on a DL entailment is not observable from its output: a case "
                          "cannot tell a processor that did not reason from one whose reasoning happened to agree.",
    "req-geometry-document-1": "Binds a consumer that interprets lifted geometry; a Semantic Emitter emits the mapped "
                               "ordinates unchanged, and the suite has no case format for interpretation.",
    "req-raster-document-3": "Binds a consumer that interprets a raster description; cell addressing is the data "
                             "layout's (DLV), which the Physical Parser cases cover.",
    "req-spatialref-document-2": "Binds a processor that evaluates spatial-reference transforms (the hxf function "
                                 "library's world and cell functions), which the processor suite does not exercise.",
    "req-spatialref-document-3": "Binds a processor that evaluates spatial-reference transforms (the hxf function "
                                 "library's hxf:column and hxf:row), which the processor suite does not exercise.",
    "req-spatialref-document-4": "A documentation requirement on a floating-point implementation, checked by reading "
                                 "its documentation.",
    "req-spatialref-document-10": "Binds a processor that evaluates rational polynomial transforms, which no processor "
                                  "class of the Processing Model does.",
    "req-spatialref-document-11": "Binds a processor that evaluates rational polynomial transforms, which no processor "
                                  "class of the Processing Model does.",
    "req-pm-privacy-1": "The runner cannot tell a base IRI derived from the input's file name from any other base the "
                        "processor reports; se-base-reported checks that the base is chosen and reported.",
    "req-hel-error-conditions-1": "A processor case observes only the Processing Model category (Expression); the "
                                  "condition is asserted by the HEL vectors (validation/test/hel-vectors.tsv, "
                                  "req-hel-conformance-9).",
    "req-hdl-modules-3": "The import bounds are the compiler's own; a case would need an imported file larger than every "
                         "conforming compiler's bound, and no size is.",
}


def counted(entry, rid):
    """Whether a requirement counts toward coverage: live, not blanket, and binding a processor (a requirement whose
    registry audience is description binds only the author of a description, which no processor case can observe)."""
    return not entry.get("withdrawn") and rid not in BLANKET and entry.get("audience", "processor") != "description"


def coverage():
    reqs = {i: e for i, e in registry().items() if counted(e, i)}
    cases = manifests()
    citing = defaultdict(list)
    for case in cases:
        for rid in case["requirements"]:
            citing[rid].append(case["id"])
    classes = {}
    for cls, _ in REQUIREMENT_CLASSES:
        row = {}
        for level in ("MUST", "SHOULD"):
            # A rule on a description's author (audience "description") is no processor's to meet.
            ids = [i for i, e in reqs.items() if e["cls"] == cls and e["level"] == level
                   and e.get("audience", "processor") == "processor"]
            covered = [i for i in ids if citing.get(i)]
            row[level] = {"total": len(ids), "covered": len(covered)}
        classes[cls] = row
    kinds = Counter()
    for case in cases:
        kinds[case["class"]] += 1
    sections = Counter(s for case in cases for s in case["sections"])
    processors = {}
    for label, members in PROCESSOR_CLASSES:
        ids = [i for i, e in reqs.items() if e["cls"] in members and e["level"] == "MUST"]
        processors[label] = {"total": len(ids), "covered": sum(1 for i in ids if citing.get(i)),
                             "notSuiteTestable": {i: NOT_SUITE_TESTABLE[i] for i in sorted(ids) if i in NOT_SUITE_TESTABLE},
                             "uncovered": sorted(i for i in ids if not citing.get(i) and i not in NOT_SUITE_TESTABLE)}
    musts = {i for i, e in reqs.items() if e["level"] == "MUST" and e.get("audience", "processor") == "processor"}
    stale = sorted(i for i in NOT_SUITE_TESTABLE if i not in musts or citing.get(i))
    if stale:
        raise SystemExit("NOT_SUITE_TESTABLE lists a withdrawn, non-MUST or cited requirement: " + ", ".join(stale))
    return {
        "cases": {cls: kinds[cls] for cls in CASE_CLASSES},
        "excluded": {"blanket": list(BLANKET), "audience": "description"},
        "processorMust": processors,
        "requirements": classes,
        "citations": {i: sorted(citing.get(i, [])) for i, e in registry().items() if not e.get("withdrawn")},
        "withdrawn": sorted(i for i, e in registry().items() if e.get("withdrawn")),
        "reports": published_reports(),
        "sections": dict(sorted(sections.items())),
    }


def published_reports():
    """The implementation reports under specification/conformance/reports/, summarised for the page."""
    out = []
    for path in sorted((SUITE / "reports").glob("*/*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        impl, counts = report.get("implementation", {}), report.get("counts", {})
        out.append({"path": path.relative_to(SUITE).as_posix(), "name": impl.get("name", ""),
                    "version": impl.get("version", ""), "date": report.get("run", {}).get("date", ""),
                    "digest": report.get("suite", {}).get("digest", ""),
                    **{s: counts.get(s, 0) for s in ("PASS", "FAIL", "SKIP")}})
    return out


def percent(covered, total):
    return f"{100 * covered / total:.0f}%" if total else "&ndash;"


def render(data):
    reqs = {i: e for i, e in registry().items() if not e.get("withdrawn")}
    total_cases = sum(data["cases"].values())
    rows = "".join(f"<tr><td>{c}</td><td>{n}</td></tr>" for c, n in data["cases"].items())
    parts = [BEGIN, '<section id="coverage"><h2>Coverage</h2>',
             f"<p>{total_cases} cases. A requirement counts as covered when at least one case cites its identifier; "
             "a case cites the requirements whose text its expected output is read from. The table is generated from "
             "the case manifests and the requirement registry (<a href=\"coverage.json\">coverage.json</a>); "
             "a processor MUST that no black-box case can observe is listed, with the reason, under "
             "<a href=\"#not-suite-testable\">Requirements no case can observe</a>. The "
             "figures leave out the blanket requirements every case may cite (" + ", ".join(f"<code>{b}</code>" for b in BLANKET)
             + ") and the requirements whose registry audience is <code>description</code>, which bind the author of a "
             "description rather than a processor.</p>",
             '<div class="table"><table><thead><tr><th>Case class</th><th>Cases</th></tr></thead><tbody>',
             rows, "</tbody></table></div>",
             '<div class="table"><table><thead><tr><th>Requirements of</th><th>MUST-level covered</th>'
             "<th>SHOULD-level covered</th></tr></thead><tbody>"]
    for cls, label in REQUIREMENT_CLASSES:
        must, should = data["requirements"][cls]["MUST"], data["requirements"][cls]["SHOULD"]
        parts.append(f"<tr><td>{label}</td><td>{must['covered']} of {must['total']} "
                     f"({percent(must['covered'], must['total'])})</td><td>{should['covered']} of {should['total']} "
                     f"({percent(should['covered'], should['total'])})</td></tr>")
    parts.append("</tbody></table></div>")
    parts.append('<h3 id="processor-coverage">Processor MUSTs by conformance class</h3><p>The MUST-level requirements '
                 "a processor of each class is bound by (a Physical Parser by the Processing Model's physical rules and "
                 "by HEL), how many at least one case cites, those no case can observe (listed below with the reason), "
                 "and those no case cites yet.</p>"
                 '<div class="table"><table><thead><tr><th>Conformance class</th><th>MUSTs covered</th>'
                 "<th>Not testable by a case</th><th>Not yet cited</th></tr></thead><tbody>")
    for label, row in data["processorMust"].items():
        missing = ", ".join(f"<code>{html.escape(i)}</code>" for i in row["uncovered"]) or "none"
        untestable = len(row["notSuiteTestable"])
        parts.append(f"<tr><td>{label}</td><td>{row['covered']} of {row['total']} ({percent(row['covered'], row['total'])})"
                     f"</td><td>{untestable}</td><td>{missing}</td></tr>")
    parts.append("</tbody></table></div>")
    parts.append('<h3 id="not-suite-testable">Requirements no case can observe</h3><p>A processor still has to meet them; '
                 "the reason says what can show that it does.</p>"
                 '<div class="table"><table><thead><tr><th>Requirement</th><th>Why no case</th></tr></thead><tbody>')
    for row in data["processorMust"].values():
        for rid, why in row["notSuiteTestable"].items():
            link = PAGE_LINKS[reqs[rid]["page"]]
            parts.append(f'<tr><td><a href="{link}#{rid}"><code>{rid}</code></a></td><td>{html.escape(why)}</td></tr>')
    parts.append("</tbody></table></div>")
    parts.append('<h3 id="published-reports">Published implementation reports</h3>')
    reports = data["reports"]
    if reports:
        parts.append('<div class="table"><table><thead><tr><th>Implementation</th><th>Version</th><th>Run</th>'
                     "<th>Pass</th><th>Fail</th><th>Skip</th><th>Suite</th></tr></thead><tbody>")
        for r in reports:
            parts.append(f'<tr><td><a href="{html.escape(r["path"])}">{html.escape(r["name"])}</a></td>'
                         f'<td>{html.escape(r["version"])}</td><td>{html.escape(r["date"])}</td><td>{r["PASS"]}</td>'
                         f'<td>{r["FAIL"]}</td><td>{r["SKIP"]}</td><td><code>{html.escape(r["digest"][:12])}</code></td></tr>')
        parts.append("</tbody></table></div>")
    else:
        parts.append("<p>None yet (<a href=\"#implementation-reports\">Implementation reports</a> says where they are "
                     "published).</p>")
    parts.append('<h3 id="requirement-index">Requirement index</h3><p>Every anchored requirement, its level and the cases '
                 "that cite it.</p>")
    by_page = defaultdict(list)
    for rid, entry in reqs.items():
        by_page[entry["page"]].append((rid, entry))
    for page, items in by_page.items():
        link = PAGE_LINKS[page]
        parts.append(f'<details><summary>{html.escape(page)} ({len(items)})</summary><div class="table"><table>'
                     "<thead><tr><th>Requirement</th><th>Level</th><th>Text</th><th>Cases</th></tr></thead><tbody>")
        for rid, entry in items:
            # Cut at a word boundary, so a CURIE is never left half-spelt (test_doc_terms reads it).
            text = entry["text"] if len(entry["text"]) <= 180 else entry["text"][:177].rsplit(" ", 1)[0] + " ..."
            cited = data["citations"][rid]
            shown = ", ".join(cited[:3]) + (f" and {len(cited) - 3} more" if len(cited) > 3 else "")
            parts.append(f'<tr><td><a href="{link}#{rid}"><code>{rid}</code></a></td><td>{entry["level"]}</td>'
                         f"<td>{html.escape(text)}</td><td>{html.escape(shown) if cited else 'none'}</td></tr>")
        parts.append("</tbody></table></div></details>")
    parts.append("</section>")
    parts.append(END)
    return "\n".join(parts)


def expected_page(source):
    start, end = source.index(BEGIN), source.index(END) + len(END)
    return source[:start] + render(coverage()) + source[end:]


def main(argv):
    source = PAGE.read_text(encoding="utf-8")
    page = expected_page(source)
    data = json.dumps(coverage(), indent=1, ensure_ascii=False) + "\n"
    if "--check" in argv:
        stale = [p.name for p, want in ((PAGE, page), (COVERAGE, data))
                 if not p.is_file() or p.read_text(encoding="utf-8") != want]
        if stale:
            print(f"FAIL: {', '.join(stale)} stale; run python tools/_build_conformance_page.py")
            return 1
        print("PASS: conformance coverage page and coverage.json are current")
        return 0
    PAGE.write_text(page, encoding="utf-8", newline="\n")
    COVERAGE.write_text(data, encoding="utf-8", newline="\n")
    print("wrote specification/conformance/index.html coverage and coverage.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
