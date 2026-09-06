"""Verify six numeric layout/compound counterexamples detect removed constraints."""
from pathlib import Path
import base64
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
ROOT=Path(__file__).resolve().parents[1]
SH=Namespace('http://www.w3.org/ns/shacl#')
shapes=Graph()
for name in ['specification/dlv/dlv.ttl','specification/aspect/bundle/bundle.ttl']:shapes.parse(ROOT/name)
cases={line.split('\t')[0]:line.split('\t') for line in (ROOT/'specification/validation/test/layout-competency.tsv').read_text().splitlines() if line and not line.startswith('#')}
for name in ['cellBitWidth zero','dimensionSize zero','dimensionStride zero','chunkSize zero','minParts negative','maxParts negative']:
    _,expected,path,encoded=cases[name]
    assert expected=='false' and path
    data=Graph().parse(data=base64.b64decode(encoded),format='turtle')
    valid,report,_=validate(data,shacl_graph=shapes,inference='none',advanced=False)
    assert not valid and URIRef(path) in report.objects(None,SH.resultPath),name
    mutant=Graph()+shapes
    removed=0
    for prop in list(mutant.subjects(SH.path,URIRef(path))):
        for predicate in [SH.minExclusive, SH.minInclusive]:
            for value in list(mutant.objects(prop,predicate)):
                mutant.remove((prop,predicate,value));removed+=1
    assert removed,name
    assert validate(data,shacl_graph=mutant,inference='none',advanced=False)[0],name
print('PASS: 6 layout/compound numeric-bound removals detected with result-path assertions')
