"""Read-only publication acceptance; a successful HTML fallback is a failure."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,urllib.request
from rdflib import OWL, RDF
from concurrent.futures import ThreadPoolExecutor
from rdflib import Graph
from rdflib.compare import isomorphic

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='https://hexplain.io')
parser.add_argument('--output',default='review-2026-09-05/live-publication.json')
args=parser.parse_args()
base=args.base_url.rstrip('/')
cases=[]
for module in json.loads((root/'specification/reference/manifest.json').read_text(encoding='utf-8')):
    for file in sorted((root/module['module']).glob('*.ttl')):
        graph=Graph().parse(file,format='turtle')
        for ontology in graph.subjects(RDF.type,OWL.Ontology):
            iri=str(ontology)
            if iri.startswith('https://hexplain.io/ns/'):
                cases.append((base+iri.removeprefix('https://hexplain.io'),'text/turtle',file))
for file in sorted((root/'releases').glob('*/manifest.json')):
    cases.append((base+'/'+file.relative_to(root).as_posix(),'application/json',file))
assert cases, 'No publication contracts discovered'
def check(case):
    url,media,file=case
    row=dict(url=url,expected_media_type=media,passed=False)
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':media}),timeout=15) as response:
            row.update(status=response.status,media_type=response.headers.get_content_type(),final_url=response.url)
            if response.status != 200: raise ValueError('Expected HTTP 200')
            body=response.read(4*1024*1024+1)
        if len(body)>4*1024*1024:raise ValueError('Response exceeds publication check limit')
        row['response_sha256']=hashlib.sha256(body).hexdigest()
        if row['media_type']!=media:raise ValueError('Incorrect negotiated media type; possible HTML fallback')
        if media=='application/json':
            if json.loads(body)!=json.loads(file.read_text(encoding='utf-8')):raise ValueError('Published manifest differs from local immutable snapshot')
        elif not isomorphic(Graph().parse(data=body,format='turtle'),Graph().parse(data=file.read_bytes(),format='turtle')):
            raise ValueError('Published RDF differs from canonical graph')
        row['passed']=True
    except Exception as error:row['error']=str(error)
    return row
with ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(check,cases))
out=root/args.output
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(dict(checked_at=datetime.now(timezone.utc).isoformat(),checks=results),indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,indent=2))
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
