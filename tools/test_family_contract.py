"""Module-scoped positive/value/cardinality contracts, also consumed by Jena.

Each case validates one small data graph against one module's shapes and is independent of
every other case, so the cases are checked across worker processes. Verdicts, result paths
and source shapes are collected and reported in authored order, which keeps a failure
message identical to the sequential form regardless of completion order.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from pyshacl import validate

from _family_contract_cases import cases

ROOT = Path(__file__).resolve().parents[1]
SH = Namespace('http://www.w3.org/ns/shacl#')

# Cases per task. Large enough to amortise parsing a module's shapes, small enough that the
# few very expensive cases spread across workers instead of serialising behind one another.
CHUNK = 24


def workers():
    """Bounded by default: an earlier concurrent run exhausted host memory."""
    requested = os.environ.get('HEXPLAIN_GATE_WORKERS')
    if requested:
        count = int(requested)
        if count < 1:
            raise ValueError('HEXPLAIN_GATE_WORKERS must be at least 1')
        return count
    return max(1, min(os.cpu_count() or 1, 8))


def check(task):
    """Validate one module's chunk, returning (index, name, reason) for each failure."""
    module, items = task
    shapes = Graph().parse(ROOT/module)
    failures = []
    for index, row in items:
        selected = shapes
        if row.get('targetShape'):
            selected = Graph()+shapes
            selected.add((URIRef(row['targetShape']), SH.targetNode, URIRef(row['targetNode'])))
        ok, report, detail = validate(Graph().parse(data=row['data'], format='turtle'),
                                      shacl_graph=selected, inference='none')
        if bool(ok) != row['expected']:
            failures.append((index, row['name'], f'expected conforms={row["expected"]}', detail))
            continue
        if row['path'] and URIRef(row['path']) not in report.objects(None, SH.resultPath):
            failures.append((index, row['name'], f'missing result path {row["path"]}', detail))
            continue
        if row.get('expectedShape') and URIRef(row['expectedShape']) not in report.objects(None, SH.sourceShape):
            failures.append((index, row['name'], f'missing source shape {row["expectedShape"]}', detail))
    return failures


def tasks(rows):
    grouped = {}
    for index, row in enumerate(rows):
        grouped.setdefault(row['module'], []).append((index, row))
    for module, items in grouped.items():
        for start in range(0, len(items), CHUNK):
            yield module, items[start:start+CHUNK]


def main():
    rows = cases()
    assert len({row['name'] for row in rows}) == len(rows), 'Case names must be unique evidence identifiers'

    queue = list(tasks(rows))
    parallel = workers()
    failures = []
    completed = 0
    print(f'Validating {len(rows)} family contracts in {len(queue)} tasks across {parallel} worker(s)', flush=True)
    with ProcessPoolExecutor(max_workers=parallel) as pool:
        for result in pool.map(check, queue):
            failures.extend(result)
            completed += 1
            if completed % 10 == 0:
                print(f'Completed {completed}/{len(queue)} family-contract tasks', flush=True)
    failures.sort()
    assert not failures, 'Family contract failures:\n' + '\n'.join(
        f'  {name}: {reason}\n{detail}' for _, name, reason, detail in failures[:5])

    p = ROOT/'specification/validation/test/family-contracts.json'
    # RDF blank-node identifiers are immaterial; compare graphs when checking retained cases.
    if '--write' in sys.argv:
        p.write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
    else:
        from rdflib.compare import isomorphic
        retained = json.loads(p.read_text(encoding='utf-8'))
        assert len(rows) == len(retained)
        for a, b in zip(rows, retained, strict=True):
            assert {k: v for k, v in a.items() if k != 'data'} == {k: v for k, v in b.items() if k != 'data'}
            assert isomorphic(Graph().parse(data=a['data'], format='turtle'),
                              Graph().parse(data=b['data'], format='turtle'))
    print(f'PASS: {len(rows)} authored module contracts with result-path assertions')


if __name__ == '__main__':
    main()
