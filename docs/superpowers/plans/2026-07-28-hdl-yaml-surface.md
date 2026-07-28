# HDL YAML Surface — Implementation Plan (Plan 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a YAML front-end to the HDL compiler — a `YamlLoader` that parses `.hx.yaml` into the *same* `Document` AST the text parser produces, so a YAML-authored format description flows through the existing resolver → HEL-synth → Turtle-emitter unchanged.

**Architecture:** New `io.hexplain.hdl.yaml.YamlLoader` (snakeyaml) → `io.hexplain.hdl.parse.ParseResult` (the existing `{document, diagnostics}` type). `HdlCompiler` is refactored to expose `compileYaml(yaml)` alongside `compile(source)`, both funnelling through one private `compile(document, parseDiagnostics)` core. Correctness is anchored on **surface equivalence** (a `.hx` and its mirror `.hx.yaml` compile to isomorphic RDF models) plus **behavioral parity** (the YAML-generated PNG/TIFF profiles parse real bytes identically), reusing Plan 1's parity harness.

**Tech Stack:** Kotlin 2.2.10 / JVM / Gradle, Apache Jena 5.5.0, JUnit 5.10.2, **snakeyaml 2.2** (new). Builds on the merged Plan 1 `hdl` module in `d:/work/hexplain-tools`.

## Global Constraints

- Versions via the catalog `gradle/libs.versions.toml`: Kotlin `2.2.10`, JUnit `5.10.2`, Jena `5.5.0`, **snakeyaml `2.2`** (add). Never hard-code versions in the module build.
- The `YamlLoader` MUST produce the exact same `io.hexplain.hdl.ast.Document` type the text parser produces (`io.hexplain.hdl.ast.*` — do not add or fork AST types). It returns `io.hexplain.hdl.parse.ParseResult(document, diagnostics)`.
- Errors are returned as `io.hexplain.hdl.diag.Diagnostic` values, never thrown to the caller of `YamlLoader.load` or `HdlCompiler.compileYaml`. A malformed YAML document (snakeyaml parse exception) becomes one ERROR diagnostic.
- **Backtick = rawHel, mirrored from the text surface:** a YAML expression scalar wrapped in backticks (e.g. `size: "\`parent.ChunkLength\`"`) yields an `Expr(source=inner, rawHel=true)`; any other expression scalar is `rawHel=false`. This keeps the escape hatch identical across surfaces.
- **`size: ".."` means to-end-of-stream** (mirrors text `[..]`); any other `size` scalar is an `ExprSize`.
- **Hex byte literals are quoted strings** in YAML (`fixed: "0x89504E47…"`, `terminator: "0x00"`) — snakeyaml would otherwise coerce a bare `0x…` to an integer and overflow. A literal position: a YAML integer → `IntLit`; a `0x…`-prefixed string → `HexLit`; a boolean → `BoolLit`; any other string → `StrLit`; a map `{curie: "ns:local"}` (prop values only) → `CurieLit`.
- **`type: bits` uses a sibling `bit-length:` scalar** for the bit count (→ `BitsType(Expr)`). All other types are plain scalars (`u32`, `str`, `ascii`, `bytes`, or a struct name).
- Curie-valued AST fields (`means`, `encoded-with`, `value.datatype`, `map[].property`, struct `means`) are plain YAML strings passed through verbatim (they are `String` in the AST, not `LiteralValue`).
- Spans: the loader assigns best-effort `Span`s (snakeyaml line/column marks where readily available via the mark on a node, else `Span(0, 0)`). Surface equivalence is checked on the compiled model, not on AST span equality, so exact spans are not required — but diagnostics should carry a usable line where possible.

## Scope note

This is **Plan 2 of 3**. Plan 1 (the core text compiler) is merged to `main`. Plan 3 (hx-bundle) is separate. This plan adds only the YAML *input surface* over Plan 1's pipeline. It does NOT add new format features — anything the text DSL can't express, the YAML can't either.

---

## File Structure

Created/modified under `d:/work/hexplain-tools`:

- Modify: `gradle/libs.versions.toml` — add snakeyaml version + library.
- Modify: `hdl/build.gradle.kts` — `implementation(libs.snakeyaml)`.
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` — YAML → `ParseResult`.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt` — extract a document-compile core, add `compileYaml`.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt` — dispatch on `.yaml`/`.hx.yaml` extension.
- Create: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlLoaderTest.kt`, `YamlClauseTest.kt`.
- Create: `hdl/src/test/kotlin/io/hexplain/hdl/parity/YamlParityTest.kt`.
- Create: `hdl/src/test/resources/png.hx.yaml`, `hdl/src/test/resources/tiff.hx.yaml`.

The YAML→AST key mapping (authoritative for all tasks):

