"""Run the BDDO + DLV + core SHACL shapes over every vocabulary fixture.

Convention: specification/<mod>/test/<feature>-valid.ttl must conform;
specification/<mod>/test/<feature>-invalid.ttl must NOT. Each -invalid file
carries an rdfs:comment naming the shape it is expected to trip.
"""
import glob
import os
import pathlib
import sys

import rdflib
from pyshacl import validate

CORE = [
    "specification/bddo/bddo.ttl",
    "specification/dlv/dlv.ttl",
    "specification/hexplain/core.ttl",
    # Aspect ontologies (and the geo vocabulary) declare the domain terms a fixture
    # targets with hexplain:mapsToProperty. Load them so fixtures reference the real
    # declarations instead of restating them locally.
    *sorted(glob.glob("specification/aspect/*/*.ttl")),
    "specification/gv/geo.ttl",
]


def load(paths):
    g = rdflib.Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g


def ontologies_for(fixture_path):
    """Core vocabularies plus the owning module's own vocabulary and shapes.

    A fixture lives at specification/<mod>/test/<feature>-{valid,invalid}.ttl.
    Some modules keep their SHACL beside the vocabulary (bddo.ttl); others put
    it in a sibling shapes.ttl (conf, req). Load whichever exist.
    """
    mod = pathlib.Path(fixture_path).parent.parent.name
    paths = list(CORE)
    for extra in (f"specification/{mod}/{mod}.ttl", f"specification/{mod}/shapes.ttl"):
        if os.path.exists(extra) and extra not in paths:
            paths.append(extra)
    return paths


fixtures = sorted(glob.glob("specification/*/test/*-valid.ttl")) + sorted(
    glob.glob("specification/*/test/*-invalid.ttl")
)
if not fixtures:
    sys.exit("FAIL: no fixtures found (wrong working directory?)")

failures = []
for path in fixtures:
    should_conform = path.endswith("-valid.ttl")
    ont = ontologies_for(path)
    data = load(ont + [path])
    shapes = load(ont)
    conforms, _, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    if conforms and not should_conform:
        failures.append(f"{path}: expected SHACL violation, but it conformed")
    elif not conforms and should_conform:
        failures.append(f"{path}: expected to conform, but did not:\n{report}")

if failures:
    print("FAIL:\n" + "\n".join(failures))
    sys.exit(1)
print(f"PASS: {len(fixtures)} vocabulary fixtures behave as expected")
