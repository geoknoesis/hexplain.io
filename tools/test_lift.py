"""Verify the bundle lift rule projects part aspect facets onto the Asset.
Extracts the authored sh:construct query from bundle.ttl and runs it over the
composed graph (bundle + referenced aspects + shapefile profile + instance),
so the test exercises the real normative query. rdflib only; no pyshacl needed.
"""
import sys
import glob

import rdflib

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
FILES = [
    "specification/bddo/bddo.ttl",
    "specification/hexplain/core.ttl",
    "specification/aspect/bundle/bundle.ttl",
    "specification/aspect/bundle/example/grid-pair-profile.ttl",
    # EVERY aspect and register, not a hand-picked few. The lift rule fires when a property's
    # rdfs:isDefinedBy equals a spec's carriesAspect, so an aspect that is not loaded makes its
    # facets SILENTLY not lift -- indistinguishable from a rule that does not work. The list
    # here was chosen for the Shapefile example and did not include hx-raster, which is exactly
    # how the synthetic replacement first appeared to fail.
    *sorted(glob.glob("specification/aspect/*/*.ttl")),
    *sorted(glob.glob("specification/register/*/*.ttl")),
    # The instance being lifted onto.
    "specification/aspect/bundle/example/bundle-example.ttl",
]

g = rdflib.Graph()
for f in FILES:
    g.parse(f, format="turtle")

# Pull the authored CONSTRUCT text out of the lift rule.
construct = None
for _, _, q in g.triples((None, SH.construct, None)):
    construct = str(q)
if construct is None:
    print("FAIL: no sh:construct rule found in bundle.ttl")
    sys.exit(1)

# Apply the rule: run the CONSTRUCT and merge results back in ($this acts as a free var).
for triple in g.query(construct):
    g.add(triple)

asset = rdflib.URIRef("https://example.org/spec/bundle#sample")
ASREF = rdflib.Namespace("https://hexplain.io/ns/aspect/spatialref#")
ARASTER = rdflib.Namespace("https://hexplain.io/ns/aspect/raster#")
# The geometry-type register (see FILES above): ageom:geometryType is still the aspect

# Compare by value, not by exact typed literal: the fixtures use bare integer
# literals (rdflib types them xsd:integer) while the source properties declare
# narrower ranges, so an exact-datatype match would give a false FAIL. Numeric
# value comparison is the robust check that the facet lifted.
def lifted_int(pred):
    v = g.value(asset, pred)
    return None if v is None else int(v.toPython())

problems = []
if lifted_int(ARASTER.width) != 256:
    problems.append("araster:width 256 not lifted from the .grd part")
if lifted_int(ARASTER.height) != 256:
    problems.append("araster:height 256 not lifted from the .grd part")
if lifted_int(ASREF.epsgCode) != 4326:
    problems.append("asref:epsgCode 4326 not lifted from the .wld part")

# Negative: fsmeta filename must NOT lift (no PartSpec declares afs as a carried aspect).
AFS = rdflib.Namespace("https://hexplain.io/ns/aspect/fsmeta#")
leaked = list(g.triples((asset, AFS.fileName, None)))

if problems:
    print("FAIL: not lifted onto Asset:", problems)
    sys.exit(1)
if leaked:
    print("FAIL: physical afs:fileName leaked onto Asset:", leaked)
    sys.exit(1)
print("PASS: aspect facets lifted onto Asset; physical properties did not leak")
