"""Shared loading for the Hexplain specification family.

Every validating tool needs the same context: a profile or fixture may map a field to any
aspect property and name a concept from any register, and the shapes that check those
(hexplain:MapsToPropertyShape, the register-binding constraint, abnd:partRole's scheme
membership) all fail when the term's home ontology is simply absent. The failure reads as
"this profile is broken" when the truth is "the loader did not load it", which is the worst
kind of false negative: it points away from the real problem.

That misfired four times while the family grew -- the hx-bundle aspect, the concept
registers, hx-sampling, then the registers again in a second tool -- each time on a
description that was actually correct, and each time fixed by adding one more path to one
more hand-maintained list. This module exists so the next aspect or register is picked up
by every tool the moment it lands, without anyone remembering to.

Paths are relative to the repository root, so callers must run from there (as every tool in
this directory already does).
"""

import glob

from rdflib import Graph

#: Vocabularies that are not aspects or registers and so are not caught by a glob.
_ROOTS = (
    "specification/bddo/bddo.ttl",
    "specification/dlv/dlv.ttl",
    "specification/hexplain/core.ttl",
    "specification/gv/geo.ttl",
    "specification/req/req.ttl",
    "specification/conf/conf.ttl",
)

#: Files carrying SHACL that is meant to apply to everything, wherever it lives. Some
#: modules keep their shapes in the vocabulary file, others in a sibling shapes.ttl.
_SHAPE_FILES = (
    "specification/bddo/bddo.ttl",
    "specification/hexplain/core.ttl",
    "specification/dlv/dlv.ttl",
    "specification/aspect/bundle/bundle.ttl",
    "specification/aspect/spatialref/spatialref.ttl",
    "specification/req/shapes.ttl",
    "specification/conf/shapes.ttl",
)


def _existing(paths):
    return [p for p in paths if glob.glob(p)]


def ontology_paths():
    """Every vocabulary, aspect and register in the family, deduplicated and ordered."""
    seen, out = set(), []
    for p in (
        *sorted(glob.glob("specification/*/*.ttl")),
        *sorted(glob.glob("specification/aspect/*/*.ttl")),
        *sorted(glob.glob("specification/register/*/*.ttl")),
    ):
        if p not in seen and glob.glob(p):
            seen.add(p)
            out.append(p)
    return [p.replace("\\", "/") for p in out]


def shape_paths():
    """The files whose SHACL should be applied when validating anything in the family."""
    return ontology_paths()


def load(paths):
    """Parse the given Turtle files into one graph."""
    g = Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g


def ontologies(extra=()):
    """The family graph, plus any caller-supplied files (a profile, a fixture)."""
    return load([*ontology_paths(), *extra])


def shapes():
    """The family's shape graph."""
    return load(shape_paths())
