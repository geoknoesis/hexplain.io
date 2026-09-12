# Hexplain specification and engine: production readiness review

Date: 12 September 2026. Scope: hexplain.io `21ca190` and hexplain-tools `ef06cf9`, including the explicitly uncommitted working-copy changes visible during review. No implementation changes made. Live hosting is excluded from scoring, as requested. Backward compatibility is not a prerelease acceptance requirement.

## Decision and scores

The specification is a strong release candidate with outstanding semantic acceptance and reproducibility work. The engine is suitable for evaluation within its documented subset; unrestricted untrusted production use is not yet justified by the reviewed evidence. Neither currently earns 9.5 under this review's production-readiness rubric.

| Dimension | Weight | Specification | Engine |
|---|---:|---:|---:|
| Correctness and semantic precision | 30 | 28.5 | 27 |
| Architecture, usability and supported versatility | 20 | 19 | 18 |
| Validation and independent evidence | 20 | 18.5 | 18.5 |
| Performance and resource behavior | 15 | 12 | 10.5 |
| Reproducible release and maintainability | 15 | 12 | 12 |
| Total | 100 | **90 / 100 (9.0)** | **86 / 100 (8.6)** |

These are review judgments, not statistically measured quality or test-pass percentages. This rubric explicitly includes performance and release evidence and should not be compared numerically with older rubrics without reweighting. Specification performance means validation/build scaling and consumer cost. Engine performance includes execution latency, allocation and scaling. A missing measurement is an evidence gap, not proof of slow execution. Scores are provisional because the tested working copy is not identical to the pushed commits.

A proposed 9.55 acceptance target is 29.5/30 correctness, 19/20 design, 19.5/20 validation, 14/15 performance and 13.5/15 release. Meeting the tasks requires reassessment; completing a checklist does not automatically establish those scores.

## Evidence and review limits

Source inspection covered conformance traversal, runtime budgets, generated-code boundaries, release inventory and containment scripts, workflows, constraint measurement, ontology review status and capability documentation. This was a targeted code review, not an exhaustive audit of every function or a new full benchmark/fuzz campaign.

The preceding integration run recorded 3,019 engine tests passed, eight skipped and zero failures/errors. Some unchanged modules used Gradle up-to-date results. Specification acceptance comprised 42 passing gates across an initial run and targeted freshness rechecks; this was not one clean full release run. The coverage regeneration recorded 1,291 cases and positive/negative evaluation evidence for all 1,165 inventoried constraint components. Those numbers do not prove every interaction is correct. The full constraint ledger is not claimed to have identical component-level instrumentation in two engines.

This review freshly ran `python tests/release/verify_spec_evidence.py --spec-root D:/work/hexplain.io`: 14 source hashes matched. It also ran `python tests/release/test_artifact_manifest.py`: 12 tests passed. These checks do not certify the older specification revision pinned by release CI, artifact publication or hosted CI. Existing reports describe a hosted billing failure; this review did not query its current status.

Source: [integration evidence](2026-09-12-branch-worktree-inventory.md). Existing drafts and generated candidate files remain dirty and were not committed by this review.

## Findings, ordered by production impact

### E01 — High: recorded dispatch provenance can fall back silently

At `core/src/main/kotlin/io/hexplain/core/conformance/ConformanceEngine.kt:112`, evaluation loops over the instances found for each constraint scope. At `:277`, `structNameOf` accepts a known recorded type, but a missing or unknown recorded type falls back to the statically declared type. A dispatching field declared as bytes can therefore contribute no selected-struct instance. An unconstrained empty instance list produces no findings. This is a source-confirmed control-flow risk for caller-supplied or modified trees; it is not a demonstrated failure of normal parser-produced metadata. The current comments promise stronger checking than this fallback implements.

**Task:** require valid provenance on dispatched child maps; check that the recorded type belongs to the field's allowed arms/default. Reject missing/unknown/impossible types explicitly. Distinguish an absent optional instance from an unresolvable present instance. Prefer a typed parsed-tree/provenance object over a boolean assertion by callers.

