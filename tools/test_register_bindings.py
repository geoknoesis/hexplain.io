"""hexplain:usesRegister must be enforced: a value outside the declared register FAILS.

Mirrors tools/test_shapes.py's optional-pyshacl skip so the rdflib-only suite stays green.
"""
import sys
try:
    from pyshacl import validate
except ImportError:
    print("SKIP: pyshacl not installed (optional formal SHACL gate)")
    sys.exit(0)

import rdflib

shapes = rdflib.Graph()
shapes.parse("specification/hexplain/core.ttl", format="turtle")

def conforms(path):
    data = rdflib.Graph()
    data.parse(path, format="turtle")
    ok, _, text = validate(data, shacl_graph=shapes, advanced=True)
    return ok, text

valid_ok, valid_text = conforms("specification/hexplain/test/register-binding-valid.ttl")
invalid_ok, _ = conforms("specification/hexplain/test/register-binding-invalid.ttl")

problems = []
if not valid_ok:
    problems.append("value inside the declared register did NOT conform:\n" + valid_text)
if invalid_ok:
    problems.append("value OUTSIDE the declared register conformed (binding not enforced)")
if problems:
    print("FAIL:\n" + "\n".join(problems))
    sys.exit(1)
print("PASS: register bindings enforced (in-register conforms, out-of-register rejected)")
