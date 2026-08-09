# tools/shacl_check.py — validate a Hexplain TTL against the family's SHACL shapes.
#
# The aspect vocabularies and every concept register are loaded as context. Register
# membership matters: hx-bundle constrains abnd:partRole to be skos:inScheme the register
# a profile binds, so without the registers in the data graph EVERY bundle profile fails
# with "not skos:inScheme the declared register" -- not because it is wrong, but because
# the concepts naming its parts were never loaded. Both shipped bundle profiles reported
# false failures this way before the registers were added here.
import sys
from pyshacl import validate

# Context and shapes both come from specgraph, so a newly added aspect or register is
# picked up here without anyone remembering to edit a list. See tools/specgraph.py for why.
import specgraph


def main(targets):
    data = specgraph.ontologies(targets)
    shapes = specgraph.shapes()
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
