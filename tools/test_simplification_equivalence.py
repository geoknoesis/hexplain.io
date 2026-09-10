"""Check the frozen simplification contract without requiring Git or a sibling engine."""
import hashlib
import json
import zipfile
from pathlib import Path
from rdflib import Graph, Namespace, RDF, Literal, URIRef
from rdflib.compare import isomorphic
from _expand_specification_patterns import ROOT
import specgraph

base = ROOT / 'review-2026-09-05/simplification'
manifest = json.loads((base / 'baseline.json').read_text(encoding='utf-8'))
archive = (base / 'baseline.zip').read_bytes()
assert hashlib.sha256(archive).hexdigest() == manifest['archive_sha256']
with zipfile.ZipFile(base / 'baseline.zip') as z:
    assert set(z.namelist()) == set(manifest['files'])
    assert len(z.namelist()) == len(set(z.namelist()))
    canonical = set(specgraph.ontology_paths())
    baseline_canonical = {p for p in z.namelist() if p.endswith('.ttl') and '/validation/test/' not in p}
    assert canonical == baseline_canonical, 'Changed ontology inventory requires a new reviewed baseline'
    checked = 0
    for path, digest in manifest['files'].items():
        original = z.read(path)
        assert hashlib.sha256(original).hexdigest() == digest
        # Processing documentation is allowed editorial additions. RDF and fixtures are fixed.
        if path.endswith('.html'):
            continue
        current = (ROOT / path).read_text(encoding='utf-8').encode()
        assert current == original, ('Published RDF/fixture bytes changed', path)
        if path.endswith('.ttl'):
            assert isomorphic(Graph().parse(data=original, format='turtle'), Graph().parse(data=current, format='turtle')), path
            checked += 1

# Counterexamples ensure equality does not discard targets, bounds, annotations or list order.
SH = Namespace('http://www.w3.org/ns/shacl#')
EX = Namespace('urn:simplification-probe:')
original = Graph().parse(data='''@prefix sh:<http://www.w3.org/ns/shacl#> .
<urn:simplification-probe:S> a sh:NodeShape; sh:targetNode <urn:simplification-probe:f>;
sh:property [ sh:path <urn:simplification-probe:p>; sh:minCount 1; sh:maxCount 1 ];
sh:in (1 2); sh:message "Keep diagnostic".''', format='turtle')
assert isomorphic(original, Graph().parse(data=original.serialize(format='turtle'), format='turtle'))
for predicate in [SH.minCount, SH.maxCount, SH.targetNode, SH.message]:
    changed = Graph() + original
    changed.remove(next(changed.triples((None, predicate, None))))
    assert not isomorphic(original, changed), predicate
changed = Graph() + original
head = changed.value(EX.S, SH['in']); tail = changed.value(head, RDF.rest)
changed.set((head, RDF.first, Literal(2))); changed.set((tail, RDF.first, Literal(1)))
assert not isomorphic(original, changed)
print(f'PASS: {checked} RDF files and retained fixtures exactly preserve the frozen baseline; negative controls detect semantic changes')
