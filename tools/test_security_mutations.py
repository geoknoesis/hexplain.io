"""Independent removals establish sensitivity of the opt-in profile's negative cases.
These are SHACL constraint tests, not authorization or inheritance tests.
"""
from pathlib import Path
import base64
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
ROOT=Path(__file__).resolve().parents[1]
SH=Namespace('http://www.w3.org/ns/shacl#')
SEC=Namespace('https://hexplain.io/ns/aspect/security#')
SKOS=Namespace('http://www.w3.org/2004/02/skos/core#')
EX=Namespace('urn:hexplain:security-example:')
original=Graph().parse(ROOT/'specification/validation/test/security-profile.ttl')
rows={}
for line in (ROOT/'specification/validation/test/security-competency.tsv').read_text(encoding='utf-8').splitlines():
    if line and not line.startswith('#'):
        name,expected,path,encoded=line.split('\t')
        rows[name]=(expected,path,Graph().parse(data=base64.b64decode(encoded),format='turtle'))
mutations=[
    ('missing system',SEC.markingSystem,SH.minCount),
    ('two systems',SEC.markingSystem,SH.maxCount),
    ('wrong register',SKOS.inScheme,SH.hasValue),
    ('untyped date',SEC.markingDate,SH.datatype),
]
for name,path,predicate in mutations:
    expected,result_path,data=rows[name]
    assert expected=='false'
    valid,report,_=validate(data,shacl_graph=original,inference='none')
    assert not valid and URIRef(result_path) in report.objects(None,SH.resultPath),name
    mutant=Graph()+original
    removed=0
    for prop in list(mutant.subjects(SH.path,path)):
        for value in list(mutant.objects(prop,predicate)):
            mutant.remove((prop,predicate,value));removed+=1
    assert removed==1,(name,removed)
    assert validate(data,shacl_graph=mutant,inference='none')[0],name
    assert validate(rows['resolved level'][2],shacl_graph=mutant,inference='none')[0],name
# Independently confirm that activation is necessary: removing its sole target
# makes all negative cases vacuously conform, not semantically correct.
untargeted=Graph()+original
assert (EX.MarkingShape,SH.targetClass,EX.Marked) in untargeted
untargeted.remove((EX.MarkingShape,SH.targetClass,EX.Marked))
negatives=0
for name,(expected,path,data) in rows.items():
    if expected=='false':
        assert not validate(data,shacl_graph=original,inference='none')[0],name
        assert validate(data,shacl_graph=untargeted,inference='none')[0],name
        negatives+=1
assert negatives==7
print('PASS: 4 isolated security constraint mutations; target-removal sensitivity for 7 negative cases; positive controls retained')
