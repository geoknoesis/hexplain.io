# hexplain-tools Spec-Compliance Audit

**Date:** 2026-08-01 · **Method:** four parallel read-only audits (one per spec area) comparing `d:/work/hexplain-tools` (`core` + `hdl`) against the Hexplain specs in `d:/work/hexplain.io/specification/`. Every finding is evidence-backed with `file:line`.

**Verdict:** the tools are **compliant on the common path** — the PNG/TIFF/Shapefile flows work end-to-end, most BDDO features execute, HEL parsing/precedence/arithmetic is solid, and the HDL compiler (after Compliance Plan A) largely conforms to its own spec. **Full** compliance has ~2 dozen gaps, concentrated in the pre-existing **`core` runtime** (`Metaparser` / `SemanticLifter` / `HelEvaluator`), not the HDL compiler.

**Remediation status:** decomposed into 4 plans (`docs/superpowers/plans/2026-08-01-*`).
- **Plan A (HDL compiler) — DONE, merged to `main` @ `b622d7b`.** Items 14–18, 20, 21 below are fixed.
- **Plans B (HEL runtime), C (BDDO/DLV + SHACL), D (hx-bundle lifting + generic processor) — PAUSED.** They overlap the active `feat/nitf-p0-conformance` branch (a conformance engine + new HEL functions, forked before Plan A). **Unify the branches and re-audit HEL before resuming** — the parallel branch may already close some HEL gaps.

Line numbers are as of the audit; verify against current source before acting (esp. `core`, which the parallel branch is changing).

---

## A. `core` runtime — the bulk of the gaps

### Missing whole capabilities

| # | Gap | Evidence | What "compliant" needs | Plan |
|---|-----|----------|------------------------|------|
| 1 | **hx-bundle facet lifting entirely unimplemented.** `abnd:LiftByCarriedAspectRule` (the SHACL-AF CONSTRUCT that lifts part facets onto the unified Asset — the point of hx-bundle) is never executed; grep `LiftByCarried\|RuleUtil\|SPARQLRule` = 0 hits. `hdl` only *authors* bundle Turtle. | `bundle.ttl:115-129` (rule authored); no consumer anywhere | A runtime: file-set + `BundleProfile` → `Asset` graph with facets lifted (apply the SHACL-AF rule via Jena `RuleUtil`, or an equivalent). | D |
| 2 | **No generic Processing-Model driver.** Only per-format mains (`ExtractSemanticGraph` extension-dispatch) + a hand-coded TIFF seek (`ExtractTiffSemanticGraph`) that ignores the IR's own offset addressing. | `ExtractSemanticGraph.kt:37-43`; `ExtractTiffSemanticGraph.kt:58-112` | A generic entry point keyed on (root Struct R, base IRI B) → RDF graph, per Processing §Inputs. | D |
| 3 | **IRI minting deviates from the Processing default** — mints `B#root` / `B#root/field/index` instead of `B` / `B/path`. | `SemanticLifter.instanceUri:312-318` | **NOT a strict gap** — deterministic + documented, which Processing §5 permits as a "MAY" alternative. Change only if isomorphism with default-scheme processors is required. | (excluded) |

### Execution bugs that break/silently-corrupt real formats

| # | Gap | Evidence | Plan |
|---|-----|----------|------|
| 4 | **DLV `dimensionSizeFromField` → size 0.** A dimension sized from a parsed field (width/height from a header — the normal case) breaks all cell addressing; `shape` reads only literal `DimensionIR.size`. DLV effectively only works with hard-coded dims, and its output is never lifted to RDF anyway. | `Metaparser.kt:45,63,79,89`; `SemanticLifter.kt:200` (MultiDimensionalData dropped) | C |
| 5 | **HEL `eof()` / `stream.*` / `self` never wired into the Metaparser** — every `HelEvaluator(...)` omits stream/self context, so `bddo:repeatUntil "eof()"` throws and `self` in repeatUntil is Null. | `Metaparser.kt:174,211,278,324,377,398,445`; `HelEvaluator.kt:47-48,143-147` | B |
| 6 | **`hasFixedValue` only checked for `bytes` fields** — integer/string magic numbers never validated. | `Metaparser.kt:234` (`fieldValue is ByteArray`) | C |
| 7 | **Checksum `coversExpression` silently skipped** — never verified (integrity hole). | `Metaparser.kt:628-630` (early-returns unless from/to both set) | C |
| 8 | **`alignment` inert unless paired with an offset** — sequential-cursor padding (TIFF, ISOBMFF) does nothing. | `Metaparser.kt:334` (only in offset resolution) | C |
| 9 | **`repeatUntil` on a scalar/bytes field ignored** — reads exactly one element. | `Metaparser.kt:364-366` (only when `structs[type] != null`) | C |

