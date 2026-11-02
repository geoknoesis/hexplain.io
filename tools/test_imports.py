"""Each module imports what it uses, and uses what it imports.

owl:imports is how a consumer loading one module learns which others it needs: fn.ttl used
dlv, core, spatialref, raster and signal terms while importing nothing, so loading it alone
gave a graph whose function signatures pointed at undefined classes. The converse also
misleads -- gv imported security and raster without using either. For every family module
this gate compares the Hexplain namespaces it references (in triples, and in the SPARQL text
of its constraints and function bodies) with the transitive closure of its owl:imports.

Cross-references that do not need the target loaded are not usage: rdfs:seeAlso, the SKOS
mapping properties, rdfs:isDefinedBy and dcterms:isReplacedBy name a term without relying on
its definition. A file without its own owl:Ontology (a module's separate shapes.ttl) is
counted as part of the ontology of the module directory it sits in.
"""

from __future__ import annotations

import pathlib
import re
import sys
from collections import defaultdict
from collections.abc import Iterable

from _family import canonical_files
from rdflib import OWL, RDF, Graph, Literal, URIRef
from rdflib.term import Node

ROOT = pathlib.Path(__file__).resolve().parents[1]
VANN_URI = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
SKOS = "http://www.w3.org/2004/02/skos/core#"
NON_USAGE = {
    URIRef("http://www.w3.org/2000/01/rdf-schema#seeAlso"),
    URIRef("http://www.w3.org/2000/01/rdf-schema#isDefinedBy"),
    URIRef("http://purl.org/dc/terms/isReplacedBy"),
    *(URIRef(SKOS + p) for p in ("exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch")),
}
PREFIXED = re.compile(r"(?<![\w:/#<])([A-Za-z][\w-]*):[A-Za-z_]")
FULL = re.compile(r"<(https://hexplain\.io/ns/[^>\s]+)>")


#: One file of a module: its path, its text and its graph.
Entry = tuple[pathlib.Path, str, Graph]


def _parse(path: pathlib.Path) -> tuple[str, Graph]:
    text = path.read_text(encoding="utf-8")
    return text, Graph().parse(data=text, format="turtle")


def modules() -> dict[Node, list[Entry]]:
    """ontology IRI -> (files, graph of those files)."""
    files = canonical_files(ROOT / "specification")
    # A file with its own owl:Ontology is its own module (a separate shapes document such as
    # conf/shapes.ttl declares <.../conf/shapes> and imports the vocabulary it validates); a
    # file without one belongs to the ontology of the module directory it sits in.
    parsed: list[tuple[pathlib.Path, str, Graph, Node | None]] = []
    owner: dict[pathlib.Path, Node] = {}
    for f in files:
        path = ROOT / "specification" / f
        text, g = _parse(path)
        own = next(iter(g.subjects(RDF.type, OWL.Ontology)), None)
        parsed.append((path, text, g, own))
        if own is not None and path.stem == path.parent.name or own is not None and path.parent not in owner:
            owner[path.parent] = own
    out: defaultdict[Node, list[Entry]] = defaultdict(list)
    for path, text, g, own in parsed:
        out[own if own is not None else owner[path.parent]].append((path, text, g))
    return dict(out)


def referenced(entries: Iterable[Entry], namespaces: list[str], prefixes: dict[str, str]) -> set[str]:
    used: set[str] = set()

    def note(iri: str) -> None:
        for ns in namespaces:
            if iri.startswith(ns) and len(iri) > len(ns):
                used.add(ns)
                return

    for _path, _text, g in entries:
        for s, p, o in g:
            for term in (s, p) if p in NON_USAGE else (s, p, o):
                if isinstance(term, URIRef):
                    note(str(term))
                elif isinstance(term, Literal) and isinstance(term.value, str) and ":" in term:
                    body = str(term)
                    for m in FULL.finditer(body):
                        note(m.group(1))
                    if re.search(r"\b(SELECT|CONSTRUCT|ASK|PREFIX|WHERE)\b", body):
                        for m in PREFIXED.finditer(body):
                            if m.group(1) in prefixes:
                                note(prefixes[m.group(1)])
    return used


def _namespaces(mods: dict[Node, list[Entry]], whole: Graph) -> dict[Node, str]:
    """ontology IRI -> the namespace it owns, or (a shapes document) shares with its vocabulary."""
    ns_of = {}
    for ont in mods:
        uri = whole.value(ont, VANN_URI)
        # A shapes document (<vocabulary>/shapes) claims no namespace of its own: its terms are in
        # the namespace of the vocabulary it validates and imports, which alone claims the prefix.
        vocabulary = URIRef(str(ont).removesuffix("/shapes"))
        if uri is None and vocabulary != ont and (ont, OWL.imports, vocabulary) in whole:
            uri = whole.value(vocabulary, VANN_URI)
        if uri is None:
            print(f"FAIL: {ont} declares no vann:preferredNamespaceUri")
            sys.exit(1)
        ns_of[ont] = str(uri)
    return ns_of


def _prefixes(mods: dict[Node, list[Entry]], owned: Iterable[str]) -> dict[str, str]:
    """prefix -> namespace, for every prefix a module binds to one of the ``owned`` namespaces."""
    owned = set(owned)
    prefixes: dict[str, str] = {}
    for entries in mods.values():
        for _p, _t, g in entries:
            for prefix, ns in g.namespace_manager.namespaces():
                if str(ns) in owned:
                    prefixes.setdefault(prefix, str(ns))
    return prefixes


def _closure(whole: Graph, ont: Node, seen: set[Node] | None = None) -> set[Node]:
    """Every ontology ``ont`` imports, directly or transitively."""
    seen = set() if seen is None else seen
    for imp in whole.objects(ont, OWL.imports):
        if imp not in seen:
            seen.add(imp)
            _closure(whole, imp, seen)
    return seen


def main() -> None:
    mods = modules()
    whole = Graph()
    for entries in mods.values():
        for _p, _t, g in entries:
            whole += g
    ns_of = _namespaces(mods, whole)
    # The vocabulary, not its shapes document, is the namespace's owner.
    ont_of = {
        ns: ont for ont, ns in sorted(ns_of.items(), key=lambda item: str(item[0]).endswith("/shapes"), reverse=True)
    }
    namespaces = sorted(ont_of, key=len, reverse=True)
    prefixes = _prefixes(mods, ont_of)

    failures = []
    for ont, entries in sorted(mods.items(), key=lambda item: str(item[0])):
        used = referenced(entries, namespaces, prefixes) - {ns_of[ont]}
        reachable = {ns_of[i] for i in _closure(whole, ont) if i in ns_of}
        for ns in sorted(used - reachable):
            failures.append(f"{ont} uses {ont_of[ns]} without importing it (directly or transitively)")
        for imp in sorted(whole.objects(ont, OWL.imports), key=str):
            # A shapes document shares its vocabulary's namespace; importing it is its use.
            if imp in ns_of and ns_of[imp] not in used and ns_of[imp] != ns_of[ont]:
                failures.append(f"{ont} imports {imp} but uses none of its terms")
    if failures:
        print("FAIL: owl:imports disagree with usage:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: {len(mods)} modules import exactly the Hexplain namespaces they use")


if __name__ == "__main__":
    main()
