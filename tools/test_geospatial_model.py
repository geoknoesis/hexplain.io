"""Executable semantic competency questions; these are not binary-driver tests."""
from fractions import Fraction
from rdflib import Graph
from pyshacl import validate
import specgraph

prefixes='''@prefix a: <https://hexplain.io/ns/aspect/raster#> .
@prefix s: <https://hexplain.io/ns/aspect/spatialref#> .
@prefix g: <https://hexplain.io/ns/aspect/geometry#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ex: <https://example.org/> .
'''
cases=[
('multiband',True,'ex:g a a:RasterGrid; a:width 1024; a:height 512; a:bandCount 2; a:hasBand ex:b,ex:c. ex:b a:bandIndex 1; a:sampleScale 0.1e0; a:sampleOffset -2.0e0. ex:c a:bandIndex 2.'),
('partial band projection',True,'ex:g a:bandCount 5; a:hasBand ex:b. ex:b a:bandIndex 3.'),
('duplicate band index',False,'ex:g a:hasBand ex:b,ex:c. ex:b a:bandIndex 1. ex:c a:bandIndex 1.'),
('band outside count',False,'ex:g a:bandCount 2; a:hasBand ex:b. ex:b a:bandIndex 3.'),
('too many described bands',False,'ex:g a:bandCount 1; a:hasBand ex:b,ex:c.'),
('negative width',False,'ex:g a:width -1.'),
('fractional width',False,'ex:g a:width 1.5.'),
('unsigned width',True,'ex:g a:width "4294967295"^^xsd:unsignedInt.'),
('NaN calibration',False,'ex:b a:sampleScale "NaN"^^xsd:double.'),
('NaN nodata permitted',True,'ex:b a a:RasterBand; a:noDataValue "NaN"^^xsd:double.'),
('mask is resource',False,'ex:b a:hasMask "mask".'),
('scalar',True,'ex:v a a:SampleArray; a:dimensions ().'),
('empty time dimension',True,'ex:v a:dimensions (ex:t ex:y ex:x). ex:t a:dimensionName "time"; a:dimensionExtent 0. ex:y a:dimensionExtent 2. ex:x a:dimensionExtent 3.'),
('shared axes different array order',True,'ex:v a:dimensions (ex:x ex:y). ex:w a:dimensions (ex:y ex:x). ex:x a:dimensionExtent 3. ex:y a:dimensionExtent 2.'),
('negative dimension',False,'ex:v a:dimensions (ex:x). ex:x a:dimensionExtent -1.'),
('fractional dimension',False,'ex:v a:dimensions (ex:x). ex:x a:dimensionExtent 2.5.'),
('missing dimension size',False,'ex:v a:dimensions (ex:x).'),
('repeated covariance dimension',True,'ex:v a:dimensions (ex:x ex:x). ex:x a:dimensionExtent 3.'),
('unterminated list',False,'ex:v a:dimensions ex:l. ex:l rdf:first ex:x. ex:x a:dimensionExtent 3.'),
('cyclic list',False,'ex:v a:dimensions ex:l. ex:l rdf:first ex:x; rdf:rest ex:l. ex:x a:dimensionExtent 3.'),
('branching list',False,'ex:v a:dimensions ex:l. ex:l rdf:first ex:x; rdf:rest rdf:nil,ex:q. ex:q rdf:first ex:y; rdf:rest rdf:nil. ex:x a:dimensionExtent 3. ex:y a:dimensionExtent 4.'),
('group hierarchy',True,'ex:g a:hasGroup ex:h. ex:h a:hasArray ex:v. ex:v a:dimensions ().'),
('group cycle',False,'ex:g a:hasGroup ex:h. ex:h a:hasGroup ex:g.'),
('missing nested array dimensions',False,'ex:g a:hasArray ex:v.'),
('complete rotated affine',True,'ex:g a s:GeoTransform; s:originX 100.0e0; s:originY 200.0e0; s:scaleX 2.0e0; s:scaleY -3.0e0; s:skewX 0.5e0; s:skewY 0.25e0.'),
('incomplete affine',False,'ex:g a s:GeoTransform; s:originX 100.0e0.'),
('untyped incomplete linked affine',False,'ex:d s:hasGeoTransform ex:g.'),
('nonfinite affine',False,'ex:g a s:GeoTransform; s:originX "INF"^^xsd:double; s:originY 0.0e0; s:scaleX 1.0e0; s:scaleY -1.0e0; s:skewX 0.0e0; s:skewY 0.0e0.'),
('distinct GCP CRS',True,'ex:d s:hasCRS ex:projected; s:groundControlPointCRS ex:geographic; s:hasGroundControlPoint ex:p. ex:p s:gcpPixelX 0.5e0; s:gcpPixelY 0.5e0; s:gcpX 5.0e0; s:gcpY 50.0e0.'),
('incomplete untyped GCP',False,'ex:d s:hasGroundControlPoint ex:p. ex:p s:gcpX 0.0e0.'),
]
cases.extend([
 ('XYM geometry',True,'ex:shape g:hasZ false; g:hasM true.'),
 ('XYZ geometry',True,'ex:shape g:hasZ true; g:hasM false.'),
 ('XYZM geometry',True,'ex:shape g:hasZ true; g:hasM true.'),
 ('invalid measured flag',False,'ex:shape g:hasM "yes".'),
])
def rpc(n=20):
    fields=['ex:r a s:CubicRationalTransform; s:polynomialBasis ex:documentedBasis']
    for axis in ['line','sample','latitude','longitude','height']:
        fields.extend([f's:{axis}Offset 0.0e0',f's:{axis}Scale 1.0e0'])
    for term in ['lineNumerator','lineDenominator','sampleNumerator','sampleDenominator']:
        fields.append('s:'+term+' ('+' '.join(['1.0e0']+['0.0e0']*(n-1))+')')
    return '; '.join(fields)+'.'
