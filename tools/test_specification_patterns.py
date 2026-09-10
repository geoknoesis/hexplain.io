"""Authoring expansion must be deterministic, complete and fail closed."""
from copy import deepcopy
from _expand_specification_patterns import load_catalogs, outputs, render, run, within, AUTHORING

manifest, constraints, datatypes = load_catalogs()
assert outputs() == outputs()
count, changed = run()
assert changed == 0
used_constraints, used_types = set(), set()
from _expand_specification_patterns import TOKEN
for source in manifest['templates'].values():
    for kind, name in TOKEN.findall(within(AUTHORING, source).read_text(encoding='utf-8')):
        (used_constraints if kind == 'constraint' else used_types).add(name)
assert used_constraints == set(constraints)
assert used_types == set(datatypes['presets'])

def rejects(action):
    try:
        action()
    except (ValueError, KeyError):
        return
    raise AssertionError('Invalid authoring input was accepted')

rejects(lambda: render('{{constraint:missing}}', constraints, datatypes))
rejects(lambda: render('{{unknown:thing}}', constraints, datatypes))
rejects(lambda: render('{{constraint:oops', constraints, datatypes))
rejects(lambda: within(AUTHORING, '../../outside'))
name = next(iter(datatypes['presets']))
broken = deepcopy(datatypes); broken['presets'][name]['unexpected'] = 'value'
rejects(lambda: render('{{datatype:' + name + '}}', constraints, broken))
broken = deepcopy(datatypes); del broken['presets'][name]['width']
rejects(lambda: render('{{datatype:' + name + '}}', constraints, broken))
print(f'PASS: {count} templates, {len(constraints)} shared constraints, {len(used_types)} presets; deterministic and invalid inputs rejected')

from _build_authoring_inventory import build
build(check=True)
