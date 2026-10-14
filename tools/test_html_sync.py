"""Each specification module ships its vocabulary twice: as <mod>/<mod>.ttl and
embedded (HTML-escaped) in <mod>/index.html. This gate parses both and compares
them as RDF graphs, so formatting differs freely but triples may not.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys
from pathlib import Path

import rdflib
from _family import DOC_SUFFIX
from rdflib.compare import graph_diff, to_isomorphic
from rdflib.term import Node

ROOT = pathlib.Path(__file__).resolve().parents[1]


# Discovered, not listed. This gate covered two modules by name for as long as it existed,
# so the other eight shipped a second copy of their vocabulary that nothing compared -- and
# gv and hexplain had both drifted, in each case an rdfs:comment that was elaborated in the
# .ttl and left at its older, shorter wording on the page. Nothing was missing, which is
# precisely why nobody caught it by reading.
#
# A module qualifies when it has both <mod>.ttl and index.html; aspects and registers sit
# one level deeper and are picked up the same way. A module that later gains a page joins
# the gate on its own.
def _modules() -> list[tuple[str, list[Path], Path]]:
    found: dict[str, tuple[list[Path], Path]] = {}
    for ttl in sorted((ROOT / "specification").glob("*/*.ttl")) + sorted((ROOT / "specification").glob("*/*/*.ttl")):
        if ttl.name.endswith(DOC_SUFFIX):
            continue  # a generated annotation graph, not the vocabulary a page embeds
        doc = ttl.parent / "index.html"
        if doc.exists():
            key = ttl.parent.relative_to(ROOT / "specification").as_posix()
            found.setdefault(key, ([], doc))[0].append(ttl)
    return [(key, paths, doc) for key, (paths, doc) in sorted(found.items())]


# Only the normative sections are the vocabulary's second copy. Non-normative
# example blocks are valid Turtle too, but they are meant to differ from the
# .ttl, so comparing them would be measuring the wrong thing.
NORMATIVE_SECTIONS = ("normative-owl", "normative-shacl")
PRE = re.compile(r'<pre class="nohighlight">(.*?)</pre>', re.S)


def _section(text: str, section_id: str) -> str:
    """The inner HTML of <section id="..."> ... </section>, or "" if absent."""
    m = re.search(rf'<section id="{section_id}">(.*?)</section>', text, re.S)
    return m.group(1) if m else ""


def turtle_graph(ttl_path: Path) -> rdflib.Graph:
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


def embedded_graph(doc_path: Path) -> rdflib.Graph:
    """Parse the Turtle embedded in the page's normative sections."""
    text = doc_path.read_text(encoding="utf-8")
    g = rdflib.Graph()
    for section_id in NORMATIVE_SECTIONS:
        for block in PRE.findall(_section(text, section_id)):
            g.parse(data=html.unescape(block), format="turtle")
    return g


def _graph_failures(modules: list[tuple[str, list[Path], Path]]) -> list[str]:
    """One message per module whose page embeds a graph other than its .ttl files state."""
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
    return failures


VANN = rdflib.Namespace("http://purl.org/vocab/vann/")


def _version_number(info: Node | None) -> str | None:
    """The dotted number that opens an owl:versionInfo, or None when the ontology states none."""
    if not info:
        return None
    found = re.match(r"\d+(\.\d+)*", str(info))
    assert found is not None, f"owl:versionInfo {info} does not open with a version number"
    return found.group(0)


def _stated_version_failures(rel: str, ttl: Path, text: str, g: rdflib.Graph, ontology: Node) -> list[str]:
    """Where a module's version IRI, header comment or page subtitle disagrees with its owl:versionInfo."""
    failures = []
    info = g.value(ontology, rdflib.OWL.versionInfo)
    number = _version_number(info)
    viri = g.value(ontology, rdflib.OWL.versionIRI)
    if number and viri is not None and not str(viri).endswith("/" + number):
        failures.append(f"{rel}: owl:versionIRI {viri} disagrees with owl:versionInfo {info}")
    first = text.split("\n", 1)[0]
    stated = re.search(r"\b(\d+\.\d+)\b", first) if first.startswith("#") else None
    if number and stated and stated.group(1) != number:
        failures.append(f"{rel}: header comment says {stated.group(1)}, owl:versionInfo is {info}")
    page = ttl.parent / "index.html"
    if number and page.exists():
        subtitle = re.search(r'subtitle:\s*"Version ([0-9.]+)"', page.read_text(encoding="utf-8"))
        if subtitle and subtitle.group(1) != number:
            failures.append(f"{page.as_posix()}: subtitle says Version {subtitle.group(1)}, {rel} is {info}")
    return failures


