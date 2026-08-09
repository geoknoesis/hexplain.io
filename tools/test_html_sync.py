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

# Discovered, not listed. This gate covered two modules by name for as long as it existed,
# so the other eight shipped a second copy of their vocabulary that nothing compared -- and
# gv and hexplain had both drifted, in each case an rdfs:comment that was elaborated in the
# .ttl and left at its older, shorter wording on the page. Nothing was missing, which is
# precisely why nobody caught it by reading.
#
# A module qualifies when it has both <mod>.ttl and index.html; aspects and registers sit
# one level deeper and are picked up the same way. A module that later gains a page joins
# the gate on its own.
def _modules():
    found = []
    for ttl in sorted(pathlib.Path("specification").glob("*/*.ttl")) + \
               sorted(pathlib.Path("specification").glob("*/*/*.ttl")):
        doc = ttl.parent / "index.html"
        if doc.exists():
            found.append((ttl.parent.relative_to("specification").as_posix(), ttl, doc))
    return found
# Only the normative sections are the vocabulary's second copy. Non-normative
# example blocks are valid Turtle too, but they are meant to differ from the
# .ttl, so comparing them would be measuring the wrong thing.
NORMATIVE_SECTIONS = ("normative-owl", "normative-shacl")
PRE = re.compile(r'<pre class="nohighlight">(.*?)</pre>', re.S)


def _section(text, section_id):
    """The inner HTML of <section id="..."> ... </section>, or "" if absent."""
    m = re.search(rf'<section id="{section_id}">(.*?)</section>', text, re.S)
    return m.group(1) if m else ""


def turtle_graph(ttl_path):
    """Parse a .ttl file from newline-normalised text.

    Read via read_text (universal newlines) rather than handing rdflib the path:
    with core.autocrlf the working tree may hold CRLF, and rdflib would then keep
    the CR inside multi-line triple-quoted literals -- the SHACL sh:select strings
    -- while the index.html side, also read via read_text, would not. That made
    identical content compare unequal on a fresh checkout but not in a working tree
    whose files had just been written with LF.
    """
    g = rdflib.Graph()
    g.parse(data=ttl_path.read_text(encoding="utf-8"), format="turtle")
    return g


def embedded_graph(doc_path):
    """Parse the Turtle embedded in the page's normative sections."""
    text = doc_path.read_text(encoding="utf-8")
    g = rdflib.Graph()
    for section_id in NORMATIVE_SECTIONS:
        for block in PRE.findall(_section(text, section_id)):
            g.parse(data=html.unescape(block), format="turtle")
    return g


modules = _modules()
if not modules:
    sys.exit("FAIL: no module has both a .ttl and an index.html (wrong working directory?)")

failures = []
for mod, ttl_path, doc_path in modules:
    canonical = to_isomorphic(turtle_graph(ttl_path))
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
print(f"PASS: {len(modules)} modules' index.html match their .ttl")
