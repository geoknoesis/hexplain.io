# HDL Compiler Conformance Fixes — Implementation Plan (Compliance Plan A of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the HDL-compiler conformance gaps against the published HDL spec (`specification/hdl/index.html`) — the "silent-default" diagnostics (spec Conformance MUST #5), the undeclared-identifier check (MUST #3), and the `<`-operator lexer gap — so the `hdl` module never emits silently-wrong output and never throws on grammar-legal input.

**Architecture:** All changes are in the `hdl` module (`d:/work/hexplain-tools`), plus two small spec-prose alignments in `hexplain.io`. Every fix is test-driven: a test reproduces the current bad behavior (RED), the fix corrects it (GREEN). No behavior on the already-working happy path changes (PNG/TIFF/Shapefile parity + all existing tests stay green).

**Tech Stack:** Kotlin 2.2.10 / Gradle / Jena 5.5.0 / JUnit 5, snakeyaml 2.2. Builds on merged Plans 1–3 (`main` @ current head).

## Global Constraints

- The compiler's façade (`HdlCompiler.compile`/`compileYaml`) MUST return a `CompileResult` with `ok == false` and at least one source-located `ERROR` `Diagnostic` for any input it cannot faithfully compile, and MUST NOT throw. (Spec §Conformance MUST #5.)
- Fixes MUST NOT regress any existing `:hdl:test` (run the full suite each task). The PNG/TIFF/Shapefile parity + YAML equivalence tests are the guardrail.
- Diagnostics carry a real source `Span` where the surface provides one; a synthetic `Span(0,0)` is acceptable only where the AST genuinely lacks position (call it out).
- Reference code in each task is a guide against the live source — the implementer reads the current file and adapts; the concrete assertion in each test is the contract.

## Scope note

Compliance Plan **A of 4**. This plan fixes the `hdl` compiler (audit items 14–18, 20, 21). Plans B (HEL runtime), C (BDDO/DLV execution + SHACL wiring), and D (hx-bundle lifting + generic processor) fix the `core` runtime and are separate. Audit item 3 (IRI minting) is intentionally NOT changed — it is a documented, deterministic scheme that Processing §5 permits as a "MAY" alternative.

---

## File Structure

- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt` — extend sibling validation to all expression positions (T1); validate bundle/asset closed vocabularies (T3).
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt` — switch-discriminator + named-enum-ref + carries/role diagnostics wiring (T2, T3).
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt` — make `emitSwitch` non-throwing (T2).
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Lexer.kt` — `<` IRI-vs-operator disambiguation (T4).
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` — best-effort diagnostic spans + reuse of the same validators (T3, T5).
- Modify (hexplain.io): `specification/hdl/index.html` — align the grammar (drop the unsupported `enum IDENT` form) and the raw-turtle prose (T5).
- Tests: extend `resolve/ResolverTest.kt`, `HdlCompilerTest.kt`, add `parse/LexerOperatorTest.kt`.

---

## Task 1: Diagnose undeclared identifiers in every expression position

**Problem (audit #14, spec MUST #3):** `Resolver.validateSiblings` only checks a *lone* bare name in size/offset/repeat-count/checksum (`Resolver.kt:102-119`). Bare names inside compound expressions and inside `if` / `value` / `repeat until` / switch guard/discriminator / map guard are silently rewritten to `parent.<name>` with no existence check, so `if unknownField == 1`, `bytes[unknownField-4]`, and `value foo/100` compile clean.

**Files:** Modify `resolve/Resolver.kt`; Test `resolve/ResolverTest.kt`.

- [ ] **Step 1: Write failing tests**

Add to `hdl/src/test/kotlin/io/hexplain/hdl/resolve/ResolverTest.kt`:

```kotlin
    private fun diagsFor(src: String) =
        Resolver().resolve(io.hexplain.hdl.parse.HdlParser(io.hexplain.hdl.parse.HdlLexer(src).tokenize()).parse().document).diagnostics

    @Test fun flagsUnknownNameInCompoundSize() {
        assertTrue(diagsFor("format f\nstruct S { a : u32\n b : bytes[nope - 4] }")
            .any { it.message.contains("nope") })
    }
    @Test fun flagsUnknownNameInPresenceAndValueAndUntil() {
        assertTrue(diagsFor("format f\nstruct S { a : u32\n g : u32 if nope == 1 }").any { it.message.contains("nope") })
        assertTrue(diagsFor("format f\nstruct S { a : u32\n v : u32 means x:y value nope / 2 }").any { it.message.contains("nope") })
        assertTrue(diagsFor("format f\nstruct S { a : u32\n r : u8 repeat until nope == 0 }").any { it.message.contains("nope") })
    }
    @Test fun flagsUnknownNameInSwitchAndMapGuards() {
        assertTrue(diagsFor("format f\nstruct S { a : u32\n d : bytes[a] switch nope { \"X\" => T } }\nstruct T { z : u8 }").any { it.message.contains("nope") })
        assertTrue(diagsFor("format f\nuse dct: \"http://purl.org/dc/terms/\"\nstruct S { a : u32\n t : str[a] map { when nope == 1 => dct:title } }").any { it.message.contains("nope") })
    }
    @Test fun doesNotFlagValidSiblingsOrRootsOrFunctions() {
        // valid sibling, reserved roots, functions, self, dotted paths, backtick raw all OK
        assertTrue(diagsFor("format f\nstruct S { a : u32\n b : bytes[a]\n c : bytes[a - 1]\n d : u8 repeat until eof()\n e : u8 repeat until self == 0\n g : u32 if a > 0 }").none { it.message.contains("unknown") })
    }
