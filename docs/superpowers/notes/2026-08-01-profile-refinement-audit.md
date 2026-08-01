# Profile refinement capability audit (Task 16)

**Date:** 2026-08-01
**Scope:** §10 risk response for the NITF P0 conformance-infrastructure plan. Answers whether
a downstream profile can `owl:imports` the NITF profile and override one field-level property,
without redefining the whole struct. Gates how P4 (NSIF 1.00/1.01) and P7 (NITF 2.0/1.1 legacy
dialects) are authored.

## Question

Can one Hexplain format profile import another (`owl:imports`) and override a field-level
property — specifically, can an importing profile restate `nitf:FH_FHDR`'s
`bddo:hasFixedValue` (`"NITF"` in the base profile) as a different value (`"NSIF"`), and have
the compiler resolve that to a single, well-defined value rather than both or an arbitrary
choice?

The probed field, as declared in
`/d/work/hexplain.io/specification/profiles/nitf/nitf.ttl` (line 107):

```turtle
nitf:FH_FHDR a bddo:Field ; rdfs:label "FHDR — File Profile Name" ;
    bddo:dataType nitf:BCSA ; bddo:size 4 ; bddo:hasFixedValue "NITF" .
```

## What was run

### Probe fixture

`specification/profiles/nitf/test/refinement-probe.ttl` (as committed):

```turtle
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix nitf: <https://hexplain.io/ns/profile/nitf#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.org/nsif-probe> a owl:Ontology ;
    rdfs:label "NSIF refinement probe" ;
    owl:imports <https://hexplain.io/ns/profile/nitf> .

nitf:FH_FHDR bddo:hasFixedValue "NSIF" .
```

Note: the brief's illustrative snippet used a different, incorrect namespace
(`https://hexplain.io/formats/nitf#`). The actual profile's ontology IRI is
`https://hexplain.io/ns/profile/nitf` with preferred prefix
`nitf: <https://hexplain.io/ns/profile/nitf#>`; the fixture above uses the real namespace so it
actually targets `nitf:FH_FHDR`.

### Attempt 1 — literal brief invocation

```
cd /d/work/hexplain-tools
./gradlew :core:runFormatIRToRdf \
  -PformatIrArgs="/d/work/hexplain.io/specification/profiles/nitf/test/refinement-probe.ttl https://hexplain.io/ns/profile/nitf#FileHeader probe-out.ttl"
```

Verbatim result: **build succeeded**, wrote `probe-out.ttl (3 triples)` — a vacuous IR
containing only an `ir:Format` node, no compiled structs, no `FH_FHDR` field, no fixed value at
all:

```turtle
[ rdf:type       ir:Format;
  ir:name        "Compiled Format";
  ir:rootStruct  <https;\\hexplain.io\ns\profile\nitf#FileHeader>
] .
```

Root cause: `ProfileLoader.load()` (`core/src/main/kotlin/io/hexplain/core/rdf/ProfileLoader.kt:28-37`)
calls `RDFDataMgr.read(model, inputStream, lang)` on a single file and never processes
`owl:imports`. `SerializeFormatIRToRdf.main()` (`core/src/main/kotlin/io/hexplain/core/rdf/SerializeFormatIRToRdf.kt:27-30`)
loads exactly one file (`args[0]`) into one `Model`. So the probe file's `owl:imports` triple
is inert data — the imported graph (`nitf.ttl`) is never fetched or merged in. `compile()`
(`RdfToIrCompiler.kt:27-30`) then finds zero `bddo:Struct` resources in that lone-file model,
so `FormatIR.structs` is empty and there is nothing to write for `FileHeader`/`FH_FHDR`.
(A secondary, unrelated artifact in that same run: Git Bash's MSYS path-mangling corrupted the
`https://...` root-struct-URI argument into a backslashed path-looking string, visible in the
garbled `ir:rootStruct` above — irrelevant to the compiler itself, noted only for
reproducibility.)

**This confirms the literal brief command does not exercise the question at all** — there is
currently no import-resolution step in the pipeline for it to test. This is itself a finding:
*profile import is not implemented*, independent of what the merge/override semantics would be
if it were.

### Attempt 2 — isolate the actual merge mechanism

