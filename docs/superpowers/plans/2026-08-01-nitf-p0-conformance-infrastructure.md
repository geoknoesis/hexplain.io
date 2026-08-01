# NITF P0 — Conformance Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the format-agnostic conformance layer — requirement/constraint vocabularies, HEL rule-expression extensions, a conformance engine, and error-recovering parse — so that NITF conformance rules can be authored declaratively in later phases.

**Architecture:** Two new format-agnostic RDF vocabularies (`hx-req`, `hx-conf`) let a profile bind HEL boolean assertions to identified standards requirements. A `ConformanceEngine` in `core` walks constraint scopes over a parsed tree and emits `Finding`s. Separately, `Metaparser` gains a `COLLECT` recovery policy so a malformed file yields many diagnostics instead of one exception; those diagnostics bridge into the same `Finding` stream. No Kotlin rule classes — conformance logic lives in HEL.

**Tech Stack:** Kotlin 2.2.10 (JVM), Apache Jena 5.5.0 (core/arq/shacl), JUnit 5.10.2, Gradle with version catalog. RDF vocabularies in Turtle with SHACL shapes, validated by the existing pySHACL harness.

## Global Constraints

- **Two repositories.** `d:\work\hexplain.io` holds vocabularies and profiles; `d:\work\hexplain-tools` holds Kotlin. Each task states its repo. Never stage files from the other repo in a commit.
- **Stage explicitly.** `hexplain.io` has many pre-existing modified files on branch `feat/hx-bundle`. Every commit lists exact paths — never `git commit -am`, never `git add -A`.
- **Backward compatibility is mandatory.** All new `HelEvaluator` constructor parameters and all new `Metaparser` parameters MUST have defaults. The existing test suite must stay green after every task.
- **Default behavior unchanged.** `RecoveryPolicy.STRICT` is the default and preserves today's throw-on-first-error semantics exactly.
- **No `now()` in HEL.** The reference instant is a run parameter surfaced as `evaluationInstant()`.
- **No risk categories.** The tool emits requirement ID, discrepancy type, and location. Never Category 1–5.
- **Namespaces:** `https://hexplain.io/ns/req#` and `https://hexplain.io/ns/conf#`.
- **Kotlin package for new runtime code:** `io.hexplain.core.conformance`.
- **Test naming:** JUnit 5, backtick-quoted descriptive names, matching `HelExpressionTest.kt`.

---

### Task 1: Error-recovering parse

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/metacodec/ParseDiagnostics.kt`
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (constructor; `parseStruct` field loop at lines 208–246)
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserRecoveryTest.kt`

**Interfaces:**
- Consumes: nothing.
- Produces: `enum class RecoveryPolicy { STRICT, COLLECT }`; `data class ParseDiagnostic(val message: String, val kind: HexplainErrorKind, val byteOffset: Int, val structName: String, val fieldName: String?)`; `class ParseDiagnostics { val entries: List<ParseDiagnostic>; fun record(d: ParseDiagnostic) }`. `Metaparser` gains constructor params `recoveryPolicy: RecoveryPolicy = RecoveryPolicy.STRICT` and `diagnostics: ParseDiagnostics? = null`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserRecoveryTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/** COLLECT recovery: a struct with two bad fixed-value fields yields two diagnostics, not one throw. */
class MetaparserRecoveryTest {

    private val bytesType = DataTypeIR(name = "bddo:Bytes", baseType = BaseType.BYTES, bitWidth = 8)

    /** Header: MAGIC(4, fixed 'NITF') VER(2, fixed '21') TAIL(2). */
    private fun formatIR(): FormatIR {
        val fields = listOf(
            FieldIR(name = "MAGIC", dataType = bytesType, size = 4, fixedValue = "NITF".toByteArray()),
            FieldIR(name = "VER", dataType = bytesType, size = 2, fixedValue = "21".toByteArray()),
            FieldIR(name = "TAIL", dataType = bytesType, size = 2),
        )
        val struct = StructIR(name = "t:Header", fields = fields)
        return FormatIR(name = "test", rootStruct = "t:Header", structs = mapOf("t:Header" to struct))
    }

    @Test
    fun `COLLECT records a diagnostic per bad fixed value and keeps parsing`() {
        val diags = ParseDiagnostics()
        val parser = Metaparser(
            formatIR = formatIR(),
            recoveryPolicy = RecoveryPolicy.COLLECT,
            diagnostics = diags,
        )

        @Suppress("UNCHECKED_CAST")
        val result = parser.parse("BIIF20ZZ".toByteArray()) as Map<String, Any>

        assertEquals(2, diags.entries.size, "expected one diagnostic for MAGIC and one for VER")
        assertEquals(listOf("MAGIC", "VER"), diags.entries.map { it.fieldName })
        assertEquals(HexplainErrorKind.VALIDATION, diags.entries[0].kind)
        assertEquals(0, diags.entries[0].byteOffset)
        assertEquals(4, diags.entries[1].byteOffset)
        assertTrue(diags.entries[0].message.contains("MAGIC"))
        // Parsing continued: the field after the failures was still read.
        assertEquals("ZZ", String(result["TAIL"] as ByteArray))
    }

