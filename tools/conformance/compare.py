"""Compare an implementation's output for a conformance case with the case's expected artifact.

    python tools/conformance/compare.py <case-dir> <actual> [--reported-base IRI] [--category-map FILE]

<actual> is what the implementation produced for the case:

  * physical-parser, success   the parsed tree in canonical JSON                                  (expected.json)
  * semantic-emitter/bundle    the instance or asset graph, Turtle or N-Triples                   (expected.ttl)
  * hdl-compiler, success      the compiled description, Turtle                                   (expected.ttl)
  * any class, error           {"category": "<Processing Model category>"}                         (expected-error.json)
  * hdl-compiler, error        {"diagnostics": [{"severity": "ERROR", "line": 3, ...}], "output": false}
  * conformance-evaluator      the run summarised as JSON (expected-report.json), or the run report as RDF
                               (expected-report.ttl)
  * pp-claims-statement        the processor's claims statement, JSON                              (expected-claims.json)

The comparison follows specification/conformance/index.html#canonicalisation; this module is the reference
reading of that section, and the gate tools/test_conformance_comparator.py tests it. It uses only the standard
library and rdflib. The exit status is 0 when the output matches and 1 otherwise, with the first differences
printed.
"""
import argparse
import json
import sys
from pathlib import Path

import rdflib
from rdflib import BNode, Literal, URIRef
from rdflib.compare import graph_diff, to_isomorphic
from rdflib.namespace import RDF, XSD

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import hel  # noqa: E402
from suite import CATEGORIES, REPORTED_BASE  # noqa: E402

BDDO = "https://hexplain.io/ns/bddo#"
CORE = "https://hexplain.io/ns/core#"
DLV = "https://hexplain.io/ns/dlv#"
CONF = "https://hexplain.io/ns/conf#"
OWL = "http://www.w3.org/2002/07/owl#"
SH = "http://www.w3.org/ns/shacl#"

#: The HEL-bearing properties of the HEL name-binding table: their literals compare by expression equivalence.
HEL_PROPERTIES = {URIRef(BDDO + p) for p in ("isPresentIf", "sizeFromExpression", "repeatCountFromExpression",
                                             "atOffsetFromExpression", "repeatUntil", "validIf", "valueFromExpression",
                                             "dispatchOnExpression", "condition", "coversFromExpression",
                                             "coversToExpression", "coversExpression")} | {
    URIRef(DLV + "dimensionStrideFromExpression"), URIRef(CORE + "condition"), URIRef(CORE + "valueExpression"),
    URIRef(CONF + "assertion")}
#: The optional physical-extent annotations a processor MAY add to a minted resource.
EXTENTS = {URIRef(CORE + "byteOffset"), URIRef(CORE + "byteLength")}
#: Predicates of an owl:Ontology header, ignored in an HDL Compiler graph unless the case compares the header.
HEADER_PREDICATES = {RDF.type, URIRef(OWL + "imports"), URIRef(OWL + "versionIRI"), URIRef(OWL + "versionInfo"),
                     URIRef(OWL + "priorVersion"), URIRef(OWL + "backwardCompatibleWith"),
                     URIRef(OWL + "incompatibleWith")}
HEADER_NAMESPACES = ("http://www.w3.org/2000/01/rdf-schema#", "http://purl.org/dc/terms/", "http://purl.org/vocab/vann/",
                     "http://purl.org/dc/elements/1.1/")
#: conf:errorCategory's deprecated string form, and the individual each string names.
CATEGORY_IRIS = {"Sync": "SyncError", "Bounds": "BoundsError", "Validation": "ValidationError",
                 "Checksum": "ChecksumError", "Expression": "ExpressionError", "Dispatch": "DispatchError",
                 "Description": "DescriptionError", "Unsupported": "UnsupportedFeature"}


class Mismatch(Exception):
    pass


# ----------------------------------------------------------------------------------------------- parsed trees

def compare_tree(expected, actual, path="$"):
    """Differences between an expected canonical tree and an actual one, both as parsed JSON (int and float kept apart:
    json.loads reads 1 as int and 1.0 as float, which is the canonical form's distinction). [] when they match."""
    if expected is None:
        return [] if actual is None else [f"{path}: expected null, got {actual!r}"]
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected a struct, got {actual!r}"]
        if set(expected) != set(actual):
            return [f"{path}: expected members {sorted(expected)}, got {sorted(actual)}"]
        out = []
        for k in expected:
            out += compare_tree(expected[k], actual[k], f"{path}.{k}")
        return out
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected an array, got {actual!r}"]
        if len(expected) != len(actual):
            return [f"{path}: expected {len(expected)} elements, got {len(actual)}"]
        out = []
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            out += compare_tree(e, a, f"{path}[{i}]")
        return out
    if isinstance(expected, bool):
        return [] if actual is expected else [f"{path}: expected {expected}, got {actual!r}"]
    if isinstance(expected, int):
        ok = isinstance(actual, int) and not isinstance(actual, bool) and actual == expected
        return [] if ok else [f"{path}: expected the integer {expected}, got {actual!r}"]
    if isinstance(expected, float):
        ok = isinstance(actual, float) and actual == expected
        return [] if ok else [f"{path}: expected the float {expected!r}, got {actual!r}"]
    return [] if actual == expected and type(actual) is type(expected) else [f"{path}: expected {expected!r}, got {actual!r}"]


