# Hexplain readiness: implementation rescore

12 September 2026. This is a delta review of the current working copies against the
[detailed review](2026-09-12-specification-engine-readiness.md), using the same rubric.
Live namespace hosting remains excluded. Prerelease backward compatibility is not required.

## Scores

| Dimension | Weight | Specification | Engine |
|---|---:|---:|---:|
| Correctness and semantic precision | 30 | 28.5 | 29 |
| Architecture, usability and supported versatility | 20 | 19 | 18.5 |
| Validation and independent evidence | 20 | 18.5 | 19.5 |
| Performance and resource behavior | 15 | 12 | 12 |
| Reproducible release and maintainability | 15 | 12 | 12 |
| Total | 100 | **90 / 100 (9.0)** | **91 / 100 (9.1)** |

Engine rises from the initial 8.6 to 9.1 (previous checkpoint: 9.0) because concrete conformance defects were addressed and resource/
performance evidence expanded. Specification remains 9.0: engine benchmarks do not establish
independent ontology acceptance or new semantic coverage. These are reviewer judgments,
not test-pass percentages. Scores apply to the dirty working candidate, not an already
released artifact. Neither component is yet demonstrated above 9.5.

## Implemented improvements supporting this score

- Present dispatched child maps now require known, allowed recorded struct provenance;
  invalid metadata cannot silently eliminate constraint evaluation.
- Conformance traversal and constructor reachability use explicit stacks. Active-path cycles
  reject; shared children remain separate occurrences. Work, depth, findings, interruption
  and cooperative deadlines are bounded. Reports expose actual evaluation counts.
- Nine local Linux container probes passed: normal generator, shell deadline, full normal
  pipeline, invalid semantics, truncation, non-cooperative callback, heap exhaustion, output
  flooding and a healthy request afterward. No acceptance containers remained.
- Benchmarks expanded from four opt-in parser fixtures to an additional 27 synthetic stage
  workloads, including interpreter/generated nested compression. Three-fork runs retain
  16,200 timed samples, allocation/GC data and exact artifact hashes. Generated measurements
  include reflection. This establishes measurements, not a throughput improvement.
- The performance supervisor now samples single-JVM RSS at 50 ms intervals. Three tests
  verify memory observation, failure rejection and timeout termination. RSS is a sampled
  lower bound on peak, not an exact maximum or a stage-specific retained-heap measure.
- Linux CI invokes the non-executable Gradle wrapper through Bash. Release CI stages the
  expanded containment executable. A manual diagnostic performance workflow is available.

## Verification boundaries

The prior complete engine verification recorded 3,024 passed and eight explicitly skipped
tests. Generated-code verification passed again after the benchmark additions, and the
expanded staging build compiled generated codecs against runtime-kotlin alone. This rescore
does not claim a new complete repository test run or hosted workflow acceptance.

[Implementation record](2026-09-12-readiness-implementation.md),
[containment evidence](2026-09-12-pipeline-containment.json),
[nested/generated baseline](2026-09-12-nested-generated-performance.md).

## What still prevents 9.5+

| Priority | Deliverable | Acceptance criterion |
|---|---|---|
| 1 | Release candidate consistency | Commit the intended source and evidence together; reconcile exact cross-repository pins; pass clean Windows/Linux builds and every shipped consumer. Existing draft tests/tooling are not equivalent to published artifacts. |
| 2 | Semantic acceptance | Independently review the frozen ontology candidate and resolve decisions; deepen high-risk term interactions and constraint-parameter mutations. Component evaluation coverage is not semantic completeness. |
| 3 | Whole-stage resource guarantees | Bound lifting/SHACL work and emitted graph size; exercise hostile inputs in each real stage and deployed worker recovery/load. The local register attack does not certify every codec or expression. |
| 4 | Representative performance and optimization | Add large real profiles/geometry/high-compression data, direct generated calls and concurrent runs. Profile compilation/SHACL before adding bounded caches or reducing graph copies. Demonstrate correctness and resource behavior before/after any change. |
| 5 | Executable support contract | Generate backend/feature coverage from actual tests, reconcile historic fixture counts, and distinguish describable IR from executable accessors/writers. Safe rejection remains valid for excluded features. |
| 6 | Distribution approval | Resolve missing license grants, dependency advisory review, shipped module scope and artifact provenance. Owner/reviewer decisions remain outstanding. |

No license was chosen on the owner's behalf, no independent review was invented, and no
deployment is claimed. The work remains uncommitted. Further score increases should follow
new acceptance evidence, not simply more tests or larger file counts.


## Fresh memory measurement

All three monitored forks completed all 27 workloads (16,200 timed samples total).

| JVM fork | Sampled peak RSS (MiB) | RSS samples |
|---|---:|---:|
| 1 | 340.7 | 491 |
| 2 | 341.0 | 418 |
| 3 | 339.2 | 392 |

RSS includes the JVM, native allocations, warmup and all stages with a fixed 512 MiB heap setting.
It is not the heap-size setting, retained heap, an exact peak, or a production service budget.
[Memory and timing results](2026-09-12-rss-performance.json) ? [Raw evidence](2026-09-12-rss-performance.zip).


## Latest resource-bound improvement

Semantic lifting now limits cumulative UTF-8 literal lexical bytes (64 MiB default), in
addition to work, depth and triple counts. Binary-to-hex output is size-checked before
allocation and uses direct nibble encoding. Tests cover UTF-8 multibyte/supplementary and
malformed-surrogate counting, exact budget boundaries, and canonical hex output.
The full core suite passed: **2079 tests, zero failures/errors/skips**.
[Latest validation counts](2026-09-12-literal-budget-validation.json).

The +0.1 engine adjustment credits strengthened correctness/resource-bound regression evidence;
performance points have not increased. Earlier benchmark and containment artifacts remain
historical evidence for their recorded JAR hashes; they were not rerun against these literal
changes. No throughput improvement is claimed. The new byte budget excludes IRIs, object
overhead and intermediate expression allocations; hard whole-request limits remain necessary.
