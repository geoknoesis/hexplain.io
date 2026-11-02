# Maintaining the ontology reference

The canonical Turtle files contain the authored definitions and usage notes; each module's generated labels, definitions and scope notes are in its sibling annotation graph, `<module>-doc.ttl`. The module pages and this catalog are generated from both; do not hand-edit the annotation graphs, the generated reference sections or the manifest.

Each named Hexplain resource must have a human-readable label, an English `skos:definition`, a `skos:scopeNote`, and an owning vocabulary (`rdfs:isDefinedBy`, except for the ontology itself), which is stated in the canonical file that declares the term. This includes classes, properties, controlled individuals, concepts, schemes, collections, named shapes and query prefix declarations. Anonymous property shapes and RDF lists are expanded within the owning named shape.

Use a definition to distinguish the term from neighboring terms. State units, coordinate conventions, index bases, code interpretation and profile dependencies where relevant. Scope notes describe intended usage; they do not introduce OWL restrictions. Do not add `skos:Concept` merely to use SKOS documentation properties.

Document actual axioms and constraints. Missing global domains and ranges must remain explicit. Do not manufacture a domain from a shape target, turn a class into an enumeration value, or describe a count in an OR branch as universally required. Keep validation constraints separate from derivation rules. The [reading guide](index.html#reading-guide) explains these distinctions for readers.

## Editing and regeneration

For annotations introduced by this documentation pass, update the editorial definitions in `tools/_term_editorial.py` and the scope guidance in `tools/_reference.py`, then run from the repository root:

```sh
python tools/_build_term_reference.py --enrich
python tools/run_gates.py
```

`--enrich` rewrites only the annotation graphs (`<module>-doc.ttl`); it never writes a canonical file. Annotations in the canonical files remain authoritative. Edit those original annotations directly when correcting them. A new term states its own `rdfs:isDefinedBy`; enrichment stops on a term without one. New term definitions without adequate original documentation need an editorial entry; missing definitions stop enrichment before any file is written.

For formal vocabulary or shape changes, edit the canonical Turtle, add appropriate validation fixtures and compatibility/version notes, then regenerate:

```sh
python tools/_build_term_reference.py
python tools/run_gates.py
```

`python tools/_build_ontology_docs.py` also rebuilds the complete references after generating the geospatial overview pages. `python tools/_build_term_reference.py --check` checks generated term sections without writing. The full gates additionally compare the embedded canonical RDF, verify term coverage and cross-term anchors, and verify that the annotation graphs contain only the permitted annotation predicates (`rdfs:label`, `skos:definition`, `skos:scopeNote`) about terms their module declares.

If the sibling engine is present, run `python tools/sync_spec.py` from `hexplain-tools` to refresh its bundled vocabulary resources. The SaaS's pinned engine patch must also include those resource changes. Documentation does not imply newly implemented binary decoders or broader conformance evidence.

## Sources

- [W3C vocabulary publication guidance](https://www.w3.org/TR/swbp-vocab-pub/)
- [SKOS documentation properties](https://www.w3.org/TR/skos-reference/#documentation)
- [RDF Schema](https://www.w3.org/TR/rdf-schema/)
- [SHACL](https://www.w3.org/TR/shacl/)
- [SHACL Advanced Features](https://www.w3.org/TR/shacl-af/)
