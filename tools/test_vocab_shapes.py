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
    # Concept registers too. A fixture naming a register concept -- a codec in an encoding
    # pipeline, a part role -- fails its shape's skos:Concept check when the register is
    # absent, reporting the fixture as broken when only the loader was. Same gap that
    # misfired repeatedly in shacl_check.py before it globbed.
    *sorted(glob.glob("specification/register/*/*.ttl")),
    "specification/gv/geo.ttl",
]


def load(paths):
    g = rdflib.Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g


def ontologies_for(fixture_path):
    """Core vocabularies plus the owning module's own vocabulary and shapes.

    A fixture lives in a `test/` directory beside the module it exercises, at either
    depth: specification/<mod>/test/ (bddo, dlv, conf, req) or
    specification/<group>/<mod>/test/ (aspect/bundle, profiles/nitf). Resolve against
    the module directory itself rather than assuming a depth, and load every .ttl
    beside it -- some modules keep their SHACL in the vocabulary file (bddo.ttl),
    others in a sibling shapes.ttl (conf, req).
    """
    mod_dir = pathlib.Path(fixture_path).parent.parent
    paths = list(CORE)
    for extra in sorted(mod_dir.glob("*.ttl")):
        s = extra.as_posix()
        if s not in paths:
            paths.append(s)
    return paths


# Two depths: specification/<mod>/test/ and specification/<group>/<mod>/test/. The
# one-level glob silently skipped every aspect and profile fixture -- they were written,
# committed and never run.
_PATTERNS = ("specification/*/test/", "specification/*/*/test/")
fixtures = sorted(
    f for pat in _PATTERNS for suffix in ("*-valid.ttl", "*-invalid.ttl")
    for f in glob.glob(pat + suffix)
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