# ----------------------------------------------------------------------------------------------- graphs

def load_graph(path_or_text, base="urn:example:base"):
    g = rdflib.Graph()
    text = Path(path_or_text).read_text(encoding="utf-8") if isinstance(path_or_text, Path) else path_or_text
    fmt = "nt" if isinstance(path_or_text, Path) and path_or_text.suffix == ".nt" else "turtle"
    g.parse(data=text, format=fmt, publicID=base)
    return g


def _canonical_literal(p, o):
    if not isinstance(o, Literal):
        return o
    if p in HEL_PROPERTIES and (o.datatype in (None, XSD.string)) and not o.language:
        c = hel.canonical(str(o))
        return Literal(c if c is not None else str(o))
    if o.datatype is None or o.language:
        return o
    try:
        return Literal(str(o), datatype=o.datatype, normalize=True) if o.ill_typed is False else o
    except Exception:  # noqa: BLE001 -- an ill-formed literal keeps its lexical form
        return o


def normalise_graph(g, *, cls=None, manifest=None, reported_base=None, header=None):
    """The graph a case compares: extents removed, the bundle profile's closure removed (Bundle Processor), the
    ontology header removed (HDL Compiler, unless the case compares it), the reported base rewritten to the
    placeholder, typed literals in canonical lexical form with their datatype unchanged, HEL literals canonical."""
    manifest = manifest or {}
    drop = set()
    if cls == "bundle-processor" and manifest.get("bundleProfile"):
        pending, closure = [URIRef(manifest["bundleProfile"])], set()
        while pending:
            node = pending.pop()
            if node in closure:
                continue
            closure.add(node)
            pending += [o for o in g.objects(node, None) if isinstance(o, BNode)]
        drop |= {t for t in g if t[0] in closure}
    compare_header = manifest.get("compareOntologyHeader", False) if header is None else header
    if cls == "hdl-compiler" and not compare_header:
        for s in set(g.subjects(RDF.type, URIRef(OWL + "Ontology"))):
            for p, o in g.predicate_objects(s):
                if p in HEADER_PREDICATES or str(p).startswith(HEADER_NAMESPACES):
                    drop.add((s, p, o))
    out = rdflib.Graph()
    for s, p, o in g:
        if p in EXTENTS or (s, p, o) in drop:
            continue
        if reported_base:
            s, o = (_rebase(t, reported_base) for t in (s, o))
        out.add((s, p, _canonical_literal(p, o)))
    return out


def _rebase(term, base):
    if isinstance(term, URIRef):
        text = str(term)
        stem = base.split("#")[0]
        if text == stem or text.startswith(stem + "#"):
            return URIRef(REPORTED_BASE + text[len(stem):])
    return term


def compare_graph(expected, actual, **kw):
    """Differences between two graphs (rdflib Graphs) after normalise_graph; [] when isomorphic."""
    base = kw.pop("reported_base", None)
    e = normalise_graph(expected, **kw)
    a = normalise_graph(actual, reported_base=base, **kw)
    ie, ia = to_isomorphic(e), to_isomorphic(a)
    if ie == ia:
        return []
    _, missing, extra = graph_diff(ie, ia)
    lines = ["graphs are not isomorphic"]
    lines += ["  missing: " + t for t in sorted(_nt(missing))[:20]]
    lines += ["  unexpected: " + t for t in sorted(_nt(extra))[:20]]
    return lines


def _nt(g):
    return [f"{s.n3()} {p.n3()} {o.n3()}" for s, p, o in g]


# ----------------------------------------------------------------------------------------------- errors

def compare_error(expected, actual, category_map=None):
    got = (actual or {}).get("category")
    got = (category_map or {}).get(got, got)
    if got not in CATEGORIES:
        return [f"expected a {expected['category']} error, got {actual!r}"]
    return [] if got == expected["category"] else [f"expected a {expected['category']} error, got {got}"]


