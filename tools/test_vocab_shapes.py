"""Run the BDDO + DLV + core SHACL shapes over every vocabulary fixture.

Convention: specification/<mod>/test/<feature>-valid.ttl must conform;
specification/<mod>/test/<feature>-invalid.ttl must NOT. Each -invalid file
carries an rdfs:comment naming the shape it is expected to trip.
"""
import glob
import pathlib
import sys

from pyshacl import validate

import specgraph

# Every vocabulary, aspect and register in the family. A fixture targets aspect properties
# with hexplain:mapsToProperty and names register concepts (a codec in an encoding pipeline,
# a part role); when the term's home ontology is missing the shape reports the FIXTURE as
# broken. specgraph globs, so a new aspect or register is context here the moment it lands.
CORE = specgraph.ontology_paths()

load = specgraph.load


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
