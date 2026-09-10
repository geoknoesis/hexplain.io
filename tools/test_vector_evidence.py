"""Public fixture integrity only; actual independent decoder comparisons run in engine tests."""
from pathlib import Path
import base64, hashlib, json

root=Path(__file__).resolve().parents[1]
p=root/'specification/coverage/gdal-tests/vector-semantic-candidate.json'
oracle=json.loads(p.read_text(encoding='utf-8'))
assert len(oracle['cases'])==136
assert len({c['name'] for c in oracle['cases']})==136
assert sum(c['name'].startswith('boundary-') for c in oracle['cases'])==24
for c in oracle['cases']:
    raw=base64.b64decode(c['base64'],validate=True)
    assert hashlib.sha256(raw).hexdigest()==c['sha256'],c['name']
    assert raw[0] in (0,1)
    assert c['expected']['type'] in range(1,8)
    assert c['expected']['dimensions'] in ('XY','XYZ','XYM','XYZM')
package=oracle['geopackage']
assert hashlib.sha256(base64.b64decode(package['base64'],validate=True)).hexdigest()==package['sha256']
assert len(package['tables'])==4
assert sum(len(t['rows']) for t in package['tables'])==60
assert all(t['srs']==4326 for t in package['tables'])
print('PASS: 136 GDAL oracle geometries and 60 GeoPackage rows retain exact fixture hashes; decoder comparison is a separate engine test')
