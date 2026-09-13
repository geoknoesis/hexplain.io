# Readiness implementation status

This records implementation against `2026-09-12-specification-engine-readiness.md`.
It is a partial completion record, not a release approval or a revised quality score.

## Implemented

- **E01:** dispatched child maps require known, allowed recorded struct names. Missing,
  unknown, non-string and unrelated names reject. Reports include actual evaluated
  instance counts; legitimate optional absence remains valid and reports zero.
- **E02, conformance stage:** added per-invocation work, depth, finding and cooperative
  deadline limits. Iterative traversal detects active-path identity cycles, preserves
  shared children as separate occurrences, avoids filtered list copies and checks finding
  capacity before constructing results. Cancellation/resource exhaustion is fatal.
  Constructor reachability traversal is iterative too.
- **R01, CI launch correction:** engine `gradlew` has Git mode 100644; CI now invokes it
  with Bash rather than requiring an executable bit.
- Added `hexplain-tools/docs/conformance-execution-contract.md` with limits and remaining
  trust boundaries.

## Verification

`gradlew.bat test :codegen-verify:check` completed successfully after retaining the expected
feature/struct names in construction diagnostics. All 2,074 core tests passed. The full
module XML inventory is retained in
`hexplain-tools/build/readiness-20260912/conformance-validation.json`.
Unchanged Gradle tasks may be up to date. The eight pre-existing skips remain excluded
from passing totals. New tests cover malformed provenance, work/depth/finding exhaustion,
budget reset, interruption/recovery, cycles versus shared references, deterministic deadline
expiry and optional zero-instance reporting. No production deployment or remote CI run is
claimed. No commits or pushes were performed by this implementation pass.

## Work still required

| Review task | Remaining acceptance |
|---|---|
| E01 | Consider a typed immutable parsed-tree API; metadata is not authentication |
| E02 | Separate lifting/SHACL limits; non-cooperative HEL still requires process isolation |
| E03 | Real whole-pipeline worker containment and hostile-stage recovery evidence |
| R01 | Freeze intended drafts, regenerate matching evidence, consistent pins, clean cross-platform release |
| S01 | Attributable independent review; reviewer has not been supplied |
| S02 | High-risk interaction register and parameter/target mutation adequacy |
| E04 | Executable capability matrix and declared field-scope/writer support decisions |
| E05 | Multi-stage performance, allocation/RSS baselines and measured optimizations |
| R02 | Owner license decision, dependency/advisory acceptance, attestation and shipped module scope |
| S03 | Generated evidence counts and scoped GDAL support catalog |
| GDAL roadmap | Pinned driver denominator, selected variant implementations and differential/fuzz campaigns |

Existing unrelated working-copy changes are preserved. Live namespace deployment remains
excluded by the user's instruction. Backward compatibility is not a prerelease requirement.


## Follow-through: local Linux pipeline containment

The extended containment acceptance passed nine scenarios: the existing generator and
shell deadline probes, plus normal pipeline, invalid semantic duration, truncated binary,
non-cooperative register callback, JVM heap exhaustion, bounded log flood and a subsequent
healthy pipeline request. Compilation, parsing, writing, lifting, SHACL and conformance
execute inside the container. The fixture uses an explicit decimal value expression for
duration; its original raw-byte mapping correctly failed the selected semantic shape.

Container logs rotate at a 1 MiB setting and retained evidence is capped to the final 64 KiB.
Docker supervisor commands have finite timeouts; cleanup runs in finally. Verification found
no remaining acceptance containers. The generated-code verification gate also passed after
staging the new acceptance executable. Release CI now stages that executable before its
Linux probe. No hosted CI run or deployment is claimed.

[Retained containment evidence](2026-09-12-pipeline-containment.json) includes exact staged
JAR hashes, pinned container image, limits, stage markers and elapsed times. These are
acceptance timings, not calibrated performance baselines. E03 is strengthened but remains
scoped: this is not every-stage hostile-input, arbitrary-codec or deployed-load certification.
E05 performance benchmarks and the other open rows above remain outstanding.


## Follow-through: initial multi-stage performance evidence

Implemented a forked JVM benchmark and diagnostic CI workflow. Three forks completed 11
workloads and 6,600 timed samples, with per-fork latency percentiles, current-thread allocation,
GC counts, exact artifact hashes and raw samples. See [the baseline](2026-09-12-performance-baseline.md).
E05 remains partial: the synthetic baseline identifies compilation/SHACL as investigation
priorities, but does not close large-format, generated execution, peak RSS or concurrent-load
performance acceptance. No speculative runtime optimization was applied.


## Follow-through: nested and generated performance

The benchmark now has 27 workloads, including four encoded nested fixtures through the
interpreter and generated codecs. Three forks completed 16,200 timed samples and all
fixture-byte prechecks. [Results and limits](2026-09-12-nested-generated-performance.md).
Generated measurements include reflective dispatch. This closes the absence of any measured
nested/generated execution examples, but not broad performance or production-load acceptance.