| YAML | AST |
|---|---|
| top: `format`, `namespace`, `endian`, `bit-order` | `FormatDecl` |
| top: `use: {prefix: iri}` | `PrefixDecl` list |
| top: `structs: {Name: {…}}` | `StructDecl` list |
| top: `fields: [ {…} ]` | `topLevelFields` |
| struct: `root: true`, `means`, `endian`, `bit-order`, `fields`, `raw-turtle`(str\|list), `prop: {curie: val}` | `StructDecl` |
| field: `name`, `as`(alias), `type`, `bit-length` (bits only) | `FieldDecl` + `TypeRef` |
| field clause `size: <scalar>` (`..`→EOS) | `SizeClause` |
| `repeat: {count: expr}` \| `{until: expr}` | `RepeatClause` |
| `at: {offset: expr, from: base}` | `OffsetClause` |
| `if: expr` | `PresentClause` |
| `fixed: <lit>` | `FixedClause` |
| `enum: {flags: bool, values: {raw: sym\|{symbol,label}}}` \| `<ref-name>` | `EnumClause` |
| `checksum: {algorithm, from, to}` \| `{algorithm, covers: expr}` | `ChecksumClause` |
| `terminator: "0x.."`, `trim-null: true` | `TerminatorClause`, `TrimNullClause` |
| `endian`, `bit-order`, `align`, `encoding` | `EndianClause`/`BitOrderClause`/`AlignClause`/`EncodingClause` |
| `switch: {on: expr, cases: {val: Struct}}` \| `{when: [{cond,type}]}` | `SwitchClause` |
| `means: curie` | `MeansClause` |
| `value: {expr, datatype?}` | `ValueClause` |
| `encoded-with: curie` | `EncodedWithClause` |
| `map: [{when, property, value?, datatype?}]` | `MapClause` |
| `layout: {cell, dims: [{axis, size, stride?}]}` | `LayoutClause` |
| `prop: {curie: val}` | `PropClause` |

---

## Task 1: snakeyaml dependency + smoke

**Files:**
- Modify: `gradle/libs.versions.toml`
- Modify: `hdl/build.gradle.kts`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/SnakeyamlSmokeTest.kt`

**Interfaces:**
- Produces: snakeyaml on the `:hdl` compile/test classpath.

- [ ] **Step 1: Add the version + library to the catalog**

In `gradle/libs.versions.toml`, under `[versions]` add `snakeyaml = "2.2"`, and under `[libraries]` add:

```toml
snakeyaml = { module = "org.yaml:snakeyaml", version.ref = "snakeyaml" }
```

- [ ] **Step 2: Add the dependency to the module**

In `hdl/build.gradle.kts`, inside `dependencies { … }`, add:

```kotlin
    implementation(libs.snakeyaml)
```

- [ ] **Step 3: Write the failing smoke test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/yaml/SnakeyamlSmokeTest.kt`:

```kotlin
package io.hexplain.hdl.yaml

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import org.yaml.snakeyaml.Yaml

class SnakeyamlSmokeTest {
    @Test
    fun snakeyamlIsOnClasspathAndParsesAMap() {
        @Suppress("UNCHECKED_CAST")
        val doc = Yaml().load<Any>("format: png\nendian: big") as Map<String, Any?>
        assertEquals("png", doc["format"])
        assertEquals("big", doc["endian"])
    }
}
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.SnakeyamlSmokeTest"`
Expected: PASS (proves snakeyaml resolves and loads).

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add gradle/libs.versions.toml hdl/build.gradle.kts hdl/src/test/kotlin/io/hexplain/hdl/yaml/SnakeyamlSmokeTest.kt
git commit -m "build(hdl): add snakeyaml dependency for the YAML surface"
```

---

## Task 2: YamlLoader core (format/use/structs/simple fields) + HdlCompiler.compileYaml

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt`
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlLoaderTest.kt`

**Interfaces:**
- Produces: `class YamlLoader { fun load(yaml: String): io.hexplain.hdl.parse.ParseResult }` (parses top-level `format`/`namespace`/`endian`/`bit-order`, `use`, `structs` with `root`/`means`/`endian`/`bit-order`/`as`/`fields`, and simple `name: type` fields with the `type: bits` + `bit-length` case; clause parsing is a stub returning `emptyList()` filled in Tasks 3–5). `HdlCompiler.compileYaml(yaml: String): CompileResult`, plus a refactored private `compileDocument(document, parseDiagnostics): CompileResult`.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlLoaderTest.kt`:

```kotlin
package io.hexplain.hdl.yaml

import io.hexplain.hdl.ast.BitsType
import io.hexplain.hdl.ast.Endian
import io.hexplain.hdl.ast.PrimType
import io.hexplain.hdl.ast.StringType
import io.hexplain.hdl.ast.StructRef
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class YamlLoaderTest {
    private fun load(y: String) = YamlLoader().load(y)

    @Test fun loadsFormatUseStructsAndSimpleFields() {
        val y = """
            format: png
            namespace: "https://hexplain.io/formats/png#"
            endian: big
            use:
              ar: "https://hexplain.io/ns/aspect/raster#"
            structs:
              Chunk:
                root: true
                means: "ar:Image"
                fields:
                  - { name: length, type: u32 }
                  - { name: type, type: ascii }
                  - { name: nested, type: IHDR }
                  - { name: flags, type: bits, bit-length: "3" }
        """.trimIndent()
        val r = load(y)
        assertTrue(r.diagnostics.isEmpty(), "unexpected: ${r.diagnostics}")
        val doc = r.document
        assertEquals("png", doc.format!!.name)
        assertEquals("https://hexplain.io/formats/png#", doc.format!!.namespace)
        assertEquals(Endian.BIG, doc.format!!.endian)
        assertEquals("ar" to "https://hexplain.io/ns/aspect/raster#",
            doc.prefixes.single().let { it.prefix to it.iri })
        val s = doc.structs.single()
        assertEquals("Chunk", s.name)
        assertTrue(s.isRoot)
        assertEquals("ar:Image", s.means)
        assertEquals(listOf("length", "type", "nested", "flags"), s.fields.map { it.name })
        assertEquals(PrimType("u32"), s.fields[0].type)
        assertEquals(StringType("ascii"), s.fields[1].type)
        assertEquals(StructRef("IHDR"), s.fields[2].type)
        assertTrue(s.fields[3].type is BitsType)
        assertEquals("3", (s.fields[3].type as BitsType).expr.source)
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlLoaderTest"`
Expected: FAIL — `YamlLoader` unresolved.

- [ ] **Step 3: Write the loader core**

