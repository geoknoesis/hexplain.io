"""The 2026-09-24 review's mutation probes, as module contracts.

tools/_review_mutation_cases.py holds one conforming graph and its mutations per defect the review
found. The probes whose shapes live in one family module and need no SHACL-AF feature are also
module contracts: they are the two-sided evidence of the constraints the review added
(tools/_constraint_coverage.py), and a validator that reads family-contracts.json runs them too.
The probes of shapes activated by a SPARQL-based target (register bindings, deprecated register
values) are vocabulary fixtures instead (specification/hexplain/test/register-*.ttl), which
the family's SHACL-AF gates run, and the strict-profile probes validate an optional profile that
is not a family module.
"""
from _review_mutation_cases import cases as probes

SPARQL_TARGETED = {"register binding"}


def cases():
    rows = []
    for probe in probes():
        if probe["group"] in SPARQL_TARGETED or probe["group"] == "strict profile" or probe.get("severity"):
            continue
        rows.append(dict(name=f"review {probe['group']}: {probe['name']}", module=probe["shapes"][0],
                         data=probe["data"], expected=probe["conforms"], path=""))
    return rows
