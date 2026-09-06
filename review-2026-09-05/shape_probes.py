from pathlib import Path
import sys, json
import rdflib
from pyshacl import validate
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import specgraph

prefix = '@prefix v: <https://hexplain.io/ns/video#> . @prefix t: <https://hexplain.io/ns/aspect/time#> . @prefix x: <http://www.w3.org/2001/XMLSchema#> . '
cases = {'negative_rate': 'v:frameRate -1', 'text_rate': 'v:frameRate "banana"', 'zero_ratio': 'v:frameRate 30 ; v:aspectRatio "16:0"', 'negative_duration': 'v:frameRate 30 ; t:duration -10', 'invalid_scan': 'v:frameRate 30 ; v:scanType <urn:invalid>'}
out = {}
for name, body in cases.items():
    data = rdflib.Graph().parse(data=prefix + '<urn:video> ' + body + ' .', format='turtle')
    direct = rdflib.Graph().parse('specification/vdv/video.ttl')
    out[name] = {'video_shapes_conforms': validate(data, shacl_graph=direct)[0], 'family_shapes_conforms': validate(data, shacl_graph=specgraph.shapes(), advanced=True)[0]}
print(json.dumps(out, indent=2))
