# tools/shacl_check.py — validate a Hexplain TTL against bddo + core SHACL shapes.
import sys
from rdflib import Graph
from pyshacl import validate

ONT = [
    "specification/bddo/bddo.ttl",
    "specification/dlv/dlv.ttl",
    "specification/hexplain/core.ttl",
    "specification/aspect/raster/raster.ttl",
    "specification/aspect/security/security.ttl",
    "specification/gv/geo.ttl",
]
SHAPES = [
    "specification/bddo/bddo.ttl",
    "specification/hexplain/core.ttl",
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
