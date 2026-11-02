"""Opt-in security profile competency, including compound-resource scoping.

Each case of tools/_build_security_competency.py is validated against security-profile.ttl, and
the retained corpus (specification/validation/test/security-competency.tsv) must be what the
cases render to. The gate only checks; the corpus is written by
``python tools/_build_security_competency.py --write``.
"""

import sys

from _build_security_competency import CORPUS, ROOT, cases, render
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")


def main() -> int:
    # The old `--write` habit must not look like a pass that regenerated something.
    assert len(sys.argv) == 1, (
        "this gate takes no arguments and writes nothing; the corpus is written by "
        "`python tools/_build_security_competency.py --write`"
    )
    shapes = Graph().parse(ROOT / "specification/validation/test/security-profile.ttl")
    rows = cases()
    for name, source, expected, path in rows:
        conforms, report, detail = validate(
            Graph().parse(data=source, format="turtle"), shacl_graph=shapes, inference="none"
        )
        assert bool(conforms) == expected, (name, detail)
        if path:
            assert URIRef(path) in report.objects(None, SH.resultPath), (name, detail)
    assert CORPUS.read_text(encoding="utf-8") == render(rows), (
        f"{CORPUS.relative_to(ROOT).as_posix()} is stale; run `python tools/_build_security_competency.py --write`"
    )
    print(f"PASS: {len(rows)} opt-in security profile cases; no implicit authorization or inheritance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
