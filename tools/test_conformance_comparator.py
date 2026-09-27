"""The conformance suite's standalone comparator (tools/conformance/compare.py) compares as the suite page says.

Unit checks of each comparison rule of specification/conformance/index.html#canonicalisation -- the HEL parser and
canonical form, tree comparison (Integer and Float kept apart), graph comparison (literals by value but datatypes
exactly, HEL literals by equivalence, the ontology header, extents, the bundle profile, the reported base), error
and diagnostic comparison, the report summary, the RDF report embedding, and the claims statement -- and then a
self-check: every expected artifact of the suite, offered as the actual output, passes its own case.
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "conformance"))

import compare  # noqa: E402
import hel  # noqa: E402
from suite import SUITE  # noqa: E402

PREFIXES = """@prefix bddo: <https://hexplain.io/ns/bddo#> . @prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix conf: <https://hexplain.io/ns/conf#> . @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <urn:ex#> .
"""


def graph(body):
    return compare.load_graph(PREFIXES + body)


def check(condition, message, failures):
    if not condition:
        failures.append(message)


def hel_checks(failures):
    check(hel.canonical("Flags&0x01==1 and not(done)") == "((instance.Flags & 1) == 1) and not instance.done",
          "the HEL page's canonical-form example", failures)
    check(hel.equivalent("n*2", "instance.n * 2"), "a bare name is instance.<name>; spacing does not matter", failures)
    check(hel.equivalent("a + b + c", "(a + b) + c"), "redundant parentheses do not matter", failures)
    check(not hel.equivalent("a + (b + c)", "a + b + c"), "grouping that changes the tree matters", failures)
    check(hel.equivalent("x == 0x10", "x == 16"), "a hex literal is its Integer", failures)
    check(hel.equivalent("f == 0.50", "f == 5e-1"), "a float literal is its binary64 value", failures)
    check(not hel.equivalent("f == 1", "f == 1.0"), "an Integer and a Float literal differ", failures)
    check(hel.equivalent("a ? b : c ? d : e", "a ? b : (c ? d : e)"), "the ternary is right-associative", failures)
    check(hel.canonical("a < b < c") is None, "comparisons do not chain", failures)
    check(hel.canonical("9223372036854775808") is None, "an Integer literal above 2^63-1 is a syntax error", failures)
    check(hel.canonical("root.self") is None, "a reserved word is not a key", failures)
    check(hel.canonical("'\\q'") is None, "an unknown escape is a syntax error", failures)
    check(hel.canonical("'a\x01b'") == "'a\\x01b'", "a control character is written \\xHH in the canonical form", failures)
    check(hel.canonical("'a\tb'") == "'a\tb'", "a tab stays itself in the canonical form", failures)
    check(hel.canonical("'\\uD83D\\uDE00'") == "'\U0001F600'", "a surrogate pair denotes one code point", failures)
    check(hel.canonical("'\\uD800'") is None, "a lone surrogate is an error", failures)
    check(hel._float(1e7) == "1.0E7" and hel._float(0.05) == "0.05" and hel._float(1e-4) == "1.0E-4",
          "floats are spelt as Java's Double.toString spells them", failures)
    check(hel.canonical("root.Directory[i].Entries[0].Tag") == "root.Directory[instance.i].Entries[0].Tag",
          "subscripts and key steps", failures)


def tree_checks(failures):
    check(compare.compare_tree({"a": 1, "b": [2.5]}, {"b": [2.5], "a": 1}) == [], "member order does not matter", failures)
    check(compare.compare_tree({"a": 1}, {"a": 1.0}) != [], "an expected Integer is not matched by a Float", failures)
    check(compare.compare_tree({"a": 1.0}, {"a": 1}) != [], "an expected Float is not matched by an Integer", failures)
    check(compare.compare_tree({"a": None}, {}) != [], "an unbound field is null, not missing", failures)
    check(compare.compare_tree({"x": "NaN"}, {"x": "NaN"}) == [], "NaN is the string NaN", failures)
    check(compare.compare_tree({"x": "18446744073709551615"}, {"x": 18446744073709551615}) != [],
          "an Integer above 2^53 is its decimal string", failures)


def graph_checks(failures):
    base = graph('ex:f bddo:size "4"^^xsd:integer ; bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; '
                 'bddo:sizeFromExpression "instance.n * 2" .')
    same = graph('ex:f bddo:size "04"^^xsd:integer ; bddo:hasFixedValue "0a0b"^^xsd:hexBinary ; bddo:sizeFromExpression "n*2" .')
    check(compare.compare_graph(base, same, cls="hdl-compiler") == [],
          "literals compare by value, and HEL literals by equivalence", failures)
    typed = graph('ex:f bddo:size "4"^^xsd:integer ; bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; '
                  'bddo:sizeFromExpression "n*2"^^bddo:HelExpression .')
    check(compare.compare_graph(base, typed, cls="hdl-compiler") == [],
          "a HEL literal typed bddo:HelExpression is the same expression as the xsd:string one", failures)
    wider = graph('ex:f bddo:size "4"^^xsd:long ; bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; '
                  'bddo:sizeFromExpression "instance.n * 2" .')
    check(compare.compare_graph(base, wider, cls="hdl-compiler") != [], "HDL literal datatypes must match exactly", failures)
    header = graph('<urn:ex> a owl:Ontology ; owl:imports <urn:other> ; owl:versionInfo "1" . ex:f bddo:size "4"^^xsd:integer ; '
                   'bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; bddo:sizeFromExpression "instance.n * 2" .')
    check(compare.compare_graph(base, header, cls="hdl-compiler") == [], "the ontology header is ignored by default", failures)
    check(compare.compare_graph(base, header, cls="hdl-compiler", manifest={"compareOntologyHeader": True}) != [],
          "compareOntologyHeader compares the header", failures)
    extent = graph('ex:r a ex:C ; hexplain:byteOffset 0 ; hexplain:byteLength 4 .')
    check(compare.compare_graph(graph('ex:r a ex:C .'), extent, cls="semantic-emitter") == [],
          "the optional extent annotations are removed", failures)
    reported = compare.load_graph('<urn:uuid:1234#root> a <urn:ex#C> .')
    check(compare.compare_graph(compare.load_graph(f'<{compare.REPORTED_BASE}#root> a <urn:ex#C> .'), reported,
                                cls="semantic-emitter", reported_base="urn:uuid:1234") == [],
          "the reported base is read as the placeholder", failures)
    bundle = graph('ex:P a ex:Profile ; ex:spec [ ex:x 1 ] . ex:asset a ex:Asset .')
    check(compare.compare_graph(graph('ex:asset a ex:Asset .'), bundle, cls="bundle-processor",
                                manifest={"bundleProfile": "urn:ex#P"}) == [],
          "the bundle profile's closure is removed", failures)


def other_checks(failures):
    check(compare.compare_error({"category": "Bounds"}, {"category": "Bounds"}) == [], "an error category matches", failures)
    check(compare.compare_error({"category": "Bounds"}, {"category": "Validation"}) != [], "another category fails", failures)
    check(compare.compare_error({"category": "Dispatch"}, {"category": "DISPATCH"}, {"DISPATCH": "Dispatch"}) == [],
          "an implementation's name maps to its category", failures)
    diags = {"diagnostics": [{"severity": "WARNING", "line": 2}, {"severity": "ERROR", "line": 3}], "output": False}
    check(compare.compare_hdl_error({"severity": "ERROR", "line": 3}, diags) == [], "an ERROR at the line", failures)
    check(compare.compare_hdl_error({"severity": "ERROR", "line": 2}, diags) != [], "a WARNING is no ERROR", failures)
    check(compare.compare_hdl_error({"severity": "ERROR"}, dict(diags, output=True)) != [], "an ERROR with output", failures)
    want = {"verdict": "nonconformant", "outcomes": {"R1": "Evaluated"},
            "findings": [{"kind": "Violation", "requirements": ["R1"]}]}
    have = {"verdict": "nonconformant", "outcomes": {"R1": "Evaluated", "R2": "NotExercised"},
            "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["R1"], "message": "m"}]}
    check(compare.compare_report_json(want, have) == [], "a report summary matches on the members stated", failures)
    check(compare.compare_report_json(want, dict(have, findings=have["findings"] * 2)) != [],
          "findings match one for one", failures)
    expected = graph('[] a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; '
                     'conf:finding [ conf:findingKind conf:Parse ; conf:errorCategory conf:BoundsError ; '
                     'conf:findingRequirement ex:R3 ] .')
    actual = graph('<urn:run> a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:failOn sh:Violation ; '
                   'conf:finding <urn:f1> . <urn:f1> a conf:Finding ; conf:findingKind conf:Parse ; conf:errorCategory "Bounds" ; '
                   'conf:findingRequirement ex:R3 ; conf:findingMessage "cut short" .')
    check(compare.compare_report_ttl(expected, actual) == [], "the expected report maps into the actual one", failures)
    two = graph('<urn:run> a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:finding <urn:f1> , <urn:f2> . '
                '<urn:f1> conf:findingKind conf:Parse ; conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:R3 . '
                '<urn:f2> conf:findingKind conf:Violation .')
    check(compare.compare_report_ttl(expected, two) != [], "an extra finding fails the report", failures)
    bad = graph('<urn:run> a conf:Run ; conf:finding <urn:f1> . <urn:f1> a conf:Finding .')
    check(compare.report_shape_violations(bad) != [], "a finding with no kind and no message fails the shapes", failures)
    claims = {"required": ["classes"], "classes": ["Physical Parser"], "optionalFeatures": ["tree-documents"],
              "mustInclude": {"classes": ["Physical Parser"]}}
    check(compare.compare_claims(claims, {"classes": ["Physical Parser"], "optionalFeatures": ["tree-documents"]}) == [],
          "a claims statement within the closed lists", failures)
    check(compare.compare_claims(claims, {"classes": ["Physical Parser"], "optionalFeatures": ["tree documents"]}) != [],
          "a feature is named by its token", failures)


def self_check(failures):
    """Every expected artifact, offered as the output, passes its own case."""
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for manifest in sorted(SUITE.glob("*/*/manifest.json")):
            case = manifest.parent
            name = compare.expected_artifact(case)
            actual = Path(tmp) / ("actual" + Path(name).suffix)
            content = (case / name).read_bytes()
            if name == "expected-error.json" and json.loads(content).get("severity"):
                expected = json.loads(content)
                content = json.dumps({"diagnostics": [expected], "output": False}).encode()
            if name == "expected-claims.json":
                expected = json.loads(content)
                content = json.dumps({"classes": expected["mustInclude"]["classes"], "optionalFeatures": []}).encode()
            actual.write_bytes(content)
            if name == "expected-report.ttl":
                # An expected run report is a pattern (blank nodes are variables, and the copies of the requirements
                # and constraints a report must carry are left out), so offered as the output it is compared as a
                # pattern only; the shape conformance of reportConformsToShapes applies to an implementation's report.
                graph = compare.load_graph(case / name)
                problems = compare.compare_report_ttl(graph, compare.load_graph(actual))
            else:
                problems = compare.compare_case(case, actual, reported_base=compare.REPORTED_BASE)
            if problems:
                failures.append(f"{case.name}: its own expected artifact does not pass: {problems[:2]}")
            n += 1
    return n


def main():
    failures = []
    hel_checks(failures)
    tree_checks(failures)
    graph_checks(failures)
    other_checks(failures)
    n = self_check(failures)
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures[:40]))
        return 1
    print(f"PASS: the comparator applies every comparison rule, and all {n} expected artifacts pass their own cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
