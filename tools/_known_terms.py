"""Which Hexplain terms a data graph uses that the family does not define.

Shared by tools/test_known_terms.py (this repository's fixtures and examples) and
tools/test_strict_profile.py (an engine checkout's format descriptions).
"""

from __future__ import annotations

from rdflib import Graph, Literal, URIRef

VANN_URI = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")


def owned_namespaces(g: Graph) -> list[str]:
    """The namespace IRIs the family's modules claim, longest first so the most specific matches."""
    return sorted({str(o) for o in g.objects(None, VANN_URI)}, key=len, reverse=True)


def unknown_terms(data: Graph, known: set[object], namespaces: list[str]) -> list[str]:
    """IRIs in ``data`` under an owned namespace that are not in ``known`` (the family's subjects)."""
    found = set()
    for triple in data:
        for term in triple:
            if isinstance(term, Literal) or not isinstance(term, URIRef):
                continue
            iri = str(term)
            if any(iri.startswith(ns) and len(iri) > len(ns) for ns in namespaces) and term not in known:
                found.add(iri)
    return sorted(found)