To test what the compiler does with a **repeated `bddo:hasFixedValue` on one field once both
statements are in the same Jena `Model`** (i.e. the graph state an `owl:imports`-aware loader
would eventually have to produce), a temporary scratch program was compiled and run in-place in
`hexplain-tools` (`core/src/main/kotlin/io/hexplain/core/rdf/RefinementProbeScratch.kt`, plus a
temporary `runRefinementProbeScratch` `JavaExec` task added to `core/build.gradle.kts`). Both
were deleted and the build file reverted after the run; nothing was committed in
`hexplain-tools`.

A second, unrelated obstacle surfaced first: compiling the real, unmodified `nitf.ttl` through
`RdfToIrCompiler.compile()` currently throws before ever reaching `FH_FHDR`:

```
Exception in thread "main" java.lang.NumberFormatException: For input string: "U"
	at org.apache.jena.rdf.model.impl.LiteralImpl.getLong(LiteralImpl.java:203)
	at io.hexplain.core.rdf.RdfToIrCompiler.compileEnumeration(RdfToIrCompiler.kt:404)
	at io.hexplain.core.rdf.RdfToIrCompiler.compileField(RdfToIrCompiler.kt:295)
	at io.hexplain.core.rdf.RdfToIrCompiler.compileStruct(RdfToIrCompiler.kt:44)
	at io.hexplain.core.rdf.RdfToIrCompiler.compile(RdfToIrCompiler.kt:29)
```

Reproduced identically by compiling pristine `nitf.ttl` alone (no probe file involved) via
`runFormatIRToRdf`. Cause: `compileEnumeration()` (line 404) reads `bddo:enumRawValue` as
`.literal.long`, but every enumeration in `nitf.ttl` (`FSCLASEnum`, `ICORDSEnum`, `IMODEEnum`,
`IREPEnum`, `ICEnum`, `PVTYPEEnum`, `TXTFMTEnum`) uses **string** raw values (`"U"`, `"S"`,
`"MONO"`, a literal space, …), not integers. `compile()` compiles every `bddo:Struct` in the
model up front (`RdfToIrCompiler.kt:27-30`), so this one bad enum aborts compilation of the
*entire* file regardless of which root struct is requested — **`nitf.ttl` cannot currently be
compiled end-to-end at all, with or without the refinement probe.** This is pre-existing,
orthogonal to the refinement question, and out of scope for this task, but is recorded here
because it blocked getting the answer through the normal full-profile path and should be
tracked separately (it will also block P1+ once real requirements/constraints are authored
against these enum fields).

To route around that unrelated bug and isolate only the refinement question, the scratch
program built a **minimal synthetic model** containing just `nitf:FileHeader` (one field,
`FH_FHDR`) and `nitf:BCSA`, using the exact triples `nitf.ttl` gives `FH_FHDR`
(`bddo:dataType nitf:BCSA ; bddo:size 4 ; bddo:hasFixedValue "NITF"`), then added a second
`nitf:FH_FHDR bddo:hasFixedValue "NSIF"` statement to the same model/subject — reproducing
exactly the merged-graph state an import-resolving loader would hand to `RdfToIrCompiler`, and
exercising the identical Jena call the compiler makes.

Verbatim output (`./gradlew :core:runRefinementProbeScratch`):

```
Statements for nitf:FH_FHDR bddo:hasFixedValue BEFORE merge:
  NITF

Statements for nitf:FH_FHDR bddo:hasFixedValue AFTER merge (both present in one model):
  NSIF
  NITF

fieldRes.getProperty(BDDO.hasFixedValue) [RdfToIrCompiler.kt:223 call] picks: NSIF

Compiled FieldIR for FH_FHDR: fixedValue = "NSIF"
Re-run #1 (same model instance): fixedValue = "NSIF"
Re-run #2 (same model instance): fixedValue = "NSIF"
Re-run #3 (same model instance): fixedValue = "NSIF"
Re-run #1 (freshly re-parsed model): fixedValue = "NSIF"
Re-run #2 (freshly re-parsed model): fixedValue = "NSIF"
Re-run #3 (freshly re-parsed model): fixedValue = "NSIF"

Reverse-order probe (NSIF parsed first, NITF added second via model.add): fixedValue = "NITF"

Two-file-read probe (nitf.ttl read() first, refinement-probe.ttl read() second, same model): fixedValue = "NSIF"

BUILD SUCCESSFUL
```

Four independent trials, all consistent: **whichever statement enters the model last —
whether via `model.add()` or via a second `RDFDataMgr.read()` call on a second file into the
same model — is the one `getProperty()` returns**, and this held across 6 repeated
recompiles/re-parses with no variation.

## Mechanism (file:line)

