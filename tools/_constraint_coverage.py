"""Measure evaluated constraint components, not term mentions or inferred coverage.

pySHACL evaluation tracing is diagnostic evidence; conformance and report paths
are still checked against the independently retained corpus expectations.
"""
from pathlib import Path
import base64, hashlib, json, runpy
from collections import defaultdict
from contextlib import contextmanager
from rdflib import Graph, Namespace, BNode, URIRef, RDF
from rdflib.compare import to_canonical_graph
from pyshacl import validate
import pyshacl
from pyshacl.constraints import ALL_CONSTRAINT_COMPONENTS
import specgraph

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'specification/validation'
SH=Namespace('http://www.w3.org/ns/shacl#')
TARGETS=[SH.targetClass,SH.targetNode,SH.targetSubjectsOf,SH.targetObjectsOf]

def two_sided(row):
    # Zero is an actual cardinality input: maxCount 0 cannot pass on nonempty values.
    # Empty datatype/class/node checks still provide no positive value witness.
    cardinality=row['component'] in {str(SH.MinCountConstraintComponent),str(SH.MaxCountConstraintComponent)}
    return bool(row['failed'] and (row['passed'] or (cardinality and row['empty_value_passes'])))

def canonical(path):
    source=Graph().parse(ROOT/path,format='turtle')
    prefix=hashlib.sha256(path.encode()).hexdigest()[:16]
    def term(t):return BNode(prefix+'_'+str(t)) if isinstance(t,BNode) else t
    g=Graph()
    for triple in to_canonical_graph(source):g.add(tuple(term(t) for t in triple))
    return g

def inventory():
    graphs={p:canonical(p) for p in specgraph.ontology_paths()}
    p='specification/validation/test/security-profile.ttl';graphs[p]=canonical(p)
    rows={}
    for path,g in graphs.items():
        for cls in ALL_CONSTRAINT_COMPONENTS:
            for param in cls.constraint_parameters():
                for node,value in g.subject_objects(param):
                    # Multiple parameters of one component constitute one obligation.
                    key=(str(node),str(cls.shacl_constraint_component))
                    if key not in rows:
                        digest=hashlib.sha256((path+'|'+key[0]+'|'+key[1]).encode()).hexdigest()
                        pending=[node];visited=set();owners=set()
                        while pending:
                            parent=pending.pop()
                            if parent in visited:continue
                            visited.add(parent)
                            if isinstance(parent,URIRef) and (parent,RDF.type,SH.NodeShape) in g:owners.add(str(parent))
                            if isinstance(parent,BNode):pending.extend(g.subjects(None,parent))
                        rows[key]=dict(id=digest,source=path,shape=key[0],component=key[1],parameters={},
                            path=str(g.value(node,SH.path) or ''),owners=sorted(owners),
                            passed=[],failed=[],empty_value_passes=[])
                    values=rows[key]['parameters'].setdefault(str(param),[])
                    if str(value) not in values:values.append(str(value));values.sort()
    return graphs,rows

@contextmanager
def trace(rows,current):
    originals=[]
    for cls in ALL_CONSTRAINT_COMPONENTS:
        original=cls.evaluate
        def wrapped(self,executor,target_graph,focus_value_nodes,evaluation_path,_original=original):
            result=_original(self,executor,target_graph,focus_value_nodes,evaluation_path)
            key=(str(self.shape.node),str(self.shacl_constraint_component))
            if key in rows and focus_value_nodes:
                field='failed' if not result[0] else ('passed' if any(focus_value_nodes.values()) else 'empty_value_passes')
                rows[key][field].append(current[0])
            return result
        originals.append((cls,original));cls.evaluate=wrapped
    try:yield
    finally:
        for cls,original in originals:cls.evaluate=original

