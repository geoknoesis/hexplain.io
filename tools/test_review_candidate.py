"""Reject stale scope, altered package bytes and non-reproducible review artifacts."""
import io, json, hashlib, zipfile
from _review_candidate import OUT, build

manifest, audit, binary = build()
actual = json.loads((OUT/'review-manifest.json').read_text(encoding='utf-8'))
# Review decisions may be added without changing the frozen artifact inventory.
# This validates record completeness only, never the identity/independence of a signer.
review_fields = {'status', 'reviewer', 'reviewed_at', 'decision', 'module_reviews'}
assert {k:v for k,v in actual.items() if k not in review_fields} == {k:v for k,v in manifest.items() if k not in review_fields}, 'Review candidate metadata is stale; regenerate the pending package'
assert [(m['module'],m['resources']) for m in actual['module_reviews']] == [(m['module'],m['resources']) for m in manifest['module_reviews']]
if actual['decision'] is None:
    assert actual['status'] == 'awaiting independent review'
else:
    assert actual['decision'] in ('accepted','rejected','changes requested')
    assert isinstance(actual['reviewer'],str) and actual['reviewer'].strip()
    assert actual['reviewed_at']
    assert all(m['status'] != 'unreviewed' for m in actual['module_reviews'])
assert json.loads((OUT/'constraint-inventory.json').read_text(encoding='utf-8')) == audit
assert (OUT/'ontology-review-candidate.zip').read_bytes() == binary, 'Archive differs from current source'
with zipfile.ZipFile(io.BytesIO(binary)) as z:
    assert all(item.create_system == 3 for item in z.infolist()), 'Archive creator metadata must be platform-independent'
    assert len(z.namelist()) == len(set(z.namelist())) == len(manifest['files'])
    for item in manifest['files']:
        data = z.read(item['path'])
        assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
assert build()[2] == binary, 'Candidate build is not deterministic'
print(f"PASS: reproducible {len(manifest['files'])}-file review candidate, {manifest['resources']} resources; review decision: {actual['decision'] or 'pending'} (identity is not authenticated by this gate)")
