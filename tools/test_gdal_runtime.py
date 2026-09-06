"""Validate the published evidence denominator, provenance and non-inflated outcome counts."""
from pathlib import Path
from collections import Counter
import hashlib,json

root=Path('specification/coverage/gdal-tests')
evidence=json.loads((root/'evidence.json').read_text())
manifest=json.loads((root/'corpus-manifest.json').read_text())
inventory=json.loads(Path('specification/coverage/gdal-drivers.json').read_text())
assert hashlib.sha256((root/'corpus-manifest.json').read_bytes()).hexdigest()==evidence['manifest_sha256']
assert evidence['corpus_commit']==manifest['commit']==evidence['runtime']['fixture_commit']
assert len(manifest['files'])==evidence['corpus_files']
assert sum(f['bytes'] for f in manifest['files'])==evidence['corpus_bytes']
assert len({f['path'] for f in manifest['files']})==len(manifest['files'])
assert {r['key'] for r in evidence['inventory']}=={r['key'] for r in inventory['drivers']}
assert dict(Counter(r['status'] for r in evidence['all_results']))==evidence['counts']
assert evidence['counts'].get('mismatch',0)==0
assert evidence['counts'].get('documented-type-difference',0)==1
assert all(x['status']=='equal' for x in evidence['encoder_checks']) and len(evidence['encoder_checks'])==3
paths={f['path']:f for f in manifest['files']}
for row in evidence['inventory']:
    assert dict(Counter(r['status'] for r in row['samples']))==row['counts']
    for sample in row['samples']:
        assert sample['gdal_driver'] in row['runtime_drivers']
        if sample['source']: assert sample['source']==paths[sample['path']]
print(f"PASS: {len(evidence['inventory'])} GDAL documentation entries, {len(evidence['all_results'])} probes, {evidence['counts']['equal']} full-pixel matches; non-passes remain explicit")

extended=json.loads((root/'extended-evidence.json').read_text(encoding='utf-8'))
assert extended['counts']==evidence['counts']
assert sum(t['tests'] for t in extended['tests'])==33
assert len(extended['contracts'])==8
assert len(extended['retained_tiff_rejections'])==11
assert all(c[k] for c in extended['contracts'] for k in ['name','implementation','scope','range','evidence','limits'])
engine=Path('../hexplain-tools')
for name,digest in extended['sources'].items():
    assert hashlib.sha256((engine/name).read_bytes()).hexdigest()==digest, name
assert 'NOT a GDAL' in Path('../hexplain-tools/adapters/src/test/resources/extended-vectors.json').read_text(encoding='utf-8')
print('PASS: 8 scoped adapter contracts, 33 tests, source hashes and separate companion evidence')
