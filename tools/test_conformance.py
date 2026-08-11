"""Verify the required-parts conformance constraint.
Extracts the authored sh:select from bundle.ttl and runs it over each instance:
the valid roads.* yields zero violation rows; the .shp-less instance yields >=1.
rdflib only.
"""
import sys
import rdflib

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
BASE = [
    "specification/aspect/bundle/bundle.ttl",
    "specification/aspect/bundle/example/grid-pair-profile.ttl",
]

# Grab the authored SELECT from the required-parts constraint SPECIFICALLY. Taking
# whichever sh:select turned up last worked only while bundle.ttl held exactly one; it
# now has several (PartSpecShape adds its own), and RDF iteration order is arbitrary, so
# the test silently began validating an unrelated constraint and passed the invalid
# fixture. Navigate from the named shape instead.
ABND = rdflib.Namespace("https://hexplain.io/ns/aspect/bundle#")
gb = rdflib.Graph()
for f in BASE:
    gb.parse(f, format="turtle")
select = None
for constraint in gb.objects(ABND.RequiredPartsShape, SH.sparql):
    for q in gb.objects(constraint, SH.select):
        select = str(q)
if select is None:
    print("FAIL: no sh:select found on abnd:RequiredPartsShape")
    sys.exit(1)

def violations(instance_file):
    g = rdflib.Graph()
    for f in BASE + [instance_file]:
        g.parse(f, format="turtle")
    return list(g.query(select))

valid = violations("specification/aspect/bundle/example/bundle-example.ttl")
invalid = violations("specification/aspect/bundle/example/bundle-example-invalid.ttl")

if valid:
    print("FAIL: valid instance reported violations:", valid)
    sys.exit(1)
if not invalid:
    print("FAIL: invalid instance (missing the required .grd part) reported no violation")
    sys.exit(1)
print(f"PASS: valid=0 violations, invalid={len(invalid)} violation(s)")
