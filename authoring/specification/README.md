# Private specification authoring

The catalogs and `.ttl.in` templates are build inputs, not a new public ontology or runtime dependency. Canonical downloadable Turtle retains its existing shape structure and term IRIs.

1. Find the canonical target in `manifest.json`; edit its template or a referenced catalog entry.
2. Use `rg 'constraint:pattern_ID' authoring/specification/templates` to find all consumers before changing a shared fragment. Share only identical constraints; targets and surrounding cardinalities remain local.
3. Run `python tools/_expand_specification_patterns.py --write`. The generator resolves all inputs before writing. It preserves the existing generated term-annotation suffix, which remains owned by `_build_term_reference.py --enrich`.
4. Run `python tools/_build_simplification_guide.py` and `python tools/_build_term_reference.py` after editorial changes. Ordinary reference generation does not enrich or change RDF.
5. Run `python tools/run_gates.py`. The new pattern and equivalence gates are automatically discovered. Default expansion without `--write` checks freshness.

Prerelease changes may intentionally change public terms and validation behavior. The current authoring expansion must still match published RDF exactly. The archived simplification baseline remains an integrity-checked historical artifact, not a constraint on current development. Historical compatibility replay is optional: `python tools/test_release_contract.py --replay-history`.

Primitive formats preserve datatype semantics and unspecified byte order. Shared scope notes appear once per module, with a link from every affected term; all original annotations remain in RDF. Each term retains its own definition, range and validation metadata.

Run `python tools/_build_authoring_inventory.py` after changing templates. `constraint-inventory.json` distinguishes reusable property clauses/value alternatives from each consuming module's activation targets. Prefixes remain local; identical lexical fragments do not imply semantic equivalence.
