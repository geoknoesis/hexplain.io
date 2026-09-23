"""Regenerate the architecture page's aspect-catalogue cells from the canonical Turtle.

The catalogue listed hand-written "key terms" for each established aspect, and they drifted:
rows marked established named depth, gridSpacing, channelLayout, hashValue, timecode and a
dozen more terms no module defines. For every row whose aspect has a module, this rewrites
the "Key terms" cell with the classes and properties the module actually defines (deprecated
terms excluded) and, where the table has an "Imports" column, the module's owl:imports.
Rows for aspects without a module (hx-style, hx-descriptive, ...) are left as written.

    python tools/_build_architecture_catalogue.py          # rewrite the page
    python tools/_build_architecture_catalogue.py --check  # fail if the page is stale
"""
import argparse
import re
import sys

from rdflib import OWL, Literal, URIRef

from _reference import ROOT, kind, load, local

PAGE = ROOT / "specification/architecture/index.html"
ROW = re.compile(r'<tr><td><code>hx-([a-z]+)</code> ✓</td>(.*?)</tr>')
TABLE = re.compile(r'<table class="simple">\s*<thead><tr>(.*?)</tr></thead>(.*?)</table>', re.S)


def module_terms(name):
    path = ROOT / f"specification/aspect/{name}/{name}.ttl"
    if not path.exists():
        return None
    g = load([path.relative_to(ROOT)], base=True)
    ns = f"https://hexplain.io/ns/aspect/{name}#"
    terms = sorted((t for t in set(g.subjects()) if isinstance(t, URIRef) and str(t).startswith(ns)
                    and kind(g, t) in ("Class", "Object property", "Datatype property")
                    and (t, OWL.deprecated, Literal(True)) not in g), key=lambda t: (kind(g, t) != "Class", local(t)))
    ont = URIRef(ns[:-1])
    imports = sorted(str(i).rsplit("/", 1)[-1] for i in g.objects(ont, OWL.imports))
    return [local(t) for t in terms], imports


def render(text):
    def table(m):
        headers = re.findall(r"<th>(.*?)</th>", m.group(1))
        body = m.group(2)
        if "Key terms" not in headers:
            return m.group(0)
        key_at = headers.index("Key terms")
        imports_at = headers.index("Imports") if "Imports" in headers else None

        def row(r):
            found = module_terms(r.group(1))
            if found is None:
                return r.group(0)
            terms, imports = found
            cells = re.findall(r"<td>(.*?)</td>", r.group(2))
            cells[key_at - 1] = ", ".join(terms)
            if imports_at is not None:
                cells[imports_at - 1] = ", ".join(imports) if imports else "—"
            return f'<tr><td><code>hx-{r.group(1)}</code> ✓</td>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        return m.group(0).replace(body, ROW.sub(row, body))
    return TABLE.sub(table, text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = PAGE.read_text(encoding="utf-8")
    expected = render(text)
    if args.check:
        if expected != text:
            print("FAIL: architecture catalogue is stale; run python tools/_build_architecture_catalogue.py")
            sys.exit(1)
        print("PASS: architecture catalogue lists the terms and imports the aspect modules define")
        return
    PAGE.write_text(expected, encoding="utf-8", newline="\n")
    print("Rewrote the aspect catalogue from canonical Turtle")


if __name__ == "__main__":
    main()
