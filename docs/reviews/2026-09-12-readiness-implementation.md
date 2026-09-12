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
