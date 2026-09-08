"""Generate auditable corpus references, not a claim of semantic completeness."""
from pathlib import Path
import base64, hashlib, json
from html import escape
from rdflib import Graph, URIRef
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'specification/validation'

def build():
    modules=json.loads((ROOT/'specification/reference/manifest.json').read_text(encoding='utf-8'))
    terms={iri:dict(iri=iri,module=m['module'],positive=[],negative=[],result_path=[]) for m in modules for iri in m['iris']}
    sources={};count=0
    for file in sorted((OUT/'test').glob('*competency.tsv')):
        sources[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        for line in file.read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):continue
            fields=line.split('\t')
            if len(fields)==5:name,module,expected,path,encoded=fields
            else:name,expected,path,encoded=fields
            assert expected in ('true','false')
            graph=Graph().parse(data=base64.b64decode(encoded),format='turtle')
            key=file.name+':'+name;count+=1
            mentioned={str(term) for triple in graph for term in triple if isinstance(term,URIRef)}
            for iri in mentioned.intersection(terms):terms[iri]['positive' if expected=='true' else 'negative'].append(key)
            if path in terms:terms[path]['result_path'].append(key)
    rows=sorted(terms.values(),key=lambda r:r['iri'])
    summary=dict(resources=len(rows),cases=count,mentioned=sum(bool(r['positive'] or r['negative']) for r in rows),with_asserted_result_path=sum(bool(r['result_path']) for r in rows))
    result=dict(hash_policy='SHA-256 of UTF-8 corpus text with universal-newline normalization to LF; immutable archives retain their original byte hashes.',scope='Syntactic references and expected result paths in four retained shared corpora. Mentions do not prove shape activation, assertion independence, complete constraints or semantic correctness. Unmentioned terms may have evidence in other suites.',summary=summary,sources=sources,resources=rows)
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Competency traceability</title><style>body{font:16px/1.6 system-ui;margin:30px;max-width:1200px}td,th{padding:8px;text-align:left;border-bottom:1px solid #ccc;overflow-wrap:anywhere}table{width:100%;table-layout:fixed}summary{cursor:pointer}a{color:#006657}</style><h1>Competency corpus traceability</h1><p>'+escape(result['scope'])+'</p><p>'+escape(str(summary))+'</p><p><a href="competency-trace.json">Machine-readable references and corpus hashes</a></p><table><thead><tr><th>Resource</th><th>Positive / negative references</th><th>Expected result-path assertions</th></tr></thead><tbody>'
    for r in rows:
        refs=r['positive']+r['negative']
        page+='<tr><td>'+escape(r['iri'])+'</td><td>'+str(len(r['positive']))+' / '+str(len(r['negative']))+('<details><summary>Cases</summary>'+ '<br>'.join(escape(x) for x in refs)+'</details>' if refs else '')+'</td><td>'+str(len(r['result_path']))+'</td></tr>'
    return json.dumps(result,indent=2)+'\n',page+'</tbody></table></html>'

if __name__=='__main__':
    data,page=build()
    (OUT/'competency-trace.json').write_text(data,encoding='utf-8')
    (OUT/'competency-trace.html').write_text(page,encoding='utf-8')
    print(json.loads(data)['summary'])
