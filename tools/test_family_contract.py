"""Module-scoped positive/value/cardinality contracts, also consumed by Jena."""
from pathlib import Path
import json,sys
from rdflib import Graph,Namespace,URIRef
from pyshacl import validate
from _family_contract_cases import cases
ROOT=Path(__file__).resolve().parents[1]
SH=Namespace('http://www.w3.org/ns/shacl#')
rows=cases();graphs={}
assert len({row['name'] for row in rows})==len(rows), 'Case names must be unique evidence identifiers'
for index,row in enumerate(rows,1):
    if row['module'] not in graphs:graphs[row['module']]=Graph().parse(ROOT/row['module'])
    selected=graphs[row['module']]
    if row.get('targetShape'):
        selected=Graph()+selected
        selected.add((URIRef(row['targetShape']),SH.targetNode,URIRef(row['targetNode'])))
    ok,report,detail=validate(Graph().parse(data=row['data'],format='turtle'),shacl_graph=selected,inference='none')
    assert bool(ok)==row['expected'],(row['name'],detail)
    if row['path']:assert URIRef(row['path']) in report.objects(None,SH.resultPath),(row['name'],detail)
    if row.get('expectedShape'):assert URIRef(row['expectedShape']) in report.objects(None,SH.sourceShape),(row['name'],detail)
    if index%100==0:print(f'Validated {index}/{len(rows)} family contracts',flush=True)
p=ROOT/'specification/validation/test/family-contracts.json'
# RDF blank-node identifiers are immaterial; compare graphs when checking retained cases.
if '--write' in sys.argv:p.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
else:
    from rdflib.compare import isomorphic
    retained=json.loads(p.read_text(encoding='utf-8'))
    assert len(rows)==len(retained)
    for a,b in zip(rows,retained):
        assert {k:v for k,v in a.items() if k!='data'}=={k:v for k,v in b.items() if k!='data'}
        assert isomorphic(Graph().parse(data=a['data'],format='turtle'),Graph().parse(data=b['data'],format='turtle'))
print(f'PASS: {len(rows)} authored module contracts with result-path assertions')