```

- [ ] **Step 2: Run — expect RED** (`./gradlew :hdl:test --tests "io.hexplain.hdl.resolve.ResolverTest"`), noting which new cases fail.

- [ ] **Step 3: Implement full-expression validation**

Replace `validateSiblings`/`clauseSiblingRefs`/`loneName` in `Resolver.kt` with a version that extracts *every* candidate sibling identifier from *every* expression in every clause and diagnoses unknowns. Add a helper `expressionsOf(clause): List<Expr>` covering: `SizeClause` (ExprSize), `RepeatClause` (count + until), `OffsetClause`, `PresentClause`, `ValueClause`, `SwitchClause` (`on` + each arm `whenExpr`), `MapClause` (each arm `whenExpr` + `value`), `ChecksumClause` (coversExpr; plus the from/to field names). Add `candidateSiblingNames(expr): List<Pair<String,Span>>` that scans `expr.source` (skip when `expr.rawHel`) for bare identifiers, EXCLUDING: identifiers immediately preceded by `.` (dotted-path members), immediately followed by `(` (function calls), the reserved roots/keywords (`RESERVED` + `and/or/not/sizeof/len/count/eof`), and the interiors of single-quoted string literals. (This mirrors `HelSynth.rewriteBareNames`'s own scanning rules — reuse that logic so the set of names it prefixes with `parent.` is exactly the set validated.) Each such name not in the struct's field-name set → `Diagnostic(ERROR, "unknown field reference '<name>'", span)`.

Reference approach:

```kotlin
    private fun validateSiblings(rs: ResolvedStruct, diags: MutableList<Diagnostic>) {
        val names = rs.fields.map { it.decl.name }.toSet()
        for (rf in rs.fields) for (c in rf.decl.clauses) {
            for (e in expressionsOf(c)) for ((name, span) in candidateSiblingNames(e)) {
                if (name !in names) diags.add(Diagnostic(Severity.ERROR, "unknown field reference '$name'", span))
            }
            checksumFieldRefs(c, names, diags)   // from/to field names (existing behavior)
        }
    }
```

Implement `candidateSiblingNames` by scanning `expr.source` char-by-char with the same skip rules `HelSynth.rewriteBareNames` uses (afterDot / followedByParen / reserved / keyword / inside-single-quote). Keep the checksum from/to field-name check.

- [ ] **Step 4: Run — GREEN**, full `:hdl:test` — no regressions (existing valid fixtures must not trip the broader check; if a legitimate expression uses a name that is a sibling-of-parent-including-self, confirm it resolves — e.g. a field's `value` referencing its own name is a valid sibling and must NOT be flagged).

- [ ] **Step 5: Commit** — `fix(hdl): diagnose undeclared identifiers in all expression positions`.

---

## Task 2: `switch` with a literal arm but no discriminator → diagnostic, not exception

**Problem (audit #15, MUST #5):** `switch { "IHDR" => S }` is grammar-legal but `TurtleEmitter.emitSwitch` calls `error("switch arm without discriminator")` → uncaught exception.

**Files:** Modify `HdlCompiler.kt` (add validation) and `emit/TurtleEmitter.kt` (make non-throwing); Test `HdlCompilerTest.kt`.

- [ ] **Step 1: Failing test** in `HdlCompilerTest.kt`:

```kotlin
    @Test fun switchLiteralArmWithoutDiscriminatorIsDiagnosticNotThrow() {
        val src = "format f\nstruct S { a : u32\n d : bytes[a] switch { \"IHDR\" => T } }\nstruct T { z : u8 }"
        val r = assertDoesNotThrow { HdlCompiler().compile(src) }
        assertFalse(r.ok)
        assertTrue(r.diagnostics.any { it.message.contains("discriminator", ignoreCase = true) })
    }
    @Test fun switchWithWhenGuardArmsNeedsNoDiscriminator() {
        val src = "format f\nstruct S { a : u32\n d : bytes[a] switch { when a == 1 => T } }\nstruct T { z : u8 }"
        assertTrue(HdlCompiler().compile(src).ok, "when-guard arms are self-contained; no 'on' needed")
    }
```

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement.** In `HdlCompiler` add a validation pass (alongside `validateEnumeratedValues`) that, for each `SwitchClause` with `on == null` and at least one arm whose `matchValue != null` (a literal arm), emits `Diagnostic(ERROR, "switch has a literal arm but no discriminator expression (add 'switch <expr> { ... }')", field.span)`. In `TurtleEmitter.emitSwitch`, replace the `error(...)` with a safe skip (emit no rule for a discriminator-less literal arm) so emission can't throw even if reached.

- [ ] **Step 4: GREEN** + full suite. **Step 5: Commit** — `fix(hdl): diagnose discriminator-less switch instead of throwing`.

---

## Task 3: Closed-vocabulary + missing-value diagnostics (enum ref, carries prefix, part role, YAML missing keys)

**Problem (audit #16, #17, #18, MUST #5):** named enum ref `enum Name` silently emits an empty Enumeration (`TurtleEmitter.kt:228`); an unknown/unbound `carries` prefix silently emits `abnd:carriesAspect <…/bundle>` (`TurtleEmitter.kt:356-358`); an unknown bare part-role mints `abnd:<Name>` with no compile error (`TurtleEmitter.kt:352-353`); the YAML loader defaults missing part `role`→`"?"`, `extension`→`""`, map `property`→`"?"`.

**Files:** Modify `resolve/Resolver.kt` (or a validation pass in `HdlCompiler.kt`), `yaml/YamlLoader.kt`; Test `HdlCompilerTest.kt`.

- [ ] **Step 1: Failing tests** in `HdlCompilerTest.kt`:

```kotlin
    private fun compile(src: String) = HdlCompiler().compile(src)
    @Test fun namedEnumRefIsDiagnostic() {
        assertFalse(compile("format f\nstruct S { ct : u8 enum ColorType }").ok)
    }
    @Test fun unknownCarriesPrefixIsDiagnostic() {
        // 'ageom' is not declared with `use`
        val r = compile("format f\nbundle B @bound-by naming-convention { part \".x\" role Payload carries ageom: }")
        assertFalse(r.ok); assertTrue(r.diagnostics.any { it.message.contains("ageom") })
    }
    @Test fun unknownPartRoleIsDiagnostic() {
        val r = compile("format f\nbundle B @bound-by naming-convention { part \".x\" role NotARealRole }")
        assertFalse(r.ok); assertTrue(r.diagnostics.any { it.message.contains("NotARealRole") })
    }
    @Test fun knownRolesAndDeclaredCarriesStillCompile() {
        assertTrue(compile("format f\nuse ageom: \"https://hexplain.io/ns/aspect/geometry#\"\nbundle B @bound-by naming-convention { part \".x\" role GeometryCarrier carries ageom: }").ok)
    }
```

And in `yaml/YamlBundleTest.kt` (or YamlLoaderTest): a YAML bundle part missing `role`, and an asset part missing `name`, each yield `!ok`.

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement a bundle/asset validation pass** (in `HdlCompiler`, reading `ResolvedDoc.bundles`/`assets`, or in the Resolver). For each `PartSpecDecl`/`AssetPartDecl`:
  - `role` MUST be a known register concept (`io.hexplain.hdl.emit.vocab.ABND.ROLE_BY_NAME` keys) OR a CURIE whose prefix is bound in `doc.prefixes`; else ERROR "unknown part role '<role>'".
  - `carries` (when present) MUST be a bound prefix (in `doc.prefixes`); else ERROR "undeclared aspect prefix '<carries>' (add a `use` declaration)".
  - `extension` (bundle part) MUST be non-empty; a part `role`/`name` MUST be non-empty.
  For the **named enum ref**, emit ERROR "named enum references are not supported; declare the enumeration inline" for any `EnumClause` with a non-null `ref` (both surfaces). Also make the YAML loader emit an ERROR (not a silent default) when a bundle part lacks `role`/`extension`, an asset part lacks `name`/`role`, or a map arm lacks `property` — mirror the existing `fieldDecl` missing-type/name diagnostics.

- [ ] **Step 4: GREEN** + full suite (ensure the existing `shapefile.hx` — which uses declared `use` prefixes and register roles — still compiles ok, and BundleShaclTest's deliberate `NotARealRole` negative test still exercises SHACL: adjust that test if it now fails compilation — it should assert `!compile().ok` OR keep using SHACL on hand-built Turtle; coordinate so the negative SHACL intent is preserved, e.g. validate a hand-written bad-role graph rather than compiler output).

- [ ] **Step 5: Commit** — `fix(hdl): diagnose named-enum-ref, unknown carries-prefix/part-role, missing YAML bundle keys`.

---

## Task 4: `<` / `<=` / `<<` in text-surface expressions

**Problem (audit #19):** `Lexer` claims every `<` for `iri()`, so an unbracketed HEL comparison/shift using `<` mis-parses. HEL defines `<`,`<=`,`<<` as operators and HDL clause interiors are HEL, so `if x < 5` is spec-valid.

**Files:** Modify `parse/Lexer.kt`; Test `parse/LexerOperatorTest.kt` (+ a parser/compiler test).

- [ ] **Step 1: Failing test** — `hdl/src/test/kotlin/io/hexplain/hdl/parse/LexerOperatorTest.kt`:

```kotlin
package io.hexplain.hdl.parse
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
class LexerOperatorTest {
    @Test fun angleBracketIriStillLexes() {
        // use-decl IRI form must still work
        val toks = HdlLexer("use ar: <https://hexplain.io/ns/aspect/raster#>").tokenize()
        assertTrue(toks.any { it.kind == TokKind.IRI && it.text.startsWith("https://") })
    }
    @Test fun unbracketedLessThanIsAnOperatorInAnExpression() {
        // an `if x < 5` presence clause must compile (x is a sibling)
        val r = io.hexplain.hdl.HdlCompiler().compile("format f\nstruct S { x : u32\n g : u32 if x < 5 }")
        assertTrue(r.ok, "${r.diagnostics}")
        val ttl = r.toTurtle()
        assertTrue(ttl.contains("isPresentIf"))
    }
    @Test fun shiftOperatorLexes() {
        val r = io.hexplain.hdl.HdlCompiler().compile("format f\nstruct S { n : u32\n b : bytes[n << 2] }")
        assertTrue(r.ok, "${r.diagnostics}")
    }
}
```

- [ ] **Step 2: RED.**

- [ ] **Step 3: Implement disambiguation in `HdlLexer`.** Change the `<` handling so it begins an IRI token ONLY when it looks like one: the character immediately after `<` is not whitespace, not `<`, and not `=`, AND a closing `>` occurs before the next whitespace/newline. Otherwise emit an operator token: `<<` (if followed by `<`), `<=` (if followed by `=`), else `<`. Ensure these operator tokens flow into the same expression-run capture that already handles `>`/`>=`/`>>` and other operators (they are captured into `BRACKET_EXPR`/`exprFromAccessorRun` runs as raw text and passed to HEL, which already supports `<`,`<=`,`<<`). Confirm the `use`-decl path still receives the `IRI` token.

- [ ] **Step 4: GREEN** + full suite (esp. LexerTest, ParserClauseTest, shapefile.hx which uses `use … <…>`). **Step 5: Commit** — `fix(hdl): lex unbracketed <, <=, << as operators; keep <iri> in use-decls`.

---

## Task 5: YAML diagnostic source locations + spec-prose alignment

**Problem (audit #21, #20):** YAML diagnostics all use `Span(0,0)`; and the HDL spec's grammar lists an `enum IDENT` form that the compiler (correctly) doesn't support, while the §Escape-Hatch prose says raw-turtle works at "struct or field scope" though the normative ABNF (and impl) confine it to struct scope.

**Files:** Modify `yaml/YamlLoader.kt`; `specification/hdl/index.html` (hexplain.io).

- [ ] **Step 1: YAML spans (best-effort).** Change `YamlLoader` to use snakeyaml's `compose`/`Node` API (or `loadAll` with marks) so diagnostics carry the YAML line/column where available, replacing the constant `SPAN = Span(0,0)`. Where a node's mark is unavailable, keep `Span(0,0)`. Add a test asserting a malformed-field diagnostic reports a line &gt; 0 for a multi-line YAML input. (If threading marks through is disproportionate, at minimum thread the top-level struct/field line; document the limitation. This step is a quality improvement — do not let it block the plan; if it proves large, split it out and mark the rest of the plan complete.)

- [ ] **Step 2: Spec alignment (hexplain.io `specification/hdl/index.html`).**
  - In the §Grammar ABNF, change the enum production to drop the unsupported named-reference alternative: `/ "enum" [ "flags" ] "{" enumpair *( "," enumpair ) "}"` (remove the `IDENT /` alternative), matching the compiler (which now diagnoses `enum <ref>`).
  - In §Escape Hatch, change "at struct or field scope" to "at struct scope" (matching the normative ABNF `raw-block` production and the implementation; note a struct-scope block can inject any field triple).

- [ ] **Step 3: Verify** — full `:hdl:test` green; the spec HTML still parses (balanced tags). **Step 4: Commit** — two commits: `fix(hdl): best-effort source locations for YAML diagnostics` (hexplain-tools) and `docs(hdl): align spec grammar/prose with compiler (enum, raw-turtle scope)` (hexplain.io).

---

## Self-Review

**Spec coverage:** MUST #3 → T1; MUST #5 (never-throw) → T2; MUST #5 (silent-default ERRORs) → T3; `<`-operator spec deviation → T4; source-located diagnostics + grammar/prose consistency → T5. Items 14–18, 20, 21 covered. Items 1–13, 19(core), 22–23 are Plans B/C/D. Item 3 intentionally excluded (compliant).

**Placeholder scan:** No TBD. T5 Step 1 is explicitly allowed to be split out if disproportionate — not a placeholder, a scoped fallback.

**Type consistency:** New validation reuses `ResolvedDoc.{structs,bundles,assets,prefixes}`, `ABND.ROLE_BY_NAME`, `HelSynth` scanning rules, and the existing `Diagnostic`/`Severity`/`Span` types. No new public types.

**Regression guardrail:** every task runs the full `:hdl:test`; the PNG/TIFF/Shapefile parity + YAML equivalence + BundleShaclTest are the safety net (T3 explicitly coordinates the BundleShaclTest negative case).
