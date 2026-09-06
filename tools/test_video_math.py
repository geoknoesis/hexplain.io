"""Public family validator rejects malformed quantities and preserves exact frame rates."""
import rdflib
from pyshacl import validate
import specgraph
prefix='@prefix v: <https://hexplain.io/ns/video#> . @prefix t: <https://hexplain.io/ns/aspect/time#> . '
bad=['v:frameRate -1','v:frameRate "banana"','v:aspectRatio "16:0"','v:aspectRatio "0:9"','t:duration -10','v:frameCount -1','v:frameCount 2.5','v:scanType <urn:invalid>','v:frameRateNumerator 30000','v:frameRateNumerator 30000 ; v:frameRateDenominator 0']
good=['v:frameRate 29.97','v:aspectRatio "16:9"','t:duration 0','v:frameCount 0','v:frameRateNumerator 30000 ; v:frameRateDenominator 1001']
for expected,cases in [(False,bad),(True,good)]:
 for case in cases:
  data=specgraph.ontologies();data.parse(data=prefix+'<urn:video> '+case+' .',format='turtle')
  result=validate(data,shacl_graph=specgraph.shapes(),advanced=True)
  assert result[0] == expected,(case,result[2])
assert 'specification/vdv/video.ttl' in specgraph.ontology_paths()
print('PASS: 15 video numeric/rational cases through the family validator')
