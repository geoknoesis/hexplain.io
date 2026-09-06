"""Enrich documentation annotations and build complete, linked HTML term references.

Run with --enrich once after editorial changes; ordinary regeneration reads canonical RDF.
--check verifies the generated sections without modifying files.
"""
import argparse,json,re,os
from html import escape as e
from collections import defaultdict
from functools import lru_cache
from rdflib import Graph,RDF,RDFS,OWL,URIRef,BNode,Literal
from _reference import *

START='<!-- BEGIN GENERATED TERM REFERENCE -->'
END='<!-- END GENERATED TERM REFERENCE -->'
GUIDE='''<section id="reading-guide"><h2>How to read a term or shape</h2>
<dl><dt><b>Identity, label and definition</b></dt><dd>The IRI is the persistent identifier; a label is a human-readable name, not a lookup key. The definition states the meaning. A scope note explains appropriate use without adding a logical axiom. Labels and documentation literals retain their language tags in the RDF.</dd>
<dt><b>Domain and range are inference axioms</b></dt><dd>An RDFS domain can infer the subject's type; a range can infer the object's type or constrain its datatype interpretation. They do not require a value to be present. Multiple asserted domains or ranges apply together, rather than offering alternatives. An explicit union expression denotes alternatives. Missing axioms are reported as missing, rather than filled in from examples.</dd>
<dt><b>Shape activation is local</b></dt><dd>Targets select focus nodes for a validation run. A shape without a target may still be applied through another shape or by a caller. Following a property path changes the value nodes being constrained; a nested shape's constraints must be read in that context. Loading the required shapes and vocabulary graph, and choosing an entailment regime, are part of the validation setup.</dd>
<dt><b>Allowed values and presence are separate</b></dt><dd>A datatype, class or allowed-value list checks values that exist. It does not make the property required. A minimum count of one requires a value; a maximum count of one permits at most one distinct RDF value. RDF graphs do not count duplicate copies of the same triple. Missing count constraints must not be read as zero or one. A non-closed shape does not reject unrelated extra properties merely because they are undocumented.</dd>
<dt><b>Alternatives and nested cardinalities</b></dt><dd>OR requires at least one conforming branch, XONE exactly one, AND all branches, and NOT rejects conformance to its operand. A count inside a branch applies within that branch, not universally to the property. Qualified counts count values conforming to the qualified shape. Read the whole owning shape before extracting a requirement from one nested clause.</dd>
<dt><b>Property paths and ordered data</b></dt><dd>An ordered list used as a SHACL path is a sequence of path steps. A list under an allowed-values constraint enumerates permitted values; a list under OR enumerates alternative shapes. RDF list order is meaningful, whereas the order of unrelated triples is not. The expanded reference preserves these distinctions and links reusable named shapes.</dd>
<dt><b>Constraints and rules</b></dt><dd>SHACL SELECT constraints identify violations. CONSTRUCT rules derive triples and require a processor supporting the applicable SHACL rule extension; their presence is not evidence that a validator runs them. A result's severity belongs to its source shape. Nested property shapes do not inherit a parent shape's severity.</dd>
<dt><b>Classes, properties and controlled concepts</b></dt><dd>Classes type resources; properties relate subjects to values; SKOS concepts are controlled values. Concept-scheme membership, collection membership, subclassing and logical equivalence are different relations. A related-resource link does not assert equivalence. A format profile maps raw codes to the selected register's concepts.</dd>
<dt><b>Validation versus implementation support</b></dt><dd>A documented term or passing RDF shape does not establish binary decoder support, mathematical proof, or conformance to every format using that concept. Source files, declared versions and the separate coverage inventory identify the evidence and boundaries.</dd></dl>
<p>Reference standards: <a href="https://www.w3.org/TR/rdf-schema/">RDF Schema</a>, <a href="https://www.w3.org/TR/shacl/">SHACL</a>, <a href="https://www.w3.org/TR/shacl-af/">SHACL Advanced Features</a>, <a href="https://www.w3.org/TR/skos-reference/">SKOS</a>, and <a href="https://www.w3.org/TR/swbp-vocab-pub/">W3C vocabulary publication guidance</a>.</p></section>'''
STYLE='''
.term-reference{max-width:1100px;margin:3rem auto;line-height:1.65}.term-reference .term-toc{display:flex;gap:.5rem 1rem;flex-wrap:wrap}.term-reference article{border:1px solid #c8d9d4;border-radius:8px;padding:1.4rem;margin:1.4rem 0;background:#fff;color:#17333d;scroll-margin-top:2rem}.term-reference h3{margin-top:0}.term-reference .term-iri{overflow-wrap:anywhere;font:13px/1.6 ui-monospace,Consolas,monospace}.term-reference dt{font-weight:700;margin-top:.9rem}.term-reference dd{margin:.2rem 0 .8rem}.term-reference .constraint{border-left:3px solid #dce9e4;padding-left:1rem;margin:.6rem 0}.term-reference .constraint>li{margin:.35rem 0}.term-reference pre{white-space:pre;overflow:auto;font:12px/1.6 ui-monospace,Consolas,monospace;background:#eff4f2;color:#17333d;padding:1rem}.term-reference summary{cursor:pointer;font-weight:650}.term-reference a{color:#006b60}.term-reference .term-kind{font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:#47665f}.term-reference .term-note{font-size:.9rem;color:#496259}.term-reference table{width:100%;border-collapse:collapse}.term-reference th,.term-reference td{padding:.5rem;border-bottom:1px solid #dce9e4;text-align:left}.term-reference :focus-visible{outline:3px solid #078779;outline-offset:3px}@media(max-width:650px){.term-reference article{padding:1rem}}@media print{.term-reference article{break-inside:avoid}.term-reference details{display:block}}
'''
PREDICATES={
SH.property:'Property constraint',SH.path:'Value path',SH.targetClass:'Target class',SH.targetSubjectsOf:'Target subjects of',SH.targetObjectsOf:'Target objects of',SH.targetNode:'Target node',
SH.datatype:'Required literal datatype (exact SHACL datatype)',SH['class']:'Required value class',SH.nodeKind:'Allowed RDF node kind',SH.minCount:'Minimum value count',SH.maxCount:'Maximum value count',
SH.minInclusive:'Minimum numeric value, inclusive',SH.minExclusive:'Minimum numeric value, exclusive',SH.maxInclusive:'Maximum numeric value, inclusive',SH.maxExclusive:'Maximum numeric value, exclusive',
SH.minLength:'Minimum string length',SH.maxLength:'Maximum string length',SH.pattern:'Regular expression',SH.flags:'Regular-expression flags',SH['in']:'Allowed values',
SH['or']:'At least one alternative must conform (OR)',SH['and']:'Every branch must conform (AND)',SH.xone:'Exactly one alternative must conform (XONE)',SH['not']:'Must NOT conform to',
SH.node:'Referenced validation shape',SH.sparql:'SPARQL validation constraint',SH.select:'SELECT query returning violations',SH.ask:'ASK validator',SH.message:'Validation message',SH.severity:'Severity',
SH.closed:'Closed shape',SH.ignoredProperties:'Properties ignored by closed-shape checking',SH.equals:'Value-set equality with path',SH.disjoint:'Disjoint value set from path',SH.lessThan:'Values less than path values',SH.lessThanOrEquals:'Values less than or equal to path values',
SH.rule:'Derivation rule (not a validation constraint)',SH.construct:'CONSTRUCT query generating triples',SH.condition:'Rule activation condition',SH.order:'Execution order',SH.deactivated:'Deactivated',SH.prefixes:'SPARQL prefix declarations',SH.declare:'Namespace declaration',SH.prefix:'Prefix',SH.namespace:'Namespace IRI',
SH.qualifiedValueShape:'Qualified value shape',SH.qualifiedMinCount:'Minimum conforming values',SH.qualifiedMaxCount:'Maximum conforming values',SH.qualifiedValueShapesDisjoint:'Qualified value shapes disjoint',
SH.alternativePath:'Alternative path',SH.inversePath:'Inverse path',SH.zeroOrMorePath:'Zero-or-more path',SH.oneOrMorePath:'One-or-more path',SH.zeroOrOnePath:'Optional path',
}