Create `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt`:

```kotlin
package io.hexplain.hdl.yaml

import io.hexplain.hdl.ast.*
import io.hexplain.hdl.diag.Diagnostic
import io.hexplain.hdl.diag.Severity
import io.hexplain.hdl.diag.Span
import io.hexplain.hdl.parse.ParseResult
import org.yaml.snakeyaml.Yaml

class YamlLoader {
    private val diags = ArrayList<Diagnostic>()

    fun load(yaml: String): ParseResult {
        diags.clear()
        val root: Any? = try {
            Yaml().load(yaml)
        } catch (ex: Exception) {
            err("YAML parse error: ${ex.message}")
            return ParseResult(Document(null, emptyList(), emptyList(), emptyList()), diags.toList())
        }
        val top = asMap(root, "document") ?: return ParseResult(
            Document(null, emptyList(), emptyList(), emptyList()), diags.toList()
        )

        val format = if (top.containsKey("format")) FormatDecl(
            name = str(top["format"]) ?: "format",
            namespace = str(top["namespace"]),
            endian = endian(top["endian"]),
            bitOrder = bitOrder(top["bit-order"]),
            span = SPAN
        ) else null

        val prefixes = (asMap(top["use"], "use") ?: emptyMap()).map { (p, v) ->
            PrefixDecl(p.toString(), str(v) ?: "", SPAN)
        }

        val structs = (asMap(top["structs"], "structs") ?: emptyMap()).map { (name, body) ->
            structDecl(name.toString(), asMap(body, "struct '$name'") ?: emptyMap())
        }

        val topFields = (asList(top["fields"]) ?: emptyList()).mapNotNull { f ->
            asMap(f, "top-level field")?.let { fieldDecl(it) }
        }

        return ParseResult(Document(format, prefixes, structs, topFields), diags.toList())
    }

    private fun structDecl(name: String, m: Map<String, Any?>): StructDecl {
        val fields = (asList(m["fields"]) ?: emptyList()).mapNotNull { f ->
            asMap(f, "field in struct '$name'")?.let { fieldDecl(it) }
        }
        val raw = when (val rt = m["raw-turtle"]) {
            is String -> listOf(RawTurtle(rt, SPAN))
            is List<*> -> rt.mapNotNull { str(it)?.let { s -> RawTurtle(s, SPAN) } }
            else -> emptyList()
        }
        val props = (asMap(m["prop"], "prop in '$name'") ?: emptyMap()).map { (c, v) ->
            PropClause(c.toString(), toLiteral(v))
        }
        return StructDecl(
            name = name,
            alias = str(m["as"]),
            isRoot = m["root"] == true,
            means = str(m["means"]),
            endian = endian(m["endian"]),
            bitOrder = bitOrder(m["bit-order"]),
            fields = fields,
            raw = raw,
            props = props,
            span = SPAN
        )
    }

    private fun fieldDecl(m: Map<String, Any?>): FieldDecl {
        val typeName = str(m["type"]) ?: "u8"
        val type = typeRef(typeName, m)
        return FieldDecl(
            name = str(m["name"]) ?: "?",
            alias = str(m["as"]),
            type = type,
            clauses = clausesOf(m),   // Tasks 3–5 fill this in; Task 2 returns emptyList()
            span = SPAN
        )
    }

    private fun typeRef(t: String, m: Map<String, Any?>): TypeRef = when (t) {
        "bytes" -> BytesType
        "str" -> StringType(null)
        "ascii", "utf8", "utf16le", "utf16be", "latin1" -> StringType(t)
        "bits" -> BitsType(expr(m["bit-length"]) ?: Expr("0", false, SPAN))
        in PRIM_TYPES -> PrimType(t)
        else -> StructRef(t)
    }

    // Filled in Tasks 3–5:
    private fun clausesOf(m: Map<String, Any?>): List<Clause> = emptyList()

    // ---- shared helpers ----
    internal fun err(msg: String) { diags.add(Diagnostic(Severity.ERROR, msg, SPAN)) }

    @Suppress("UNCHECKED_CAST")
    internal fun asMap(v: Any?, what: String): Map<String, Any?>? = when (v) {
        null -> null
        is Map<*, *> -> v.entries.associate { (k, value) -> k.toString() to value }
        else -> { err("expected a mapping for $what but got ${v::class.simpleName}"); null }
    }
    internal fun asList(v: Any?): List<Any?>? = (v as? List<*>)?.toList()
    internal fun str(v: Any?): String? = (v as? String)
    internal fun endian(v: Any?): Endian? = when (str(v)) {
        "big" -> Endian.BIG; "little" -> Endian.LITTLE; null -> null
        else -> { err("bad endian '${v}'"); null }
    }
    internal fun bitOrder(v: Any?): BitOrderOpt? = when (str(v)) {
        "msb" -> BitOrderOpt.MSB; "lsb" -> BitOrderOpt.LSB; null -> null
        else -> { err("bad bit-order '${v}'"); null }
    }

    /** A YAML expression scalar → Expr. Backtick-wrapped → rawHel. */
    internal fun expr(v: Any?): Expr? {
        val s = when (v) { is String -> v; is Number -> v.toString(); is Boolean -> v.toString(); else -> return null }
        val t = s.trim()
        return if (t.startsWith("`") && t.endsWith("`") && t.length >= 2)
            Expr(t.substring(1, t.length - 1), true, SPAN)
        else Expr(t, false, SPAN)
    }

    /** A YAML value in a LiteralValue position (@fixed / @prop / enum raw / terminator). */
    internal fun toLiteral(v: Any?): LiteralValue = when (v) {
        is Boolean -> BoolLit(v)
        is Int -> IntLit(v.toLong())
        is Long -> IntLit(v)
        is Map<*, *> -> {
            val c = v["curie"]?.toString()
            if (c != null) CurieLit(c) else { err("unrecognized literal map $v"); StrLit(v.toString()) }
        }
        is String -> if (v.startsWith("0x") || v.startsWith("0X")) HexLit(hexToBytes(v)) else StrLit(v)
        else -> { err("unrecognized literal $v"); StrLit(v.toString()) }
    }

    internal fun hexToBytes(t: String): ByteArray {
        val h = t.removePrefix("0x").removePrefix("0X")
        return ByteArray(h.length / 2) {
            ((Character.digit(h[it * 2], 16) shl 4) + Character.digit(h[it * 2 + 1], 16)).toByte()
        }
    }

    companion object {
        private val SPAN = Span(0, 0)
        val PRIM_TYPES = setOf(
            "u8","i8","u16","u16le","u16be","u32","u32le","u32be","u64","u64le","u64be",
            "i16","i16le","i16be","i32","i32le","i32be","i64","i64le","i64be",
            "f32","f32le","f32be","f64","f64le","f64be"
        )
    }
}
```

