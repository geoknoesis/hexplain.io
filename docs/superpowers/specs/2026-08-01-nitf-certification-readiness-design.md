# Design — NITFS Certification Readiness for hexplain-tools

**Status:** approved design, pending spec review
**Date:** 2026-08-01
**Author:** Stephane Fellah / Geoknoesis LLC
**Subject of certification:** `hexplain-tools` as an **interpreting** NITFS implementation
**Sources of truth:** NGA *NITFS Conformance Program Plan* (NCPP) v1.0, November 2023;
MIL-STD-2500C; MIL-STD-2500A; NGA.STDI.0002; Joint BIIF Profile (JBP) 2021.2;
STANAG 4545 Ed 1/2; NGA.STND.0044 (MIE4NITF); BPJ2K01.10.

---

## 1. Goal and locked scope decisions

Bring `hexplain-tools` to the point where a NITFS Conformance Certification test could be
requested with justified confidence — i.e. where first-party conformance assessment
(NCPP §3.5) produces evidence that no Category 1 or 2 discrepancy remains within the
claimed configuration.

Locked decisions from brainstorming:

- **Subject:** `hexplain-tools` (Kotlin runtime: `Metaparser`, `HelEvaluator`,
  `CodecRegistry`) driven by the Hexplain NITF profile, as an interpreting
  implementation / NITFS analysis application. The NCPP explicitly lists "test
  applications evaluating NITFS" as certifiable Implementations.
- **Functional claim:** full interpretation — unpack **and** decode, including JPEG (C3)
  and JPEG 2000 (C8, both NL and VL profiles per BPJ2K01.10).
- **Version matrix:** full — NITF 2.1, NITF 2.0, NITF 1.1, NSIF 1.00, NSIF 1.01.
- **Approach:** **declarative-first (Approach A)**. Conformance rules are expressed in the
  profile as HDL/HEL, not as hand-written Kotlin rule classes. Native code is confined to
  the pre-existing `CodecRegistry` extension point for pixel reconstruction.
- **Engagement posture:** technical readiness ahead of any JITC agreement. No test date is
  assumed; the plan optimizes for provable conformance and for the artifacts JITC demands
  at NCPP §4.2.2, not for a calendar.

**Scope acknowledgement.** Full version matrix × full decode is the maximum scope on both
axes and is a multi-phase program, not a sprint. It is delivered in full here. The phasing
in §8 is arranged so each milestone terminates at an independently defensible claim rather
than gating all value on the final codec.

## 2. What certification actually requires

Recorded here because the technical plan is meaningless without the acceptance criterion.

**Pass criterion (NCPP §4.2.5):** testing of the Implementation is *complete* against the
agreed Test Case Matrix **and** free of Category 1 or 2 discrepancies. Two failure modes
are therefore equally fatal:

1. **Discrepancies.** Cat 1 = adverse operational impact on anticipated users; Cat 2 = same
   for unanticipated enterprise users. Cat 3/4 do not block but must be fixed by the next
   registration event; Cat 5 is informational.
2. **Coverage gaps.** "Unsampled test cases rated as high risk prevent completion of
   certification testing." A configuration you claim but cannot exercise blocks
   certification exactly as a defect does.

**Discrepancy types (NCPP Table F-2)** — every finding the tool emits must be classifiable
as one of:

| Type | Impacts | Violates |
|---|---|---|
| Syntactic | interpretability | format specifications, compression schemes |
| Semantic | understandability | data dictionaries, content specifications |
| Functional | usability | community/system documentation, community data models |

**Process shape (NCPP §4.2):** Test Request → Test Planning → Test Execution → Test
Reporting → Certification. Certification is scoped to the exact version, build, and
configuration tested, and any change to NITF components or to implemented NITFS requires
retest. Agreements — Interagency Agreement for NSG members, CRADA for commercial vendors,
Foreign Military Sales Agreement for international partners — run up to five years and
want roughly six months of lead time.

**Consequence for design:** the tool must produce, for every discrepancy, a
*requirement-identified, type-classified, byte-located* finding. Risk **category** is
deliberately not produced by the tool — see §3.4.

## 3. Architecture: the conformance layer

Three vocabulary modules. The first two are format-agnostic and belong to the Hexplain
framework; only the third is NITF-specific.

