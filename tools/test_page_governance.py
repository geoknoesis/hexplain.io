"""No published page is unchecked, and restated counts match their authority."""
from _page_governance import QUANTITIES, problems, registered_pages

found = problems()
assert not found, 'Page governance failures:\n  ' + '\n  '.join(found)

declared = registered_pages()
current = sum(1 for e in declared.values() if e['status'] == 'current')
historical = len(declared) - current
assert current and historical, 'Both current and historical pages must be represented'

# The contracts must be live: each quantity has to resolve to a real value.
for name, (_, authority) in sorted(QUANTITIES.items()):
    value = authority()
    assert isinstance(value, int) and value > 0, f'{name} authority produced {value!r}'

print(f'PASS: {len(declared)} published pages registered ({current} current, {historical} historical); '
      f'{len(QUANTITIES)} shared quantities match their authority')