- [ ] **Step 4: Refactor HdlCompiler to add compileYaml**

In `hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt`, refactor `compile(source)` to share a document-compile core, and add `compileYaml`. Replace the body of `compile` and add the two methods (keep `validateExpressions`/`validateEnumeratedValues`/companion unchanged):

```kotlin
    fun compile(source: String): CompileResult {
        val parsed = HdlParser(HdlLexer(source).tokenize()).parse()
        return compileDocument(parsed.document, parsed.diagnostics)
    }

    fun compileYaml(yaml: String): CompileResult {
        val parsed = io.hexplain.hdl.yaml.YamlLoader().load(yaml)
        return compileDocument(parsed.document, parsed.diagnostics)
    }

    private fun compileDocument(
        document: io.hexplain.hdl.ast.Document,
        parseDiagnostics: List<Diagnostic>
    ): CompileResult {
        val resolved = Resolver().resolve(document)
        val diags = ArrayList<Diagnostic>()
        diags.addAll(parseDiagnostics)
        diags.addAll(resolved.diagnostics)
        validateExpressions(resolved, diags)
        validateEnumeratedValues(resolved, diags)
        val model = TurtleEmitter(resolved).emit()
        return CompileResult(model, resolved.rootStructUri, diags)
    }
```

- [ ] **Step 5: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlLoaderTest"` then the full `./gradlew :hdl:test` (confirm no regression to existing `HdlCompilerTest`).
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlLoaderTest.kt
git commit -m "feat(hdl): YamlLoader core + HdlCompiler.compileYaml"
```

---

## Task 3: YamlLoader — physical clauses

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` (`clausesOf`)
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt`

**Interfaces:** fills `clausesOf` for `size` (incl. `..` and backtick-rawHel), `repeat`, `at`, `if`, `fixed`, `terminator`, `trim-null`, `endian`, `bit-order`, `align`, `encoding`.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt`:

```kotlin
package io.hexplain.hdl.yaml

import io.hexplain.hdl.ast.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class YamlClauseTest {
    private fun field(fieldYaml: String): FieldDecl {
        val y = "structs:\n  S:\n    fields:\n      - $fieldYaml"
        return YamlLoader().load(y).document.structs.single().fields.single()
    }

    @Test fun sizeSiblingEosAndRawHel() {
        assertEquals("length",
            (field("{ name: d, type: bytes, size: length }").clauses.filterIsInstance<SizeClause>().first().spec as ExprSize).expr.source)
        assertTrue(field("{ name: d, type: bytes, size: \"..\" }").clauses.any { it is SizeClause && it.spec is ToEndOfStream })
        val raw = field("{ name: d, type: bytes, size: \"`parent.n`\" }").clauses.filterIsInstance<SizeClause>().first().spec as ExprSize
        assertTrue(raw.expr.rawHel); assertEquals("parent.n", raw.expr.source)
    }

    @Test fun repeatOffsetPresenceFixedTerminatorAlignEncoding() {
        assertEquals("n", field("{ name: e, type: Item, repeat: { count: n } }").clauses.filterIsInstance<RepeatClause>().first().count!!.source)
        assertEquals("eof()", field("{ name: e, type: Item, repeat: { until: \"eof()\" } }").clauses.filterIsInstance<RepeatClause>().first().until!!.source)
        val off = field("{ name: x, type: u8, at: { offset: p, from: stream-start } }").clauses.filterIsInstance<OffsetClause>().first()
        assertEquals("p", off.expr.source); assertEquals(OffsetBaseOpt.STREAM_START, off.base)
        assertTrue(field("{ name: g, type: u32, if: \"h == 1\" }").clauses.any { it is PresentClause })
        assertTrue(field("{ name: s, type: bytes, size: 4, fixed: \"0x89504E47\" }").clauses.any { it is FixedClause && it.value is HexLit })
        assertTrue(field("{ name: n, type: str, terminator: \"0x00\", trim-null: true, encoding: latin1 }").clauses.any { it is TerminatorClause })
        assertTrue(field("{ name: a, type: u32, align: 4, endian: little, bit-order: lsb }").clauses.any { it is AlignClause && it.n == 4L })
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlClauseTest"`
Expected: FAIL (empty clause list).

- [ ] **Step 3: Implement the physical branch of `clausesOf`**

Replace `clausesOf` in `YamlLoader.kt` with the physical-clause implementation (enum/checksum/switch/semantic/layout come in Tasks 4–5 — leave those keys for now):

