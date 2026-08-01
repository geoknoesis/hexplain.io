# HEL Runtime Conformance Fixes — Implementation Plan (Compliance Plan B of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Bring the `core` HEL runtime (`HelEvaluator` + the `Metaparser` that drives it) into full conformance with the HEL 1.0 spec (`specification/hel/index.html` §Conformance + §Type Coercion): wire the currently-unreachable `eof()`/`stream.*`/`self` roots into real parsing, raise runtime errors on incompatible-type equality and undefined-name references, apply per-field encoding in Bytes↔String comparisons, and support `sizeof` of structs/numeric fields and multi-level `parent`.

**Architecture:** Changes are in the `core` module (`io.hexplain.core.hel.HelEvaluator`, `io.hexplain.core.metacodec.Metaparser`, and the IR types they consult). The Metaparser is enriched to hand the evaluator the context it needs (a stream view, the just-parsed element, an ancestor chain, the current struct's field set, and per-field byte/encoding metadata). Every fix is test-driven; the existing PNG/TIFF/Shapefile parse behavior (and all `:core` tests) is the guardrail.

**Tech Stack:** Kotlin 2.2.10 / Gradle / Jena 5.5.0 / JUnit 5. Builds on the merged Plans 1–3 + Compliance Plan A (`main` @ current head).

## Global Constraints

- Conform to `specification/hel/index.html` §Conformance (MUST: implement all five roots `instance/parent/root/self/stream`; all operators+functions; value-type + coercion rules; report runtime errors on type errors, div/mod-by-zero, and undefined names) and §Type Coercion (Bytes-vs-String decode via the field's `bddo:encoding`; incompatible-type comparison is an error).
- **No regression to `:core` or `:hdl`.** The full `./gradlew build` (both modules) must stay green each task. The existing Metaparser parse results for real formats must be unchanged (the PNG/TIFF tests + HDL parity are the guardrail).
- Runtime errors are raised as `io.hexplain.core.hel.HelEvaluationException` (existing type) — the Metaparser already surfaces these as parse failures.
- The evaluator's public constructor may gain parameters, but they MUST be defaulted so existing call sites (e.g. `HelEvaluatorTest`, any direct users) keep compiling; the Metaparser is the primary caller and passes the new context.

## Scope note

Compliance Plan **B of 4** (of the "fix all" compliance effort). Plan A (HDL compiler) is merged. This plan fixes the HEL runtime (audit items 5, 10, 11, 12, 13, 14). Plan C (BDDO/DLV execution + SHACL) and Plan D (hx-bundle lifting + generic processor) are separate.

## Re-audit addendum (current `main` @ d030b91 — post NITFS-conformance merge)

A parallel "conformance engine" feature merged into `main` after this plan was drafted. A re-audit confirms **all six items (5, 10–14) are STILL OPEN** — the merge added capability but fixed none of the defects (only two error-message strings changed). Two things changed the plan's execution constraints:

- **PRESERVE the new HEL surface — do not break or duplicate it.** `HelEvaluator` now also implements: quantifiers `all(coll,pred)`/`any(coll,pred)`; string fns `matches/substr/startsWith/trim`; temporal `datetime/evaluationInstant`; geometry `ringOrientation/isSelfIntersecting`; register `inRegister`; a `FIXED_ARITY` map + arity pre-check that runs **before** arg evaluation (keep that ordering); and two extra constructor params `evaluationInstant`, `registerProvider`. Every task that changes the `HelEvaluator` constructor MUST **add** its new params (defaulted) without dropping these, and update **all** construction sites in lockstep — the ~8 in `Metaparser.kt`, plus `Metawriter`, `SemanticLifter`, and **`ConformanceEngine.kt`** (which currently passes `streamContext = null` at ~`:110`).
- **Two error paths — assert per-path.** A thrown `HelEvaluationException` in the **Metaparser** path propagates and aborts the parse (it is a plain `RuntimeException`, not a caught `HexplainParsingException`); `isPresentIf`/`repeatUntil` sites are outside the recovery try/catch. In the **`ConformanceEngine`** path, `evaluate()` is wrapped in `catch(RuntimeException)` → a per-constraint Finding. So "raise a runtime error" (items 5/10/11) means *throws-and-aborts* in the parser and *becomes-a-Finding* in the engine — tests MUST assert the correct behavior for each path.
- **Current line hints (verify live):** `isEqual` `else -> false` at `HelEvaluator.kt:~344`; `sizeof` at `:~195-199`; parent one-hop at `:~54-64,73-75`; the `HelEvaluator(...)` sites in `Metaparser.kt:~198,257,365,411,464,485,514,532`; `ConformanceEngine.kt:~110`. Item 5's stream wiring should also fix `ConformanceEngine`'s `streamContext=null` so `conf:` rules can use `eof()`/`stream.*`.

---

## File Structure

- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` — equality/undefined-name/encoding/sizeof/parent semantics.
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` — thread stream view, self, ancestor chain, field set, and per-field byte/encoding metadata into every `HelEvaluator(...)` construction (audit: ~lines 174, 211, 278, 324, 377, 398, 445).
- Possibly modify: `core/src/main/kotlin/io/hexplain/core/ir/Model.kt` — if a helper is needed to expose a struct's field set / a field's encoding/byte-width to the evaluator (read-only additions).
- Tests: extend `core/src/test/kotlin/io/hexplain/core/hel/HelExpressionTest.kt` (evaluator-level), `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserTest.kt` (end-to-end parsing), and add cases proving each spec rule.

---

## Task 1: Incompatible-type equality raises (spec §Coercion rule 6, Conformance #5)

**Problem (audit #10):** `HelEvaluator.isEqual` (`HelEvaluator.kt:201-213`) returns `else -> false` for two non-null values of incompatible types (`true == 1`, `'IHDR' == 5`, `bytes == 3`), instead of raising. The spec: "Comparing values of otherwise incompatible types … is an error."

**Files:** `hel/HelEvaluator.kt`; Test `hel/HelExpressionTest.kt`.

- [ ] **Step 1: Failing tests** (construct `HelEvaluator` directly with literal ASTs, as the existing HelExpressionTest does):

```kotlin
    @Test fun incompatibleTypeEqualityRaises() {
        // Boolean vs Integer, String vs Integer, Bytes vs Integer → error (not false)
        assertThrows(HelEvaluationException::class.java) { evalExpr("true == 1") }
        assertThrows(HelEvaluationException::class.java) { evalExpr("'x' == 5") }
    }
    @Test fun compatibleAndNullEqualityStillWork() {
        assertEquals(true, evalExpr("1 == 1"))
        assertEquals(true, evalExpr("'IHDR' == 'IHDR'"))
        // Null == Null true; Null == x false (still not an error)
        assertEquals(true, evalExpr("missing == missing"))   // both absent → Null == Null
    }
```

(Use the test file's existing helper for building/evaluating an expression against a context; if none, add a small `evalExpr(src, context = emptyMap())` that lexes+parses via `HelParser` and evaluates.)

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement.** In `isEqual`, replace the final `else -> false` with `else -> throw HelEvaluationException("Cannot compare ${typeName(left)} and ${typeName(right)} for equality")`. Keep the null-branch (line 202) and all recognized compatible pairs (Number/Number, String/String, Boolean/Boolean, ByteArray/ByteArray, and the Bytes↔String pair) returning as before. `!=` (which is `!isEqual`) will correctly propagate the error.

- [ ] **Step 4: GREEN** + full `./gradlew build`. **Regression watch:** confirm no existing parse relies on a silent-false incompatible comparison (the PNG/TIFF fixtures compare like-typed values). **Step 5: Commit** — `fix(core/hel): raise on incompatible-type equality per HEL spec`.

---

## Task 2: Wire the stream context + `eof()` / `stream.*` into the Metaparser (spec §Data Model, Conformance #2)

**Problem (audit #5):** every `HelEvaluator(context, parentContext, rootContext)` construction in the Metaparser (~lines 174, 211, 278, 324, 377, 398, 445) omits `streamContext`, so the spec's own `bddo:repeatUntil "eof()"` and any `stream.length/position/remaining` reference throw "stream is not available" at runtime.

**Files:** `metacodec/Metaparser.kt`; Test `metacodec/MetaparserTest.kt`.

- [ ] **Step 1: Failing test** — a small FormatIR whose root struct has `repeatUntil "eof()"` (a repeated element read until end of stream) parses a fixed byte array and yields the expected element count; and a field sized by `stream.remaining`. (Build the FormatIR via a tiny profile TTL through `ProfileLoader`+`RdfToIrCompiler`, or hand-construct `FormatIR`/`StructIR`/`FieldIR` — whichever the existing MetaparserTest already does; mirror its harness.) The key assertion: parsing succeeds and `eof()`/`stream.remaining` evaluate correctly (no "stream is not available" exception).

- [ ] **Step 2: RED** (currently throws).

- [ ] **Step 3: Implement.** Introduce a helper that builds the stream-context map from the current buffer state at an evaluation point: `mapOf("length" to buffer.limit().toLong(), "position" to buffer.position().toLong(), "remaining" to buffer.remaining().toLong())` (adapt to the Metaparser's actual buffer/cursor representation — it uses a `ByteBuffer`/bounded region; use the OUTERMOST stream's length/position for `stream.*`, so `eof()` is true at true end-of-stream, per the spec's "end of stream"). Pass this `streamContext` to EVERY `HelEvaluator(...)` construction. Ensure `eof()` reflects the real outer-stream end (not a bounded sub-region's end) — the spec's `eof()` is "cursor at end of stream".

- [ ] **Step 4: GREEN** + full build, no regressions (existing repeatUntil-by-condition and sized fields still parse). **Step 5: Commit** — `fix(core): supply stream context so eof()/stream.* work during parsing`.

---

## Task 3: Wire the `self` context into `repeatUntil` (spec §Reserved Roots)

**Problem (audit #5, self):** the `repeatUntil` evaluation (`Metaparser.kt:~174`, `parseStructSequence`) constructs the evaluator with no `selfContext`, so `self` (the "array element most recently parsed, the one under test" — the sole documented use of `self`) resolves to Null.

**Files:** `metacodec/Metaparser.kt`; Test `metacodec/MetaparserTest.kt`.

- [ ] **Step 1: Failing test** — a repeated struct field with `repeatUntil "self.Marker == 0"` (or `self == 0` for a repeated scalar): parsing stops after the element whose `self` matches. Assert the element count / that the terminating element is included per the spec (repeatUntil tests the just-parsed element).

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement.** In the `repeatUntil` evaluation site(s), after parsing an element, pass that element as `selfContext` to the `HelEvaluator` that evaluates the `repeatUntil` expression. For a repeated struct, `self` is the element's map; for a repeated scalar, `self` is the scalar value; `self.Field` resolves against the element map. Preserve the existing loop semantics (the condition is tested after each element; the matching element is retained).

- [ ] **Step 4: GREEN** + full build. **Step 5: Commit** — `fix(core): supply self context to repeatUntil evaluation`.

---

## Task 4: Multi-level `parent` chain (spec §Reserved Roots)

**Problem (audit #14):** `HelEvaluator` (`:61-63`) sets `currentParent = null` after one `.parent` hop, so `parent.parent.X` (or `instance.parent.parent.X`) yields Null. The Metaparser passes only a single `parentContext`.

**Files:** `hel/HelEvaluator.kt`, `metacodec/Metaparser.kt`; Tests both levels.

- [ ] **Step 1: Failing tests** — evaluator unit: with an ancestor chain wired, `parent.parent.X` reaches the grandparent's field `X`. Metaparser integration: a 3-level nested struct where an inner field's expression references `parent.parent.<outerField>` resolves correctly.

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement.** Change `HelEvaluator` to accept an ordered **ancestor chain** (e.g. `ancestors: List<Map<String, Any>>` from immediate parent outward, defaulted to `parentContext?.let{listOf(it)} ?: emptyList()` for back-compat) and resolve successive `.parent` steps by walking that chain (each `.parent` advances one level; running off the end → Null, matching absent-optional semantics). The Metaparser threads the ancestor chain as it descends (push each enclosing struct's map; the innermost eval sees the full stack). Keep `parent` (single hop) working exactly as before for the common case.

- [ ] **Step 4: GREEN** + full build, no regressions (single-`parent` expressions unchanged — this is the overwhelming majority). **Step 5: Commit** — `fix(core): support multi-level parent chain in HEL`.

---

## Task 5: Undefined-name references raise (spec Conformance #5)

**Problem (audit #11):** the evaluator is schema-less — a bare `Key` access to a name not declared in the struct returns Kotlin `null` (indistinguishable from a declared-but-absent optional), so `undefinedName == x` silently yields Null-semantics instead of the required runtime error.

**Files:** `hel/HelEvaluator.kt`, `metacodec/Metaparser.kt` (+ `ir/Model.kt` if a field-set accessor helps); Tests both.

- [ ] **Step 1: Failing tests** — evaluator unit: given the current struct's declared field-name set, a bare accessor to a name NOT in the set raises `HelEvaluationException("unknown name ...")`; a declared field that is ABSENT (an optional not present in the parsed map) resolves to Null (NOT an error). Metaparser integration: an expression referencing a non-existent field name fails the parse with a clear error; a legitimately-absent optional field referenced in a presence guard yields Null (parse continues).

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement.** Thread the **declared field-name set** of the struct an expression is evaluated in (and, for `parent`/ancestor/`root` steps, the corresponding struct's field set) from the Metaparser (which has the `StructIR`/`FieldIR` definitions) into the evaluator. On a bare `Key` step (first-segment implicit-`instance` access, or after `parent`/`root`), if the key is NOT in the relevant struct's declared field set → raise `HelEvaluationException("reference to undefined field '<name>'")`; if it IS declared but absent from the parsed map → return Null (absent optional). Provide a field-set accessor on the IR if needed (e.g. `StructIR.fieldNames`). Where the evaluator genuinely has no schema for a context (e.g. `stream`/`self` scalars), fall back to the prior lenient behavior. This distinguishes "undefined" (error) from "absent optional" (Null) exactly as the spec requires.

- [ ] **Step 4: GREEN** + full build. **CRITICAL regression watch:** every real expression in the PNG/TIFF fixtures references only declared fields, so none should now error — but this is the highest-risk task; if any existing parse breaks, the field-set threading is wrong (or a fixture references a name via a path the schema-walk doesn't cover) — fix the walk, not by loosening to silence errors. **Step 5: Commit** — `fix(core/hel): raise on undefined-name references (schema-aware), keep absent-optional as Null`.

---

## Task 6: `sizeof` of structs/numeric fields + per-field encoding in Bytes↔String (spec §Functions, §Coercion)

**Problem (audit #13, #12):** `sizeof` (`HelEvaluator.kt:138-142`) handles only Bytes/String; the spec says byte length "of the parsed field **or struct**." And Bytes↔String equality (`:209-210`) hardcodes UTF-8 instead of the field's `bddo:encoding`.

**Files:** `hel/HelEvaluator.kt`, `metacodec/Metaparser.kt` (byte-range recording + encoding), `ir/Model.kt` if needed; Tests both.

- [ ] **Step 1: Failing tests** — `sizeof(<struct field>)` returns the struct's parsed byte length; `sizeof(<numeric field>)` returns its byte width (e.g. `sizeof` of a `uint32` = 4). And a `bytes` field declared with a non-UTF-8 `encoding` compared to a string literal decodes with THAT encoding (construct a field with `latin1` encoding whose bytes differ under utf8 vs latin1, and assert the comparison uses latin1).

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement.**
  - **sizeof of structs:** the Metaparser records per-node byte lengths (it has a `recordByteRange` option and `__byteLength` key). Ensure byte-length recording is on for the parse (or record it for struct nodes), and make `sizeof` of a Map (struct) node read its recorded `__byteLength`. For a **numeric field**, resolve the byte width from the field's `DataTypeIR.bitWidth / 8` — the evaluator needs the field definition for the accessed name; thread the field metadata (or have `sizeof`'s argument accessor return the field's byte length) so a numeric/fixed-width field returns its declared byte size.
  - **encoding:** thread the accessed field's `encoding` (charset) to the evaluator so the Bytes↔String branch in `isEqual` decodes the `ByteArray` operand with the field's charset (default utf8 when unset). This requires the evaluator to know which field produced the Bytes operand — carry the field's encoding alongside the value (or resolve it via the field-set/definition threaded in Task 5).

  If cleanly threading per-operand field metadata proves large, implement it via the same schema/definition channel established in Task 5 (the evaluator already knows the field being accessed) — reuse that, don't build a parallel mechanism.

- [ ] **Step 4: GREEN** + full `./gradlew build`, no regressions (the common `sizeof(bytes/string)` and UTF-8 comparisons unchanged). **Step 5: Commit** — `fix(core/hel): sizeof of structs/numeric fields + per-field encoding in Bytes↔String comparison`.

---

## Self-Review

**Spec coverage:** Conformance #5 (errors) → T1 (incompatible equality) + T5 (undefined name); roots `stream`/`eof()` → T2; `self` → T3; `parent` (multi-level) → T4; `sizeof` field-or-struct → T6; Coercion Bytes-vs-String encoding → T6. Audit items 5, 10, 11, 12, 13, 14 all covered.

**Placeholder scan:** No TBD. T5/T6 note that the field-metadata threading is shared (T6 reuses T5's channel) — a design directive, not a placeholder; each task has a concrete failing test.

**Type consistency:** `HelEvaluator` constructor gains defaulted params (ancestor chain, field-set/schema, stream, self) so existing callers compile; `Metaparser` is the primary caller supplying them. `HelEvaluationException` reused. IR additions (field-name set / byte-width access) are read-only.

**Risk register:** T5 (undefined-name) is highest-risk (a wrong schema-walk could reject valid fixtures); T4/T2/T3 change the Metaparser's eval wiring (guarded by the full parse-behavior test suite). Every task ends with `./gradlew build` across `:core`+`:hdl` and treats the PNG/TIFF/Shapefile fixtures as the regression guard.