def _namespace_failures(rel: str, g: rdflib.Graph, ontology: Node, registry: str) -> list[str]:
    """Where a module's namespace prefix is missing, misplaced or absent from the family's registry."""
    prefix, uri = g.value(ontology, VANN.preferredNamespacePrefix), g.value(ontology, VANN.preferredNamespaceUri)
    if str(ontology).endswith("/shapes"):
        # A shapes document's terms are in its vocabulary's namespace; only the vocabulary
        # claims the prefix, so a shapes document that claims one too is the defect.
        if prefix is not None or uri is not None:
            return [f"{rel}: a shapes document claims its vocabulary's namespace prefix"]
        return []
    if prefix is None or uri is None:
        return [f"{rel}: no vann:preferredNamespacePrefix/Uri to register"]
    if f"<code>{prefix}</code></td><td><code>{uri}</code>" not in registry:
        return [f"specification/index.html#namespaces: {prefix} -> {uri} ({rel}) is not registered"]
    return []


def _module_failures(family: list[str]) -> list[str]:
    """Version and namespace restatements that disagree with the canonical RDF, module by module."""
    failures = []
    registry = (ROOT / "specification/index.html").read_text(encoding="utf-8")
    registry = _section(registry, "namespaces")
    for rel in family:
        ttl = ROOT / "specification" / rel
        text = ttl.read_text(encoding="utf-8").replace("\r\n", "\n")
        g = rdflib.Graph().parse(data=text, format="turtle")
        ontology = next(iter(g.subjects(rdflib.RDF.type, rdflib.OWL.Ontology)), None)
        if ontology is None:
            continue
        failures += _stated_version_failures(rel, ttl, text, g, ontology)
        failures += _namespace_failures(rel, g, ontology, registry)
    return failures


def _catalogue_failures() -> list[str]:
    """A message when the architecture page's aspect catalogue no longer matches the aspects."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from _build_architecture_catalogue import PAGE as _CATALOGUE
    from _build_architecture_catalogue import render as _catalogue

    if _catalogue(_CATALOGUE.read_text(encoding="utf-8")) != _CATALOGUE.read_text(encoding="utf-8"):
        return [
            "specification/architecture/index.html: aspect catalogue is stale; "
            "run python tools/_build_architecture_catalogue.py"
        ]
    return []


def _lead_failures() -> tuple[int, list[str]]:
    """The number of generated page leads, and a message for each that differs from its ontology."""
    from html import escape as _escape

    from _build_term_reference import LEAD as _LEAD
    from _build_term_reference import lead_text as _lead_text
    from _reference import load as _load_module
    from _reference import modules as _modules_of

    leads = 0
    failures = []
    for directory, paths in _modules_of().items():
        page = directory / "index.html"
        if not page.exists():
            continue
        match = _LEAD.search(page.read_text(encoding="utf-8"))
        if not match:
            continue
        leads += 1
        title, lead = _lead_text(_load_module(paths))
        if match[2] != _escape(title) or match[4] != _escape(lead):
            failures.append(
                f"{page.relative_to(pathlib.Path.cwd().resolve()).as_posix() if page.is_absolute() else page}: "
                "title or lead differs from the ontology's rdfs:label / rdfs:comment; "
                "run python tools/_build_term_reference.py"
            )
    return leads, failures


def main() -> int:
    modules = _modules()
    if not modules:
        sys.exit("FAIL: no module has both a .ttl and an index.html (wrong working directory?)")

    failures = _graph_failures(modules)
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
    family = [
        f
        for f in json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]
        if not f.endswith(DOC_SUFFIX)
    ]
    version_failures = _module_failures(family) + _catalogue_failures()
    # ---- Page leads ----------------------------------------------------------------------------
    # A generated module page opens with the ontology's label and a lead paragraph. The conf page's
    # lead said "Severity is deliberately absent" long after conf.ttl gained conf:severity: the
    # lead is a restatement of rdfs:comment, so it is compared with it (its first paragraph).
    leads, lead_failures = _lead_failures()
    version_failures += lead_failures

    if version_failures:
        print("FAIL:\n  " + "\n  ".join(version_failures))
        sys.exit(1)
    print(
        f"PASS: versions, header comments, namespace registry and aspect catalogue agree with {len(family)} modules; "
        f"{leads} generated page leads restate their ontology's comment"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