**Acceptance:** add regression vectors for missing metadata, unknown type, known-but-unrelated type, each valid dispatch arm, fallback and repeated nested maps. A malformed present child must not return a conformant report. Retain legitimate zero-instance optional constraints, but report evaluated-instance counts.

### E02 — High: conformance has no independent work or output bound

`ConformanceEngine.kt:112–139` indexes the tree, evaluates assertions and accumulates findings; `:232` recursively collects instances. This API accepts maps directly and does not accept a stage budget. Parser limits do not protect a caller-supplied deeply nested or cyclic map, a huge finding set or an expensive HEL expression. This is a visible API/resource-bound gap, not a newly executed denial-of-service demonstration.

**Task:** introduce conformance limits for visited instances, nesting, evaluations, findings and elapsed time; use iterative traversal with active-path identity detection. Preserve legitimate repeated references. Propagate cancellation/resource exhaustion as fatal stage failure rather than ordinary rule discrepancy. Bound semantic lifting and SHACL execution separately as well.

**Acceptance:** cyclic/deep trees, broad repetitions, many findings, cancellation and deliberately expensive assertions terminate with explicit limits; no partial success. Verify per-invocation reset and normal nested dispatch behavior.

### E03 — High: containment evidence covers only a narrow execution path

`tests/release/containment_acceptance.py` runs one normal generator invocation and kills a shell busy loop in a constrained container. It correctly labels its limits. `ParseLimits.kt` and `runtime-kotlin/.../ReadBudget.kt` are cooperative budgets. Neither those budgets nor this drill demonstrate every compile/parse/write/lift/conformance/custom-codec stage under hard limits.

**Task:** run the real complete request pipeline inside a supported worker boundary with CPU, memory, process, network, filesystem, output and wall-clock controls. Keep the embedded library usable, but document its trusted-use contract separately.

**Acceptance:** hostile inputs in each stage, runaway custom codec, memory exhaustion and output flood are terminated; workers and temporary files are reclaimed; a following healthy request succeeds. Retain Linux evidence for the supported deployment model. Hosted namespace rollout remains outside this score.

### R01 — High: locally verified draft and releasable candidate differ

Both repositories have uncommitted changes; engine tests include untracked profile tests, and specification tooling, dependency/workflow edits and generated evidence are dirty. Passing these files does not prove the pushed main revisions reproduce the same result. `tests/release/artifact_manifest.py` correctly rejects a dirty candidate. Engine release CI pins specification `7320e629...`, which is different from the reviewed main; this is not itself proof that the pin is invalid.

**Task:** classify and commit the intended release sources and their evidence together, update compatibility pins deliberately, then build from fresh checkouts and empty dependency caches. Verify the exact pinned graph/source contract, not simply the newest branch name. Separate unrelated paper/design drafts from release inputs.

**Acceptance:** clean Windows/Linux candidate runs, strict mandatory gates with declared skips only, artifact inventories, vocabulary hashes, independent consumers and generated-code consumers all identify the same immutable candidate. Resolve hosted execution/access restrictions if still present. Keep failed attempts visible.

### S01 — Medium: independent semantic acceptance remains absent

`specification/ontology-review/review-manifest.json` explicitly has null reviewer/decision and unreviewed modules. Automated coverage is substantial, but does not supply independent ontology acceptance.

**Task:** obtain an attributable review of the frozen candidate by an ontology reviewer and relevant binary/geospatial domain reviewers. Review every module, with deeper attention to numeric value spaces, identity versus equality, units, scope, bit ordering, compound ownership and geospatial interpretation.

**Acceptance:** module decisions, reviewed hashes, concrete objections, resolutions and independent rechecks. Do not manufacture a reviewer or equate this assistant review with external acceptance.

### S02 — Medium: component coverage is not interaction or mutation adequacy

`tools/_constraint_coverage.py` records actual component evaluations; `two_sided` intentionally permits empty-value success for cardinality. The review instructions correctly disclaim proof of all parameter combinations. Preserve that distinction.

**Task:** add an interaction register for bit order × endian × stride × extent, dispatch × repetition × regions, compound membership × identifiers × security scope, and CRS axis order × units × masks/nodata. Mutate constraint parameters and targeting rules, not only instance data. Replay portable semantic expectations in both pySHACL and Jena with explicit inference policy and normalized report paths.

