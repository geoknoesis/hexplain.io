"""Competency cases for the conformance, requirement and function vocabularies.

conf, req and fn had shapes and fixtures but no case in a shared competency corpus, so the
competency trace, and the capability summary built from it, showed none of their resources as
exercised. specification/validation/test/conformance-competency.tsv holds independently
written cases -- one conforming and one or more non-conforming per competency question -- in
the four-column corpus format (name, conforms, expected result path, base64 Turtle). This gate
validates each against the conf, req and fn shapes and checks the stored corpus is current;
run it with --write after changing a case.
"""
import base64
import sys
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

import specgraph

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "specification/validation/test/conformance-competency.tsv"
SHAPES = ["specification/conf/conf.ttl", "specification/conf/shapes.ttl", "specification/req/req.ttl",
          "specification/req/shapes.ttl", "specification/fn/fn.ttl"]
SH = Namespace("http://www.w3.org/ns/shacl#")
P = """@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req: <https://hexplain.io/ns/req#> .
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix hxf: <https://hexplain.io/ns/fn#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:conformance-competency:> .
"""
REQ = """ex:r1 a req:Requirement ; req:requirementId "R-1" ; req:fromStandard "Example Format 2.0" ;
    req:statement "The magic shall be HX." ; req:discrepancyType req:Syntactic ; req:appliesToVersion "2.0" .
ex:r2 a req:Requirement ; req:requirementId "R-2" ; req:fromStandard "Example Format 2.0" ;
    req:statement "The count shall be positive." ; req:discrepancyType req:Semantic .
ex:Header a bddo:Struct . ex:count a bddo:Field .
"""
CON = """ex:c1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HX'" ;
    conf:satisfies ex:r1 ; conf:message "Magic is {value}." ; conf:severity sh:Violation .
ex:c2 a conf:Constraint ; conf:scope ex:count ; conf:assertion "self > 0" ;
    conf:satisfies ex:r2 ; conf:message "{field} is {value}, not positive." ; conf:severity sh:Warning .
"""
NS = {"conf": "https://hexplain.io/ns/conf#", "req": "https://hexplain.io/ns/req#", "hxf": "https://hexplain.io/ns/fn#"}


def cases():
    rows = []

    def add(name, body, ok, path=""):
        prefix, local = path.split(":") if path else ("", "")
        rows.append((name, ok, NS[prefix] + local if path else "", P + body))
    # Which requirements does a profile check, and at what severity? (declared coverage)
    add("struct- and field-scoped constraints citing requirements", REQ + CON, True)
    add("constraint citing a non-requirement", REQ + CON.replace("conf:satisfies ex:r2", "conf:satisfies ex:count"),
        False, "conf:satisfies")
    add("constraint scoped to something that is not a struct or field",
        REQ + CON.replace("conf:scope ex:count", "conf:scope ex:r1"), False, "conf:scope")
    add("constraint with two severities", REQ + CON.replace("conf:severity sh:Warning", "conf:severity sh:Warning , sh:Info"),
        False, "conf:severity")
    # Which requirement does a parse error break? (parse attribution)
    add("parse attribution of a checksum error", REQ + 'ex:pa a conf:ParseAttribution ; conf:errorCategory "Checksum" ; conf:satisfies ex:r1 .', True)
    add("parse attribution naming an unknown category",
        REQ + 'ex:pa a conf:ParseAttribution ; conf:errorCategory "Crc" ; conf:satisfies ex:r1 .', False, "conf:errorCategory")
    # What did a run find, and how did each requirement fare? (findings and run coverage)
    run = (REQ + CON + 'ex:f1 a conf:Finding ; conf:findingKind conf:Violation ; conf:findingConstraint ex:c1 ; '
           'conf:findingRequirement ex:r1 ; conf:severity sh:Violation ; conf:findingMessage "Magic is XX." ; conf:focusNode ex:h0 .\n'
           'ex:f2 a conf:Finding ; conf:findingKind conf:Parse ; conf:errorCategory "Bounds" ; conf:severity sh:Violation ; '
           'conf:findingMessage "Truncated at byte 12." .\n'
           'ex:run a conf:Run ; conf:outcome [ conf:outcomeRequirement ex:r1 ; conf:outcomeValue conf:Evaluated ] , '
           '[ conf:outcomeRequirement ex:r2 ; conf:outcomeValue conf:NotReached ] .\n')
    add("run with a violation, an unattributed parse finding and two outcomes", run, True)
    add("finding attributed to a requirement its constraint does not cite",
        run.replace("conf:findingRequirement ex:r1 ;", "conf:findingRequirement ex:r1 , ex:r2 ;"), False)
    add("outcome value that is a finding kind",
        run.replace("conf:outcomeValue conf:NotReached", "conf:outcomeValue conf:RuleError"), False, "conf:outcomeValue")
    add("rule error without its constraint",
        run.replace("conf:findingKind conf:Violation ; conf:findingConstraint ex:c1 ;", "conf:findingKind conf:RuleError ;"), False)
    # Is a requirement identified once? (requirement identity)
    add("same identifier in two standards", REQ + 'ex:r3 a req:Requirement ; req:requirementId "R-1" ; '
        'req:fromStandard "Other Format 1.0" ; req:statement "Other." ; req:discrepancyType req:Functional .', True)
    add("same identifier in one standard written with other case", REQ + 'ex:r3 a req:Requirement ; req:requirementId "R-1" ; '
        'req:fromStandard "example format 2.0" ; req:statement "Again." ; req:discrepancyType req:Syntactic .', False)
    add("empty version", REQ.replace('req:appliesToVersion "2.0"', 'req:appliesToVersion ""'), False, "req:appliesToVersion")
    # Does every native function say when it answers nothing? (function contract)
    add("native function declaring when it is unbound",
        'ex:fn a hxf:Function ; hxf:kind hxf:Native ; hxf:unboundWhen "The index is outside the array."@en .', True)
    add("native function declaring nothing", "ex:fn a hxf:Function ; hxf:kind hxf:Native .", False)
    add("window limit of zero", "ex:cfg hxf:maxCellsPerWindow 0 .", False, "hxf:maxCellsPerWindow")
    return rows


def render(rows):
    lines = ["# Conformance, requirement and function competency cases (tools/test_conformance_competency.py --write).",
             "# name\tconforms\texpected-path\tbase64 Turtle"]
    for name, ok, path, body in rows:
        lines.append("\t".join([name, "true" if ok else "false", path, base64.b64encode(body.encode()).decode()]))
    return "\n".join(lines) + "\n"


def main():
    shapes = specgraph.load([str(ROOT / p) for p in SHAPES])
    family = specgraph.ontologies()
    rows = cases()
    for name, ok, path, body in rows:
        data = Graph().parse(data=body, format="turtle")
        conforms, report, text = validate(data, shacl_graph=shapes, ont_graph=family, inference="none", advanced=True)
        assert bool(conforms) == ok, (name, text)
        if path:
            assert URIRef(path) in report.objects(None, SH.resultPath), (name, text)
    expected = render(rows)
    if "--write" in sys.argv:
        CORPUS.write_text(expected, encoding="utf-8", newline="\n")
    if not CORPUS.exists() or CORPUS.read_text(encoding="utf-8") != expected:
        print("FAIL: conformance-competency.tsv is stale; run python tools/test_conformance_competency.py --write")
        sys.exit(1)
    print(f"PASS: {len(rows)} conformance, requirement and function competency cases with result-path assertions")


if __name__ == "__main__":
    main()
