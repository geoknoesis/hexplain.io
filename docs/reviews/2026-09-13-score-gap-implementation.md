# Score-gap implementation record, 13 September 2026

Work against the review of what prevents a 9.5+ score. Scope is both repositories: the engine
(`hexplain-tools`) and this specification repository. Each item below is either implemented with a
test that failed first, or listed as not done. No score is claimed here; the changes are evidence
for a rescore, not a rescore.

## Engine correctness

### The compiler mutated its caller's profile model

`RdfToIrCompiler.compile()` read the bundled `bddo.ttl` **into the model the caller supplied**.
Three defects followed from one line:

- the caller's model grew by 2,168 triples per compile, visibly and permanently;
- a profile model shared between request threads was written to without synchronisation;
- 218 KB of Turtle was parsed on every compile — once per bundle part, so up to
  `BundleLimits.maxParts` (1,024) Turtle parses in a single admitted request.

The concurrency defect was not theoretical. The test that exposed it — eight threads compiling one
shared profile — failed with `ArrayIndexOutOfBoundsException: Index -10 out of bounds for length 19`
thrown from inside Jena's in-memory graph: a corrupted index, not a clean error.

Compilation now runs against a read-only union view (`BundledVocabulary.compilationView`) of the
caller's model and one process-wide parsed copy of the vocabulary. Nothing is copied and nothing is
written. `CompilerModelOwnershipTest` covers caller-model size after compile and after lifting,
repeated compiles, the eight-thread concurrent compile, and that the vocabulary is parsed once.

### The bundle lifting query had no deadline

`processBundle` bounded admission, graph writes, triples and literal bytes — all of which are only
consulted when a triple is *added*. A CONSTRUCT that joins expensively while emitting little was
therefore unbounded. `BundleLimits.maxQueryMillis` (default 30 s) now bounds it, measured from
entry to `processBundle` rather than from query execution: part parsing and vocabulary loading
spend the same budget, so it is a whole-request deadline and a request that has already overrun it
never starts the query. ARQ's own timeout enforces the remainder, and a cancellation surfaces as
`BundleLimitException`.

### Colliding bundle part URIs were silently merged

Part root URIs are minted by stripping any fragment and appending `#root`, so `urn:part#a` and
`urn:part#b` both became `urn:part#root` — one `abnd:Part` node carrying two parts' facets and two
roles, producing a wrong Asset with no error. Colliding parts are now refused by name.

### HEL quantifiers were unbounded and could not be cancelled

`all`/`any` are one node to the enclosing parse or write budget but run their predicate once per
element — and a nested pair costs the product. A quantifier over a large parsed array escaped the
work accounting and the cooperative deadline entirely, and allocated a fresh evaluator per element.
`HelLimits.maxQuantifierElements` (default 1,000,000) is now charged at `quantifierScope`, the one
point both the compiled program and the reference interpreter pass through, so the compiled and
reference paths stay differentially identical. The budget is shared across nested quantifiers and
checks for interruption. Five tests cover the budget, the shared nested budget, the interpreter
path, cancellation, and that short-circuiting still avoids spending the budget.

The budget is per expression evaluation, so a profile with many rules still has no aggregate
quantifier bound across them; a hard whole-request limit remains necessary. What has changed is that
a single quantifier can no longer run without limit, and that it now observes an interrupt — a
cancelled request previously could not stop inside one at all.

### An unselected shape module could still be active

`InstanceGraphValidator` de-targets a module the caller did not select by deleting its explicit
`sh:targetClass`/`targetNode`/`targetSubjectsOf`/`targetObjectsOf` triples. SHACL *implicit* class
targets — a resource typed both `sh:NodeShape` and a class — have no target property to delete and
would survive. No bundled vocabulary declares one today, so this was sound by accident.
`BundledShapeAudit` now checks it, with a negative control that plants one and requires detection.

## Engine performance

The writer's deadline was a hardcoded 30-second literal, and each layout pass re-encoded every
encoded field: the writer re-runs the whole layout until length bindings converge, and codecs are
deterministic, so compression was paid once per pass. Both are fixed — `Metawriter(maxMillis = …)`
is now a declared limit, and an encoded payload is encoded once per `write`. The test measures it
directly through a counting codec: two writes previously cost four encodes, now two.

