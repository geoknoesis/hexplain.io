"""Transport integer boundaries, including RFC 768's absent-source-port encoding.

Each case of tools/_build_network_competency.py is validated against net.ttl alone, so each
property independently activates validation, and the retained corpus
(specification/validation/test/network-competency.tsv) must be what the cases render to. The
gate only checks; the corpus is written by ``python tools/_build_network_competency.py --write``.
"""

import sys

from _build_network_competency import CORPUS, ROOT, cases, render
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")


def main() -> int:
    # The old `--write` habit must not look like a pass that regenerated something.
    assert len(sys.argv) == 1, (
        "this gate takes no arguments and writes nothing; the corpus is written by "
        "`python tools/_build_network_competency.py --write`"
    )
    shapes = Graph().parse(ROOT / "specification/npv/net.ttl")
    rows = cases()
    for name, source, expected, path in rows:
        ok, report, detail = validate(Graph().parse(data=source, format="turtle"), shacl_graph=shapes, inference="none")
        assert bool(ok) == expected, (name, detail)
        if not expected:
            assert URIRef(path) in report.objects(None, SH.resultPath), (name, detail)
    assert CORPUS.read_text(encoding="utf-8") == render(rows), (
        f"{CORPUS.relative_to(ROOT).as_posix()} is stale; run `python tools/_build_network_competency.py --write`"
    )
    print(f"PASS: {len(rows)} transport boundary contracts; each property independently activates validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
