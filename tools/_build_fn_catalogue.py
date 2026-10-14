"""Write or check the function catalogue of specification/fn/index.html.

The catalogue section is generated from fn.ttl: each hxf:Function's kind, signature, hxf:reads
and rdfs:comment, one table row per function. ``--write`` regenerates the section in place;
``--check`` exits 1 when the page's section is not what fn.ttl renders to. The gate
``tools/test_fn_catalogue.py`` checks the same and writes nothing.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Namespace, URIRef
from rdflib.term import Node

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "specification/fn/index.html"
HXF = Namespace("https://hexplain.io/ns/fn#")
SECTION = re.compile(r'<section id="catalogue">.*?</section>', re.S)


def curie(g: Graph, term: Node) -> str:
    return g.namespace_manager.normalizeUri(term) if isinstance(term, URIRef) else str(term)


def render() -> str:
    g = Graph().parse(data=(ROOT / "specification/fn/fn.ttl").read_text(encoding="utf-8"), format="turtle")
    functions = [f for f in g.subjects(RDF.type, HXF.Function)]
    # Catalogue order: by layer, then as the vocabulary declares them (source order is not kept
    # by RDF, so by the signature's position in the file).
    source = (ROOT / "specification/fn/fn.ttl").read_text(encoding="utf-8")
    functions.sort(
        key=lambda f: (int(str(g.value(f, HXF.layer) or 0)), source.find(":" + str(f).split("#")[1] + " a "))
    )
    rows = []
    for f in functions:
        kind = str(g.value(f, HXF.kind)).split("#")[-1]
        reads = ", ".join(sorted(curie(g, r) for r in g.objects(f, HXF.reads))) or "&#8212;"
        rows.append(
            f"<tr><td><code>{curie(g, f)}</code></td><td>{kind}</td>"
            f"<td><code>{html.escape(str(g.value(f, HXF.signature)))}</code></td>"
            f"<td>{reads}</td><td>{html.escape(str(g.value(f, RDFS.comment)), quote=False)}</td></tr>"
        )
    return (
        '<section id="catalogue"><h2>Function catalogue</h2><p>' + str(len(functions)) + " functions, one row per "
        '<code>hxf:Function</code>, generated from <a href="fn.ttl">fn.ttl</a>. <b>Kind</b> is <code>hxf:Pure</code> '
        "(a SHACL-AF <code>sh:SPARQLFunction</code> body any SHACL-AF engine can run) or <code>hxf:Native</code> "
        "(implemented against the Hexplain engine, no SPARQL body). <b>Reads</b> names the aspect and core vocabulary "
        "terms the function reads from the graph; a dash means the function needs only its own arguments. When a "
        'function answers nothing is its <code>hxf:unboundWhen</code> in the vocabulary.</p><table class="simple">'
        "<thead><tr><th>Function</th><th>Kind</th><th>Signature</th><th>Reads</th><th>Description</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table></section>"
    )


def expected_page() -> tuple[str, str]:
    """The page as it is and as it should be, with the catalogue section rendered from fn.ttl."""
    text = PAGE.read_text(encoding="utf-8")
    return text, SECTION.sub(lambda m: render(), text, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate the catalogue section from fn.ttl")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the section is not what --write produces")
    args = parser.parse_args(argv)
    text, expected = expected_page()
    relative = PAGE.relative_to(ROOT).as_posix()
    if args.write:
        PAGE.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote the function catalogue of {relative}")
        return 0
    if text != expected:
        print(f"STALE: the function catalogue of {relative} differs from fn.ttl; run this builder with --write")
        return 1
    print(f"CURRENT: the function catalogue of {relative} is what fn.ttl renders to")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
