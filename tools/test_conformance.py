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
    "specification/profiles/shapefile/shapefile.ttl",
]

# Grab the authored SELECT from the constraint.
gb = rdflib.Graph()
for f in BASE:
    gb.parse(f, format="turtle")
select = None
for _, _, q in gb.triples((None, SH.select, None)):
    select = str(q)
if select is None:
    print("FAIL: no sh:select constraint found in bundle.ttl")
    sys.exit(1)

def violations(instance_file):
    g = rdflib.Graph()
    for f in BASE + [instance_file]:
        g.parse(f, format="turtle")
    return list(g.query(select))

valid = violations("specification/profiles/shapefile/example.ttl")
invalid = violations("specification/profiles/shapefile/example-invalid.ttl")

if valid:
    print("FAIL: valid instance reported violations:", valid)
    sys.exit(1)
if not invalid:
    print("FAIL: invalid instance (missing .shp) reported no violation")
    sys.exit(1)
print(f"PASS: valid=0 violations, invalid={len(invalid)} violation(s)")