@lru_cache(maxsize=None)
def file_subjects(path):
    return set(load([path]).subjects())

def enrich():
    edits=[]
    for directory,paths in modules().items():
        g=load(paths,base=True)
        for path in paths:
            base=(ROOT/path).read_text(encoding='utf-8').split(ANNOTATION_MARKER)[0].rstrip()+'\n'
            ownfile=Graph().parse(data=base,format='turtle');rows=[]
            for t in owned(ownfile):
                annotations=[(SKOS.definition,Literal(definition(g,t),lang='en')),(SKOS.scopeNote,Literal(scope(g,t),lang='en'))]
                if not list(g.objects(t,RDFS.label)):annotations.append((RDFS.label,Literal(label(g,t),lang='en')))
                if not list(g.objects(t,RDFS.isDefinedBy)) and kind(g,t)!='Ontology':annotations.append((RDFS.isDefinedBy,owner(t)))
                for predicate,value in annotations:
                    if not list(ownfile.objects(t,predicate)):rows.append(f'{t.n3()} {predicate.n3()} {value.n3()} .')
            edits.append((ROOT/path,base+ANNOTATION_MARKER+'# Editorial annotations only; OWL axioms and SHACL constraints above are unchanged.\n'+'\n'.join(rows)+'\n'))
    # Resolve every definition before any write, so a missing entry cannot leave half an update.
    for p,text in edits:p.write_text(text,encoding='utf-8')

