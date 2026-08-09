# tools/shacl_check.py — validate a Hexplain TTL against the family's SHACL shapes.
#
# The aspect vocabularies and every concept register are loaded as context. Register
# membership matters: hx-bundle constrains abnd:partRole to be skos:inScheme the register
# a profile binds, so without the registers in the data graph EVERY bundle profile fails
# with "not skos:inScheme the declared register" -- not because it is wrong, but because
# the concepts naming its parts were never loaded. Both shipped bundle profiles reported
# false failures this way before the registers were added here.
import glob
import sys
from rdflib import Graph
from pyshacl import validate

ONT = [
    "specification/bddo/bddo.ttl",
    "specification/dlv/dlv.ttl",
    "specification/hexplain/core.ttl",
    "specification/aspect/raster/raster.ttl",
    "specification/aspect/security/security.ttl",
    "specification/aspect/bundle/bundle.ttl",
    "specification/gv/geo.ttl",
    "specification/req/req.ttl",
] + sorted(glob.glob("specification/register/*/*.ttl"))
SHAPES = [
    "specification/bddo/bddo.ttl",
    "specification/hexplain/core.ttl",
    "specification/aspect/bundle/bundle.ttl",
    "specification/req/shapes.ttl",
]

def load(paths):
    g = Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g

def main(targets):
    data = load(ONT + list(targets))
    shapes = load(SHAPES)
    conforms, _, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    print(report)
    sys.exit(0 if conforms else 1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python tools/shacl_check.py <target.ttl> [more.ttl ...]")
        sys.exit(2)
    main(sys.argv[1:])
