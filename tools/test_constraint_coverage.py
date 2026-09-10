"""Require a fresh ledger and two-sided evidence for every inventoried component."""
import hashlib,json
from _constraint_coverage import ROOT,OUT,inventory,trace,SH,two_sided
from rdflib import Graph,Namespace
from pyshacl import validate

evidence=json.loads((OUT/'constraint-coverage.json').read_text(encoding='utf-8'))
graphs,rows=inventory()
expected={r['id']:r for r in rows.values()}
actual={r['id']:r for r in evidence['constraints']}
assert len(actual)==len(evidence['constraints'])==len(expected)
for key,row in actual.items():
    for field in ['source','shape','component','parameters','path','owners']:assert row[field]==expected[key][field],(key,field)
    assert row['two_sided_evaluation']==two_sided(row)
    for field in ['passed','failed','empty_value_passes']:
        assert row[field]==sorted(set(row[field])),(key,field)
assert evidence['complete']==all(r['two_sided_evaluation'] for r in actual.values())
assert evidence['complete'], 'Component coverage regressed: add witnesses and remeasure before accepting this candidate'
assert evidence['summary']['components']==len(actual)
assert evidence['summary']['two_sided']==sum(r['two_sided_evaluation'] for r in actual.values())
assert evidence['summary']['never_evaluated']==sum(not(r['passed'] or r['failed'] or r['empty_value_passes']) for r in actual.values())
for collection in ['sources','corpus_hashes']:
    for path,digest in evidence[collection].items():
        assert hashlib.sha256((ROOT/path).read_text(encoding='utf-8').encode()).hexdigest()==digest,path
assert set(evidence['sources'])==set(graphs)
# An independent small contract checks instrumentation rather than trusting counts.
EX=Namespace('urn:coverage-probe:')
shapes=Graph().parse(data='''@prefix sh:<http://www.w3.org/ns/shacl#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
<urn:coverage-probe:S> a sh:NodeShape; sh:targetNode <urn:coverage-probe:f>; sh:property <urn:coverage-probe:P>.
<urn:coverage-probe:P> sh:path <urn:coverage-probe:value>; sh:datatype xsd:integer; sh:minCount 1; sh:maxCount 1.
''',format='turtle')
observed={(str(EX.P),str(SH[c+'ConstraintComponent'])):{'passed':[],'failed':[],'empty_value_passes':[]} for c in ['Datatype','MinCount','MaxCount']}
current=['']
with trace(observed,current):
    for name,value,ok in [('integer','1',True),('wrong type','"one"',False),('missing',None,False),('duplicate','1,2',False)]:
        current[0]=name
        data=Graph() if value is None else Graph().parse(data=f'<{EX.f}> <{EX.value}> {value}.',format='turtle')
        assert validate(data,shacl_graph=shapes,inference='none')[0]==ok
assert observed[(str(EX.P),str(SH.DatatypeConstraintComponent))]['failed']==['wrong type']
assert observed[(str(EX.P),str(SH.DatatypeConstraintComponent))]['empty_value_passes']==['missing']
assert observed[(str(EX.P),str(SH.MinCountConstraintComponent))]['failed']==['missing']
assert observed[(str(EX.P),str(SH.MaxCountConstraintComponent))]['failed']==['duplicate']
assert two_sided(dict(component=str(SH.MaxCountConstraintComponent),passed=[],empty_value_passes=['zero'],failed=['one']))
assert not two_sided(dict(component=str(SH.DatatypeConstraintComponent),passed=[],empty_value_passes=['zero'],failed=['wrong']))
print(f"PASS: {len(actual)} component obligations have fresh two-sided evidence; independent semantic review remains separate")