The writer also visited the budget through a `ThreadLocal` and called `System.nanoTime()` on
**every node**, an optimisation `Metaparser` had already received and the writer had not. Budget
access is now an identity comparison and the deadline is sampled every 1,024 nodes — except at
coarse expensive boundaries (an encode stage, a stream chunk, a layout pass), which check
unbatched, because a single large compression would otherwise never be sampled at all.

Measured with the repository's own protocol — three JVM forks, 100 warmups, 200 samples, 27
workloads — against the recorded 12 September baseline on this host:

| Workload | Baseline p50 (µs) | Now (µs) | Allocation |
|---|---:|---:|---|
| `compile-loaded-profile` | 17,981 – 21,425 | **163 – 237** | 2,607,304 B → 49,592 B |
| `shacl-scalar-prepared-validator` | 16,016 – 19,100 | 3,517 – 3,828 | 1,885,504 B → 720,320 B |
| `write-encoded-propagated` | 212 – 610 | 168 – 277 | 126,752 B → 111,288 B |
| `write-bytes-1048576` | 474 – 638 | 349 – 390 | unchanged |
| `write-scalar` | 84 – 140 | 65 – 77 | unchanged |

Read honestly, this is one unambiguous result and a set of readings that are not evidence of much.

**`compile-loaded-profile` is real**: roughly 90x, with allocation down 53x, and the mechanism is
known — a 218 KB Turtle parse per compile was removed. It is the per-request path for every lifting
call and every bundle part.

**The SHACL result is two effects, only one of them earned.** The first drop — to roughly 5.9 ms
with allocation unchanged — happened before `InstanceGraphValidator` was touched at all, and is most
likely reduced allocation pressure in the same JVM now that the compile workload no longer allocates
2.6 MB per iteration. It is reported because it was measured, not because it was earned. The second
drop is a real change: the validator copied the entire bundled supporting vocabulary into a fresh
model on **every** call, so the vocabulary rather than the instance under test dominated both cost
and allocation. It now validates against a read-only union of vocabulary and caller model, and
allocation falls from 1.89 MB to 0.72 MB per validation — a figure that, unlike the timings, does
not move with machine load. Those later timings were taken while the specification gate suite was
running on the same host, so they are an upper bound rather than a clean measurement.

**No writer throughput improvement is claimed.** The encoded-write workloads land inside or near
their baseline ranges, and `write-encoded-recursive` is slower at the low end (283 → 321 µs). These
fixtures are small, uncompressed-level payloads where encoding is not the cost, so removing a
duplicate encode does not show. The removed work is proven by the codec call count, not by these
timings. Several read-side workloads also measure slower than the recorded baseline
(`parse-bytes-1024` 12–15 → 15–19 µs, `lift-scalar` 26–32 → 32–40 µs); nothing in this change set
touches those paths, the cause was not identified, and the baseline was recorded on a different day
under different machine state. A calibrated regression budget remains open work.

## Engine release and reproducibility

- **CI is now an OS matrix** — `ubuntu-latest` and `windows-latest`, `fail-fast: false`. Windows is
  the development and measurement host and had no CI job at all.
- **The specification repository is checked out in CI** and `HEXPLAIN_REQUIRE_SPEC=1` makes
  `SpecSyncTest` fail rather than skip when it cannot find one. Bundled ontologies are copies of
  this repository's; the drift check existed but skipped itself in every CI run.
- **Skips are now reported and, where required, fatal.** `tools/report_skips.py` aggregates JUnit
  XML, prints every skipped case, and fails when a suite that must run skipped itself. A skip and a
  pass are the same green check, and this repository's strongest independent evidence — the GDAL
  parity suites — skips itself when the corpus is absent. Current full run: **4,129 tests, 8
  skipped**, all eight now named in the log.
- **GDAL differential conformance is no longer dispatch-only.** It runs weekly and on any pull
  request touching a profile, the parity suites or the GDAL harness, and the job requires its
  parity suites to have actually run.
- **Dependency verification is enabled**: `gradle/verification-metadata.xml` pins SHA-256 for 214
  components. A full clean `build test --rerun-tasks` passes under it.
- **A clean full build no longer runs out of memory.** There was no `gradle.properties` at all, and
  `build test --rerun-tasks` failed with `OutOfMemoryError: GC overhead limit exceeded` in the
  Kotlin daemon. Heap and metaspace are now set explicitly, because building from a fresh checkout
  is the release-acceptance path and must not depend on incremental state to fit in memory.