def compare_hdl_error(expected, actual):
    """An HDL Compiler error case: at least one ERROR diagnostic (at the stated line, when the case states one) and no
    compiled output."""
    diags = [d for d in (actual or {}).get("diagnostics", []) if str(d.get("severity", "")).upper() == "ERROR"]
    out = []
    if not diags:
        out.append(f"expected an ERROR diagnostic, got {actual!r}")
    elif "line" in expected and not any(d.get("line") == expected["line"] for d in diags):
        out.append(f"expected an ERROR at line {expected['line']}, got lines {[d.get('line') for d in diags]}")
    if (actual or {}).get("output"):
        out.append("the compiler produced output for input it reported an ERROR for")
    return out


# ----------------------------------------------------------------------------------------------- run reports

def compare_report_json(expected, actual):
    """The summary comparison: verdict, truncation, scoping and every listed outcome equal; findings one for one, each
    on the members the expected finding states."""
    out = []
    for key in ("verdict", "truncated", "versionScopingApplied"):
        if key in expected and expected[key] != actual.get(key):
            out.append(f"{key}: expected {expected[key]!r}, got {actual.get(key)!r}")
    for req, value in expected.get("outcomes", {}).items():
        got = actual.get("outcomes", {}).get(req)
        if got != value:
            out.append(f"outcome of {req}: expected {value}, got {got}")
    if "findings" in expected:
        have = list(actual.get("findings", []))
        if len(expected["findings"]) != len(have):
            out.append(f"expected {len(expected['findings'])} finding(s), got {len(have)}")
        for want in expected["findings"]:
            match = next((h for h in have if all(_finding_member(k, v, h.get(k)) for k, v in want.items())), None)
            if match is None:
                out.append(f"no finding matches {want}")
            else:
                have.remove(match)
    return out


def _finding_member(key, want, got):
    if key == "requirements":
        return sorted(want) == sorted(got or [])
    return want == got


def _report_graph(g):
    """A report graph with conf:errorCategory strings read as the category individuals they name."""
    out = rdflib.Graph()
    for s, p, o in g:
        if p == URIRef(CONF + "errorCategory") and isinstance(o, Literal) and str(o) in CATEGORY_IRIS:
            o = URIRef(CONF + CATEGORY_IRIS[str(o)])
        out.add((s, p, _canonical_literal(p, o)))
    return out


def compare_report_ttl(expected, actual):
    """The expected run report maps into the actual one: each blank node of the expected graph is a variable, bound
    injectively to a node of the actual graph so that every expected triple is an actual triple. The actual run must
    have exactly as many conf:finding values as the expected run, unless the expected run is truncated."""
    e, a = _report_graph(expected), _report_graph(actual)
    run_type = URIRef(CONF + "Run")
    runs_e, runs_a = list(e.subjects(RDF.type, run_type)), list(a.subjects(RDF.type, run_type))
    if len(runs_e) != 1:
        raise Mismatch("the expected report states exactly one conf:Run")
    if len(runs_a) != 1:
        return [f"expected one conf:Run in the report, found {len(runs_a)}"]
    out = []
    finding = URIRef(CONF + "finding")
    truncated = e.value(runs_e[0], URIRef(CONF + "truncated"))
    n_e, n_a = len(list(e.objects(runs_e[0], finding))), len(list(a.objects(runs_a[0], finding)))
    if not (isinstance(truncated, Literal) and truncated.toPython() is True) and n_e != n_a:
        out.append(f"expected {n_e} conf:finding value(s), got {n_a}")
    binding = _embed(list(e), a, {runs_e[0]: runs_a[0]} if isinstance(runs_e[0], BNode) else {})
    if binding is None:
        unmatched = [t for t in e if not _triple_in(t, a)]
        out.append("the expected report does not map into the actual one; expected triples with no counterpart: "
                   + "; ".join(f"{s.n3()} {p.n3()} {o.n3()}" for s, p, o in unmatched[:10]))
    return out


def _triple_in(t, g):
    s, p, o = (None if isinstance(x, BNode) else x for x in t)
    return any(True for _ in g.triples((s, p, o)))


def _embed(triples, g, binding):
    """A mapping of the blank nodes of [triples] into g's nodes, extending [binding], under which every triple is in g;
    None when there is none. Backtracking, most-constrained triple first."""
    if not triples:
        return binding

    def unbound(t):
        return sum(1 for x in (t[0], t[2]) if isinstance(x, BNode) and x not in binding)

    triples = sorted(triples, key=unbound)
    s, p, o = triples[0]
    rest = triples[1:]

    def resolve(x):
        return binding.get(x) if isinstance(x, BNode) else x

    for cs, _, co in g.triples((resolve(s), p, resolve(o))):
        trial = dict(binding)
        ok = True
        for var, val in ((s, cs), (o, co)):
            if isinstance(var, BNode):
                if var in trial and trial[var] != val:
                    ok = False
                elif var not in trial:
                    if val in trial.values():
                        ok = False
                    trial[var] = val
        if ok:
            result = _embed(rest, g, trial)
            if result is not None:
                return result
    return None


