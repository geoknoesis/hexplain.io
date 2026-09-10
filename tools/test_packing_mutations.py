"""Packing declarations: independently remove the constraint named by each counterexample."""
from pathlib import Path
import base64
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
ROOT=Path(__file__).resolve().parents[1]
SH=Namespace('http://www.w3.org/ns/shacl#')
DLV=Namespace('https://hexplain.io/ns/dlv#')
original=Graph().parse(ROOT/'specification/dlv/dlv.ttl')
rows={r.split('\t')[0]:r.split('\t') for r in (ROOT/'specification/validation/test/layout-competency.tsv').read_text(encoding='utf-8').splitlines() if r and not r.startswith('#')}
controls=Graph().parse(data=base64.b64decode(rows['three bit cross byte packing'][3]),format='turtle')
for name,path,predicate in [
    ('unknown packing order',DLV.cellPackingOrder,SH['in']),
    ('two packing orders',DLV.cellPackingOrder,SH.maxCount),
    ('two packed widths',DLV.cellBitWidth,SH.maxCount),
    ('untyped width field',DLV.cellBitWidthFromField,SH['class']),
    ('untyped stride field',DLV.dimensionStrideFromField,SH['class']),
]:
    row=rows[name]
    data=Graph().parse(data=base64.b64decode(row[3]),format='turtle')
    conforms,report,_=validate(data,shacl_graph=original,inference='none')
    assert not conforms and URIRef(row[2]) in report.objects(None,SH.resultPath),name
    mutant=Graph()+original
    removed=[]
    for prop in mutant.subjects(SH.path,path):removed.extend(mutant.triples((prop,predicate,None)))
    assert len(removed)==1,(name,removed)
    for triple in removed:mutant.remove(triple)
    assert validate(data,shacl_graph=mutant,inference='none')[0],name
    assert validate(controls,shacl_graph=mutant,inference='none')[0],name
print('PASS: 5 isolated packing/field-reference mutations detected; positive controls retained')
