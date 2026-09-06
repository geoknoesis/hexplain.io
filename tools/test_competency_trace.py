"""Require the published traceability matrix to match retained corpus bytes."""
from _competency_trace import build, OUT
expected_json,expected_html=build()
assert (OUT/'competency-trace.json').read_text(encoding='utf-8')==expected_json
assert (OUT/'competency-trace.html').read_text(encoding='utf-8')==expected_html
print('PASS: competency traceability references, result paths and corpus hashes match generated artifacts')