### 3.1 `hx-req` — requirements register (format-agnostic)

Describes what standards documents demand, independent of any profile.

- `req:Requirement` — identified by its native ID (`JBP-2021.2-002`, a MIL-STD-2500C table
  and field reference, an STDI-0002 TRE clause, a BPJ2K01.10 constraint).
- `req:fromStandard` — the source document and edition.
- `req:statement` — verbatim requirement text. Newer standards publish requirements in
  EARS syntax, which transcribes directly.
- `req:discrepancyType` — `req:Syntactic` | `req:Semantic` | `req:Functional`, per NCPP
  Table F-2.
- `req:appliesToVersion` — which of the five claimed dialects the requirement governs.

This module is the machine-readable form of the conformance criteria, and is the artifact
most directly reusable in the Data Content Specification handed to JITC.

### 3.2 `hx-conf` — conformance constraints (format-agnostic)

Binds executable assertions to requirements.

- `conf:Constraint` — a named rule.
- `conf:scope` — a `bddo:Struct`, a `bddo:Field`, or the whole stream; determines the
  evaluation context and how often the rule fires.
- `conf:assertion` — a HEL expression evaluating to boolean. True = conformant.
- `conf:satisfies` — one or more `req:Requirement`. **Required**, not optional.
- `conf:message` — a template for the finding text, interpolating field values.

Severity is **not** a property of the constraint. It is derived from the requirement's
`req:discrepancyType`, so a structural rule reused across profiles inherits the correct
classification everywhere rather than being restated inconsistently.

### 3.3 `nitf-req.ttl` and profile constraints (NITF-specific)

The population of both vocabularies for the claimed matrix, colocated with the existing
profile in `specification/profiles/nitf/`.

### 3.4 Why coverage is computable, and why category is not produced

`conf:satisfies` makes the coverage matrix a query rather than a spreadsheet:

- Requirements with **no** constraint → the implementation gap list.
- Constraints with **no** test case → untested rules.
- Requirements × claimed version → the input to JITC's Test Case Matrix.

This query is the readiness dashboard for the whole program and the evidence bundle in §7.

Risk **category** (1–5) is intentionally out of the tool. NCPP Table F-3 defines category
by operational impact on *anticipated versus unanticipated systems and users* — a judgment
about deployment context, not a property of the file or of the rule. The tool reports
requirement, type, and location; category is assigned during test reporting. Emitting a
category would be fabricating a determination reserved to the Executive Test Agent.

## 4. HEL extensions

Assessed against the actual JITC Quick-Look test objectives. HEL today has literals,
accessor paths (`self`, `parent`, `root`, `stream`), indexed path steps, unary/binary
operators, boolean `and`/`or`/`not`, and the functions `len`, `count`, `size`, `sizeof`,
`remaining`, `eof`. Cross-segment navigation is therefore **already expressible** — the
gaps are narrower than a redesign.

| Extension | Form | Needed for |
|---|---|---|
| Quantifiers | `all(path, expr)`, `any(path, expr)` | Rules ranging over dynamic counts: every image band's `IREPBAND`, every TRE in UDHD registered, no segment classified above file. Existing indexing only covers fixed counts; `NUMI`, `NBANDS`/`XBANDS` are dynamic. |
| Pattern predicates | `matches`, `substr`, `startsWith`, `trim` | ICORDS variants (DD/DMS/UTM/MGRS), `CCYYMMDDhhmmss` well-formedness, REL TO delimiter syntax. JITC has an explicit negative case where FDT/IDATIM/TXTDT all carry `21JAN01123015`. |
| Temporal | `datetime(s, fmt)` yielding an ordered value | Segment-created-after-file ordering, impossible-early dates, future dates. |
| Register lookup | `inRegister(value, <scheme>)` | Unregistered TRE tags and DES, GENC trigraphs vs FIPS 10-4/GEC digraphs, field-value registers. |
| Geometry | `ringOrientation`, `isSelfIntersecting` | IGEOLO winding (counterclockwise detection) and bowtie footprints. |

Two design commitments:

**No `now()` builtin.** The reference instant for "future date" rules is a **run
parameter**. Wall-clock inside the expression language makes conformance runs
irreproducible, and reproducibility is the point of the evidence bundle.