def sortkey(g,node,seen=frozenset()):
    if not isinstance(node,BNode):return str(node)
    if node in seen:return 'recursive'
    return '['+';'.join(sorted(str(p)+'='+sortkey(g,o,seen|{node}) for p,o in g.predicate_objects(node)))+']'

class Renderer:
    def __init__(self,g,registry,doc):self.g=g;self.registry=registry;self.doc=doc
    def link(self,node):
        if isinstance(node,Literal):return '<code>'+e(node.n3())+'</code>'
        if node==RDF.nil:return '<code>rdf:nil</code> (empty list)'
        if isinstance(node,BNode):return self.node(node)
        label=compact(self.g,node);target=self.registry.get(node)
        href=(os.path.relpath(target,self.doc.parent).replace('\\','/')+'#term-'+local(node)) if target else str(node)
        return f'<a href="{e(href,quote=True)}"><code>{e(label)}</code></a>'
    def values(self,vals):return ', '.join(self.link(v) for v in sorted(vals,key=lambda x:sortkey(self.g,x)))
    def node(self,node,seen=frozenset()):
        if not isinstance(node,BNode):return self.link(node)
        if node in seen:return '<em>Recursive blank-node reference; see canonical Turtle.</em>'
        seen=seen|{node}
        if (node,RDF.first,None) in self.g:
            vals=[];current=node;cells=set()
            while current!=RDF.nil:
                if current in cells:return '<em>Cyclic RDF list; inspect canonical Turtle.</em>'
                cells.add(current);first=list(self.g.objects(current,RDF.first));rest=list(self.g.objects(current,RDF.rest))
                if len(first)!=1 or len(rest)!=1:return '<em>Malformed RDF list; inspect canonical Turtle.</em>'
                vals.append(self.node(first[0],seen));current=rest[0]
            return '<ol>'+''.join('<li>'+v+'</li>' for v in vals)+'</ol>'
        return self.constraints(node,seen)
    def constraints(self,node,seen=frozenset()):
        rows=[]
        for p,o in sorted(self.g.predicate_objects(node),key=lambda x:(str(x[0]),sortkey(self.g,x[1]))):
            if p in ANNOTATIONS or p==RDFS.comment:continue
            title=PREDICATES.get(p,compact(self.g,p))
            val='<pre>'+e(str(o))+'</pre>' if p in [SH.select,SH.construct,SH.ask] else self.node(o,seen)
            rows.append(f'<li><b>{e(title)}:</b> {val}</li>')
        return '<ul class="constraint">'+''.join(rows)+'</ul>'

