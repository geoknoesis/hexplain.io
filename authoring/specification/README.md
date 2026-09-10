# Private specification authoring

The catalogs and `.ttl.in` templates are build inputs, not a new public ontology or runtime dependency. Canonical downloadable Turtle retains its existing shape structure and term IRIs.

1. Find the canonical target in `manifest.json`; edit its template or a referenced catalog entry.
2. Use `rg 'constraint:pattern_ID' authoring/specification/templates` to find all consumers before changing a shared fragment. Share only identical constraints; targets and surrounding cardinalities remain local.
3. Run `python tools/_expand_specification_patterns.py --write`. The generator resolves all inputs before writing. It preserves the existing generated term-annotation suffix, which remains owned by `_build_term_reference.py --enrich`.
4. Run `python tools/_build_simplification_guide.py` and `python tools/_build_term_reference.py` after editorial changes. Ordinary reference generation does not enrich or change RDF.
5. Run `python tools/run_gates.py`. The new pattern and equivalence gates are automatically discovered. Default expansion without `--write` checks freshness.

The simplification baseline is deliberately strict: canonical UTF-8/LF text and retained fixtures must remain identical, and RDF graphs must be isomorphic. Future intentional semantic changes need a separately reviewed compatibility change; do not replace this baseline just to make a failure pass. Immutable releases are not regenerated.

Primitive formats preserve exact source formatting as well as datatype semantics. Unspecified byte order remains absent. Processing summaries document common explanations and their exceptions; they introduce no engine normalization or new fallback.

Term-page scope deduplication is deferred: the frozen baseline lacks required annotations for `bddo:separatedBy`, so its reference generator cannot complete. Existing term pages remain intact. Downloadable RDF keeps every original annotation.
