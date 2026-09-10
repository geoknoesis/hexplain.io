# Specification simplification with preserved expressiveness — implementation plan

**Status:** Partially implemented on `specification-simplification` in the isolated worktree. See [implementation evidence](../../../review-2026-09-05/simplification/index.html) for exact scope and outstanding acceptance. The detailed checklist below remains the original acceptance inventory; unchecked items are not claimed complete.

**Goal:** Reduce the effort needed to understand, author and maintain Hexplain while preserving its public vocabulary, validation contracts, reader/writer behavior and semantic output.

**Approach:** Simplify the authoring source and the explanation of existing semantics first. Keep existing public terms and convenient syntax. Use deterministic generation for repeated declarations. Introduce shared processing descriptions only after documenting their exceptions. Engine refactoring is conditional on an identified implementation need, not a prerequisite for editorial improvement.

**Repositories:** Specification and documentation in `hexplain.io`; engine verification in sibling `hexplain-tools`.

## 1. Scope and invariants

- [x] Preserve public term IRIs, classes, properties, datatype presets, registers and their meanings.
- [ ] Preserve the set of accepted and rejected descriptions in each supported validation configuration, including module-only validation, whole-family validation and explicit reuse of named shapes.
- [x] Preserve inferred RDF consequences under each documented entailment regime. A SHACL refactor is not permission to change OWL/RDFS axioms.
- [ ] Preserve evaluation order, defaults, inheritance, dependency resolution, cursor movement, bounds, errors, reader values, writer output and semantic RDF.
- [x] Preserve capability rejection. A normalization must not silently enable a previously rejected layout or codec combination.
- [ ] Retain complete per-term labels, definitions, usage scope and range information in downloadable artifacts and accessible reference pages.
- [x] Keep immutable releases unchanged. Any changed downloadable bytes require a new artifact identity; graph equivalence does not imply hash equivalence.
- [x] Leave deployment and live publication deferred and excluded from scoring, as requested by the user.
- [x] Keep independent ontology acceptance separate from implementation and test completion. Do not assign a higher score mechanically.

Do not merge these distinct concepts:

| Distinction | Behavior that must remain expressible |
|---|---|
| Ordered conditional rules / dispatch tables | First-match predicate selection versus independently contributed, uniquely keyed arms |
| Physical dimensions / semantic array dimensions | Byte addressing versus scientific meaning and coordinate interpretation |
| Cell packing width / significant sample bits | Occupied storage bits versus useful precision within a container |
| Checksum field bounds / expression bounds | Field-inclusive coverage versus expression-based half-open intervals |
| Field reference / arbitrary expression | A structural dependency usable for writer inference versus a computation that may not be invertible |
| Inherited byte order / explicit byte order | Parent-dependent interpretation versus a fixed override |
| OWL/RDFS axioms / SHACL validation | Inference versus scoped acceptance constraints |

## 2. Deliverables and file ownership

Paths marked **new** are proposed paths. Confirm current repository structure before implementation; the GDAL wave work may have advanced since this plan was written.

| Deliverable | Files or areas |
|---|---|
| Baseline and equivalence inventory | **new:** `review-2026-09-05/simplification/baseline.json`, `equivalence-matrix.json` |
| Private reusable authoring definitions | **new:** `authoring/specification/constraint-patterns.json`, `primitive-types.json`, `processing-contracts.json` |
| Deterministic expansion | **new:** `tools/_expand_specification_patterns.py` |
| Generation and equivalence gates | **new:** `tools/test_specification_patterns.py`, `test_simplification_equivalence.py` |
| Existing editorial generators | `tools/_term_editorial.py`, `_build_term_reference.py`, `_build_ontology_docs.py`, `_reference.py` |
| Published vocabulary and shapes | `specification/bddo/bddo.ttl`, `dlv/dlv.ttl`, `hexplain/core.ttl`, relevant aspect and domain modules |
| Processing documentation | `specification/processing/index.html`, `hel/index.html`, `coverage/writer-tests/index.html`, generated module reference pages |
| Existing evidence and packaging | `tools/_constraint_coverage.py`, `test_constraint_coverage.py`, `_review_candidate.py`, `_snapshot_release.py`, `test_release_contract.py` |
| Conditional engine verification | `hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt`, `FormatIRToRdf.kt`, `SerializeFormatIRToRdf.kt`, `semantic/SemanticLifter.kt`, `codegen/.../lower/Lowering.kt`; corresponding tests |