```kotlin
    private fun clausesOf(m: Map<String, Any?>): List<Clause> {
        val out = ArrayList<Clause>()
        // size
        if (m.containsKey("size")) {
            val sv = m["size"]
            if (str(sv)?.trim() == "..") out.add(SizeClause(ToEndOfStream))
            else expr(sv)?.let { out.add(SizeClause(ExprSize(it))) }
        }
        // repeat
        asMap(m["repeat"], "repeat")?.let { r ->
            val count = r["count"]?.let { expr(it) }
            val until = r["until"]?.let { expr(it) }
            out.add(RepeatClause(count, until))
        }
        // at (offset)
        asMap(m["at"], "at")?.let { a ->
            expr(a["offset"])?.let { e -> out.add(OffsetClause(e, offsetBase(a["from"]))) }
        }
        m["if"]?.let { expr(it)?.let { e -> out.add(PresentClause(e)) } }
        if (m.containsKey("fixed")) out.add(FixedClause(toLiteral(m["fixed"])))
        if (m.containsKey("terminator")) out.add(TerminatorClause(hexBytesOf(toLiteral(m["terminator"]))))
        if (m["trim-null"] == true) out.add(TrimNullClause)
        endian(m["endian"])?.let { out.add(EndianClause(it)) }
        bitOrder(m["bit-order"])?.let { out.add(BitOrderClause(it)) }
        (m["align"] as? Int)?.let { out.add(AlignClause(it.toLong())) }
        (m["align"] as? Long)?.let { out.add(AlignClause(it)) }
        str(m["encoding"])?.let { out.add(EncodingClause(it)) }
        out.addAll(semanticAndStructuralClauses(m))  // Tasks 4–5
        return out
    }

    // Filled in Tasks 4–5:
    private fun semanticAndStructuralClauses(m: Map<String, Any?>): List<Clause> = emptyList()

    private fun offsetBase(v: Any?): OffsetBaseOpt? = when (str(v)) {
        "stream-start" -> OffsetBaseOpt.STREAM_START
        "stream-end" -> OffsetBaseOpt.STREAM_END
        "parent-start" -> OffsetBaseOpt.PARENT_START
        "current" -> OffsetBaseOpt.CURRENT
        null -> null
        else -> { err("bad offset base '$v'"); null }
    }

    private fun hexBytesOf(v: LiteralValue): ByteArray = when (v) {
        is HexLit -> v.bytes
        is IntLit -> byteArrayOf(v.value.toByte())
        else -> { err("terminator must be a hex/int literal"); ByteArray(0) }
    }
```

Note: the `endian`/`bit-order` on a field vs. on the struct — `clausesOf` is only called for fields, and `structDecl` reads its own `endian`/`bit-order` keys directly, so there is no collision.

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlClauseTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt
git commit -m "feat(hdl): YAML physical clauses (size/repeat/at/if/fixed/terminator/align/encoding)"
```

---

## Task 4: YamlLoader — enum / checksum / switch

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` (`semanticAndStructuralClauses`, part 1)
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt` (add cases)

**Interfaces:** extends `semanticAndStructuralClauses` for `enum`, `checksum`, `switch`.

- [ ] **Step 1: Add failing tests**

Append to `YamlClauseTest.kt`:

```kotlin
    @Test fun enumChecksumSwitch() {
        val en = field("{ name: ct, type: u8, enum: { values: { 0: Grayscale, 2: RGB } } }")
            .clauses.filterIsInstance<EnumClause>().first()
        assertEquals(2, en.inline!!.size)
        assertEquals(0L, (en.inline!![0].raw as IntLit).value)
        assertEquals("Grayscale", en.inline!![0].symbol)

        val cs = field("{ name: crc, type: u32, checksum: { algorithm: crc32, from: type, to: data } }")
            .clauses.filterIsInstance<ChecksumClause>().first()
        assertEquals("crc32", cs.algo); assertEquals("type", cs.fromField); assertEquals("data", cs.toField)

        val sw = field("{ name: d, type: bytes, size: length, switch: { on: type, cases: { IHDR: IHDR_ChunkData, PLTE: PLTE_ChunkData } } }")
            .clauses.filterIsInstance<SwitchClause>().first()
        assertEquals("type", sw.on!!.source)
        assertEquals(2, sw.arms.size)
        assertEquals("IHDR", sw.arms[0].struct)
        assertEquals("IHDR", (sw.arms[0].matchValue as StrLit).value)
    }
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlClauseTest.enumChecksumSwitch"`
Expected: FAIL.

- [ ] **Step 3: Implement part 1 of `semanticAndStructuralClauses`**

Replace the `semanticAndStructuralClauses` stub with an accumulating implementation and add the helpers (part 2 in Task 5 appends the semantic/layout branches):

