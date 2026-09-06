"""Documentation completeness, determinism and annotation-only change contract."""
import json,re
from html.parser import HTMLParser
from rdflib.compare import isomorphic
from _reference import *
from _build_term_reference import build,START,END,GUIDE

class Page(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.terms=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if 'data-term-iri' in a:self.terms.append(a['data-term-iri'])
        if tag=='a':self.links.append(a.get('href',''))

pages={};total=0;shapes=0
for directory,paths in modules().items():
    g=load(paths);base=load(paths,base=True)
    # Parse only appended full-IRI annotations, then subtract them from this parse.
    annotations=Graph()
    for p in paths:
        text=(ROOT/p).read_text(encoding='utf-8')
        assert ANNOTATION_MARKER in text,p
        annotations.parse(data=text.split(ANNOTATION_MARKER,1)[1],format='turtle')
    assert all(p in ANNOTATIONS for s,p,o in annotations),'Documentation changed formal semantics'
    assert isomorphic(g-annotations,base),directory
    for t in owned(g):
        total+=1
        assert g.value(t,RDFS.label) or g.value(t,SKOS.prefLabel),t
        definition=g.value(t,SKOS.definition);scope_note=g.value(t,SKOS.scopeNote)
        assert definition and len(str(definition))>25 and str(definition).strip()!=label(g,t),t
        assert scope_note and len(str(scope_note))>40,t
        assert kind(g,t)=='Ontology' or g.value(t,RDFS.isDefinedBy),t
        shapes+=kind(g,t) in ['Node shape','Property shape']
    p=ROOT/directory/'index.html';page=Page();page.feed(p.read_text(encoding='utf-8'));pages[p]=page
    assert len(page.ids)==len(set(page.ids)),f'Duplicate fragment IDs in {p}'
    assert sorted(page.terms)==sorted(map(str,owned(g))),f'Missing or duplicate term cards in {p}'
    text=p.read_text(encoding='utf-8')
    assert '<dt>Definition</dt>' in text and '<dt>Usage scope</dt>' in text
for path,page in pages.items():
    for href in page.links:
        if '://' in href or href.startswith(('mailto:','javascript:')):continue
        target,_,fragment=href.partition('#')
        resolved=(path.parent/target).resolve() if target else path
        # Check generated cross-term links; legacy prose may link external build assets.
        if fragment.startswith('term-'):
            assert resolved in pages,(path,href)
            assert fragment in pages[resolved].ids,(path,href)
manifest=build(check=True)
saved=json.loads((ROOT/'specification/reference/manifest.json').read_text(encoding='utf-8'))
assert saved==manifest,'Reference manifest stale'
assert GUIDE in (ROOT/'specification/reference/index.html').read_text(encoding='utf-8'),'Reading guide stale'
print(f'PASS: {total} documented terms, {shapes} named shapes, {len(pages)} modules; canonical annotations, exact generated content and fragment links verified')
