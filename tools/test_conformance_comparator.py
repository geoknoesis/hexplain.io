"""The conformance suite's standalone comparator (tools/conformance/compare.py) compares as the suite page says.

Unit checks of each comparison rule of specification/conformance/index.html#canonicalisation -- the HEL parser and
canonical form, tree comparison (Integer and Float kept apart), graph comparison (literals by value but datatypes
exactly, HEL literals by equivalence, the ontology header, extents, the bundle profile, the reported base), error
and diagnostic comparison, the report summary, the RDF report embedding, and the claims statement -- and then a
self-check: every expected artifact of the suite, offered as the actual output, passes its own case.
"""

from __future__ import annotations

import itertools
import json
import logging
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

from rdflib import Graph

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "conformance"))

import compare  # noqa: E402
import hel  # noqa: E402
from suite import SUITE  # noqa: E402

PREFIXES = """@prefix bddo: <https://hexplain.io/ns/bddo#> . @prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix conf: <https://hexplain.io/ns/conf#> . @prefix sh: <http://www.w3.org/ns/shacl#> . @prefix ex: <urn:ex#> .
"""


def graph(body: str) -> Graph:
    return compare.load_graph(PREFIXES + body)


def check(condition: object, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def hel_checks(failures: list[str]) -> None:
    check(
        hel.canonical("Flags&0x01==1 and not(done)") == "((instance.Flags & 1) == 1) and not instance.done",
        "the HEL page's canonical-form example",
        failures,
    )
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
    check(hel.canonical("a.param") is None, "param is a reserved root, not a key", failures)
    check(hel.canonical("param.w + 1") == "param.w + 1", "param is a root, not a field of instance", failures)
    check(hel.canonical("asset(1)") is None and hel.canonical("param()") is None, "a root is not a function", failures)
    check(hel.canonical("5e-324") == "4.9E-324", "one digit that round-trips is written as the nearest two", failures)
    check(hel.canonical("1e23") == "1.0E23" and hel.canonical("0.5") == "0.5", "shortest digits elsewhere", failures)
    check(hel.canonical("'\\q'") is None, "an unknown escape is a syntax error", failures)
    deep = hel.canonical("- " * 511 + "1")
    check(
        deep == "-" * 511 + "1", "an expression 512 deep (HEL's default depth limit) has its canonical form", failures
    )
    check(
        hel.canonical("not " * 600 + "a") == "not " * 600 + "instance.a", "a long chain of not is canonical", failures
    )
    check(hel.canonical("(" * 5000 + "1" + ")" * 5000) is None, "nesting beyond the parser is no crash", failures)
    from comparison_worker import comparison

    depth = SUITE / "physical-parser/pp-limit-hel-default-depth"
    check(
        comparison("round-trip", depth, depth / "expected.json", "") == [],
        "the round-trip comparison of a 512-deep expression's case does not overflow the stack",
        failures,
    )
    check(
        hel.canonical("'a\x01b'") == "'a\\x01b'", "a control character is written \\xHH in the canonical form", failures
    )
    check(hel.canonical("'a\tb'") == "'a\tb'", "a tab stays itself in the canonical form", failures)
    check(hel.canonical("'\\uD83D\\uDE00'") == "'\U0001f600'", "a surrogate pair denotes one code point", failures)
    check(hel.canonical("'\\uD800'") is None, "a lone surrogate is an error", failures)
    check(
        hel._float(1e7) == "1.0E7" and hel._float(0.05) == "0.05" and hel._float(1e-4) == "1.0E-4",
        "floats are spelt as Java's Double.toString spells them",
        failures,
    )
    check(
        hel.canonical("root.Directory[i].Entries[0].Tag") == "root.Directory[instance.i].Entries[0].Tag",
        "subscripts and key steps",
        failures,
    )


def tree_checks(failures: list[str]) -> None:
    check(
        compare.compare_tree({"a": 1, "b": [2.5]}, {"b": [2.5], "a": 1}) == [], "member order does not matter", failures
    )
    check(compare.compare_tree({"a": 1}, {"a": 1.0}) != [], "an expected Integer is not matched by a Float", failures)
    check(compare.compare_tree({"a": 1.0}, {"a": 1}) != [], "an expected Float is not matched by an Integer", failures)
    check(compare.compare_tree({"a": None}, {}) != [], "an unbound field is null, not missing", failures)
    check(compare.compare_tree({"x": "NaN"}, {"x": "NaN"}) == [], "NaN is the string NaN", failures)
    check(
        compare.compare_tree({"x": "18446744073709551615"}, {"x": 18446744073709551615}) != [],
        "an Integer above 2^53 is its decimal string",
        failures,
    )


def graph_checks(failures: list[str]) -> None:
    base = graph(
        'ex:f bddo:size "4"^^xsd:integer ; bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; '
        'bddo:sizeFromExpression "instance.n * 2" .'
    )
    same = graph(
        'ex:f bddo:size "04"^^xsd:integer ; bddo:hasFixedValue "0a0b"^^xsd:hexBinary ; bddo:sizeFromExpression "n*2" .'
    )
    check(
        compare.compare_graph(base, same, cls="hdl-compiler") == [],
        "literals compare by value, and HEL literals by equivalence",
        failures,
    )
    typed = graph(
        'ex:f bddo:size "4"^^xsd:integer ; bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; '
        'bddo:sizeFromExpression "n*2"^^bddo:HelExpression .'
    )
    check(
        compare.compare_graph(base, typed, cls="hdl-compiler") == [],
        "a HEL literal typed bddo:HelExpression is the same expression as the xsd:string one",
        failures,
    )
    local = graph('ex:f bddo:localExpression "n*2" .')
    local_typed = graph('ex:f bddo:localExpression "instance.n * 2"^^bddo:HelExpression .')
    check(
        compare.compare_graph(local, local_typed, cls="hdl-compiler") == [],
        "bddo:localExpression is HEL-bearing, whatever its expression literal is typed",
        failures,
    )
    for prop in ("hexplain:parameterExpression", "hexplain:codecFromExpression"):
        plain = graph(f'ex:s {prop} "n*2" .')
        canonical = graph(f'ex:s {prop} "instance.n * 2"^^bddo:HelExpression .')
        check(
            compare.compare_graph(plain, canonical, cls="hdl-compiler") == [],
            f"{prop} is HEL-bearing: its literal compares by expression equivalence",
            failures,
        )
    args = graph('ex:f bddo:hasArgument ( "n*2" "m" ) .')
    args_typed = graph(
        'ex:f bddo:hasArgument ( "instance.n * 2"^^bddo:HelExpression "instance.m"^^bddo:HelExpression ) .'
    )
    check(
        compare.compare_graph(args, args_typed, cls="hdl-compiler") == [],
        "the members of a bddo:hasArgument list are HEL expressions",
        failures,
    )
    other = graph('ex:f ex:values ( "n*2" ) .')
    other_typed = graph('ex:f ex:values ( "instance.n * 2"^^bddo:HelExpression ) .')
    check(
        compare.compare_graph(other, other_typed, cls="hdl-compiler") != [],
        "an rdf:List that is not an argument list is not read as HEL",
        failures,
    )
    wider = graph(
        'ex:f bddo:size "4"^^xsd:long ; bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; '
        'bddo:sizeFromExpression "instance.n * 2" .'
    )
    check(
        compare.compare_graph(base, wider, cls="hdl-compiler") != [],
        "HDL literal datatypes must match exactly",
        failures,
    )
    header = graph(
        '<urn:ex> a owl:Ontology ; owl:imports <urn:other> ; owl:versionInfo "1" . ex:f bddo:size "4"^^xsd:integer ; '
        'bddo:hasFixedValue "0A0B"^^xsd:hexBinary ; bddo:sizeFromExpression "instance.n * 2" .'
    )
    check(
        compare.compare_graph(base, header, cls="hdl-compiler") == [],
        "the ontology header is ignored by default",
        failures,
    )
    check(
        compare.compare_graph(base, header, cls="hdl-compiler", manifest={"compareOntologyHeader": True}) != [],
        "compareOntologyHeader compares the header",
        failures,
    )
    extent = graph(
        'ex:r a ex:C ; hexplain:byteOffset "0"^^xsd:nonNegativeInteger ; '
        'hexplain:byteLength "4"^^xsd:nonNegativeInteger .'
    )
    check(
        compare.compare_graph(graph("ex:r a ex:C ."), extent, cls="semantic-emitter") == [],
        "the optional extent annotations are removed",
        failures,
    )
    for body, what in (
        ('ex:r a ex:C . ex:other hexplain:byteOffset "0"^^xsd:nonNegativeInteger .', "on a resource never minted"),
        ("ex:r a ex:C ; hexplain:byteOffset 0 .", "typed xsd:integer, not xsd:nonNegativeInteger"),
        ('ex:r a ex:C ; hexplain:byteLength "-4"^^xsd:nonNegativeInteger .', "negative"),
        ('ex:r a ex:C ; hexplain:byteLength "four"^^xsd:nonNegativeInteger .', "not a number"),
        ('ex:r a ex:C . ex:C hexplain:byteLength "4"^^xsd:nonNegativeInteger .', "on an object that is no subject"),
    ):
        logging.disable(logging.WARNING)  # rdflib logs the ill-typed literal these probes parse on purpose.
        try:
            actual_graph = graph(body)
        finally:
            logging.disable(logging.NOTSET)
        check(
            compare.compare_graph(graph("ex:r a ex:C ."), actual_graph, cls="semantic-emitter") != [],
            f"an extent {what} is reported, not removed: the instance graph holds nothing else",
            failures,
        )
    minted = compare.load_graph(
        f"<urn:uuid:1#root> a <urn:ex#C> . <urn:uuid:1#root/a> <{compare.CORE}byteOffset> "
        '"3"^^<http://www.w3.org/2001/XMLSchema#nonNegativeInteger> .'
    )
    check(
        compare.compare_graph(
            compare.load_graph(f"<{compare.REPORTED_BASE}#root> a <urn:ex#C> ."),
            minted,
            cls="semantic-emitter",
            reported_base="urn:uuid:1",
        )
        == [],
        "an extent on a resource minted under the reported base is removed",
        failures,
    )
    blank = graph('ex:r ex:p [ a ex:C ; hexplain:byteOffset "1"^^xsd:nonNegativeInteger ] .')
    check(
        compare.compare_graph(graph("ex:r ex:p [ a ex:C ] ."), blank, cls="semantic-emitter") == [],
        "an extent on a blank node the graph describes is removed",
        failures,
    )
    simple, typed_string = graph('ex:r ex:p "x" .'), graph('ex:r ex:p "x"^^xsd:string .')
    for cls in ("semantic-emitter", "hdl-compiler"):
        check(
            compare.compare_graph(simple, typed_string, cls=cls) == []
            and compare.compare_graph(typed_string, simple, cls=cls) == [],
            f"{cls}: a simple literal and its xsd:string twin are one RDF 1.1 term",
            failures,
        )
    check(
        compare.compare_graph(simple, graph('ex:r ex:p "x"@en .'), cls="semantic-emitter") != [],
        "a language-tagged string is not a simple literal",
        failures,
    )
    decimal, padded = graph('ex:r ex:p "1.0"^^xsd:decimal .'), graph('ex:r ex:p "01.00"^^xsd:decimal .')
    check(
        compare.compare_graph(decimal, padded, cls="hdl-compiler") == [],
        "an HDL Compiler decimal compares by value: 1.0 is 01.00",
        failures,
    )
    check(
        compare.compare_graph(decimal, graph('ex:r ex:p "1.5"^^xsd:decimal .'), cls="hdl-compiler") != [],
        "another decimal value fails",
        failures,
    )
    check(
        compare.compare_graph(decimal, padded, cls="semantic-emitter") != [],
        "an emitted decimal still compares as written (its lexical form is fixed)",
        failures,
    )
    reported = compare.load_graph("<urn:uuid:1234#root> a <urn:ex#C> .")
    check(
        compare.compare_graph(
            compare.load_graph(f"<{compare.REPORTED_BASE}#root> a <urn:ex#C> ."),
            reported,
            cls="semantic-emitter",
            reported_base="urn:uuid:1234",
        )
        == [],
        "the reported base is read as the placeholder",
        failures,
    )
    bundle = graph("ex:P a ex:Profile ; ex:spec [ ex:x 1 ] . ex:asset a ex:Asset .")
    check(
        compare.compare_graph(
            graph("ex:asset a ex:Asset ."), bundle, cls="bundle-processor", manifest={"bundleProfile": "urn:ex#P"}
        )
        == [],
        "the bundle profile's closure is removed",
        failures,
    )


def writer_checks(failures: list[str]) -> None:
    """A Writer case compares bytes exactly, and an error only with an error."""
    check(compare.compare_bytes(b"\x01\x02", b"\x01\x02") == [], "equal bytes match", failures)
    check(compare.compare_bytes(b"\x01\x02", b"\x01\x03") != [], "one differing byte fails", failures)
    check(compare.compare_bytes(b"\x01\x02", b"\x01\x02\x00") != [], "a longer output fails", failures)
    check(compare.compare_bytes(b"\x01\x02", b"\x01") != [], "a shorter output fails", failures)
    check(compare.parse_hex("01 0a\nff\n") == b"\x01\x0a\xff", "expected.hex ignores white space", failures)
    for bad in ("0A", "012", "0g"):
        try:
            compare.parse_hex(bad)
            failures.append(f"expected.hex accepted {bad!r}")
        except ValueError:
            pass
    with tempfile.TemporaryDirectory() as tmp:
        bytes_case, error_case = SUITE / "writer/w-field-order", SUITE / "writer/w-tree-undeclared-key"
        written, error = Path(tmp) / "actual.bin", Path(tmp) / "error.json"
        written.write_bytes(bytes.fromhex("01ffd8020003"))
        error.write_text(json.dumps({"category": "Validation"}), encoding="utf-8", newline="\n")
        check(compare.compare_case(bytes_case, written) == [], "the bytes a Writer case expects pass", failures)
        check(compare.compare_case(bytes_case, error) != [], "an error where bytes are expected fails", failures)
        check(compare.compare_case(error_case, error) == [], "the category a Writer case expects passes", failures)
        check(compare.compare_case(error_case, written) != [], "bytes where an error is expected fail", failures)
        written.write_bytes(bytes.fromhex("01ffd8020300"))
        check(compare.compare_case(bytes_case, written) != [], "the other byte order fails", failures)
        error.write_text(json.dumps({"category": "Unsupported"}), encoding="utf-8", newline="\n")
        check(compare.compare_case(error_case, error) != [], "another category fails a Writer case", failures)


def other_checks(failures: list[str]) -> None:
    check(
        compare.compare_error({"category": "Bounds"}, {"category": "Bounds"}) == [],
        "an error category matches",
        failures,
    )
    check(
        compare.compare_error({"category": "Bounds"}, {"category": "Validation"}) != [],
        "another category fails",
        failures,
    )
    check(
        compare.compare_error({"category": "Dispatch"}, {"category": "DISPATCH"}, {"DISPATCH": "Dispatch"}) == [],
        "an implementation's name maps to its category",
        failures,
    )
    diags = {"diagnostics": [{"severity": "WARNING", "line": 2}, {"severity": "ERROR", "line": 3}], "output": False}
    check(compare.compare_hdl_error({"severity": "ERROR", "line": 3}, diags) == [], "an ERROR at the line", failures)
    check(compare.compare_hdl_error({"severity": "ERROR", "line": 2}, diags) != [], "a WARNING is no ERROR", failures)
    for line in (True, 1.0, "1", None):
        check(
            compare.compare_hdl_error({"line": 1}, {"diagnostics": [{"severity": "ERROR", "line": line}]}) != [],
            f"a non-integer diagnostic line {line!r} cannot match line 1",
            failures,
        )
    check(
        compare.compare_hdl_error({"line": 1}, {"diagnostics": [{"severity": "error", "line": 1}]}) == [],
        "an integer diagnostic line still matches with case-insensitive severity",
        failures,
    )
    malformed_diagnostics: tuple[object, ...] = (
        None,
        [],
        "ERROR",
        {"diagnostics": None},
        {"diagnostics": {}},
        {"diagnostics": [1]},
    )
    for malformed in malformed_diagnostics:
        check(
            bool(compare.compare_hdl_error({"severity": "ERROR"}, malformed)),
            f"malformed diagnostics {malformed!r} return a comparison failure",
            failures,
        )
    check(
        compare.compare_hdl_error({"severity": "ERROR"}, dict(diags, output=True)) != [],
        "an ERROR with output",
        failures,
    )
    want = {
        "verdict": "nonconformant",
        "outcomes": {"R1": "Evaluated"},
        "findings": [{"kind": "Violation", "requirements": ["R1"]}],
    }
    have: dict[str, Any] = {
        "verdict": "nonconformant",
        "outcomes": {"R1": "Evaluated", "R2": "NotExercised"},
        "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["R1"], "message": "m"}],
    }
    check(compare.compare_report_json(want, have) == [], "a report summary matches on the members stated", failures)
    check(
        compare.compare_report_json(want, dict(have, findings=have["findings"] * 2)) != [],
        "findings match one for one",
        failures,
    )
    expected = graph(
        "[] a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; "
        "conf:finding [ conf:findingKind conf:Parse ; conf:errorCategory conf:BoundsError ; "
        "conf:findingRequirement ex:R3 ] ."
    )
    actual = graph(
        "<urn:run> a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:failOn sh:Violation ; "
        'conf:finding <urn:f1> . <urn:f1> a conf:Finding ; conf:findingKind conf:Parse ; conf:errorCategory "Bounds" ; '
        'conf:findingRequirement ex:R3 ; conf:findingMessage "cut short" .'
    )
    check(compare.compare_report_ttl(expected, actual) == [], "the expected report maps into the actual one", failures)
    two = graph(
        "<urn:run> a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:finding <urn:f1> , "
        "<urn:f2> . "
        "<urn:f1> conf:findingKind conf:Parse ; conf:errorCategory conf:BoundsError ; conf:findingRequirement ex:R3 . "
        "<urn:f2> conf:findingKind conf:Violation ."
    )
    check(compare.compare_report_ttl(expected, two) != [], "an extra finding fails the report", failures)
    bad = graph("<urn:run> a conf:Run ; conf:finding <urn:f1> . <urn:f1> a conf:Finding .")
    check(
        compare.report_shape_violations(bad) != [], "a finding with no kind and no message fails the shapes", failures
    )
    claims = {
        "required": ["classes"],
        "classes": ["Physical Parser"],
        "optionalFeatures": ["tree-documents"],
        "mustInclude": {"classes": ["Physical Parser"]},
    }
    check(
        compare.compare_claims(claims, {"classes": ["Physical Parser"], "optionalFeatures": ["tree-documents"]}) == [],
        "a claims statement within the closed lists",
        failures,
    )
    check(
        compare.compare_claims(claims, {"classes": ["Physical Parser"], "optionalFeatures": ["tree documents"]}) != [],
        "a feature is named by its token",
        failures,
    )
    menc = "https://hexplain.io/ns/register/media-encoding#"
    with_codecs = {
        "required": ["classes", "codecs"],
        "classes": ["Physical Parser"],
        "optionalFeatures": [],
        "mustInclude": {"classes": ["Physical Parser"], "codecs": [menc + "Store"]},
    }
    check(
        compare.compare_claims(with_codecs, {"classes": ["Physical Parser"], "codecs": [menc + "Store", menc + "Zstd"]})
        == [],
        "a claims statement listing codec IRIs",
        failures,
    )
    check(
        compare.compare_claims(with_codecs, {"classes": ["Physical Parser"], "codecs": [menc + "Zstd"]}) != [],
        "a claims statement must list the minimum codecs",
        failures,
    )
    check(
        compare.compare_claims(with_codecs, {"classes": ["Physical Parser"], "codecs": [menc + "Store", "zstd"]}) != [],
        "a codec is named by its register IRI",
        failures,
    )
    check(
        compare.compare_claims(with_codecs, {"classes": ["Physical Parser"], "codecs": {menc + "Store": True}}) != [],
        "the codecs member is an array, not an object keyed by IRI",
        failures,
    )


def artifact_checks(failures: list[str]) -> None:
    """Errors cannot masquerade as reports or successful trees, including a tree with a category field."""
    values: tuple[dict[str, Any], ...] = ({}, {"category": None}, {"category": []}, {"category": "Invalid"})
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for expected in ("expected-report.json", "expected-report.ttl"):
            for allowed in (False, True):
                cases = [
                    p.parent
                    for p in (SUITE / "conformance-evaluator").glob("*/" + expected)
                    if bool(json.loads((p.parent / "manifest.json").read_text(encoding="utf-8")).get("orError"))
                    == allowed
                ]
                case = sorted(cases)[0]
                for filename in (compare.ERROR_FILE, "actual.json"):
                    actual = root / filename
                    for value in values:
                        actual.write_text(json.dumps(value), encoding="utf-8", newline="\n")
                        check(bool(compare.compare_case(case, actual)), f"{case.name} accepted {value!r}", failures)
                    actual.write_text('{"category":"ResourceLimit"}', encoding="utf-8", newline="\n")
                    check(
                        (compare.compare_case(case, actual) == []) == allowed,
                        f"{case.name}: explicit alternative error was not respected",
                        failures,
                    )
                    actual.write_text('{"category":"limited"}', encoding="utf-8", newline="\n")
                    check(
                        (compare.compare_case(case, actual, category_map={"limited": "ResourceLimit"}) == [])
                        == allowed,
                        f"{case.name}: mapped alternative error was not respected",
                        failures,
                    )
        case = root / "tree"
        case.mkdir()
        (case / "manifest.json").write_text('{"class":"physical-parser"}', encoding="utf-8", newline="\n")
        (case / "expected.json").write_text('{"category":"Bounds"}', encoding="utf-8", newline="\n")
        error = root / compare.ERROR_FILE
        error.write_text('{"category":"Bounds"}', encoding="utf-8", newline="\n")
        check(bool(compare.compare_case(case, error)), "an error passed as a matching tree", failures)
        success = root / "actual.json"
        success.write_bytes(error.read_bytes())
        check(compare.compare_case(case, success) == [], "a legitimate category field was rejected", failures)
        # An error case requires the error artifact: a successful output that holds a category is not an error.
        for cls, error_case in (
            ("physical-parser", SUITE / "physical-parser/pp-align-derived-field"),
            ("writer", SUITE / "writer/w-tree-undeclared-key"),
        ):
            wanted = (error_case / "expected-error.json").read_text(encoding="utf-8")
            success.write_text(wanted, encoding="utf-8", newline="\n")
            error.write_text(wanted, encoding="utf-8", newline="\n")
            check(bool(compare.compare_case(error_case, success)), f"{cls}: actual.json passed as an error", failures)
            check(compare.compare_case(error_case, error) == [], f"{cls}: the error artifact failed", failures)
        # Processor JSON is read strictly: a repeated member or a NaN is not JSON a comparison can trust.
        category = json.loads(wanted)["category"]
        for text in (
            f'{{"category":"Validation","category":"{category}"}}',
            f'{{"category":"{category}","n":NaN}}',
            f'{{"category":"{category}","n":-Infinity}}',
        ):
            error.write_text(text, encoding="utf-8", newline="\n")
            check(bool(compare.compare_case(error_case, error)), f"non-RFC 8259 JSON was accepted: {text}", failures)
        success.write_text('{"a":1,"a":2}', encoding="utf-8", newline="\n")
        (case / "expected.json").write_text('{"a":2}', encoding="utf-8", newline="\n")
        check(bool(compare.compare_case(case, success)), "a tree with a repeated member passed", failures)


def self_check(failures: list[str]) -> int:
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
            elif name == "expected-error.json":
                actual = Path(tmp) / compare.ERROR_FILE  # An error is reported as the error artifact.
            if name == "expected-claims.json":
                expected = json.loads(content)
                content = json.dumps(
                    {
                        "classes": expected["mustInclude"]["classes"],
                        "optionalFeatures": [],
                        "codecs": expected["mustInclude"].get("codecs", []),
                    }
                ).encode()
            if name == "expected.hex":
                actual, content = actual.with_suffix(".bin"), bytes.fromhex(content.decode("ascii"))
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
            if name != "expected-error.json":
                error = Path(tmp) / compare.ERROR_FILE
                for value in ({}, {"category": None}):
                    error.write_text(json.dumps(value), encoding="utf-8", newline="\n")
                    if not compare.compare_case(case, error):
                        failures.append(f"{case.name}: malformed error artifact passed: {value!r}")
            n += 1
    return n


def report_regressions(failures: list[str]) -> None:
    for key in ("truncated", "versionScopingApplied"):
        for value in (False, True):
            check(
                bool(compare.compare_report_json({key: value}, {key: int(value)})),
                f"{key} rejects numeric booleans",
                failures,
            )
    wants = {"findings": [{"severity": "ERROR"}, {"severity": "ERROR", "message": "specific"}]}
    have = [{"severity": "ERROR", "message": "specific"}, {"severity": "ERROR", "message": "other"}]
    for findings in (have, list(reversed(have))):
        check(not compare.compare_report_json(wants, {"findings": findings}), "overlapping finding matching", failures)
    check(
        bool(compare.compare_report_json(wants, {"findings": [have[1], have[1]]})),
        "matching cannot reuse a finding",
        failures,
    )
    malformed_values: tuple[Any, ...] = (None, {}, 0, "invalid")
    for malformed in malformed_values:
        check(
            bool(compare.compare_report_json({"findings": []}, {"findings": malformed})),
            "malformed findings rejected",
            failures,
        )


def matching_oracle(failures: list[str]) -> None:
    """Compare the polynomial matcher to exhaustive assignments on small overlapping patterns."""
    rng = random.Random(5301)
    for _ in range(200):
        n = rng.randrange(1, 6)
        have = [{"severity": rng.choice(["ERROR", "WARNING"]), "message": rng.choice(["a", "b"])} for _ in range(n)]
        wants = [{k: v for k, v in rng.choice(have).items() if rng.choice([False, True])} for _ in range(n)]
        possible = any(
            all(all(h.get(k) == v for k, v in w.items()) for w, h in zip(wants, order, strict=True))
            for order in itertools.permutations(have)
        )
        matched = not compare.compare_report_json({"findings": wants}, {"findings": have})
        check(matched == possible, "finding matcher agrees with exhaustive assignment", failures)


def main() -> int:
    failures: list[str] = []
    matching_oracle(failures)
    report_regressions(failures)
    hel_checks(failures)
    tree_checks(failures)
    graph_checks(failures)
    other_checks(failures)
    writer_checks(failures)
    artifact_checks(failures)
    n = self_check(failures)
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures[:40]))
        return 1
    print(f"PASS: the comparator applies every comparison rule, and all {n} expected artifacts pass their own cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
