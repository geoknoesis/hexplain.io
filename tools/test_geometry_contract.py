"""Geometry module rejects invalid declared values without closing unrelated RDF."""
from pathlib import Path
from rdflib import Graph,Namespace,URIRef
from pyshacl import validate
ROOT=Path(__file__).resolve().parents[1]
shapes=Graph().parse(ROOT/'specification/aspect/geometry/geometry.ttl')
prefix='@prefix g:<https://hexplain.io/ns/aspect/geometry#>. @prefix xsd:<http://www.w3.org/2001/XMLSchema#>. @prefix skos:<http://www.w3.org/2004/02/skos/core#>. '
cases=[('negative','<urn:g> g:dimensionality -2.',False,'dimensionality'),('zero','<urn:g> g:dimensionality 0.',False,'dimensionality'),('fraction','<urn:g> g:dimensionality 2.5.',False,'dimensionality'),('integer','<urn:g> g:dimensionality "3"^^xsd:unsignedByte.',True,''),('literal type','<urn:g> g:geometryType "Point".',False,'geometryType'),('undeclared concept','<urn:g> g:geometryType <urn:Point>.',False,'geometryType'),('declared concept','<urn:g> g:geometryType <urn:Point>. <urn:Point> a skos:Concept.',True,''),('unknown flags','<urn:g> g:dimensionality 3.',True,''),('unrelated','<urn:g> <urn:other> -2.',True,'')]
for name,data,expected,path in cases:
 ok,report,detail=validate(Graph().parse(data=prefix+data,format='turtle'),shacl_graph=shapes,inference='none')
 assert bool(ok)==expected,(name,detail)
 if path:assert URIRef('https://hexplain.io/ns/aspect/geometry#'+path) in report.objects(None,Namespace('http://www.w3.org/ns/shacl#').resultPath)
print('PASS: 9 geometry value contracts with explicit result paths')