`core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt`, `compileField()`, line 223:

```kotlin
val fixedValue = fieldRes.getProperty(BDDO.hasFixedValue)?.literal?.let { literal -> ... }
```

This calls Jena's `Resource.getProperty(Property)`, which returns a **single** `Statement`.
Jena's own contract for this method, when more than one statement matches subject+predicate, is
to return *some* matching statement — it does not document or guarantee "first", "last", or any
other selection rule. (The alternative, `Resource.listProperties(Property)`, returns a
`StmtIterator` over *all* matching statements and is used elsewhere in this same file, e.g.
`compileEnumeration()` at line 402 for `bddo:hasEnumValue` — so the single- vs. multi-valued
choice per property is deliberate and file-local, not accidental.)

Empirically, in this Jena version (`5.5.0`, per `libs.jena.core` in `gradle/libs.versions.toml`)
with the default in-memory `Model` (`ModelFactory.createDefaultModel()`, used by both
`ProfileLoader` and the scratch probe), `getProperty()` consistently returned the most-recently
added statement in every trial (8 total: forward order via `model.add`, reverse order via
`model.add`, forward order via a second `RDFDataMgr.read()`, and 6 repeat re-runs of both). This
looks like a stable "last write wins," but **it is not a documented API contract** — it is an
artifact of how Jena's default graph implementation happens to store and iterate statements for
a given subject+predicate pair. It is not guaranteed across Jena versions, across alternate
`Model`/`Graph` implementations (e.g. a `MultiUnion` graph that a real `owl:imports` resolver
might use to layer imported and importing graphs, which could enumerate sub-graphs in either
order), or if the loading order ever changes (e.g. imports loaded *after* the importing file
instead of before).

## Verdict

**Refinement needs a precedence rule.**

Not *"refinement works as-is"*: nothing in the current pipeline processes `owl:imports` at all
(confirmed by Attempt 1), so there is no working import mechanism to begin with — that alone
must be built. And once import-merging exists and both statements land in one model,
`compileField()`'s single-valued `getProperty()` call resolves the conflict by accident of
Jena's internal iteration order, not by a rule the codebase states or tests anywhere. That is
exactly the "silently nondeterministic" failure mode this investigation was watching for: it
happened to be reproducible and last-write-wins in every trial here, but there is no code, test,
or documented contract pinning that down, so it is one dependency upgrade or graph-implementation
change away from silently flipping. It does not need new vocabulary — `bddo:hasFixedValue`
already carries the right value on the right resource; the gap is entirely in (a) an
`owl:imports` resolution step that does not exist yet, and (b) a documented, tested precedence
rule (e.g. "importing profile's own file, read last, wins" or an explicit `owl:imports`-order
rule) for what `compileField()` should do when a field-level property is asserted more than
once, backed by a test that pins the winning value.

## Consequence for P4 and P7

**Recommendation: add a precedence rule to the compiler (and the missing import-resolution
step it depends on), rather than authoring NSIF as a full sibling profile.** The one-field probe
here already shows the compiler *can* be made to pick the override value correctly once the
statements are merged — the missing pieces are (1) an actual `owl:imports` loader (currently
absent — Attempt 1 shows the whole mechanism is a no-op today) and (2) turning the accidental
last-write-wins behavior into an explicit, tested rule (e.g., "load imported graphs first, then
the importing file, and last-asserted-wins" or an explicit override predicate). That is bounded,
compiler-level work with a clear test (repeat this exact probe as an automated unit test) versus
authoring NSIF 1.00/1.01 as ~226 duplicated field definitions with no shared source of truth
against NITF 2.1 — which would also have to be repeated again for the NITF 2.0 and 1.1 legacy
dialects in P7, multiplying the duplication and the maintenance burden (every NITF 2.1 field fix
would need manually re-applying to three more sibling profiles). Given NSIF differs from NITF
2.1 by only a handful of field values, the sibling-profile path is the more expensive option by
a wide margin and should be avoided unless the precedence-rule work proves infeasible.

## Artifacts

- Probe fixture (committed): `specification/profiles/nitf/test/refinement-probe.ttl`
- Scratch program used for Attempt 2 (not committed, deleted after use):
  `hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/RefinementProbeScratch.kt`
- `hexplain-tools/core/build.gradle.kts` temporarily gained a `runRefinementProbeScratch` task
  for the above; reverted via `git checkout` after the run. No commits were made in
  `hexplain-tools`.
