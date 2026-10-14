"""Competency cases for the conformance, requirement and function vocabularies.

conf, req and fn had shapes and fixtures but no case in a shared competency corpus, so the
competency trace, and the capability summary built from it, showed none of their resources as
exercised. specification/validation/test/conformance-competency.tsv holds independently
written cases -- one conforming and one or more non-conforming per competency question -- in
the four-column corpus format (name, conforms, expected result path, base64 Turtle). This gate
validates each against the conf, req and fn shapes and checks the stored corpus is current. It
only checks: the cases are authored in tools/_build_conformance_competency.py, and after
changing one, ``python tools/_build_conformance_competency.py --write`` regenerates the corpus.

The ontology graph mixed into each case is the modules the cases are written in terms of (conf,
req, fn, bddo and what they import), not the whole family: a shape here reads the class of a
requirement or a struct, which those modules state, and nothing the other thirty state.
"""

from __future__ import annotations

import sys

import specgraph
from _build_conformance_competency import CORPUS, cases, render
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

SHAPES = [
    "specification/conf/conf.ttl",
    "specification/conf/shapes.ttl",
    "specification/req/req.ttl",
    "specification/req/shapes.ttl",
    "specification/fn/fn.ttl",
]
SH = Namespace("http://www.w3.org/ns/shacl#")


def main() -> int:
    # The old `--write` habit must not look like a pass that regenerated something.
    assert len(sys.argv) == 1, (
        "this gate takes no arguments and writes nothing; the corpus is written by "
        "`python tools/_build_conformance_competency.py --write`"
    )
    shapes = specgraph.load(SHAPES)
    rows = cases()
    parsed = [Graph().parse(data=body, format="turtle") for _, _, _, body in rows]
    context = specgraph.shapes_of(specgraph.modules_used_by(*parsed))
    for (name, ok, path, _), data in zip(rows, parsed, strict=True):
        conforms, report, text = validate(data, shacl_graph=shapes, ont_graph=context, inference="none", advanced=True)
        assert bool(conforms) == ok, (name, text)
        if path:
            assert URIRef(path) in report.objects(None, SH.resultPath), (name, text)
    if not CORPUS.exists() or CORPUS.read_text(encoding="utf-8") != render(rows):
        print("FAIL: conformance-competency.tsv is stale; run python tools/_build_conformance_competency.py --write")
        return 1
    print(f"PASS: {len(rows)} conformance, requirement and function competency cases with result-path assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
