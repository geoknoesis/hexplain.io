"""Audit the pinned documentation denominator and evidence requirements offline."""
import json,re
from collections import Counter
from pathlib import Path
p=Path('specification/coverage/gdal-drivers.json');d=json.loads(p.read_text(encoding='utf-8'))
rows=d['drivers'];keys=[r['key'] for r in rows]
assert len(keys)==len(set(keys)) and len(keys)>200
counts=Counter(r['kind'] for r in rows)
for s in d['sources']:
    kind=s['url'].split('/')[-2]
    assert s['document_pages']==counts[kind]
for r in rows:
    assert '/'+d['gdal_release']+'/' in r['source']
    assert re.fullmatch('[0-9a-f]{64}',r['sha256'])
    assert r['assessment'] in ['not-runtime-verified','runtime-verified']
    if r['assessment']=='runtime-verified':
        assert r.get('evidence'),r['key']
        for path in r['evidence']:assert Path(path).is_file(),path
assert {'raster:gtiff','raster:nitf','raster:hdf5','raster:netcdf','raster:zarr','vector:gpkg','vector:parquet','vector:flatgeobuf'}.issubset(keys)
print(f'PASS: {len(rows)} uniquely keyed GDAL documentation pages ({dict(counts)}); pinned sources and evidence policy valid')