```kotlin
    private fun semanticAndStructuralClauses(m: Map<String, Any?>): List<Clause> {
        val out = ArrayList<Clause>()
        // enum
        when (val e = m["enum"]) {
            is String -> out.add(EnumClause(false, e, null))
            is Map<*, *> -> {
                val em = asMap(e, "enum")!!
                val flags = em["flags"] == true
                val values = asMap(em["values"], "enum values") ?: emptyMap()
                val pairs = values.map { (rawKey, symVal) ->
                    val raw = literalFromKey(rawKey)
                    when (symVal) {
                        is Map<*, *> -> {
                            val sm = asMap(symVal, "enum value")!!
                            EnumPair(raw, str(sm["symbol"]) ?: "?", str(sm["label"]))
                        }
                        else -> EnumPair(raw, str(symVal) ?: symVal.toString(), null)
                    }
                }
                out.add(EnumClause(flags, null, pairs))
            }
            else -> {}
        }
        // checksum
        asMap(m["checksum"], "checksum")?.let { c ->
            val algo = str(c["algorithm"]) ?: ""
            if (c.containsKey("covers")) out.add(ChecksumClause(algo, null, null, expr(c["covers"])))
            else out.add(ChecksumClause(algo, str(c["from"]), str(c["to"]), null))
        }
        // switch
        asMap(m["switch"], "switch")?.let { sw ->
            val on = sw["on"]?.let { expr(it) }
            val arms = ArrayList<SwitchArm>()
            asMap(sw["cases"], "switch cases")?.forEach { (value, struct) ->
                arms.add(SwitchArm(literalFromKey(value), null, str(struct) ?: struct.toString()))
            }
            (asList(sw["when"]) ?: emptyList()).forEach { w ->
                asMap(w, "switch when arm")?.let { wm ->
                    arms.add(SwitchArm(null, expr(wm["cond"]), str(wm["type"]) ?: "?"))
                }
            }
            out.add(SwitchClause(on, arms))
        }
        out.addAll(semanticClauses(m))  // Task 5
        return out
    }

    // Filled in Task 5:
    private fun semanticClauses(m: Map<String, Any?>): List<Clause> = emptyList()

    /** A YAML map key (always a String from snakeyaml, but numeric keys arrive typed) → LiteralValue. */
    private fun literalFromKey(k: Any?): LiteralValue = when (k) {
        is Int -> IntLit(k.toLong())
        is Long -> IntLit(k)
        is Boolean -> BoolLit(k)
        is String -> if (k.startsWith("0x") || k.startsWith("0X")) HexLit(hexToBytes(k)) else StrLit(k)
        else -> StrLit(k.toString())
    }
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlClauseTest"`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt
git commit -m "feat(hdl): YAML enum/checksum/switch clauses"
```

---

## Task 5: YamlLoader — means / value / encoded-with / map / layout

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` (`semanticClauses`)
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt` (add cases)

**Interfaces:** fills `semanticClauses` for `means`, `value`, `encoded-with`, `map`, `layout`. (`prop` at field level is not a text-DSL field clause — the text DSL only allows `@prop` at struct level and as an escape; for YAML, field-level `prop` is out of scope to match; struct-level `prop` was handled in Task 2.)

- [ ] **Step 1: Add failing tests**

Append to `YamlClauseTest.kt`:

```kotlin
    @Test fun meansValueEncodedWithMapLayout() {
        val f = field("{ name: w, type: u32, means: \"ar:width\", value: { expr: \"w / 2\", datatype: \"xsd:double\" } }")
        assertEquals("ar:width", f.clauses.filterIsInstance<MeansClause>().first().curie)
        val v = f.clauses.filterIsInstance<ValueClause>().first()
        assertEquals("w / 2", v.expr.source); assertEquals("xsd:double", v.datatype)

        assertEquals("aenc:deflate",
            field("{ name: d, type: bytes, size: \"..\", encoded-with: \"aenc:deflate\" }")
                .clauses.filterIsInstance<EncodedWithClause>().first().curie)

        val map = field("{ name: t, type: str, terminator: \"0x00\", map: [ { when: \"k == 'Title'\", property: \"dct:title\" } ] }")
            .clauses.filterIsInstance<MapClause>().first()
        assertEquals(1, map.arms.size)
        assertEquals("dct:title", map.arms[0].property)

        val lay = field("{ name: px, type: bytes, size: \"..\", layout: { cell: u8, dims: [ { axis: Y, size: height }, { axis: Band, size: 3 } ] } }")
            .clauses.filterIsInstance<LayoutClause>().first()
        assertEquals(2, lay.dims.size)
        assertEquals("Y", lay.dims[0].axis); assertEquals("height", lay.dims[0].sizeFromField)
        assertEquals(3L, (lay.dims[1].size as IntLit).value)
    }
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlClauseTest.meansValueEncodedWithMapLayout"`
Expected: FAIL.

- [ ] **Step 3: Implement `semanticClauses`**

Replace the `semanticClauses` stub:

```kotlin
    private fun semanticClauses(m: Map<String, Any?>): List<Clause> {
        val out = ArrayList<Clause>()
        str(m["means"])?.let { out.add(MeansClause(it)) }
        asMap(m["value"], "value")?.let { v ->
            expr(v["expr"])?.let { e -> out.add(ValueClause(e, str(v["datatype"]))) }
        }
        str(m["encoded-with"])?.let { out.add(EncodedWithClause(it)) }
        (asList(m["map"]) ?: emptyList()).let { arms ->
            if (arms.isNotEmpty()) {
                val mapArms = arms.mapNotNull { a ->
                    asMap(a, "map arm")?.let { am ->
                        expr(am["when"])?.let { w ->
                            MapArm(w, str(am["property"]) ?: "?", am["value"]?.let { expr(it) }, str(am["datatype"]))
                        }
                    }
                }
                out.add(MapClause(mapArms))
            }
        }
        asMap(m["layout"], "layout")?.let { l ->
            val cell = typeRef(str(l["cell"]) ?: "u8", l)
            val dims = (asList(l["dims"]) ?: emptyList()).mapNotNull { d ->
                asMap(d, "layout dim")?.let { dm ->
                    val axis = str(dm["axis"]) ?: "X"
                    val sizeVal = dm["size"]
                    val (size, sizeFromField) = when (sizeVal) {
                        is Int -> IntLit(sizeVal.toLong()) to null
                        is Long -> IntLit(sizeVal) to null
                        is String -> null to sizeVal
                        else -> null to null
                    }
                    DimDecl(axis, size, sizeFromField, dm["stride"]?.let { expr(it) })
                }
            }
            out.add(LayoutClause(cell, dims))
        }
        return out
    }
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlClauseTest"` then full `./gradlew :hdl:test`.
Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlClauseTest.kt
git commit -m "feat(hdl): YAML semantic/layout clauses (means/value/encoded-with/map/layout)"
```

---

## Task 6: Diagnostics + CLI dispatch

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlLoaderTest.kt` (add cases)