def measure():
    graphs,rows=inventory();family=Graph()
    for p,g in graphs.items():
        if '/validation/test/' not in p:family+=g
    current=[''];cases=0
    def check(name,data,shapes,expected,path='',expected_shape=''):
        nonlocal cases
        current[0]=name
        ok,report,detail=validate(data,shacl_graph=shapes,inference='none',advanced=True)
        assert bool(ok)==expected,(name,detail)
        if path:assert URIRef(path) in report.objects(None,SH.resultPath),(name,detail)
        if expected_shape:assert URIRef(expected_shape) in report.objects(None,SH.sourceShape),(name,detail)
        cases+=1
        if cases%100==0:print(f'Traced {cases} validation calls',flush=True)
    with trace(rows,current):
        for row in json.loads((OUT/'test/family-contracts.json').read_text(encoding='utf-8')):
            selected=graphs[row['module']]
            if row.get('targetShape'):
                selected=Graph()+selected
                selected.add((URIRef(row['targetShape']),SH.targetNode,URIRef(row['targetNode'])))
            check('family-contracts:'+row['name'],Graph().parse(data=row['data'],format='turtle'),selected,row['expected'],row['path'],row.get('expectedShape',''))
        selections={
            'layout-competency.tsv':['specification/dlv/dlv.ttl','specification/aspect/bundle/bundle.ttl'],
            'security-competency.tsv':['specification/validation/test/security-profile.ttl'],
            'geometry-competency.tsv':['specification/aspect/geometry/geometry.ttl'],
            'network-competency.tsv':['specification/npv/net.ttl'],
        }
        for filename,paths in selections.items():
            shapes=Graph()
            for p in paths:shapes+=graphs[p]
            for line in (OUT/'test'/filename).read_text(encoding='utf-8').splitlines():
                if not line or line.startswith('#'):continue
                name,expected,path,encoded=line.split('\t')
                check(filename+':'+name,Graph().parse(data=base64.b64decode(encoded),format='turtle'),shapes,expected=='true',path)
        for line in (OUT/'test/competency.tsv').read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):continue
            name,module,expected,path,encoded=line.split('\t');stem=Path(module).stem
            selected=graphs[f'specification/aspect/{stem}/{stem}.ttl'];shapes=Graph()+family
            for pred in TARGETS:
                for s,o in list(shapes.subject_objects(pred)):
                    if (s,pred,o) not in selected:shapes.remove((s,pred,o))
            data=family+Graph().parse(data=base64.b64decode(encoded),format='turtle')
            check('competency.tsv:'+name,data,shapes,expected=='true',path)
        fixtures=sorted(set(ROOT.glob('specification/*/test/*-valid.ttl'))|set(ROOT.glob('specification/*/test/*-invalid.ttl'))|set(ROOT.glob('specification/*/*/test/*-valid.ttl'))|set(ROOT.glob('specification/*/*/test/*-invalid.ttl')))
        for file in fixtures:
            shapes=Graph()+family
            for extra in file.parent.parent.glob('*.ttl'):
                if extra.relative_to(ROOT).as_posix() not in graphs:shapes.parse(extra)
            check(file.relative_to(ROOT).as_posix(),family+Graph().parse(file),shapes,file.name.endswith('-valid.ttl'))
        # Reuse procedural semantic gates with the same canonical shape identities.
        # Their original independent assertions, including exact arithmetic, still run.
        procedural=['tools/test_geospatial_model.py','tools/test_video_math.py','tools/test_numeric_boundaries.py']
        original_validate=pyshacl.validate
        original_ontologies,original_shapes=specgraph.ontologies,specgraph.shapes
        try:
            specgraph.ontologies=lambda extra=(): Graph()+family+specgraph.load(extra)
            specgraph.shapes=lambda: Graph()+family
            for source in procedural:
                invocation=[0]
                def tracked_validate(*args,**kwargs):
                    nonlocal cases
                    invocation[0]+=1;cases+=1
                    current[0]=source+':validation-'+str(invocation[0])
                    return original_validate(*args,**kwargs)
                pyshacl.validate=tracked_validate
                runpy.run_path(str(ROOT/source),run_name='__main__')
        finally:
            pyshacl.validate=original_validate
            specgraph.ontologies,specgraph.shapes=original_ontologies,original_shapes
    result=[]
    for row in rows.values():
        for field in ['passed','failed','empty_value_passes']:row[field]=sorted(set(row[field]))
        row['two_sided_evaluation']=two_sided(row)
        result.append(row)
    result.sort(key=lambda r:r['id'])
    corpus_paths=sorted(set(p.relative_to(ROOT).as_posix() for p in fixtures)|set(p.relative_to(ROOT).as_posix() for p in (OUT/'test').glob('*competency.tsv'))|set(procedural)|{'specification/validation/test/family-contracts.json'})
    return dict(scope='Integrated pySHACL component evaluations in current shared corpora, vocabulary fixtures and procedural geospatial/video/numeric gates. Nested branch failures may occur within conforming graphs; two-sided evaluation is not independent semantic review or proof that each parameter is necessary. Empty-value passes are recorded separately and count as positive evidence only for cardinality components, where zero is a meaningful input. Rules and custom targets are not constraint components.',
        validator=pyshacl.__version__,
        corpus_hashes={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8').encode()).hexdigest() for p in corpus_paths},
        sources={p:hashlib.sha256((ROOT/p).read_text(encoding='utf-8').encode()).hexdigest() for p in graphs},
        summary=dict(cases=cases,components=len(result),two_sided=sum(r['two_sided_evaluation'] for r in result),never_evaluated=sum(not(r['passed'] or r['failed'] or r['empty_value_passes']) for r in result)),
        complete=all(r['two_sided_evaluation'] for r in result),constraints=result)

def extend_family():
    """Reuse evidence only for byte-identical inputs and append-only authored cases."""
    from _family_contract_cases import cases as authored_cases
    from rdflib.compare import isomorphic
    evidence=json.loads((OUT/'constraint-coverage.json').read_text(encoding='utf-8'))
    assert evidence['validator']==pyshacl.__version__, 'Changed validator requires full measurement'
    for collection in ['sources','corpus_hashes']:
        for path,digest in evidence[collection].items():
            assert hashlib.sha256((ROOT/path).read_text(encoding='utf-8').encode()).hexdigest()==digest, ('Changed input requires full measurement',path)
    graphs,inventory_rows=inventory()
    assert set(graphs)==set(evidence['sources'])
    previous={r['id']:r for r in evidence['constraints']}
    assert set(previous)=={r['id'] for r in inventory_rows.values()}
    for key,row in inventory_rows.items():
        old=previous[row['id']]
        for field in ['source','shape','component','parameters','path','owners']:assert row[field]==old[field]
        for field in ['passed','failed','empty_value_passes']:row[field]=list(old[field])
    corpus_path=OUT/'test/family-contracts.json'
    retained=json.loads(corpus_path.read_text(encoding='utf-8'))
    generated=authored_cases()
    by_name={r['name']:r for r in generated}
    assert len(by_name)==len(generated)
    assert len({r['name'] for r in retained})==len(retained)
    for old in retained:
        new=by_name[old['name']]
        assert {k:v for k,v in old.items() if k!='data'}=={k:v for k,v in new.items() if k!='data'}, 'Changed expectation requires full measurement'
        assert isomorphic(Graph().parse(data=old['data'],format='turtle'),Graph().parse(data=new['data'],format='turtle')), 'Changed case requires full measurement'
    old_names={r['name'] for r in retained}
    additions=[r for r in generated if r['name'] not in old_names]
    assert additions, 'No appended cases to measure'
    current=['']
    with trace(inventory_rows,current):
        for row in additions:
            current[0]='family-contracts:'+row['name']
            selected=graphs[row['module']]
            if row.get('targetShape'):
                selected=Graph()+selected
                selected.add((URIRef(row['targetShape']),SH.targetNode,URIRef(row['targetNode'])))
            ok,report,detail=validate(Graph().parse(data=row['data'],format='turtle'),shacl_graph=selected,inference='none',advanced=True)
            assert bool(ok)==row['expected'],(row['name'],detail)
            if row['path']:assert URIRef(row['path']) in report.objects(None,SH.resultPath),(row['name'],detail)
            if row.get('expectedShape'):assert URIRef(row['expectedShape']) in report.objects(None,SH.sourceShape),(row['name'],detail)
    for row in inventory_rows.values():
        for field in ['passed','failed','empty_value_passes']:row[field]=sorted(set(row[field]))
        row['two_sided_evaluation']=two_sided(row)
    evidence['constraints']=sorted(inventory_rows.values(),key=lambda r:r['id'])
    evidence['summary']['cases']+=len(additions)
    evidence['summary']['two_sided']=sum(r['two_sided_evaluation'] for r in inventory_rows.values())
    evidence['summary']['never_evaluated']=sum(not(r['passed'] or r['failed'] or r['empty_value_passes']) for r in inventory_rows.values())
    evidence['complete']=all(r['two_sided_evaluation'] for r in inventory_rows.values())
    # Preserve old serialization as well as semantics. A partial write is detected by the hash gate.
    corpus_text=json.dumps(retained+additions,indent=2)+'\n'
    evidence['corpus_hashes'][corpus_path.relative_to(ROOT).as_posix()]=hashlib.sha256(corpus_text.encode()).hexdigest()
    evidence.setdefault('append_only_measurements',[]).append(dict(added_cases=len(additions),previous_cases=evidence['summary']['cases']-len(additions)))
    corpus_path.write_text(corpus_text,encoding='utf-8')
    return evidence

if __name__=='__main__':
    import sys
    result=extend_family() if '--extend-family' in sys.argv else measure()
    (OUT/'constraint-coverage.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summary']))
