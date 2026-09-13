"""Derive what each specification module demonstrably supports, from retained evidence.

Every field here is read from an evidence artifact that a gate produces: documented terms
and shapes from the reference manifest, constraint obligations and their two-sided results
from the coverage ledger, and corpus exercise from the competency trace. Nothing in the
generated matrix is asserted by hand, so a capability cannot be claimed without the
evidence that establishes it.

Exercise is deliberately reported as a count rather than a verdict. A module whose terms
are never referenced by a competency case is described and constrained but not exercised,
and that distinction is the point of the matrix.
"""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT/'specification/capabilities.json'

# Evidence artifacts, each produced by a gate in this repository.
REFERENCE = ROOT/'specification/reference/manifest.json'
COVERAGE = ROOT/'specification/validation/constraint-coverage.json'
COMPETENCY = ROOT/'specification/validation/competency-trace.json'
EVIDENCE = (REFERENCE, COVERAGE, COMPETENCY)


def digest(path):
    return hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def module_of(source):
    """Owning module directory of a specification source path."""
    return str(Path(source).parent).replace('\\', '/')


def build():
    reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
    coverage = json.loads(COVERAGE.read_text(encoding='utf-8'))
    competency = json.loads(COMPETENCY.read_text(encoding='utf-8'))

    obligations = defaultdict(int)
    two_sided = defaultdict(int)
    for constraint in coverage['constraints']:
        module = module_of(constraint['source'])
        obligations[module] += 1
        two_sided[module] += bool(constraint['two_sided_evaluation'])

    described = defaultdict(int)
    exercised = defaultdict(int)
    with_result_path = defaultdict(int)
    for resource in competency['resources']:
        module = resource['module']
        described[module] += 1
        exercised[module] += bool(resource['positive'] or resource['negative'])
        with_result_path[module] += bool(resource['result_path'])

    modules = []
    for entry in sorted(reference, key=lambda e: e['module']):
        module = entry['module']
        modules.append(dict(
            module=module,
            terms=entry['terms'],
            shapes=entry['shapes'],
            constraint_obligations=obligations.get(module, 0),
            two_sided_obligations=two_sided.get(module, 0),
            traced_resources=described.get(module, 0),
            exercised_resources=exercised.get(module, 0),
            resources_asserting_result_path=with_result_path.get(module, 0),
        ))

    # Obligations measured against sources that are not documented modules (validation
    # fixtures, for example) are counted rather than dropped, so the matrix accounts for
    # every measured obligation in the ledger.
    documented = {entry['module'] for entry in reference}
    unattributed = {module: count for module, count in sorted(obligations.items()) if module not in documented}

    matrix = dict(
        schema_version=1,
        scope=('Per-module capability derived from retained evidence. Obligations are SHACL '
               'constraint components measured with two-sided witnesses; exercise counts '
               'resources referenced by a competency case. Counts describe the declared '
               'corpora only and are not proof of complete semantic coverage.'),
        validator=coverage['validator'],
        evidence={path.relative_to(ROOT).as_posix(): digest(path) for path in EVIDENCE},
        unattributed_obligations=unattributed,
        totals=dict(
            modules=len(modules),
            measured_obligations=len(coverage['constraints']),
            terms=sum(m['terms'] for m in modules),
            constraint_obligations=sum(m['constraint_obligations'] for m in modules),
            two_sided_obligations=sum(m['two_sided_obligations'] for m in modules),
            exercised_resources=sum(m['exercised_resources'] for m in modules),
            traced_resources=sum(m['traced_resources'] for m in modules),
        ),
        modules=modules,
    )
    return json.dumps(matrix, indent=2)+'\n'


if __name__ == '__main__':
    TARGET.write_text(build(), encoding='utf-8')
    print(json.loads(TARGET.read_text(encoding='utf-8'))['totals'])
