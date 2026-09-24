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
              "specification/req/index.html": "../req/index.html"}


def manifests():
    out = []
    for cls in CASE_CLASSES:
        for path in sorted((SUITE / cls).glob("*/manifest.json")):
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def registry():
    return json.loads((SUITE / "requirements.json").read_text(encoding="utf-8"))["requirements"]


def coverage():
    reqs = {i: e for i, e in registry().items() if not e.get("withdrawn")}
    cases = manifests()
    citing = defaultdict(list)
    for case in cases:
        for rid in case["requirements"]:
            citing[rid].append(case["id"])
    classes = {}
    for cls, _ in REQUIREMENT_CLASSES:
        row = {}
        for level in ("MUST", "SHOULD"):
            ids = [i for i, e in reqs.items() if e["cls"] == cls and e["level"] == level]
            covered = [i for i in ids if citing.get(i)]
            row[level] = {"total": len(ids), "covered": len(covered)}
        classes[cls] = row
    kinds = Counter()
    for case in cases:
        kinds[case["class"]] += 1
    sections = Counter(s for case in cases for s in case["sections"])
    return {
        "cases": {cls: kinds[cls] for cls in CASE_CLASSES},
        "requirements": classes,
        "citations": {i: sorted(citing.get(i, [])) for i in reqs},
        "sections": dict(sorted(sections.items())),
    }


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
             "requirements that no black-box case can observe, such as a processor stating its claims, stay "
             "uncovered here and are listed below with no case.</p>",
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
