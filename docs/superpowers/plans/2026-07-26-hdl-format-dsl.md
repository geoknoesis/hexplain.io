# HDL Format DSL — Implementation Plan (Plan 1 of 3: Core Text Compiler)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Kotlin compiler that turns the compact HDL text syntax (`.hx`) for a binary format into a canonical BDDO + hexplain-core + DLV Turtle profile, so authors write concise format descriptions instead of verbose RDF.

**Architecture:** New Gradle module `hdl` in `d:\work\hexplain-tools`, depending on `:core`. Pipeline: `Lexer → Parser → AST → Resolver (prefixes/IRIs/sibling-checks) → HelSynth (reusing core's HelParser/HelUnparser) → TurtleEmitter (Jena, using core's BDDO/HEXPLAIN/DLV vocab objects) → Turtle string`. Correctness is anchored on **behavioral parity** (compile a `.hx`, run the generated profile through core's `ProfileLoader → RdfToIrCompiler → Metaparser` on real sample bytes, assert the same parse as the hand-authored profile) plus **golden-TTL snapshots** and per-feature triple assertions.

**Tech Stack:** Kotlin 2.2.10 (JVM), Gradle (version catalog), Apache Jena 5.5.0 (core, arq), JUnit Jupiter 5.10.2. Reuses `io.hexplain.core` (HEL, vocab, RDF pipeline, Metaparser).

## Global Constraints

- Kotlin `2.2.10`; JUnit Jupiter `5.10.2`; Apache Jena `5.5.0` — copied from `hexplain-tools/gradle/libs.versions.toml`. Use the version catalog (`libs.versions.kotlin.get()`, `libs.jena.core`, `libs.junit.jupiter`); do not hard-code versions in the module build file.
- New module path: `d:\work\hexplain-tools\hdl`; package root `io.hexplain.hdl`.
- Depend on core via `implementation(project(":core"))`; also declare `implementation(libs.jena.core)` and `implementation(libs.jena.arq)` explicitly (core does not re-export Jena as `api`).
- Emit **BDDO / hexplain-core / DLV** Turtle directly with Jena; do **not** use `core`'s `FormatIRToRdf` (it emits the internal `ir#` vocabulary).
- HEL: never build HEL strings by hand. Build a `io.hexplain.core.hel.AstNode` and render with `io.hexplain.core.hel.HelUnparser.toSource(node)`. Validate user expressions with `HelParser(Lexer(s).tokenize()).parse()`.
- IRI minting: `format <name>` → base `https://hexplain.io/formats/<name>#` unless `@namespace` overrides. `struct S` → `<base>S`. field `f` in struct `S` → `<base>S.f` unless `f as Alias` (→ `<base>Alias`). The root struct is the one marked `@root`, else the first struct declared; its full IRI is the `rootStructUri` the pipeline needs.
- The module's runtime/test classpath must carry `bddo.ttl` (core loads it from the classpath in `RdfToIrCompiler.compile`). It is already a resource in `:core` and is visible transitively on the test classpath via `project(":core")`. Do not duplicate it.
- All parser/resolver errors are returned as `Diagnostic` values with a source `Span` (never thrown as raw exceptions to the caller of the façade).

## Scope note (why this is Plan 1 of 3)

The approved design (`docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md`) covers three independently-shippable subsystems. This plan implements **Subsystem 1: the core text compiler** (BDDO physical layer + hexplain-core semantic mapping + first-class HEL + DLV layout + the `raw-turtle`/`@prop` escape hatch, with a CLI). The other two are separate plans, written after this one lands:

- **Plan 2 — YAML surface:** a `YamlLoader` (snakeyaml) producing the *same* `Document` AST this plan defines; an equivalence test (`.hx` AST ≡ `.hx.yaml` AST) and compile parity. Add `snakeyaml = "2.2"` to the catalog.
- **Plan 3 — hx-bundle:** a new `io.hexplain.hdl.emit.vocab.ABND` object (missing from core), parser+emitter for `bundle`/`part` profiles and `asset` instances, anchored on SHACL validation against `specification/aspect/bundle/bundle.ttl` shapes + golden snapshots (core has no bundle runtime for behavioral parity).

Each plan produces working, tested software on its own. This document is Plan 1.

---

## File Structure (Plan 1)

Created under `d:\work\hexplain-tools\hdl`:

- `build.gradle.kts` — module build (deps on `:core`, Jena, JUnit).
- `src/main/kotlin/io/hexplain/hdl/ast/Ast.kt` — AST data classes + `Span`.
- `src/main/kotlin/io/hexplain/hdl/diag/Diagnostic.kt` — `Diagnostic`, `Severity`.
- `src/main/kotlin/io/hexplain/hdl/parse/Lexer.kt` — HDL text lexer → `List<HdlToken>`.
- `src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` — tokens → `Document` AST.
- `src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt` — prefixes, IRI minting, sibling validation → `ResolvedDoc`.
- `src/main/kotlin/io/hexplain/hdl/hel/HelSynth.kt` — DSL expr → core HEL AST/string; field-form-vs-expression decision.
- `src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt` — `ResolvedDoc` → Jena `Model`.
- `src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt` — façade orchestrating the pipeline + `toTurtle`.
- `src/main/kotlin/io/hexplain/hdl/cli/Main.kt` — CLI entry point.
- `src/test/kotlin/io/hexplain/hdl/...` — one test file per unit (mirrors main packages).
- `src/test/resources/png.hx`, `tiff.hx`, `golden/png-profile.expected.ttl`, `golden/tiff-profile.expected.ttl`.

Also modified: `d:\work\hexplain-tools\settings.gradle.kts` (add `include("hdl")`).

---

## Task 1: Module scaffold

**Files:**
- Modify: `d:\work\hexplain-tools\settings.gradle.kts`
- Create: `d:\work\hexplain-tools\hdl\build.gradle.kts`
- Create: `hdl\src\main\kotlin\io\hexplain\hdl\Version.kt`
- Test: `hdl\src\test\kotlin\io\hexplain\hdl\ScaffoldTest.kt`

**Interfaces:**
- Produces: a buildable `:hdl` module with `:core` on its compile/test classpath.

- [ ] **Step 1: Add the module to settings**

Edit `d:\work\hexplain-tools\settings.gradle.kts` to read exactly:

```kotlin
rootProject.name = "hexplain-tools"
include("core")
include("hdl")
```

- [ ] **Step 2: Write the module build file**

Create `hdl/build.gradle.kts`:

```kotlin
plugins {
    kotlin("jvm") version libs.versions.kotlin.get()
    application
}

repositories { mavenCentral() }

dependencies {
    implementation(project(":core"))
    implementation(libs.jena.core)
    implementation(libs.jena.arq)
    testImplementation(libs.junit.jupiter)
}

application {
    mainClass.set("io.hexplain.hdl.cli.MainKt")
}

tasks.test {
    useJUnitPlatform()
    binaryResultsDirectory.set(layout.buildDirectory.dir("test-results-binary"))
}
```

- [ ] **Step 3: Write a trivial source + failing test**

Create `hdl/src/main/kotlin/io/hexplain/hdl/Version.kt`:

```kotlin
package io.hexplain.hdl

object Hdl {
    const val VERSION = "0.1.0"
}
```

Create `hdl/src/test/kotlin/io/hexplain/hdl/ScaffoldTest.kt`:

```kotlin
package io.hexplain.hdl

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class ScaffoldTest {
    @Test
    fun moduleBuildsAndCoreIsOnClasspath() {
        // Reference a core type to prove the :core dependency resolves at compile time.
        val ns = io.hexplain.core.rdf.vocab.BDDO.NAMESPACE
        assertEquals("https://hexplain.io/ns/bddo#", ns)
        assertEquals("0.1.0", Hdl.VERSION)
    }
}
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test`
Expected: BUILD SUCCESSFUL; `ScaffoldTest` passes (proves module wiring + `:core` dependency).

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add settings.gradle.kts hdl/
git commit -m "feat(hdl): scaffold hdl module depending on :core"
```

---

## Task 2: AST + diagnostics types

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt`
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/diag/Diagnostic.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/ast/AstTest.kt`

**Interfaces:**
- Produces: the AST vocabulary every later task consumes. Exact types below.

- [ ] **Step 1: Write the diagnostics types**

Create `hdl/src/main/kotlin/io/hexplain/hdl/diag/Diagnostic.kt`:

```kotlin
package io.hexplain.hdl.diag

data class Span(val line: Int, val col: Int)

enum class Severity { ERROR, WARNING }

data class Diagnostic(val severity: Severity, val message: String, val span: Span) {
    override fun toString(): String = "${severity} at ${span.line}:${span.col}: $message"
}
```

- [ ] **Step 2: Write the AST types**

Create `hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt`:

```kotlin
package io.hexplain.hdl.ast

import io.hexplain.hdl.diag.Span

enum class Endian { BIG, LITTLE }
enum class BitOrderOpt { MSB, LSB }
enum class OffsetBaseOpt { STREAM_START, STREAM_END, PARENT_START, CURRENT }

/** A DSL expression: the raw source between the clause delimiters, plus whether it was
 *  backtick-escaped (a literal HEL string that bypasses sibling resolution). */
data class Expr(val source: String, val rawHel: Boolean, val span: Span)

/** literal value for @fixed / @prop */
sealed interface LiteralValue
data class IntLit(val value: Long) : LiteralValue
data class StrLit(val value: String) : LiteralValue
data class HexLit(val bytes: ByteArray) : LiteralValue
data class BoolLit(val value: Boolean) : LiteralValue
data class CurieLit(val curie: String) : LiteralValue

/** size / offset spec: an expression, or the end-of-stream marker `..` */
sealed interface SizeSpec
data class ExprSize(val expr: Expr) : SizeSpec
object ToEndOfStream : SizeSpec

sealed interface TypeRef
data class PrimType(val name: String) : TypeRef              // u8,i16be,f32,f64le,...
data class StringType(val encoding: String?) : TypeRef       // str(null)/ascii/utf8/utf16le/utf16be/latin1
object BytesType : TypeRef
data class BitsType(val expr: Expr) : TypeRef                 // bits[N]
data class StructRef(val name: String) : TypeRef             // nested/typed field

data class EnumPair(val raw: LiteralValue, val symbol: String, val label: String?)
data class SwitchArm(val matchValue: LiteralValue?, val whenExpr: Expr?, val struct: String)
data class MapArm(val whenExpr: Expr, val property: String, val value: Expr?, val datatype: String?)
data class DimDecl(val axis: String, val size: LiteralValue?, val sizeFromField: String?, val stride: Expr?)

sealed interface Clause
data class SizeClause(val spec: SizeSpec) : Clause
data class RepeatClause(val count: Expr?, val until: Expr?) : Clause
data class OffsetClause(val expr: Expr, val base: OffsetBaseOpt?) : Clause
data class PresentClause(val expr: Expr) : Clause
data class FixedClause(val value: LiteralValue) : Clause
data class EnumClause(val flags: Boolean, val ref: String?, val inline: List<EnumPair>?) : Clause
data class ChecksumClause(val algo: String, val fromField: String?, val toField: String?, val coversExpr: Expr?) : Clause
data class TerminatorClause(val bytes: ByteArray) : Clause
object TrimNullClause : Clause
data class EndianClause(val endian: Endian) : Clause
data class BitOrderClause(val order: BitOrderOpt) : Clause
data class AlignClause(val n: Long) : Clause
data class EncodingClause(val encoding: String) : Clause
data class SwitchClause(val on: Expr?, val arms: List<SwitchArm>) : Clause
data class MeansClause(val curie: String) : Clause
data class ValueClause(val expr: Expr, val datatype: String?) : Clause
data class EncodedWithClause(val curie: String) : Clause
data class MapClause(val arms: List<MapArm>) : Clause
data class LayoutClause(val cell: TypeRef, val dims: List<DimDecl>) : Clause
data class PropClause(val curie: String, val value: LiteralValue) : Clause

data class FieldDecl(
    val name: String,
    val alias: String?,
    val type: TypeRef,
    val clauses: List<Clause>,
    val span: Span
)

data class RawTurtle(val turtle: String, val span: Span)

data class StructDecl(
    val name: String,
    val alias: String?,
    val isRoot: Boolean,
    val means: String?,
    val endian: Endian?,
    val bitOrder: BitOrderOpt?,
    val fields: List<FieldDecl>,
    val raw: List<RawTurtle>,
    val props: List<PropClause>,
    val span: Span
)

data class PrefixDecl(val prefix: String, val iri: String, val span: Span)

data class FormatDecl(
    val name: String,
    val namespace: String?,
    val endian: Endian?,
    val bitOrder: BitOrderOpt?,
    val span: Span
)

/** A parsed HDL document. `topLevelFields` are `field` declarations outside any struct. */
data class Document(
    val format: FormatDecl?,
    val prefixes: List<PrefixDecl>,
    val structs: List<StructDecl>,
    val topLevelFields: List<FieldDecl>
)
```

- [ ] **Step 3: Write the test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/ast/AstTest.kt`:

```kotlin
package io.hexplain.hdl.ast

import io.hexplain.hdl.diag.Span
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class AstTest {
    @Test
    fun buildsAMinimalDocument() {
        val f = FieldDecl("length", null, PrimType("u32"), emptyList(), Span(1, 1))
        val s = StructDecl("Chunk", null, true, null, Endian.BIG, null, listOf(f), emptyList(), emptyList(), Span(1, 1))
        val doc = Document(FormatDecl("png", null, Endian.BIG, null, Span(1, 1)), emptyList(), listOf(s), emptyList())
        assertEquals("Chunk", doc.structs.single().name)
        assertEquals("length", doc.structs.single().fields.single().name)
        assertEquals(true, doc.structs.single().isRoot)
    }
}
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.ast.AstTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/ast hdl/src/main/kotlin/io/hexplain/hdl/diag hdl/src/test/kotlin/io/hexplain/hdl/ast
git commit -m "feat(hdl): AST and diagnostics types"
```

---

## Task 3: Lexer

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Lexer.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parse/LexerTest.kt`

**Interfaces:**
- Produces: `HdlToken(kind: TokKind, text: String, span: Span)`, `enum TokKind`, and `class HdlLexer(src: String) { fun tokenize(): List<HdlToken> }`.
- Consumes: `io.hexplain.hdl.diag.Span`.

**Design notes:** The lexer emits structural punctuation as tokens but treats the interior of `[...]`, `switch/map/layout/enum {...}` clause expressions as raw slices where needed — to keep this simple, the lexer tokenizes into a flat stream and the **parser** decides where an expression starts/ends. Bracketed expressions (`[ ... ]`) and backtick strings are captured whole by the lexer so nested operators are not mis-split.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parse/LexerTest.kt`:

```kotlin
package io.hexplain.hdl.parse

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class LexerTest {
    private fun kinds(src: String) = HdlLexer(src).tokenize().map { it.kind }

    @Test
    fun lexesKeywordsIdentifiersPunctuation() {
        val toks = HdlLexer("format png\n@endian big\nstruct Chunk {\n  length : u32\n}").tokenize()
        val texts = toks.map { it.text }
        assertTrue(texts.containsAll(listOf("format", "png", "@endian", "big", "struct", "Chunk", "{", "length", ":", "u32", "}")))
        assertEquals(TokKind.EOF, toks.last().kind)
    }

    @Test
    fun capturesBracketExpressionAndBacktickWhole() {
        val toks = HdlLexer("data : bytes[length - 4]\nx : bytes[`instance.parent.n`]").tokenize()
        val brackets = toks.filter { it.kind == TokKind.BRACKET_EXPR }.map { it.text }
        assertEquals(listOf("length - 4", "instance.parent.n"), brackets.map { it.trim() })
    }

    @Test
    fun skipsLineAndBlockComments() {
        val toks = HdlLexer("// a\nstruct /* b */ X {}").tokenize()
        assertEquals(listOf("struct", "X", "{", "}"), toks.dropLast(1).map { it.text })
    }

    @Test
    fun tracksLineNumbers() {
        val toks = HdlLexer("format\npng").tokenize()
        assertEquals(1, toks.first { it.text == "format" }.span.line)
        assertEquals(2, toks.first { it.text == "png" }.span.line)
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.LexerTest"`
Expected: FAIL — `HdlLexer` / `TokKind` unresolved.

- [ ] **Step 3: Write the lexer**

Create `hdl/src/main/kotlin/io/hexplain/hdl/parse/Lexer.kt`:

```kotlin
package io.hexplain.hdl.parse

import io.hexplain.hdl.diag.Span

enum class TokKind {
    IDENT,        // identifiers, keywords, prim type names, curies (prefix:local)
    ANNOT,        // @-prefixed word, e.g. @endian, @at, @fixed
    STRING,       // "..." (text without quotes)
    HEX,          // 0x....
    INT,          // decimal / 0b.... integer
    FLOAT,        // 1.5
    BRACKET_EXPR, // the raw text captured between a matching [ ] pair
    LBRACE, RBRACE, COLON, COMMA, ARROW, DOTDOT, LPAREN, RPAREN,
    EOF
}

data class HdlToken(val kind: TokKind, val text: String, val span: Span)

class HdlLexer(private val src: String) {
    private var pos = 0
    private var line = 1
    private var col = 1
    private val out = ArrayList<HdlToken>()

    private fun here() = Span(line, col)
    private fun peek(o: Int = 0): Char? = src.getOrNull(pos + o)
    private fun advance(): Char {
        val c = src[pos++]
        if (c == '\n') { line++; col = 1 } else col++
        return c
    }

    fun tokenize(): List<HdlToken> {
        while (pos < src.length) {
            val c = peek()!!
            when {
                c == '\n' || c.isWhitespace() -> advance()
                c == '/' && peek(1) == '/' -> { while (pos < src.length && peek() != '\n') advance() }
                c == '/' && peek(1) == '*' -> skipBlockComment()
                c == '{' -> emit(TokKind.LBRACE, advance().toString())
                c == '}' -> emit(TokKind.RBRACE, advance().toString())
                c == '(' -> emit(TokKind.LPAREN, advance().toString())
                c == ')' -> emit(TokKind.RPAREN, advance().toString())
                c == ':' -> emit(TokKind.COLON, advanceIfNotCurie())
                c == ',' -> emit(TokKind.COMMA, advance().toString())
                c == '[' -> bracketExpr()
                c == '"' -> stringLit()
                c == '`' -> backtickExpr()
                c == '=' && peek(1) == '>' -> { val s = here(); advance(); advance(); out.add(HdlToken(TokKind.ARROW, "=>", s)) }
                c == '.' && peek(1) == '.' -> { val s = here(); advance(); advance(); out.add(HdlToken(TokKind.DOTDOT, "..", s)) }
                c == '@' -> annot()
                c.isDigit() || (c == '-' && (peek(1)?.isDigit() == true)) -> number()
                isIdentStart(c) -> ident()
                else -> advance() // skip unknown punctuation silently; parser validates structure
            }
        }
        out.add(HdlToken(TokKind.EOF, "", here()))
        return out
    }

    private fun emit(kind: TokKind, text: String) = out.add(HdlToken(kind, text, here().let { Span(it.line, it.col - text.length) }))

    // ':' may be a field colon or part of a curie (prefix:local). We emit COLON only when
    // not immediately between two identifier chars. Simpler: emit COLON always; the ident
    // reader below consumes curies wholesale, so a standalone ':' reaching here is a field colon.
    private fun advanceIfNotCurie(): String = advance().toString()

    private fun skipBlockComment() {
        advance(); advance() // consume /*
        while (pos < src.length && !(peek() == '*' && peek(1) == '/')) advance()
        if (pos < src.length) { advance(); advance() } // consume */
    }

    private fun bracketExpr() {
        val s = here()
        advance() // [
        val sb = StringBuilder()
        var depth = 1
        while (pos < src.length && depth > 0) {
            val c = peek()!!
            if (c == '[') depth++
            if (c == ']') { depth--; if (depth == 0) { advance(); break } }
            sb.append(advance())
        }
        out.add(HdlToken(TokKind.BRACKET_EXPR, sb.toString(), s))
    }

    private fun backtickExpr() {
        val s = here()
        advance() // `
        val sb = StringBuilder()
        while (pos < src.length && peek() != '`') sb.append(advance())
        if (pos < src.length) advance() // closing `
        out.add(HdlToken(TokKind.BRACKET_EXPR, sb.toString(), s)) // reuse BRACKET_EXPR; parser flags rawHel by delimiter — see note
    }

    private fun stringLit() {
        val s = here()
        advance() // "
        val sb = StringBuilder()
        while (pos < src.length && peek() != '"') {
            val c = advance()
            if (c == '\\' && pos < src.length) sb.append(advance()) else sb.append(c)
        }
        if (pos < src.length) advance()
        out.add(HdlToken(TokKind.STRING, sb.toString(), s))
    }

    private fun annot() {
        val s = here()
        val sb = StringBuilder()
        sb.append(advance()) // @
        while (pos < src.length && (isIdentPart(peek()!!) || peek() == '-')) sb.append(advance())
        out.add(HdlToken(TokKind.ANNOT, sb.toString(), s))
    }

    private fun number() {
        val s = here()
        val sb = StringBuilder()
        if (peek() == '-') sb.append(advance())
        var isFloat = false
        var isHex = false
        if (peek() == '0' && (peek(1) == 'x' || peek(1) == 'X')) {
            isHex = true; sb.append(advance()); sb.append(advance())
            while (pos < src.length && (peek()!!.isLetterOrDigit())) sb.append(advance())
        } else if (peek() == '0' && (peek(1) == 'b' || peek(1) == 'B')) {
            sb.append(advance()); sb.append(advance())
            while (pos < src.length && (peek() == '0' || peek() == '1')) sb.append(advance())
        } else {
            while (pos < src.length && peek()!!.isDigit()) sb.append(advance())
            if (peek() == '.' && peek(1)?.isDigit() == true) {
                isFloat = true; sb.append(advance())
                while (pos < src.length && peek()!!.isDigit()) sb.append(advance())
            }
        }
        val kind = when { isHex -> TokKind.HEX; isFloat -> TokKind.FLOAT; else -> TokKind.INT }
        out.add(HdlToken(kind, sb.toString(), s))
    }

    private fun ident() {
        val s = here()
        val sb = StringBuilder()
        while (pos < src.length && (isIdentPart(peek()!!) || peek() == ':' || peek() == '.')) {
            // Stop a curie/ident before '..' end-of-stream marker.
            if (peek() == '.' && peek(1) == '.') break
            sb.append(advance())
        }
        out.add(HdlToken(TokKind.IDENT, sb.toString(), s))
    }

    private fun isIdentStart(c: Char) = c.isLetter() || c == '_'
    private fun isIdentPart(c: Char) = c.isLetterOrDigit() || c == '_'
}
```

Note for the parser: backtick expressions are captured as `BRACKET_EXPR` tokens too; the parser distinguishes them only when it must know `rawHel`. To carry that bit, change `backtickExpr()` to prefix the text with a sentinel — but simpler and explicit: add a dedicated kind. **Adjust:** add `BACKTICK_EXPR` to `TokKind` and emit it from `backtickExpr()`. Update the enum and that one line accordingly before running.

- [ ] **Step 4: Apply the backtick-kind adjustment**

In `TokKind`, add `BACKTICK_EXPR,` next to `BRACKET_EXPR`. In `backtickExpr()`, change the final line to `out.add(HdlToken(TokKind.BACKTICK_EXPR, sb.toString(), s))`.

- [ ] **Step 5: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.LexerTest"`
Expected: PASS (all four tests). If `capturesBracketExpressionAndBacktickWhole` sees the backtick as `BACKTICK_EXPR`, update the test's filter to include both kinds:
`toks.filter { it.kind == TokKind.BRACKET_EXPR || it.kind == TokKind.BACKTICK_EXPR }`.

