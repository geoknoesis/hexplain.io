"""Verify immutable archive bytes and replay their original corpus against archived/current shapes."""
import argparse
import base64
from pyshacl import validate
from rdflib import Namespace, URIRef
import hashlib
import json
import zipfile
from pathlib import Path
from rdflib import Graph
import specgraph
from test_instance_contract import check_corpus

current_files = {p: Path(p).read_text(encoding='utf-8') for p in specgraph.ontology_paths()}
current = specgraph.ontologies()
parser=argparse.ArgumentParser()
parser.add_argument('--release', help='Replay only this existing release identifier')
args=parser.parse_args()
releases = sorted(Path('releases').glob('*/manifest.json'))
if args.release: releases=[p for p in releases if p.parent.name==args.release]
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
    for corpus_name, shape_paths in [
        ('layout-competency.tsv',['specification/dlv/dlv.ttl','specification/aspect/bundle/bundle.ttl']),
        ('security-competency.tsv',['specification/validation/test/security-profile.ttl']),
        ('geometry-competency.tsv',['specification/aspect/geometry/geometry.ttl'])]:
        corpus_path='specification/validation/test/'+corpus_name
        if corpus_path not in files: continue  # Older immutable releases predate these suites.
        for archived in [True,False]:
            selected=Graph()
            for shape_path in shape_paths:
                selected.parse(data=files[shape_path] if archived else Path(shape_path).read_text(encoding='utf-8'),format='turtle')
            for row in files[corpus_path].splitlines():
                if not row or row.startswith('#'):continue
                name,expected,result_path,encoded=row.split('\t')
                ok,report,detail=validate(Graph().parse(data=base64.b64decode(encoded).decode(),format='turtle'),shacl_graph=selected,inference='none',advanced=False)
                assert bool(ok)==(expected=='true'),(path,name,archived,detail)
                if result_path:assert URIRef(result_path) in report.objects(None,Namespace('http://www.w3.org/ns/shacl#').resultPath),(name,detail)
        cases += sum(bool(row) and not row.startswith('#') for row in files[corpus_path].splitlines())
print(f'PASS: {len(releases)} immutable snapshot(s); {cases} archived/current compatibility cases replayed twice')
