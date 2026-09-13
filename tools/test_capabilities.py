"""Capability claims must be regenerated from evidence, never asserted by hand."""
import json

from _capabilities import COVERAGE, EVIDENCE, ROOT, TARGET, build, digest

published = TARGET.read_text(encoding='utf-8')
assert published == build(), 'Regenerate specification/capabilities.json from current evidence'

matrix = json.loads(published)
assert matrix['schema_version'] == 1

# The matrix must describe exactly the modules the reference manifest documents.
reference = json.loads((ROOT/'specification/reference/manifest.json').read_text(encoding='utf-8'))
assert [m['module'] for m in matrix['modules']] == sorted(e['module'] for e in reference), 'Module set drifted'

# Recorded evidence must still exist and hash to the recorded value, so no capability
# outlives the measurement that produced it.
assert set(matrix['evidence']) == {p.relative_to(ROOT).as_posix() for p in EVIDENCE}
for relative, recorded in matrix['evidence'].items():
    assert digest(ROOT/relative) == recorded, f'{relative} changed since the matrix was generated'

for row in matrix['modules']:
    module = row['module']
    # An obligation without a two-sided witness would be validation capability that no
    # component evaluation supports.
    assert row['two_sided_obligations'] == row['constraint_obligations'], (
        f"{module}: {row['constraint_obligations'] - row['two_sided_obligations']} obligations lack two-sided evidence")
    assert row['exercised_resources'] <= row['traced_resources'], module
    assert row['resources_asserting_result_path'] <= row['traced_resources'], module
    if row['shapes']:
        assert row['constraint_obligations'] > 0, f'{module}: publishes shapes but has no measured obligation'

# Every measured obligation is attributed, either to a documented module or to a named
# non-module source. Evidence may not be silently dropped.
coverage = json.loads(COVERAGE.read_text(encoding='utf-8'))
attributed = sum(row['constraint_obligations'] for row in matrix['modules'])
unattributed = sum(matrix['unattributed_obligations'].values())
assert attributed + unattributed == len(coverage['constraints']) == matrix['totals']['measured_obligations'], (
    'Matrix loses measured obligations', attributed, unattributed, len(coverage['constraints']))

totals = matrix['totals']
assert totals['modules'] == len(matrix['modules'])
for field in ('terms', 'constraint_obligations', 'two_sided_obligations', 'traced_resources', 'exercised_resources'):
    assert totals[field] == sum(row[field] for row in matrix['modules']), field

print(f"PASS: {totals['modules']} modules; {totals['measured_obligations']} measured obligations all two-sided "
      f"({unattributed} outside documented modules); {totals['exercised_resources']} of {totals['traced_resources']} "
      f"resources exercised by a competency case")