The authoring catalogs are build inputs, not new public ontology namespaces or an additional user-facing format language. Prefer extending existing generators where that avoids duplicate infrastructure.

## 3. Task 1 — Freeze the actual baseline

**Purpose:** Make equivalence assessable despite ongoing work in both repositories.

- [ ] Record each repository's revision and relevant working-tree changes; do not assume earlier review numbers describe the current tree.
- [ ] Record hashes for canonical Turtle, published metadata, shape modules, fixture corpora, processing documents and bundled engine vocabularies.
- [ ] Record validator versions, engine/runtime versions, selected shapes, inference settings and explicit target additions.
- [x] Inventory repeated constraint patterns and processing mechanisms using read-only scripts.
- [x] Separate exact repetitions from merely similar contracts. In particular, retain the narrower accepted datatype set of raster `ExtentShape` unless a separate behavior change is intentionally proposed later.
- [ ] Capture current module-only, family-wide and emitted-instance validation results, plus the applicable reader/writer/code-generation evidence.
- [x] Record unrelated files that must not be staged or modified. Use a task-scoped change set in each repository.

**Acceptance:** A second run against the same inputs reproduces the inventory and hashes. Every proposed simplification identifies the baseline artifacts and behavior it affects.

**Review observations to recheck:** The September 10 analysis found 16 copies of the same eleven-datatype union across six modules, four identical required-string `bddo:condition` constraints, and substantial repetition in generated scope notes. These are observations, not permanent acceptance thresholds.

## 4. Task 2 — Establish an equivalence gate before refactoring

**Purpose:** Prevent “simpler” from meaning less strict, less expressive or operationally different.

- [x] Define an equivalence matrix with one row per proposed transformation, its scope, preconditions, exceptions, counterexamples and test location.
- [x] For generation-only transformations, compare full expanded RDF graphs by isomorphism. Include annotations, target declarations and list structure; do not compare only selected triples.
- [x] Check repeated generation for deterministic bytes. Keep LF-normalized development checks distinct from exact release/archive byte hashes.
- [ ] Compare validation verdicts and meaningful diagnostics: focus node, result path, offending RDF term, severity, component, message and nested detail relationships. Normalize only incidental blank-node identifiers through graph structure.
- [ ] Do not ignore changed `sourceShape` or report nesting wholesale. A published helper-shape refactor that changes diagnostics is a compatibility change even if conformance is unchanged.
- [x] Replay the retained shared module corpus in pySHACL and Jena, with the original module selection and activation metadata.
- [ ] For processing changes, compare parsed values, exact integers, logical/physical extents, cursor restoration, emitted RDF, written bytes and explicit failures against the frozen implementation.
- [ ] Use independent expected-byte and mathematical vectors as well as old/new differential comparisons. Agreement between two implementations alone can preserve a shared bug.
- [ ] Add negative controls showing that the gate detects a removed bound, changed target, reversed rule order, changed default and lost writer inference.

**Acceptance:** Deliberate semantic changes fail the gate; harmless serialization changes pass graph comparison but remain visible to byte-hash checks. No baseline implementation is edited to make a differential test pass.

## 5. Task 3 — Factor repeated constraints at authoring time

**First implementation priority; depends on Tasks 1–2.**

- [x] Extract the exact repeated integer datatype alternatives into private authoring patterns. Keep datatype membership separate from positive/nonnegative bounds and upper limits.
- [x] Add patterns for genuinely identical required-string conditions, codec references and repeated size declarations.
- [x] Expand patterns into the existing published shape structure. Preserve targets, messages, bounds, cardinalities, list order and vocabulary annotations.
- [x] Reject unknown pattern names, missing parameters, unexpected arguments and ambiguous output ownership.
- [x] Keep generated regions deterministic and clearly owned by the generator. Check that regenerating an already generated candidate produces no difference.
- [x] Ensure reviewers can trace each expanded constraint to its authoring definition and each pattern to its consumers.
- [x] Retain current module loading behavior. Do not introduce an implicit network import or a new runtime helper dependency.
- [ ] Run graph-isomorphism, diagnostic-equivalence and both-validator tests before broadening the pattern catalog.

**Acceptance:** Public RDF graphs and validation behavior match the baseline; repeated authoring definitions have one source of truth. The number of published component obligations need not decrease for this task to succeed.

**Deferred alternative:** Replacing expanded constraints with public named helper shapes is not required. Assess it separately only if the additional loading and diagnostic compatibility costs are justified.

## 6. Task 4 — Separate value constraints from activation in the authoring model

