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
import json
import pathlib
import re
import sys
from collections import defaultdict

from rdflib import OWL, RDF, Graph, Literal, URIRef

ROOT = pathlib.Path(__file__).resolve().parents[1]
VANN_URI = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
SKOS = "http://www.w3.org/2004/02/skos/core#"
NON_USAGE = {URIRef("http://www.w3.org/2000/01/rdf-schema#seeAlso"),
             URIRef("http://www.w3.org/2000/01/rdf-schema#isDefinedBy"),
             URIRef("http://purl.org/dc/terms/isReplacedBy"),
             *(URIRef(SKOS + p) for p in ("exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch"))}
PREFIXED = re.compile(r"(?<![\w:/#<])([A-Za-z][\w-]*):[A-Za-z_]")
FULL = re.compile(r"<(https://hexplain\.io/ns/[^>\s]+)>")


def _parse(path):
    text = path.read_text(encoding="utf-8")
    return text, Graph().parse(data=text, format="turtle")


def modules():
    """ontology IRI -> (files, graph of those files)."""
    files = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]
    by_dir, owner = defaultdict(list), {}
    for f in files:
        path = ROOT / "specification" / f
        text, g = _parse(path)
        by_dir[path.parent].append((path, text, g))
        for ont in g.subjects(RDF.type, OWL.Ontology):
            owner[path.parent] = ont
    out = {}
    for directory, entries in by_dir.items():
        ont = owner[directory]
        out[ont] = entries
    return out


def referenced(entries, namespaces, prefixes):
    used = set()

    def note(iri):
        for ns in namespaces:
            if iri.startswith(ns) and len(iri) > len(ns):
                used.add(ns)
                return
    for _path, _text, g in entries:
        for s, p, o in g:
            if p in NON_USAGE:
                o = None
            for term in (s, p, o):
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


def main():
    mods = modules()
    whole = Graph()
    for entries in mods.values():
        for _p, _t, g in entries:
            whole += g
    ns_of = {}
    for ont in mods:
        uri = whole.value(ont, VANN_URI)
        if uri is None:
            print(f"FAIL: {ont} declares no vann:preferredNamespaceUri")
            sys.exit(1)
        ns_of[ont] = str(uri)
    ont_of = {ns: ont for ont, ns in ns_of.items()}
    namespaces = sorted(ont_of, key=len, reverse=True)
    prefixes = {}
    for entries in mods.values():
        for _p, _t, g in entries:
            for prefix, ns in g.namespace_manager.namespaces():
                if str(ns) in ont_of:
                    prefixes.setdefault(prefix, str(ns))

    def closure(ont, seen=None):
        seen = set() if seen is None else seen
        for imp in whole.objects(ont, OWL.imports):
            if imp not in seen:
                seen.add(imp)
                closure(imp, seen)
        return seen

    failures = []
    for ont, entries in sorted(mods.items()):
        used = referenced(entries, namespaces, prefixes) - {ns_of[ont]}
        reachable = {ns_of[i] for i in closure(ont) if i in ns_of}
        for ns in sorted(used - reachable):
            failures.append(f"{ont} uses {ont_of[ns]} without importing it (directly or transitively)")
        for imp in sorted(whole.objects(ont, OWL.imports)):
            if imp in ns_of and ns_of[imp] not in used:
                failures.append(f"{ont} imports {imp} but uses none of its terms")
    if failures:
        print("FAIL: owl:imports disagree with usage:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: {len(mods)} modules import exactly the Hexplain namespaces they use")


if __name__ == "__main__":
    main()