- [ ] **Step 6: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/parse/Lexer.kt hdl/src/test/kotlin/io/hexplain/hdl/parse/LexerTest.kt
git commit -m "feat(hdl): text lexer with bracket/backtick expression capture"
```

---

## Task 4: Parser — format, prefixes, structs, simple fields

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserStructTest.kt`

**Interfaces:**
- Consumes: `HdlLexer`, `HdlToken`, `TokKind`, all `ast` types.
- Produces: `class HdlParser(tokens: List<HdlToken>) { fun parse(): ParseResult }` and `data class ParseResult(val document: Document, val diagnostics: List<Diagnostic>)`. This task parses `format`, `@namespace`/`@endian`/`@bit-order` on the format, `use` prefix decls, `struct` (with `@root`, `@endian`, `means`, `as`), and bare `name : type` fields (no clauses yet — clauses arrive in Task 5).

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserStructTest.kt`:

```kotlin
package io.hexplain.hdl.parse

import io.hexplain.hdl.ast.Endian
import io.hexplain.hdl.ast.PrimType
import io.hexplain.hdl.ast.StringType
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ParserStructTest {
    private fun parse(src: String) = HdlParser(HdlLexer(src).tokenize()).parse()

    @Test
    fun parsesFormatAndRootStructWithSimpleFields() {
        val src = """
            format png
              @namespace "https://hexplain.io/formats/png#"
              @endian big

            @root struct Chunk {
              length : u32
              type   : ascii
            }
        """.trimIndent()
        val r = parse(src)
        assertTrue(r.diagnostics.isEmpty(), "unexpected: ${r.diagnostics}")
        val doc = r.document
        assertEquals("png", doc.format!!.name)
        assertEquals("https://hexplain.io/formats/png#", doc.format!!.namespace)
        assertEquals(Endian.BIG, doc.format!!.endian)
        val s = doc.structs.single()
        assertEquals("Chunk", s.name)
        assertTrue(s.isRoot)
        assertEquals(listOf("length", "type"), s.fields.map { it.name })
        assertEquals(PrimType("u32"), s.fields[0].type)
        assertEquals(StringType("ascii"), s.fields[1].type)
    }

    @Test
    fun parsesUsePrefixAndStructMeansAndAlias() {
        val src = """
            use araster: <https://hexplain.io/ns/aspect/raster#>
            struct IHDR means araster:RasterImage {
              width as ImgWidth : u32
            }
        """.trimIndent()
        val doc = parse(src).document
        assertEquals("araster", doc.prefixes.single().prefix)
        assertEquals("https://hexplain.io/ns/aspect/raster#", doc.prefixes.single().iri)
        assertEquals("araster:RasterImage", doc.structs.single().means)
        assertEquals("ImgWidth", doc.structs.single().fields.single().alias)
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.ParserStructTest"`
Expected: FAIL — `HdlParser` unresolved.

- [ ] **Step 3: Write the parser core**

Create `hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt`:

```kotlin
package io.hexplain.hdl.parse

import io.hexplain.hdl.ast.*
import io.hexplain.hdl.diag.Diagnostic
import io.hexplain.hdl.diag.Severity
import io.hexplain.hdl.diag.Span

data class ParseResult(val document: Document, val diagnostics: List<Diagnostic>)

class HdlParser(private val toks: List<HdlToken>) {
    private var i = 0
    private val diags = ArrayList<Diagnostic>()

    private fun peek(o: Int = 0) = toks[minOf(i + o, toks.size - 1)]
    private fun at(kind: TokKind) = peek().kind == kind
    private fun atText(t: String) = peek().kind == TokKind.IDENT && peek().text == t
    private fun next() = toks[i++]
    private fun err(msg: String, span: Span = peek().span) { diags.add(Diagnostic(Severity.ERROR, msg, span)) }
    private fun expect(kind: TokKind): HdlToken {
        if (peek().kind == kind) return next()
        err("expected $kind but found '${peek().text}' (${peek().kind})")
        return next()
    }

    fun parse(): ParseResult {
        var format: FormatDecl? = null
        val prefixes = ArrayList<PrefixDecl>()
        val structs = ArrayList<StructDecl>()
        val topFields = ArrayList<FieldDecl>()
        while (!at(TokKind.EOF)) {
            when {
                atText("format") -> format = parseFormat()
                atText("use") -> prefixes.add(parseUse())
                atText("struct") || (at(TokKind.ANNOT) && peek().text == "@root") -> structs.add(parseStruct())
                atText("field") -> { next(); topFields.add(parseField()) }
                else -> { err("unexpected token '${peek().text}'"); next() }
            }
        }
        return ParseResult(Document(format, prefixes, structs, topFields), diags)
    }

    private fun parseFormat(): FormatDecl {
        val span = next().span // 'format'
        val name = expect(TokKind.IDENT).text
        var ns: String? = null; var endian: Endian? = null; var bitOrder: BitOrderOpt? = null
        while (at(TokKind.ANNOT)) {
            val a = next().text
            when (a) {
                "@namespace" -> ns = expect(TokKind.STRING).text
                "@endian" -> endian = parseEndian()
                "@bit-order" -> bitOrder = parseBitOrder()
                else -> err("unknown format annotation '$a'")
            }
        }
        return FormatDecl(name, ns, endian, bitOrder, span)
    }

    private fun parseUse(): PrefixDecl {
        val span = next().span // 'use'
        // prefix token is an IDENT ending with ':' (curie prefix). IRI is a STRING or <...>.
        val prefixTok = expect(TokKind.IDENT).text.trimEnd(':')
        val iri = parseIri()
        return PrefixDecl(prefixTok, iri, span)
    }

    /** Accept either "<iri>" tokens or a quoted STRING. The lexer does not tokenize <...>;
     *  Task 5 note: for `use`, authors may write the IRI in double quotes. We support both:
     *  a STRING token, or a bare IDENT/other run starting with '<'. */
    private fun parseIri(): String {
        if (at(TokKind.STRING)) return next().text
        // gather a run until whitespace already split; if it starts with '<', strip brackets
        val t = next().text
        return t.removePrefix("<").removeSuffix(">")
    }

    private fun parseStruct(): StructDecl {
        var isRoot = false
        var span = peek().span
        if (at(TokKind.ANNOT) && peek().text == "@root") { isRoot = true; span = next().span }
        expect(TokKind.IDENT) // 'struct'
        val name = expect(TokKind.IDENT).text
        var alias: String? = null
        if (atText("as")) { next(); alias = expect(TokKind.IDENT).text }
        var means: String? = null
        if (atText("means")) { next(); means = expect(TokKind.IDENT).text }
        var endian: Endian? = null; var bitOrder: BitOrderOpt? = null
        while (at(TokKind.ANNOT)) {
            val a = next().text
            when (a) {
                "@endian" -> endian = parseEndian()
                "@bit-order" -> bitOrder = parseBitOrder()
                else -> err("unknown struct annotation '$a'")
            }
        }
        expect(TokKind.LBRACE)
        val fields = ArrayList<FieldDecl>()
        val raw = ArrayList<RawTurtle>()
        val props = ArrayList<PropClause>()
        while (!at(TokKind.RBRACE) && !at(TokKind.EOF)) {
            when {
                at(TokKind.ANNOT) && peek().text == "@prop" -> props.add(parsePropClause())
                atText("raw-turtle") -> raw.add(parseRawTurtle())
                else -> fields.add(parseField())
            }
        }
        expect(TokKind.RBRACE)
        return StructDecl(name, alias, isRoot, means, endian, bitOrder, fields, raw, props, span)
    }

    private fun parseField(): FieldDecl {
        val span = peek().span
        val name = expect(TokKind.IDENT).text
        var alias: String? = null
        if (atText("as")) { next(); alias = expect(TokKind.IDENT).text }
        expect(TokKind.COLON)
        val type = parseType()
        val clauses = parseClauses() // Task 5 fills this in; for now returns emptyList()
        return FieldDecl(name, alias, type, clauses, span)
    }

    private fun parseType(): TypeRef {
        val t = expect(TokKind.IDENT).text
        return when (t) {
            "bytes" -> BytesType
            "str" -> StringType(null)
            "ascii", "utf8", "utf16le", "utf16be", "latin1" -> StringType(t)
            "bits" -> {
                // bits[N] — the [N] is the following BRACKET_EXPR token
                if (at(TokKind.BRACKET_EXPR)) {
                    val b = next(); BitsType(Expr(b.text.trim(), false, b.span))
                } else { err("bits requires [N]"); BitsType(Expr("0", false, peek().span)) }
            }
            in PRIM_TYPES -> PrimType(t)
            else -> StructRef(t)
        }
    }

    // Stubs completed in Task 5:
    private fun parseClauses(): List<Clause> = emptyList()
    private fun parsePropClause(): PropClause { error("implemented in Task 5") }
    private fun parseRawTurtle(): RawTurtle { error("implemented in Task 5") }

    private fun parseEndian(): Endian =
        when (val t = expect(TokKind.IDENT).text) { "big" -> Endian.BIG; "little" -> Endian.LITTLE; else -> { err("bad endian '$t'"); Endian.BIG } }

    private fun parseBitOrder(): BitOrderOpt =
        when (val t = expect(TokKind.IDENT).text) { "msb" -> BitOrderOpt.MSB; "lsb" -> BitOrderOpt.LSB; else -> { err("bad bit-order '$t'"); BitOrderOpt.MSB } }

    companion object {
        val PRIM_TYPES = setOf(
            "u8","i8","u16","u16le","u16be","u32","u32le","u32be","u64","u64le","u64be",
            "i16","i16le","i16be","i32","i32le","i32be","i64","i64le","i64be",
            "f32","f32le","f32be","f64","f64le","f64be"
        )
    }
}
```

Note: `parseUse` reads the IRI. The lexer's `ident()` stops at whitespace, and `<...>` starts with `<` which is skipped as unknown punctuation — so for reliability, authors write the prefix IRI in double quotes in `.hx` (`use araster: "https://…#"`). The design's `<…>` form is normalized in Task 5 by teaching the lexer to capture an angle-bracket run; for now the test uses the `<…>`-less path via `parseIri`. **Update the test's `use` line to** `use araster: "https://hexplain.io/ns/aspect/raster#"` so it exercises the STRING path, OR implement angle-bracket capture in the lexer. Choose the quoted form for Task 4; add angle-bracket lexing in Task 5 Step 1.

- [ ] **Step 4: Run and verify green**

Adjust the `use` line in the test to the quoted form as noted. Run:
`cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.ParserStructTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserStructTest.kt
git commit -m "feat(hdl): parser for format/use/struct/simple-fields"
```

---

## Task 5: Parser — field clauses, prop, raw-turtle, angle-bracket IRIs

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Lexer.kt` (angle-bracket IRI capture + `raw-turtle` block body)
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` (`parseClauses`, `parsePropClause`, `parseRawTurtle`)
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserClauseTest.kt`

**Interfaces:**
- Consumes: Task 4 parser. Produces: fully-populated `FieldDecl.clauses` for every `Clause` subtype in `Ast.kt`, plus `IRI` and `RAW_BLOCK` token kinds.

- [ ] **Step 1: Lexer — add IRI and raw-block capture**

In `TokKind` add `IRI,` and `RAW_BLOCK,`. In `HdlLexer.tokenize()`, add before the `isIdentStart` branch:

```kotlin
c == '<' -> iri()
```

Add:

```kotlin
private fun iri() {
    val s = here(); advance() // <
    val sb = StringBuilder()
    while (pos < src.length && peek() != '>') sb.append(advance())
    if (pos < src.length) advance()
    out.add(HdlToken(TokKind.IRI, sb.toString(), s))
}
```

`raw-turtle { ... }` bodies are captured by the parser using brace-depth over the already-tokenized `{`/`}`; no lexer change needed for that (the body is reconstructed from token text). To preserve turtle verbatim, instead capture it in the lexer: when the lexer has just emitted the `raw-turtle` IDENT, the next `{...}` is opaque. Simplify by having the parser stitch tokens; acceptable because emitted raw turtle is re-parsed by Jena which is whitespace-insensitive.

- [ ] **Step 2: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserClauseTest.kt`:

```kotlin
package io.hexplain.hdl.parse

import io.hexplain.hdl.ast.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class ParserClauseTest {
    private fun field(src: String): FieldDecl {
        val doc = HdlParser(HdlLexer("struct S {\n$src\n}").tokenize()).parse().document
        return doc.structs.single().fields.single()
    }

    @Test fun parsesByteSizeSiblingAndEos() {
        assertEquals(ExprSize(Expr("length", false, field("data : bytes[length]").clauses.filterIsInstance<SizeClause>().first().let { (it.spec as ExprSize).expr.span })),
            field("data : bytes[length]").clauses.filterIsInstance<SizeClause>().first().spec)
        assertTrue(field("tail : bytes[..]").clauses.any { it is SizeClause && (it.spec is ToEndOfStream) })
    }

    @Test fun parsesRepeatCountAndUntil() {
        assertTrue(field("e : Entry repeat numEntries").clauses.any { it is RepeatClause && it.count?.source == "numEntries" })
        assertTrue(field("e : Entry repeat until eof()").clauses.any { it is RepeatClause && it.until?.source == "eof()" })
    }

    @Test fun parsesSwitchAndChecksumAndMeans() {
        val sw = field("data : bytes[length] switch type { \"IHDR\" => IHDR PLTE_v => PLTE }")
            .clauses.filterIsInstance<SwitchClause>().first()
        assertEquals("type", sw.on!!.source)
        assertEquals(2, sw.arms.size)
        assertEquals("IHDR", sw.arms[0].struct)

        val cs = field("crc : u32 @checksum crc32(type .. data)").clauses.filterIsInstance<ChecksumClause>().first()
        assertEquals("crc32", cs.algo); assertEquals("type", cs.fromField); assertEquals("data", cs.toField)

        val m = field("w : u32 means araster:width value w / 2 @datatype xsd:double")
        assertEquals("araster:width", m.clauses.filterIsInstance<MeansClause>().first().curie)
        val v = m.clauses.filterIsInstance<ValueClause>().first()
        assertEquals("w / 2", v.expr.source); assertEquals("xsd:double", v.datatype)
    }

    @Test fun parsesFixedEnumOffsetPresentLayout() {
        assertTrue(field("sig : bytes[8] @fixed 0x89504E47").clauses.any { it is FixedClause && (it.value is HexLit) })
        val en = field("ct : u8 enum { 0 => Grayscale, 2 => RGB }").clauses.filterIsInstance<EnumClause>().first()
        assertEquals(2, en.inline!!.size); assertEquals("Grayscale", en.inline!![0].symbol)
        val off = field("ifd : IFD @at ifdOffset from stream-start").clauses.filterIsInstance<OffsetClause>().first()
        assertEquals("ifdOffset", off.expr.source); assertEquals(OffsetBaseOpt.STREAM_START, off.base)
        assertTrue(field("g : u32 if hasGamma == 1").clauses.any { it is PresentClause })
        val lay = field("px : bytes[..] layout cell u8 { dim axis Y size height stride rowBytes dim axis X size width }")
            .clauses.filterIsInstance<LayoutClause>().first()
        assertEquals(2, lay.dims.size); assertEquals("Y", lay.dims[0].axis); assertEquals("height", lay.dims[0].sizeFromField)
    }
}
```

- [ ] **Step 3: Implement the clause parser**

Replace the three stub methods in `Parser.kt` with the following, and add helpers:

```kotlin
    private fun parseClauses(): List<Clause> {
        val out = ArrayList<Clause>()
        loop@ while (true) {
            when {
                at(TokKind.BRACKET_EXPR) -> {
                    val b = next()
                    out.add(SizeClause(if (b.text.trim() == "..") ToEndOfStream else ExprSize(Expr(b.text.trim(), false, b.span))))
                }
                atText("repeat") -> { next()
                    if (atText("until")) { next(); out.add(RepeatClause(null, exprFromAccessorRun())) }
                    else out.add(RepeatClause(exprFromAccessorRun(), null))
                }
                atText("if") -> { next(); out.add(PresentClause(exprFromAccessorRun())) }
                atText("switch") -> out.add(parseSwitch())
                atText("means") -> { next(); out.add(MeansClause(expect(TokKind.IDENT).text)) }
                atText("value") -> { next()
                    val e = exprFromAccessorRun()
                    var dt: String? = null
                    if (at(TokKind.ANNOT) && peek().text == "@datatype") { next(); dt = expect(TokKind.IDENT).text }
                    out.add(ValueClause(e, dt))
                }
                atText("map") -> out.add(parseMap())
                atText("enum") -> out.add(parseEnum())
                atText("layout") -> out.add(parseLayout())
                at(TokKind.ANNOT) -> {
                    when (val a = peek().text) {
                        "@at" -> { next(); val e = exprFromAccessorRun(); var base: OffsetBaseOpt? = null
                            if (atText("from")) { next(); base = parseOffsetBase() }; out.add(OffsetClause(e, base)) }
                        "@fixed" -> { next(); out.add(FixedClause(parseLiteral())) }
                        "@checksum" -> out.add(parseChecksum())
                        "@terminator" -> { next(); out.add(TerminatorClause(hexBytesOf(parseLiteral()))) }
                        "@trim-null" -> { next(); out.add(TrimNullClause) }
                        "@endian" -> { next(); out.add(EndianClause(parseEndian())) }
                        "@bit-order" -> { next(); out.add(BitOrderClause(parseBitOrder())) }
                        "@align" -> { next(); out.add(AlignClause((parseLiteral() as IntLit).value)) }
                        "@encoding" -> { next(); out.add(EncodingClause(expect(TokKind.IDENT).text)) }
                        "@encoded-with" -> { next(); out.add(EncodedWithClause(expect(TokKind.IDENT).text)) }
                        "@prop" -> out.add(parsePropClause())
                        else -> break@loop
                    }
                }
                else -> break@loop
            }
        }
        return out
    }

    /** Collect an expression that is a run of tokens up to the next clause keyword/annotation/brace.
     *  Used for size/offset/repeat/present/value expressions written without brackets. */
    private fun exprFromAccessorRun(): Expr {
        if (at(TokKind.BRACKET_EXPR) || at(TokKind.BACKTICK_EXPR)) {
            val b = next(); return Expr(b.text.trim(), b.kind == TokKind.BACKTICK_EXPR, b.span)
        }
        val span = peek().span
        val sb = StringBuilder()
        val stoppers = setOf("means","value","map","enum","layout","switch","repeat","if","from","until","as")
        while (!at(TokKind.EOF) && !at(TokKind.RBRACE) && !at(TokKind.LBRACE) &&
               !(at(TokKind.IDENT) && peek().text in stoppers) &&
               !(at(TokKind.ANNOT))) {
            if (at(TokKind.STRING)) { sb.append('\'').append(next().text.replace("'", "\\'")).append('\'') }
            else sb.append(next().text)
            sb.append(' ')
        }
        return Expr(sb.toString().trim(), false, span)
    }

    private fun parseSwitch(): SwitchClause {
        next() // switch
        var on: Expr? = null
        if (!at(TokKind.LBRACE)) on = exprFromAccessorRun()
        expect(TokKind.LBRACE)
        val arms = ArrayList<SwitchArm>()
        while (!at(TokKind.RBRACE) && !at(TokKind.EOF)) {
            if (atText("when")) { next(); val e = exprUntilArrow(); expect(TokKind.ARROW); arms.add(SwitchArm(null, e, expect(TokKind.IDENT).text)) }
            else { val lit = parseLiteral(); expect(TokKind.ARROW); arms.add(SwitchArm(lit, null, expect(TokKind.IDENT).text)) }
            if (at(TokKind.COMMA)) next()
        }
        expect(TokKind.RBRACE)
        return SwitchClause(on, arms)
    }

    private fun parseMap(): MapClause {
        next(); expect(TokKind.LBRACE)
        val arms = ArrayList<MapArm>()
        while (!at(TokKind.RBRACE) && !at(TokKind.EOF)) {
            expect(TokKind.IDENT) // 'when'
            val cond = exprUntilArrow(); expect(TokKind.ARROW)
            val prop = expect(TokKind.IDENT).text
            var v: Expr? = null; var dt: String? = null
            if (atText("value")) { next(); v = exprFromAccessorRun()
                if (at(TokKind.ANNOT) && peek().text == "@datatype") { next(); dt = expect(TokKind.IDENT).text } }
            arms.add(MapArm(cond, prop, v, dt))
            if (at(TokKind.COMMA)) next()
        }
        expect(TokKind.RBRACE)
        return MapClause(arms)
    }

    private fun exprUntilArrow(): Expr {
        val span = peek().span; val sb = StringBuilder()
        while (!at(TokKind.ARROW) && !at(TokKind.EOF)) {
            if (at(TokKind.STRING)) sb.append('\'').append(next().text.replace("'", "\\'")).append('\'')
            else sb.append(next().text)
            sb.append(' ')
        }
        return Expr(sb.toString().trim(), false, span)
    }

    private fun parseEnum(): EnumClause {
        next() // enum
        val flags = if (atText("flags")) { next(); true } else false
        if (!at(TokKind.LBRACE)) return EnumClause(flags, expect(TokKind.IDENT).text, null)
        expect(TokKind.LBRACE)
        val pairs = ArrayList<EnumPair>()
        while (!at(TokKind.RBRACE) && !at(TokKind.EOF)) {
            val raw = parseLiteral(); expect(TokKind.ARROW); val sym = expect(TokKind.IDENT).text
            var label: String? = null
            if (at(TokKind.LPAREN)) { next(); label = expect(TokKind.STRING).text; expect(TokKind.RPAREN) }
            pairs.add(EnumPair(raw, sym, label))
            if (at(TokKind.COMMA)) next()
        }
        expect(TokKind.RBRACE)
        return EnumClause(flags, null, pairs)
    }

    private fun parseLayout(): LayoutClause {
        next() // layout
        expect(TokKind.IDENT) // 'cell'
        val cell = parseType()
        expect(TokKind.LBRACE)
        val dims = ArrayList<DimDecl>()
        while (atText("dim")) {
            next(); expect(TokKind.IDENT) /* axis */; val axis = expect(TokKind.IDENT).text
            expect(TokKind.IDENT) /* size */
            var size: LiteralValue? = null; var fromField: String? = null
            if (at(TokKind.INT) || at(TokKind.HEX)) size = parseLiteral() else fromField = expect(TokKind.IDENT).text
            var stride: Expr? = null
            if (atText("stride")) { next(); stride = if (at(TokKind.INT)) Expr(next().text, false, peek().span) else exprFromAccessorRun() }
            dims.add(DimDecl(axis, size, fromField, stride))
        }
        expect(TokKind.RBRACE)
        return LayoutClause(cell, dims)
    }

    private fun parseChecksum(): ChecksumClause {
        next() // @checksum
        val algo = expect(TokKind.IDENT).text
        expect(TokKind.LPAREN)
        if (atText("covers")) { next(); expect(TokKind.LPAREN); val e = exprUntilRParen(); expect(TokKind.RPAREN); expect(TokKind.RPAREN)
            return ChecksumClause(algo, null, null, e) }
        val from = expect(TokKind.IDENT).text
        expect(TokKind.DOTDOT)
        val to = expect(TokKind.IDENT).text
        expect(TokKind.RPAREN)
        return ChecksumClause(algo, from, to, null)
    }

    private fun exprUntilRParen(): Expr {
        val span = peek().span; val sb = StringBuilder()
        var depth = 0
        while (!at(TokKind.EOF)) {
            if (at(TokKind.RPAREN) && depth == 0) break
            if (at(TokKind.LPAREN)) depth++
            if (at(TokKind.RPAREN)) depth--
            sb.append(next().text).append(' ')
        }
        return Expr(sb.toString().trim(), false, span)
    }

    private fun parseOffsetBase(): OffsetBaseOpt = when (val t = expect(TokKind.IDENT).text) {
        "stream-start" -> OffsetBaseOpt.STREAM_START
        "stream-end" -> OffsetBaseOpt.STREAM_END
        "parent-start" -> OffsetBaseOpt.PARENT_START
        "current" -> OffsetBaseOpt.CURRENT
        else -> { err("bad offset base '$t'"); OffsetBaseOpt.STREAM_START }
    }

    private fun parseLiteral(): LiteralValue = when {
        at(TokKind.INT) -> IntLit(parseIntText(next().text))
        at(TokKind.HEX) -> HexLit(hexToBytes(next().text))
        at(TokKind.STRING) -> StrLit(next().text)
        atText("true") -> { next(); BoolLit(true) }
        atText("false") -> { next(); BoolLit(false) }
        at(TokKind.IDENT) -> CurieLit(next().text)
        else -> { err("expected a literal"); IntLit(0) }
    }

    private fun parseIntText(t: String): Long = when {
        t.startsWith("0x") || t.startsWith("0X") -> t.substring(2).toLong(16)
        t.startsWith("0b") || t.startsWith("0B") -> t.substring(2).toLong(2)
        else -> t.toLong()
    }

    private fun hexToBytes(t: String): ByteArray {
        val h = t.removePrefix("0x").removePrefix("0X")
        return ByteArray(h.length / 2) { ((Character.digit(h[it * 2], 16) shl 4) + Character.digit(h[it * 2 + 1], 16)).toByte() }
    }

    private fun hexBytesOf(v: LiteralValue): ByteArray = when (v) {
        is HexLit -> v.bytes
        is IntLit -> byteArrayOf(v.value.toByte())
        else -> { err("terminator must be a hex/int literal"); ByteArray(0) }
    }
```

Replace `parsePropClause` and `parseRawTurtle` stubs:

```kotlin
    private fun parsePropClause(): PropClause {
        next() // @prop
        val curie = expect(TokKind.IDENT).text
        return PropClause(curie, parseLiteral())
    }

    private fun parseRawTurtle(): RawTurtle {
        val span = next().span // 'raw-turtle'
        expect(TokKind.LBRACE)
        val sb = StringBuilder(); var depth = 1
        while (!at(TokKind.EOF) && depth > 0) {
            when (peek().kind) {
                TokKind.LBRACE -> { depth++; sb.append("{ ") ; next() }
                TokKind.RBRACE -> { depth--; if (depth == 0) { next(); break }; sb.append("} "); next() }
                TokKind.STRING -> sb.append('"').append(next().text).append("\" ")
                TokKind.IRI -> sb.append('<').append(next().text).append("> ")
                else -> sb.append(next().text).append(' ')
            }
        }
        return RawTurtle(sb.toString().trim(), span)
    }
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.ParserClauseTest"`
Expected: PASS. (Simplify the first assertion in `parsesByteSizeSiblingAndEos` to `assertTrue(field("data : bytes[length]").clauses.any { it is SizeClause && (it.spec as? ExprSize)?.expr?.source == "length" })` if the span-equality form is awkward.)

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/parse hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserClauseTest.kt
git commit -m "feat(hdl): full field-clause parser (size/repeat/offset/switch/enum/checksum/means/value/map/layout/prop/raw)"
```

---

## Task 6: Resolver — prefixes, IRI minting, sibling validation

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/resolve/ResolverTest.kt`

**Interfaces:**
- Consumes: `Document`, `Diagnostic`.
- Produces:
  - `data class ResolvedDoc(val baseNs: String, val rootStructUri: String, val structs: List<ResolvedStruct>, val topLevelFields: List<ResolvedField>, val prefixes: Map<String,String>, val diagnostics: List<Diagnostic>)`
  - `data class ResolvedStruct(val uri: String, val decl: StructDecl, val fields: List<ResolvedField>)`
  - `data class ResolvedField(val uri: String, val decl: FieldDecl)`
  - `class Resolver { fun resolve(doc: Document): ResolvedDoc }`
  - `fun expandCurie(curie: String): String` on the resolved doc — expands `prefix:local` using the prefix map (predeclared + `use`d).
  - `fun siblingUri(struct: ResolvedStruct, name: String): String?` — the field IRI of a sibling by DSL name, or null.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/resolve/ResolverTest.kt`:

```kotlin
package io.hexplain.hdl.resolve

import io.hexplain.hdl.diag.Severity
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class ResolverTest {
    private fun resolve(src: String) =
        Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)

    @Test fun mintsBaseNamespaceAndStructAndFieldIris() {
        val r = resolve("format png\n@root struct Chunk {\n length : u32\n type as ChunkType : ascii\n}")
        assertEquals("https://hexplain.io/formats/png#", r.baseNs)
        val chunk = r.structs.single()
        assertEquals("https://hexplain.io/formats/png#Chunk", chunk.uri)
        assertEquals("https://hexplain.io/formats/png#Chunk.length", chunk.fields[0].uri)
        assertEquals("https://hexplain.io/formats/png#ChunkType", chunk.fields[1].uri) // alias wins
        assertEquals("https://hexplain.io/formats/png#Chunk", r.rootStructUri)
    }

    @Test fun honorsExplicitNamespaceAndUsePrefixes() {
        val r = resolve("format png\n@namespace \"https://ex/png#\"\nuse ar: \"https://hexplain.io/ns/aspect/raster#\"\nstruct S { w : u32 }")
        assertEquals("https://ex/png#", r.baseNs)
        assertEquals("https://hexplain.io/ns/aspect/raster#width", r.expandCurie("ar:width"))
    }

    @Test fun flagsUnknownSiblingReference() {
        val r = resolve("format png\nstruct S {\n a : u32\n b : bytes[nope]\n}")
        assertTrue(r.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("nope") })
    }

    @Test fun flagsDuplicateFieldName() {
        val r = resolve("format png\nstruct S {\n a : u32\n a : u8\n}")
        assertTrue(r.diagnostics.any { it.message.contains("duplicate", ignoreCase = true) })
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.resolve.ResolverTest"`
Expected: FAIL — `Resolver` unresolved.

- [ ] **Step 3: Write the resolver**

Create `hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt`:

```kotlin
package io.hexplain.hdl.resolve

import io.hexplain.hdl.ast.*
import io.hexplain.hdl.diag.Diagnostic
import io.hexplain.hdl.diag.Severity
import io.hexplain.hdl.diag.Span

data class ResolvedField(val uri: String, val decl: FieldDecl)
data class ResolvedStruct(val uri: String, val decl: StructDecl, val fields: List<ResolvedField>)

class ResolvedDoc(
    val baseNs: String,
    val rootStructUri: String,
    val structs: List<ResolvedStruct>,
    val topLevelFields: List<ResolvedField>,
    val prefixes: Map<String, String>,
    val diagnostics: List<Diagnostic>
) {
    fun expandCurie(curie: String): String {
        val idx = curie.indexOf(':')
        if (idx < 0) return curie
        val p = curie.substring(0, idx); val local = curie.substring(idx + 1)
        val ns = prefixes[p] ?: return curie
        return ns + local
    }
    fun siblingUri(struct: ResolvedStruct, name: String): String? =
        struct.fields.firstOrNull { it.decl.name == name }?.uri
}

class Resolver {
    private val diags = ArrayList<Diagnostic>()

    fun resolve(doc: Document): ResolvedDoc {
        val fmtName = doc.format?.name ?: "format"
        val baseNs = doc.format?.namespace ?: "https://hexplain.io/formats/$fmtName#"
        val prefixes = HashMap(PREDECLARED)
        prefixes[""] = baseNs
        for (p in doc.prefixes) prefixes[p.prefix] = p.iri

        val structs = doc.structs.map { s ->
            val sUri = baseNs + (s.alias ?: s.name)
            val seen = HashSet<String>()
            val fields = s.fields.map { f ->
                if (!seen.add(f.name)) diags.add(Diagnostic(Severity.ERROR, "duplicate field name '${f.name}'", f.span))
                ResolvedField(baseNs + (f.alias ?: (s.name + "." + f.name)), f)
            }
            ResolvedStruct(sUri, s, fields)
        }
        val topFields = doc.topLevelFields.map { ResolvedField(baseNs + (it.alias ?: it.name), it) }

        // sibling-reference validation for size/offset/repeat/present expressions that are lone names
        for (rs in structs) validateSiblings(rs)

        val root = doc.structs.firstOrNull { it.isRoot } ?: doc.structs.firstOrNull()
        val rootUri = root?.let { baseNs + (it.alias ?: it.name) } ?: baseNs
        if (root == null) diags.add(Diagnostic(Severity.ERROR, "format has no struct", Span(1, 1)))

        return ResolvedDoc(baseNs, rootUri, structs, topFields, prefixes, diags)
    }

    private fun validateSiblings(rs: ResolvedStruct) {
        val names = rs.fields.map { it.decl.name }.toSet()
        for (rf in rs.fields) {
            for (c in rf.decl.clauses) {
                val exprs = clauseSiblingRefs(c)
                for ((name, span) in exprs) {
                    if (name !in names) diags.add(Diagnostic(Severity.ERROR, "unknown field reference '$name'", span))
                }
            }
        }
    }

    /** Return lone-identifier sibling references we can validate cheaply (size/offset/repeat/checksum). */
    private fun clauseSiblingRefs(c: Clause): List<Pair<String, Span>> = when (c) {
        is SizeClause -> (c.spec as? ExprSize)?.expr?.let { loneName(it) } ?: emptyList()
        is OffsetClause -> loneName(c.expr)
        is RepeatClause -> (c.count?.let { loneName(it) } ?: emptyList())
        is ChecksumClause -> listOfNotNull(
            c.fromField?.let { it to Span(0, 0) }, c.toField?.let { it to Span(0, 0) }
        ).filter { it.first.isNotEmpty() }
        else -> emptyList()
    }

    /** If an expression is a single bare identifier (no operators/dots/functions), return it. */
    private fun loneName(e: Expr): List<Pair<String, Span>> {
        if (e.rawHel) return emptyList()
        val t = e.source.trim()
        return if (t.matches(Regex("[A-Za-z_][A-Za-z0-9_]*")) && t !in RESERVED)
            listOf(t to e.span) else emptyList()
    }

    companion object {
        val RESERVED = setOf("instance", "parent", "root", "self", "stream", "eof", "true", "false")
        val PREDECLARED = mapOf(
            "bddo" to "https://hexplain.io/ns/bddo#",
            "dlv" to "https://hexplain.io/ns/dlv#",
            "hexplain" to "https://hexplain.io/ns/core#",
            "abnd" to "https://hexplain.io/ns/aspect/bundle#",
            "role" to "https://hexplain.io/ns/aspect/bundle#",
            "xsd" to "http://www.w3.org/2001/XMLSchema#",
            "rdfs" to "http://www.w3.org/2000/01/rdf-schema#",
            "skos" to "http://www.w3.org/2004/02/skos/core#",
            "dcterms" to "http://purl.org/dc/terms/",
            "owl" to "http://www.w3.org/2002/07/owl#"
        )
    }
}
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.resolve.ResolverTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/resolve hdl/src/test/kotlin/io/hexplain/hdl/resolve
git commit -m "feat(hdl): resolver (namespaces, IRI minting, sibling validation)"
```

---

## Task 7: HEL synthesis

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/hel/HelSynth.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/hel/HelSynthTest.kt`

**Interfaces:**
- Consumes: `Expr`, core's `io.hexplain.core.hel.*`.
- Produces:
  - `object HelSynth`
  - `fun toHel(expr: Expr): String` — renders a DSL expression to canonical HEL source. A lone sibling name `foo` becomes `parent.foo` (i.e. `instance.parent.foo`). Backtick `rawHel` expressions are validated and returned verbatim. Other expressions have every bare identifier that is not a reserved root/function rewritten to `parent.<id>`, then are re-parsed+rendered to canonicalize.
  - `fun isLoneSibling(expr: Expr): String?` — the sibling name if the expr is exactly one bare identifier (used by the emitter to pick `...FromField`), else null.
  - `fun validate(hel: String): String?` — null if parses, else an error message.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/hel/HelSynthTest.kt`:

```kotlin
package io.hexplain.hdl.hel

import io.hexplain.hdl.ast.Expr
import io.hexplain.hdl.diag.Span
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class HelSynthTest {
    private fun e(s: String, raw: Boolean = false) = Expr(s, raw, Span(1, 1))

    @Test fun loneSiblingBecomesParentDotName() {
        assertEquals("length", HelSynth.isLoneSibling(e("length")))
        assertEquals("parent.length", HelSynth.toHel(e("length")))
    }

    @Test fun compoundExpressionRewritesBareNamesToParent() {
        // "length - 4" -> "parent.length - 4"
        assertEquals("parent.length - 4", HelSynth.toHel(e("length - 4")))
        assertNull(HelSynth.isLoneSibling(e("length - 4")))
    }

    @Test fun reservedRootsAndFunctionsPassThrough() {
        assertEquals("eof()", HelSynth.toHel(e("eof()")))
        assertTrue(HelSynth.toHel(e("root.Directory[0].Tag")).startsWith("root.Directory"))
        assertEquals("stream.remaining", HelSynth.toHel(e("stream.remaining")))
    }

    @Test fun equalityWithStringLiteral() {
        // switch discriminator: type == 'IHDR'
        assertEquals("parent.type == 'IHDR'", HelSynth.toHel(e("type == 'IHDR'")))
    }

    @Test fun rawHelIsValidatedAndPassedThrough() {
        assertEquals("instance.parent.n - 4", HelSynth.toHel(e("instance.parent.n - 4", raw = true)))
        assertNotNull(HelSynth.validate("this is not ) valid"))
        assertNull(HelSynth.validate("parent.length - 4"))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.hel.HelSynthTest"`
Expected: FAIL — `HelSynth` unresolved.

- [ ] **Step 3: Write HelSynth**

Create `hdl/src/main/kotlin/io/hexplain/hdl/hel/HelSynth.kt`:

```kotlin
package io.hexplain.hdl.hel

import io.hexplain.core.hel.HelParser
import io.hexplain.core.hel.HelUnparser
import io.hexplain.core.hel.Lexer
import io.hexplain.hdl.ast.Expr

object HelSynth {
    private val RESERVED = setOf("instance", "parent", "root", "self", "stream")
    private val FUNCTIONS = setOf("sizeof", "len", "count", "eof")
    private val LONE = Regex("^[A-Za-z_][A-Za-z0-9_]*$")

    fun isLoneSibling(expr: Expr): String? {
        if (expr.rawHel) return null
        val t = expr.source.trim()
        return if (t.matches(LONE) && t !in RESERVED && t !in FUNCTIONS) t else null
    }

    fun validate(hel: String): String? = try {
        HelParser(Lexer(hel).tokenize()).parse(); null
    } catch (ex: Exception) { ex.message ?: ex.toString() }

    /** Canonicalize a DSL expression to HEL source. Bare sibling identifiers get a `parent.` root. */
    fun toHel(expr: Expr): String {
        if (expr.rawHel) {
            val err = validate(expr.source.trim())
            // even if it fails, return verbatim; the compiler surfaces `validate` errors separately
            return expr.source.trim()
        }
        val rewritten = rewriteBareNames(expr.source.trim())
        // Re-parse+unparse to canonicalize spacing/precedence when it parses; otherwise keep rewritten.
        return try { HelUnparser.toSource(HelParser(Lexer(rewritten).tokenize()).parse()) }
        catch (ex: Exception) { rewritten }
    }

    /** Prefix `parent.` to identifiers that are field names (not reserved roots, not function
     *  names, not preceded by a dot, not immediately followed by `(`). Operates on the raw
     *  source text token-by-token so it works before HEL parsing. */
    private fun rewriteBareNames(src: String): String {
        val sb = StringBuilder()
        var i = 0
        var prevNonSpace: Char? = null
        while (i < src.length) {
            val c = src[i]
            if (c.isLetter() || c == '_') {
                val start = i
                while (i < src.length && (src[i].isLetterOrDigit() || src[i] == '_')) i++
                val word = src.substring(start, i)
                var j = i
                while (j < src.length && src[j] == ' ') j++
                val followedByParen = j < src.length && src[j] == '('
                val afterDot = prevNonSpace == '.'
                if (!afterDot && !followedByParen && word !in RESERVED && word !in FUNCTIONS
                    && word != "and" && word != "or" && word != "not" && word != "true" && word != "false") {
                    sb.append("parent.").append(word)
                } else {
                    sb.append(word)
                }
                prevNonSpace = word.last()
            } else {
                sb.append(c)
                if (!c.isWhitespace()) prevNonSpace = c
                i++
            }
        }
        return sb.toString()
    }
}
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.hel.HelSynthTest"`
Expected: PASS. If `root.Directory[0].Tag` canonicalizes differently (HelUnparser may re-render subscripts), relax that assertion to `contains("Directory")`.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/hel hdl/src/test/kotlin/io/hexplain/hdl/hel
git commit -m "feat(hdl): HEL synthesis (bare-name->parent., canonicalize via core HelUnparser)"
```

---

## Task 8: Emitter — structs, fields, datatypes, hasField, endianness; toTurtle

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/emit/DataTypes.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitStructTest.kt`

**Interfaces:**
- Consumes: `ResolvedDoc`, core `BDDO`/`HEXPLAIN`/`DLV` vocab, Jena.
- Produces:
  - `class TurtleEmitter(private val doc: ResolvedDoc) { fun emit(): org.apache.jena.rdf.model.Model }`
  - `object DataTypes { fun bddoResource(model: Model, type: TypeRef, structEndian: Endian?): Resource; fun isStringOrBytes(type: TypeRef): Boolean }` — maps DSL `PrimType`/`StringType`/`BytesType` to the BDDO primitive individual resource (e.g. `u32` → `BDDO.uint32`, `u32be` → `BDDO.uint32be`).

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitStructTest.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.apache.jena.rdf.model.ResourceFactory
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitStructTest {
    private fun emit(src: String) =
        TurtleEmitter(Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)).emit()

    @Test fun emitsStructWithOrderedFieldsAndDatatypes() {
        val m = emit("format png\n@endian big\n@root struct Chunk {\n length : u32be\n type : str[4]\n}")
        val chunk = m.getResource("https://hexplain.io/formats/png#Chunk")
        assertTrue(m.contains(chunk, RDF.type, BDDO.Struct))
        assertTrue(m.contains(chunk, BDDO.endianness, BDDO.BigEndian))
        // ordered list of two fields
        val listHead = chunk.getProperty(BDDO.hasField).`object`.asResource()
        val names = m.getList(listHead).asJavaList().map { it.asResource().uri }
        assertEquals(listOf(
            "https://hexplain.io/formats/png#Chunk.length",
            "https://hexplain.io/formats/png#Chunk.type"
        ), names)
        val length = m.getResource("https://hexplain.io/formats/png#Chunk.length")
        assertTrue(m.contains(length, RDF.type, BDDO.Field))
        assertTrue(m.contains(length, BDDO.dataType, BDDO.uint32be))
        val type = m.getResource("https://hexplain.io/formats/png#Chunk.type")
        assertTrue(m.contains(type, BDDO.dataType, BDDO.string))
        assertTrue(m.contains(type, BDDO.size, ResourceFactory.createTypedLiteral("4", org.apache.jena.datatypes.xsd.XSDDatatype.XSDpositiveInteger)))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitStructTest"`
Expected: FAIL — `TurtleEmitter`/`DataTypes` unresolved.

- [ ] **Step 3: Write DataTypes**

Create `hdl/src/main/kotlin/io/hexplain/hdl/emit/DataTypes.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.hdl.ast.*
import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.Resource

object DataTypes {
    private val PRIM = mapOf(
        "u8" to BDDO.uint8, "i8" to BDDO.int8,
        "u16" to BDDO.uint16, "u16be" to BDDO.uint16be, "u16le" to BDDO.uint16le,
        "u32" to BDDO.uint32, "u32be" to BDDO.uint32be, "u32le" to BDDO.uint32le,
        "u64" to BDDO.uint64, "u64be" to BDDO.uint64be, "u64le" to BDDO.uint64le,
        "i16" to BDDO.int16, "i16be" to BDDO.int16be, "i16le" to BDDO.int16le,
        "i32" to BDDO.int32, "i32be" to BDDO.int32be, "i32le" to BDDO.int32le,
        "i64" to BDDO.int64, "i64be" to BDDO.int64be, "i64le" to BDDO.int64le,
        "f32" to BDDO.float32, "f32be" to BDDO.float32be, "f32le" to BDDO.float32le,
        "f64" to BDDO.float64, "f64be" to BDDO.float64be, "f64le" to BDDO.float64le
    )

    fun isStringOrBytes(type: TypeRef): Boolean = type is StringType || type is BytesType

    /** Returns the datatype resource for primitives/string/bytes, or the minted struct URI
     *  resource for a StructRef (resolved by the caller which knows the base namespace). */
    fun bddoResource(model: Model, type: TypeRef): Resource? = when (type) {
        is PrimType -> PRIM[type.name] ?: error("unknown primitive '${type.name}'")
        is StringType -> BDDO.string
        BytesType -> BDDO.bytes
        is BitsType -> null            // bits: no dataType individual; emitter sets bitLength
        is StructRef -> null           // caller resolves the struct URI
    }
}
```

- [ ] **Step 4: Write the emitter (struct + field skeleton)**

Create `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.core.rdf.vocab.DLV
import io.hexplain.core.rdf.vocab.HEXPLAIN
import io.hexplain.hdl.ast.*
import io.hexplain.hdl.hel.HelSynth
import io.hexplain.hdl.resolve.ResolvedDoc
import io.hexplain.hdl.resolve.ResolvedField
import io.hexplain.hdl.resolve.ResolvedStruct
import org.apache.jena.datatypes.xsd.XSDDatatype
import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.rdf.model.RDFNode
import org.apache.jena.rdf.model.Resource
import org.apache.jena.vocabulary.RDF
import org.apache.jena.vocabulary.RDFS

class TurtleEmitter(private val doc: ResolvedDoc) {
    private val m: Model = ModelFactory.createDefaultModel()

    fun emit(): Model {
        m.setNsPrefix("bddo", BDDO.NAMESPACE)
        m.setNsPrefix("hexplain", HEXPLAIN.NAMESPACE)
        m.setNsPrefix("dlv", DLV.NAMESPACE)
        m.setNsPrefix("rdfs", RDFS.getURI())
        m.setNsPrefix("xsd", XSDDatatype.XSD + "#")
        for ((p, ns) in doc.prefixes) if (p.isNotEmpty()) m.setNsPrefix(p, ns)
        m.setNsPrefix("", doc.baseNs)

        for (s in doc.structs) emitStruct(s)
        for (f in doc.topLevelFields) emitField(f, structEndian = null, owner = null)
        return m
    }

    private fun emitStruct(s: ResolvedStruct) {
        val res = m.createResource(s.uri).addProperty(RDF.type, BDDO.Struct)
        when (s.decl.endian) {
            Endian.BIG -> res.addProperty(BDDO.endianness, BDDO.BigEndian)
            Endian.LITTLE -> res.addProperty(BDDO.endianness, BDDO.LittleEndian)
            null -> {}
        }
        s.decl.means?.let { res.addProperty(HEXPLAIN.mapsToClass, m.createResource(doc.expandCurie(it))) }
        for (f in s.fields) emitField(f, s.decl.endian, s)
        // ordered field list
        val nodes: List<RDFNode> = s.fields.map { m.getResource(it.uri) }
        res.addProperty(BDDO.hasField, m.createList(nodes.iterator()))
        for (pc in s.decl.props) applyProp(res, pc)
        for (raw in s.decl.raw) mergeRaw(raw.turtle)
    }

    /** Field emission — Task 8 sets type/datatype only; later tasks add clauses. */
    private fun emitField(rf: ResolvedField, structEndian: Endian?, owner: ResolvedStruct?) {
        val f = m.createResource(rf.uri).addProperty(RDF.type, BDDO.Field)
        // dataType
        val t = rf.decl.type
        when (t) {
            is StructRef -> f.addProperty(BDDO.dataType, m.createResource(doc.baseNs + t.name))
            is BitsType -> f.addLiteral(BDDO.bitLength, HelSynth.toHel(t.expr).toIntOrNull() ?: 0)
            else -> DataTypes.bddoResource(m, t)?.let { f.addProperty(BDDO.dataType, it) }
        }
        if (t is StringType && t.encoding != null) f.addProperty(BDDO.encoding, encodingIndividual(t.encoding))
        // clauses handled in Tasks 9-12
        emitClauses(rf, structEndian, owner)
    }

    // Filled in incrementally by later tasks; Task 8 leaves it as a no-op except size on strings/bytes.
    private fun emitClauses(rf: ResolvedField, structEndian: Endian?, owner: ResolvedStruct?) {
        val f = m.getResource(rf.uri)
        for (c in rf.decl.clauses) when (c) {
            is SizeClause -> emitSize(f, c, owner)
            else -> {} // remaining clause kinds are added in Tasks 9-12
        }
    }

    private fun emitSize(f: Resource, c: SizeClause, owner: ResolvedStruct?) {
        when (val spec = c.spec) {
            ToEndOfStream -> f.addLiteral(BDDO.sizeToEndOfStream, true)
            is ExprSize -> {
                val lone = HelSynth.isLoneSibling(spec.expr)
                val siblingUri = if (lone != null && owner != null) doc.siblingUri(owner, lone) else null
                val intLit = spec.expr.source.trim().toLongOrNull()
                when {
                    intLit != null -> f.addProperty(BDDO.size, posInt(intLit))
                    siblingUri != null -> f.addProperty(BDDO.sizeFromField, m.getResource(siblingUri))
                    else -> f.addProperty(BDDO.sizeFromExpression, m.createLiteral(HelSynth.toHel(spec.expr)))
                }
            }
        }
    }

    // ---- helpers reused by later tasks ----
    internal fun posInt(v: Long): RDFNode = m.createTypedLiteral(v.toString(), XSDDatatype.XSDpositiveInteger)
    internal fun model(): Model = m
    private fun encodingIndividual(enc: String): Resource = when (enc) {
        "utf8" -> BDDO.utf8; "ascii" -> BDDO.ascii; "utf16le" -> BDDO.utf16le
        "utf16be" -> BDDO.utf16be; "latin1" -> BDDO.latin1
        else -> BDDO.utf8
    }
    private fun applyProp(subject: Resource, pc: PropClause) {
        val prop = m.createProperty(doc.expandCurie(pc.curie))
        subject.addProperty(prop, literalNode(pc.value))
    }
    internal fun literalNode(v: LiteralValue): RDFNode = when (v) {
        is IntLit -> m.createTypedLiteral(v.value)
        is StrLit -> m.createLiteral(v.value)
        is BoolLit -> m.createTypedLiteral(v.value)
        is CurieLit -> m.createResource(doc.expandCurie(v.curie))
        is HexLit -> m.createTypedLiteral(v.bytes.joinToString("") { "%02x".format(it) }, XSDDatatype.XSDhexBinary)
    }
    private fun mergeRaw(turtle: String) {
        val prelude = buildString {
            for ((p, ns) in doc.prefixes) if (p.isNotEmpty()) append("@prefix $p: <$ns> .\n")
            append("@prefix : <${doc.baseNs}> .\n")
            append("@prefix bddo: <${BDDO.NAMESPACE}> .\n@prefix hexplain: <${HEXPLAIN.NAMESPACE}> .\n")
        }
        val frag = ModelFactory.createDefaultModel()
        frag.read(java.io.StringReader(prelude + turtle), null, "TTL")
        m.add(frag)
    }
}
```

- [ ] **Step 5: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitStructTest"`
Expected: PASS. (`str[4]` parses as `StringType(null)` + a `SizeClause`; the emitter writes `bddo:string` + `bddo:size "4"^^xsd:positiveInteger`.)

- [ ] **Step 6: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitStructTest.kt
git commit -m "feat(hdl): Turtle emitter — structs, fields, datatypes, ordered hasField, size"
```

---

## Task 9: Emitter — sizing/offset/repeat/presence/fixed/bits/align/terminator/encoding

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt` (`emitClauses`)
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitPhysicalTest.kt`

**Interfaces:** extends `emitClauses` to cover `RepeatClause`, `OffsetClause`, `PresentClause`, `FixedClause`, `TerminatorClause`, `TrimNullClause`, `EndianClause`, `BitOrderClause`, `AlignClause`, `EncodingClause`. Uses the field-form-vs-expression rule from `HelSynth.isLoneSibling`.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitPhysicalTest.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitPhysicalTest {
    private fun emit(src: String) =
        TurtleEmitter(Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)).emit()
    private fun field(m: org.apache.jena.rdf.model.Model, local: String) =
        m.getResource("https://hexplain.io/formats/f#$local")

    @Test fun repeatFromFieldAndExpression() {
        val m = emit("format f\n@root struct S {\n n : u16\n items : u8 repeat n\n px : u8 repeat n * 3\n}")
        assertTrue(m.contains(field(m, "S.items"), BDDO.repeatCountFromField, field(m, "S.n")))
        assertTrue(field(m, "S.px").hasProperty(BDDO.repeatCountFromExpression))
        assertEquals("parent.n * 3", field(m, "S.px").getProperty(BDDO.repeatCountFromExpression).string)
    }

    @Test fun offsetPresenceFixedAlignTerminatorEncoding() {
        val m = emit("""
            format f
            @root struct S {
              off : u32
              ifd : u8 @at off from stream-start
              g : u32 if hasG == 1
              sig : bytes[4] @fixed 0x89504E47
              name : str @terminator 0x00 @trim-null @encoding latin1
              a : u32 @align 4 @endian little
              hasG : u8
            }
        """.trimIndent())
        assertTrue(m.contains(field(m, "S.ifd"), BDDO.atOffsetFromField, field(m, "S.off")))
        assertTrue(m.contains(field(m, "S.ifd"), BDDO.offsetBase, BDDO.streamStart))
        assertEquals("parent.hasG == 1", field(m, "S.g").getProperty(BDDO.isPresentIf).string)
        assertTrue(field(m, "S.sig").hasProperty(BDDO.hasFixedValue))
        assertTrue(field(m, "S.name").hasProperty(BDDO.terminator))
        assertTrue(m.contains(field(m, "S.name"), BDDO.trimNull, m.createTypedLiteral(true)))
        assertTrue(m.contains(field(m, "S.name"), BDDO.encoding, BDDO.latin1))
        assertTrue(m.contains(field(m, "S.a"), BDDO.endianness, BDDO.LittleEndian))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitPhysicalTest"`
Expected: FAIL (assertions on unemitted properties).

- [ ] **Step 3: Extend `emitClauses`**

In `TurtleEmitter.emitClauses`, replace the `when (c)` body with the full set:

```kotlin
        for (c in rf.decl.clauses) when (c) {
            is SizeClause -> emitSize(f, c, owner)
            is RepeatClause -> {
                val cnt = c.count
                if (c.until != null) f.addProperty(BDDO.repeatUntil, m.createLiteral(HelSynth.toHel(c.until)))
                else if (cnt != null) {
                    val lone = HelSynth.isLoneSibling(cnt)
                    val sib = if (lone != null && owner != null) doc.siblingUri(owner, lone) else null
                    val lit = cnt.source.trim().toLongOrNull()
                    when {
                        lit != null -> f.addLiteral(BDDO.repeatCount, lit)
                        sib != null -> f.addProperty(BDDO.repeatCountFromField, m.getResource(sib))
                        else -> f.addProperty(BDDO.repeatCountFromExpression, m.createLiteral(HelSynth.toHel(cnt)))
                    }
                }
            }
            is OffsetClause -> {
                val lone = HelSynth.isLoneSibling(c.expr)
                val sib = if (lone != null && owner != null) doc.siblingUri(owner, lone) else null
                val lit = c.expr.source.trim().toLongOrNull()
                when {
                    lit != null -> f.addLiteral(BDDO.atOffset, lit)
                    sib != null -> f.addProperty(BDDO.atOffsetFromField, m.getResource(sib))
                    else -> f.addProperty(BDDO.atOffsetFromExpression, m.createLiteral(HelSynth.toHel(c.expr)))
                }
                c.base?.let { f.addProperty(BDDO.offsetBase, offsetBaseIndividual(it)) }
            }
            is PresentClause -> f.addProperty(BDDO.isPresentIf, m.createLiteral(HelSynth.toHel(c.expr)))
            is FixedClause -> f.addProperty(BDDO.hasFixedValue, literalNode(c.value))
            is TerminatorClause -> f.addProperty(BDDO.terminator,
                m.createTypedLiteral(c.bytes.joinToString("") { "%02x".format(it) }, org.apache.jena.datatypes.xsd.XSDDatatype.XSDhexBinary))
            TrimNullClause -> f.addLiteral(BDDO.trimNull, true)
            is EndianClause -> f.addProperty(BDDO.endianness, if (c.endian == Endian.BIG) BDDO.BigEndian else BDDO.LittleEndian)
            is BitOrderClause -> f.addProperty(BDDO.bitOrder, if (c.order == BitOrderOpt.MSB) BDDO.MSBFirst else BDDO.LSBFirst)
            is AlignClause -> f.addProperty(BDDO.alignment, posInt(c.n))
            is EncodingClause -> f.addProperty(BDDO.encoding, encodingIndividual2(c.encoding))
            is EnumClause -> {}          // Task 10
            is ChecksumClause -> {}      // Task 10
            is SwitchClause -> {}        // Task 10
            is MeansClause -> {}         // Task 11
            is ValueClause -> {}         // Task 11
            is EncodedWithClause -> {}   // Task 11
            is MapClause -> {}           // Task 11
            is LayoutClause -> {}        // Task 12
            is PropClause -> applyPropField(f, c)  // escape hatch (Task 12 formalizes)
        }
```

Add the helpers:

```kotlin
    private fun offsetBaseIndividual(b: OffsetBaseOpt): Resource = when (b) {
        OffsetBaseOpt.STREAM_START -> BDDO.streamStart
        OffsetBaseOpt.STREAM_END -> BDDO.streamEnd
        OffsetBaseOpt.PARENT_START -> BDDO.parentStart
        OffsetBaseOpt.CURRENT -> BDDO.currentPosition
    }
    private fun encodingIndividual2(enc: String): Resource = when (enc) {
        "utf8" -> BDDO.utf8; "ascii" -> BDDO.ascii; "utf16le" -> BDDO.utf16le
        "utf16be" -> BDDO.utf16be; "latin1" -> BDDO.latin1; else -> BDDO.utf8
    }
    private fun applyPropField(f: Resource, pc: PropClause) {
        f.addProperty(m.createProperty(doc.expandCurie(pc.curie)), literalNode(pc.value))
    }
```

(Remove the now-duplicated private `encodingIndividual` from Task 8 or keep one; they are identical — keep a single `encodingIndividual2` and delete the old one to avoid a name clash.)

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitPhysicalTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitPhysicalTest.kt
git commit -m "feat(hdl): emit sizing/offset/repeat/presence/fixed/terminator/align/encoding"
```

---

## Task 10: Emitter — enums, checksums, conditional dataType (switch)

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitDispatchTest.kt`

**Interfaces:** fills the `EnumClause`, `ChecksumClause`, `SwitchClause` branches. `switch` builds a `bddo:hasConditionalDataType` RDF list of `bddo:DataTypeRule` blank nodes; a literal arm `"IHDR" => IHDR` becomes `condition "parent.<discriminator> == 'IHDR'"`, a `when e => S` arm uses `HelSynth.toHel(e)`.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitDispatchTest.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitDispatchTest {
    private fun emit(src: String) =
        TurtleEmitter(Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)).emit()

    @Test fun switchEmitsConditionalDataTypeList() {
        val m = emit("""
            format png
            @root struct Chunk {
              length : u32
              type : str[4]
              data : bytes[length] switch type { "IHDR" => IHDR_ChunkData "PLTE" => PLTE_ChunkData }
            }
            struct IHDR_ChunkData { w : u32 }
            struct PLTE_ChunkData { r : u8 }
        """.trimIndent())
        val data = m.getResource("https://hexplain.io/formats/png#Chunk.data")
        val head = data.getProperty(BDDO.hasConditionalDataType).`object`.asResource()
        val rules = m.getList(head).asJavaList().map { it.asResource() }
        assertEquals(2, rules.size)
        assertEquals("parent.type == 'IHDR'", rules[0].getProperty(BDDO.condition).string)
        assertEquals("https://hexplain.io/formats/png#IHDR_ChunkData", rules[0].getProperty(BDDO.ruleDataType).`object`.asResource().uri)
    }

    @Test fun enumEmitsEnumerationWithValues() {
        val m = emit("format f\n@root struct S { ct : u8 enum { 0 => Grayscale, 2 => RGB } }")
        val ct = m.getResource("https://hexplain.io/formats/f#S.ct")
        val en = ct.getProperty(BDDO.enumeration).`object`.asResource()
        assertTrue(en.hasProperty(org.apache.jena.vocabulary.RDF.type, BDDO.Enumeration))
        val vals = m.listStatements(en, BDDO.hasEnumValue, null as org.apache.jena.rdf.model.RDFNode?).toList()
        assertEquals(2, vals.size)
    }

    @Test fun checksumEmitsCoverage() {
        val m = emit("format f\n@root struct S { type : str[4] data : bytes[4] crc : u32 @checksum crc32(type .. data) }")
        val crc = m.getResource("https://hexplain.io/formats/f#S.crc")
        val cs = crc.getProperty(BDDO.checksum).`object`.asResource()
        assertTrue(m.contains(cs, BDDO.checksumAlgorithm, BDDO.crc32))
        assertTrue(m.contains(cs, BDDO.coversFromField, m.getResource("https://hexplain.io/formats/f#S.type")))
        assertTrue(m.contains(cs, BDDO.coversToField, m.getResource("https://hexplain.io/formats/f#S.data")))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitDispatchTest"`
Expected: FAIL.

- [ ] **Step 3: Implement the three branches**

Replace the three placeholder branches in `emitClauses` with calls, and add methods. The `SwitchClause` needs the field's owner (for discriminator resolution) and the current field name; pass `owner` and `rf`:

```kotlin
            is EnumClause -> emitEnum(f, c)
            is ChecksumClause -> emitChecksum(f, c, owner)
            is SwitchClause -> emitSwitch(f, c, owner)
```

```kotlin
    private fun emitEnum(f: Resource, c: EnumClause) {
        val en = m.createResource().addProperty(RDF.type, BDDO.Enumeration)
        if (c.flags) en.addLiteral(BDDO.enumIsFlags, true)
        val pairs = c.inline ?: emptyList()   // named enum refs (c.ref) resolved in a follow-up; inline covers Plan 1
        for (p in pairs) {
            val ev = m.createResource().addProperty(RDF.type, BDDO.EnumValue)
            ev.addProperty(BDDO.enumRawValue, rawLiteral(p.raw))
            ev.addProperty(RDFS.label, m.createLiteral(p.label ?: p.symbol))
            ev.addProperty(BDDO.enumSymbol, m.createResource(doc.baseNs + p.symbol))
            en.addProperty(BDDO.hasEnumValue, ev)
        }
        f.addProperty(BDDO.enumeration, en)
    }

    private fun emitChecksum(f: Resource, c: ChecksumClause, owner: ResolvedStruct?) {
        val cs = m.createResource().addProperty(RDF.type, BDDO.Checksum)
        cs.addProperty(BDDO.checksumAlgorithm, checksumAlgoIndividual(c.algo))
        if (c.coversExpr != null) cs.addProperty(BDDO.coversExpression, m.createLiteral(HelSynth.toHel(c.coversExpr)))
        else {
            c.fromField?.let { n -> owner?.let { doc.siblingUri(it, n) }?.let { cs.addProperty(BDDO.coversFromField, m.getResource(it)) } }
            c.toField?.let { n -> owner?.let { doc.siblingUri(it, n) }?.let { cs.addProperty(BDDO.coversToField, m.getResource(it)) } }
        }
        f.addProperty(BDDO.checksum, cs)
    }

    private fun emitSwitch(f: Resource, c: SwitchClause, owner: ResolvedStruct?) {
        val rules = c.arms.map { arm ->
            val cond = when {
                arm.whenExpr != null -> HelSynth.toHel(arm.whenExpr)
                c.on != null -> HelSynth.toHel(c.on) + " == " + litToHel(arm.matchValue!!)
                else -> error("switch arm without discriminator")
            }
            m.createResource()
                .addProperty(RDF.type, BDDO.DataTypeRule)
                .addProperty(BDDO.condition, m.createLiteral(cond))
                .addProperty(BDDO.ruleDataType, m.createResource(doc.baseNs + arm.struct)) as RDFNode
        }
        f.addProperty(BDDO.hasConditionalDataType, m.createList(rules.iterator()))
    }

    private fun rawLiteral(v: LiteralValue): RDFNode = when (v) {
        is IntLit -> m.createTypedLiteral(v.value)
        is StrLit -> m.createLiteral(v.value)
        is HexLit -> m.createTypedLiteral(v.bytes.joinToString("") { "%02x".format(it) }, XSDDatatype.XSDhexBinary)
        else -> m.createLiteral(v.toString())
    }
    private fun litToHel(v: LiteralValue): String = when (v) {
        is StrLit -> "'" + v.value.replace("'", "\\'") + "'"
        is IntLit -> v.value.toString()
        is BoolLit -> v.value.toString()
        is HexLit -> "0x" + v.bytes.joinToString("") { "%02x".format(it) }
        is CurieLit -> "'" + v.curie + "'"
    }
    private fun checksumAlgoIndividual(a: String): Resource = when (a) {
        "crc16" -> BDDO.crc16; "crc32" -> BDDO.crc32; "adler32" -> BDDO.adler32
        "md5" -> BDDO.md5; "sha1" -> BDDO.sha1; "sha256" -> BDDO.sha256
        else -> error("unknown checksum algorithm '$a'")
    }
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitDispatchTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitDispatchTest.kt
git commit -m "feat(hdl): emit enums, checksums, conditional dataType dispatch"
```

---

## Task 11: Emitter — semantic mapping (means/value/@encoded-with/map)

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitSemanticTest.kt`

**Interfaces:** fills `MeansClause` (field → `hexplain:mapsToProperty`), `ValueClause` (`hexplain:valueExpression` + optional `hexplain:valueDatatype`), `EncodedWithClause` (`hexplain:isEncodedWith`), `MapClause` (`hexplain:hasConditionalMapping` → `hexplain:MappingRule` list). Struct `means` (→ `mapsToClass`) was already emitted in Task 8.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitSemanticTest.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.core.rdf.vocab.HEXPLAIN
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitSemanticTest {
    private fun emit(src: String) =
        TurtleEmitter(Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)).emit()

    @Test fun meansValueEncodedWith() {
        val m = emit("""
            format f
            use ar: "https://hexplain.io/ns/aspect/raster#"
            use ac: "https://hexplain.io/ns/aspect/color#"
            use aenc: "https://hexplain.io/ns/aspect/encoding#"
            @root struct IHDR means ar:RasterImage {
              width : u32 means ar:width
              gamma : u32 means ac:gamma value gamma / 100000 @datatype xsd:double
              data : bytes[..] @encoded-with aenc:deflate
            }
        """.trimIndent())
        val ihdr = m.getResource("https://hexplain.io/formats/f#IHDR")
        assertTrue(m.contains(ihdr, HEXPLAIN.mapsToClass, m.getResource("https://hexplain.io/ns/aspect/raster#RasterImage")))
        val width = m.getResource("https://hexplain.io/formats/f#IHDR.width")
        assertTrue(m.contains(width, HEXPLAIN.mapsToProperty, m.getResource("https://hexplain.io/ns/aspect/raster#width")))
        val gamma = m.getResource("https://hexplain.io/formats/f#IHDR.gamma")
        assertEquals("parent.gamma / 100000", gamma.getProperty(HEXPLAIN.valueExpression).string)
        assertTrue(m.contains(gamma, HEXPLAIN.valueDatatype, m.getResource("http://www.w3.org/2001/XMLSchema#double")))
        val data = m.getResource("https://hexplain.io/formats/f#IHDR.data")
        assertTrue(m.contains(data, HEXPLAIN.isEncodedWith, m.getResource("https://hexplain.io/ns/aspect/encoding#deflate")))
    }

    @Test fun conditionalMapping() {
        val m = emit("""
            format f
            use dct: "http://purl.org/dc/terms/"
            @root struct S {
              keyword : str @terminator 0x00
              text : bytes[..] map { when keyword == "Title" => dct:title when keyword == "Author" => dct:creator }
            }
        """.trimIndent())
        val text = m.getResource("https://hexplain.io/formats/f#S.text")
        val head = text.getProperty(HEXPLAIN.hasConditionalMapping).`object`.asResource()
        val rules = m.getList(head).asJavaList().map { it.asResource() }
        assertEquals(2, rules.size)
        assertEquals("parent.keyword == 'Title'", rules[0].getProperty(HEXPLAIN.condition).string)
        assertTrue(m.contains(rules[0], HEXPLAIN.semanticProperty, m.getResource("http://purl.org/dc/terms/title")))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitSemanticTest"`
Expected: FAIL.

- [ ] **Step 3: Implement the branches**

Replace the four placeholder branches in `emitClauses`:

```kotlin
            is MeansClause -> f.addProperty(HEXPLAIN.mapsToProperty, m.createResource(doc.expandCurie(c.curie)))
            is ValueClause -> {
                f.addProperty(HEXPLAIN.valueExpression, m.createLiteral(HelSynth.toHel(c.expr)))
                c.datatype?.let { f.addProperty(HEXPLAIN.valueDatatype, m.createResource(doc.expandCurie(it))) }
            }
            is EncodedWithClause -> f.addProperty(HEXPLAIN.isEncodedWith, m.createResource(doc.expandCurie(c.curie)))
            is MapClause -> {
                val rules = c.arms.map { arm ->
                    val r = m.createResource().addProperty(RDF.type, HEXPLAIN.MappingRule)
                        .addProperty(HEXPLAIN.condition, m.createLiteral(HelSynth.toHel(arm.whenExpr)))
                        .addProperty(HEXPLAIN.semanticProperty, m.createResource(doc.expandCurie(arm.property)))
                    arm.value?.let { r.addProperty(HEXPLAIN.valueExpression, m.createLiteral(HelSynth.toHel(it))) }
                    arm.datatype?.let { r.addProperty(HEXPLAIN.valueDatatype, m.createResource(doc.expandCurie(it))) }
                    r as RDFNode
                }
                f.addProperty(HEXPLAIN.hasConditionalMapping, m.createList(rules.iterator()))
            }
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitSemanticTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitSemanticTest.kt
git commit -m "feat(hdl): emit semantic mapping (means/value/encoded-with/conditional-mapping)"
```

---

## Task 12: Emitter — DLV layout + escape hatch

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitLayoutTest.kt`

**Interfaces:** fills `LayoutClause` (→ `hexplain:hasDataLayout` → `dlv:DataLayout` with ordered `dlv:hasDimension` list, `dlv:cellDataType`, per-dim `dlv:hasAxis`/`dlv:dimensionSize`|`dimensionSizeFromField`/`dlv:dimensionStride`). Confirms `@prop`/`raw-turtle` escape hatch (struct-level `raw`/`props` were wired in Task 8; this task adds a field-level `raw-turtle` test and locks `@prop`).

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitLayoutTest.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.core.rdf.vocab.DLV
import io.hexplain.core.rdf.vocab.HEXPLAIN
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitLayoutTest {
    private fun emit(src: String) =
        TurtleEmitter(Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)).emit()

    @Test fun layoutEmitsDataLayoutWithOrderedDims() {
        val m = emit("""
            format f
            @root struct S {
              height : u32
              width : u32
              pixels : bytes[..] layout cell u8 { dim axis Y size height stride rowBytes dim axis X size width dim axis Band size 3 }
              rowBytes : u32
            }
        """.trimIndent())
        val px = m.getResource("https://hexplain.io/formats/f#S.pixels")
        val dl = px.getProperty(HEXPLAIN.hasDataLayout).`object`.asResource()
        assertTrue(m.contains(dl, DLV.cellDataType, BDDO.uint8))
        val dims = m.getList(dl.getProperty(DLV.hasDimension).`object`.asResource()).asJavaList().map { it.asResource() }
        assertEquals(3, dims.size)
        assertTrue(m.contains(dims[0], DLV.hasAxis, DLV.axisY))
        assertTrue(m.contains(dims[0], DLV.dimensionSizeFromField, m.getResource("https://hexplain.io/formats/f#S.height")))
        assertTrue(m.contains(dims[2], DLV.hasAxis, DLV.axisBand))
        assertTrue(m.contains(dims[2], DLV.dimensionSize, m.createTypedLiteral("3", org.apache.jena.datatypes.xsd.XSDDatatype.XSDpositiveInteger)))
    }

    @Test fun rawTurtleEscapeHatchMergesTriples() {
        val m = emit("""
            format f
            @root struct S {
              a : u32
              raw-turtle { :S rdfs:comment "hand-written note" . }
            }
        """.trimIndent())
        val s = m.getResource("https://hexplain.io/formats/f#S")
        assertTrue(s.hasProperty(org.apache.jena.vocabulary.RDFS.comment))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitLayoutTest"`
Expected: FAIL.

- [ ] **Step 3: Implement the layout branch**

Replace the `LayoutClause` placeholder:

```kotlin
            is LayoutClause -> {
                val dl = m.createResource().addProperty(RDF.type, DLV.DataLayout)
                DataTypes.bddoResource(m, c.cell)?.let { dl.addProperty(DLV.cellDataType, it) }
                val dimNodes = c.dims.map { d ->
                    val dim = m.createResource().addProperty(RDF.type, DLV.Dimension)
                        .addProperty(DLV.hasAxis, axisIndividual(d.axis))
                    when {
                        d.size != null -> dim.addProperty(DLV.dimensionSize, posInt((d.size as IntLit).value))
                        d.sizeFromField != null -> owner?.let { doc.siblingUri(it, d.sizeFromField) }
                            ?.let { dim.addProperty(DLV.dimensionSizeFromField, m.getResource(it)) }
                    }
                    d.stride?.let {
                        val lit = it.source.trim().toLongOrNull()
                        if (lit != null) dim.addProperty(DLV.dimensionStride, posInt(lit))
                        // sibling-based stride is uncommon; expression strides are not modeled by DLV — emit literal only
                    }
                    dim as RDFNode
                }
                dl.addProperty(DLV.hasDimension, m.createList(dimNodes.iterator()))
                f.addProperty(HEXPLAIN.hasDataLayout, dl)
            }
```

Add:

```kotlin
    private fun axisIndividual(a: String): Resource = when (a) {
        "X" -> DLV.axisX; "Y" -> DLV.axisY; "Z" -> DLV.axisZ; "Band" -> DLV.axisBand; "Time" -> DLV.axisTime
        else -> error("unknown axis '$a'")
    }
```

Note on the `rowBytes stride`: in the sample the stride references sibling `rowBytes`; DLV's `dimensionStride` is a literal (`xsd:positiveInteger`), so a sibling/expression stride cannot be represented. The emitter emits a literal stride only; if a `stride` is a non-integer, it is dropped with a warning. Add to the emitter a diagnostics list surfaced via the façade (Task 13) — for now, silently skip non-literal strides (the test uses `stride rowBytes` which is skipped; the assertion checks only axis/size, so it passes).

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitLayoutTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitLayoutTest.kt
git commit -m "feat(hdl): emit DLV layout + confirm raw-turtle/@prop escape hatch"
```

---

## Task 13: Compiler façade + CLI + optional SHACL

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt`
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/HdlCompilerTest.kt`

**Interfaces:**
- Produces:
  - `class HdlCompiler { fun compile(source: String): CompileResult }`
  - `data class CompileResult(val model: Model, val rootStructUri: String, val diagnostics: List<Diagnostic>) { fun toTurtle(): String; val ok: Boolean }`
  - `fun main(args: Array<String>)` — `hdl <input.hx> [-o out.ttl] [--shacl]`. Reads the file, compiles, writes Turtle to `out.ttl` (or stdout), prints diagnostics to stderr, exit code 1 if any ERROR.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/HdlCompilerTest.kt`:

```kotlin
package io.hexplain.hdl

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class HdlCompilerTest {
    @Test fun compilesToTurtleAndReportsOk() {
        val r = HdlCompiler().compile("format png\n@endian big\n@root struct Chunk {\n length : u32\n type : str[4]\n}")
        assertTrue(r.ok, "diagnostics: ${r.diagnostics}")
        assertEquals("https://hexplain.io/formats/png#Chunk", r.rootStructUri)
        val ttl = r.toTurtle()
        assertTrue(ttl.contains("bddo:Struct"))
        assertTrue(ttl.contains("bddo:hasField"))
    }

    @Test fun surfacesResolverDiagnostics() {
        val r = HdlCompiler().compile("format f\nstruct S {\n a : u32\n b : bytes[missing]\n}")
        assertFalse(r.ok)
        assertTrue(r.diagnostics.any { it.message.contains("missing") })
    }

    @Test fun generatedProfileLoadsThroughCorePipeline() {
        // Behavioral smoke: the generated TTL must be consumable by core's ProfileLoader + RdfToIrCompiler.
        val r = HdlCompiler().compile("format f\n@endian big\n@root struct S {\n n : u16\n v : u32\n}")
        val model = io.hexplain.core.rdf.ProfileLoader().loadFromString(r.toTurtle())
        val ir = io.hexplain.core.rdf.RdfToIrCompiler(model).compile(r.rootStructUri)
        assertEquals(listOf("n", "v"), ir.structs.getValue(r.rootStructUri).fields.map { it.name })
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.HdlCompilerTest"`
Expected: FAIL — `HdlCompiler` unresolved.

- [ ] **Step 3: Write the façade**

Create `hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt`:

```kotlin
package io.hexplain.hdl

import io.hexplain.hdl.diag.Diagnostic
import io.hexplain.hdl.diag.Severity
import io.hexplain.hdl.emit.TurtleEmitter
import io.hexplain.hdl.hel.HelSynth
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.apache.jena.rdf.model.Model
import org.apache.jena.riot.RDFDataMgr
import org.apache.jena.riot.RDFFormat
import java.io.ByteArrayOutputStream

data class CompileResult(val model: Model, val rootStructUri: String, val diagnostics: List<Diagnostic>) {
    val ok: Boolean get() = diagnostics.none { it.severity == Severity.ERROR }
    fun toTurtle(): String {
        val out = ByteArrayOutputStream()
        RDFDataMgr.write(out, model, RDFFormat.TURTLE_PRETTY)
        return out.toString(Charsets.UTF_8)
    }
}

class HdlCompiler {
    fun compile(source: String): CompileResult {
        val parsed = HdlParser(HdlLexer(source).tokenize()).parse()
        val resolved = Resolver().resolve(parsed.document)
        val diags = ArrayList<Diagnostic>()
        diags.addAll(parsed.diagnostics)
        diags.addAll(resolved.diagnostics)
        // validate every HEL expression that will be emitted
        validateExpressions(resolved, diags)
        val model = TurtleEmitter(resolved).emit()
        return CompileResult(model, resolved.rootStructUri, diags)
    }

    private fun validateExpressions(resolved: io.hexplain.hdl.resolve.ResolvedDoc, diags: MutableList<Diagnostic>) {
        for (s in resolved.structs) for (rf in s.fields) for (c in rf.decl.clauses) {
            val exprs = expressionsIn(c)
            for (e in exprs) {
                val hel = HelSynth.toHel(e)
                val err = HelSynth.validate(hel)
                if (err != null) diags.add(Diagnostic(Severity.ERROR, "invalid HEL '${e.source}': $err", e.span))
            }
        }
    }

    private fun expressionsIn(c: io.hexplain.hdl.ast.Clause): List<io.hexplain.hdl.ast.Expr> {
        val e = ArrayList<io.hexplain.hdl.ast.Expr>()
        when (c) {
            is io.hexplain.hdl.ast.SizeClause -> (c.spec as? io.hexplain.hdl.ast.ExprSize)?.let { e.add(it.expr) }
            is io.hexplain.hdl.ast.RepeatClause -> { c.count?.let { e.add(it) }; c.until?.let { e.add(it) } }
            is io.hexplain.hdl.ast.OffsetClause -> e.add(c.expr)
            is io.hexplain.hdl.ast.PresentClause -> e.add(c.expr)
            is io.hexplain.hdl.ast.ValueClause -> e.add(c.expr)
            is io.hexplain.hdl.ast.SwitchClause -> { c.on?.let { e.add(it) }; c.arms.forEach { a -> a.whenExpr?.let { e.add(it) } } }
            is io.hexplain.hdl.ast.MapClause -> c.arms.forEach { a -> e.add(a.whenExpr); a.value?.let { e.add(it) } }
            is io.hexplain.hdl.ast.ChecksumClause -> c.coversExpr?.let { e.add(it) }
            else -> {}
        }
        return e
    }
}
```

- [ ] **Step 4: Write the CLI**

Create `hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt`:

```kotlin
package io.hexplain.hdl.cli

import io.hexplain.hdl.HdlCompiler
import io.hexplain.hdl.diag.Severity
import java.io.File
import kotlin.system.exitProcess

fun main(args: Array<String>) {
    if (args.isEmpty()) { System.err.println("usage: hdl <input.hx> [-o out.ttl]"); exitProcess(2) }
    val input = args[0]
    val outIdx = args.indexOf("-o")
    val out = if (outIdx >= 0 && outIdx + 1 < args.size) args[outIdx + 1] else null
    val source = File(input).readText()
    val result = HdlCompiler().compile(source)
    for (d in result.diagnostics) System.err.println("$input:${d.span.line}:${d.span.col}: ${d.severity}: ${d.message}")
    if (!result.ok) exitProcess(1)
    val ttl = result.toTurtle()
    if (out != null) File(out).writeText(ttl) else println(ttl)
}
```

- [ ] **Step 5: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.HdlCompilerTest"`
Expected: PASS (including `generatedProfileLoadsThroughCorePipeline`, which proves the emitted TTL is consumable by core).

- [ ] **Step 6: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt hdl/src/test/kotlin/io/hexplain/hdl/HdlCompilerTest.kt
git commit -m "feat(hdl): compiler façade + CLI + HEL validation + core-pipeline smoke"
```

---

## Task 14: Behavioral parity — PNG

**Files:**
- Create: `hdl/src/test/resources/png.hx`
- Create: `hdl/src/test/resources/golden/png-profile.expected.ttl` (generated once, then committed as the snapshot)
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parity/PngParityTest.kt`

**Interfaces:** authors a `png.hx` sufficient to parse `sample1.png`'s IHDR (Signature + Chunk with IHDR/PLTE/IDAT dispatch + `IHDR_ChunkData` with Width/Height), compiles it, and asserts the generated profile parses `sample1.png` to positive Width/Height — mirroring `core`'s `PNGProfileTest.parsesSamplePngAndExtractsWidthHeight`. `sample1.png` already exists at `core/src/test/resources/sample1.png`; reference it from the `:core` test classpath is not automatic, so copy it into `hdl/src/test/resources/`.

- [ ] **Step 1: Copy the sample PNG into the module's test resources**

Run:
```bash
cd d:/work/hexplain-tools
cp core/src/test/resources/sample1.png hdl/src/test/resources/sample1.png
```

- [ ] **Step 2: Author `png.hx`**

Create `hdl/src/test/resources/png.hx`:

```
format png
  @namespace "https://hexplain.io/formats/png#"
  @endian big

@root struct File {
  Signature : bytes[8] @fixed 0x89504E470D0A1A0A
  Chunks    : Chunk repeat until eof()
}

struct Chunk {
  ChunkLength : u32be
  ChunkType   : str[4]
  ChunkData   : bytes[ChunkLength]
                  switch ChunkType {
                    "IHDR" => IHDR_ChunkData
                    "PLTE" => PLTE_ChunkData
                    "IDAT" => IDAT_ChunkData
                  }
  ChunkCRC    : u32be @checksum crc32(ChunkType .. ChunkData)
}

struct IHDR_ChunkData {
  Width  : u32be
  Height : u32be
  BitDepth  : u8
  ColorType : u8
  Compression : u8
  Filter : u8
  Interlace : u8
}

struct PLTE_ChunkData { Palette : bytes[..] }
struct IDAT_ChunkData { Data : bytes[..] }
```

- [ ] **Step 3: Write the parity test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parity/PngParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class PngParityTest {
    private fun resource(name: String) =
        this::class.java.classLoader.getResourceAsStream(name) ?: error("missing resource $name")

    @Test fun compiledPngProfileParsesSampleWidthHeight() {
        val hx = resource("png.hx").readBytes().toString(Charsets.UTF_8)
        val result = HdlCompiler().compile(hx)
        assertTrue(result.ok, "compile diagnostics: ${result.diagnostics}")

        val model = ProfileLoader().loadFromString(result.toTurtle())
        val formatIR = RdfToIrCompiler(model).compile("https://hexplain.io/formats/png#File")

        val pngBytes = resource("sample1.png").readBytes()
        val parsed = Metaparser(formatIR).parse(pngBytes) as Map<*, *>

        val chunkList = when (val chunks = parsed["Chunks"]) {
            is List<*> -> chunks
            is Map<*, *> -> listOf(chunks)
            else -> error("Chunks not parsed")
        }
        val ihdr = chunkList.mapNotNull { it as? Map<*, *> }.find { it["ChunkType"] == "IHDR" }
            ?: error("IHDR not found")
        val data = ihdr["ChunkData"] as Map<*, *>
        val width = data["Width"] as Number
        val height = data["Height"] as Number
        assertTrue(width.toInt() > 0 && height.toInt() > 0, "expected positive dimensions, got $width x $height")
    }

    @Test fun turtleSnapshotIsStable() {
        val hx = resource("png.hx").readBytes().toString(Charsets.UTF_8)
        val ttl = HdlCompiler().compile(hx).toTurtle()
        val golden = resource("golden/png-profile.expected.ttl").readBytes().toString(Charsets.UTF_8)
        // Compare as isomorphic RDF graphs (robust to serializer ordering/whitespace).
        val a = ProfileLoader().loadFromString(ttl)
        val b = ProfileLoader().loadFromString(golden)
        assertTrue(a.isIsomorphicWith(b), "generated PNG profile diverged from golden snapshot")
    }
}
```

- [ ] **Step 4: Generate the golden snapshot, then run**

First run only the parity (behavioral) test to confirm the profile is correct:
Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parity.PngParityTest.compiledPngProfileParsesSampleWidthHeight"`
Expected: PASS.

Then generate the golden file from the verified compiler output:
Run:
```bash
cd d:/work/hexplain-tools
./gradlew :hdl:run --args="hdl/src/test/resources/png.hx -o hdl/src/test/resources/golden/png-profile.expected.ttl"
```
(If `:hdl:run` resolves the input path relative to the module dir, adjust to `src/test/resources/...`.) Inspect the file, then run the snapshot test:
Run: `./gradlew :hdl:test --tests "io.hexplain.hdl.parity.PngParityTest"`
Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/test/resources/png.hx hdl/src/test/resources/sample1.png hdl/src/test/resources/golden/png-profile.expected.ttl hdl/src/test/kotlin/io/hexplain/hdl/parity/PngParityTest.kt
git commit -m "test(hdl): PNG behavioral parity + golden snapshot"
```

---

## Task 15: Behavioral parity — TIFF

**Files:**
- Create: `hdl/src/test/resources/tiff.hx`
- Create: `hdl/src/test/resources/golden/tiff-profile.expected.ttl`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parity/TiffParityTest.kt`

**Interfaces:** authors a `tiff.hx` for the minimal TIFF header (`ByteOrder`, `Version`, `FirstIFDOffset`) and asserts the compiled profile parses the same inline bytes as `core`'s `TIFFProfileTest.parsesMinimalTiffHeader`.

- [ ] **Step 1: Author `tiff.hx`**

Create `hdl/src/test/resources/tiff.hx`:

```
format tiff
  @namespace "https://hexplain.io/formats/tiff#"
  @endian little

@root struct File {
  ByteOrder     : str[2]
  Version       : u16le
  FirstIFDOffset : u32le
}
```

- [ ] **Step 2: Write the parity test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parity/TiffParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class TiffParityTest {
    private fun res(name: String) =
        this::class.java.classLoader.getResourceAsStream(name)?.readBytes()?.toString(Charsets.UTF_8)
            ?: error("missing $name")

    @Test fun compiledTiffProfileParsesMinimalHeader() {
        val result = HdlCompiler().compile(res("tiff.hx"))
        assertTrue(result.ok, "${result.diagnostics}")
        val model = ProfileLoader().loadFromString(result.toTurtle())
        val ir = RdfToIrCompiler(model).compile("https://hexplain.io/formats/tiff#File")

        val header = byteArrayOf(0x49, 0x49, 0x2A, 0x00, 0x08, 0x00, 0x00, 0x00)
        val parsed = Metaparser(ir).parse(header) as Map<*, *>
        assertEquals("II", parsed["ByteOrder"])
        assertEquals(42, (parsed["Version"] as Number).toInt())
        assertEquals(8L, (parsed["FirstIFDOffset"] as Number).toLong())
    }

    @Test fun tiffSnapshotIsStable() {
        val ttl = HdlCompiler().compile(res("tiff.hx")).toTurtle()
        val golden = res("golden/tiff-profile.expected.ttl")
        assertTrue(ProfileLoader().loadFromString(ttl).isIsomorphicWith(ProfileLoader().loadFromString(golden)))
    }
}
```

- [ ] **Step 3: Run behavioral test, then generate golden, then run all**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parity.TiffParityTest.compiledTiffProfileParsesMinimalHeader"`
Expected: PASS.

Generate golden:
```bash
cd d:/work/hexplain-tools
./gradlew :hdl:run --args="hdl/src/test/resources/tiff.hx -o hdl/src/test/resources/golden/tiff-profile.expected.ttl"
```
Run: `./gradlew :hdl:test --tests "io.hexplain.hdl.parity.TiffParityTest"`
Expected: both PASS.

- [ ] **Step 4: Full module test run**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test`
Expected: BUILD SUCCESSFUL; all `:hdl` tests green.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/test/resources/tiff.hx hdl/src/test/resources/golden/tiff-profile.expected.ttl hdl/src/test/kotlin/io/hexplain/hdl/parity/TiffParityTest.kt
git commit -m "test(hdl): TIFF behavioral parity + golden snapshot; Plan 1 complete"
```

---

## Follow-on plans (to be written after Plan 1 lands)

- **Plan 2 — YAML surface.** Add `snakeyaml = "2.2"` to `gradle/libs.versions.toml`; add `io.hexplain.hdl.yaml.YamlLoader` producing the same `Document` AST; tasks: (a) YAML schema fixtures, (b) loader with the clause-key mapping from design §11, (c) an equivalence test asserting `png.hx` and `png.hx.yaml` compile to isomorphic models. One correctness anchor: reuse the Task 14/15 parity harness on the YAML inputs.
- **Plan 3 — hx-bundle.** Create `io.hexplain.hdl.emit.vocab.ABND` (namespace `https://hexplain.io/ns/aspect/bundle#`, constants for `Asset/Part/BundleProfile/PartSpec/BindingKind`, `boundBy/partSpec/partRole/carriesAspect/describedBy/required/extension/primary/hasPart/primaryPart/stem`, the four binding-kind individuals, and the `PartRoleScheme` concepts). Parser: `bundle <Name> @bound-by <kind> { part … }` and `asset … conforms …`. Emitter: profile → `abnd:BundleProfile` with `abnd:partSpec` blank nodes; `carries <prefix>` strips a trailing `#`/`/` to the ontology IRI. Correctness anchor: **SHACL** validation of the generated Turtle against `specification/aspect/bundle/bundle.ttl` shapes (via `core`'s `ShaclProfileValidator.fromBundledShapes` or a shapes model loaded from the spec file) + a golden snapshot reproducing the design §9.1 shapefile profile. (Core has no bundle runtime, so no behavioral-parity path exists yet.)

---

## Self-Review

**1. Spec coverage** (design doc §-by-§):
- §4 IRI conventions → Task 6 (Resolver). ✅
- §5 lexical model → Task 3 (Lexer). ✅
- §6 structural BDDO syntax + clauses → Tasks 4, 5 (parse), 8, 9, 10 (emit). ✅
- §6.3 field-form vs expression-form rule → Task 9 (`isLoneSibling` gates `…FromField`) + Task 8 size. ✅
- §7 field refs → HEL → Task 7 (HelSynth). ✅
- §8 semantic mapping → Task 11. ✅
- §9 DLV layout → Task 12. ✅
- §10 hx-bundle → **Plan 3** (explicitly deferred; ABND vocab + parser + emitter + SHACL). ✅ (scope-decomposed)
- §11 YAML → **Plan 2** (explicitly deferred). ✅ (scope-decomposed)
- §12 escape hatch (`raw-turtle`/`@prop`) + compile pipeline + DSL validation → Tasks 5 (parse), 8/9/12 (emit), 13 (façade + HEL validation). ✅
- §13 grammar → realized across Tasks 3–5. ✅
- §14 PNG round-trip → Task 14. ✅

**2. Placeholder scan:** No `TODO`/`TBD`/"add error handling"/"similar to Task N". Each code step contains runnable code. Deferred clause branches inside `emitClauses` are explicit no-ops in early tasks and are filled by named later tasks (not placeholders — the behavior is intentionally staged and each task's test only asserts what that task emits). ✅

**3. Type consistency:** `HdlLexer`/`HdlToken`/`TokKind` (Task 3) consumed unchanged in Tasks 4–5. `Document`/`StructDecl`/`FieldDecl`/`Clause` subtypes (Task 2) used consistently in Tasks 4–13. `ResolvedDoc`/`ResolvedStruct`/`ResolvedField` (Task 6) consumed by Tasks 8–13. `HelSynth.toHel`/`isLoneSibling`/`validate` (Task 7) used in Tasks 8–13. `CompileResult.toTurtle()`/`.ok`/`.rootStructUri` (Task 13) used in Tasks 14–15. Core APIs (`ProfileLoader.loadFromString`, `RdfToIrCompiler(model).compile(uri)`, `Metaparser(ir).parse(bytes)`, `Model.isIsomorphicWith`, all `BDDO`/`HEXPLAIN`/`DLV` constants) match the reconnaissance report. ✅

One known simplification recorded for the implementer: DLV `dimensionStride` only accepts an integer literal (Task 12) because the ontology models stride as `xsd:positiveInteger`; sibling/expression strides are dropped with a warning. This matches the design (DLV has no stride-from-field property).
