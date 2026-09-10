"""Rebuild a deterministic review package; never manufactures reviewer acceptance."""
from pathlib import Path
import hashlib, io, json, zipfile
from rdflib import Graph, Namespace, URIRef
import specgraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'specification/ontology-review'
SH = Namespace('http://www.w3.org/ns/shacl#')

def text_bytes(path):
    return (ROOT / path).read_text(encoding='utf-8').encode('utf-8')

def build():
    modules = json.loads(text_bytes('specification/reference/manifest.json'))
    trace = json.loads(text_bytes('specification/validation/competency-trace.json'))
    refs = {r['iri']: r for r in trace['resources']}
    requirements = []
    for path in sorted(specgraph.ontology_paths()):
        graph = Graph().parse(data=text_bytes(path), format='turtle')
        for shape in sorted(set(graph.subjects(None, SH.NodeShape)), key=str):
            if not isinstance(shape, URIRef):
                continue
            paths = sorted({str(p) for prop in graph.objects(shape, SH.property)
                            for p in graph.objects(prop, SH.path) if isinstance(p, URIRef)})
            requirements.append(dict(shape=str(shape), source=path,
                targets=sorted(str(o) for pred in [SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf]
                               for o in graph.objects(shape, pred)),
                direct_property_paths=paths,
                candidate_cases=sorted({c for p in paths for c in refs.get(p, {}).get('positive', []) + refs.get(p, {}).get('negative', [])}),
                review_status='needs constraint-level review'))
    audit = dict(scope='Named node-shape inventory. Direct path references are discovery aids, not proof of activation or constraint coverage. Nested paths, SPARQL and ontology axioms require manual review.',
                 resources=trace['summary']['resources'], shapes=requirements)
    payload = {}
    paths = set(specgraph.ontology_paths())
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'specification/validation/test').glob('*') if p.is_file())
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'tools').glob('*.py'))
    paths.update(m['page'] for m in modules)
    paths.update(['requirements.txt', 'specification/reference/manifest.json',
                  'specification/validation/competency-trace.json',
                  'specification/validation/constraint-coverage.json',
                  'specification/ontology-review/review-instructions.md',
                  'specification/ontology-review/governance.md',
                  'specification/ontology-review/candidate-migration.md',
                  'specification/coverage/gdal-tests/vector-semantic-candidate.json'])
    for path in sorted(paths):
        payload[path] = text_bytes(path)
    payload['specification/ontology-review/constraint-inventory.json'] = (json.dumps(audit, indent=2)+'\n').encode()
    content = io.BytesIO()
    with zipfile.ZipFile(content, 'w', compression=zipfile.ZIP_STORED) as archive:
        for path, data in sorted(payload.items()):
            info = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    binary = content.getvalue()
    manifest = dict(status='awaiting independent review', reviewer=None, reviewed_at=None, decision=None,
        resources=sum(m['terms'] for m in modules), modules=len(modules),
        hash_policy='SHA-256 of exact archive entry bytes; source UTF-8 text normalized to LF before packaging. Historical release archives are unchanged.',
        archive='ontology-review-candidate.zip', archive_sha256=hashlib.sha256(binary).hexdigest(),
        scope='Canonical ontologies, shapes, generated module documentation, validation fixtures and offline gate tools. Not a signed release or independent acceptance.',
        module_reviews=[dict(module=m['module'],resources=m['terms'],status='unreviewed') for m in modules],
        files=[dict(path=p,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()) for p,b in sorted(payload.items())])
    return manifest, audit, binary

if __name__ == '__main__':
    manifest, audit, binary = build()
    old = json.loads((OUT/'review-manifest.json').read_text(encoding='utf-8'))
    if old.get('reviewer') or old.get('decision'):
        raise SystemExit('Preserve the attributable review before creating a different candidate.')
    (OUT/'review-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (OUT/'constraint-inventory.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    (OUT/'ontology-review-candidate.zip').write_bytes(binary)
    print(f"Prepared {manifest['resources']} resources, {len(manifest['files'])} files; independent acceptance pending")
