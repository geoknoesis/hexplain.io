"""Generate an editorial guide from private catalogs; never modify RDF."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build(check=False):
    source = ROOT / 'authoring/specification'
    contracts = json.loads((source / 'processing-contracts.json').read_text(encoding='utf-8'))
    catalog = json.loads((source / 'primitive-types.json').read_text(encoding='utf-8'))
    def detail(c):
        procedure='<ol>'+''.join('<li>'+escape(x)+'</li>' for x in c.get('procedure',[]))+'</ol>' if c.get('procedure') else ''
        table=''
        if c.get('rows'):
            table='<div role="region" tabindex="0" aria-label="'+escape(c['name'])+' comparison"><table><thead><tr>'+''.join('<th scope="col">'+escape(x)+'</th>' for x in c['columns'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(x)+'</td>' for x in row)+'</tr>' for row in c['rows'])+'</tbody></table></div>'
        return procedure+table
    sections = ''.join('<section><h2>'+escape(c['name'])+'</h2><p>'+escape(c['rule'])+
                       '</p><p>'+escape(c['exceptions'])+'</p>'+detail(c)+'<p><a href="'+escape(c['source'])+
                       '">Existing contract</a></p></section>' for c in contracts)
    rows = ''.join('<tr>'+''.join('<td>'+escape(str(row.get(key, 'Not declared')))+'</td>'
                                for key in ['name','base','width','signed','order','rdf_type'])+'</tr>'
                   for row in catalog['presets'].values())
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Shared specification patterns</title><style>body{font:17px/1.65 system-ui;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#17333d}a{color:#006b60}table{border-collapse:collapse}td,th{padding:.5rem;border:1px solid #bcc}div{overflow:auto}</style>'
            '<body><a href="../reference/index.html">Complete term reference</a><h1>Shared specification patterns</h1>'
            '<p>This editorial guide summarizes existing contracts. It adds no vocabulary, fallback policy or implementation capability. Canonical RDF and the linked processing contracts remain authoritative.</p>'+
            sections+'<p><a href="../../authoring/specification/constraint-inventory.json">Reusable constraints, consumers and local activation targets</a></p><h2>Primitive preset matrix</h2><p>Each row retains its named public preset. Missing byte order remains unspecified; no platform default is inserted. Width is storage width, not a semantic significant-bit count.</p>'
            '<div role="region" aria-label="Primitive presets" tabindex="0"><table><thead><tr><th>Preset</th><th>Base category</th><th>Bits</th><th>Signed</th><th>Byte order</th><th>RDF datatype</th></tr></thead><tbody>'+rows+'</tbody></table></div></body></html>\n')
    target = ROOT / 'specification/shared-patterns/index.html'
    if check:
        assert target.read_text(encoding='utf-8') == html, 'Stale shared-pattern guide'
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding='utf-8')
    return len(catalog['presets'])

if __name__ == '__main__':
    import sys
    print(f'PASS: {build("--check" in sys.argv)} presets in shared-pattern guide')