cases.extend([
 ('RPC repeated coefficient values',True,rpc()),
 ('RPC short coefficient vector',False,rpc(19)),
 ('RPC long coefficient vector',False,rpc(21)),
 ('RPC missing basis contract',False,rpc().replace('; s:polynomialBasis ex:documentedBasis','')),
 ('RPC zero scale',False,rpc().replace('s:heightScale 1.0e0','s:heightScale 0.0e0')),
 ('RPC nonfinite coefficient',False,rpc().replace('1.0e0 0.0e0','"INF"^^xsd:double 0.0e0',1)),
])
ont=specgraph.ontologies(); shapes=specgraph.shapes()
for name,expected,body in cases:
    data=ont+Graph().parse(data=prefixes+body,format='turtle')
    conforms,_,report=validate(data,shacl_graph=shapes,inference='none',advanced=True)
    assert bool(conforms)==expected,f'{name}: expected {expected}\n{report}'

# Exact independent arithmetic oracle for the documented six-coefficient equations.
gt=list(map(Fraction,['100','2','0.5','200','0.25','-3']))
def forward(p,l):return gt[0]+p*gt[1]+l*gt[2],gt[3]+p*gt[4]+l*gt[5]
def inverse(x,y):
    det=gt[1]*gt[5]-gt[2]*gt[4]
    if not det:raise ValueError('singular affine')
    x-=gt[0];y-=gt[3]
    return (gt[5]*x-gt[2]*y)/det,(-gt[4]*x+gt[1]*y)/det
assert forward(Fraction(1,2),Fraction(1,2))==(Fraction('101.25'),Fraction('198.625'))
for p in range(-5,6):
    for l in range(-5,6):assert inverse(*forward(p,l))==(p,l)
gt[1:3]=[Fraction(1),Fraction(2)];gt[4:6]=[Fraction(2),Fraction(4)]
try:inverse(0,0)
except ValueError:pass
else:raise AssertionError('singular inverse accepted')
assert Fraction(100)*Fraction('0.1')+Fraction(-2)==8
print(f'PASS: {len(cases)} geospatial/array SHACL cases; 121 exact affine round trips; center, singularity and calibration vectors')
