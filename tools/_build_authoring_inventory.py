"""Trace private fragments to consumers without creating runtime helper shapes."""
import json
from pathlib import Path
from rdflib import Graph,Namespace
from _expand_specification_patterns import ROOT,AUTHORING,TOKEN,load_catalogs
SH=Namespace('http://www.w3.org/ns/shacl#')

def build(check=False):
    manifest,patterns,types=load_catalogs()
    consumers={name:[] for name in patterns}
    modules=[]
    for target,template in manifest['templates'].items():
        text=(AUTHORING/template).read_text(encoding='utf-8')
        for kind,name in TOKEN.findall(text):
            if kind=='constraint' and target not in consumers[name]:consumers[name].append(target)
        g=Graph().parse(ROOT/target,format='turtle')
        activation=sorted({(str(s),str(p),str(o)) for p in [SH.targetClass,SH.targetNode,SH.targetSubjectsOf,SH.targetObjectsOf] for s,o in g.subject_objects(p)})
        modules.append(dict(source=target,template=template,activation=[dict(shape=s,predicate=p,target=o) for s,p,o in activation]))
    rows=[dict(id=name,kind='property constraint' if 'sh:path' in row['text'] else 'value alternatives',fragment=row['text'],consumers=sorted(consumers[name])) for name,row in patterns.items()]
    result=dict(policy='Lexical authoring reuse only. Prefixes resolve in each consumer. Reuse does not assert ontology equivalence or transfer shape targets. Expanded modules retain local activation and need no helper imports.',patterns=rows,modules=modules)
    output=json.dumps(result,indent=2)+'\n'
    path=AUTHORING/'constraint-inventory.json'
    if check:assert path.read_text(encoding='utf-8')==output,'Stale authoring inventory'
    else:path.write_text(output,encoding='utf-8')
    return result

if __name__=='__main__':
    result=build()
    print(f"PASS: {len(result['patterns'])} fragments have consumer and activation provenance")