### HEL normative-conformance failures (spec §Conformance, §Type Coercion)

| # | Gap | Evidence | Plan |
|---|-----|----------|------|
| 10 | **Incompatible-type equality returns `false` instead of raising** (`true == 1`). Violates coercion rule 6 + Conformance #5. | `HelEvaluator.kt:211` (`else -> false`) | B |
| 11 | **Undefined-name references don't raise** — schema-less eval can't distinguish undefined from absent-optional (both → Null). Conformance #5. (Now caught at HDL *compile* time by Plan A, so runtime gap only affects hand-authored profiles.) | `HelEvaluator.kt:59-77` | B |
| 12 | **Bytes-vs-String comparison hardcodes UTF-8**, ignoring `bddo:encoding`. Low impact — `string` fields are decoded at parse with their encoding, so only raw `bytes` fields hit this path. | `HelEvaluator.kt:209-210` | B |
| 13 | **`sizeof` doesn't support structs or numeric fields** (spec: "field or struct"). | `HelEvaluator.kt:138-142` | B |
| 14 | **`parent.parent…` beyond one level → Null.** | `HelEvaluator.kt:61-63,87` | B |

### Core-semantic notes (mostly conformant)

- Core mapping (`mapsToClass/Property`, `hasConditionalMapping`, `valueExpression`/`valueDatatype`) is implemented in `SemanticLifter`. `isEncodedWith` works only because the Metaparser decodes+re-parses before lifting (`Metaparser.kt:425-441`); the lifter has no independent handling.
- `hasDataLayout` yields **no** semantic output (Processing §7 says MAY, so conformant-but-inert) — see #4.
- Field-level `bddo:endianness` is dropped at compile (`readEndianness` only applied to the datatype, not the field) — low impact (be/le-suffixed primitives cover it).
- `offsetBase parentStart` is containing-struct-relative, not grandparent-relative (fine for the usual intent).

---

## B. `hdl` compiler — FIXED by Compliance Plan A (merged `b622d7b`)

| # | Gap (now fixed) | Fix |
|---|-----|-----|
| 14a | Undeclared identifiers not diagnosed outside the lone-name case (MUST #3) | Full-expression sibling validation via a unified `HelSynth.bareIdentifiers` scanner (also fixed a pre-existing `0x10`→`parent.x10` HEL bug). |
| 15 | `switch { "lit" => S }` (no discriminator) threw (MUST #5) | ERROR diagnostic + non-throwing `emitSwitch`. |
| 16 | Named-enum-ref / unknown carries-prefix / unknown part-role / missing YAML keys silently wrong (MUST #5) | Source-located ERROR diagnostics for each. |
| 17 | Unbracketed `<` / `<=` / `<<` mis-lexed | Lexer disambiguates `<iri>` (use-decls) from operators. |
| 20 | Spec prose said raw-turtle works at "struct or field" scope | Aligned spec to "struct scope" (matches the normative ABNF). |
| 21 | YAML diagnostics unlocated `Span(0,0)` | Best-effort YAML source locations (parallel snakeyaml Node tree). |

---

## C. Validation infrastructure (both modules)

| # | Gap | Evidence | Plan |
|---|-----|----------|------|
| 19 | **SHACL never wired into any pipeline** — opt-in only, and it validates the *description*, never the emitted *instance graph*. `RdfToIrCompiler` explicitly declines to validate. | `ShaclProfileValidator.kt:19-21`; no `validate/conforms` call site outside its own test | C |
| 23 | **Core/DLV SHACL shapes not shippable** — `core.ttl` absent from `main` resources; `dlv.ttl`/`bundle.ttl` are test-only. Only `bddo.ttl` shapes run in a normal deployment. | `core/src/main/resources/` has only `bddo.ttl`; `dlv.ttl` at `core/src/test/resources/spec/`; `bundle.ttl` at `hdl/src/test/resources/` | C |

---

## Suggested remediation order (when compliance resumes, on the unified base)

1. **Plan B — HEL runtime** (items 5, 10–14): wire eof/stream/self; incompatible-type + undefined-name errors; per-field encoding; sizeof structs/numeric; parent chain. *Re-audit first — the conformance branch overlaps here.*
2. **Plan C — BDDO/DLV execution + validation** (items 4, 6–9, 19, 23): DLV dynamic sizing + semantic lifting; fixed-value/checksum-expr/alignment/scalar-repeatUntil; ship `core.ttl`/`dlv.ttl` shapes and wire SHACL into the pipeline.
3. **Plan D — hx-bundle lifting + generic processor** (items 1, 2): execute `LiftByCarriedAspectRule`; a generic (root Struct, base IRI) → RDF driver.

Item 3 (IRI minting) is excluded — already compliant as a documented "MAY" alternative.