## Memory measurement and rescore

Added a tested subprocess RSS monitor and completed three monitored 27-workload forks.
The same readiness rubric now scores the engine 9.0 (previously 8.6) and specification 9.0
(unchanged). [Detailed rescore and remaining acceptance](2026-09-12-readiness-rescore.html).
Sampled RSS is explicitly a lower bound on process peak; no production performance claim
is inferred. No runtime optimization or release commit was made by this follow-through.

## Follow-through: bounded semantic lifting

Added `LiftingLimits` for work, recursive depth, emitted distinct triples and cooperative
deadlines. Active-path cycles reject, while shared children retain their separate semantic
paths. A per-invocation worker resets all budgets and closes partial models on failure.
Successful models detach their construction budget and remain editable without retaining
the profile/input through the budget wrapper. Processing helpers expose the limits.

Regression coverage includes cycle/shared-child behavior, graph-cap failure and reset,
caller mutation after success, depth/work exhaustion and interruption/recovery. An initial
graph-factory substitution changed Jena literal matching; the implementation now uses the
original default-model graph, and all semantic tests pass. This is an additional scoped
E02 mitigation: total literal byte limits and hard expression/SHACL deadlines remain open.
See `hexplain-tools/docs/semantic-lifting-limits.md` for the supported contract.

Final lifting validation: the complete engine/generated-code command passed. 3,027 tests passed, 8 skipped, zero failures/errors. [Module counts](2026-09-12-lifting-validation.json). Unchanged tasks may be up to date. No commit or push was performed.


## Literal byte budget and updated score

Added cumulative UTF-8 literal-byte accounting and binary-to-hex preallocation checks,
with direct canonical nibble encoding. All 2079 core tests passed. Engine readiness is now
9.1/10 under the unchanged rubric; specification remains 9.0. [Rescore](2026-09-12-readiness-rescore.html).
No fresh throughput claim, release commit or deployment is implied.

## Commit and lifecycle cleanup follow-up

The readiness implementation was committed and pushed as engine 14ce529 and specification
reports 5cef87d. Earlier uncommitted statements describe those checkpoints. Unrelated drafts
remain separate.

Engine follow-up d95bf28 closes temporary profile models owned by the stream/string APIs and
closes emitted graphs when validation throws. Caller-owned profiles and successful graphs
retain their ownership. The targeted semantic and instance-validation command passed after
an incremental compiler memory failure was resolved with a single-worker, non-incremental,
in-process compilation using a 768 MiB heap.

Remote engine CI run 34716273861 did not start its job: GitHub reported failed account payments
or an insufficient spending limit. No hosted test success or billing change is claimed.

## Explicit validator and result ownership

InstanceGraphValidator now closes its owned vocabulary/shape models, rejects calls after
closure, and coordinates close with concurrent validation using a read/write lock. Module
parse failures and failed validator preparation close temporary models; copying the input
graph now occurs inside its cleanup block. InstanceValidationResult and ValidatedSemanticGraph
expose close operations for their owned report/emitted graphs, while caller inputs stay open.
The benchmark and acceptance callers use these lifetimes.

Ownership regressions verify caller/result separation, repeated validator close, rejection
after close and successful validation after a preceding report was closed. The targeted
semantic/instance suites and acceptance/benchmark source compilation passed. See
hexplain-tools/docs/semantic-model-ownership.md. This follow-up is uncommitted; historical
performance measurements are not re-labelled as measurements of these cleanup changes.

## Extraction command and TIFF model cleanup

The PNG/TIFF commands now close loaded profiles and emitted graphs in finally blocks,
including parse and output-write failures. PNG also closes its profile stream. The shared
TIFF processor closes the compiler profile copy and temporary directory graph, and closes
partial output when extraction fails. Caller-owned profiles and successful results remain
open. A regression verifies caller profile preservation across successful extraction,
output disposal and invalid-offset failure.

The targeted semantic and instance-validator suites pass (43 tests, no failures or skips);
git diff --check passes. These changes remain uncommitted. This is lifecycle correctness
evidence, not a new performance benchmark or full release verification; scores stay unchanged.

## Profile loading and description-validator ownership

ProfileLoader closes partial profiles on parsing/validation failure and disposes internal
conforming reports. Description validation closes its temporary data model and validator.
ShaclProfileValidator now owns a shapes snapshot, supports idempotent close, rejects use
after close, and serializes validation with close. Boolean conformance checks dispose their
reports; returned reports and exception diagnostics remain caller-owned.

The RDF and semantic suites passed: 1335 tests, 0 failures,
0 errors, 0 skips. New regressions cover independent shapes ownership,
reports surviving validator closure, repeat validation and caller input preservation during
success and setup failure. git diff --check passes. Changes remain uncommitted; scores and
historical performance measurements are unchanged.

