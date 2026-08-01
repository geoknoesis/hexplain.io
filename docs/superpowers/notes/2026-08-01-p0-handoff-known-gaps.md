# P0 Handoff — Known Gaps Between the Conformance Layer and Real NITF

**Date:** 2026-08-01
**Branches:** `hexplain-tools@feat/nitf-p0-conformance` (17 commits), `hexplain.io@feat/hx-bundle` (vocabularies)
**Status of P0:** complete, whole-branch reviewed, ready to merge. core 227/227, hdl 78/78 green.

## Read this before planning P1

Everything P0 delivers is verified **against a four-field synthetic fixture**. The layer has
never touched [specification/profiles/nitf/nitf.ttl](../../specification/profiles/nitf/nitf.ttl).
Four independent blockers sit between this infrastructure and its only intended consumer, all
discovered during P0 review and none caused by it. "227/227 green" must not be read as implying
the NITF profile works.

Each gap below states the mechanism, the consequence, and the JITC test objectives it maps to.

### P1-GAP-1 — `bddo:hasFixedValue` is a no-op on string-typed fields

`Metaparser` guards the fixed-value check on `fieldValue is ByteArray`. A `bddo:baseString`
field parses to a Kotlin `String`, so the guard is unconditionally false.

`nitf:BCSA` is `bddo:baseType bddo:baseString`, and **all nine** `hasFixedValue` declarations in
the NITF profile sit on BCSA fields: `FH_FHDR "NITF"`, `FH_FVER "02.10"`, `FH_STYPE "BF01"`,
`IS_IM "IM"`, `GS_SY "SY"`, `GS_SFMT "C"`, `TS_TE "TE"`, `DES_DE "DE"`, `RES_RE "RE"`. Every one
validates nothing today, and the `recoverable()` routing added in P0 Task 1 is dead code for the
entire profile.

Maps directly to JITC Quick Look negatives `NITF_FMT_NEG_01` (invalid version number → `FVER`)
and `NITF_FMT_NEG_04` (invalid format value `BIIF` → `FHDR`).

**Prefer expressing these as `conf:Constraint`s rather than extending the parser check** — a
constraint yields an attributed, requirement-citing finding instead of an `UNATTRIBUTED` parse
diagnostic.

### P1-GAP-2 — `RecoveryPolicy.COLLECT` cannot recover from truncation

Confirmed empirically. A truncated file raises `java.nio.BufferUnderflowException` from
`readField`. That is not a `HexplainParsingException`, so the per-field recovery catch never sees
it; it propagates to `Metaparser.parse()`'s outer handler and aborts the whole parse with **zero**
diagnostics recorded.

Maps to `NITF_FMT_NEG_02` (deficient bytes — 2/3 of pixel data missing) and `NITF_FMT_NEG_03`
(extraneous bytes) — precisely the "does the application inform the user" objectives.

Fix: widen the field-level catch to cover `BufferUnderflowException`/`IndexOutOfBoundsException`,
or pre-validate declared widths against remaining bytes.

### P1-GAP-3 — NITF enumerations cannot be compiled

`RdfToIrCompiler.compileEnumeration` has two independent blockers against `nitf.ttl`:

1. it reads `enumRawValue` as `?.literal?.long`, but every NITF enum raw value is a **string** —
   `"INT"`/`"SI"`/`"R"`/`"C"` (PVTYPE), `"B"`/`"P"`/`"R"`/`"S"` (IMODE), the ICORDS letters;
2. it requires `bddo:enumSymbol` and returns null without one, but NITF's enum entries declare
   `enumRawValue` **only** — so every value maps to null, the list ends empty, and the whole
   enumeration is silently dropped even if (1) were fixed.

Root cause is the IR type: `EnumValueIR(rawValue: Long, symbol: String)` cannot represent a
string-valued, symbol-less enumeration. These are exactly the fields the JITC image subtests
exercise (PVTYPE, IMODE, ICORDS).

Fix: widen `EnumValueIR` to a string-or-numeric raw value and make `enumSymbol` optional.

### P1-GAP-4 — `bddo:repeatUntil "end-of-region"` is not a supported sentinel

`nitf.ttl` uses it at six sites (lines 239, 247, 407, 415, 501, 580). Nothing handles it;
`RdfToIrCompiler` lexes it as HEL arithmetic (`end - of - region`), so any NITF file containing a
TRE dies with an uncaught `HelEvaluationException` out of `Metaparser.parse()` — under **both**
STRICT and COLLECT, with zero diagnostics.

## Residual defect on the P0 branch (non-blocking, prescribed fix)

`ConformanceEngine.collectInstances` ignores `StructIR.usesStruct` while `Metaparser` parses
template fields, so a constraint scoped to a struct reachable only through an inherited field
would evaluate zero times — and the scope-validation added in the final fix wave does **not**
catch it, because the scope IRI is a valid key.

Unreachable today: `bddo:usesStruct` is an explicitly removed legacy term, allow-listed as such in
`VocabAlignmentTest`, and it appears nowhere under `specification/` — not even in the NITF profile.

**Smallest safe mitigation** (~5 lines, purely additive, changes no parsing or collection
behaviour): add a reachability clause to `validateConstraintScopes` requiring each
`constraint.scope` to be in the `visited` set already computed by the conditional-dispatch walk.
This catches the `usesStruct` route *and* orphan structs.

## Deferred to a publication pass (hexplain.io)

- `specification/hel/index.html` documents only `sizeof`/`len`/`count`/`eof`; P0 added eleven HEL
  functions (`all`, `any`, `matches`, `substr`, `startsWith`, `trim`, `datetime`,
  `evaluationInstant`, `ringOrientation`, `isSelfIntersecting`, `inRegister`).
- `req:Syntactic`/`Semantic`/`Functional` lack `owl:NamedIndividual`, unlike the `bddo.ttl`
  convention for controlled individuals.

## Profile refinement — gates P4 (NSIF) and P7 (legacy dialects)

See [2026-08-01-profile-refinement-audit.md](2026-08-01-profile-refinement-audit.md). Verdict:
refinement **needs a precedence rule**. `ProfileLoader` does not process `owl:imports` at all, and
once graphs are merged manually the compiler resolves a repeated property via Jena's single-valued
`getProperty()`, whose winner rests on undocumented iteration order. Neither NSIF nor the legacy
dialects can proceed on a refinement model until `owl:imports` handling plus an explicit, tested
precedence rule exist.

## Process note worth carrying forward

Four tests authored in the P0 plan were caught asserting nothing. Three used a **disjunction** to
hedge uncertainty about which branch the code would take (`or ISCLAS == 'U'`;
`contains(quoted) || contains(unquoted)`); the fourth never triggered the path it was named for. A
test that accepts either outcome asserts nothing.

Rules adopted for later phases: **no disjunctive assertions in regression tests**, and **prove each
new guard by reverting the code it guards and confirming the test fails.** That revert-verification
caught all four.