**Geometry as pure HEL builtins, not native rules.** A shoelace test written inline is a
200-character expression nobody can review against the standard. Adding two pure functions
keeps the rule readable and declarative; escaping to Kotlin rule classes would break
Approach A.

**Registers as SKOS.** `inRegister` resolves against NSG registers modelled as SKOS
`ConceptScheme`s — the pattern the aspect layer already uses. This is population work
against existing machinery, not new machinery.

## 5. Runtime

### 5.1 Error-recovering parse (prerequisite)

`Metaparser` today fails on error. Conformance requires it to **continue and report**: a
file with twelve discrepancies must yield twelve findings, not the first one. Every JITC
objective phrased "does the application inform the user…" depends on this.

Required: error recovery with resynchronization at segment boundaries, driven by the
segment length table in the file header, so that a corrupt image subheader does not
prevent evaluation of the text and DES segments after it. Structural discrepancies
detected during parse — truncated pixel data, extraneous trailing bytes, invalid `FHDR`,
bad version — are mapped to requirements and emitted as findings, not thrown.

This is the single largest runtime change in the program and blocks all format work.

### 5.2 Conformance engine

`ConformanceEngine` in `core` walks `conf:scope` over the parse tree, evaluates
`conf:assertion` via `HelEvaluator`, and emits `Finding` records carrying: requirement ID,
discrepancy type, byte offset, field path, and rendered message. Findings from the two
producers — parse-time structural, post-parse constraint evaluation — land in a single
`ConformanceReport`. Consumers cannot tell which producer originated a finding, and should
not need to.

## 6. Format coverage

### 6.1 Dialects

JBP 2021.2 already unified the NITFS and NSIF requirement sets, and the NSIF 1.00/1.01
structural deltas from NITF 2.1 are `FHDR`/`FVER` fixed values plus a small number of field
constraints. NSIF is therefore a **profile refinement** of the existing NITF 2.1 profile:
shared struct definitions with overrides.

The TRE modules already import the base profile, so import exists; **refinement/override
does not, and must be confirmed or built early** — NITF 2.0 and 1.1 need it too. Those two
are genuine dialects rather than variants (2.0 carries Symbol and Label segments where 2.1
has Graphic and no Label, and uses a different security field set), so they receive their
own profiles sharing the TRE framework.

### 6.2 TREs

Current coverage is BLOCKA and RPC00B — 2 of the 100+ controlled extensions in NGA.STDI.0002
plus NGA.STND.0044. Each TRE is an independent declarative module against a fixed framework,
making this the most parallelizable body of work in the program.

The four TRE areas (UDHD, XHD, UDID, IXSHD) and their DES overflow forms are already modelled
in the container profile and are exercised directly by the JITC `NITF_STD2-1_*` test cases.

### 6.3 Codecs, and the split that preserves the thesis

BPJ2K01.10 conformance is largely a set of **constraints on the codestream** — tiling,
progression order, layer counts, precinct sizes, and the NL versus VL profile limits. Those
are describable. Therefore:

- **Declarative:** the JPEG 2000 codestream markers are modelled as an HDL format, and the
  BPJ2K01.10 profile constraints are ordinary `conf:Constraint`s over that description,
  reviewable against the standard like every other rule.
- **Native:** pixel reconstruction is delegated through `CodecRegistry` to a proven decoder
  (OpenJPEG or a JVM equivalent). Writing a wavelet transform is not a differentiator and
  is a defect source.

The same split applies to C3/JPEG. The pixel-model matrix — PVTYPE INT/SI/R/C, 11-in-16 and
14-in-16 packing, IMODE B/P/R/S, IREP MONO/RGB/RGB-LUT/YCbCr601/MULTI/NODISPLY, `NBANDS=0`
with `XBANDS`, NM and M4 block masks, I1 downsampling — is joint profile and codec work.

## 7. Evidence artifacts

- **Coverage matrix** — SPARQL over `conf:satisfies`, joining requirements, constraints, and
  test cases. Regenerated on every build; a drop in coverage is a build signal.
- **Data Content Specification** — generated from profile plus register. This is the NCPP
  §4.2.2 artifact; without it JITC cannot plan a test at all, and generating it removes the
  risk of the document drifting from the implementation.
- **Conformance report** — per-file findings, machine-readable and human-readable.
- **Self-assessment record** — first-party assessment results over the full corpus, which is
  the evidence NCPP §3.5 expects a Product Owner to carry into test planning.

