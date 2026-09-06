"""Shared emitted-instance competency corpus, also executed by Apache Jena in the engine."""
from pathlib import Path
import base64
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
import specgraph

SH = Namespace('http://www.w3.org/ns/shacl#')
TARGETS = [SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf]

def check_corpus(family, files, corpus):
    count = 0
    for line in corpus.splitlines():
        if not line or line.startswith('#'):
            continue
        name, module, expected, path, encoded = line.split('\t')
        stem = Path(module).stem
        selected = files[f'specification/aspect/{stem}/{stem}.ttl']
        selected_graph = Graph().parse(data=selected, format='turtle')
        shapes = Graph() + family
        for pred in TARGETS:
            for s, o in list(shapes.subject_objects(pred)):
                if (s, pred, o) not in selected_graph:
                    shapes.remove((s, pred, o))
        data = Graph().parse(data=base64.b64decode(encoded).decode(), format='turtle')
        actual, report, detail = validate(family + data, shacl_graph=shapes, inference='none', advanced=True)
        assert bool(actual) == (expected == 'true'), (name, detail)
        if path:
            assert URIRef(path) in set(report.objects(None, SH.resultPath)), (name, detail)
        count += 1
    return count

if __name__ == '__main__':
    files = {p: Path(p).read_text(encoding='utf-8') for p in specgraph.ontology_paths()}
    count = check_corpus(specgraph.ontologies(), files, Path('specification/validation/test/competency.tsv').read_text(encoding='utf-8'))
    print(f'PASS: {count} cross-engine instance contracts, including selected targets and result paths')