**Interfaces:** the CLI reads `.yaml`/`.hx.yaml` inputs via `compileYaml`, else `compile`. The loader returns diagnostics (not exceptions) on malformed YAML and on a non-mapping document.

- [ ] **Step 1: Add failing diagnostic tests**

Append to `YamlLoaderTest.kt`:

```kotlin
    @Test fun malformedYamlBecomesDiagnosticNotException() {
        val r = YamlLoader().load("format: png\n  bad: : indent")
        assertTrue(r.diagnostics.any { it.message.contains("YAML parse error") })
    }

    @Test fun nonMappingDocumentIsADiagnostic() {
        val r = YamlLoader().load("- just\n- a\n- list")
        assertFalse(r.diagnostics.isEmpty())
    }

    @Test fun compileYamlEndToEndThroughFacade() {
        val y = "format: f\nendian: big\nstructs:\n  S:\n    root: true\n    fields:\n      - { name: n, type: u16 }\n      - { name: v, type: u32 }"
        val r = io.hexplain.hdl.HdlCompiler().compileYaml(y)
        assertTrue(r.ok, "${r.diagnostics}")
        assertEquals("https://hexplain.io/formats/f#S", r.rootStructUri)
        assertTrue(r.toTurtle().contains("bddo:Struct"))
    }
```

- [ ] **Step 2: Run to verify it fails/passes**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlLoaderTest"`
Expected: the two diagnostic tests + the façade test PASS (the loader already returns diagnostics; if `nonMappingDocumentIsADiagnostic` fails because a list document produced no diagnostic, ensure `asMap(root, "document")` on a non-map emits the "expected a mapping" error — it does). If any fails, fix the loader so a non-mapping root yields a diagnostic.

- [ ] **Step 3: Extend the CLI to dispatch on extension**

In `hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt`, change the compile call to pick the surface by extension:

```kotlin
    val source = File(input).readText()
    val result = if (input.endsWith(".yaml") || input.endsWith(".yml"))
        HdlCompiler().compileYaml(source)
    else HdlCompiler().compile(source)
```

(Leave the rest of `main` — diagnostics to stderr, exit 1 on ERROR, `-o` output — unchanged.)

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test` (full suite).
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/cli/Main.kt hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlLoaderTest.kt
git commit -m "feat(hdl): YAML diagnostics + CLI .yaml dispatch"
```

---

## Task 7: Surface equivalence + behavioral parity (PNG & TIFF)

**Files:**
- Create: `hdl/src/test/resources/png.hx.yaml`, `hdl/src/test/resources/tiff.hx.yaml`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parity/YamlParityTest.kt`

**Interfaces:** proves the YAML surface is a faithful mirror: for PNG and TIFF, `compileYaml(<fmt>.hx.yaml)` produces a model isomorphic to `compile(<fmt>.hx)`, and the YAML-generated PNG profile parses `sample1.png` to the same Width/Height. Reuses the existing `png.hx`/`tiff.hx` and `sample1.png` test resources from Plan 1.

- [ ] **Step 1: Author `png.hx.yaml` mirroring `png.hx`**

Read `hdl/src/test/resources/png.hx` (the Plan-1 PNG source) and translate it faithfully to YAML. Create `hdl/src/test/resources/png.hx.yaml` (mirror the exact structs/fields/clauses, including the `repeat until` chunk termination and the backtick `` `parent.ChunkLength` `` sizing on PLTE/IDAT — as YAML `size: "\`parent.ChunkLength\`"`). Example shape (fill from the real png.hx):

```yaml
format: png
namespace: "https://hexplain.io/formats/png#"
endian: big
structs:
  File:
    root: true
    fields:
      - { name: Signature, type: bytes, size: 8, fixed: "0x89504E470D0A1A0A" }
      - { name: Chunks, type: Chunk, repeat: { until: "instance.ChunkType == \"IEND\"" } }
  Chunk:
    fields:
      - { name: ChunkLength, type: u32be }
      - { name: ChunkType, type: str, size: 4 }
      - name: ChunkData
        type: bytes
        size: ChunkLength
        switch: { on: ChunkType, cases: { IHDR: IHDR_ChunkData, PLTE: PLTE_ChunkData, IDAT: IDAT_ChunkData } }
      - { name: ChunkCRC, type: u32be, checksum: { algorithm: crc32, from: ChunkType, to: ChunkData } }
  IHDR_ChunkData:
    fields:
      - { name: Width, type: u32be }
      - { name: Height, type: u32be }
      - { name: BitDepth, type: u8 }
      - { name: ColorType, type: u8 }
      - { name: Compression, type: u8 }
      - { name: Filter, type: u8 }
      - { name: Interlace, type: u8 }
  PLTE_ChunkData:
    fields:
      - { name: Palette, type: bytes, size: "`parent.ChunkLength`" }
  IDAT_ChunkData:
    fields:
      - { name: Data, type: bytes, size: "`parent.ChunkLength`" }