def report_shape_violations(report):
    """The SHACL results of a run report validated on its own against the conf and req shapes (the report carries the
    requirement and constraint descriptions it cites). Uses pyshacl, a dependency of the specification tooling."""
    from pyshacl import validate  # imported here: only the RDF report cases need it
    root = HERE.parents[1] / "specification"
    shapes = rdflib.Graph()
    for part in ("conf/shapes.ttl", "req/shapes.ttl"):
        shapes.parse(root / part, format="turtle")
    ontology = rdflib.Graph()
    for part in ("conf/conf.ttl", "req/req.ttl"):
        ontology.parse(root / part, format="turtle")
    conforms, results, _ = validate(report, shacl_graph=shapes, ont_graph=ontology, inference="none",
                                    advanced=True, allow_warnings=True)
    if conforms:
        return []
    messages = sorted({str(m) for m in results.objects(None, URIRef(SH + "resultMessage"))})
    return ["the report does not conform to the conf and req shapes: " + "; ".join(messages[:5])]


# ----------------------------------------------------------------------------------------------- claims

def compare_claims(expected, actual):
    out = []
    for key in expected.get("required", []):
        if key not in actual:
            out.append(f"the claims statement lacks {key}")
    for key in ("classes", "optionalFeatures"):
        allowed = set(expected.get(key, []))
        value = actual.get(key, [])
        stated = {k for k, v in value.items() if (v.get("claimed") if isinstance(v, dict) else v)} if isinstance(value, dict) else set(value)
        for item in sorted(stated - allowed):
            out.append(f"{key}: {item!r} is not in the Processing Model's closed list")
        for item in expected.get("mustInclude", {}).get(key, []):
            if item not in stated:
                out.append(f"{key}: a processor running this case claims {item!r}")
    return out


# ----------------------------------------------------------------------------------------------- one case

def expected_artifact(case_dir):
    for name in ("expected.json", "expected.ttl", "expected-error.json", "expected-report.json", "expected-report.ttl",
                 "expected-claims.json"):
        if (case_dir / name).is_file():
            return name
    raise Mismatch(f"{case_dir}: no expected artifact")


def compare_case(case_dir, actual_path, reported_base=None, category_map=None):
    """Differences between the output at [actual_path] and the expectation of the case at [case_dir]."""
    case_dir, actual_path = Path(case_dir), Path(actual_path)
    manifest = json.loads((case_dir / "manifest.json").read_text(encoding="utf-8"))
    cls = manifest["class"]
    name = expected_artifact(case_dir)
    if name.endswith(".json"):
        expected = json.loads((case_dir / name).read_text(encoding="utf-8"))
        actual = json.loads(actual_path.read_text(encoding="utf-8")) if actual_path.is_file() else None
        if name == "expected.json":
            return compare_tree(expected, actual)
        if name == "expected-error.json":
            if cls == "hdl-compiler":
                return compare_hdl_error(expected, actual)
            if isinstance(actual, dict) and "category" not in actual and cls == "conformance-evaluator" and manifest.get("orError"):
                return [f"expected a {expected['category']} error, got a report"]
            return compare_error(expected, actual, category_map)
        if name == "expected-report.json":
            if isinstance(actual, dict) and "category" in actual:
                return [] if actual["category"] == manifest.get("orError") else [f"expected a report, got {actual}"]
            return compare_report_json(expected, actual or {})
        return compare_claims(expected, actual or {})
    expected_graph = load_graph(case_dir / name)
    if not actual_path.is_file():
        return [f"no output at {actual_path}"]
    if actual_path.suffix == ".json":
        actual = json.loads(actual_path.read_text(encoding="utf-8"))
        if name == "expected-report.ttl" and actual.get("category") == manifest.get("orError"):
            return []
        return [f"expected a graph, got {actual!r}"]
    actual_graph = load_graph(actual_path)
    if name == "expected-report.ttl":
        problems = compare_report_ttl(expected_graph, actual_graph)
        if manifest.get("reportConformsToShapes"):
            problems += report_shape_violations(actual_graph)
        return problems
    return compare_graph(expected_graph, actual_graph, cls=cls, manifest=manifest, reported_base=reported_base)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("case", help="the case directory")
    ap.add_argument("actual", help="the implementation's output for the case")
    ap.add_argument("--reported-base", help="the base IRI the processor reported (a case whose manifest gives no base)")
    ap.add_argument("--category-map", help="JSON file mapping the implementation's error names to the categories")
    args = ap.parse_args(argv)
    cmap = json.loads(Path(args.category_map).read_text(encoding="utf-8")) if args.category_map else None
    problems = compare_case(args.case, args.actual, args.reported_base, cmap)
    if problems:
        print("FAIL: " + Path(args.case).name + "\n  " + "\n  ".join(problems))
        return 1
    print("PASS: " + Path(args.case).name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
