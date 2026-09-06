"""Create a new, never-overwritten local draft snapshot with a pinned compatibility corpus."""
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from rdflib import Graph, OWL, RDF
import specgraph

ROOT = Path(__file__).resolve().parent.parent

def snapshot(release_id):
    assert re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}\.[1-9][0-9]*', release_id), 'Use YYYY-MM-DD.N'
    out = ROOT / 'releases' / release_id
    assert not out.exists(), 'Immutable snapshot already exists; choose a new revision'
    paths = specgraph.ontology_paths() + ['specification/validation/test/competency.tsv', 'specification/validation/test/layout-competency.tsv', 'specification/validation/test/security-competency.tsv', 'specification/validation/test/security-profile.ttl', 'specification/validation/test/geometry-competency.tsv']
    files = []
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            data = (ROOT / path).read_bytes()
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
            item = {'path': path, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
            if path.endswith('.ttl'):
                g = Graph().parse(data=data, format='turtle')
                item['ontologies'] = [{'iri': str(o), 'versionIri': str(g.value(o, OWL.versionIRI) or '')}
                    for o in sorted(g.subjects(RDF.type, OWL.Ontology), key=str)]
            files.append(item)
    binary = content.getvalue()
    manifest = {'schemaVersion': 1, 'releaseId': release_id, 'status': 'local working-draft snapshot',
        'archive': 'hexplain-spec.zip', 'sha256': hashlib.sha256(binary).hexdigest(),
        'entailment': 'none; SHACL subclass traversal over explicitly supplied vocabulary', 'files': files}
    out.mkdir(parents=True)
    (out / 'hexplain-spec.zip').write_bytes(binary)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(f'Created {release_id}: {len(files)} pinned files; local artifact, not a live namespace release')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('release_id')
    snapshot(parser.parse_args().release_id)
