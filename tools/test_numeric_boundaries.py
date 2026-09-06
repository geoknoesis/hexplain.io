"""Adversarial RDF-value tests: lexical form is not numeric value or term identity."""
from rdflib import Graph, Literal, Namespace, URIRef, BNode, RDF
from pyshacl import validate
import specgraph

A=Namespace('https://hexplain.io/ns/aspect/raster#')
S=Namespace('https://hexplain.io/ns/aspect/spatialref#')
X=Namespace('http://www.w3.org/2001/XMLSchema#')
ont=specgraph.ontologies();shapes=specgraph.shapes();failures=[];count=0

def check(name, graph, expected):
    global count
    count+=1
    actual=bool(validate(ont+graph,shacl_graph=shapes,advanced=True)[0])
    if actual!=expected:failures.append(f'{name}: expected {expected}, got {actual}')

for lexical,expected in [('1e309',False),('-1e309',False),('NaN',False),('INF',False),('1.7976931348623157e308',True),('-0.0',True)]:
    g=Graph();g.add((URIRef('urn:band'),A.sampleScale,Literal(lexical,datatype=X.double,normalize=False)))
    check('calibration '+lexical,g,expected)

g=Graph().parse(data='''@prefix a:<https://hexplain.io/ns/aspect/raster#>. @prefix x:<http://www.w3.org/2001/XMLSchema#>.
<urn:g> a:hasBand <urn:b>,<urn:c>. <urn:b> a:bandIndex 1. <urn:c> a:bandIndex "1"^^x:unsignedInt.''',format='turtle')
check('equal band indices with different integer datatypes',g,False)

# Two equal-valued but distinct double literals are still TWO rdf:first values.
g=Graph();head=BNode();g.add((URIRef('urn:rpc'),S.lineNumerator,head))
# Apply the vector shape directly through a small local target wrapper.
SH=Namespace('http://www.w3.org/ns/shacl#');wrapper=URIRef('urn:vector-test')
local=shapes+Graph();local.add((wrapper,RDF.type,SH.NodeShape));local.add((wrapper,SH.targetNode,head));local.add((wrapper,SH.node,S.CoefficientVectorShape))
cell=head
for i in range(20):
    g.add((cell,RDF.first,Literal('1.0',datatype=X.double,normalize=False)))
    next_cell=BNode() if i<19 else RDF.nil
    g.add((cell,RDF.rest,next_cell));cell=next_cell
count+=1
if not validate(ont+g,shacl_graph=local,advanced=True)[0]:failures.append('valid 20-cell coefficient vector rejected')
g.add((head,RDF.first,Literal('1.00',datatype=X.double,normalize=False)))
count+=1
if validate(ont+g,shacl_graph=local,advanced=True)[0]:failures.append('duplicate equal-valued rdf:first accepted')

assert not failures,'\n'.join(failures)
print(f'PASS: {count} lexical numeric and RDF term-identity boundary cases')
