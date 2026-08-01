"""Each specification module ships its vocabulary twice: as <mod>/<mod>.ttl and
embedded (HTML-escaped) in <mod>/index.html. This gate parses both and compares
them as RDF graphs, so formatting differs freely but triples may not.
"""
import html
import pathlib
import re
import sys

import rdflib
from rdflib.compare import graph_diff, to_isomorphic

MODULES = ["bddo", "dlv"]
# Only the normative sections are the vocabulary's second copy. Non-normative
# example blocks are valid Turtle too, but they are meant to differ from the
# .ttl, so comparing them would be measuring the wrong thing.
NORMATIVE_SECTIONS = ("normative-owl", "normative-shacl")
PRE = re.compile(r'<pre class="nohighlight">(.*?)</pre>', re.S)


def _section(text, section_id):
    """The inner HTML of <section id="..."> ... </section>, or "" if absent."""
    m = re.search(rf'<section id="{section_id}">(.*?)</section>', text, re.S)
    return m.group(1) if m else ""


def embedded_graph(doc_path):
    """Parse the Turtle embedded in the page's normative sections."""
    text = doc_path.read_text(encoding="utf-8")
    g = rdflib.Graph()
    for section_id in NORMATIVE_SECTIONS:
        for block in PRE.findall(_section(text, section_id)):
            g.parse(data=html.unescape(block), format="turtle")
    return g


failures = []
for mod in MODULES:
    ttl_path = pathlib.Path(f"specification/{mod}/{mod}.ttl")
    doc_path = pathlib.Path(f"specification/{mod}/index.html")
    if not ttl_path.exists() or not doc_path.exists():
        failures.append(f"{mod}: missing {ttl_path} or {doc_path}")
        continue
    canonical = to_isomorphic(rdflib.Graph().parse(ttl_path, format="turtle"))
    embedded = to_isomorphic(embedded_graph(doc_path))
    if canonical == embedded:
        continue
    _, only_ttl, only_html = graph_diff(canonical, embedded)
    lines = [f"{mod}: index.html does not match {mod}.ttl"]
    for s, p, o in sorted(only_ttl, key=str)[:10]:
        lines.append(f"    in .ttl only : {s} {p} {o}")
    for s, p, o in sorted(only_html, key=str)[:10]:
        lines.append(f"    in .html only: {s} {p} {o}")
    failures.append("\n".join(lines))

if failures:
    print("FAIL:\n" + "\n\n".join(failures))
    sys.exit(1)
print(f"PASS: {len(MODULES)} modules' index.html match their .ttl")