**Depends on Task 3.**

- [ ] Classify constraints into reusable property rules, domain activation and domain-specific additions.
- [ ] Start with identical audio/video codec constraints, audio/image bit-depth constraints and Struct/Field size properties.
- [ ] Generate the same existing domain shape targets and local constraints from that classification.
- [ ] Add cases for properties on unrelated resources, target-only graphs, missing types, imported class hierarchies and explicitly reused named shapes.
- [ ] Document module dependencies explicitly; preserve standalone module validation by shipping all required expanded definitions.

**Acceptance:** No new global `sh:targetSubjectsOf` behavior is introduced. Domain modules become shorter to author without silently broadening or narrowing validation scope.

## 7. Task 5 — Define one value-source processing description

**Depends on Task 2; documentation first.**

- [ ] Inventory fixed, field-reference and expression forms for size, offset, repetition, dimension stride and related values.
- [ ] Describe a common resolution procedure with explicit evaluation context, availability, numeric conversion, units and error propagation.
- [ ] Add a property-family table identifying exceptions: enclosing region, sequence versus element extent, offset origin, cursor restoration, zero allowance and evaluation timing.
- [ ] Preserve a tagged distinction between literal, field reference and expression in any internal representation. Do not turn everything into HEL text.
- [ ] Document writer-inferable dependencies separately from expression constraints. Preserve local/shared length inference, crossing dependencies, empty arrays, cycles and nonconvergence rejection.
- [ ] If engine normalization is needed, test both RDF-to-IR and IR-to-RDF paths; retain original surface forms or provenance where serialization requires them.
- [ ] Add vectors for fractional/overflowing values, absent dependencies, bounded EOF, counted element extents and addressed payloads.

**Acceptance:** A reader can locate the shared rules once and find each exception in a table. Equivalent input forms retain their behavior; forms with different writer capabilities remain distinguishable. No general expression inversion is introduced.

## 8. Task 6 — Consolidate ordered-selection documentation

**Depends on Tasks 2 and 5.**

- [ ] Inventory datatype, endianness, cell-type, dimension-order, semantic-property and semantic-class rule families.
- [ ] Specify the shared first-match procedure once, including evaluation errors and the distinction between false and unavailable/invalid conditions.
- [ ] For every family, document result type, evaluation context, timing, no-match behavior, fallback and inheritance.
- [ ] Keep specialized public classes and properties. Do not introduce an unrestricted generic assignment construct.
- [ ] Keep dispatch tables outside the ordered-rule abstraction: preserve independent arm contributions, key equality, uniqueness and fallback precedence.
- [ ] Test overlapping predicates, no matches, failing conditions, explicit overrides, nested contexts and dispatch contributions from multiple graphs.
- [ ] Verify that independent cell-type and dimension-order selection remains compositional; do not replace it with a cross-product of complete layouts.

**Acceptance:** Shared prose replaces repeated explanations, while every existing family-specific behavior remains stated and tested.

## 9. Task 7 — Document encoding shorthand normalization

**Depends on Task 2.**

- [ ] Define the precise conditions under which `isEncodedWith` denotes a one-step encoding pipeline with no explicit parameters.
- [ ] Specify decode order, encode order, codec defaults, parameter handling, framing and failure propagation in one place.
- [ ] Preserve the current rejection of simultaneous shorthand and explicit pipeline declarations.
- [ ] Keep the shorthand public; retain authored RDF form or equivalent provenance where round-trip serialization exposes it.
- [ ] Compare shorthand and one-step forms using supported codecs, invalid parameters, unknown codecs, truncated input and output-budget exhaustion.
- [ ] Include a multi-step example to establish order, plus negative examples showing where a shorthand expansion is not justified.

**Acceptance:** Equivalent supported forms yield equal values, outputs and errors under the stated conditions. Unsupported behavior is still rejected. Engine deduplication is optional if documentation alone delivers the simplification.

## 10. Task 8 — Generate datatype presets from a parameter matrix

**Depends on Tasks 2–3.**

- [ ] Inventory current preset IRIs and their exact base category, width, signedness, RDF datatype and byte-order declarations.
- [ ] Encode those definitions in a private authoring matrix, with explicit exceptions for variable-width, textual and otherwise specialized types.
- [ ] Generate the same RDF definitions and a human-readable comparison table.
- [ ] Preserve an absent endianness declaration as absent. Do not substitute the platform order or a fixed order.
- [ ] Preserve named preset identities; do not add `owl:sameAs` merely because two declarations sometimes decode the same bytes.
- [ ] Verify all preset triples, labels and annotations, then test inherited/explicit byte order, signed boundaries, unsigned maxima and floating-point bit patterns.