def related_shapes(g):
    use=defaultdict(set)
    for shape in sorted(set(g.subjects(RDF.type,SH.NodeShape))|set(g.subjects(RDF.type,SH.PropertyShape)),key=str):
        if not isinstance(shape,URIRef):continue
        for cell in closure(g,shape):
            for p,o in g.predicate_objects(cell):
                if isinstance(o,URIRef) and str(o).startswith('https://hexplain.io/ns/') and p not in ANNOTATIONS and p!=RDF.type:use[o].add(shape)
    return use

def reference_section(g,terms,doc,registry,used,existing=''):
    render=Renderer(g,registry,doc)
    toc='<nav class="term-toc" aria-label="Term reference">'+''.join(f'<a href="#term-{e(local(t))}">{e(compact(g,t))}</a>' for t in terms)+'</nav>'
    cards=[]
    for t in terms:
        k=kind(g,t);name=label(g,t);definition_text=g.value(t,SKOS.definition);scope_text=g.value(t,SKOS.scopeNote)
        if not definition_text or not scope_text:raise ValueError(f'Missing canonical documentation: {t}; run with --enrich')
        shape=k in ['Node shape','Property shape','SHACL prefix declarations']
        aliases='' if re.search(r'\bid=["\']'+re.escape(local(t))+r'["\']',existing) else f'<span id="{e(local(t))}"></span>'
        def row(title,value):return f'<dt>{e(title)}</dt><dd>{value}</dd>'
        metadata=row('Label',e(name))+row('Definition',e(str(definition_text)))+row('Usage scope',e(str(scope_text)))
        metadata+=row('Declared RDF type',render.values(g.objects(t,RDF.type)) or 'No rdf:type declared; this node provides the listed infrastructure declarations.')
        if 'property' in k.lower() and not shape:
            metadata+=row('RDFS domain',render.values(g.objects(t,RDFS.domain)) or 'No global domain declared. SHACL usage scopes below do not create a global domain axiom.')
            metadata+=row('RDFS range',render.values(g.objects(t,RDFS.range)) or ('No narrower literal datatype declared; this datatype property carries literal values. Consult the applicable shapes and profile.' if k=='Datatype property' else 'No global range declared. Consult the applicable shapes and profile for permitted resources/values.'))
        else:metadata+=row('Domain / range','Not applicable to this '+e(k.lower())+'. Domain and range describe predicates; the types, relationships and constraints below describe this resource.')
        for pred,title in [(RDFS.subClassOf,'Superclass / class expression'),(RDFS.subPropertyOf,'Superproperty'),(OWL.inverseOf,'Inverse property'),(OWL.equivalentClass,'Equivalent class'),(OWL.equivalentProperty,'Equivalent property'),(SKOS.inScheme,'Concept scheme'),(SKOS.broader,'Broader concept'),(SKOS.narrower,'Narrower concept'),(SKOS.member,'Collection members'),(SKOS.altLabel,'Alternative labels'),(RDFS.seeAlso,'Related resources (no equivalence implied)'),(OWL.imports,'Imports'),(OWL.versionIRI,'Version IRI'),(OWL.versionInfo,'Version'),(OWL.priorVersion,'Prior version'),(OWL.deprecated,'Deprecation status')]:
            vals=list(g.objects(t,pred))
            if vals:metadata+=row(title,render.values(vals))
        metadata+=row('Defined by',render.values(g.objects(t,RDFS.isDefinedBy)) or render.link(t if k=='Ontology' else owner(t)))
        if not shape:
            matches=used.get(t,set())
            metadata+=row('Shape usage / validation context',render.values(matches) if matches else 'No direct named family-shape reference found. This is not a claim that a profile cannot add constraints or reference this term indirectly.')
            metadata+=row('Cardinality','Context-dependent. The linked shapes state minimum/maximum counts at their value paths; no universal cardinality is inferred.' if matches else 'No universal cardinality declared for this term.')
        elif k=='SHACL prefix declarations':
            metadata+=row('Activation / severity','Not applicable. Prefix declarations supply query namespace bindings; they do not select focus nodes or produce validation results.')
        else:
            metadata+=row('Activation',e(shape_targets(g,t)))
            metadata+=row('Severity',(render.values(g.objects(t,SH.severity)) or 'SHACL default: sh:Violation.')+' This applies to results of this shape; nested property shapes have their own severity (default sh:Violation), rather than inheriting it. Rules generate triples instead of validation results.')
        other=[str(x) for x in g.objects(t,RDFS.comment) if str(x)!=str(definition_text)]
        if other:metadata+=row('Additional source notes','<br>'.join(e(x) for x in other))
        for pred in [SKOS.note,SKOS.example]:
            vals=list(g.objects(t,pred))
            if vals:metadata+=row('Notes / examples',render.values(vals))
        source_files=[p for p in modules().get(doc.parent.relative_to(ROOT),[]) if t in file_subjects(p)]
        metadata+=row('Canonical source',', '.join(f'<a href="{e(p.name)}">{e(p.name)}</a>' for p in source_files))
        declaration='<details><summary>'+('Constraint and rule specification' if shape else 'Declared axioms and values')+'</summary>'+render.constraints(t)+'</details>'
        cards.append(f'<article id="term-{e(local(t))}" data-term-iri="{e(str(t))}">{aliases}<div class="term-kind">{e(k)}</div><h3>{e(compact(g,t))} — {e(name)}</h3><p class="term-iri">IRI: <a href="{e(str(t))}">{e(str(t))}</a></p><dl>{metadata}</dl>{declaration}</article>')
    return START+f'<style>{STYLE}</style><section class="term-reference" id="term-reference"><h2>Complete term and shape reference</h2><p>{len(terms)} named resources are documented below. Definitions and usage notes come from the canonical RDF; range and validation facts are rendered from its axioms and shapes. RDFS/OWL inference, SHACL validation, and editorial usage guidance are shown separately. Blank-node property shapes and logical alternatives are expanded under their owning named shapes.</p><p>Constraint language follows <a href="https://www.w3.org/TR/shacl/">W3C SHACL</a>; publication and persistent term identifiers follow the <a href="https://www.w3.org/TR/swbp-vocab-pub/">W3C vocabulary publication guidance</a>. Concept definitions and scope notes use <a href="https://www.w3.org/TR/skos-reference/">SKOS documentation properties</a>.</p>'+toc+''.join(cards)+'</section>'+END