## Semantic lifecycle rescore ? 12 September 2026

Specification: **9.0/10**. Engine: **9.1/10**. Existing weights and dimension scores
remain unchanged. The lifecycle fixes strengthen this assessment but do not establish a
new performance, release or independent semantic acceptance milestone.

Bundle processing now closes temporary part/CONSTRUCT graphs and failed working graphs.
A new counterexample exposed caller-profile mutation (14 triples became 3,782); bundle
parts now compile from owned copies. The corrected regression and semantic/profile ownership
suites pass: 40 tests, zero failures/errors/skips. The preceding RDF/semantic run passed
1,335 tests before this bundle change; it is not a full latest-candidate release run.

Remaining priorities are clean cross-platform release acceptance with consistent artifact
pins, representative performance and retained-memory measurements, whole-stage SHACL/HEL
containment, and independent ontology/semantic interaction review. Bundle aggregation and
its CONSTRUCT query still need aggregate request budgets; per-part lifting limits do not
bound the complete bundle. Direct generic compilation still enriches its supplied profile;
the new copy isolation applies specifically to bundle processing. No performance gain is
claimed from adding copies. Live hosting remains excluded from scoring. Changes are uncommitted.

## Bundle aggregate admission and graph limits

Added optional BundleLimits: cumulative part/input/profile admission, per-graph distinct
triple caps, and shared graph-write work limits. CONSTRUCT output is streamed into a bounded
separate graph. Tests cover cumulative repeated inputs/profiles, exact admission boundaries,
part/triple/write rejection, successful reuse after failures and caller output edits.
All three BundleProcessor tests pass; diff checks pass. This supersedes the absence of bundle
aggregation caps in the preceding checkpoint, but aggregate decoding and hard query/CPU limits
remain open. See hexplain-tools/docs/bundle-execution-limits.md for precise exclusions.
Scores remain specification 9.0 and engine 9.1; changes remain uncommitted.

## Bundle literal budget and adversarial checks

BundleLimits now caps cumulative UTF-8 literal lexical bytes across assembly and CONSTRUCT
graphs (64 MiB default). Repeated writes to an existing triple consume work without charging
literal storage twice in that graph. Insertion into a second graph charges again. Counting
avoids a temporary byte array; rejection occurs before insertion, not before producer allocation.
Six bundle tests pass, including exact multibyte/supplementary boundaries, shared duplicate-write
exhaustion, interruption flag preservation and detached output mutation. The initial Unicode
fixture was corrupted by shell encoding and corrected to explicit Kotlin escapes before the
successful run. Hard query deadlines and aggregate decoded-byte limits remain open. Scores
stay specification 9.0 and engine 9.1; this work remains uncommitted.

## Bundle executable-query boundary and rescore

The bundle lifting query now comes exclusively from the bundled vocabulary, isolated from
caller sh:rule/sh:construct triples. Missing bundled definitions fail explicitly; the duplicated
fallback query is removed. Seven bundle tests pass, including a caller-authored CONSTRUCT
that must not execute. This regression establishes the corrected boundary; no claim is made
that the previous graph's nondeterministic property selection always selected injected data.

Scores remain specification **9.0/10**, engine **9.1/10**, using unchanged weights. Recent
ownership, admission and materialization fixes strengthen the candidate, but hard query limits,
aggregate decoding budgets, representative performance, clean release acceptance and independent
ontology review remain incomplete. Live hosting remains excluded. Latest verification is the
seven-test bundle suite and diff checks, not a complete release run. Changes are uncommitted.

## Specification bundle semantics clarification

Added a linked bundle execution contract documenting exact role/aspect selection, preservation
of conflicting values, duplicate graph semantics, explicit membership without inference,
non-recursive facet copying, trusted query selection and separate validation/resource stages.
Seven new RDFLib competency cases compare exact output graphs and preserve their inputs.
These complement the Kotlin execution tests; they are not an independent ontology review or
a claim of dual-SHACL-engine acceptance. Vocabulary/shape RDF is unchanged. Scores remain
specification 9.0 and engine 9.1 pending broader acceptance.

## Technical-only acceptance implementation

Independent human ontology review is no longer a scoring requirement. The unchanged rubric
uses reproducible semantic/differential tests and independent implementations instead; live
hosting remains excluded. See 2026-09-12-technical-acceptance-plan.md for completion criteria.

Gate reports now distinguish running, failed and completed suites, list/hash selected gate
scripts, record environment/timestamps and replace results atomically. Fresh strict filtered
acceptance passed 3 gates with zero skips/failures: runner behavior, seven bundle lifting
cases and 1,165 two-sided component obligations. This is not a full release run or proof of
complete term-interaction coverage. Scores remain specification 9.0 and engine 9.1.