    @Test
    fun `STRICT is unchanged and still throws on the first bad fixed value`() {
        val parser = Metaparser(formatIR = formatIR())
        val e = org.junit.jupiter.api.assertThrows<HexplainParsingException> {
            parser.parse("BIIF20ZZ".toByteArray())
        }
        assertTrue(e.message!!.contains("MAGIC"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.MetaparserRecoveryTest"`
Expected: FAIL — compilation error, `RecoveryPolicy`/`ParseDiagnostics` unresolved.

- [ ] **Step 3: Create the diagnostics model**

Create `core/src/main/kotlin/io/hexplain/core/metacodec/ParseDiagnostics.kt`:

```kotlin
package io.hexplain.core.metacodec

/**
 * How the metaparser reacts to a recoverable parse failure.
 *
 * STRICT  — throw on the first failure (historical behaviour; the default).
 * COLLECT — record a [ParseDiagnostic] and keep going, so one pass over a malformed
 *           file reports every discrepancy rather than only the first. Conformance
 *           testing requires this: a file with twelve defects must yield twelve findings.
 */
enum class RecoveryPolicy { STRICT, COLLECT }

/** One recoverable parse failure, located in the stream and in the format description. */
data class ParseDiagnostic(
    val message: String,
    val kind: HexplainErrorKind,
    val byteOffset: Int,
    val structName: String,
    val fieldName: String?,
)

/** Ordered collector for [ParseDiagnostic]s produced during a COLLECT-mode parse. */
class ParseDiagnostics {
    private val _entries = mutableListOf<ParseDiagnostic>()
    val entries: List<ParseDiagnostic> get() = _entries.toList()

    fun record(diagnostic: ParseDiagnostic) {
        _entries.add(diagnostic)
    }

    fun isEmpty(): Boolean = _entries.isEmpty()
}
```

- [ ] **Step 4: Add the constructor parameters to Metaparser**

In `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt`, add the two defaulted parameters to the `Metaparser` class constructor, alongside the existing ones (do not reorder existing parameters — append):

```kotlin
    /** Reaction to recoverable failures. STRICT (default) preserves throw-on-first-error. */
    private val recoveryPolicy: RecoveryPolicy = RecoveryPolicy.STRICT,
    /** Collector used when [recoveryPolicy] is COLLECT. Ignored under STRICT. */
    private val diagnostics: ParseDiagnostics? = null,
```

- [ ] **Step 5: Add the recovery helper to Metaparser**

Add this private method inside the `Metaparser` class body:

```kotlin
    /**
     * Handles a recoverable failure. Under STRICT this rethrows, preserving historical
     * behaviour. Under COLLECT it records a diagnostic and returns, letting the caller
     * continue. Recovery is only offered where the stream position stays trustworthy —
     * a fixed-width field has already been consumed, so the cursor is still valid.
     */
    private fun recoverable(
        message: String,
        kind: HexplainErrorKind,
        byteOffset: Int,
        structName: String,
        fieldName: String?,
    ) {
        if (recoveryPolicy == RecoveryPolicy.STRICT || diagnostics == null) {
            throw HexplainParsingException(message, kind)
        }
        diagnostics.record(ParseDiagnostic(message, kind, byteOffset, structName, fieldName))
    }
```

- [ ] **Step 6: Route the fixed-value check through the helper**

In `parseStruct`, replace the fixed-value validation block (currently around lines 234–238):

```kotlin
            if (fieldDef.fixedValue != null && fieldValue is ByteArray) {
                if (!fieldValue.contentEquals(fieldDef.fixedValue)) {
                    throw HexplainParsingException("Validation failed for field '${fieldDef.name}'. Expected ${fieldDef.fixedValue.toHex()} but got ${fieldValue.toHex()}.")
                }
            }
```

with:

```kotlin
            if (fieldDef.fixedValue != null && fieldValue is ByteArray) {
                if (!fieldValue.contentEquals(fieldDef.fixedValue)) {
                    recoverable(
                        message = "Validation failed for field '${fieldDef.name}'. Expected ${fieldDef.fixedValue.toHex()} but got ${fieldValue.toHex()}.",
                        kind = HexplainErrorKind.VALIDATION,
                        byteOffset = baseOffset + fieldStartPos,
                        structName = structDef.name,
                        fieldName = fieldDef.name,
                    )
                }
            }
```

- [ ] **Step 7: Run the new tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.MetaparserRecoveryTest"`
Expected: PASS — both tests.

- [ ] **Step 8: Run the full suite to confirm nothing regressed**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS — all pre-existing tests still green (STRICT is the default, so behaviour is unchanged).

- [ ] **Step 9: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/metacodec/ParseDiagnostics.kt \
        core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserRecoveryTest.kt
git commit -m "feat(metacodec): add COLLECT recovery policy and parse diagnostics"
```

---

### Task 2: Field-read recovery for fixed-width fields

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (`parseStruct` field loop)
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserRecoveryTest.kt`

**Interfaces:**
- Consumes: `RecoveryPolicy`, `ParseDiagnostics`, `recoverable(...)` from Task 1.
- Produces: no new public types. Behaviour: under COLLECT, a `HexplainParsingException` thrown while reading a field whose `size` is statically known is recorded, the cursor is advanced past the field, and the loop continues; when the size is not statically known the struct aborts and returns its partial result.

- [ ] **Step 1: Write the failing test**

Append to `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserRecoveryTest.kt`, inside the class:

```kotlin
    /** Header with a bad enum-ish read in the middle: BAD has a fixed size so recovery can skip it. */
    private fun formatIRWithUnreadableMiddle(): FormatIR {
        val intType = DataTypeIR(name = "bddo:UInt24", baseType = BaseType.INTEGER, bitWidth = 24) // unsupported width -> throws
        val fields = listOf(
            FieldIR(name = "HEAD", dataType = bytesType, size = 2),
            FieldIR(name = "BAD", dataType = intType, size = 3),
            FieldIR(name = "TAIL", dataType = bytesType, size = 2),
        )
        val struct = StructIR(name = "t:Mid", fields = fields)
        return FormatIR(name = "test", rootStruct = "t:Mid", structs = mapOf("t:Mid" to struct))
    }

    @Test
    fun `COLLECT skips an unreadable fixed-width field and parses the next one`() {
        val diags = ParseDiagnostics()
        val parser = Metaparser(
            formatIR = formatIRWithUnreadableMiddle(),
            recoveryPolicy = RecoveryPolicy.COLLECT,
            diagnostics = diags,
        )

        @Suppress("UNCHECKED_CAST")
        val result = parser.parse("AA___ZZ".toByteArray()) as Map<String, Any>

        assertEquals(1, diags.entries.size)
        assertEquals("BAD", diags.entries[0].fieldName)
        assertEquals(2, diags.entries[0].byteOffset)
        assertEquals("AA", String(result["HEAD"] as ByteArray))
        assertEquals("ZZ", String(result["TAIL"] as ByteArray), "cursor must have skipped BAD's 3 bytes")
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.MetaparserRecoveryTest"`
Expected: FAIL — `HexplainParsingException: Unsupported integer bit width: 24` propagates out of `parse`.

- [ ] **Step 3: Wrap the field read in recovery**

In `parseStruct`, replace this block:

```kotlin
            val fieldStartPos = buffer.position()
            val fieldValue = readField(fieldDef, buffer, currentContext, parentContext, rootContext, structDef.endianness, structStartPos, bitCursor, baseOffset)
            fieldStart[fieldDef.name] = fieldStartPos
            fieldEnd[fieldDef.name] = buffer.position()
            result[fieldDef.name] = fieldValue
```

with:

```kotlin
            val fieldStartPos = buffer.position()
            val fieldValue = try {
                readField(fieldDef, buffer, currentContext, parentContext, rootContext, structDef.endianness, structStartPos, bitCursor, baseOffset)
            } catch (e: HexplainParsingException) {
                if (recoveryPolicy == RecoveryPolicy.STRICT || diagnostics == null) throw e
                diagnostics.record(
                    ParseDiagnostic(
                        message = e.message ?: "Failed to read field '${fieldDef.name}'.",
                        kind = e.kind,
                        byteOffset = baseOffset + fieldStartPos,
                        structName = structDef.name,
                        fieldName = fieldDef.name,
                    )
                )
                // Recovery is only sound when the field's width is known independently of its
                // content: reposition past it and carry on. Otherwise the cursor is untrustworthy,
                // so abandon this struct and return what was parsed so far.
                val width = fieldDef.size?.toInt()
                    ?: return finishStruct(result, buffer, outerLimit, regionEnd, structStartPos, baseOffset)
                buffer.position(minOf(fieldStartPos + width, buffer.limit()))
                continue
            }
            fieldStart[fieldDef.name] = fieldStartPos
            fieldEnd[fieldDef.name] = buffer.position()
            result[fieldDef.name] = fieldValue
```

- [ ] **Step 4: Extract the struct-finishing tail into a reusable method**

The early `return` above needs the same tail the normal path runs. In `parseStruct`, replace the closing block:

```kotlin
        // Restore the outer limit and, for a sized struct, advance past any trailing padding to the region end.
        buffer.limit(outerLimit)
        regionEnd?.let { buffer.position(it) }
        if (recordByteRange) {
            val endPos = buffer.position()
            result[BYTE_OFFSET_KEY] = baseOffset + structStartPos
            result[BYTE_LENGTH_KEY] = endPos - structStartPos
        }
        return result
```

with:

```kotlin
        return finishStruct(result, buffer, outerLimit, regionEnd, structStartPos, baseOffset)
```

and add this private method to the class:

```kotlin
    /**
     * Restores the outer buffer limit, advances past trailing padding for a sized struct,
     * and stamps the byte range. Shared by the normal completion path and by COLLECT-mode
     * early exit, so a partially parsed struct is finished consistently.
     */
    private fun finishStruct(
        result: MutableMap<String, Any>,
        buffer: ByteBuffer,
        outerLimit: Int,
        regionEnd: Int?,
        structStartPos: Int,
        baseOffset: Int,
    ): Map<String, Any> {
        buffer.limit(outerLimit)
        regionEnd?.let { buffer.position(it) }
        if (recordByteRange) {
            val endPos = buffer.position()
            result[BYTE_OFFSET_KEY] = baseOffset + structStartPos
            result[BYTE_LENGTH_KEY] = endPos - structStartPos
        }
        return result
    }
```

Note: `regionEnd` is declared `var regionEnd: Int? = null` in `parseStruct`; passing it by value at the call sites is correct because it is only read after the loop.

- [ ] **Step 5: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.MetaparserRecoveryTest"`
Expected: PASS — all three tests.

- [ ] **Step 6: Run the full suite**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS — no regressions.

- [ ] **Step 7: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserRecoveryTest.kt
git commit -m "feat(metacodec): recover from field-read failures at known field widths"
```

---

### Task 3: HEL quantifiers — `all()` and `any()`

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` (`evaluateFunction`)
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt` (grammar doc comment only)
- Test: `core/src/test/kotlin/io/hexplain/core/hel/HelQuantifierTest.kt`

**Interfaces:**
- Consumes: existing `HelEvaluator` constructor.
- Produces: HEL functions `all(collection, predicate)` and `any(collection, predicate)`. The predicate argument is **not** eagerly evaluated; it is re-evaluated once per element, with a `Map` element bound as the evaluation context (so bare field names resolve against it) and every element additionally bound to `self`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/hel/HelQuantifierTest.kt`:

```kotlin
package io.hexplain.core.hel

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Test

/** HEL quantifiers over dynamic-length repeats. */
class HelQuantifierTest {

    private fun parse(src: String): AstNode = HelParser(Lexer(src).tokenize()).parse()
    private fun eval(src: String, context: Map<String, Any> = emptyMap()): Any? =
        HelEvaluator(context).evaluate(parse(src))

    private val bands = mapOf(
        "BANDS" to listOf(
            mapOf("IREPBAND" to "R", "NLUTS" to 0L),
            mapOf("IREPBAND" to "G", "NLUTS" to 0L),
            mapOf("IREPBAND" to "B", "NLUTS" to 2L),
        ),
        "NUMS" to listOf(1L, 2L, 3L),
    )

    @Test fun `all is true when every struct element satisfies the predicate`() =
        assertEquals(true, eval("all(BANDS, IREPBAND != '')", bands))

    @Test fun `all is false when one struct element fails`() =
        assertEquals(false, eval("all(BANDS, NLUTS == 0)", bands))

    @Test fun `any is true when one struct element satisfies`() =
        assertEquals(true, eval("any(BANDS, NLUTS > 0)", bands))

    @Test fun `any is false when none satisfy`() =
        assertEquals(false, eval("any(BANDS, IREPBAND == 'X')", bands))

    @Test fun `scalar elements bind to self`() {
        assertEquals(true, eval("all(NUMS, self > 0)", bands))
        assertEquals(false, eval("all(NUMS, self > 1)", bands))
    }

    @Test fun `all is vacuously true and any vacuously false on an empty collection`() {
        val empty = mapOf("E" to emptyList<Any>())
        assertEquals(true, eval("all(E, self > 0)", empty))
        assertEquals(false, eval("any(E, self > 0)", empty))
    }

    @Test fun `quantifiers require an array first argument`() {
        val e = assertThrows<HelEvaluationException> { eval("all(NOPE, self > 0)", bands) }
        assertTrue(e.message!!.contains("requires an array"))
    }

    @Test fun `predicate must evaluate to a boolean`() {
        val e = assertThrows<HelEvaluationException> { eval("all(NUMS, self + 1)", bands) }
        assertTrue(e.message!!.contains("boolean"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelQuantifierTest"`
Expected: FAIL — `HelEvaluationException: Unknown function 'all'`.

- [ ] **Step 3: Implement lazy quantifier dispatch**

In `HelEvaluator.evaluateFunction`, insert this block as the **first** statement of the method, before `fun arg0()`:

```kotlin
        // Quantifiers must not eagerly evaluate their predicate: it is re-evaluated once per
        // element, against that element. Handled ahead of the general argument evaluation below.
        if (node.name == "all" || node.name == "any") {
            if (node.args.size != 2) {
                throw HelEvaluationException("${node.name}() takes exactly 2 arguments (collection, predicate)")
            }
            val collection = evaluate(node.args[0]) as? List<*>
                ?: throw HelEvaluationException("${node.name}() requires an array as its first argument, got ${typeName(evaluate(node.args[0]))}")
            val predicate = node.args[1]
            val wantAll = node.name == "all"
            for (element in collection) {
                @Suppress("UNCHECKED_CAST")
                val elementContext = element as? Map<String, Any> ?: context
                val sub = HelEvaluator(
                    context = elementContext,
                    parentContext = context,
                    rootContext = rootContext,
                    streamContext = streamContext,
                    selfContext = element,
                )
                val verdict = sub.evaluate(predicate) as? Boolean
                    ?: throw HelEvaluationException("${node.name}() predicate must evaluate to a boolean")
                if (wantAll && !verdict) return false
                if (!wantAll && verdict) return true
            }
            return wantAll
        }
```

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelQuantifierTest"`
Expected: PASS — all eight tests.

- [ ] **Step 5: Update the grammar doc comment**

In `HelParser.kt`, change the functions line of the header comment from:

```
 *  - functions: sizeof(x), len(x), count(x), eof()
```

to:

```
 *  - functions: sizeof(x), len(x), count(x), eof()
 *  - quantifiers: all(collection, predicate), any(collection, predicate)
 *      The predicate is evaluated once per element: a struct element becomes the evaluation
 *      context (bare field names resolve against it) and every element is bound to `self`.
```

- [ ] **Step 6: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt \
        core/src/test/kotlin/io/hexplain/core/hel/HelQuantifierTest.kt
git commit -m "feat(hel): add all()/any() quantifiers with lazy predicate evaluation"
```

---

### Task 4: HEL string and pattern functions

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` (`evaluateFunction`)
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt` (grammar doc comment only)
- Test: `core/src/test/kotlin/io/hexplain/core/hel/HelStringFunctionTest.kt`

**Interfaces:**
- Consumes: Task 3's `evaluateFunction` structure.
- Produces: HEL functions `matches(s, regex) -> Boolean`, `substr(s, start, length) -> String`, `startsWith(s, prefix) -> Boolean`, `trim(s) -> String`. All accept `String` or `ByteArray` (decoded UTF-8) as `s`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/hel/HelStringFunctionTest.kt`:

```kotlin
package io.hexplain.core.hel

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/** HEL string/pattern predicates used by field-syntax conformance rules. */
class HelStringFunctionTest {

    private fun parse(src: String): AstNode = HelParser(Lexer(src).tokenize()).parse()
    private fun eval(src: String, context: Map<String, Any> = emptyMap()): Any? =
        HelEvaluator(context).evaluate(parse(src))

    private val ctx = mapOf(
        "FDT" to "20260801123015",
        "BAD" to "21JAN01123015",
        "ICORDS" to "G",
        "PAD" to "  ABC  ",
        "RAW" to "NITF".toByteArray(),
    )

    private val datePattern = "'[0-9]{14}'"

    @Test fun `matches accepts a well-formed CCYYMMDDhhmmss value`() =
        assertEquals(true, eval("matches(FDT, $datePattern)", ctx))

    @Test fun `matches rejects irregular date content`() =
        assertEquals(false, eval("matches(BAD, $datePattern)", ctx))

    @Test fun `matches is anchored to the whole value`() =
        assertEquals(false, eval("matches('X20260801123015', $datePattern)", ctx))

    @Test fun `matches decodes a bytes value`() =
        assertEquals(true, eval("matches(RAW, 'NITF')", ctx))

    @Test fun `substr extracts a fixed slice`() =
        assertEquals("2026", eval("substr(FDT, 0, 4)", ctx))

    @Test fun `substr clamps a length that runs past the end`() =
        assertEquals("15", eval("substr(FDT, 12, 9)", ctx))

    @Test fun `substr rejects a negative start`() {
        val e = assertThrows<HelEvaluationException> { eval("substr(FDT, -1, 2)", ctx) }
        assertTrue(e.message!!.contains("negative"))
    }

    @Test fun `startsWith tests a prefix`() {
        assertEquals(true, eval("startsWith(FDT, '2026')", ctx))
        assertEquals(false, eval("startsWith(FDT, '1999')", ctx))
    }

    @Test fun `trim removes surrounding whitespace`() =
        assertEquals("ABC", eval("trim(PAD)", ctx))

    @Test fun `unknown function still raises`() {
        val e = assertThrows<HelEvaluationException> { eval("nope('x')", ctx) }
        assertTrue(e.message!!.contains("Unknown function"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelStringFunctionTest"`
Expected: FAIL — `Unknown function 'matches'`.

- [ ] **Step 3: Add a string-coercion helper**

In `HelEvaluator.kt`, add to the `// ---- coercion / helpers ----` section:

```kotlin
    /** Coerces a field value to text for string predicates; bytes decode as UTF-8. */
    private fun stringOperand(value: Any?, fn: String): String = when (value) {
        is String -> value
        is ByteArray -> String(value, UTF_8)
        else -> throw HelEvaluationException("$fn() requires a string or bytes value, got ${typeName(value)}")
    }

    /** Coerces to a non-negative Int index for slicing. */
    private fun indexOperand(value: Any?, fn: String, what: String): Int {
        val n = (value as? Number)?.toLong()
            ?: throw HelEvaluationException("$fn() $what must be an integer, got ${typeName(value)}")
        if (n < 0) throw HelEvaluationException("$fn() $what must not be negative (got $n)")
        return n.toInt()
    }
```

- [ ] **Step 4: Add the functions to the dispatch**

In `evaluateFunction`, add these branches to the `when (node.name)` block, immediately before the final `else ->`:

```kotlin
            "matches" -> {
                val s = stringOperand(evaluate(node.args[0]), "matches")
                val pattern = evaluate(node.args[1]) as? String
                    ?: throw HelEvaluationException("matches() requires a string pattern as its second argument")
                // Anchored: a conformance rule asks whether the whole field matches, never a substring.
                Regex(pattern).matches(s)
            }
            "substr" -> {
                val s = stringOperand(evaluate(node.args[0]), "substr")
                val start = indexOperand(evaluate(node.args[1]), "substr", "start")
                val length = indexOperand(evaluate(node.args[2]), "substr", "length")
                if (start > s.length) "" else s.substring(start, minOf(start + length, s.length))
            }
            "startsWith" -> {
                val s = stringOperand(evaluate(node.args[0]), "startsWith")
                val prefix = stringOperand(evaluate(node.args[1]), "startsWith")
                s.startsWith(prefix)
            }
            "trim" -> stringOperand(evaluate(node.args[0]), "trim").trim()
```

- [ ] **Step 5: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelStringFunctionTest"`
Expected: PASS — all ten tests.

- [ ] **Step 6: Update the grammar doc comment**

In `HelParser.kt`, extend the functions line:

```
 *  - string functions: matches(s, regex) [anchored], substr(s, start, len), startsWith(s, prefix), trim(s)
```

- [ ] **Step 7: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt \
        core/src/test/kotlin/io/hexplain/core/hel/HelStringFunctionTest.kt
git commit -m "feat(hel): add matches/substr/startsWith/trim string predicates"
```

---

### Task 5: HEL temporal functions

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` (constructor + `evaluateFunction`)
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt` (grammar doc comment only)
- Test: `core/src/test/kotlin/io/hexplain/core/hel/HelTemporalTest.kt`

**Interfaces:**
- Consumes: Task 4's helpers (`stringOperand`).
- Produces: `HelEvaluator` gains constructor parameter `evaluationInstant: Long? = null` (epoch seconds UTC). HEL functions `datetime(s, fmt) -> Long` (epoch seconds; `null` when unparseable) and `evaluationInstant() -> Long`. Format string uses `java.time.format.DateTimeFormatter` patterns.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/hel/HelTemporalTest.kt`:

```kotlin
package io.hexplain.core.hel

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Test

/** HEL temporal comparison: segment ordering and future-date rules. */
class HelTemporalTest {

    private fun parse(src: String): AstNode = HelParser(Lexer(src).tokenize()).parse()
    private fun eval(
        src: String,
        context: Map<String, Any> = emptyMap(),
        instant: Long? = null,
    ): Any? = HelEvaluator(context, evaluationInstant = instant).evaluate(parse(src))

    private val fmt = "'yyyyMMddHHmmss'"
    private val ctx = mapOf(
        "FDT" to "20260801120000",
        "IDATIM" to "20260801130000",   // image AFTER file - a discrepancy
        "TXTDT" to "20260801110000",    // text BEFORE file - fine
        "JUNK" to "21JAN01123015",
    )

    // 2026-08-01T12:30:00Z
    private val runInstant = 1785587400L

    @Test fun `datetime yields comparable epoch seconds`() =
        assertEquals(1785585600L, eval("datetime(FDT, $fmt)", ctx))

    @Test fun `image after file is detectable by ordering`() =
        assertEquals(true, eval("datetime(IDATIM, $fmt) > datetime(FDT, $fmt)", ctx))

    @Test fun `text before file compares correctly`() =
        assertEquals(true, eval("datetime(TXTDT, $fmt) < datetime(FDT, $fmt)", ctx))

    @Test fun `unparseable content yields null rather than throwing`() =
        assertNull(eval("datetime(JUNK, $fmt)", ctx))

    @Test fun `a null datetime makes an ordering comparison false`() =
        assertEquals(false, eval("datetime(JUNK, $fmt) > datetime(FDT, $fmt)", ctx))

    @Test fun `evaluationInstant returns the run parameter`() =
        assertEquals(runInstant, eval("evaluationInstant()", ctx, runInstant))

    @Test fun `a future file date is detectable against the run instant`() {
        assertEquals(false, eval("datetime(FDT, $fmt) > evaluationInstant()", ctx, runInstant))
        val future = mapOf("FDT" to "20990101000000")
        assertEquals(true, eval("datetime(FDT, $fmt) > evaluationInstant()", future, runInstant))
    }

    @Test fun `evaluationInstant without a run parameter is an error not a wall-clock read`() {
        val e = assertThrows<HelEvaluationException> { eval("evaluationInstant()", ctx) }
        assertTrue(e.message!!.contains("run parameter"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelTemporalTest"`
Expected: FAIL — compilation error, no `evaluationInstant` parameter.

- [ ] **Step 3: Add the constructor parameter**

In `HelEvaluator.kt`, append to the constructor parameter list (after `selfContext`):

```kotlin
    /**
     * Reference instant (epoch seconds, UTC) for temporal rules such as "date is in the future".
     * Supplied as a run parameter rather than read from the wall clock, so a conformance run is
     * reproducible: re-running the evidence bundle must give identical findings.
     */
    private val evaluationInstant: Long? = null,
```

Add the import at the top of the file:

```kotlin
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
```

- [ ] **Step 4: Add the functions to the dispatch**

In `evaluateFunction`, add before the final `else ->`:

```kotlin
            "datetime" -> {
                val text = stringOperand(evaluate(node.args[0]), "datetime").trim()
                val pattern = evaluate(node.args[1]) as? String
                    ?: throw HelEvaluationException("datetime() requires a string format as its second argument")
                // Unparseable content is a finding for a *syntax* rule to report, not an evaluation
                // failure: returning null lets ordering comparisons stay false rather than abort.
                try {
                    LocalDateTime.parse(text, DateTimeFormatter.ofPattern(pattern))
                        .toEpochSecond(ZoneOffset.UTC)
                } catch (_: DateTimeParseException) {
                    return@evaluateFunction null
                }
            }
            "evaluationInstant" -> evaluationInstant
                ?: throw HelEvaluationException("evaluationInstant() requires the reference instant run parameter")
```

Because one branch now returns `null`, change the `evaluateFunction` signature from:

```kotlin
    private fun evaluateFunction(node: FunctionCallNode): Any {
```

to:

```kotlin
    private fun evaluateFunction(node: FunctionCallNode): Any? {
```

- [ ] **Step 4b: Forward the instant into quantified predicates**

The quantifier sub-evaluator added in Task 3 constructs a fresh `HelEvaluator` and would otherwise drop the new parameter, so `all(BANDS, datetime(D, 'yyyy') > evaluationInstant())` would fail inside a quantifier while working outside one. Update its construction in `evaluateFunction` to forward it:

```kotlin
                val sub = HelEvaluator(
                    context = elementContext,
                    parentContext = context,
                    rootContext = rootContext,
                    streamContext = streamContext,
                    selfContext = element,
                    evaluationInstant = evaluationInstant,
                )
```

Add this regression test to `HelTemporalTest`:

```kotlin
    @Test fun `evaluationInstant is available inside a quantified predicate`() {
        val ctx = mapOf("ROWS" to listOf(mapOf("D" to "20990101000000"), mapOf("D" to "20200101000000")))
        assertEquals(true, eval("any(ROWS, datetime(D, $fmt) > evaluationInstant())", ctx, runInstant))
        assertEquals(false, eval("all(ROWS, datetime(D, $fmt) > evaluationInstant())", ctx, runInstant))
    }
```

- [ ] **Step 5: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelTemporalTest"`
Expected: PASS — all nine tests, including the quantified-predicate regression test.

- [ ] **Step 6: Update the grammar doc comment**

In `HelParser.kt`, add:

```
 *  - temporal: datetime(s, fmt) -> epoch seconds or null; evaluationInstant() -> run parameter
```

- [ ] **Step 7: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt \
        core/src/test/kotlin/io/hexplain/core/hel/HelTemporalTest.kt
git commit -m "feat(hel): add datetime() and evaluationInstant() temporal functions"
```

---

### Task 6: HEL geometry functions

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/hel/HelGeometry.kt`
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` (`evaluateFunction`)
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt` (grammar doc comment only)
- Test: `core/src/test/kotlin/io/hexplain/core/hel/HelGeometryTest.kt`

**Interfaces:**
- Consumes: nothing from earlier tasks beyond the dispatch structure.
- Produces: `object HelGeometry { fun ringOrientation(xs: List<Double>, ys: List<Double>): Long; fun isSelfIntersecting(xs: List<Double>, ys: List<Double>): Boolean }`. HEL functions `ringOrientation(xs, ys) -> Long` (`1` counterclockwise, `-1` clockwise, `0` degenerate) and `isSelfIntersecting(xs, ys) -> Boolean`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/hel/HelGeometryTest.kt`:

```kotlin
package io.hexplain.core.hel

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Test

/** IGEOLO footprint sanity: winding direction and bowtie detection. */
class HelGeometryTest {

    private fun parse(src: String): AstNode = HelParser(Lexer(src).tokenize()).parse()
    private fun eval(src: String, context: Map<String, Any> = emptyMap()): Any? =
        HelEvaluator(context).evaluate(parse(src))

    // Corner order as NITF IGEOLO records it, clockwise from upper-left in image space.
    private val clockwise = mapOf(
        "LON" to listOf(0.0, 1.0, 1.0, 0.0),
        "LAT" to listOf(1.0, 1.0, 0.0, 0.0),
    )
    // (0,0) -> (1,0) -> (1,1) -> (0,1): right, up, left, down. A reversal of the
    // clockwise ring, not a rotation of it — rotation preserves winding.
    private val counterClockwise = mapOf(
        "LON" to listOf(0.0, 1.0, 1.0, 0.0),
        "LAT" to listOf(0.0, 0.0, 1.0, 1.0),
    )
    private val bowtie = mapOf(
        "LON" to listOf(0.0, 1.0, 0.0, 1.0),
        "LAT" to listOf(0.0, 0.0, 1.0, 1.0),
    )
    private val degenerateLine = mapOf(
        "LON" to listOf(0.0, 1.0, 2.0, 3.0),
        "LAT" to listOf(0.0, 0.0, 0.0, 0.0),
    )

    @Test fun `clockwise ring reports -1`() =
        assertEquals(-1L, eval("ringOrientation(LON, LAT)", clockwise))

    @Test fun `counterclockwise ring reports 1`() =
        assertEquals(1L, eval("ringOrientation(LON, LAT)", counterClockwise))

    @Test fun `collinear ring reports 0`() =
        assertEquals(0L, eval("ringOrientation(LON, LAT)", degenerateLine))

    @Test fun `a simple quad is not self-intersecting`() {
        assertEquals(false, eval("isSelfIntersecting(LON, LAT)", clockwise))
        assertEquals(false, eval("isSelfIntersecting(LON, LAT)", counterClockwise))
    }

    @Test fun `a bowtie is self-intersecting`() =
        assertEquals(true, eval("isSelfIntersecting(LON, LAT)", bowtie))

    @Test fun `mismatched coordinate array lengths are an error`() {
        val bad = mapOf("LON" to listOf(0.0, 1.0), "LAT" to listOf(0.0))
        val e = assertThrows<HelEvaluationException> { eval("ringOrientation(LON, LAT)", bad) }
        assertTrue(e.message!!.contains("same length"))
    }

    @Test fun `integer coordinates are accepted`() {
        val ints = mapOf("LON" to listOf(0L, 1L, 1L, 0L), "LAT" to listOf(1L, 1L, 0L, 0L))
        assertEquals(-1L, eval("ringOrientation(LON, LAT)", ints))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelGeometryTest"`
Expected: FAIL — `Unknown function 'ringOrientation'`.

- [ ] **Step 3: Implement the geometry primitives**

Create `core/src/main/kotlin/io/hexplain/core/hel/HelGeometry.kt`:

```kotlin
package io.hexplain.core.hel

/**
 * Planar geometry helpers backing the HEL functions used by footprint conformance rules
 * (e.g. NITF IGEOLO corner sanity). Coordinates are treated as planar; for the small
 * quadrilaterals IGEOLO describes this is the same answer a spherical test would give,
 * and it keeps the rule reviewable against the standard text.
 */
object HelGeometry {

    /** Signed-area winding: 1 counterclockwise, -1 clockwise, 0 degenerate (collinear or empty). */
    fun ringOrientation(xs: List<Double>, ys: List<Double>): Long {
        val n = xs.size
        if (n < 3) return 0L
        // Shoelace: sum of (x2-x1)(y2+y1). Positive sum means clockwise in a y-up frame.
        var sum = 0.0
        for (i in 0 until n) {
            val j = (i + 1) % n
            sum += (xs[j] - xs[i]) * (ys[j] + ys[i])
        }
        return when {
            sum > 0.0 -> -1L
            sum < 0.0 -> 1L
            else -> 0L
        }
    }

    /** True when any pair of non-adjacent edges of the closed ring crosses (a "bowtie"). */
    fun isSelfIntersecting(xs: List<Double>, ys: List<Double>): Boolean {
        val n = xs.size
        if (n < 4) return false
        for (i in 0 until n) {
            for (j in i + 1 until n) {
                // Skip adjacent edges (they legitimately share a vertex), including the
                // wrap-around pair of the first and last edge.
                if (j == i + 1) continue
                if (i == 0 && j == n - 1) continue
                if (segmentsCross(
                        xs[i], ys[i], xs[(i + 1) % n], ys[(i + 1) % n],
                        xs[j], ys[j], xs[(j + 1) % n], ys[(j + 1) % n],
                    )
                ) return true
            }
        }
        return false
    }

    private fun segmentsCross(
        ax: Double, ay: Double, bx: Double, by: Double,
        cx: Double, cy: Double, dx: Double, dy: Double,
    ): Boolean {
        val d1 = cross(cx, cy, dx, dy, ax, ay)
        val d2 = cross(cx, cy, dx, dy, bx, by)
        val d3 = cross(ax, ay, bx, by, cx, cy)
        val d4 = cross(ax, ay, bx, by, dx, dy)
        if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
            ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))
        ) return true
        // Collinear touching cases are not treated as crossings: a degenerate footprint is
        // reported by ringOrientation() == 0, which is a distinct requirement.
        return false
    }

    /** Cross product of (p2-p1) x (p3-p1); sign gives the turn direction. */
    private fun cross(
        p1x: Double, p1y: Double, p2x: Double, p2y: Double, p3x: Double, p3y: Double,
    ): Double = (p2x - p1x) * (p3y - p1y) - (p2y - p1y) * (p3x - p1x)
}
```

- [ ] **Step 4: Add a coordinate-array coercion helper**

In `HelEvaluator.kt`, add to the helpers section:

```kotlin
    /** Coerces a HEL array of numbers to Doubles for geometry functions. */
    private fun coordinateArray(value: Any?, fn: String, which: String): List<Double> {
        val list = value as? List<*>
            ?: throw HelEvaluationException("$fn() requires an array for $which, got ${typeName(value)}")
        return list.map {
            (it as? Number)?.toDouble()
                ?: throw HelEvaluationException("$fn() $which must contain only numbers, got ${typeName(it)}")
        }
    }
```

- [ ] **Step 5: Add the functions to the dispatch**

In `evaluateFunction`, add before the final `else ->`:

```kotlin
            "ringOrientation", "isSelfIntersecting" -> {
                val xs = coordinateArray(evaluate(node.args[0]), node.name, "the first argument")
                val ys = coordinateArray(evaluate(node.args[1]), node.name, "the second argument")
                if (xs.size != ys.size) {
                    throw HelEvaluationException("${node.name}() coordinate arrays must be the same length (got ${xs.size} and ${ys.size})")
                }
                if (node.name == "ringOrientation") HelGeometry.ringOrientation(xs, ys)
                else HelGeometry.isSelfIntersecting(xs, ys)
            }
```

- [ ] **Step 6: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelGeometryTest"`
Expected: PASS — all seven tests.

- [ ] **Step 7: Update the grammar doc comment**

In `HelParser.kt`, add:

```
 *  - geometry: ringOrientation(xs, ys) -> 1 CCW / -1 CW / 0 degenerate; isSelfIntersecting(xs, ys)
```

- [ ] **Step 8: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/hel/HelGeometry.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt \
        core/src/test/kotlin/io/hexplain/core/hel/HelGeometryTest.kt
git commit -m "feat(hel): add ringOrientation and isSelfIntersecting geometry predicates"
```

---

### Task 7: HEL register lookup

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/conformance/RegisterProvider.kt`
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` (constructor + `evaluateFunction`)
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt` (grammar doc comment only)
- Test: `core/src/test/kotlin/io/hexplain/core/conformance/SkosRegisterProviderTest.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/hel/HelRegisterTest.kt`

**Interfaces:**
- Consumes: Task 4's `stringOperand`.
- Produces: `interface RegisterProvider { fun contains(schemeUri: String, value: String): Boolean }`; `class SkosRegisterProvider(model: org.apache.jena.rdf.model.Model) : RegisterProvider`; `class MapRegisterProvider(entries: Map<String, Set<String>>) : RegisterProvider`. `HelEvaluator` gains constructor parameter `registerProvider: RegisterProvider? = null`. HEL function `inRegister(value, schemeUri) -> Boolean`.

- [ ] **Step 1: Write the failing provider test**

Create `core/src/test/kotlin/io/hexplain/core/conformance/SkosRegisterProviderTest.kt`:

```kotlin
package io.hexplain.core.conformance

import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.io.StringReader

/** SKOS-backed register membership, used for TRE tags, DES ids and country codes. */
class SkosRegisterProviderTest {

    private val turtle = """
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix ex:   <https://example.org/genc#> .

        ex:Scheme a skos:ConceptScheme .
        ex:USA a skos:Concept ; skos:inScheme ex:Scheme ; skos:notation "USA" .
        ex:GBR a skos:Concept ; skos:inScheme ex:Scheme ; skos:notation "GBR" .
        ex:Retired a skos:Concept ; skos:notation "XXX" .
    """.trimIndent()

    private fun provider(): SkosRegisterProvider {
        val model = ModelFactory.createDefaultModel()
        RDFDataMgr.read(model, StringReader(turtle), null, Lang.TTL)
        return SkosRegisterProvider(model)
    }

    @Test fun `a notation in the scheme is a member`() {
        val p = provider()
        assertTrue(p.contains("https://example.org/genc#Scheme", "USA"))
        assertTrue(p.contains("https://example.org/genc#Scheme", "GBR"))
    }

    @Test fun `a notation outside the scheme is not a member`() =
        assertFalse(provider().contains("https://example.org/genc#Scheme", "XXX"))

    @Test fun `an unknown notation is not a member`() =
        assertFalse(provider().contains("https://example.org/genc#Scheme", "ZZZ"))

    @Test fun `lookup is whitespace-insensitive because fixed-width fields are space padded`() =
        assertTrue(provider().contains("https://example.org/genc#Scheme", "USA  "))

    @Test fun `an unknown scheme is not a member`() =
        assertFalse(provider().contains("https://example.org/nope#Scheme", "USA"))
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.SkosRegisterProviderTest"`
Expected: FAIL — compilation error, `SkosRegisterProvider` unresolved.

- [ ] **Step 3: Implement the providers**

Create `core/src/main/kotlin/io/hexplain/core/conformance/RegisterProvider.kt`:

```kotlin
package io.hexplain.core.conformance

import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ResourceFactory

/**
 * Membership test against a controlled register (a SKOS concept scheme).
 *
 * Conformance rules ask whether a field value is a *registered* value — a registered TRE
 * tag, a registered DES identifier, a GENC trigraph. Registers are external, versioned
 * artifacts, so they are supplied to the engine rather than compiled into it.
 */
interface RegisterProvider {
    /** True when [value] is a notation of a concept in the scheme identified by [schemeUri]. */
    fun contains(schemeUri: String, value: String): Boolean
}

/** Reads membership from an in-memory SKOS graph. */
class SkosRegisterProvider(model: Model) : RegisterProvider {

    private val notationsByScheme: Map<String, Set<String>> = buildIndex(model)

    override fun contains(schemeUri: String, value: String): Boolean =
        notationsByScheme[schemeUri]?.contains(value.trim()) == true

    private fun buildIndex(model: Model): Map<String, Set<String>> {
        val inScheme = ResourceFactory.createProperty(SKOS_NS + "inScheme")
        val notation = ResourceFactory.createProperty(SKOS_NS + "notation")
        val index = mutableMapOf<String, MutableSet<String>>()
        val statements = model.listStatements(null, inScheme, null as org.apache.jena.rdf.model.RDFNode?)
        while (statements.hasNext()) {
            val statement = statements.nextStatement()
            val schemeUri = statement.`object`.asResource().uri ?: continue
            val concept = statement.subject
            val notations = concept.listProperties(notation)
            while (notations.hasNext()) {
                val text = notations.nextStatement().`object`.asLiteral().string.trim()
                index.getOrPut(schemeUri) { mutableSetOf() }.add(text)
            }
        }
        return index
    }

    companion object {
        const val SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
    }
}

/** In-memory provider for tests and for registers that are not yet published as SKOS. */
class MapRegisterProvider(private val entries: Map<String, Set<String>>) : RegisterProvider {
    override fun contains(schemeUri: String, value: String): Boolean =
        entries[schemeUri]?.contains(value.trim()) == true
}
```

- [ ] **Step 4: Run the provider test**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.SkosRegisterProviderTest"`
Expected: PASS — all five tests.

- [ ] **Step 5: Write the failing HEL integration test**

Create `core/src/test/kotlin/io/hexplain/core/hel/HelRegisterTest.kt`:

```kotlin
package io.hexplain.core.hel

import io.hexplain.core.conformance.MapRegisterProvider
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Test

/** inRegister() over a controlled vocabulary, as used for TRE tags and country codes. */
class HelRegisterTest {

    private val scheme = "https://example.org/tre#Scheme"
    private val provider = MapRegisterProvider(mapOf(scheme to setOf("BLOCKA", "RPC00B")))

    private fun parse(src: String): AstNode = HelParser(Lexer(src).tokenize()).parse()
    private fun eval(src: String, context: Map<String, Any> = emptyMap(), withProvider: Boolean = true): Any? =
        HelEvaluator(context, registerProvider = if (withProvider) provider else null).evaluate(parse(src))

    private val ctx = mapOf(
        "CETAG" to "BLOCKA",
        "PADDED" to "RPC00B ",
        "BOGUS" to "NOTATRE",
        "TAGS" to listOf(mapOf("CETAG" to "BLOCKA"), mapOf("CETAG" to "RPC00B")),
        "MIXED" to listOf(mapOf("CETAG" to "BLOCKA"), mapOf("CETAG" to "NOTATRE")),
    )

    @Test fun `a registered tag is in the register`() =
        assertEquals(true, eval("inRegister(CETAG, '$scheme')", ctx))

    @Test fun `a space-padded fixed-width tag still resolves`() =
        assertEquals(true, eval("inRegister(PADDED, '$scheme')", ctx))

    @Test fun `an unregistered tag is not in the register`() =
        assertEquals(false, eval("inRegister(BOGUS, '$scheme')", ctx))

    @Test fun `inRegister composes with quantifiers`() {
        assertEquals(true, eval("all(TAGS, inRegister(CETAG, '$scheme'))", ctx))
        assertEquals(false, eval("all(MIXED, inRegister(CETAG, '$scheme'))", ctx))
        assertEquals(true, eval("any(MIXED, inRegister(CETAG, '$scheme'))", ctx))
    }

    @Test fun `inRegister without a provider is an error`() {
        val e = assertThrows<HelEvaluationException> { eval("inRegister(CETAG, '$scheme')", ctx, withProvider = false) }
        assertTrue(e.message!!.contains("register provider"))
    }
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelRegisterTest"`
Expected: FAIL — compilation error, no `registerProvider` parameter.

- [ ] **Step 7: Wire the provider into the evaluator**

In `HelEvaluator.kt`, append to the constructor parameter list (after `evaluationInstant`):

```kotlin
    /** Controlled-register membership source for inRegister(); absent outside conformance runs. */
    private val registerProvider: io.hexplain.core.conformance.RegisterProvider? = null,
```

In `evaluateFunction`, add before the final `else ->`:

```kotlin
            "inRegister" -> {
                val provider = registerProvider
                    ?: throw HelEvaluationException("inRegister() requires a register provider")
                val value = stringOperand(evaluate(node.args[0]), "inRegister")
                val schemeUri = evaluate(node.args[1]) as? String
                    ?: throw HelEvaluationException("inRegister() requires a scheme URI string as its second argument")
                provider.contains(schemeUri, value)
            }
```

In the quantifier block, the sub-evaluator must also forward the register provider (Task 5 Step 4b already added `evaluationInstant`). Update its construction to:

```kotlin
                val sub = HelEvaluator(
                    context = elementContext,
                    parentContext = context,
                    rootContext = rootContext,
                    streamContext = streamContext,
                    selfContext = element,
                    evaluationInstant = evaluationInstant,
                    registerProvider = registerProvider,
                )
```

- [ ] **Step 8: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelRegisterTest"`
Expected: PASS — all five tests, including the quantifier composition case.

- [ ] **Step 9: Update the grammar doc comment**

In `HelParser.kt`, add:

```
 *  - registers: inRegister(value, schemeUri) -> membership in a SKOS controlled register
```

- [ ] **Step 10: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/conformance/RegisterProvider.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt \
        core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt \
        core/src/test/kotlin/io/hexplain/core/conformance/SkosRegisterProviderTest.kt \
        core/src/test/kotlin/io/hexplain/core/hel/HelRegisterTest.kt
git commit -m "feat(hel): add inRegister() backed by SKOS controlled registers"
```

---

### Task 8: `hx-req` requirements vocabulary

**Repo:** `hexplain.io`

**Files:**
- Create: `specification/req/req.ttl`
- Create: `specification/req/shapes.ttl`
- Test: `specification/req/test/req-valid.ttl`
- Test: `specification/req/test/req-invalid.ttl`

**Interfaces:**
- Consumes: nothing.
- Produces: namespace `https://hexplain.io/ns/req#` with class `req:Requirement`; properties `req:requirementId` (xsd:string, exactly 1), `req:fromStandard` (xsd:string, exactly 1), `req:statement` (xsd:string, exactly 1), `req:discrepancyType` (one of `req:Syntactic`, `req:Semantic`, `req:Functional`, exactly 1), `req:appliesToVersion` (xsd:string, 0..n).

- [ ] **Step 1: Write the vocabulary**

Create `specification/req/req.ttl`:

```turtle
@prefix :        <https://hexplain.io/ns/req#> .
@prefix req:     <https://hexplain.io/ns/req#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .

<https://hexplain.io/ns/req> a owl:Ontology ;
    rdfs:label "Hexplain Requirements Vocabulary" ;
    owl:versionInfo "1.0" ;
    rdfs:comment """Identifies requirements stated by an external standards document, so that
executable conformance constraints can cite them. Format-agnostic: it describes what documents
demand, independent of any binary format description.""" .

# --- Classes ---
:Requirement a owl:Class ; rdfs:label "Requirement" ;
    rdfs:comment "A single normative requirement drawn from a standards document." ;
    rdfs:isDefinedBy <https://hexplain.io/ns/req> .

:DiscrepancyType a owl:Class ; rdfs:label "Discrepancy Type" ;
    rdfs:comment "The class of defect that violating a requirement produces." ;
    rdfs:isDefinedBy <https://hexplain.io/ns/req> .

# --- Controlled individuals ---
# Definitions track the discrepancy types used by conformance test reporting: a violation
# impairs interpretability (syntactic), understandability (semantic), or usability (functional).
:Syntactic a :DiscrepancyType ; rdfs:label "Syntactic" ;
    rdfs:comment "Impacts interpretability of the data: violates format or compression specifications." .
:Semantic a :DiscrepancyType ; rdfs:label "Semantic" ;
    rdfs:comment "Impacts understandability of the data: violates data dictionaries or content specifications." .
:Functional a :DiscrepancyType ; rdfs:label "Functional" ;
    rdfs:comment "Impacts usability of the data: violates community or system documentation and data models." .

# --- Properties ---
:requirementId a owl:DatatypeProperty ; rdfs:label "requirement id" ;
    rdfs:comment "The identifier the source standard uses, verbatim (e.g. 'JBP-2021.2-002')." ;
    rdfs:range xsd:string .

:fromStandard a owl:DatatypeProperty ; rdfs:label "from standard" ;
    rdfs:comment "Source document and edition (e.g. 'MIL-STD-2500C, 01 May 2006')." ;
    rdfs:range xsd:string .

:statement a owl:DatatypeProperty ; rdfs:label "statement" ;
    rdfs:comment "The requirement text, quoted verbatim from the source." ;
    rdfs:range xsd:string .

:discrepancyType a owl:ObjectProperty ; rdfs:label "discrepancy type" ;
    rdfs:comment "The class of defect a violation produces." ;
    rdfs:range :DiscrepancyType .

:appliesToVersion a owl:DatatypeProperty ; rdfs:label "applies to version" ;
    rdfs:comment "A format version the requirement governs (e.g. 'NITF 2.1'). Absent means all." ;
    rdfs:range xsd:string .
```

- [ ] **Step 2: Write the SHACL shapes**

Create `specification/req/shapes.ttl`:

```turtle
@prefix :     <https://hexplain.io/ns/req#> .
@prefix req:  <https://hexplain.io/ns/req#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

:RequirementShape a sh:NodeShape ;
    sh:targetClass req:Requirement ;
    rdfs:label "Requirement shape" ;
    sh:property [
        sh:path req:requirementId ;
        sh:datatype xsd:string ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:minLength 1 ;
        sh:message "A Requirement needs exactly one non-empty req:requirementId." ;
    ] ;
    sh:property [
        sh:path req:fromStandard ;
        sh:datatype xsd:string ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:message "A Requirement needs exactly one req:fromStandard." ;
    ] ;
    sh:property [
        sh:path req:statement ;
        sh:datatype xsd:string ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:message "A Requirement needs exactly one req:statement quoting the source text." ;
    ] ;
    sh:property [
        sh:path req:discrepancyType ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:in ( req:Syntactic req:Semantic req:Functional ) ;
        sh:message "A Requirement needs exactly one req:discrepancyType from the controlled set." ;
    ] ;
    sh:property [
        sh:path req:appliesToVersion ;
        sh:datatype xsd:string ;
    ] .
```

- [ ] **Step 3: Write the positive and negative fixtures**

Create `specification/req/test/req-valid.ttl`:

```turtle
@prefix req: <https://hexplain.io/ns/req#> .
@prefix ex:  <https://example.org/nitf-req#> .

ex:JBP-2021_2-002 a req:Requirement ;
    req:requirementId "JBP-2021.2-002" ;
    req:fromStandard "Joint BIIF Profile 2021.2, 20 April 2021" ;
    req:statement "Packing/production implementation shall ensure all produced JBP files are compliant within the bounds of the established complexity levels." ;
    req:discrepancyType req:Syntactic ;
    req:appliesToVersion "NITF 2.1", "NSIF 1.01" .
```

Create `specification/req/test/req-invalid.ttl` — missing `req:statement` and using an uncontrolled discrepancy type:

```turtle
@prefix req: <https://hexplain.io/ns/req#> .
@prefix ex:  <https://example.org/nitf-req#> .

ex:Broken a req:Requirement ;
    req:requirementId "BROKEN-001" ;
    req:fromStandard "Nowhere" ;
    req:discrepancyType ex:Cosmetic .
```

- [ ] **Step 4: Validate the positive fixture**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/req/shapes.ttl -d specification/req/test/req-valid.ttl -f human
```

Expected: `Conforms: True`, exit 0.

- [ ] **Step 5: Validate the negative fixture**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/req/shapes.ttl -d specification/req/test/req-invalid.ttl -f human
```

Expected: `Conforms: False`, exit 1, with violations naming `req:statement` (minCount) and `req:discrepancyType` (sh:in).

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain.io
git add specification/req/req.ttl specification/req/shapes.ttl \
        specification/req/test/req-valid.ttl specification/req/test/req-invalid.ttl
git commit -m "feat(req): add hx-req requirements vocabulary with SHACL shapes"
```

---

### Task 9: `hx-conf` conformance constraint vocabulary

**Repo:** `hexplain.io`

**Files:**
- Create: `specification/conf/conf.ttl`
- Create: `specification/conf/shapes.ttl`
- Test: `specification/conf/test/conf-valid.ttl`
- Test: `specification/conf/test/conf-invalid.ttl`

**Interfaces:**
- Consumes: `req:Requirement` from Task 8.
- Produces: namespace `https://hexplain.io/ns/conf#` with class `conf:Constraint`; properties `conf:scope` (IRI of a `bddo:Struct` or `bddo:Field`, exactly 1), `conf:assertion` (xsd:string HEL, exactly 1), `conf:satisfies` (`req:Requirement`, minCount 1), `conf:message` (xsd:string, exactly 1).

- [ ] **Step 1: Write the vocabulary**

Create `specification/conf/conf.ttl`:

```turtle
@prefix :     <https://hexplain.io/ns/conf#> .
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req:  <https://hexplain.io/ns/req#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

<https://hexplain.io/ns/conf> a owl:Ontology ;
    rdfs:label "Hexplain Conformance Vocabulary" ;
    owl:versionInfo "1.0" ;
    owl:imports <https://hexplain.io/ns/req> ;
    rdfs:comment """Binds executable HEL assertions to the standards requirements they check.
Format-agnostic. Severity is deliberately absent: it derives from the cited requirement's
req:discrepancyType, so a rule reused across profiles is classified consistently.""" .

# --- Classes ---
:Constraint a owl:Class ; rdfs:label "Constraint" ;
    rdfs:comment "An executable check: a HEL assertion evaluated within a scope, citing the requirements it enforces." ;
    rdfs:isDefinedBy <https://hexplain.io/ns/conf> .

# --- Properties ---
:scope a owl:ObjectProperty ; rdfs:label "scope" ;
    rdfs:comment "The bddo:Struct or bddo:Field the assertion is evaluated against. A struct scope fires once per parsed instance of that struct." ;
    rdfs:range rdfs:Resource .

:assertion a owl:DatatypeProperty ; rdfs:label "assertion" ;
    rdfs:comment "A HEL expression evaluating to boolean. True means conformant; false raises a finding." ;
    rdfs:range xsd:string .

:satisfies a owl:ObjectProperty ; rdfs:label "satisfies" ;
    rdfs:comment "A requirement this constraint enforces. Required: an unattributed rule cannot be reported or counted toward coverage." ;
    rdfs:range req:Requirement .

:message a owl:DatatypeProperty ; rdfs:label "message" ;
    rdfs:comment "Finding text template. {field} interpolates the scoped field name, {value} its parsed value." ;
    rdfs:range xsd:string .
```

- [ ] **Step 2: Write the SHACL shapes**

Create `specification/conf/shapes.ttl`:

```turtle
@prefix :     <https://hexplain.io/ns/conf#> .
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req:  <https://hexplain.io/ns/req#> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

:ConstraintShape a sh:NodeShape ;
    sh:targetClass conf:Constraint ;
    rdfs:label "Constraint shape" ;
    sh:property [
        sh:path conf:scope ;
        sh:nodeKind sh:IRI ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:message "A Constraint needs exactly one conf:scope IRI naming the struct or field it applies to." ;
    ] ;
    sh:property [
        sh:path conf:assertion ;
        sh:datatype xsd:string ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:minLength 1 ;
        sh:message "A Constraint needs exactly one non-empty conf:assertion HEL expression." ;
    ] ;
    sh:property [
        sh:path conf:satisfies ;
        sh:class req:Requirement ;
        sh:minCount 1 ;
        sh:message "A Constraint must cite at least one req:Requirement; an unattributed rule cannot be reported." ;
    ] ;
    sh:property [
        sh:path conf:message ;
        sh:datatype xsd:string ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:message "A Constraint needs exactly one conf:message finding template." ;
    ] .
```

- [ ] **Step 3: Write the positive and negative fixtures**

Create `specification/conf/test/conf-valid.ttl`:

```turtle
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req:  <https://hexplain.io/ns/req#> .
@prefix ex:   <https://example.org/nitf#> .

ex:R-FHDR a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-FHDR" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "FHDR shall contain the value NITF." ;
    req:discrepancyType req:Syntactic ;
    req:appliesToVersion "NITF 2.1" .

ex:C-FHDR a conf:Constraint ;
    conf:scope ex:FileHeader ;
    conf:assertion "FHDR == 'NITF'" ;
    conf:satisfies ex:R-FHDR ;
    conf:message "FHDR must be 'NITF' but was '{value}'." .
```

Create `specification/conf/test/conf-invalid.ttl` — no `conf:satisfies`, and a blank-node scope:

```turtle
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix ex:   <https://example.org/nitf#> .

ex:C-Orphan a conf:Constraint ;
    conf:scope [ ] ;
    conf:assertion "FHDR == 'NITF'" ;
    conf:message "FHDR must be 'NITF'." .
```

- [ ] **Step 4: Validate the positive fixture**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/conf/shapes.ttl \
  -d specification/conf/test/conf-valid.ttl \
  -e specification/req/req.ttl -f human
```

Expected: `Conforms: True`, exit 0. (`-e` supplies the `req` ontology so `sh:class req:Requirement` resolves.)

- [ ] **Step 5: Validate the negative fixture**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/conf/shapes.ttl \
  -d specification/conf/test/conf-invalid.ttl \
  -e specification/req/req.ttl -f human
```

Expected: `Conforms: False`, exit 1, with violations naming `conf:satisfies` (minCount) and `conf:scope` (nodeKind sh:IRI).

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain.io
git add specification/conf/conf.ttl specification/conf/shapes.ttl \
        specification/conf/test/conf-valid.ttl specification/conf/test/conf-invalid.ttl
git commit -m "feat(conf): add hx-conf constraint vocabulary with SHACL shapes"
```

---

### Task 10: Conformance IR and findings model

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/conformance/ConformanceModel.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/conformance/ConformanceModelTest.kt`

**Interfaces:**
- Consumes: `HELExpression` from `io.hexplain.core.hel`.
- Produces:
  - `enum class DiscrepancyType { SYNTACTIC, SEMANTIC, FUNCTIONAL }` with `companion object { fun fromIri(iri: String): DiscrepancyType }`
  - `data class RequirementIR(val id: String, val fromStandard: String, val statement: String, val discrepancyType: DiscrepancyType, val appliesToVersion: List<String> = emptyList())`
  - `data class ConstraintIR(val id: String, val scope: String, val assertion: HELExpression, val requirementIds: List<String>, val message: String)`
  - `data class ConformanceIR(val requirements: Map<String, RequirementIR>, val constraints: List<ConstraintIR>)`
  - `data class Finding(val requirementId: String, val discrepancyType: DiscrepancyType, val message: String, val byteOffset: Int?, val scope: String, val fieldName: String?, val constraintId: String?)`
  - `data class ConformanceReport(val findings: List<Finding>) { fun isConformant(): Boolean; fun byRequirement(): Map<String, List<Finding>> }`

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/conformance/ConformanceModelTest.kt`:

```kotlin
package io.hexplain.core.conformance

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Test

class ConformanceModelTest {

    private fun finding(reqId: String, type: DiscrepancyType) = Finding(
        requirementId = reqId,
        discrepancyType = type,
        message = "boom",
        byteOffset = 0,
        scope = "ex:FileHeader",
        fieldName = "FHDR",
        constraintId = "ex:C-FHDR",
    )

    @Test fun `discrepancy type maps from its vocabulary IRI`() {
        assertEquals(DiscrepancyType.SYNTACTIC, DiscrepancyType.fromIri("https://hexplain.io/ns/req#Syntactic"))
        assertEquals(DiscrepancyType.SEMANTIC, DiscrepancyType.fromIri("https://hexplain.io/ns/req#Semantic"))
        assertEquals(DiscrepancyType.FUNCTIONAL, DiscrepancyType.fromIri("https://hexplain.io/ns/req#Functional"))
    }

    @Test fun `an unknown discrepancy type IRI is rejected`() {
        val e = assertThrows<IllegalArgumentException> {
            DiscrepancyType.fromIri("https://hexplain.io/ns/req#Cosmetic")
        }
        assertTrue(e.message!!.contains("Cosmetic"))
    }

    @Test fun `an empty report is conformant`() =
        assertTrue(ConformanceReport(emptyList()).isConformant())

    @Test fun `a report with any finding is not conformant`() =
        assertFalse(ConformanceReport(listOf(finding("R1", DiscrepancyType.SYNTACTIC))).isConformant())

    @Test fun `findings group by requirement`() {
        val report = ConformanceReport(
            listOf(
                finding("R1", DiscrepancyType.SYNTACTIC),
                finding("R1", DiscrepancyType.SYNTACTIC),
                finding("R2", DiscrepancyType.SEMANTIC),
            )
        )
        val grouped = report.byRequirement()
        assertEquals(setOf("R1", "R2"), grouped.keys)
        assertEquals(2, grouped["R1"]!!.size)
        assertEquals(1, grouped["R2"]!!.size)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ConformanceModelTest"`
Expected: FAIL — compilation error, `DiscrepancyType` unresolved.

- [ ] **Step 3: Implement the model**

Create `core/src/main/kotlin/io/hexplain/core/conformance/ConformanceModel.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.hel.HELExpression

/**
 * The class of defect a requirement violation produces. Mirrors req:DiscrepancyType.
 *
 * Deliberately NOT a risk category: risk is assigned by a test agent from operational
 * impact on anticipated versus unanticipated users, which is a deployment judgement and
 * not a property of the file or of the rule.
 */
enum class DiscrepancyType {
    SYNTACTIC, SEMANTIC, FUNCTIONAL;

    companion object {
        private const val NS = "https://hexplain.io/ns/req#"

        fun fromIri(iri: String): DiscrepancyType = when (iri) {
            NS + "Syntactic" -> SYNTACTIC
            NS + "Semantic" -> SEMANTIC
            NS + "Functional" -> FUNCTIONAL
            else -> throw IllegalArgumentException("Unknown req:DiscrepancyType IRI: $iri")
        }
    }
}

/** A requirement stated by an external standards document. Mirrors req:Requirement. */
data class RequirementIR(
    val id: String,
    val fromStandard: String,
    val statement: String,
    val discrepancyType: DiscrepancyType,
    val appliesToVersion: List<String> = emptyList(),
)

/** An executable check citing the requirements it enforces. Mirrors conf:Constraint. */
data class ConstraintIR(
    /** The constraint's own IRI, for traceability from a finding back to the rule. */
    val id: String,
    /** IRI of the bddo:Struct or bddo:Field this assertion is evaluated against. */
    val scope: String,
    val assertion: HELExpression,
    /** Requirement ids, in declaration order. Never empty — enforced by the SHACL shape. */
    val requirementIds: List<String>,
    val message: String,
)

/** The compiled conformance rule set for a format. */
data class ConformanceIR(
    val requirements: Map<String, RequirementIR>,
    val constraints: List<ConstraintIR>,
)

/** One discrepancy, attributed to a requirement and located in the stream. */
data class Finding(
    val requirementId: String,
    val discrepancyType: DiscrepancyType,
    val message: String,
    val byteOffset: Int?,
    val scope: String,
    val fieldName: String?,
    val constraintId: String?,
)

/**
 * The result of a conformance run. Findings from constraint evaluation and from parse
 * recovery land here indistinguishably: a consumer should not care which produced them.
 */
data class ConformanceReport(val findings: List<Finding>) {
    fun isConformant(): Boolean = findings.isEmpty()

    fun byRequirement(): Map<String, List<Finding>> = findings.groupBy { it.requirementId }
}
```

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ConformanceModelTest"`
Expected: PASS — all five tests.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/conformance/ConformanceModel.kt \
        core/src/test/kotlin/io/hexplain/core/conformance/ConformanceModelTest.kt
git commit -m "feat(conformance): add requirement, constraint, and finding IR model"
```

---

### Task 11: Conformance RDF loader

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/rdf/vocab/REQ.kt`
- Create: `core/src/main/kotlin/io/hexplain/core/rdf/vocab/CONF.kt`
- Create: `core/src/main/kotlin/io/hexplain/core/rdf/ConformanceRdfLoader.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/rdf/ConformanceRdfLoaderTest.kt`

**Interfaces:**
- Consumes: `RequirementIR`, `ConstraintIR`, `ConformanceIR`, `DiscrepancyType` (Task 10); `ProfileLoader` conventions; `HelParser`/`Lexer`.
- Produces: `object REQ` and `object CONF` vocabulary constants following the `BDDO.kt` style; `class ConformanceRdfLoader { fun load(model: Model): ConformanceIR }`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/rdf/ConformanceRdfLoaderTest.kt`:

```kotlin
package io.hexplain.core.rdf

import io.hexplain.core.conformance.DiscrepancyType
import io.hexplain.core.hel.HelEvaluator
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.Test
import java.io.StringReader

class ConformanceRdfLoaderTest {

    private val turtle = """
        @prefix conf: <https://hexplain.io/ns/conf#> .
        @prefix req:  <https://hexplain.io/ns/req#> .
        @prefix ex:   <https://example.org/nitf#> .

        ex:R-FHDR a req:Requirement ;
            req:requirementId "MIL-STD-2500C-A1-FHDR" ;
            req:fromStandard "MIL-STD-2500C, Table A-1" ;
            req:statement "FHDR shall contain the value NITF." ;
            req:discrepancyType req:Syntactic ;
            req:appliesToVersion "NITF 2.1" .

        ex:C-FHDR a conf:Constraint ;
            conf:scope ex:FileHeader ;
            conf:assertion "FHDR == 'NITF'" ;
            conf:satisfies ex:R-FHDR ;
            conf:message "FHDR must be 'NITF' but was '{value}'." .
    """.trimIndent()

    private fun model(ttl: String) = ModelFactory.createDefaultModel().also {
        RDFDataMgr.read(it, StringReader(ttl), null, Lang.TTL)
    }

    @Test fun `loads a requirement with its discrepancy type and versions`() {
        val ir = ConformanceRdfLoader().load(model(turtle))
        val r = ir.requirements.getValue("MIL-STD-2500C-A1-FHDR")
        assertEquals("MIL-STD-2500C, Table A-1", r.fromStandard)
        assertEquals(DiscrepancyType.SYNTACTIC, r.discrepancyType)
        assertEquals(listOf("NITF 2.1"), r.appliesToVersion)
        assertTrue(r.statement.startsWith("FHDR shall"))
    }

    @Test fun `loads a constraint with a parsed assertion`() {
        val ir = ConformanceRdfLoader().load(model(turtle))
        assertEquals(1, ir.constraints.size)
        val c = ir.constraints[0]
        assertEquals("https://example.org/nitf#C-FHDR", c.id)
        assertEquals("https://example.org/nitf#FileHeader", c.scope)
        assertEquals(listOf("MIL-STD-2500C-A1-FHDR"), c.requirementIds)
        // The assertion is a parsed AST, ready to evaluate.
        assertEquals(true, HelEvaluator(mapOf("FHDR" to "NITF")).evaluate(c.assertion))
        assertEquals(false, HelEvaluator(mapOf("FHDR" to "BIIF")).evaluate(c.assertion))
    }

    @Test fun `a constraint citing an undeclared requirement is rejected`() {
        val orphan = turtle.replace("conf:satisfies ex:R-FHDR", "conf:satisfies ex:R-Missing")
        val e = assertThrows<IllegalStateException> { ConformanceRdfLoader().load(model(orphan)) }
        assertTrue(e.message!!.contains("R-Missing"))
    }

    @Test fun `an unparseable assertion names the offending constraint`() {
        val bad = turtle.replace("FHDR == 'NITF'", "FHDR ==")
        val e = assertThrows<IllegalStateException> { ConformanceRdfLoader().load(model(bad)) }
        assertTrue(e.message!!.contains("C-FHDR"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.rdf.ConformanceRdfLoaderTest"`
Expected: FAIL — compilation error, `ConformanceRdfLoader` unresolved.

- [ ] **Step 3: Create the vocabulary constants**

Create `core/src/main/kotlin/io/hexplain/core/rdf/vocab/REQ.kt`:

```kotlin
package io.hexplain.core.rdf.vocab

import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.rdf.model.Property
import org.apache.jena.rdf.model.Resource

/**
 * Vocabulary definitions for the Hexplain Requirements Vocabulary (hx-req) 1.0.
 * Namespace: https://hexplain.io/ns/req#
 *
 * Mirrors specification/req/req.ttl.
 */
object REQ {

    private val m: Model = ModelFactory.createDefaultModel()

    const val NAMESPACE = "https://hexplain.io/ns/req#"
    fun getURI(): String = NAMESPACE

    private fun m_resource(local: String): Resource = m.createResource(NAMESPACE + local)
    private fun m_property(local: String): Property = m.createProperty(NAMESPACE + local)

    // --- Classes ---
    val Requirement: Resource = m_resource("Requirement")
    val DiscrepancyType: Resource = m_resource("DiscrepancyType")

    // --- Controlled individuals ---
    val Syntactic: Resource = m_resource("Syntactic")
    val Semantic: Resource = m_resource("Semantic")
    val Functional: Resource = m_resource("Functional")

    // --- Properties ---
    val requirementId: Property = m_property("requirementId")
    val fromStandard: Property = m_property("fromStandard")
    val statement: Property = m_property("statement")
    val discrepancyType: Property = m_property("discrepancyType")
    val appliesToVersion: Property = m_property("appliesToVersion")
}
```

Create `core/src/main/kotlin/io/hexplain/core/rdf/vocab/CONF.kt`:

```kotlin
package io.hexplain.core.rdf.vocab

import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.rdf.model.Property
import org.apache.jena.rdf.model.Resource

/**
 * Vocabulary definitions for the Hexplain Conformance Vocabulary (hx-conf) 1.0.
 * Namespace: https://hexplain.io/ns/conf#
 *
 * Mirrors specification/conf/conf.ttl.
 */
object CONF {

    private val m: Model = ModelFactory.createDefaultModel()

    const val NAMESPACE = "https://hexplain.io/ns/conf#"
    fun getURI(): String = NAMESPACE

    private fun m_resource(local: String): Resource = m.createResource(NAMESPACE + local)
    private fun m_property(local: String): Property = m.createProperty(NAMESPACE + local)

    // --- Classes ---
    val Constraint: Resource = m_resource("Constraint")

    // --- Properties ---
    val scope: Property = m_property("scope")
    val assertion: Property = m_property("assertion")
    val satisfies: Property = m_property("satisfies")
    val message: Property = m_property("message")
}
```

- [ ] **Step 4: Implement the loader**

Create `core/src/main/kotlin/io/hexplain/core/rdf/ConformanceRdfLoader.kt`:

```kotlin
package io.hexplain.core.rdf

import io.hexplain.core.conformance.ConformanceIR
import io.hexplain.core.conformance.ConstraintIR
import io.hexplain.core.conformance.DiscrepancyType
import io.hexplain.core.conformance.RequirementIR
import io.hexplain.core.hel.HelParser
import io.hexplain.core.hel.Lexer
import io.hexplain.core.rdf.vocab.CONF
import io.hexplain.core.rdf.vocab.REQ
import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.Resource
import org.apache.jena.vocabulary.RDF

/**
 * Compiles req:Requirement and conf:Constraint statements from an RDF graph into
 * [ConformanceIR], parsing each conf:assertion into a HEL AST up-front so evaluation
 * never pays parse cost and syntax errors surface at load time, named by constraint.
 *
 * Structural cardinality is the SHACL shapes' job; this loader assumes a shape-valid
 * graph and fails loudly on anything that would otherwise produce a silently broken rule.
 */
class ConformanceRdfLoader {

    fun load(model: Model): ConformanceIR {
        val requirements = loadRequirements(model)
        val constraints = loadConstraints(model, requirements)
        return ConformanceIR(requirements = requirements, constraints = constraints)
    }

    private fun loadRequirements(model: Model): Map<String, RequirementIR> {
        val result = mutableMapOf<String, RequirementIR>()
        val subjects = model.listSubjectsWithProperty(RDF.type, REQ.Requirement)
        while (subjects.hasNext()) {
            val node = subjects.nextResource()
            val id = requiredString(node, REQ.requirementId, "req:requirementId")
            val typeIri = node.getPropertyResourceValue(REQ.discrepancyType)?.uri
                ?: error("Requirement <${node.uri}> has no req:discrepancyType")
            val versions = mutableListOf<String>()
            val versionStatements = node.listProperties(REQ.appliesToVersion)
            while (versionStatements.hasNext()) {
                versions.add(versionStatements.nextStatement().`object`.asLiteral().string)
            }
            if (result.containsKey(id)) {
                error("Duplicate req:requirementId '$id' (second declaration at <${node.uri}>)")
            }
            result[id] = RequirementIR(
                id = id,
                fromStandard = requiredString(node, REQ.fromStandard, "req:fromStandard"),
                statement = requiredString(node, REQ.statement, "req:statement"),
                discrepancyType = DiscrepancyType.fromIri(typeIri),
                appliesToVersion = versions.sorted(),
            )
        }
        return result
    }

    private fun loadConstraints(
        model: Model,
        requirements: Map<String, RequirementIR>,
    ): List<ConstraintIR> {
        val result = mutableListOf<ConstraintIR>()
        val subjects = model.listSubjectsWithProperty(RDF.type, CONF.Constraint)
        while (subjects.hasNext()) {
            val node = subjects.nextResource()
            val constraintIri = node.uri ?: error("conf:Constraint must be an IRI, found a blank node")
            val scope = node.getPropertyResourceValue(CONF.scope)?.uri
                ?: error("Constraint <$constraintIri> has no IRI conf:scope")

            val requirementIds = mutableListOf<String>()
            val satisfies = node.listProperties(CONF.satisfies)
            while (satisfies.hasNext()) {
                val target = satisfies.nextStatement().`object`.asResource()
                val id = target.getProperty(REQ.requirementId)?.`object`?.asLiteral()?.string
                    ?: error("Constraint <$constraintIri> cites <${target.uri}>, which declares no req:requirementId")
                if (id !in requirements) {
                    error("Constraint <$constraintIri> cites requirement '$id', which is not declared in this graph")
                }
                requirementIds.add(id)
            }
            if (requirementIds.isEmpty()) {
                error("Constraint <$constraintIri> cites no requirement; an unattributed rule cannot be reported")
            }

            val source = requiredString(node, CONF.assertion, "conf:assertion")
            val assertion = try {
                HelParser(Lexer(source).tokenize()).parse()
            } catch (e: Exception) {
                error("Constraint <$constraintIri> has an unparseable conf:assertion '$source': ${e.message}")
            }

            result.add(
                ConstraintIR(
                    id = constraintIri,
                    scope = scope,
                    assertion = assertion,
                    requirementIds = requirementIds,
                    message = requiredString(node, CONF.message, "conf:message"),
                )
            )
        }
        return result.sortedBy { it.id }
    }

    private fun requiredString(node: Resource, property: org.apache.jena.rdf.model.Property, label: String): String =
        node.getProperty(property)?.`object`?.asLiteral()?.string
            ?: error("<${node.uri}> has no $label")
}
```

- [ ] **Step 5: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.rdf.ConformanceRdfLoaderTest"`
Expected: PASS — all four tests.

- [ ] **Step 6: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/rdf/vocab/REQ.kt \
        core/src/main/kotlin/io/hexplain/core/rdf/vocab/CONF.kt \
        core/src/main/kotlin/io/hexplain/core/rdf/ConformanceRdfLoader.kt \
        core/src/test/kotlin/io/hexplain/core/rdf/ConformanceRdfLoaderTest.kt
git commit -m "feat(rdf): load req/conf vocabularies into conformance IR"
```

---

### Task 12: Conformance engine

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/conformance/ConformanceEngine.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/conformance/ConformanceEngineTest.kt`

**Interfaces:**
- Consumes: `ConformanceIR`, `ConstraintIR`, `Finding`, `ConformanceReport`, `DiscrepancyType` (Task 10); `RegisterProvider` (Task 7); `HelEvaluator` with all new parameters (Tasks 3–7); `FormatIR`/`StructIR` and `Metaparser.BYTE_OFFSET_KEY`.
- Produces: `class ConformanceEngine(conformanceIR: ConformanceIR, formatIR: FormatIR, registerProvider: RegisterProvider? = null, evaluationInstant: Long? = null) { fun evaluate(parsed: Map<String, Any>): ConformanceReport }`.

Scope resolution: a constraint whose `scope` equals a struct IRI fires once per parsed instance of that struct found in the tree. Struct instances are located by matching `StructIR.name` against the map produced for that struct — the engine walks the parsed tree alongside the `FormatIR` so it knows which struct each map came from.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/conformance/ConformanceEngineTest.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.hel.HelParser
import io.hexplain.core.hel.Lexer
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ConformanceEngineTest {

    private val bytesType = DataTypeIR(name = "bddo:Bytes", baseType = BaseType.BYTES, bitWidth = 8)

    private fun hel(src: String) = HelParser(Lexer(src).tokenize()).parse()

    /**
     * Root FileHeader with a nested repeated ImageSubheader list. A field descends into a
     * struct when its DataTypeIR.name is a key in FormatIR.structs — the same resolution
     * Metaparser uses (`formatIR.structs[effectiveDataType.name]`).
     */
    private val formatIR = FormatIR(
        name = "test",
        rootStruct = "ex:FileHeader",
        structs = mapOf(
            "ex:FileHeader" to StructIR(
                name = "ex:FileHeader",
                fields = listOf(
                    FieldIR(name = "FHDR", dataType = bytesType, size = 4),
                    FieldIR(
                        name = "IMAGES",
                        dataType = DataTypeIR(name = "ex:ImageSubheader", baseType = BaseType.BYTES, bitWidth = 8),
                    ),
                ),
            ),
            "ex:ImageSubheader" to StructIR(
                name = "ex:ImageSubheader",
                fields = listOf(FieldIR(name = "ISCLAS", dataType = bytesType, size = 1)),
            ),
        ),
    )

    private val requirements = mapOf(
        "R-FHDR" to RequirementIR("R-FHDR", "MIL-STD-2500C A-1", "FHDR shall be NITF.", DiscrepancyType.SYNTACTIC),
        "R-CLAS" to RequirementIR("R-CLAS", "MIL-STD-2500C A-3", "ISCLAS shall be a known level.", DiscrepancyType.SEMANTIC),
    )

    private fun engine(constraints: List<ConstraintIR>) = ConformanceEngine(
        conformanceIR = ConformanceIR(requirements, constraints),
        formatIR = formatIR,
    )

    private val fhdrRule = ConstraintIR(
        id = "ex:C-FHDR",
        scope = "ex:FileHeader",
        assertion = hel("FHDR == 'NITF'"),
        requirementIds = listOf("R-FHDR"),
        message = "FHDR must be 'NITF' but was '{value}'.",
    )

    private val clasRule = ConstraintIR(
        id = "ex:C-CLAS",
        scope = "ex:ImageSubheader",
        assertion = hel("ISCLAS == 'U' or ISCLAS == 'S'"),
        requirementIds = listOf("R-CLAS"),
        message = "ISCLAS '{value}' is not a known classification level.",
    )

    private fun parsedTree(fhdr: String, classifications: List<String>): Map<String, Any> = mapOf(
        "FHDR" to fhdr,
        "__byteOffset" to 0,
        "IMAGES" to classifications.mapIndexed { i, c ->
            mapOf("ISCLAS" to c, "__byteOffset" to 100 + i * 10)
        },
    )

    @Test fun `a conformant tree produces no findings`() {
        val report = engine(listOf(fhdrRule, clasRule)).evaluate(parsedTree("NITF", listOf("U", "S")))
        assertTrue(report.isConformant())
    }

    @Test fun `a root-scoped violation is reported with its requirement and type`() {
        val report = engine(listOf(fhdrRule)).evaluate(parsedTree("BIIF", listOf("U")))
        assertEquals(1, report.findings.size)
        val f = report.findings[0]
        assertEquals("R-FHDR", f.requirementId)
        assertEquals(DiscrepancyType.SYNTACTIC, f.discrepancyType)
        assertEquals("ex:C-FHDR", f.constraintId)
        assertEquals("ex:FileHeader", f.scope)
        assertEquals(0, f.byteOffset)
        assertFalse(report.isConformant())
    }

    @Test fun `a struct-scoped rule fires once per instance and locates each one`() {
        val report = engine(listOf(clasRule)).evaluate(parsedTree("NITF", listOf("U", "X", "Z")))
        assertEquals(2, report.findings.size)
        assertEquals(listOf(110, 120), report.findings.map { it.byteOffset })
        assertEquals("ex:ImageSubheader", report.findings[0].scope)
    }

    @Test fun `the message template interpolates the offending value`() {
        val report = engine(listOf(fhdrRule)).evaluate(parsedTree("BIIF", listOf("U")))
        assertTrue(report.findings[0].message.contains("'BIIF'"), report.findings[0].message)
    }

    @Test fun `an assertion that throws becomes a finding rather than aborting the run`() {
        val brokenRule = ConstraintIR(
            id = "ex:C-Broken",
            scope = "ex:FileHeader",
            assertion = hel("MISSING_FIELD == 'x'"),
            requirementIds = listOf("R-FHDR"),
            message = "unused",
        )
        // A rule referencing an absent field must not stop the other rules running.
        val report = engine(listOf(brokenRule, fhdrRule)).evaluate(parsedTree("BIIF", listOf("U")))
        assertEquals(2, report.findings.size)
        assertTrue(report.findings.any { it.constraintId == "ex:C-Broken" })
        assertTrue(report.findings.any { it.constraintId == "ex:C-FHDR" })
    }

    @Test fun `a nested-scope constraint can reach the root for cross-segment rules`() {
        // "No segment is classified above the file" is the archetypal cross-segment rule
        // and is unwritable unless a nested scope can navigate to root.
        val dominance = ConstraintIR(
            id = "ex:C-Dominance",
            scope = "ex:ImageSubheader",
            assertion = hel("ISCLAS == root.FHDR or ISCLAS == 'U'"),
            requirementIds = listOf("R-CLAS"),
            message = "ISCLAS '{value}' exceeds the file classification.",
        )
        val clean = engine(listOf(dominance)).evaluate(parsedTree("NITF", listOf("U")))
        assertTrue(clean.isConformant())

        val violating = engine(listOf(dominance)).evaluate(parsedTree("NITF", listOf("S")))
        assertEquals(1, violating.findings.size)
        assertEquals("R-CLAS", violating.findings[0].requirementId)
    }

    @Test fun `a constraint citing several requirements yields one finding each`() {
        val multi = fhdrRule.copy(id = "ex:C-Multi", requirementIds = listOf("R-FHDR", "R-CLAS"))
        val report = engine(listOf(multi)).evaluate(parsedTree("BIIF", listOf("U")))
        assertEquals(setOf("R-FHDR", "R-CLAS"), report.findings.map { it.requirementId }.toSet())
    }
}
```

Note: `DataTypeIR`'s first parameter `name` is required and has no default — every construction must supply it.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ConformanceEngineTest"`
Expected: FAIL — compilation error, `ConformanceEngine` unresolved.

- [ ] **Step 3: Implement the engine**

Create `core/src/main/kotlin/io/hexplain/core/conformance/ConformanceEngine.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.hel.HelEvaluationException
import io.hexplain.core.hel.HelEvaluator
import io.hexplain.core.ir.FormatIR
import io.hexplain.core.metacodec.Metaparser

/**
 * Evaluates declarative conformance constraints against a parsed tree.
 *
 * A constraint's conf:scope names a struct; the engine locates every parsed instance of
 * that struct and evaluates the assertion once per instance, with the instance as the HEL
 * evaluation context. A false result becomes one [Finding] per cited requirement, so a
 * rule enforcing two requirements reports against both.
 */
class ConformanceEngine(
    private val conformanceIR: ConformanceIR,
    private val formatIR: FormatIR,
    private val registerProvider: RegisterProvider? = null,
    private val evaluationInstant: Long? = null,
) {

    fun evaluate(parsed: Map<String, Any>): ConformanceReport {
        val instances = mutableMapOf<String, MutableList<Instance>>()
        collectInstances(formatIR.rootStruct, parsed, null, parsed, instances)

        val findings = mutableListOf<Finding>()
        for (constraint in conformanceIR.constraints) {
            for (instance in instances[constraint.scope].orEmpty()) {
                findings.addAll(evaluateOne(constraint, instance))
            }
        }
        return ConformanceReport(findings)
    }

    private fun evaluateOne(constraint: ConstraintIR, instance: Instance): List<Finding> {
        val evaluator = HelEvaluator(
            context = instance.data,
            parentContext = instance.parent,
            // The root must be reachable: cross-segment rules are the point of a scoped
            // constraint language. "No segment is classified above the file" is exactly
            // `FSCLAS`-vs-`root.FSCLAS`, and it cannot be written without this.
            rootContext = instance.root,
            streamContext = null,
            selfContext = instance.data,
            evaluationInstant = evaluationInstant,
            registerProvider = registerProvider,
        )

        val message: String
        try {
            if (evaluator.evaluate(constraint.assertion) == true) return emptyList()
            message = render(constraint.message, instance)
        } catch (e: HelEvaluationException) {
            // A rule that cannot be evaluated is itself a discrepancy to report: the file did
            // not present what the rule needed. Aborting the run would hide every later rule.
            return findingsFor(constraint, instance, "Could not evaluate '${constraint.id}': ${e.message}")
        }
        return findingsFor(constraint, instance, message)
    }

    private fun findingsFor(constraint: ConstraintIR, instance: Instance, message: String): List<Finding> =
        constraint.requirementIds.map { requirementId ->
            val requirement = conformanceIR.requirements[requirementId]
                ?: error("Constraint '${constraint.id}' cites unknown requirement '$requirementId'")
            Finding(
                requirementId = requirementId,
                discrepancyType = requirement.discrepancyType,
                message = message,
                byteOffset = instance.byteOffset,
                scope = constraint.scope,
                fieldName = null,
                constraintId = constraint.id,
            )
        }

    /** Interpolates {value} with the scoped instance's single-field value where unambiguous. */
    private fun render(template: String, instance: Instance): String {
        if (!template.contains("{value}")) return template
        val scalar = instance.data.entries
            .firstOrNull { !it.key.startsWith("__") && it.value !is Map<*, *> && it.value !is List<*> }
            ?.value
        val text = when (scalar) {
            null -> "?"
            is ByteArray -> String(scalar, Charsets.UTF_8)
            else -> scalar.toString()
        }
        return template.replace("{value}", text)
    }

    /** A parsed struct instance, tagged with the struct it came from. */
    private data class Instance(
        val data: Map<String, Any>,
        val parent: Map<String, Any>?,
        val root: Map<String, Any>,
        val byteOffset: Int?,
    )

    /**
     * Walks the parsed tree alongside the FormatIR so every map can be attributed to the
     * struct that produced it — the parsed tree alone carries no type tag.
     */
    private fun collectInstances(
        structName: String,
        data: Map<String, Any>,
        parent: Map<String, Any>?,
        root: Map<String, Any>,
        out: MutableMap<String, MutableList<Instance>>,
    ) {
        out.getOrPut(structName) { mutableListOf() }
            .add(Instance(data, parent, root, data[Metaparser.BYTE_OFFSET_KEY] as? Int))

        val structDef = formatIR.structs[structName] ?: return
        for (field in structDef.fields) {
            val nested = nestedStructName(field) ?: continue
            when (val value = data[field.name]) {
                is Map<*, *> -> {
                    @Suppress("UNCHECKED_CAST")
                    collectInstances(nested, value as Map<String, Any>, data, root, out)
                }
                is List<*> -> value.filterIsInstance<Map<*, *>>().forEach {
                    @Suppress("UNCHECKED_CAST")
                    collectInstances(nested, it as Map<String, Any>, data, root, out)
                }
                else -> Unit
            }
        }
    }

    /**
     * Name of the struct a field descends into, or null for a scalar field. A field's data
     * type names a struct when its IRI is a key in FormatIR.structs — the same resolution
     * Metaparser performs at `formatIR.structs[effectiveDataType.name]`.
     */
    private fun nestedStructName(field: io.hexplain.core.ir.FieldIR): String? =
        field.dataType.name.takeIf { formatIR.structs.containsKey(it) }
}
```

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ConformanceEngineTest"`
Expected: PASS — all seven tests.

- [ ] **Step 5: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/conformance/ConformanceEngine.kt \
        core/src/test/kotlin/io/hexplain/core/conformance/ConformanceEngineTest.kt
git commit -m "feat(conformance): add engine evaluating scoped HEL constraints"
```

---

### Task 13: Parse diagnostics to findings bridge

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/conformance/ParseDiagnosticBridge.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/conformance/ParseDiagnosticBridgeTest.kt`

**Interfaces:**
- Consumes: `ParseDiagnostic`, `HexplainErrorKind` (Task 1); `Finding`, `DiscrepancyType`, `ConformanceIR` (Task 10).
- Produces: `class ParseDiagnosticBridge(kindRequirements: Map<HexplainErrorKind, String>, conformanceIR: ConformanceIR) { fun toFindings(diagnostics: List<ParseDiagnostic>): List<Finding> }`.

Structural failures detected during parse have no `conf:Constraint` behind them, so each `HexplainErrorKind` is mapped to a requirement id by configuration. A kind with no mapping produces a finding attributed to the reserved id `UNATTRIBUTED`, typed `SYNTACTIC` — visible rather than silently dropped.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/conformance/ParseDiagnosticBridgeTest.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.metacodec.HexplainErrorKind
import io.hexplain.core.metacodec.ParseDiagnostic
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ParseDiagnosticBridgeTest {

    private val requirements = mapOf(
        "R-FHDR" to RequirementIR("R-FHDR", "MIL-STD-2500C A-1", "FHDR shall be NITF.", DiscrepancyType.SYNTACTIC),
        "R-BOUNDS" to RequirementIR("R-BOUNDS", "MIL-STD-2500C 5.1", "Segment lengths shall be consistent.", DiscrepancyType.FUNCTIONAL),
    )
    private val ir = ConformanceIR(requirements, emptyList())

    private fun bridge(mapping: Map<HexplainErrorKind, String>) = ParseDiagnosticBridge(mapping, ir)

    private val validationDiag = ParseDiagnostic(
        message = "Validation failed for field 'FHDR'.",
        kind = HexplainErrorKind.VALIDATION,
        byteOffset = 0,
        structName = "ex:FileHeader",
        fieldName = "FHDR",
    )
    private val boundsDiag = ParseDiagnostic(
        message = "Read past end of stream.",
        kind = HexplainErrorKind.BOUNDS,
        byteOffset = 4096,
        structName = "ex:ImageSubheader",
        fieldName = null,
    )

    @Test fun `a mapped kind is attributed to its requirement with that requirement's type`() {
        val findings = bridge(mapOf(HexplainErrorKind.VALIDATION to "R-FHDR")).toFindings(listOf(validationDiag))
        assertEquals(1, findings.size)
        assertEquals("R-FHDR", findings[0].requirementId)
        assertEquals(DiscrepancyType.SYNTACTIC, findings[0].discrepancyType)
        assertEquals(0, findings[0].byteOffset)
        assertEquals("FHDR", findings[0].fieldName)
        assertEquals("ex:FileHeader", findings[0].scope)
        assertEquals(null, findings[0].constraintId)
    }

    @Test fun `each kind maps independently`() {
        val findings = bridge(
            mapOf(HexplainErrorKind.VALIDATION to "R-FHDR", HexplainErrorKind.BOUNDS to "R-BOUNDS")
        ).toFindings(listOf(validationDiag, boundsDiag))
        assertEquals(listOf("R-FHDR", "R-BOUNDS"), findings.map { it.requirementId })
        assertEquals(DiscrepancyType.FUNCTIONAL, findings[1].discrepancyType)
    }

    @Test fun `an unmapped kind is surfaced as UNATTRIBUTED rather than dropped`() {
        val findings = bridge(emptyMap()).toFindings(listOf(boundsDiag))
        assertEquals(1, findings.size)
        assertEquals("UNATTRIBUTED", findings[0].requirementId)
        assertEquals(DiscrepancyType.SYNTACTIC, findings[0].discrepancyType)
        assertTrue(findings[0].message.contains("Read past end of stream"))
    }

    @Test fun `a mapping naming an undeclared requirement is UNATTRIBUTED`() {
        val findings = bridge(mapOf(HexplainErrorKind.BOUNDS to "R-NOPE")).toFindings(listOf(boundsDiag))
        assertEquals("UNATTRIBUTED", findings[0].requirementId)
    }

    @Test fun `an empty diagnostic list yields no findings`() =
        assertEquals(emptyList<Finding>(), bridge(emptyMap()).toFindings(emptyList()))
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ParseDiagnosticBridgeTest"`
Expected: FAIL — compilation error, `ParseDiagnosticBridge` unresolved.

- [ ] **Step 3: Implement the bridge**

Create `core/src/main/kotlin/io/hexplain/core/conformance/ParseDiagnosticBridge.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.metacodec.HexplainErrorKind
import io.hexplain.core.metacodec.ParseDiagnostic

/**
 * Converts parse-time diagnostics into [Finding]s so that structural discrepancies and
 * constraint violations reach the report through one channel.
 *
 * Structural failures are detected before any constraint can run and so have no
 * conf:Constraint behind them. Each [HexplainErrorKind] is therefore attributed to a
 * requirement by configuration. Anything unmapped is reported under [UNATTRIBUTED] rather
 * than discarded: a silently dropped discrepancy is worse than an unattributed one.
 */
class ParseDiagnosticBridge(
    private val kindRequirements: Map<HexplainErrorKind, String>,
    private val conformanceIR: ConformanceIR,
) {

    fun toFindings(diagnostics: List<ParseDiagnostic>): List<Finding> = diagnostics.map { diagnostic ->
        val requirement = kindRequirements[diagnostic.kind]?.let { conformanceIR.requirements[it] }
        Finding(
            requirementId = requirement?.id ?: UNATTRIBUTED,
            discrepancyType = requirement?.discrepancyType ?: DiscrepancyType.SYNTACTIC,
            message = diagnostic.message,
            byteOffset = diagnostic.byteOffset,
            scope = diagnostic.structName,
            fieldName = diagnostic.fieldName,
            constraintId = null,
        )
    }

    companion object {
        /** Reserved id for a discrepancy no requirement has been mapped to yet. */
        const val UNATTRIBUTED = "UNATTRIBUTED"
    }
}
```

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ParseDiagnosticBridgeTest"`
Expected: PASS — all five tests.

- [ ] **Step 5: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/conformance/ParseDiagnosticBridge.kt \
        core/src/test/kotlin/io/hexplain/core/conformance/ParseDiagnosticBridgeTest.kt
git commit -m "feat(conformance): bridge parse diagnostics into findings"
```

---

### Task 14: Coverage query

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/main/kotlin/io/hexplain/core/conformance/CoverageReport.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/conformance/CoverageReportTest.kt`

**Interfaces:**
- Consumes: `ConformanceIR`, `RequirementIR`, `ConstraintIR` (Task 10).
- Produces: `data class CoverageRow(val requirementId: String, val fromStandard: String, val discrepancyType: DiscrepancyType, val appliesToVersion: List<String>, val constraintIds: List<String>)`; `object CoverageReport { fun rows(ir: ConformanceIR): List<CoverageRow>; fun uncovered(ir: ConformanceIR): List<String>; fun toCsv(rows: List<CoverageRow>): String }`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/conformance/CoverageReportTest.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.hel.HelParser
import io.hexplain.core.hel.Lexer
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class CoverageReportTest {

    private fun hel(src: String) = HelParser(Lexer(src).tokenize()).parse()

    private val ir = ConformanceIR(
        requirements = mapOf(
            "R-A" to RequirementIR("R-A", "STD-1", "A shall hold.", DiscrepancyType.SYNTACTIC, listOf("NITF 2.1")),
            "R-B" to RequirementIR("R-B", "STD-1", "B shall hold.", DiscrepancyType.SEMANTIC, listOf("NITF 2.1", "NSIF 1.01")),
            "R-C" to RequirementIR("R-C", "STD-2", "C shall hold.", DiscrepancyType.FUNCTIONAL),
        ),
        constraints = listOf(
            ConstraintIR("ex:C1", "ex:S", hel("true"), listOf("R-A"), "m"),
            ConstraintIR("ex:C2", "ex:S", hel("true"), listOf("R-A", "R-B"), "m"),
        ),
    )

    @Test fun `every requirement appears exactly once, sorted by id`() {
        val rows = CoverageReport.rows(ir)
        assertEquals(listOf("R-A", "R-B", "R-C"), rows.map { it.requirementId })
    }

    @Test fun `a requirement lists every constraint enforcing it`() {
        val rows = CoverageReport.rows(ir).associateBy { it.requirementId }
        assertEquals(listOf("ex:C1", "ex:C2"), rows.getValue("R-A").constraintIds)
        assertEquals(listOf("ex:C2"), rows.getValue("R-B").constraintIds)
        assertEquals(emptyList<String>(), rows.getValue("R-C").constraintIds)
    }

    @Test fun `uncovered lists requirements with no constraint`() =
        assertEquals(listOf("R-C"), CoverageReport.uncovered(ir))

    @Test fun `csv has a header and one row per requirement`() {
        val csv = CoverageReport.toCsv(CoverageReport.rows(ir))
        val lines = csv.trim().lines()
        assertEquals(4, lines.size)
        assertEquals("requirementId,fromStandard,discrepancyType,appliesToVersion,constraintIds", lines[0])
        assertTrue(lines[1].startsWith("R-A,STD-1,SYNTACTIC,"), lines[1])
    }

    @Test fun `csv quotes fields containing commas`() {
        val csv = CoverageReport.toCsv(CoverageReport.rows(ir))
        assertTrue(csv.contains("\"NITF 2.1;NSIF 1.01\"") || csv.contains("NITF 2.1;NSIF 1.01"), csv)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.CoverageReportTest"`
Expected: FAIL — compilation error, `CoverageReport` unresolved.

- [ ] **Step 3: Implement the coverage report**

Create `core/src/main/kotlin/io/hexplain/core/conformance/CoverageReport.kt`:

```kotlin
package io.hexplain.core.conformance

/** One requirement and the constraints enforcing it. */
data class CoverageRow(
    val requirementId: String,
    val fromStandard: String,
    val discrepancyType: DiscrepancyType,
    val appliesToVersion: List<String>,
    val constraintIds: List<String>,
)

/**
 * Derives conformance coverage from the conf:satisfies relation.
 *
 * Coverage is computed, never maintained by hand: a requirement with no constraint is an
 * implementation gap, and that list is the readiness signal for the whole programme. It is
 * also the input to a test agent's test case matrix, so it must be reproducible.
 */
object CoverageReport {

    fun rows(ir: ConformanceIR): List<CoverageRow> {
        val byRequirement = mutableMapOf<String, MutableList<String>>()
        for (constraint in ir.constraints) {
            for (requirementId in constraint.requirementIds) {
                byRequirement.getOrPut(requirementId) { mutableListOf() }.add(constraint.id)
            }
        }
        return ir.requirements.values
            .sortedBy { it.id }
            .map { requirement ->
                CoverageRow(
                    requirementId = requirement.id,
                    fromStandard = requirement.fromStandard,
                    discrepancyType = requirement.discrepancyType,
                    appliesToVersion = requirement.appliesToVersion,
                    constraintIds = byRequirement[requirement.id].orEmpty().sorted(),
                )
            }
    }

    /** Requirements no constraint enforces — the implementation gap list. */
    fun uncovered(ir: ConformanceIR): List<String> =
        rows(ir).filter { it.constraintIds.isEmpty() }.map { it.requirementId }

    fun toCsv(rows: List<CoverageRow>): String = buildString {
        appendLine("requirementId,fromStandard,discrepancyType,appliesToVersion,constraintIds")
        for (row in rows) {
            append(escape(row.requirementId)); append(',')
            append(escape(row.fromStandard)); append(',')
            append(row.discrepancyType.name); append(',')
            append(escape(row.appliesToVersion.joinToString(";"))); append(',')
            appendLine(escape(row.constraintIds.joinToString(";")))
        }
    }

    private fun escape(value: String): String =
        if (value.contains(',') || value.contains('"') || value.contains('\n')) {
            "\"" + value.replace("\"", "\"\"") + "\""
        } else {
            value
        }
}
```

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.CoverageReportTest"`
Expected: PASS — all five tests.

- [ ] **Step 5: Run the full suite and commit**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test`
Expected: PASS

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/conformance/CoverageReport.kt \
        core/src/test/kotlin/io/hexplain/core/conformance/CoverageReportTest.kt
git commit -m "feat(conformance): derive coverage rows from conf:satisfies"
```

---

### Task 15: End-to-end walking skeleton

**Repo:** `hexplain-tools`

**Files:**
- Test: `core/src/test/kotlin/io/hexplain/core/conformance/ConformanceEndToEndTest.kt`
- Test resource: `core/src/test/resources/conformance/mini-nitf-profile.ttl`
- Test resource: `core/src/test/resources/conformance/mini-nitf-conformance.ttl`

**Interfaces:**
- Consumes: everything from Tasks 1–14. Produces no new production types — this task proves the layer works end to end and is the gate on P0 being complete.

- [ ] **Step 1: Write the profile fixture**

Create `core/src/test/resources/conformance/mini-nitf-profile.ttl` — a minimal BDDO description of a four-field header. Match the property style used by `core/src/test/resources/png-profile.ttl`; read that file first and mirror its prefixes and `bddo:hasField` list form exactly.

```turtle
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://example.org/mininitf#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:FileHeader a bddo:Struct ;
    rdfs:label "Mini NITF file header" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( ex:FHDR ex:FVER ex:FDT ex:FSCLAS ) .

ex:FHDR a bddo:Field ; rdfs:label "FHDR" ;
    bddo:dataType bddo:String ; bddo:size 4 .
ex:FVER a bddo:Field ; rdfs:label "FVER" ;
    bddo:dataType bddo:String ; bddo:size 5 .
ex:FDT a bddo:Field ; rdfs:label "FDT" ;
    bddo:dataType bddo:String ; bddo:size 14 .
ex:FSCLAS a bddo:Field ; rdfs:label "FSCLAS" ;
    bddo:dataType bddo:String ; bddo:size 1 .
```

- [ ] **Step 2: Write the conformance fixture**

Create `core/src/test/resources/conformance/mini-nitf-conformance.ttl`:

```turtle
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req:  <https://hexplain.io/ns/req#> .
@prefix ex:   <https://example.org/mininitf#> .

ex:R-FHDR a req:Requirement ;
    req:requirementId "MINI-001" ;
    req:fromStandard "Mini NITF, Table 1" ;
    req:statement "FHDR shall contain the value NITF." ;
    req:discrepancyType req:Syntactic ;
    req:appliesToVersion "Mini 1.0" .

ex:R-FDT a req:Requirement ;
    req:requirementId "MINI-002" ;
    req:fromStandard "Mini NITF, Table 1" ;
    req:statement "FDT shall be formatted CCYYMMDDhhmmss." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "Mini 1.0" .

ex:R-FSCLAS a req:Requirement ;
    req:requirementId "MINI-003" ;
    req:fromStandard "Mini NITF, Table 1" ;
    req:statement "FSCLAS shall be a registered classification level." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "Mini 1.0" .

ex:C-FHDR a conf:Constraint ;
    conf:scope ex:FileHeader ;
    conf:assertion "FHDR == 'NITF'" ;
    conf:satisfies ex:R-FHDR ;
    conf:message "FHDR must be 'NITF'." .

ex:C-FDT a conf:Constraint ;
    conf:scope ex:FileHeader ;
    conf:assertion "matches(FDT, '[0-9]{14}')" ;
    conf:satisfies ex:R-FDT ;
    conf:message "FDT must be CCYYMMDDhhmmss." .

ex:C-FSCLAS a conf:Constraint ;
    conf:scope ex:FileHeader ;
    conf:assertion "inRegister(FSCLAS, 'https://example.org/mininitf#ClassLevels')" ;
    conf:satisfies ex:R-FSCLAS ;
    conf:message "FSCLAS '{value}' is not a registered classification level." .
```

- [ ] **Step 3: Write the end-to-end test**

Create `core/src/test/kotlin/io/hexplain/core/conformance/ConformanceEndToEndTest.kt`:

```kotlin
package io.hexplain.core.conformance

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.metacodec.ParseDiagnostics
import io.hexplain.core.metacodec.RecoveryPolicy
import io.hexplain.core.rdf.ConformanceRdfLoader
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * The P0 gate: profile + conformance rules load from RDF, a file parses under COLLECT
 * recovery, and constraint violations plus parse diagnostics arrive in one report.
 */
class ConformanceEndToEndTest {

    private val classScheme = "https://example.org/mininitf#ClassLevels"
    private val registers = MapRegisterProvider(mapOf(classScheme to setOf("U", "R", "C", "S", "T")))

    // FHDR(4) FVER(5) FDT(14) FSCLAS(1)
    private fun file(fhdr: String, fver: String, fdt: String, fsclas: String) =
        (fhdr + fver + fdt + fsclas).toByteArray()

    private fun resource(name: String) =
        checkNotNull(javaClass.getResourceAsStream("/conformance/$name")) { "missing fixture $name" }

    private fun run(bytes: ByteArray): ConformanceReport {
        val profileModel = ProfileLoader().load(resource("mini-nitf-profile.ttl"))
        val formatIR = RdfToIrCompiler(profileModel).compile("https://example.org/mininitf#FileHeader")

        val confModel = ProfileLoader().load(resource("mini-nitf-conformance.ttl"))
        val conformanceIR = ConformanceRdfLoader().load(confModel)

        val diagnostics = ParseDiagnostics()
        val parser = Metaparser(
            formatIR = formatIR,
            recoveryPolicy = RecoveryPolicy.COLLECT,
            diagnostics = diagnostics,
        )
        @Suppress("UNCHECKED_CAST")
        val parsed = parser.parse(bytes) as Map<String, Any>

        val engine = ConformanceEngine(
            conformanceIR = conformanceIR,
            formatIR = formatIR,
            registerProvider = registers,
            evaluationInstant = 1785587400L,
        )
        val constraintFindings = engine.evaluate(parsed).findings
        val parseFindings = ParseDiagnosticBridge(emptyMap(), conformanceIR).toFindings(diagnostics.entries)
        return ConformanceReport(parseFindings + constraintFindings)
    }

    @Test fun `a conformant file yields an empty report`() {
        val report = run(file("NITF", "02.10", "20260801120000", "U"))
        assertTrue(report.isConformant(), report.findings.joinToString("\n") { it.message })
    }

    @Test fun `three independent defects yield three findings in one pass`() {
        val report = run(file("BIIF", "02.10", "21JAN01123015", "Q"))
        assertEquals(3, report.findings.size, report.findings.joinToString("\n") { it.message })
        assertEquals(
            setOf("MINI-001", "MINI-002", "MINI-003"),
            report.findings.map { it.requirementId }.toSet(),
        )
        assertFalse(report.isConformant())
    }

    @Test fun `findings carry the discrepancy type of the requirement they cite`() {
        val report = run(file("BIIF", "02.10", "21JAN01123015", "U"))
        val byRequirement = report.findings.associateBy { it.requirementId }
        assertEquals(DiscrepancyType.SYNTACTIC, byRequirement.getValue("MINI-001").discrepancyType)
        assertEquals(DiscrepancyType.SEMANTIC, byRequirement.getValue("MINI-002").discrepancyType)
    }

    @Test fun `coverage over the fixture shows every requirement enforced`() {
        val conformanceIR = ConformanceRdfLoader().load(ProfileLoader().load(resource("mini-nitf-conformance.ttl")))
        assertEquals(emptyList<String>(), CoverageReport.uncovered(conformanceIR))
        assertEquals(3, CoverageReport.rows(conformanceIR).size)
    }
}
```

- [ ] **Step 4: Run the test and reconcile the profile fixture**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.conformance.ConformanceEndToEndTest"`

The compiler API is `RdfToIrCompiler(model).compile(rootStructUri)` — already used correctly above. The remaining unknown is the profile fixture's BDDO surface: `compile` resolves primitive data types against `bddo.ttl` on the classpath, so the `bddo:String` datatype IRI and the `bddo:hasField` list form in Step 1 must match what `core/src/test/resources/png-profile.ttl` uses. Read that file and correct the fixture's prefixes, datatype IRIs, and field-list syntax to match before re-running.

Expected after reconciliation: PASS — all four tests.

- [ ] **Step 5: Run the full suite**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — both `core` and `hdl` modules green.

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/test/kotlin/io/hexplain/core/conformance/ConformanceEndToEndTest.kt \
        core/src/test/resources/conformance/mini-nitf-profile.ttl \
        core/src/test/resources/conformance/mini-nitf-conformance.ttl
git commit -m "test(conformance): end-to-end walking skeleton for the P0 layer"
```

---

### Task 16: Profile refinement capability audit

**Repo:** `hexplain.io`

**Files:**
- Create: `docs/superpowers/notes/2026-08-01-profile-refinement-audit.md`
- Test: `specification/profiles/nitf/test/refinement-probe.ttl`

**Interfaces:**
- Consumes: nothing.
- Produces: a written decision record answering whether a profile can import another and override a field, which P4 (NSIF) and P7 (NITF 2.0/1.1) both depend on. No production code.

This is the §10 risk response. It is placed last because nothing in P0 blocks on the answer, but P4 cannot be planned without it.

- [ ] **Step 1: Write the probe fixture**

Create `specification/profiles/nitf/test/refinement-probe.ttl` — a profile that imports the NITF profile and attempts to override `FHDR`'s fixed value, as an NSIF profile would need to:

```turtle
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix nitf: <https://hexplain.io/formats/nitf#> .
@prefix nsif: <https://example.org/nsif-probe#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.org/nsif-probe> a owl:Ontology ;
    rdfs:label "NSIF refinement probe" ;
    owl:imports <https://hexplain.io/formats/nitf> .

# Probe: can a downstream profile restate a field's fixed value without redefining the
# whole struct? If the compiler takes the last-written value, refinement works. If it
# takes both, or the first, refinement needs explicit support.
nitf:FH_FHDR bddo:hasFixedValue "NSIF" .
```

- [ ] **Step 2: Run the probe through the compiler**

Run:

```bash
cd /d/work/hexplain-tools
./gradlew :core:runFormatIRToRdf \
  -PformatIrArgs="/d/work/hexplain.io/specification/profiles/nitf/test/refinement-probe.ttl https://hexplain.io/formats/nitf#FileHeader /tmp/probe-out.ttl"
```

Record verbatim: whether the run succeeds, and what `FH_FHDR`'s fixed value is in the output — `NITF`, `NSIF`, both, or an error.

- [ ] **Step 3: Check the compiler's merge behaviour**

Read `core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt` and determine, from the code, how a repeated `bddo:hasFixedValue` on one field resolves. Record which function decides it and at which line.

- [ ] **Step 4: Write the decision record**

Create `docs/superpowers/notes/2026-08-01-profile-refinement-audit.md` containing:

- **Question:** can a profile import another and override a field-level property?
- **Probe result:** the verbatim outcome from Step 2.
- **Mechanism:** the function and line from Step 3 that decides it.
- **Verdict:** one of — *refinement works as-is* / *refinement needs a precedence rule* / *refinement needs new vocabulary*.
- **Consequence for P4 and P7:** if refinement does not work, state whether NSIF must be authored as a full sibling profile (duplicating ~226 field definitions) or whether adding a precedence rule to the compiler is the smaller change, with a one-paragraph recommendation.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain.io
git add docs/superpowers/notes/2026-08-01-profile-refinement-audit.md \
        specification/profiles/nitf/test/refinement-probe.ttl
git commit -m "docs(nitf): record profile refinement capability audit for P4/P7"
```

---

## Completion criteria for P0

P0 is done when all of the following hold:

1. `./gradlew test` is green in `hexplain-tools` (both modules).
2. `python -m pyshacl` reports `Conforms: True` on both positive vocabulary fixtures and `Conforms: False` on both negative fixtures.
3. `ConformanceEndToEndTest` passes: a three-defect file yields exactly three findings, each attributed to a requirement and carrying that requirement's discrepancy type.
4. `CoverageReport.uncovered()` runs against a loaded rule set and returns the gap list.
5. The refinement audit decision record exists and states a verdict.

At that point the conformance layer is real and P1 can begin authoring NITF 2.1 requirements and constraints against a stable vocabulary and HEL surface.