**Corpus.** JITC's Quick Look, Basic, Products, Source, NEA, and Negative datasets, obtained
via the Test Data Request form — **requested at program start**, since the forms carry lead
time and the negative datasets are what exercise most of §5.1. Supplemented with synthesized
negatives for cases the JITC sets do not cover in the claimed matrix.

**CIVA dependency: none.** CIVA is distributed to *government programs* on approved request,
so a commercial path may not obtain it. The plan does not depend on it. Independent
cross-checking runs against certified applications listed on the JITC conformance register,
which is also what the NTB recommends for minimizing discrepancies not attributable to the
implementation under test.

## 8. Phasing

Each milestone terminates at an independently defensible claim.

| Phase | Deliverable | Rationale |
|---|---|---|
| **P0** | Conformance infrastructure: `hx-req`, `hx-conf`, HEL extensions, `ConformanceEngine`, **error-recovering parse** | No format coverage gained; everything downstream blocks on it |
| **P1** | NITF 2.1 structural and field conformance; uncompressed pixel access | First defensible claim: NITF 2.1 interpretation, uncompressed, structural and field-level |
| **P2** | Semantic families — geospatial, temporal, security — plus register population | Where most Category 1/2 discrepancies live |
| **P3** | TRE completion: STDI-0002 full set + STND.0044 | 2 of 100+ today; highly parallelizable |
| **P4** | NSIF 1.00/1.01 by profile refinement | Cheap once P0–P3 land |
| **P5** | Compression: NM, M4, C3, I1 | |
| **P6** | C8 / JPEG 2000 plus BPJ2K01.10 codestream constraints | Triggers the separate J2K Test Plan |
| **P7** | Legacy NITF 2.0 and 1.1 dialects | Deliberately last: lowest value per unit of work, blocks nothing |
| **P8** | Evidence packaging: DCS, coverage matrix, self-assessment report | |

P7 is the one slice worth reconsidering once P1–P6 are real. Placing it last preserves that
option at zero cost.

**Plan decomposition.** This spec covers the whole program; it is not a single
implementation plan. Each phase gets its own plan → implementation → review cycle. The
immediate implementation plan covers **P0 only**, because P0 is where the vocabulary
surface and the HEL surface are fixed, and every later phase is authored against them —
planning P1+ in detail before P0 lands would be planning against an unstable interface.

## 9. Non-goals

- **No risk category assignment** by the tool (§3.4).
- **No generation/production claim.** `Metawriter` is out of scope; certifying generation
  would roughly double the Test Case Matrix and require produced files to satisfy JBP
  complexity levels.
- **No MTI / STANAG 4607.** Separate test plan, unrelated standard.
- **No human factors assessment work.** The NITF Test Plan includes a usability assessment,
  but it applies to the interactive application under test and is not addressed by the
  runtime.
- **No JITC agreement, funding, or scheduling artifacts** — engagement posture is technical
  readiness first.
- **No Kotlin rule classes.** Conformance logic that is not a codec stays declarative.

## 10. Risks and dependencies

| Risk | Response |
|---|---|
| Profile refinement/override may not exist in BDDO/HDL | Confirm in P0; if absent, build it there — P4 and P7 both depend on it |
| HEL may resist quantifiers over dynamic repeats | P0 spike before committing the vocabulary surface |
| Standards access: STDI-0002, JBP 2021.2, BPJ2K01.10 editions | Obtain via nsgreg.nga.mil at program start; requirement transcription blocks P2 onward |
| JITC dataset request lead time | Submit at program start, not at test readiness |
| J2K decoder licensing and JNI/FFI packaging | Evaluate during P5, before P6 commits |
| Register drift (TRE/DES/field value registers) | Registers are versioned SKOS schemes; treat updates as retest triggers, mirroring NCPP retest policy |

## 11. Repository split

- **`hexplain.io`** — `hx-req` and `hx-conf` vocabularies, NITF requirement register, all
  profile constraints, dialect profiles, TRE modules, J2K codestream description.
- **`hexplain-tools`** — HEL extensions, `ConformanceEngine`, error-recovering parse, codec
  registrations, report and DCS generation, coverage query tooling.

The seam matches the existing one: `hexplain.io` describes, `hexplain-tools` executes.
