"""Executable layout and compound-dataset contracts, without inference or rules."""
from pathlib import Path
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
import base64, json
ROOT=Path(__file__).resolve().parents[1]
PREFIX="""@prefix ex:<urn:hexplain:competency:> .
@prefix dlv:<https://hexplain.io/ns/dlv#> .
@prefix b:<https://hexplain.io/ns/bddo#> .
@prefix a:<https://hexplain.io/ns/aspect/bundle#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
@prefix skos:<http://www.w3.org/2004/02/skos/core#> .
@prefix dct:<http://purl.org/dc/terms/> .
b:uint8 a b:DataType . ex:axis a dlv:Axis . ex:f a b:Field .
ex:role a skos:Concept .
"""
CASES=[]
def case(name,data,ok,path=''): CASES.append((name,data,ok,path))
layout='ex:l a dlv:DataLayout; dlv:cellDataType b:uint8; dlv:hasDimension (ex:d). ex:d a dlv:Dimension; dlv:hasAxis ex:axis; dlv:dimensionSize 8. '
for prop in ['cellBitWidth','dimensionSize','dimensionStride','chunkSize']:
    owner='ex:l' if prop=='cellBitWidth' else 'ex:d'
    base=layout.replace('dlv:dimensionSize 8','dlv:dimensionSize 8')
    if prop=='dimensionSize': base=base.replace('; dlv:dimensionSize 8','')
    if prop=='chunkSize': base+='ex:l dlv:chunkOffsetsFromField ex:f. '
    for label,value,ok in [('integer','3',True),('typed integer','"3"^^xsd:unsignedByte',True),('zero','0',False),('negative','-1',False),('fraction','1.5',False),('string','"3"',False)]:
        case(prop+' '+label,base+f'{owner} dlv:{prop} {value}.',ok,'' if ok else 'https://hexplain.io/ns/dlv#'+prop)
case('MSB packed',layout+'ex:l dlv:cellBitWidth 1; dlv:cellPackingOrder b:MSBFirst.',True)
case('LSB packed',layout+'ex:l dlv:cellBitWidth 4; dlv:cellPackingOrder b:LSBFirst.',True)
case('dynamic packed width',layout+'ex:l dlv:cellBitWidthFromField ex:f.',True)
case('conflicting packed widths',layout+'ex:l dlv:cellBitWidth 4; dlv:cellBitWidthFromField ex:f.',False)
case('unrelated metadata','ex:x dlv:cellBitWidth "verbatim".',True)
for prop in ['minParts','maxParts']:
    for label,value,ok in [('zero','0',True),('integer','2',True),('fraction','0.5',False),('negative','-1',False),('string','"2"',False)]:
        case(prop+' '+label,f'ex:s a a:PartSpec; a:{prop} {value}.',ok,'' if ok else 'https://hexplain.io/ns/aspect/bundle#'+prop)
profile='ex:profile a a:BundleProfile; a:partSpec ex:spec. ex:spec a a:PartSpec; a:required true; a:partRole ex:role. '
asset='ex:asset a a:Asset; dct:conformsTo ex:profile. '
part='ex:asset a:hasPart ex:p. ex:p a a:Part; a:partRole ex:role. '
case('required compound part',profile+asset+part,True)
case('missing required compound part',profile+asset,False)
case('nested compound scoped independently',profile+asset+part+'ex:p a a:Asset; dct:conformsTo ex:profile.',False)
case('nested compound satisfied',profile+asset+part+'ex:p a a:Asset; dct:conformsTo ex:profile; a:hasPart ex:leaf. ex:leaf a a:Part; a:partRole ex:role.',True)
case('primary typed part',asset+part+'ex:asset a:primaryPart ex:p.',True)
case('literal primary',asset+'ex:asset a:primaryPart "part".',False,'https://hexplain.io/ns/aspect/bundle#primaryPart')
case('inverted count range','ex:s a a:PartSpec; a:minParts 3; a:maxParts 2.',False)
case('required zero contradiction','ex:s a a:PartSpec; a:required true; a:minParts 0.',False)


case('primary alone satisfies required role',profile+asset+'ex:asset a:primaryPart ex:p. ex:p a a:Part; a:partRole ex:role.',True)
case('primary wrong role still rejects',profile+asset+'ex:asset a:primaryPart ex:p. ex:p a a:Part.',False)
case('literal compound member',asset+'ex:asset a:hasPart "file".',False,'https://hexplain.io/ns/aspect/bundle#hasPart')
case('untyped compound member',asset+'ex:asset a:hasPart ex:p.',False,'https://hexplain.io/ns/aspect/bundle#hasPart')
case('unrelated hasPart remains out of scope','ex:x a:hasPart "verbatim".',True)

def run():
    shapes=Graph()
    for f in ['specification/dlv/dlv.ttl','specification/aspect/bundle/bundle.ttl']:shapes.parse(ROOT/f)
    rows=['# name\tconforms\texpected-path\tbase64 Turtle']
    for name,data,expected,path in CASES:
        source=PREFIX+data
        ok,report,detail=validate(Graph().parse(data=source,format='turtle'),shacl_graph=shapes,inference='none',advanced=False)
        assert bool(ok)==expected,(name,detail)
        if path:assert URIRef(path) in report.objects(None,Namespace('http://www.w3.org/ns/shacl#').resultPath),(name,detail)
        rows.append('\t'.join([name,str(expected).lower(),path,base64.b64encode(source.encode()).decode()]))
    corpus=ROOT/'specification/validation/test/layout-competency.tsv'
    rendered='\n'.join(rows)+'\n'
    if '--write' in __import__('sys').argv:corpus.write_text(rendered,encoding='utf-8')
    else:assert corpus.read_text(encoding='utf-8')==rendered
    print(f'PASS: {len(CASES)} layout/compound cases with inference and rule execution disabled')
if __name__=='__main__':run()