Verification: full `gradlew build test --rerun-tasks` with `HEXPLAIN_REQUIRE_SPEC=1` — **4,129
tests, zero failures, zero errors, 8 skipped** — under dependency verification, from a full
recompile, with the specification comparison enforced rather than skipped.

## Specification repository

### The first module to gain constraints from this work

`specification/aspect/security` published thirteen terms, had five of them exercised by competency
cases, and measured **zero** constraint obligations: it shipped no shapes, so the "component
coverage is complete" claim was complete over nothing. It now measures **15 obligations, all
two-sided**, and five resources assert a result path where none did before. Repository totals move
from 1,148 to 1,163 two-sided constraint obligations, 1,180 measured, none unevaluated.

The useful part was a correction the evidence forced rather than the count. The first shape bounded
the spine properties at `sh:maxCount 1`, which reads as obviously right. The module's own valid
fixture disagrees: `ex:SharedAssessment` is marked under two systems at once —

```turtle
ex:SharedAssessment
    asec:markingSystem        "TLP-2.0" , "UK-GSC" ;
    asec:sensitivityLevel     tlp:Amber , uk:Official ;
    asec:marking              tlp:LimitedDisclosure , uk:Sensitive .
```

— and a cardinality bound would have made the exact case hx-security 2.0 exists for invalid. The
published shape therefore constrains value *shape* only: verbatim parts are strings, decision dates
are `xsd:date` rather than instants, register-bound parts are `skos:Concept`. It says so explicitly,
because "there is deliberately no cardinality bound here, and this is why" is worth more to a reader
than the bound would have been.

One coherence rule survives multi-system marking and is published with it: a declared
`asec:levelChangesTo` must carry an `asec:levelChangeDate`, since the date is defined as when the
change takes effect, and a change without one cannot be read. Its failing witness is authored by
hand, because no valid/invalid/duplicate variant of a property that is *present* can demonstrate a
minimum-count violation.

This is one module of the ten that publish terms and measure nothing. It is offered as a worked
example of what closing the gap costs, not as the gap closed.

### Gate cost is now measured, not just timed

Per-gate **memory is now measured**. The parallel gates' eight-worker cap exists because a
concurrent run exhausted host memory, and the recorded evidence was wall-clock only. The gate
runner now samples the resident size of each gate *and its descendants* every 50 ms and records
peak bytes, peak process count and sample count alongside the duration. It is a sampled lower
bound: the test that proves it works also demonstrates that an allocation shorter than the sampling
interval is invisible to it.

The first measurement is already worth having. A full strict run is **46 gates, 46 passed, 0
skipped, 0 failed** with no validation input changed during execution, and its peak is **724.6 MiB
across at most 12 processes**, reached in `test_vocab_shapes` — the gate whose worker cap exists
because a concurrent run exhausted host memory. `test_family_contract` peaks at 427 MiB. Those two
are now the pair to watch before anyone raises `HEXPLAIN_GATE_WORKERS`, and the number to reason
with rather than the anecdote.

Specification CI also gains the same OS matrix as the engine, and publishes a per-gate cost summary
(`tools/_gate_cost.py`) with the retained evidence. The recorded 536 s suite timing came from a
20-core Windows host; a hosted runner has four, and the job's ceiling is set generously on purpose
until the uploaded evidence says what it should be.

## Not done

These remain open, and are listed so the record is not read as more than it is.

1. **Corpus exercise** — 52 of 795 traced resources are referenced by a competency case, and 26 of
   36 modules have none at all. This is authoring work; generating cases mechanically would
   manufacture weak evidence rather than coverage.
2. **Unconstrained terms** — with `aspect/security` done, 77 non-register published terms remain in
   modules that ship no shapes at all: `color` (2), `encoding` (4), `fsmeta` (6), `integrity` (3),
   `networkflow` (10), `pointcloud` (3), `provenance` (7), `tabular` (6) and `fn` (36).
3. **`sh:resultPath` breadth** — 31 of 795 resources assert one, so most negative witnesses prove
   only that validation failed, not where.
4. **Cross-validator breadth** — still two suites and 88 cases, top-level diagnostics only.
5. **Representative performance** — large real profiles, high-compression and large-geometry data,
   direct (non-reflective) generated calls and concurrent load are still unmeasured, as are
   calibrated regression budgets.
6. **Distribution decisions** — licence grants, dependency advisory review, shipped module scope
   and artefact provenance remain owner decisions.

The engine working tree remains uncommitted.
