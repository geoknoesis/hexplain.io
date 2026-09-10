"""The editorial overview must match its private source catalogs."""
from _build_simplification_guide import build

assert build(check=True) == 26
print("PASS: shared processing overview and all 26 preset rows match their catalogs")

import hashlib
from html import escape
from _reference import ROOT, modules, load, owned, SKOS, local
links=0
for directory,paths in modules().items():
    g=load(paths)
    page=(ROOT/directory/'index.html').read_text(encoding='utf-8')
    for term in owned(g):
        scope=str(g.value(term,SKOS.scopeNote))
        anchor='scope-'+hashlib.sha256(scope.encode()).hexdigest()[:16]
        start=page.index('id="term-'+escape(local(term))+'"')
        card=page[start:page.index('</article>',start)]
        if 'href="#'+anchor+'"' in card:
            assert page.count('id="'+anchor+'"')==1
            target=page.index('id="'+anchor+'"')
            assert escape(scope) in page[target:page.index('</dd>',target)]
            links+=1
        else:
            assert escape(scope) in card, term
assert links>0
print(f'PASS: {links} shared scope links resolve to exact visible canonical notes')
