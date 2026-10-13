# Private specification authoring

The catalogs and `.ttl.in` templates are build inputs, not a new public ontology or runtime dependency. Canonical downloadable Turtle retains its existing shape structure and term IRIs.

1. Find the canonical target in `manifest.json`; edit its template or a referenced catalog entry.
2. Use `rg 'constraint:pattern_ID' authoring/specification/templates` to find all consumers before changing a shared fragment. Share only identical constraints; targets and surrounding cardinalities remain local.
3. Run `python tools/_expand_specification_patterns.py --write`. The generator resolves all inputs before writing. A templated module is its expanded template, whole; the generated term annotations live in the module's sibling `<module>-doc.ttl`, which is owned by `_build_term_reference.py --enrich` and which this generator never touches. A term's `rdfs:isDefinedBy` is authored in the template.
4. Run `python tools/_build_term_reference.py --enrich` after any change to a module or to `tools/_term_editorial.py`: it rewrites every `<module>-doc.ttl` and the term reference pages. Without `--enrich` it rebuilds the pages from the RDF as it stands and changes no Turtle. Run `python tools/_build_simplification_guide.py` after changing a shared fragment.
5. After changing, adding or removing a node shape, run `python tools/_build_shape_requirements.py --write` (it regenerates `specification/req/requirements.ttl`, one requirement per node shape, from the shapes and their current annotations), then `python tools/_build_term_reference.py --enrich` once more so that `requirements-doc.ttl` and the req page follow.
6. Run `python tools/run_gates.py --strict`. Every gate is declared in `tools/gates.json`; a new `tools/test_*.py` that is not declared there fails the run. Expansion without `--write` checks freshness.

Prerelease changes may intentionally change public terms and validation behavior. The current authoring expansion must still match published RDF exactly. The archived simplification baseline remains an integrity-checked historical artifact, not a constraint on current development. Historical compatibility replay is optional: `python tools/test_release_contract.py --replay-history`.

Primitive formats preserve datatype semantics and unspecified byte order. A module's own scope note is stated once, on its ontology; a term carries a scope note only when it says something about that term. Each term retains its own definition, range and validation metadata. A register states its concepts' definitions, and a codec contract the meaning of each parameter, in the register file itself.

Run `python tools/_build_authoring_inventory.py` after changing templates. `constraint-inventory.json` distinguishes reusable property clauses/value alternatives from each consuming module's activation targets. Prefixes remain local; identical lexical fragments do not imply semantic equivalence.
