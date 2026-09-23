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
    found = {}
    for ttl in sorted(pathlib.Path("specification").glob("*/*.ttl")) + \
               sorted(pathlib.Path("specification").glob("*/*/*.ttl")):
        doc = ttl.parent / "index.html"
        if doc.exists():
            key = ttl.parent.relative_to("specification").as_posix()
            found.setdefault(key, ([], doc))[0].append(ttl)
    return [(key, paths, doc) for key, (paths, doc) in sorted(found.items())]
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
for mod, ttl_paths, doc_path in modules:
    combined = rdflib.Graph()
    for ttl_path in ttl_paths:
        combined += turtle_graph(ttl_path)
    canonical = to_isomorphic(combined)
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


# ---- Versions and the namespace registry --------------------------------------------------
# The embedded vocabulary matching its .ttl says nothing about the prose around it: dlv and
# npv pages announced "Version 1.0" over a 1.1 vocabulary, eleven Turtle header comments named
# a version the ontology no longer had, and the family's namespace registry listed 27 of 36
# namespaces. Each of those is a restatement of a fact the canonical RDF owns, so each is
# compared with it here.
import json  # noqa: E402

MARKER = "\n# BEGIN GENERATED TERM DOCUMENTATION\n"
VANN = rdflib.Namespace("http://purl.org/vocab/vann/")
version_failures = []
family = json.loads(pathlib.Path("specification/family.json").read_text(encoding="utf-8"))["files"]
registry = pathlib.Path("specification/index.html").read_text(encoding="utf-8")
registry = _section(registry, "namespaces")
for rel in family:
    ttl = pathlib.Path("specification") / rel
    text = ttl.read_text(encoding="utf-8").replace("\r\n", "\n")
    g = rdflib.Graph().parse(data=text.split(MARKER)[0], format="turtle")
    ontology = next(iter(g.subjects(rdflib.RDF.type, rdflib.OWL.Ontology)), None)
    if ontology is None:
        continue
    info = g.value(ontology, rdflib.OWL.versionInfo)
    number = re.match(r"\d+(\.\d+)*", str(info)).group(0) if info else None
    viri = g.value(ontology, rdflib.OWL.versionIRI)
    if number and viri is not None and not str(viri).endswith("/" + number):
        version_failures.append(f"{rel}: owl:versionIRI {viri} disagrees with owl:versionInfo {info}")
    first = text.split("\n", 1)[0]
    stated = re.search(r"\b(\d+\.\d+)\b", first) if first.startswith("#") else None
    if number and stated and stated.group(1) != number:
        version_failures.append(f"{rel}: header comment says {stated.group(1)}, owl:versionInfo is {info}")
    page = ttl.parent / "index.html"
    if number and page.exists():
        subtitle = re.search(r'subtitle:\s*"Version ([0-9.]+)"', page.read_text(encoding="utf-8"))
        if subtitle and subtitle.group(1) != number:
            version_failures.append(f"{page.as_posix()}: subtitle says Version {subtitle.group(1)}, "
                                    f"{rel} is {info}")
    prefix, uri = g.value(ontology, VANN.preferredNamespacePrefix), g.value(ontology, VANN.preferredNamespaceUri)
    if prefix is None or uri is None:
        version_failures.append(f"{rel}: no vann:preferredNamespacePrefix/Uri to register")
    elif f"<code>{prefix}</code></td><td><code>{uri}</code>" not in registry:
        version_failures.append(f"specification/index.html#namespaces: {prefix} -> {uri} ({rel}) is not registered")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _build_architecture_catalogue import PAGE as _CATALOGUE, render as _catalogue  # noqa: E402

if _catalogue(_CATALOGUE.read_text(encoding="utf-8")) != _CATALOGUE.read_text(encoding="utf-8"):
    version_failures.append("specification/architecture/index.html: aspect catalogue is stale; "
                            "run python tools/_build_architecture_catalogue.py")
if version_failures:
    print("FAIL:\n  " + "\n  ".join(version_failures))
    sys.exit(1)
print(f"PASS: versions, header comments, namespace registry and aspect catalogue agree with {len(family)} modules")