def replace_normative(text,paths):
    source='\n'.join((ROOT/p).read_text(encoding='utf-8').rstrip() for p in paths)+'\n'
    section='<section id="normative-owl"><h2>Canonical vocabulary and shapes</h2><pre class="nohighlight">'+e(source,quote=False)+'</pre></section>'
    text=re.sub(r'<section id="normative-shacl">.*?</section>','',text,flags=re.S)
    if '<section id="normative-owl">' in text:return re.sub(r'<section id="normative-owl">.*?</section>',lambda m:section,text,flags=re.S)
    return text.replace('</body>',section+'</body>')

def build(check=False):
    file_subjects.cache_clear()
    mods=modules();g=load([p for paths in mods.values() for p in paths]);registry={};termsets={}
    for directory,paths in mods.items():
        terms=owned(load(paths));termsets[directory]=terms
        for t in terms:registry[t]=ROOT/directory/'index.html'
    used=related_shapes(g);failures=[];manifest=[]
    for directory,paths in mods.items():
        doc=ROOT/directory/'index.html';terms=termsets[directory];module_graph=load(paths)
        if doc.exists():text=doc.read_text(encoding='utf-8')
        else:
            ontology=next(iter(module_graph.subjects(RDF.type,OWL.Ontology)),None)
            title=label(module_graph,ontology) if ontology else directory.name
            intro=str(module_graph.value(ontology,RDFS.comment) or module_graph.value(ontology,SKOS.definition) or '')
            rootlink=os.path.relpath(ROOT/'specification/index.html',doc.parent).replace('\\','/')
            text=f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} — Hexplain specification</title><style>body{{font:16px/1.65 system-ui,sans-serif;margin:2rem auto;padding:0 1.5rem;max-width:1120px;color:#17333d}}pre{{overflow:auto}}a{{color:#006b60}}</style></head><body><header><a href="{rootlink}">Specification family</a><h1>{e(title)}</h1><p>{e(intro)}</p><p>Unofficial working specification. The namespace and version metadata below identify the vocabulary; documentation does not certify an implementation.</p></header></body></html>'
        without=re.sub(re.escape(START)+'.*?'+re.escape(END),'',text,flags=re.S)
        without=re.sub(r'<nav id="ontology-reference-navigation".*?</nav>','',without,flags=re.S)
        catalog=os.path.relpath(ROOT/'specification/reference/index.html',doc.parent).replace('\\','/')
        navigation=f'<nav id="ontology-reference-navigation" aria-label="Ontology documentation"><p><a href="#term-reference">Complete reference: {len(terms)} terms and shapes</a> · <a href="{catalog}">All vocabularies and reading guide</a></p></nav>'
        without=re.sub(r'(<body\b[^>]*>)',lambda m:m[0]+navigation,without,count=1)
        if not re.search(r'<meta\s+name=["\']viewport["\']',without,re.I):
            without=without.replace('</head>','<meta name="viewport" content="width=device-width,initial-scale=1"></head>',1)
        section=reference_section(g,terms,doc,registry,used,without)
        expected=replace_normative(without,paths)
        if '<section id="normative-owl">' in expected:expected=re.sub(r'\s*(<section id="normative-owl">)',lambda m:'\n'+section+'\n'+m[1],expected,count=1)
        else:expected=expected.replace('</body>',section+'</body>')
        # Keep normalized whitespace outside literal blocks predictable across Windows checkouts.
        expected='\n'.join(x.rstrip() for x in expected.splitlines())+'\n'
        if check:
            match=re.search(re.escape(START)+'(.*?)'+re.escape(END),text,re.S)
            if not match or START+match[1]+END!=section:failures.append(str(doc.relative_to(ROOT)))
        else:doc.write_text(expected,encoding='utf-8')
        manifest.append({'module':directory.as_posix(),'page':doc.relative_to(ROOT).as_posix(),'terms':len(terms),'shapes':sum(kind(g,t) in ['Node shape','Property shape'] for t in terms),'iris':[str(t) for t in terms]})
    if failures:raise AssertionError('Stale term references: '+', '.join(failures))
    if not check:
        out=ROOT/'specification/reference';out.mkdir(exist_ok=True)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        links=''.join(f'<li><a href="{os.path.relpath(ROOT/m["page"],out).replace(chr(92),"/")}">{e(m["module"].removeprefix("specification/"))}</a> — {m["terms"]} terms, {m["shapes"]} named shapes</li>' for m in manifest)
        (out/'index.html').write_text(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hexplain complete ontology reference</title><style>body{{font:17px/1.7 system-ui;margin:3rem auto;max-width:1000px;padding:0 24px;color:#17333d}}a{{color:#006b60}}li{{margin:8px 0}}dt{{margin-top:1rem}}dd{{margin:.2rem 0 1rem}}:focus-visible{{outline:3px solid #078779;outline-offset:3px}}</style></head><body><a href="../index.html">Specification family</a><h1>Complete ontology and shape reference</h1><p>{sum(m["terms"] for m in manifest)} named resources across {len(manifest)} modules, including {sum(m["shapes"] for m in manifest)} named shapes. Each entry includes its label, IRI, definition, usage scope, type, declared range or an explicit explanation of its absence, relationships, and validation context. Shape entries expand their value paths, alternatives, cardinalities, messages and executable queries.</p><p><a href="../validation/index.html">Validation and pinned snapshots</a> | <a href="#reading-guide">How to read terms and constraints</a> · <a href="manifest.json">Machine-readable documentation manifest</a></p><ul>{links}</ul>{GUIDE}<p>Definitions and scope notes are canonical RDF annotations. Human-readable pages are generated from that RDF. Imported terms link to their owning module; namespace reuse does not imply ownership.</p></body></html>',encoding='utf-8')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--enrich',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.enrich and args.check:parser.error('--check cannot be combined with --enrich')
    if args.enrich:enrich()
    result=build(args.check)
    print(f'PASS: {sum(m["terms"] for m in result)} terms in {len(result)} modules have complete generated references')
