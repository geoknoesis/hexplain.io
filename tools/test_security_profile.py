"""Opt-in security profile competency, including compound-resource scoping."""
from pathlib import Path
import base64
from rdflib import Graph,Namespace,URIRef
from pyshacl import validate

root=Path(__file__).resolve().parents[1]
shapes=Graph().parse(root/'specification/validation/test/security-profile.ttl')
prefix='''@prefix ex:<urn:hexplain:security-example:> .
@prefix sec:<https://hexplain.io/ns/aspect/security#> .
@prefix skos:<http://www.w3.org/2004/02/skos/core#> .
@prefix pack:<https://hexplain.io/ns/aspect/packaging#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
ex:Low a skos:Concept; skos:inScheme ex:Levels .
ex:Control a skos:Concept; skos:inScheme ex:Controls .
'''
valid='ex:file a ex:Marked; sec:markingSystem "Example"; sec:sensitivityLevel ex:Low .'
cases=[('resolved level',valid,True,None),
 ('unrelated unmarked data','ex:other sec:sensitivityLevel "verbatim".',True,None),
 ('missing system',valid.replace('sec:markingSystem "Example";',''),False,'markingSystem'),
 ('two systems',valid+'ex:file sec:markingSystem "Other".',False,'markingSystem'),
 ('literal level',valid.replace('sec:sensitivityLevel ex:Low','sec:sensitivityLevel "Low"'),False,'sensitivityLevel'),
 ('wrong register',valid.replace('sec:sensitivityLevel ex:Low','sec:sensitivityLevel ex:Control'),False,'sensitivityLevel'),
 ('undeclared concept',valid.replace('sec:sensitivityLevel ex:Low','sec:sensitivityLevel ex:Unknown'),False,'sensitivityLevel'),
 ('retained source text',valid+'ex:file sec:sensitivityLevelText "RAW LOW".',True,None),
 ('repeatable controls',valid+'ex:file sec:marking ex:Low,ex:Control.',True,None),
 ('literal control',valid+'ex:file sec:marking "Control".',False,'marking'),
 ('typed date',valid+'ex:file sec:markingDate "2026-09-06"^^xsd:date.',True,None),
 ('untyped date',valid+'ex:file sec:markingDate "2026-09-06".',False,'markingDate'),
 ('compound scope',valid+'ex:file a pack:Container; pack:hasEntry ex:child. ex:child a pack:Entry.',True,None)]
cases.extend([
 ('missing level',valid.replace('; sec:sensitivityLevel ex:Low',''),False,'sensitivityLevel'),
 ('two levels',valid+'ex:Other a skos:Concept; skos:inScheme ex:Levels. ex:file sec:sensitivityLevel ex:Other.',False,'sensitivityLevel'),
 ('child independently marked missing system',valid+'ex:file pack:hasEntry ex:child. ex:child a ex:Marked; sec:sensitivityLevel ex:Low.',False,'markingSystem'),
 ('child independently valid',valid+'ex:file pack:hasEntry ex:child. ex:child a ex:Marked; sec:markingSystem "Other"; sec:sensitivityLevel ex:Low.',True,None),
 ('child marking does not repair parent',valid.replace('sec:markingSystem "Example";','')+'ex:file pack:hasEntry ex:child. ex:child sec:markingSystem "Example".',False,'markingSystem'),
 ('multiple raw source labels',valid+'ex:file sec:sensitivityLevelText "LOW", "L".',False,'sensitivityLevelText'),
])
rows=['# name\tconforms\texpected-path\tbase64 Turtle']
for name,data,expected,path in cases:
    rows.append('\t'.join([name,str(expected).lower(),'https://hexplain.io/ns/aspect/security#'+path if path else '',base64.b64encode((prefix+data).encode()).decode()]))
    conforms,report,detail=validate(Graph().parse(data=prefix+data,format='turtle'),shacl_graph=shapes,inference='none')
    assert bool(conforms)==expected,(name,detail)
    if path:assert URIRef('https://hexplain.io/ns/aspect/security#'+path) in report.objects(None,Namespace('http://www.w3.org/ns/shacl#').resultPath),(name,detail)
corpus=root/'specification/validation/test/security-competency.tsv'
rendered='\n'.join(rows)+'\n'
if '--write' in __import__('sys').argv: corpus.write_text(rendered,encoding='utf-8')
else: assert corpus.read_text(encoding='utf-8')==rendered
print(f'PASS: {len(cases)} opt-in security profile cases; no implicit authorization or inheritance')