**Acceptance:** Every existing preset remains available with the same meaning and override behavior. Adding a future preset requires a deliberate matrix entry and tests, not hand-copying several declarations.

## 11. Task 9 — Simplify the human reference without losing term detail

**Can start after Task 1; final integration depends on Tasks 3–8.**

- [ ] Put common module conventions in a prominent shared section and link each term to the conventions that apply.
- [ ] Make term-specific meaning and exceptions the primary visible text; keep full definition, scope, range and constraints accessible for every term.
- [ ] Use comparative tables for numeric families, value-source mechanisms, conditional families, byte-order presets and encoding forms.
- [ ] Keep stable term anchors, searchability, downloadable annotations and existing external links.
- [ ] If details are expandable, make them keyboard accessible and usable without custom JavaScript; ensure print/export includes the complete reference.
- [ ] Keep normative requirements identifiable. Shortening presentation must not turn a requirement into an optional example or remove an exception.
- [ ] Check representative narrow and wide layouts, keyboard navigation, anchor navigation and complete printed/reference output.
- [ ] Run HTML synchronization, documentation-term and term-reference checks against the generated pages.

**Acceptance:** A user can find both the common rule and the exact term contract without reading repeated paragraphs. All prior per-term information remains available.

## 12. Task 10 — Integrate evidence and prepare a local candidate

- [ ] Regenerate documentation and authoring outputs; verify a second generation produces no differences.
- [ ] Run `python tools/run_gates.py` from `hexplain.io` after generated artifacts and the pending review package are current.
- [ ] Recompute the component ledger when shape/corpus inputs change, then render its HTML report. Never edit coverage counts manually.
- [ ] If graph structure changes, map old and new obligations explicitly and retain the old evidence. Do not claim that fewer obligations alone means better coverage.
- [ ] Run relevant `hexplain-tools` tests for any compiler, serializer, normalization or generated-code changes; broaden to release acceptance only when those surfaces are affected.
- [ ] Replay archived compatibility corpora against archived and candidate shapes. Create a new immutable local snapshot if delivering changed artifacts; never replace an existing snapshot.
- [ ] Refresh the pending independent-review package with the authoring sources, expanded artifacts, equivalence matrix and verification logs.
- [ ] Record remaining limitations and whether each simplification is editorial, graph-preserving generation or a separately reviewed compatibility change.
- [ ] Keep publication and deployment out of this implementation. Do not report remote CI or independent acceptance unless actually obtained.

**Acceptance:** All affected gates pass on the concrete candidate, published meanings are preserved, and the before/after evidence is sufficient for an independent reviewer to assess equivalence.

## 13. Delivery order and rollback

| Milestone | Tasks | Completion criterion |
|---|---|---|
| A: Equivalence baseline | 1–2 | Reproducible baseline and a gate that detects deliberate differences |
| B: Low-risk maintenance simplification | 3–4, initial 9 | Less duplicated authoring; equivalent expanded graphs and domain activation |
| C: Clearer processing model | 5–7 | Shared explanations with explicit exceptions and behavioral evidence |
| D: Presets and reference presentation | 8–9 | Equivalent datatype definitions and complete, more navigable documentation |
| E: Candidate acceptance | 10 | Current artifacts, passing gates, compatibility replay and review package |

Deliver each task as a focused change set with its own evidence. Do not combine a semantic bug fix or a new GDAL format capability with a simplification: record it separately so equivalence remains assessable. If a candidate transformation fails equivalence, retain the existing semantics and revert that transformation rather than weakening the oracle, deleting counterexamples or changing the baseline.

## 14. Definition of done

- [ ] All seven simplification opportunities have an implemented outcome or a documented reason for retaining the current form.
- [ ] Public vocabulary, validation scope and processing behavior remain equivalent within the declared contracts.
- [ ] New authoring machinery is smaller and easier to maintain than the duplication it replaces; unnecessary abstraction has been removed.
- [ ] Complete per-term documentation and accessible navigation are retained.
- [ ] Reproducible evidence supports the changes; limitations and external acceptance remain explicit.

**Standards references:** [SHACL shape composition and reports](https://www.w3.org/TR/shacl/), [RDF Schema domain and range semantics](https://www.w3.org/TR/rdf-schema/). These inform the compatibility boundaries; they do not establish that a particular proposed rewrite is equivalent.
