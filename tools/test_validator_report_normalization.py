"""Negative controls ensure diagnostic mismatches are not collapsed."""
from rdflib import Graph, Namespace, RDF, BNode, URIRef
from _compare_validator_reports import normalize
SH = Namespace("http://www.w3.org/ns/shacl#")
def report(focus="urn:f", path="urn:p", component="MinCountConstraintComponent", severity="Violation",
           count=1, value="urn:v", shape="urn:s"):
    graph = Graph()
    for _ in range(count):
        node = BNode()
        graph.add((URIRef("urn:report"),SH.result,node))
        for predicate,term in [(RDF.type,SH.ValidationResult),(SH.focusNode,URIRef(focus)),(SH.resultPath,URIRef(path)),(SH.sourceConstraintComponent,SH[component]),(SH.resultSeverity,SH[severity])]:
            graph.add((node,predicate,term))
        # rdflib terms subclass str, so only a plain str is an IRI to construct.
        if value is not None:
            graph.add((node,SH.value,URIRef(value) if type(value) is str else value))
        if shape is not None:
            graph.add((node,SH.sourceShape,URIRef(shape) if type(shape) is str else shape))
    return graph
baseline = normalize(report())
variants = [report(focus="urn:other"),report(path="urn:p-extra"),report(component="MaxCountConstraintComponent"),
            report(severity="Warning"),report(count=2),
            # Added fields: a different reported value, a different named shape, an absent
            # value, and a shape whose identity is anonymous rather than named.
            report(value="urn:other-value"),report(value=None),
            report(shape="urn:other-shape"),report(shape=BNode())]
for variant in variants:
    assert baseline != normalize(variant), variant.serialize(format="nt")
assert baseline == normalize(report())
assert normalize(Graph()) != baseline

# A blank-node source shape has no cross-engine identity, so it must be counted rather than
# compared, and the count itself must be observable.
counted, anonymous = normalize(report(shape=BNode()))
assert anonymous == 1, anonymous
assert normalize(report())[1] == 0
assert normalize(report(shape=BNode(), count=3))[1] == 3

# A blank node in a compared field stays a hard failure rather than being normalized away.
for field in (SH.focusNode, SH.value):
    hidden = report()
    result = next(hidden.objects(URIRef("urn:report"), SH.result))
    hidden.remove((result, field, None))
    hidden.add((result, field, BNode()))
    try:
        normalize(hidden)
        raise AssertionError(f"blank node accepted in {field}")
    except AssertionError as error:
        assert "structural normalization" in str(error), error

print("PASS: focus/path/component/severity/value/named-shape, duplicate-count, "
      "anonymous-shape counting and blank-node rejection controls")

# A failed attempt must overwrite prior success even before the first corpus is read.
import subprocess
import sys
import tempfile
import json
from pathlib import Path
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory)/"result.json"
    output.write_text('{"status":"complete","cases":["stale"]}', encoding="utf-8")
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("_compare_validator_reports.py")),
                             str(Path(directory)/"missing"), "--output", str(output)],
                            capture_output=True, timeout=30)
    assert result.returncode != 0
    evidence = json.loads(output.read_text())
    assert evidence["status"] == "failed" and evidence["cases"] == []
    assert evidence["versions"]["pyshacl"]
print("PASS: failed comparison replaces stale successful evidence")