**Acceptance:** every declared high-risk interaction has a real-format positive example and minimal negative counterexample; each applicable non-equivalent constraint mutation is detected or independently justified. Report mutation adequacy separately from existing component evaluation coverage. Preserve the zero-unevaluated-component gate.

### E04 — Medium: scope is explicit, but specification and execution are not fully symmetric

`docs/capability-matrix.md` lists unsupported packed/chunked access, writer combinations and vector families. `ConformanceEngine.kt:58` rejects field-scoped constraints even though vocabulary/shapes allow them. These explicit rejections are strengths, not silent corruption. A 9.5 bounded release need not implement every describable feature, but it must not imply universal execution.

**Task:** generate the public capability matrix from executable feature checks spanning RDF/HDL, IR, interpreter reader/writer, generated reader/writer, accessors, semantic lifting and conformance. Implement field-scoped conformance if included in the release contract; otherwise expose it as an explicit unsupported capability before execution. For expanded writers, define framing and solvable length dependencies before implementation.

**Acceptance:** each supported cell has independent bytes/values and failure-boundary tests; each unsupported cell fails with a stable feature diagnostic. Add nesting/composition cases rather than isolated feature-only tests. Define supported tiers in the release manifest.

### E05 — Medium: performance evidence is not broad enough to justify optimization claims

`hdl/.../bench/MetaparserBench.kt` is an opt-in four-fixture parser timing test with warmup and generous ceilings; it was skipped in the integration run. It does not measure allocations, compilation, writers, lifting or SHACL. `ConformanceEngine.collectInstances` builds per-struct lists and uses `filterIsInstance`, introducing materialization worth measuring, not automatically a demonstrated bottleneck.

**Task:** establish reproducible benchmarks for compile, parse, write, generated execution, lifting and validation. Cover small latency-sensitive input, large contiguous arrays, deeply nested records, compressed blocks and large geometry collections. Record throughput, p50/p95/p99, allocations, peak RSS, GC and cold/warm behavior on fixed hardware/runtime settings.

**Acceptance:** published repeatable baselines and workload-specific budgets, with regression tolerances derived from run variance. Profile before changing code. Candidate optimizations include bounded compiled-profile caching keyed by all source/options hashes, streaming conformance traversal, reducing intermediate collections and immutable byte slices with explicit ownership. Preserve exact arithmetic, bounds checks and cancellation; compare before/after results and memory.

### R02 — Medium: integrity inventory is not complete supply-chain acceptance

The artifact tool explicitly states it is not an SBOM or provenance attestation. `LICENSING.md` leaves files without existing grants awaiting an owner decision. Release workflows use version tags for third-party actions.

**Task:** resolve licenses and third-party notices with the owner; generate JVM/dependency and artifact inventories, perform an advisory review, pin workflow actions to reviewed immutable revisions, and attest the built candidate. Include all modules claimed in the release: current library inventory has six modules, so decide explicitly whether query/query-fuseki are shipped products or excluded components.

**Acceptance:** each distributed file has a recorded license basis, dependencies and notices; no untriaged release-blocking advisories; consumer tests exercise every shipped product. Maintain an update process for pinned dependencies/actions rather than freezing indefinitely.

### S03 — Medium: capability documentation can drift from executable evidence

The engine capability matrix still cites 112 WKB cases while integration records a 136-case corpus. These counts may describe different scopes; the documentation does not make the relationship sufficiently clear. File totals such as 611 raster matches cannot establish a driver coverage percentage.

**Task:** derive counts and links from a single versioned evidence catalog, separating historical, current, native, adapter and external-library cases. Give each profile a feature/variant support contract and machine-readable exclusions.

**Acceptance:** documentation checks reject stale counts and missing evidence. Every claimed support statement identifies profile hash, runtime/backend, fixture scope and independent oracle. Preserve historical reports as dated snapshots.

## GDAL versatility roadmap

