"""Verify the bundle lift rule projects part aspect facets onto the Asset.
Extracts the authored sh:construct query from bundle.ttl and runs it over the
composed graph (bundle + referenced aspects + shapefile profile + instance),
so the test exercises the real normative query. rdflib only; no pyshacl needed.
"""
import sys
import rdflib

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
FILES = [
    "specification/aspect/bundle/bundle.ttl",
    "specification/aspect/geometry/geometry.ttl",
    "specification/aspect/spatialref/spatialref.ttl",
    "specification/aspect/tabular/tabular.ttl",
    "specification/aspect/fsmeta/fsmeta.ttl",
    # Register document: the geometry-type CONCEPT the .shp part's ageom:geometryType
    # points at (rgeo:MultiLineString) was split out of the geometry aspect into this
    # standalone, swappable register (pluggable-concept-registers migration, Task 3) --
    # mirrors what that same task did to tools/test_shapes.py's BASE list.
    "specification/register/geometry-type/geometry-type.ttl",
    "specification/profiles/shapefile/shapefile.ttl",
    "specification/profiles/shapefile/example.ttl",
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

roads = rdflib.URIRef("https://example.org/data/roads")
AGEOM = rdflib.Namespace("https://hexplain.io/ns/aspect/geometry#")
ASREF = rdflib.Namespace("https://hexplain.io/ns/aspect/spatialref#")
ATAB = rdflib.Namespace("https://hexplain.io/ns/aspect/tabular#")
# The geometry-type register (see FILES above): ageom:geometryType is still the aspect
# PROPERTY, but the CONCEPT it points at now lives here, not in AGEOM.
RGEO = rdflib.Namespace("https://hexplain.io/ns/register/geometry-type#")

# Compare by value, not by exact typed literal: the fixtures use bare integer
# literals (rdflib types them xsd:integer) while the source properties declare
# narrower ranges, so an exact-datatype match would give a false FAIL. Numeric
# value comparison is the robust check that the facet lifted.
def lifted_int(pred):
    v = g.value(roads, pred)
    return None if v is None else int(v.toPython())

problems = []
if (roads, AGEOM.geometryType, RGEO.MultiLineString) not in g:  # object is a URI — exact match is fine
    problems.append("ageom:geometryType rgeo:MultiLineString not lifted from .shp")
if lifted_int(ASREF.epsgCode) != 4326:
    problems.append("asref:epsgCode 4326 not lifted from .prj")
if lifted_int(ATAB.rowCount) != 1200:
    problems.append("atab:rowCount 1200 not lifted from .dbf")

# Negative: fsmeta filename must NOT lift (no PartSpec declares afs as a carried aspect).
AFS = rdflib.Namespace("https://hexplain.io/ns/aspect/fsmeta#")
leaked = list(g.triples((roads, AFS.fileName, None)))

if problems:
    print("FAIL: not lifted onto Asset:", problems)
    sys.exit(1)
if leaked:
    print("FAIL: physical afs:fileName leaked onto Asset:", leaked)
    sys.exit(1)
print("PASS: aspect facets lifted onto Asset; physical properties did not leak")