```

(Match `png.hx` exactly — if the real file differs in field names or the repeat/switch details, follow the real file, not this sketch.)

- [ ] **Step 2: Author `tiff.hx.yaml` mirroring `tiff.hx`**

Create `hdl/src/test/resources/tiff.hx.yaml`:

```yaml
format: tiff
namespace: "https://hexplain.io/formats/tiff#"
endian: little
structs:
  File:
    root: true
    fields:
      - { name: ByteOrder, type: str, size: 2 }
      - { name: Version, type: u16le }
      - { name: FirstIFDOffset, type: u32le }
```

(Match the real `tiff.hx`.)

- [ ] **Step 3: Write the parity test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parity/YamlParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class YamlParityTest {
    private fun res(name: String) =
        this::class.java.classLoader.getResourceAsStream(name)?.readBytes()?.toString(Charsets.UTF_8)
            ?: error("missing $name")
    private fun bytes(name: String) =
        this::class.java.classLoader.getResourceAsStream(name)?.readBytes() ?: error("missing $name")

    @Test fun pngYamlIsIsomorphicToTextSurface() {
        val fromText = HdlCompiler().compile(res("png.hx"))
        val fromYaml = HdlCompiler().compileYaml(res("png.hx.yaml"))
        assertTrue(fromText.ok && fromYaml.ok, "text=${fromText.diagnostics} yaml=${fromYaml.diagnostics}")
        assertTrue(fromText.model.isIsomorphicWith(fromYaml.model),
            "YAML-compiled PNG profile is not isomorphic to the text-compiled one")
    }

    @Test fun tiffYamlIsIsomorphicToTextSurface() {
        val fromText = HdlCompiler().compile(res("tiff.hx"))
        val fromYaml = HdlCompiler().compileYaml(res("tiff.hx.yaml"))
        assertTrue(fromText.ok && fromYaml.ok, "text=${fromText.diagnostics} yaml=${fromYaml.diagnostics}")
        assertTrue(fromText.model.isIsomorphicWith(fromYaml.model))
    }

    @Test fun yamlPngProfileParsesSampleWidthHeight() {
        val result = HdlCompiler().compileYaml(res("png.hx.yaml"))
        assertTrue(result.ok, "${result.diagnostics}")
        val model = ProfileLoader().loadFromString(result.toTurtle())
        val ir = RdfToIrCompiler(model).compile("https://hexplain.io/formats/png#File")
        val parsed = Metaparser(ir).parse(bytes("sample1.png")) as Map<*, *>
        val chunkList = when (val chunks = parsed["Chunks"]) {
            is List<*> -> chunks; is Map<*, *> -> listOf(chunks); else -> error("Chunks not parsed")
        }
        val ihdr = chunkList.mapNotNull { it as? Map<*, *> }.find { it["ChunkType"] == "IHDR" } ?: error("no IHDR")
        val data = ihdr["ChunkData"] as Map<*, *>
        assertTrue((data["Width"] as Number).toInt() > 0 && (data["Height"] as Number).toInt() > 0)
    }
}
```

- [ ] **Step 4: Run, iterate the YAML until isomorphic + parsing, verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parity.YamlParityTest"`
Expected: all three PASS. If `pngYamlIsIsomorphicToTextSurface` fails, diff the two `toTurtle()` outputs (print both) and adjust `png.hx.yaml` until the mirror is exact (common causes: a missing field, a `size`/`switch` detail, or a `str size N` vs `strN` mismatch). Do NOT weaken the assertions — the YAML must genuinely mirror the text. Then run the full `./gradlew :hdl:test`.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/test/resources/png.hx.yaml hdl/src/test/resources/tiff.hx.yaml hdl/src/test/kotlin/io/hexplain/hdl/parity/YamlParityTest.kt
git commit -m "test(hdl): YAML surface equivalence + behavioral parity (PNG/TIFF); Plan 2 complete"
```

---

## Self-Review

**1. Spec coverage** (design §11 YAML projection): every clause key in the design's YAML mapping table has a loader branch (Tasks 3–5) and the mapping table above is reproduced from §11. `format`/`use`/`structs`/`fields` (Task 2); physical clauses (Task 3); enum/checksum/switch (Task 4); means/value/encoded-with/map/layout (Task 5); diagnostics + CLI (Task 6); equivalence + parity (Task 7). The `compileYaml` façade entry and CLI dispatch are covered. ✅

**2. Placeholder scan:** No TODO/TBD. Each `clausesOf`/`semanticAndStructuralClauses`/`semanticClauses` stub is an explicit, named staging point filled by a later numbered task (not a placeholder — each task's test asserts only what it adds), mirroring Plan 1's staged-emitter pattern. ✅

**3. Type consistency:** `YamlLoader.load` returns `io.hexplain.hdl.parse.ParseResult` (the existing type). All AST constructors used (`FormatDecl`, `PrefixDecl`, `StructDecl`, `FieldDecl`, every `Clause`/`TypeRef`/`LiteralValue` subtype, `EnumPair`/`SwitchArm`/`MapArm`/`DimDecl`) match the current `Ast.kt` field names/types exactly (verified against the merged Plan 1 AST). `HdlCompiler.compileYaml`/`compileDocument` reuse the existing `Resolver`/`TurtleEmitter`/`CompileResult`. `Metaparser`/`ProfileLoader`/`RdfToIrCompiler` calls match the signatures used in Plan 1's parity tests. ✅

**4. Backtick/EOS/hex conventions** are stated once in Global Constraints and applied uniformly in `expr`/`clausesOf`/`toLiteral`. ✅

---

## Follow-on

**Plan 3 — hx-bundle** remains: an `ABND` Kotlin vocab (absent from core), AST + parser + YAML + emitter for `bundle`/`part` profiles and `asset` instances, anchored on SHACL validation against `specification/aspect/bundle/bundle.ttl` shapes (core has no bundle runtime for behavioral parity).
