"""Verify immutable archive bytes and replay their original corpus against archived/current shapes."""
import hashlib
import json
import zipfile
from pathlib import Path
from rdflib import Graph
import specgraph
from test_instance_contract import check_corpus

current_files = {p: Path(p).read_text(encoding='utf-8') for p in specgraph.ontology_paths()}
current = specgraph.ontologies()
releases = sorted(Path('releases').glob('*/manifest.json'))
assert releases, 'No pinned specification snapshot'
cases = 0
for path in releases:
    manifest = json.loads(path.read_text(encoding='utf-8'))
    assert manifest['releaseId'] == path.parent.name
    archive = path.parent / manifest['archive']
    assert archive.parent == path.parent and archive.name == 'hexplain-spec.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['sha256'], archive
    files = {}
    family = Graph()
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        assert sorted(z.namelist()) == sorted(f['path'] for f in manifest['files'])
        for item in manifest['files']:
            data = z.read(item['path'])
            assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], item['path']
            files[item['path']] = data.decode('utf-8')
            if item['path'].endswith('.ttl'):
                family.parse(data=data, format='turtle')
    corpus = files['specification/validation/test/competency.tsv']
    archived_count = check_corpus(family, files, corpus)
    assert check_corpus(current, current_files, corpus) == archived_count
    cases += archived_count
print(f'PASS: {len(releases)} immutable snapshot(s); {cases} archived/current compatibility cases replayed twice')
