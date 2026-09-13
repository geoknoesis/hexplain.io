"""Compare normalized Jena/pySHACL diagnostics for the frozen layout/security corpus."""
import argparse
import base64
from collections import Counter
import hashlib
import json
from importlib.metadata import version
from datetime import datetime, timezone
from pathlib import Path
from rdflib import Graph, Namespace, BNode
from pyshacl import validate
SH = Namespace("http://www.w3.org/ns/shacl#")
ROOT = Path(__file__).resolve().parents[1]

# Compared for every result. A blank node in any of these is a diagnostic whose identity
# cannot be matched across engines, so it is rejected rather than silently normalized away.
COMPARED = (SH.focusNode, SH.resultPath, SH.sourceConstraintComponent, SH.resultSeverity, SH.value)


def normalize(graph):
    """Multiset of comparable diagnostic fields, plus the unresolvable source-shape count.

    sh:sourceShape is usually a blank node in the shapes graph, and the exported Jena
    reports carry no shape definitions, so a blank-node shape has no cross-engine identity.
    Named shapes are compared; blank-node shapes are counted so that the unverified
    remainder stays visible and a change in that remainder is detectable.
    """
    rows = []
    anonymous_shapes = 0
    for result in graph.objects(None, SH.result):
        row = []
        for predicate in COMPARED:
            values = list(graph.objects(result, predicate))
            assert len(values) <= 1, (predicate, values)
            assert not any(isinstance(v, BNode) for v in values), "Blank-node diagnostic requires structural normalization"
            row.append(values[0].n3() if values else "")
        shapes = list(graph.objects(result, SH.sourceShape))
        assert len(shapes) <= 1, (SH.sourceShape, shapes)
        if shapes and isinstance(shapes[0], BNode):
            anonymous_shapes += 1
            row.append("")
        else:
            row.append(shapes[0].n3() if shapes else "")
        rows.append(tuple(row))
    return Counter(rows), anonymous_shapes

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = dict(schema_version=2, status="running", started_utc=datetime.now(timezone.utc).isoformat(),
                    versions={name: version(name) for name in ("rdflib", "pyshacl")},
                    inputs={}, cases=[], scope="Top-level diagnostic multiset over focus node, result path, constraint component, severity, value term and named source shape; counts blank-node source shapes and nested detail asymmetry without comparing nested structure or engine-authored messages")
    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
        temporary.replace(args.output)
    save()
    try:
        compare(args, evidence)
        evidence["status"] = "complete"
    except BaseException as error:
        evidence.update(status="failed", error=str(error))
        raise
    finally:
        evidence["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    print(f"PASS: {len(evidence['cases'])} cross-validator diagnostic comparisons")

def compare(args, evidence):
    cases = evidence["cases"]
    for suite, shapes in {
        "layout": [("layout-competency-shapes.ttl", "specification/dlv/dlv.ttl"), ("compound-competency-shapes.ttl", "specification/aspect/bundle/bundle.ttl")],
        "security": [("security-profile.ttl", "specification/validation/test/security-profile.ttl")]
    }.items():
        shape_graph = Graph()
        for copied, source in shapes:
            assert (args.reports/copied).read_text(encoding="utf-8") == (ROOT/source).read_text(encoding="utf-8"), source
            source_text = (ROOT/source).read_text(encoding="utf-8")
            evidence["inputs"][source] = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
            shape_graph.parse(data=source_text, format="turtle")
        corpus = ROOT/f"specification/validation/test/{suite}-competency.tsv"
        text = corpus.read_text(encoding="utf-8")
        assert text == (args.reports/corpus.name).read_text(encoding="utf-8")
        evidence["inputs"][corpus.relative_to(ROOT).as_posix()] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        lines = [line for line in text.splitlines() if line and not line.startswith("#")]
        for index,line in enumerate(lines):
            name, expected, path, encoded = line.split("\t")
            data = Graph().parse(data=base64.b64decode(encoded), format="turtle")
            conforms, report, _ = validate(data, shacl_graph=shape_graph, inference="none", advanced=False)
            jena_file = args.reports/f"{suite}-{index}.ttl"
            jena = Graph().parse(jena_file)
            assert bool(conforms) == (expected == "true"), name
            assert bool(next(jena.objects(None, SH.conforms)).toPython()) == bool(conforms), name
            (a, a_anonymous), (b, b_anonymous) = normalize(report), normalize(jena)
            assert a == b, (suite,name,"pySHACL",a,"Jena",b)
            assert a_anonymous == b_anonymous, (suite,name,"anonymous source shapes",a_anonymous,b_anonymous)
            pyshacl_details = len(list(report.triples((None,SH.detail,None))))
            jena_details = len(list(jena.triples((None,SH.detail,None))))
            cases.append(dict(suite=suite,name=name,conforms=bool(conforms),diagnostics=sum(a.values()),
                              compared_fields=len(COMPARED)+1,anonymous_source_shapes=a_anonymous,
                              pyshacl_detail_links=pyshacl_details,jena_detail_links=jena_details,
                              detail_asymmetry=pyshacl_details != jena_details,
                              jena_report_sha256=hashlib.sha256(jena_file.read_bytes()).hexdigest()))
if __name__ == "__main__": main()

