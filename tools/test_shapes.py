"""Execute the bundle's SHACL (structural shapes + rule + conformance) against the
shapefile fixtures using a real engine. Optional formal gate: if pyshacl is not
installed, SKIP (exit 0) so the rdflib-only suite stays green; where pyshacl is
present this genuinely runs AssetShape, PartShape (incl. register membership),
and RequiredPartsShape.
"""
import sys
try:
    from pyshacl import validate
except ImportError:
    print("SKIP: pyshacl not installed (optional formal SHACL gate)")
    sys.exit(0)
import rdflib

SHAPES = "specification/aspect/bundle/bundle.ttl"
BASE = [
    SHAPES,
    "specification/aspect/geometry/geometry.ttl",
    "specification/aspect/spatialref/spatialref.ttl",
    "specification/aspect/tabular/tabular.ttl",
    "specification/aspect/fsmeta/fsmeta.ttl",
    "specification/profiles/shapefile/shapefile.ttl",
]

def conforms(instance):
    data = rdflib.Graph()
    for f in BASE + [instance]:
        data.parse(f, format="turtle")
    shapes = rdflib.Graph()
    shapes.parse(SHAPES, format="turtle")
    ok, _, text = validate(data, shacl_graph=shapes, advanced=True)
    return ok, text

valid_ok, valid_text = conforms("specification/profiles/shapefile/example.ttl")
invalid_ok, _ = conforms("specification/profiles/shapefile/example-invalid.ttl")

problems = []
if not valid_ok:
    problems.append("valid example.ttl did NOT conform:\n" + valid_text)
if invalid_ok:
    problems.append("invalid example-invalid.ttl unexpectedly conformed (required-parts not enforced)")

if problems:
    print("FAIL:\n" + "\n".join(problems))
    sys.exit(1)
print("PASS: valid fixture conforms; invalid fixture fails SHACL (structural + required-parts executed)")