Use GDAL's separate [raster](https://gdal.org/en/stable/drivers/raster/index.html) and [vector](https://gdal.org/en/stable/drivers/vector/index.html) driver catalogs as inventory sources. Their entries include different storage and service models; complete GDAL coverage is not equivalent to implementing a finite list of binary codecs.

1. Freeze the denominator: selected GDAL revision/build, available drivers, optional dependencies and intended operations. Classify each as native binary, text, container/database, remote service or delegation. Track supported, partial, rejected and untested separately.
2. Prioritize reusable capability families: indexed/chunked storage; vector geometry plus attributes; multidimensional arrays; compression/filter pipelines; masks/georeferencing. A native profile and a library adapter must remain distinct claims.
3. Expand comparisons beyond pixels: integer interpretation, NaN policy, axes, units, affine transforms, CRS identity, nodata versus masks, scale/offset, geometry dimensions, empty values, attribute nulls, encoding and feature identifiers.
4. Pin upstream fixture licenses and hashes, deduplicate inputs and retain generated edge cases. Independently inspect every rejection; preserve the signed-24-bit datatype difference as an exact non-pass, not a broad exclusion.
5. Add seeded property-based and mutation fuzzing across interpreter/generated readers and writers, with independent oracle comparisons and persisted minimized failures. Publish campaign duration, seeds, explored scope and exclusions. A round trip alone can preserve a shared mistake.

Acceptance for each promoted format variant: positive decode vectors, malformed/truncated boundary vectors, exact independent value/semantic comparisons, resource-limit tests and writer interoperability where write support is claimed. No requirement to complete all GDAL drivers before a well-scoped 9.5 release.

## Specification design and author experience tasks

- Preserve the current modular model and simplify duplicated author-facing concepts only where equivalence is established. Prerelease breaking changes are allowed; migration shims are not required by this review.
- Make normative definitions, non-normative examples and implementation subset notes visually and structurally distinct. Every relevant term should identify label, definition, usage scope, domain/range where meaningful, units, constraints and a real use case; do not invent range axioms merely to fill documentation fields.
- Provide small complete profiles that progress from scalar fields to dependent lengths, bounded nesting, dispatch and semantic mapping, with their compiled form and negative diagnostics. Keep one canonical source and mechanically verify alternate representations.
- Document how consumers choose shapes, supply vocabulary context and detect zero applicable targets. SHACL validates data against a selected shapes graph; a true result is not automatically application-level certification. See [W3C SHACL validation and reports](https://www.w3.org/TR/shacl/#validation).
- Benchmark the full family and selected-module validation at increasing graph sizes; check repeated-call memory and offline import behavior. Compile/cache safely only after measuring benefit and verifying cache invalidation.

## Execution order and release exit criteria

| Order | Owner role | Deliverable | Completion gate |
|---|---|---|---|
| 1 | Engine maintainer | E01 provenance and E02 conformance limits | Counterexamples reject; valid pipelines retain results |
| 2 | Release maintainer | R01 frozen candidate and consistent pins | Clean strict cross-platform acceptance, all shipped consumers |
| 3 | Engine/platform maintainer | E03 complete worker containment | Real-stage hostile requests bounded; recovery verified |
| 4 | Ontology maintainer + independent reviewers | S01/S02 semantic decisions and interactions | Attributable review, mutation/interaction corpus, no unresolved high findings |
| 5 | Engine/performance maintainer | E05 measured baselines and optimizations | Declared latency/memory budgets met with reproducible evidence |
| 6 | Engine/spec maintainers | E04/S03 executable capability contract | Every supported claim linked to evidence; unsupported behavior explicit |
| 7 | Repository owner/release maintainer | R02 distribution approval and supply chain | License basis, advisory disposition, integrity/provenance, release manifest |
| 8 | Format maintainers | Selected GDAL family expansion | Per-variant differential and resource acceptance |

A 9.5+ release should have no unresolved high correctness/resource findings in its declared scope, a reproducible committed candidate, independent semantic acceptance, explicit capability limits, measured performance and releasable artifacts. Broad GDAL coverage is a parallel roadmap with a published denominator. Live hosting is deliberately not a scoring gate here. This review does not deploy, alter licenses, commit drafts or change implementation.
