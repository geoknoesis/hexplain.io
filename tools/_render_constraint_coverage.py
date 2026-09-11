"""Render the measured ledger without upgrading diagnostic evidence to acceptance."""
from pathlib import Path
from _site_inventory import with_print_link
import json
from html import escape
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'specification/validation'

def render():
    e=json.loads((OUT/'constraint-coverage.json').read_text(encoding='utf-8'))
    s=e['summary']
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Constraint-level coverage</title><style>body{max-width:1200px;margin:30px auto;padding:20px;font:16px/1.6 system-ui;color:#18323b}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{padding:10px;border-bottom:1px solid #ccd;text-align:left;vertical-align:top;overflow-wrap:anywhere}input{font:inherit;padding:6px}a{color:#006657}summary{cursor:pointer}</style><main><h1>Constraint-level coverage</h1>'''
    status='Every inventoried component has two-sided evaluation evidence.' if e['complete'] else 'Component coverage is not complete.'
    page+=f'<p><strong>{status}</strong> {s["components"]} component obligations; {s["two_sided"]} have observed success and failure; {s["never_evaluated"]} were never evaluated in these {s["cases"]} retained validation calls.</p>'
    page+='<p>'+escape(e['scope'])+'</p><p><a href="constraint-coverage.json">Exact obligations, input hashes and case references</a></p><p><label>Filter by module, shape or component <input id="query" type="search"></label> <label><input id="gaps" type="checkbox" checked> Show gaps only</label></p><p id="count" role="status"></p><table><thead><tr><th>Source / shape</th><th>Component / parameters</th><th>Observed cases</th></tr></thead><tbody>'
    for r in e['constraints']:
        page+=f'<tr data-covered="{str(r["two_sided_evaluation"]).lower()}"><td>'+escape(r['source'])+'<br>'+escape(', '.join(r.get('owners',[])))+'<br>'+escape(r.get('path',''))+'<details><summary>Shape and stable obligation ID</summary>'+escape(r['shape'])+'<br>'+escape(r['id'])+'</details></td><td>'+escape(r['component'].split('#')[-1])+'<details><summary>Parameters</summary>'+escape(json.dumps(r['parameters'],ensure_ascii=False))+'</details></td><td>'
        for field,label in [('passed','Success'),('failed','Failure'),('empty_value_passes','Empty-value success')]:
            page+=f'<details><summary>{label}: {len(r[field])}</summary>'+ '<br>'.join(escape(v) for v in r[field])+'</details>'
        page+='</td></tr>'
    page+='''</tbody></table><script>const q=document.getElementById('query'),g=document.getElementById('gaps'),rows=[...document.querySelectorAll('tbody tr')];function filter(){let n=0;for(const r of rows){r.hidden=(g.checked&&r.dataset.covered==='true')||!r.textContent.toLowerCase().includes(q.value.toLowerCase());if(!r.hidden)n++;}document.getElementById('count').textContent=n+' obligations shown';}q.addEventListener('input',filter);g.addEventListener('change',filter);filter();</script></main></html>'''
    return with_print_link(OUT/'constraint-coverage.html',page)

if __name__=='__main__':(OUT/'constraint-coverage.html').write_text(render(),encoding='utf-8')
