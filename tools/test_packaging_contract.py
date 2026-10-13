"""Packaging competency questions with explicit targets, expected paths and no inference.

These test semantic metadata, not ZIP/TAR parsing or safe filesystem extraction.

Each case is validated in the context of the modules its terms belong to (packaging, archive,
fsmeta and what they import), not the whole family: the case's triples and those modules'
triples are the data graph, and those modules' shapes are the shapes graph. The class hierarchy
a case relies on (an archive entry is a packaging entry) is in that context; the thirty-odd
modules a packaging case never mentions are not, and validating against them cost twenty times
the time for the same verdicts. The context copied into each data graph and the graph given to
pySHACL as shapes are separate objects (``specgraph.context_and_shapes`` says why).
"""

from __future__ import annotations

import specgraph
from _cases import PREFIXES, prefix_block
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

P = Namespace(PREFIXES["packaging"])
SH = Namespace(PREFIXES["sh"])
PREFIX = prefix_block({"p": "packaging", "a": "archive", "f": "fsmeta"})

#: (name, Turtle body, expected conformance, result path a rejection must carry).
CASES: list[tuple[str, str, bool, URIRef | None]] = [
    ("empty container", "<urn:c> a p:Container.", True, None),
    ("unnamed box entry", "<urn:c> p:hasEntry <urn:e>. <urn:e> a p:Entry.", True, None),
    (
        "duplicate archive paths retain separate identities",
        '<urn:c> p:hasEntry <urn:e>,<urn:f>. <urn:e> a p:Entry; p:entryPath "same". <urn:f> a p:Entry; '
        'p:entryPath "same".',
        True,
        None,
    ),
    ("verbatim path is not extraction authorization", '<urn:e> a p:Entry; p:entryPath "../outside".', True, None),
    ("literal member", '<urn:c> p:hasEntry "entry".', False, P.hasEntry),
    ("missing member type under no inference", "<urn:c> p:hasEntry <urn:e>.", False, P.hasEntry),
    ("path must be text", "<urn:e> p:entryPath 42.", False, P.entryPath),
    ("one entry cannot have conflicting paths", '<urn:e> a p:Entry; p:entryPath "one", "two".', False, P.entryPath),
    (
        "archive specialization accepts its own entry subtype",
        "<urn:c> a a:Archive; p:hasEntry <urn:e>. <urn:e> a a:ArchiveEntry.",
        True,
        None,
    ),
    (
        "archive specialization rejects generic entry",
        "<urn:c> a a:Archive; p:hasEntry <urn:e>. <urn:e> a p:Entry.",
        False,
        P.hasEntry,
    ),
    (
        "generic filename does not activate archive cardinality",
        '<urn:f> f:fileName "alias-one", "alias-two".',
        True,
        None,
    ),
]


def main() -> int:
    parsed = [(name, Graph().parse(data=PREFIX + ttl, format="turtle"), ok, path) for name, ttl, ok, path in CASES]
    context, shapes = specgraph.context_and_shapes(specgraph.modules_used_by(*(data for _, data, _, _ in parsed)))
    for name, data, expected, path in parsed:
        actual, report, detail = validate(context + data, shacl_graph=shapes, inference="none", advanced=True)
        assert bool(actual) == expected, (name, detail)
        if path:
            assert path in set(report.objects(None, SH.resultPath)), (name, detail)
    print(f"PASS: {len(CASES)} packaging competency cases with constraint-path assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
