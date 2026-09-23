"""Run the BDDO + DLV + core SHACL shapes over every vocabulary fixture.

Convention: specification/<mod>/test/<feature>-valid.ttl must conform;
specification/<mod>/test/<feature>-invalid.ttl must NOT.

Failing "somehow" is not evidence: a fixture written to trip one shape can fail on an
unrelated typo and pass forever. Each -invalid file therefore declares what it must trip,
one comment line per expected SHACL result:

    # expect: <focus node> <node shape> [<constraint component>]

using CURIEs bound by the fixture's own @prefix lines (plus sh:). A line is satisfied by a
result whose sh:focusNode is that node and whose sh:sourceShape is the named node shape or
a property shape nested under it, and -- when given -- whose sh:sourceConstraintComponent
matches. Every expect line must be satisfied, and every -invalid fixture needs at least one.
Further results are allowed: a bad value can legitimately trip more than one shape.
"""
import functools
import re
import glob
import os
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor

from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

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

@functools.lru_cache(maxsize=None)
def shapes_for(ont):
    """One shapes graph per distinct ontology set, reused by every fixture of that module."""
    return load(list(ont))


SH = Namespace("http://www.w3.org/ns/shacl#")
EXPECT = re.compile(r"^#\s*expect:\s*(\S+)\s+(\S+)(?:\s+(\S+))?\s*$", re.M)


def expectations(path):
    """The (focus, shape, component) triples an -invalid fixture declares, as IRIs."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    prefixes = Graph().parse(data=text, format="turtle").namespace_manager
    bound = dict(prefixes.namespaces())
    bound.setdefault("sh", URIRef(str(SH)))

    def iri(curie):
        if curie.startswith("<") and curie.endswith(">"):
            return URIRef(curie[1:-1])
        prefix, _, local = curie.partition(":")
        if prefix not in bound:
            raise ValueError(f"{path}: expect line uses unbound prefix '{prefix}:'")
        return URIRef(str(bound[prefix]) + local)
    return [(iri(f), iri(s), iri(c) if c else None) for f, s, c in EXPECT.findall(text)]


def _nested(shapes, node, seen=None):
    """A node shape and every shape reachable from it through blank-node constraint structure."""
    seen = set() if seen is None else seen
    if node in seen:
        return seen
    seen.add(node)
    for _p, o in shapes.predicate_objects(node):
        if not isinstance(o, URIRef):
            _nested(shapes, o, seen)
    return seen


def unmet(report, shapes, expected):
    """Expect lines no result satisfies."""
    results = [(report.value(r, SH.focusNode), report.value(r, SH.sourceShape),
                report.value(r, SH.sourceConstraintComponent))
               for r in report.subjects(SH.resultSeverity, None)]
    missing = []
    for focus, shape, component in expected:
        family = _nested(shapes, shape)
        if not any(f == focus and s in family and (component is None or c == component)
                   for f, s, c in results):
            missing.append((focus, shape, component))
    return missing


def check(path):
    """Validate one fixture, returning a failure description or None."""
    should_conform = path.endswith("-valid.ttl")
    ont = ontologies_for(path)
    data = load(ont + [path])
    shapes = shapes_for(tuple(ont))
    conforms, report_graph, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    if should_conform:
        return None if conforms else f"{path}: expected to conform, but did not:\n{report}"
    expected = expectations(path)
    if not expected:
        return f"{path}: an -invalid fixture must declare '# expect: <focus> <shape> [<component>]'"
    if conforms:
        return f"{path}: expected SHACL violation, but it conformed"
    missing = unmet(report_graph, shapes, expected)
    if missing:
        listed = "\n  ".join(" ".join(str(x) for x in m if x is not None) for m in missing)
        return f"{path}: expected results not reported:\n  {listed}\n{report}"
    return None


def workers():
    """Bounded by default: an earlier concurrent run exhausted host memory."""
    requested = os.environ.get("HEXPLAIN_GATE_WORKERS")
    if requested:
        count = int(requested)
        if count < 1:
            raise ValueError("HEXPLAIN_GATE_WORKERS must be at least 1")
        return count
    return max(1, min(os.cpu_count() or 1, 8))


def main():
    parallel = workers()
    print(f"Validating {len(fixtures)} vocabulary fixtures across {parallel} worker(s)", flush=True)
    # Fixtures sharing an ontology set are adjacent, so each worker reuses its cached shapes.
    if parallel == 1:
        results = [check(path) for path in fixtures]
    else:
        with ProcessPoolExecutor(max_workers=parallel) as pool:
            results = list(pool.map(check, fixtures, chunksize=2))
    failures = [failure for failure in results if failure]
    if failures:
        print("FAIL:\n" + "\n".join(failures))
        sys.exit(1)
    print(f"PASS: {len(fixtures)} vocabulary fixtures behave as expected")


if __name__ == "__main__":
    main()
