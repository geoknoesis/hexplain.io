"""The function catalogue of specification/fn/index.html is generated from fn.ttl.

The catalogue table was maintained by hand and drifted from the canonical RDF: after the affine
became corner-based, it still said hxf:column and hxf:row round to the nearest cell centre for
asref:PixelCenter. The table is now rendered from each hxf:Function's kind, signature, hxf:reads
and rdfs:comment, and this gate fails when the page differs. Run with --write to regenerate.
"""
import html
import re
import sys
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "specification/fn/index.html"
HXF = Namespace("https://hexplain.io/ns/fn#")
SECTION = re.compile(r'<section id="catalogue">.*?</section>', re.S)


def curie(g, term):
    return g.namespace_manager.normalizeUri(term) if isinstance(term, URIRef) else str(term)


def render():
    g = Graph().parse(data=(ROOT / "specification/fn/fn.ttl").read_text(encoding="utf-8"), format="turtle")
    functions = [f for f in g.subjects(RDF.type, HXF.Function)]
    # Catalogue order: by layer, then as the vocabulary declares them (source order is not kept
    # by RDF, so by the signature's position in the file).
    source = (ROOT / "specification/fn/fn.ttl").read_text(encoding="utf-8")
    functions.sort(key=lambda f: (int(g.value(f, HXF.layer) or 0), source.find(":" + str(f).split("#")[1] + " a ")))
    rows = []
    for f in functions:
        kind = str(g.value(f, HXF.kind)).split("#")[-1]
        reads = ", ".join(sorted(curie(g, r) for r in g.objects(f, HXF.reads))) or "&#8212;"
        rows.append(f"<tr><td><code>{curie(g, f)}</code></td><td>{kind}</td><td><code>{html.escape(str(g.value(f, HXF.signature)))}</code></td>"
                    f"<td>{reads}</td><td>{html.escape(str(g.value(f, RDFS.comment)), quote=False)}</td></tr>")
    return ('<section id="catalogue"><h2>Function catalogue</h2><p>' + str(len(functions)) + ' functions, one row per '
            '<code>hxf:Function</code>, generated from <a href="fn.ttl">fn.ttl</a>. <b>Kind</b> is <code>hxf:Pure</code> '
            '(a SHACL-AF <code>sh:SPARQLFunction</code> body any SHACL-AF engine can run) or <code>hxf:Native</code> '
            '(implemented against the Hexplain engine, no SPARQL body). <b>Reads</b> names the aspect and core vocabulary '
            'terms the function reads from the graph; a dash means the function needs only its own arguments. When a '
            'function answers nothing is its <code>hxf:unboundWhen</code> in the vocabulary.</p><table class="simple">'
            '<thead><tr><th>Function</th><th>Kind</th><th>Signature</th><th>Reads</th><th>Description</th></tr></thead>'
            '<tbody>' + "".join(rows) + "</tbody></table></section>")


def main():
    text = PAGE.read_text(encoding="utf-8")
    expected = SECTION.sub(lambda m: render(), text, count=1)
    if "--write" in sys.argv:
        PAGE.write_text(expected, encoding="utf-8", newline="\n")
        text = expected
    if text != expected:
        print("FAIL: the function catalogue of specification/fn/index.html differs from fn.ttl; "
              "run python tools/test_fn_catalogue.py --write")
        return 1
    print("PASS: the function catalogue is generated from fn.ttl and current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
