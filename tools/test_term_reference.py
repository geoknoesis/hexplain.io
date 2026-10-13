"""Documentation completeness, determinism and annotation-only change contract."""

from __future__ import annotations

import json
from html.parser import HTMLParser

from _build_term_reference import GUIDE, build
from _reference import (
    GENERATED_ANNOTATIONS,
    RDFS,
    ROOT,
    SKOS,
    Graph,
    documentation_path,
    kind,
    label,
    load,
    modules,
    owned,
)
from rdflib.compare import isomorphic


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.terms: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if "id" in a:
            self.ids.append(self.stated(a, "id"))
        if "data-term-iri" in a:
            self.terms.append(self.stated(a, "data-term-iri"))
        if tag == "a":
            self.links.append(self.stated(a, "href") if "href" in a else "")

    @staticmethod
    def stated(attrs: dict[str, str | None], name: str) -> str:
        """The value of an attribute the page states; one written without a value is a defect."""
        value = attrs[name]
        assert value is not None, f"a generated page has a {name} attribute without a value"
        return value


def main() -> int:
    pages = {}
    total = 0
    shapes = 0
    for directory, paths in modules().items():
        g = load(paths)
        base = load(paths, base=True)
        # The generated annotation graph of each module file: editorial annotations only, about terms
        # the module declares, and nothing the module already states.
        annotations = Graph()
        for p in paths:
            doc = ROOT / documentation_path(p)
            assert doc.is_file(), f"{p}: no generated annotation graph ({doc.name}); run --enrich"
            annotations.parse(data=doc.read_text(encoding="utf-8"), format="turtle")
        assert all(p in GENERATED_ANNOTATIONS for s, p, o in annotations), "Documentation changed formal semantics"
        assert set(annotations.subjects()) <= set(owned(base)), (
            f"{directory}: documentation of a term not declared here"
        )
        assert not set(annotations) & set(base), f"{directory}: the annotation graph repeats the canonical file"
        assert isomorphic(g - annotations, base), directory
        for t in owned(g):
            total += 1
            assert g.value(t, RDFS.label) or g.value(t, SKOS.prefLabel), t
            # A term's definition is its skos:definition, else its rdfs:comment (the family rule in
            # specification/ontology-design, Documentation annotations); only an ontology must carry a
            # scope note, and a term's note, when it has one, says something.
            definition = g.value(t, SKOS.definition) or g.value(t, RDFS.comment)
            scope_note = g.value(t, SKOS.scopeNote)
            assert definition and len(str(definition)) > 25 and str(definition).strip() != label(g, t), t
            assert (scope_note is None and kind(g, t) != "Ontology") or (scope_note and len(str(scope_note)) > 40), t
            # Ownership is stated where the term is declared, never in the generated graph.
            assert kind(g, t) == "Ontology" or base.value(t, RDFS.isDefinedBy), (
                f"{t}: no rdfs:isDefinedBy in the canonical file"
            )
            shapes += kind(g, t) in ["Node shape", "Property shape"]
        p = ROOT / directory / "index.html"
        page = Page()
        page.feed(p.read_text(encoding="utf-8"))
        pages[p] = page
        assert len(page.ids) == len(set(page.ids)), f"Duplicate fragment IDs in {p}"
        assert sorted(page.terms) == sorted(map(str, owned(g))), f"Missing or duplicate term cards in {p}"
        text = p.read_text(encoding="utf-8")
        assert "<dt>Definition</dt>" in text and "<dt>Usage scope</dt>" in text
    for path, page in pages.items():
        for href in page.links:
            if "://" in href or href.startswith(("mailto:", "javascript:")):
                continue
            target, _, fragment = href.partition("#")
            resolved = (path.parent / target).resolve() if target else path
            # Check generated cross-term links; legacy prose may link external build assets.
            if fragment.startswith("term-"):
                assert resolved in pages, (path, href)
                assert fragment in pages[resolved].ids, (path, href)
    manifest = build(check=True)
    saved = json.loads((ROOT / "specification/reference/manifest.json").read_text(encoding="utf-8"))
    assert saved == manifest, "Reference manifest stale"
    assert GUIDE in (ROOT / "specification/reference/index.html").read_text(encoding="utf-8"), "Reading guide stale"
    print(
        f"PASS: {total} documented terms, {shapes} named shapes, {len(pages)} modules; canonical annotations, "
        "exact generated content and fragment links verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
