# NITF P1 — Blockers Cleared and First Real Conformance Rules

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `nitf.ttl` compile and parse a real NITF file, then express MIL-STD-2500C **file-header** (Table A-1) requirements as executable `conf:Constraint`s so the P0 engine reports genuine NITF conformance findings.

**Scope reduction from the phase brief, stated deliberately:** the brief named file-header *and* image-subheader requirements. Image-subheader (Table A-3) rules are deferred, because a rule can only be exercised against bytes that exist and the synthesized fixture is header-only (`NUMI=000`). Adding Table A-3 requires `NitfFileBuilder` to emit a real image segment — subheader, band records and a pixel block — which is a phase-sized change and is the natural opening of P2. Authoring A-3 rules now would produce constraints that never evaluate, which is precisely the silent-zero-evaluation failure the P0 engine was hardened against.

**Architecture:** Four blockers found during P0 are cleared first — three of them stop `nitf.ttl` loading at all. Then a synthesized, byte-verified NITF 2.1 file becomes the fixture that replaces P0's four-field synthetic stand-in. Finally, requirements are transcribed into `nitf-req.ttl` and rules into `nitf-conf.ttl`, and the whole pipeline runs end to end with positive and negative variants.

**Tech Stack:** Kotlin 2.2.10 (JVM), Apache Jena 5.5.0, JUnit 5.10.2, Gradle version catalog. RDF in Turtle with SHACL shapes validated by pySHACL 0.30.1 / Python 3.11.4.

## Global Constraints

- **Two repositories.** `d:\work\hexplain-tools` holds Kotlin; `d:\work\hexplain.io` holds profiles, vocabularies and requirement/rule files. Each task states its repo. Never stage files from the other repo in one commit.
- **Stage explicitly.** `git add <exact paths>` only. Never `git add -A`, never `git add .`, never `git commit -am`.
- **Baselines that must stay green:** hexplain-tools `./gradlew test` — core 231, hdl 102. Report exact counts each task.
- **New constructor/function parameters must have defaults** so existing call sites keep compiling.
- **`RecoveryPolicy.STRICT` behaviour must not change.** Only COLLECT gains capability.
- **No disjunctive (`||`) assertions in tests.** An assertion satisfied by two different outcomes proves nothing. Four such tests were caught in P0.
- **Prove every new guard by reverting the code it guards** and confirming the test fails, then restoring. Report the observation.
- **No risk categories.** Findings carry requirement id, discrepancy type and location only.
- **Namespaces:** `https://hexplain.io/ns/req#`, `https://hexplain.io/ns/conf#`, profile `https://hexplain.io/formats/nitf#`.

---

### Task 1: Widen the enumeration IR to string raw values

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/ir/Model.kt:56` (`EnumValueIR`)
- Test: `core/src/test/kotlin/io/hexplain/core/ir/EnumValueIRTest.kt`

**Interfaces:**
- Consumes: nothing.
- Produces: `data class EnumValueIR(val rawValue: Any, val symbol: String? = null)` where `rawValue` is `Long` or `String`. `EnumerationIR.lookup(raw: Any): String?` returning the symbol when one exists, else null.

Why: `EnumValueIR(rawValue: Long, symbol: String)` cannot represent NITF's enumerations. Every NITF `bddo:enumRawValue` is a string (`"INT"`, `"B"`, `"P"`), and NITF's enum entries declare no `bddo:enumSymbol` at all.

- [ ] **Step 1: Read the current type and its uses**

Run: `grep -rn "EnumValueIR\|EnumerationIR" core/src/main hdl/src/main`
Record every construction site and every read of `.rawValue`/`.symbol` — each must still compile after the change.

- [ ] **Step 2: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/ir/EnumValueIRTest.kt`:

```kotlin
package io.hexplain.core.ir

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

/** NITF enumerations are string-valued and carry no symbol; the IR must represent both shapes. */
class EnumValueIRTest {

    @Test fun `a numeric enumeration still round-trips`() {
        val e = EnumerationIR(listOf(EnumValueIR(0L, "ex:None"), EnumValueIR(1L, "ex:Deflate")))
        assertEquals("ex:Deflate", e.lookup(1L))
        assertNull(e.lookup(7L))
    }

    @Test fun `a string-valued enumeration resolves by its raw text`() {
        val e = EnumerationIR(listOf(EnumValueIR("INT", "ex:Integer"), EnumValueIR("SI", "ex:SignedInt")))
        assertEquals("ex:Integer", e.lookup("INT"))
        assertNull(e.lookup("R"))
    }

    @Test fun `a symbol-less value is representable and looks up as null`() {
        // NITF declares enumRawValue with no enumSymbol. The value must still be in the
        // enumeration so membership is known, even though there is nothing to map to.
        val e = EnumerationIR(listOf(EnumValueIR("B"), EnumValueIR("P")))
        assertEquals(2, e.values.size)
        assertNull(e.lookup("B"))
    }

    @Test fun `membership is distinguishable from absence`() {
        val e = EnumerationIR(listOf(EnumValueIR("B"), EnumValueIR("P")))
        assertEquals(true, e.contains("B"))
        assertEquals(false, e.contains("Z"))
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.ir.EnumValueIRTest"`
Expected: FAIL — compilation error; `EnumValueIR` takes `Long` and requires a symbol; `contains`/`lookup` unresolved.

- [ ] **Step 4: Widen the type**

In `Model.kt`, replace the `EnumValueIR` declaration and extend `EnumerationIR`:

```kotlin
/**
 * One entry of a value enumeration. [rawValue] is Long for numeric enumerations and String
 * for text enumerations (NITF's BCS-A fields use the latter). [symbol] is the IRI the raw
 * value maps to, and is absent when the profile enumerates permitted values without naming
 * them — membership alone is still meaningful for conformance.
 */
data class EnumValueIR(val rawValue: Any, val symbol: String? = null)
```

Add to `EnumerationIR`:

```kotlin
    /** The symbol IRI for [raw], or null when the value is unknown or has no symbol. */
    fun lookup(raw: Any): String? = values.firstOrNull { it.rawValue == raw }?.symbol

    /** True when [raw] is a declared value of this enumeration. */
    fun contains(raw: Any): Boolean = values.any { it.rawValue == raw }
```

If `EnumerationIR` already declares a lookup-like member, keep the existing name and adapt these bodies to it rather than adding a duplicate — report which you did.

- [ ] **Step 5: Repair the call sites recorded in Step 1**

Any site reading `.symbol` as non-null must handle null. Any site constructing with a `Long` still compiles unchanged. Do not change behaviour for numeric enumerations.

- [ ] **Step 6: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — the four new tests, plus core 231 and hdl 102 baselines still green.

- [ ] **Step 7: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/ir/Model.kt \
        core/src/test/kotlin/io/hexplain/core/ir/EnumValueIRTest.kt
git commit -m "feat(ir): allow string-valued and symbol-less enumeration entries"
```

---

### Task 2: Compile NITF's string enumerations

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt:404-405` (`compileEnumeration`)
- Test: `core/src/test/kotlin/io/hexplain/core/rdf/CompileEnumerationTest.kt`

**Interfaces:**
- Consumes: `EnumValueIR(rawValue: Any, symbol: String? = null)`, `EnumerationIR.contains`, `.lookup` (Task 1).
- Produces: no new types. `compileEnumeration` accepts a string or numeric `bddo:enumRawValue` and treats `bddo:enumSymbol` as optional.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/rdf/CompileEnumerationTest.kt`:

```kotlin
package io.hexplain.core.rdf

import io.hexplain.core.ir.EnumerationIR
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.io.StringReader

/** NITF's enumerations are string-valued with no symbols; both must survive compilation. */
class CompileEnumerationTest {

    private val turtle = """
        @prefix bddo: <https://hexplain.io/ns/bddo#> .
        @prefix ex:   <https://example.org/e#> .

        ex:PVTYPEEnum a bddo:Enumeration ;
            bddo:hasEnumValue
              [ a bddo:EnumValue ; bddo:enumRawValue "INT" ] ,
              [ a bddo:EnumValue ; bddo:enumRawValue "SI" ] ,
              [ a bddo:EnumValue ; bddo:enumRawValue "R" ] .

        ex:NumericEnum a bddo:Enumeration ;
            bddo:hasEnumValue
              [ a bddo:EnumValue ; bddo:enumRawValue 0 ; bddo:enumSymbol ex:None ] ,
              [ a bddo:EnumValue ; bddo:enumRawValue 1 ; bddo:enumSymbol ex:Deflate ] .
    """.trimIndent()

    private fun enumerationNamed(local: String): EnumerationIR? {
        val model = ModelFactory.createDefaultModel()
        RDFDataMgr.read(model, StringReader(turtle), null, Lang.TTL)
        val res = model.getResource("https://example.org/e#$local")
        return RdfToIrCompiler(model).compileEnumerationForTest(res)
    }

    @Test fun `string enumeration values survive compilation`() {
        val e = assertNotNull(enumerationNamed("PVTYPEEnum"))
        assertEquals(3, e!!.values.size)
        assertTrue(e.contains("INT"))
        assertTrue(e.contains("SI"))
        assertTrue(e.contains("R"))
    }

    @Test fun `a symbol-less string enumeration is not silently dropped`() {
        // Before this task the whole enumeration compiled to null, so PVTYPE/IMODE/ICORDS
        // vanished from the IR entirely and no rule could reference them.
        assertNotNull(enumerationNamed("PVTYPEEnum"))
    }

    @Test fun `numeric enumerations with symbols still compile unchanged`() {
        val e = assertNotNull(enumerationNamed("NumericEnum"))
        assertEquals(2, e!!.values.size)
        assertEquals("https://example.org/e#Deflate", e.lookup(1L))
    }
}
```

- [ ] **Step 2: Expose the private method for testing**

`compileEnumeration` is private. Add a test seam to `RdfToIrCompiler` rather than widening the real method's visibility:

```kotlin
    /** Test seam: compiles a single bddo:Enumeration resource. Not part of the public pipeline. */
    internal fun compileEnumerationForTest(enumRes: Resource): EnumerationIR? = compileEnumeration(enumRes)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.rdf.CompileEnumerationTest"`
Expected: FAIL — the two string-enumeration tests fail because `compileEnumeration` returns null (every value maps to null and `values` ends empty).

- [ ] **Step 4: Accept string raw values and optional symbols**

In `compileEnumeration`, replace the two lines that read the raw value and symbol:

```kotlin
            val rawLit = ev.getProperty(BDDO.enumRawValue)?.literal ?: return@mapNotNull null
            // NITF's BCS-A enumerations are text; numeric formats keep Long. Anything else
            // is a profile error and is skipped rather than guessed at.
            val raw: Any = when {
                rawLit.datatypeURI == null || rawLit.datatypeURI.endsWith("#string") -> rawLit.string
                else -> runCatching { rawLit.long }.getOrElse { rawLit.string }
            }
            // enumSymbol is optional: a profile may enumerate permitted values without naming them.
            val symbol = ev.getProperty(BDDO.enumSymbol)?.`object`?.asResource()?.uri
            EnumValueIR(raw, symbol)
```

- [ ] **Step 5: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — three new tests; core and hdl baselines green.

- [ ] **Step 6: Prove the fix bites**

Revert only the `raw`/`symbol` lines to their previous form, re-run `CompileEnumerationTest`, confirm the two string tests FAIL, then restore. Report the observation.

- [ ] **Step 7: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt \
        core/src/test/kotlin/io/hexplain/core/rdf/CompileEnumerationTest.kt
git commit -m "fix(rdf): compile string-valued and symbol-less enumerations"
```

---

### Task 3: Make the stream context region-aware

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt:166-170` (`streamCtx`)
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/StreamContextRegionTest.kt`

**Interfaces:**
- Consumes: nothing.
- Produces: no new types. `streamCtx` reports `remaining` relative to the active region limit rather than the whole buffer.

Why this is a real bug, not just a NITF enabler: `applyRegion` bounds a struct region by capping `buffer.limit()`, but `streamCtx` computes `remaining` as `capacity - position`. So inside any sized struct, `stream.remaining` reports bytes beyond the region and `eof()` never fires at the region end. Task 4 depends on this being correct.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/metacodec/StreamContextRegionTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/**
 * A sized struct bounds its region by capping buffer.limit(). eof() and stream.remaining
 * must respect that bound, otherwise a repeatUntil inside a bounded area never terminates
 * at the right place.
 */
class StreamContextRegionTest {

    private val bytesType = DataTypeIR(name = "bddo:Bytes", baseType = BaseType.BYTES, bitWidth = 8)

    /** Outer(8 bytes total): REGION is a 4-byte sized struct holding two 2-byte elements. */
    private fun formatIR(): FormatIR {
        val element = StructIR(
            name = "t:Element",
            fields = listOf(FieldIR(name = "PAIR", dataType = bytesType, size = 2)),
            repeatUntil = HelParserHelper.parse("eof()"),
        )
        val region = StructIR(
            name = "t:Region",
            fields = listOf(FieldIR(name = "ITEMS", dataType = DataTypeIR(name = "t:Element", baseType = BaseType.BYTES, bitWidth = 8))),
            size = 4,
        )
        val root = StructIR(
            name = "t:Outer",
            fields = listOf(
                FieldIR(name = "REGION", dataType = DataTypeIR(name = "t:Region", baseType = BaseType.BYTES, bitWidth = 8)),
                FieldIR(name = "TRAILER", dataType = bytesType, size = 4),
            ),
        )
        return FormatIR(
            name = "test",
            rootStruct = "t:Outer",
            structs = mapOf("t:Outer" to root, "t:Region" to region, "t:Element" to element),
        )
    }

    @Test
    fun `eof fires at the end of a bounded region, not the end of the stream`() {
        @Suppress("UNCHECKED_CAST")
        val result = Metaparser(formatIR()).parse("AABBZZZZ".toByteArray()) as Map<String, Any>

        @Suppress("UNCHECKED_CAST")
        val region = result["REGION"] as Map<String, Any>
        @Suppress("UNCHECKED_CAST")
        val items = region["ITEMS"] as List<Map<String, Any>>

        // Exactly two 2-byte elements fit the 4-byte region. Region-blind eof() would keep
        // consuming into the trailer and yield four.
        assertEquals(2, items.size)
        assertEquals("AA", String(items[0]["PAIR"] as ByteArray))
        assertEquals("BB", String(items[1]["PAIR"] as ByteArray))
        assertEquals("ZZZZ", String(result["TRAILER"] as ByteArray))
    }
}

/** Small helper so the fixture can express a HEL expression inline. */
object HelParserHelper {
    fun parse(src: String) =
        io.hexplain.core.hel.HelParser(io.hexplain.core.hel.Lexer(src).tokenize()).parse()
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.StreamContextRegionTest"`
Expected: FAIL — more than two items, or a bounds error, because `eof()` is computed against `capacity()`.

- [ ] **Step 3: Make `streamCtx` respect the region limit**

Replace `streamCtx`:

```kotlin
    /**
     * Stream context for HEL. `remaining` is measured against the ACTIVE LIMIT, not the
     * buffer capacity, so that inside a struct region bounded by applyRegion() both
     * `stream.remaining` and `eof()` describe the region rather than the whole file.
     * `length` remains the full stream length, which is what a profile means by it.
     */
    private fun streamCtx(buffer: ByteBuffer): Map<String, Any> = mapOf(
        "length" to buffer.capacity().toLong(),
        "position" to buffer.position().toLong(),
        "remaining" to (buffer.limit() - buffer.position()).toLong()
    )
```

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — the new test plus core 231 and hdl 102 baselines.

If any existing test now fails, it was asserting the region-blind behaviour. Do NOT adjust the new code to restore it — report the failing test and its assertion so it can be judged, since at top level `limit == capacity` and nothing should change there.

- [ ] **Step 5: Prove the fix bites**

Revert `remaining` to `capacity() - position`, re-run the test, confirm FAIL, restore. Report the observation.

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/StreamContextRegionTest.kt
git commit -m "fix(metacodec): measure stream remaining against the region limit"
```

---

### Task 4: Replace the `end-of-region` sentinel in the NITF profile

**Repo:** `hexplain.io`

**Files:**
- Modify: `specification/profiles/nitf/nitf.ttl` lines 239, 247, 407, 415, 501, 580

**Interfaces:**
- Consumes: region-aware `eof()` (Task 3).
- Produces: a profile whose TRE areas terminate correctly. No Kotlin change.

Why: `bddo:repeatUntil "end-of-region"` is not a supported sentinel. `RdfToIrCompiler` lexes it as the HEL arithmetic expression `end - of - region`, so any NITF file containing a TRE dies with an uncaught `HelEvaluationException`. All six sites are TRE areas already bounded by a `sizeFromExpression`, so once `eof()` is region-aware it expresses the intent exactly.

**CRITICAL staging note:** this repo has unrelated files under `specification/`. Stage only `specification/profiles/nitf/nitf.ttl`.

- [ ] **Step 1: Confirm the six sites**

Run: `cd /d/work/hexplain.io && grep -n 'repeatUntil "end-of-region"' specification/profiles/nitf/nitf.ttl`
Expected: exactly six lines — 239, 247, 407, 415, 501, 580. If the count differs, stop and report.

- [ ] **Step 2: Replace the sentinel**

Run: `cd /d/work/hexplain.io && sed -i 's/bddo:repeatUntil "end-of-region"/bddo:repeatUntil "eof()"/g' specification/profiles/nitf/nitf.ttl`

Then verify: `grep -c 'repeatUntil "eof()"' specification/profiles/nitf/nitf.ttl` → 6, and `grep -c 'end-of-region' specification/profiles/nitf/nitf.ttl` → 0.

- [ ] **Step 3: Confirm the profile still validates**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/bddo/bddo.ttl -d specification/profiles/nitf/nitf.ttl -f human
```

Expected: `Conforms: True`. If the harness needs additional ontologies, use the invocation recorded in `specification/profiles/nitf/` or the P0 harness; report exactly what you ran.

- [ ] **Step 4: Commit**

```bash
cd /d/work/hexplain.io
git add specification/profiles/nitf/nitf.ttl
git commit -m "fix(nitf): express TRE-area termination as eof() instead of an unsupported sentinel"
```

---

### Task 4b: Bound a repeating struct field by its own declared size

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (`readFieldBody`, the struct-sequence dispatch)
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/FieldRegionSequenceTest.kt`

**Interfaces:**
- Consumes: `applyRegion(buffer, start, size, outerLimit, structName)`, region-aware `streamCtx` (Task 3), `RecoveryPolicy`/`ParseDiagnostics`.
- Produces: no new types. A struct-typed field that carries `repeatUntil` **and** a declared size (`size`, `sizeFromField` or `sizeFromExpression`) has its sequence bounded to that many bytes.

**Why this task exists.** Added after Task 4's review. The plan assumed `eof()` would bound the NITF TRE areas because they declare `bddo:sizeFromExpression`. It does not: `applyRegion`/`resolveStructSize` fire only from **struct**-level sizing, and when a struct-typed field carries `repeatUntil`, `readFieldBody` dispatches straight to `parseStructSequence`, which never consults the field's own size. A reviewer proved this with a live repro — the sequence over-consumed past the declared boundary and starved the following field with `BufferUnderflowException`. Task 3 fixed the struct-level case; this is its field-level mirror, and Task 8 needs it to parse the real profile.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/metacodec/FieldRegionSequenceTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.hel.HelParser
import io.hexplain.core.hel.Lexer
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/**
 * A struct-typed field carrying repeatUntil must respect its OWN declared size. The NITF TRE
 * areas are shaped exactly this way (sizeFromExpression "UDHDL - 3" plus repeatUntil), and
 * without this bound the sequence runs past the area and consumes the following field.
 */
class FieldRegionSequenceTest {

    private val bytesType = DataTypeIR(name = "bddo:Bytes", baseType = BaseType.BYTES, bitWidth = 8)
    private fun hel(src: String) = HelParser(Lexer(src).tokenize()).parse()

    /** LEN(2 ascii) AREA(struct sequence, LEN bytes) TRAILER(4). */
    private fun formatIR(): FormatIR {
        val record = StructIR(
            name = "t:Record",
            fields = listOf(FieldIR(name = "R", dataType = bytesType, size = 2)),
        )
        val root = StructIR(
            name = "t:Outer",
            fields = listOf(
                FieldIR(name = "LEN", dataType = DataTypeIR(name = "bddo:string", baseType = BaseType.STRING, bitWidth = 8), size = 2),
                FieldIR(
                    name = "AREA",
                    dataType = DataTypeIR(name = "t:Record", baseType = BaseType.BYTES, bitWidth = 8),
                    sizeFromExpression = hel("LEN"),
                    repeatUntil = hel("eof()"),
                ),
                FieldIR(name = "TRAILER", dataType = bytesType, size = 4),
            ),
        )
        return FormatIR(
            name = "test",
            rootStruct = "t:Outer",
            structs = mapOf("t:Outer" to root, "t:Record" to record),
        )
    }

    @Test
    fun `a repeating struct field stops at its declared size and leaves the trailer intact`() {
        // LEN=04 -> AREA is 4 bytes -> exactly two 2-byte records; TRAILER must still read ZZZZ.
        @Suppress("UNCHECKED_CAST")
        val result = Metaparser(formatIR()).parse("04AABBZZZZ".toByteArray()) as Map<String, Any>

        @Suppress("UNCHECKED_CAST")
        val area = result["AREA"] as List<Map<String, Any>>
        assertEquals(2, area.size)
        assertEquals("AA", String(area[0]["R"] as ByteArray))
        assertEquals("BB", String(area[1]["R"] as ByteArray))
        assertEquals("ZZZZ", String(result["TRAILER"] as ByteArray))
    }

    @Test
    fun `a zero-length area yields no records and consumes no bytes`() {
        // NITF writes UDHDL="00000" for an absent TRE area; the sequence must be empty, not
        // an error and not a consumer of the following field.
        @Suppress("UNCHECKED_CAST")
        val result = Metaparser(formatIR()).parse("00ZZZZ".toByteArray()) as Map<String, Any>

        @Suppress("UNCHECKED_CAST")
        val area = result["AREA"] as List<Map<String, Any>>
        assertEquals(0, area.size)
        assertEquals("ZZZZ", String(result["TRAILER"] as ByteArray))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.FieldRegionSequenceTest"`
Expected: FAIL — the sequence consumes past the area, so `AREA` holds too many records and `TRAILER` underflows.

- [ ] **Step 3: Bound the sequence before dispatching**

In `readFieldBody`, at the branch that dispatches a struct-typed field with `repeatUntil` to `parseStructSequence`, resolve the field's own declared size first and cap the buffer for the duration of the sequence:

```kotlin
                // A repeating struct field may declare its own extent (NITF's TRE areas do:
                // sizeFromExpression "UDHDL - 3" plus repeatUntil). applyRegion only ever fires
                // for STRUCT-level sizing, so bound the sequence here or it runs past the area
                // and eats the following field.
                val declared: Int? = when {
                    fieldDef.size != null -> fieldDef.size.toInt()
                    fieldDef.sizeFromField != null ->
                        (context[fieldDef.sizeFromField] as? Number)?.toInt()
                            ?: (context[fieldDef.sizeFromField] as? String)?.trim()?.toIntOrNull()
                    fieldDef.sizeFromExpression != null ->
                        (HelEvaluator(context, parentContext, rootContext, streamContext = streamCtx(buffer))
                            .evaluate(fieldDef.sizeFromExpression) as? Number)?.toInt()
                    else -> null
                }
                if (declared != null) {
                    // A negative or zero extent means the area is absent. NITF writes
                    // UDHDL="00000", and "UDHDL - 3" is then negative — that is an empty area,
                    // not an error.
                    val extent = declared.coerceAtLeast(0)
                    val outer = buffer.limit()
                    val end = applyRegion(buffer, buffer.position(), extent, outer, structDef.name)
                    val seq = parseStructSequence(nestedStructDef, buffer, context, rootContext, fieldDef.repeatUntil, fieldDef.name, baseOffset)
                    buffer.limit(outer)
                    buffer.position(end)
                    return seq
                }
```

Read the surrounding code before editing: use the parameter names actually in scope at that point (`context`, `parentContext`, `rootContext`, `nestedStructDef`, `structDef`, `baseOffset`), and keep the existing unbounded call as the `else` path so fields with no declared size behave exactly as before.

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — both new tests, and both module baselines still green.

- [ ] **Step 5: Prove the fix bites**

Remove the `if (declared != null)` block so the unbounded call is always taken, re-run, confirm BOTH new tests FAIL, restore. Report the observation.

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/FieldRegionSequenceTest.kt
git commit -m "fix(metacodec): bound a repeating struct field by its own declared size"
```

---

### Task 4c: Add a `toNumber()` HEL builtin

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt` (the function dispatch `when`)
- Test: `core/src/test/kotlin/io/hexplain/core/hel/HelToNumberTest.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/FieldRegionSequenceTest.kt` (add the negative-extent case Task 4b could not write)

**Interfaces:**
- Consumes: `stringOperand`, `HelEvaluationException`, the existing function dispatch.
- Produces: `toNumber(x)` — parses numeric text to a number. A `Number` passes through unchanged; a `String` or `ByteArray` is trimmed and parsed as `Long`, or as `Double` when it is not integral; anything else, and any text that is not numeric, raises `HelEvaluationException`.

**Why this task exists.** Added after Task 4b's review, by human ruling. Every NITF numeric field is text: `nitf:BCSN` and `nitf:BCSNpos` both declare `bddo:baseType bddo:baseString` (`nitf.ttl:29-32`), so `context["UDHDL"]` is a Kotlin `String`. All six TRE areas size themselves with `bddo:sizeFromExpression "<LEN> - 3"`, and `HelEvaluator.arithmetic` rejects a non-`Number` operand outright (`HelEvaluator.kt:262-263`), throwing `HelEvaluationException` — a `RuntimeException`, **not** a `HexplainParsingException`, so `parseStruct`'s recovery catch never sees it and it aborts the whole parse even under COLLECT. Task 4b's field-level bound therefore cannot fire for the areas it was written for.

The ruling rejected implicit coercion inside `arithmetic()` — it would change evaluation semantics for every format and silently mask genuine type errors — in favour of an explicit builtin at the call site. This is the same mechanism Task 10's note already named as the way to express the parked `HL <= FL` rule, so it closes that P2 candidate too.

**Scope note:** P1's own fixture does not depend on this. The TRE fields carry `bddo:isPresentIf "UDHDL != '00000'"` and Task 7 writes `UDHDL="00000"`, so the field is skipped and the expression never evaluates. This task makes a TRE-bearing file parseable and lets Task 4b's `coerceAtLeast(0)` be tested at all.

- [ ] **Step 1: Read the dispatch and the arity table**

Run: `grep -n '"trim"\|"len"\|FIXED_ARITY' core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt`
`toNumber` takes one argument. Single-argument builtins (`trim`, `len`) are **not** listed in `FIXED_ARITY` — follow that precedent rather than adding an entry.

- [ ] **Step 2: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/hel/HelToNumberTest.kt`. Follow the construction idiom already used by `HelStringFunctionTest.kt` in the same package — read it first and match how it builds a context and evaluates an expression, rather than inventing a second idiom.

Cases, each asserting one outcome (no `||`):

```
toNumber('00005')                 -> 5L          // zero-padded BCS-N
toNumber('  42  ')                -> 42L         // surrounding space is trimmed
toNumber('-7')                    -> -7L
toNumber('3.5')                   -> 3.5         // non-integral falls to Double
toNumber(UDHDL) - 3               -> 2L          // UDHDL = "00005"; THE NITF SHAPE
toNumber(UDHDL) - 3               -> -3L         // UDHDL = "00000"; the absent-area shape
toNumber(5)                       -> 5L          // a Number passes through
toNumber('ABC')                   -> throws HelEvaluationException
toNumber('')                      -> throws HelEvaluationException
```

The two `toNumber(UDHDL) - 3` cases are the point of the task: they are the exact expression the profile carries, over a `String` field value, and they must be present.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.hel.HelToNumberTest"`
Expected: FAIL — `HelEvaluationException: Unknown function 'toNumber'`.

- [ ] **Step 4: Add the builtin**

In the function dispatch `when`, beside the other single-argument string functions:

```kotlin
            // NITF and other text formats carry numbers as zero-padded text, and arithmetic
            // deliberately refuses to coerce silently. toNumber() is the explicit opt-in.
            "toNumber" -> {
                val v = evaluate(node.args[0])
                if (v is Number) v else {
                    val s = stringOperand(v, "toNumber").trim()
                    s.toLongOrNull() ?: s.toDoubleOrNull()
                        ?: throw HelEvaluationException("toNumber() requires numeric text, got '$s'")
                }
            }
```

Do **not** touch `arithmetic()`. The ruling is that coercion is explicit at the call site and nowhere else.

- [ ] **Step 5: Close Task 4b's untested guard**

Task 4b bounds a repeating struct field by its declared size and coerces a negative extent to zero, but the negative case could not be tested — `hel("LEN - 3")` threw before reaching the guard. Add that case to `FieldRegionSequenceTest.kt` now: a field whose `sizeFromExpression` is `hel("toNumber(LEN) - 3")` with `LEN = "00"`, asserting an empty sequence and an intact trailer. Without it, `coerceAtLeast(0)` could be deleted and every test would still pass.

- [ ] **Step 6: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — the new tests plus both module baselines green. Report exact counts.

- [ ] **Step 7: Prove the fix bites**

Remove the `"toNumber"` branch, re-run `HelToNumberTest` and confirm every case fails with `Unknown function 'toNumber'`; restore. Then delete `coerceAtLeast(0)` in `Metaparser.kt`, re-run `FieldRegionSequenceTest`, and confirm the new negative-extent case FAILS; restore. Report both observations.

- [ ] **Step 8: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt \
        core/src/test/kotlin/io/hexplain/core/hel/HelToNumberTest.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/FieldRegionSequenceTest.kt
git commit -m "feat(hel): add toNumber() for formats that carry numbers as text"
```

---

### Task 4d: Size the TRE areas with `toNumber()`

**Repo:** `hexplain.io`

**Files:**
- Modify: `specification/profiles/nitf/nitf.ttl` lines 239, 247, 407, 415, 501, 580

**Interfaces:**
- Consumes: `toNumber()` (Task 4c) and Task 4b's field-level region bound.
- Produces: six TRE areas whose declared extent actually evaluates. No Kotlin change.

Why: the counterpart to Task 4c in the profile. Until these six sites say `toNumber(...)`, the builtin is unused and the areas still throw. Task 8 copies `nitf.ttl` into test resources, so this must land first.

**CRITICAL staging note:** this repo has unrelated files under `specification/`. Stage only `specification/profiles/nitf/nitf.ttl`.

- [ ] **Step 1: Confirm the six sites**

Run: `cd /d/work/hexplain.io && grep -n 'sizeFromExpression' specification/profiles/nitf/nitf.ttl`
Expected: exactly six, at lines 239, 247, 407, 415, 501, 580, reading `"UDHDL - 3"`, `"XHDL - 3"`, `"UDIDL - 3"`, `"IXSHDL - 3"`, `"SXSHDL - 3"`, `"TXSHDL - 3"`. If the count or the forms differ, stop and report.

- [ ] **Step 2: Wrap each length field**

Each becomes `toNumber(<LEN>) - 3` — for example line 239:

```turtle
    bddo:sizeFromExpression "toNumber(UDHDL) - 3" ; bddo:repeatUntil "eof()" .
```

Change only the `sizeFromExpression` strings. Leave `repeatUntil`, `isPresentIf` and every other predicate exactly as they are.

Then verify: `grep -c 'toNumber(' specification/profiles/nitf/nitf.ttl` → 6, and
`grep -c 'sizeFromExpression "[A-Z]' specification/profiles/nitf/nitf.ttl` → 0.

- [ ] **Step 3: Confirm the profile still validates**

Run the harness Task 4 used and recorded — `python tools/shacl_check.py` for the NITF profile, not a bare two-graph `pyshacl` invocation, which reports four spurious violations because it never merges `bddo.ttl` into the data graph. Expected: `Conforms: True`. Report exactly what you ran.

- [ ] **Step 4: Commit**

```bash
cd /d/work/hexplain.io
git add specification/profiles/nitf/nitf.ttl
git commit -m "fix(nitf): size the TRE areas with toNumber() so the expression evaluates"
```

---

### Task 5: Validate fixed values on string fields

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt:313`
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/FixedValueStringTest.kt`

**Interfaces:**
- Consumes: `recoverable(...)` and `RecoveryPolicy` (P0).
- Produces: no new types. The fixed-value check compares string-typed fields as text.

Why: the check is guarded on `fieldValue is ByteArray`, and `nitf:BCSA` is `bddo:baseString`, so **all nine** `bddo:hasFixedValue` declarations in the NITF profile validate nothing — `FH_FHDR "NITF"`, `FH_FVER "02.10"`, `FH_STYPE "BF01"`, `IS_IM "IM"`, `GS_SY "SY"`, `GS_SFMT "C"`, `TS_TE "TE"`, `DES_DE "DE"`, `RES_RE "RE"`.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/metacodec/FixedValueStringTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

/** bddo:hasFixedValue must bite on string-typed fields; NITF declares all of its on BCS-A. */
class FixedValueStringTest {

    private val stringType = DataTypeIR(name = "bddo:string", baseType = BaseType.STRING, bitWidth = 8)

    private fun formatIR(): FormatIR {
        val fields = listOf(
            FieldIR(name = "FHDR", dataType = stringType, size = 4, fixedValue = "NITF".toByteArray()),
            FieldIR(name = "FVER", dataType = stringType, size = 5, fixedValue = "02.10".toByteArray()),
        )
        return FormatIR(
            name = "test",
            rootStruct = "t:Header",
            structs = mapOf("t:Header" to StructIR(name = "t:Header", fields = fields)),
        )
    }

    @Test fun `a conformant string field produces no diagnostic`() {
        val diags = ParseDiagnostics()
        Metaparser(formatIR(), recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse("NITF02.10".toByteArray())
        assertEquals(0, diags.entries.size)
    }

    @Test fun `a wrong string fixed value is reported under COLLECT`() {
        val diags = ParseDiagnostics()
        Metaparser(formatIR(), recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse("BIIF02.10".toByteArray())
        assertEquals(1, diags.entries.size)
        assertEquals("FHDR", diags.entries[0].fieldName)
        assertEquals(HexplainErrorKind.VALIDATION, diags.entries[0].kind)
        assertEquals(0, diags.entries[0].byteOffset)
    }

    @Test fun `both wrong fixed values are reported in one pass`() {
        val diags = ParseDiagnostics()
        Metaparser(formatIR(), recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse("BIIF02.00".toByteArray())
        assertEquals(listOf("FHDR", "FVER"), diags.entries.map { it.fieldName })
    }

    @Test fun `STRICT still throws on the first wrong string fixed value`() {
        val e = assertThrows<HexplainParsingException> {
            Metaparser(formatIR()).parse("BIIF02.10".toByteArray())
        }
        assertTrue(e.message!!.contains("FHDR"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.FixedValueStringTest"`
Expected: FAIL — the three violation tests find 0 diagnostics and STRICT does not throw, because the check is skipped for `String` values.

- [ ] **Step 3: Compare string-typed fields as text**

Replace the block at `Metaparser.kt:313`:

```kotlin
            if (fieldDef.fixedValue != null && fieldValue is ByteArray) {
```

with a form that covers both representations:

```kotlin
            // bddo:hasFixedValue is declared as text in profiles. A field may parse to a
            // ByteArray or, for a bddo:baseString type, to a String — compare either against
            // the declared bytes. Guarding on ByteArray alone silently skipped every
            // fixed-value declaration in a text-typed profile.
            if (fieldDef.fixedValue != null) {
                val actual: ByteArray? = when (fieldValue) {
                    is ByteArray -> fieldValue
                    is String -> fieldValue.toByteArray(UTF_8)
                    else -> null
                }
                if (actual != null && !actual.contentEquals(fieldDef.fixedValue)) {
```

Keep the existing `recoverable(...)` call and its arguments inside, and close the two blocks correctly. Read the surrounding lines before editing so the brace structure stays intact.

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — four new tests; core and hdl baselines green.

- [ ] **Step 5: Prove the fix bites**

Restore the `is ByteArray` guard, re-run, confirm the three violation tests FAIL, restore the fix. Report the observation.

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/FixedValueStringTest.kt
git commit -m "fix(metacodec): validate fixed values on string-typed fields"
```

---

### Task 6: Recover from truncation under COLLECT

**Repo:** `hexplain-tools`

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (the field-read `catch` in `parseStruct`)
- Test: `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserTruncationTest.kt`

**Interfaces:**
- Consumes: `RecoveryPolicy`, `ParseDiagnostics`, `finishStruct(...)` (P0).
- Produces: no new types. Under COLLECT, a read that runs past the available bytes becomes a `BOUNDS` diagnostic instead of aborting the parse.

Why: a truncated file raises `java.nio.BufferUnderflowException`, which is not a `HexplainParsingException`, so the field-level catch never sees it; it reaches the outer handler at `parse()` and aborts with **zero** diagnostics. Real conformance corpora deliberately include truncated and over-long files.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserTruncationTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

/** A deliberately short file must report a bounds discrepancy, not abort silently. */
class MetaparserTruncationTest {

    private val stringType = DataTypeIR(name = "bddo:string", baseType = BaseType.STRING, bitWidth = 8)

    private fun formatIR(): FormatIR {
        val fields = listOf(
            FieldIR(name = "A", dataType = stringType, size = 4),
            FieldIR(name = "B", dataType = stringType, size = 8),
            FieldIR(name = "C", dataType = stringType, size = 4),
        )
        return FormatIR(
            name = "test",
            rootStruct = "t:S",
            structs = mapOf("t:S" to StructIR(name = "t:S", fields = fields)),
        )
    }

    @Test fun `a truncated file yields a bounds diagnostic instead of aborting`() {
        val diags = ParseDiagnostics()
        // 6 bytes for a 16-byte layout: A reads fine, B runs off the end.
        val result = Metaparser(formatIR(), recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse("AAAABB".toByteArray())

        assertTrue(diags.entries.isNotEmpty(), "truncation must produce at least one diagnostic")
        assertEquals(HexplainErrorKind.BOUNDS, diags.entries[0].kind)
        assertEquals("B", diags.entries[0].fieldName)

        @Suppress("UNCHECKED_CAST")
        val map = result as Map<String, Any>
        assertEquals("AAAA", map["A"], "fields parsed before the truncation must survive")
    }

    @Test fun `STRICT still aborts on truncation`() {
        assertThrows<HexplainParsingException> {
            Metaparser(formatIR()).parse("AAAABB".toByteArray())
        }
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.metacodec.MetaparserTruncationTest"`
Expected: FAIL — a `HexplainParsingException` escapes the COLLECT test, because `BufferUnderflowException` bypasses the field-level catch.

- [ ] **Step 3: Widen the field-read catch**

In `parseStruct`, the field read is wrapped in `catch (e: HexplainParsingException)`. Add bounds exceptions ahead of it so they are converted at the field level, where the field name and offset are known:

```kotlin
            } catch (e: java.nio.BufferUnderflowException) {
                if (recoveryPolicy == RecoveryPolicy.STRICT || diagnostics == null) throw e
                diagnostics.record(
                    ParseDiagnostic(
                        message = "Field '${fieldDef.name}' reads past the end of the available bytes.",
                        kind = HexplainErrorKind.BOUNDS,
                        byteOffset = baseOffset + fieldStartPos,
                        structName = structDef.name,
                        fieldName = fieldDef.name,
                    )
                )
                // The cursor is untrustworthy after a short read, so stop this struct and
                // return what was parsed. Continuing would invent field boundaries.
                return finishStruct(result, buffer, outerLimit, regionEnd, structStartPos, baseOffset)
            } catch (e: IndexOutOfBoundsException) {
```

Give `IndexOutOfBoundsException` the identical body (same message wording, same `BOUNDS` kind, same early return). Under STRICT both rethrow, so `parse()`'s outer handler still converts them exactly as before.

- [ ] **Step 4: Run the tests**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — both new tests; core and hdl baselines green.

- [ ] **Step 5: Prove the fix bites**

Remove the two new catch clauses, re-run, confirm the COLLECT test FAILS with an escaping exception, restore. Report the observation.

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt \
        core/src/test/kotlin/io/hexplain/core/metacodec/MetaparserTruncationTest.kt
git commit -m "fix(metacodec): report truncation as a bounds diagnostic under COLLECT"
```

---

### Task 7: Synthesize a minimal conformant NITF 2.1 file

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/test/kotlin/io/hexplain/core/nitf/NitfFileBuilder.kt`
- Test: `core/src/test/kotlin/io/hexplain/core/nitf/NitfFileBuilderTest.kt`

**Interfaces:**
- Consumes: nothing.
- Produces: `object NitfFileBuilder { fun minimalHeaderOnly(fhdr: String = "NITF", fver: String = "02.10", fdt: String = "20260801120000", fsclas: String = "U"): ByteArray }` — a NITF 2.1 file header with zero image, graphic, text, DES and RES segments, sized exactly per MIL-STD-2500C Table A-1.

No NITF file exists anywhere in either repo, and JITC test datasets require a request with lead time. A byte-exact synthesized header is what lets P1 stop testing against a four-field stand-in.

- [ ] **Step 1: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/nitf/NitfFileBuilderTest.kt`:

```kotlin
package io.hexplain.core.nitf

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/**
 * Field widths are from MIL-STD-2500C Table A-1. The total is asserted so a mis-sized field
 * fails here rather than as a confusing parse error three tasks later.
 */
class NitfFileBuilderTest {

    @Test fun `header-only file has the exact Table A-1 length`() {
        val bytes = NitfFileBuilder.minimalHeaderOnly()
        // FHDR 4 + FVER 5 + CLEVEL 2 + STYPE 4 + OSTAID 10 + FDT 14 + FTITLE 80
        // + FSCLAS 1 + FSCLSY 2 + FSCODE 11 + FSCTLH 2 + FSREL 20 + FSDCTP 2
        // + FSDCDT 8 + FSDCXM 4 + FSDG 1 + FSDGDT 8 + FSCLTX 43 + FSCATP 1
        // + FSCAUT 40 + FSCRSN 1 + FSSRDT 8 + FSCTLN 15 + FSCOP 5 + FSCPYS 5
        // + ENCRYP 1 + FBKGC 3 + ONAME 24 + OPHONE 18 + FL 12 + HL 6
        // + NUMI 3 + NUMS 3 + NUMX 3 + NUMT 3 + NUMDES 3 + NUMRES 3
        // + UDHDL 5 + XHDL 5
        assertEquals(404, bytes.size)
    }

    @Test fun `the leading fields carry the declared fixed values`() {
        val s = String(NitfFileBuilder.minimalHeaderOnly(), Charsets.US_ASCII)
        assertEquals("NITF", s.substring(0, 4))
        assertEquals("02.10", s.substring(4, 9))
        assertEquals("BF01", s.substring(11, 15))
    }

    @Test fun `segment counts are all zero for a header-only file`() {
        val s = String(NitfFileBuilder.minimalHeaderOnly(), Charsets.US_ASCII)
        // NUMI..NUMRES occupy six 3-byte counts ending at HL's boundary; all "000".
        val counts = s.substring(371, 389)
        assertEquals("000000000000000000", counts)
    }

    @Test fun `overridden values appear at their declared offsets`() {
        val s = String(NitfFileBuilder.minimalHeaderOnly(fhdr = "BIIF", fsclas = "S"), Charsets.US_ASCII)
        assertEquals("BIIF", s.substring(0, 4))
        assertEquals("S", s.substring(119, 120))
    }

    @Test fun `FL records the total file length`() {
        val s = String(NitfFileBuilder.minimalHeaderOnly(), Charsets.US_ASCII)
        assertEquals("000000000404", s.substring(342, 354))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.nitf.NitfFileBuilderTest"`
Expected: FAIL — `NitfFileBuilder` unresolved.

- [ ] **Step 3: Build the header**

Create `core/src/test/kotlin/io/hexplain/core/nitf/NitfFileBuilder.kt`:

```kotlin
package io.hexplain.core.nitf

/**
 * Builds byte-exact NITF 2.1 file headers for tests, per MIL-STD-2500C Table A-1.
 *
 * Test-only: real files come from an accredited corpus, but none is available in-repo and
 * obtaining one carries lead time. Every width here is transcribed from Table A-1; the
 * builder asserts nothing itself so a wrong width surfaces in NitfFileBuilderTest.
 */
object NitfFileBuilder {

    /** BCS-A: left-justified, space-filled to [width]. */
    private fun a(value: String, width: Int): String {
        require(value.length <= width) { "value '$value' exceeds field width $width" }
        return value.padEnd(width, ' ')
    }

    /** BCS-N: right-justified, zero-filled to [width]. */
    private fun n(value: Long, width: Int): String = value.toString().padStart(width, '0')

    fun minimalHeaderOnly(
        fhdr: String = "NITF",
        fver: String = "02.10",
        fdt: String = "20260801120000",
        fsclas: String = "U",
    ): ByteArray {
        val head = buildString {
            append(a(fhdr, 4))          // FHDR
            append(a(fver, 5))          // FVER
            append(n(3, 2))             // CLEVEL
            append(a("BF01", 4))        // STYPE
            append(a("HEXPLAIN", 10))   // OSTAID
            append(a(fdt, 14))          // FDT
            append(a("P1 SYNTHETIC HEADER", 80)) // FTITLE
            append(a(fsclas, 1))        // FSCLAS
            append(a("", 2))            // FSCLSY
            append(a("", 11))           // FSCODE
            append(a("", 2))            // FSCTLH
            append(a("", 20))           // FSREL
            append(a("", 2))            // FSDCTP
            append(a("", 8))            // FSDCDT
            append(a("", 4))            // FSDCXM
            append(a("", 1))            // FSDG
            append(a("", 8))            // FSDGDT
            append(a("", 43))           // FSCLTX
            append(a("", 1))            // FSCATP
            append(a("", 40))           // FSCAUT
            append(a("", 1))            // FSCRSN
            append(a("", 8))            // FSSRDT
            append(a("", 15))           // FSCTLN
            append(n(0, 5))             // FSCOP
            append(n(0, 5))             // FSCPYS
            append(n(0, 1))             // ENCRYP
            append("\u0000\u0000\u0000") // FBKGC (3 binary bytes)
            append(a("", 24))           // ONAME
            append(a("", 18))           // OPHONE
        }
        // FL is the total file length including itself; for a header-only file that is the
        // header length. Compose the tail first so the total is known.
        val tail = buildString {
            append(n(404, 6))           // HL
            append(n(0, 3))             // NUMI
            append(n(0, 3))             // NUMS
            append(n(0, 3))             // NUMX
            append(n(0, 3))             // NUMT
            append(n(0, 3))             // NUMDES
            append(n(0, 3))             // NUMRES
            append(n(0, 5))             // UDHDL
            append(n(0, 5))             // XHDL
        }
        val total = head.length + 12 + tail.length
        return (head + n(total.toLong(), 12) + tail).toByteArray(Charsets.US_ASCII)
    }
}
```

- [ ] **Step 4: Run the tests and reconcile the widths**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.nitf.NitfFileBuilderTest"`

If the length assertion fails, the transcription is wrong somewhere. Reconcile against the authoritative widths already encoded in `/d/work/hexplain.io/specification/profiles/nitf/nitf.ttl` — the `nitf:FileHeader` field list carries `bddo:size` for every field and was verified against Table A-1 during the profile work. Adjust the builder AND the expected offsets in the test to match the profile, and report every width you changed.

Expected after reconciliation: PASS — all five tests.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/test/kotlin/io/hexplain/core/nitf/NitfFileBuilder.kt \
        core/src/test/kotlin/io/hexplain/core/nitf/NitfFileBuilderTest.kt
git commit -m "test(nitf): add a byte-exact NITF 2.1 header builder"
```

---

### Task 8: Compile and parse the real NITF profile

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/test/resources/nitf/nitf.ttl` (copy of the profile)
- Create: `core/src/test/kotlin/io/hexplain/core/nitf/NitfProfileParseTest.kt`

**Interfaces:**
- Consumes: Tasks 1-7 — string enumerations, region-aware `eof()`, the `eof()` profile edit, string fixed values, truncation recovery, `NitfFileBuilder`.
- Produces: proof that `nitf.ttl` compiles to a `FormatIR` and parses a synthesized header. This is the task that retires "the layer has never touched the real NITF profile".

- [ ] **Step 1: Copy the profile into test resources**

```bash
cd /d/work/hexplain-tools
mkdir -p core/src/test/resources/nitf
cp /d/work/hexplain.io/specification/profiles/nitf/nitf.ttl core/src/test/resources/nitf/nitf.ttl
```

Record in the test file's KDoc that this is a copy and which commit of hexplain.io it came from (`git -C /d/work/hexplain.io rev-parse --short HEAD`).

- [ ] **Step 2: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/nitf/NitfProfileParseTest.kt`:

```kotlin
package io.hexplain.core.nitf

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.metacodec.ParseDiagnostics
import io.hexplain.core.metacodec.RecoveryPolicy
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * The real NITF 2.1 profile, compiled and run. core/src/test/resources/nitf/nitf.ttl is a
 * copy of hexplain.io specification/profiles/nitf/nitf.ttl.
 */
class NitfProfileParseTest {

    private val rootStruct = "https://hexplain.io/formats/nitf#FileHeader"

    private fun formatIR() = RdfToIrCompiler(
        ProfileLoader().load(checkNotNull(javaClass.getResourceAsStream("/nitf/nitf.ttl")))
    ).compile(rootStruct)

    @Test fun `the NITF profile compiles to a FormatIR`() {
        val ir = formatIR()
        assertTrue(ir.structs.containsKey(rootStruct), "root struct must be present")
        assertTrue(ir.structs.size >= 13, "expected the profile's 13 structs, got ${ir.structs.size}")
    }

    @Test fun `the file header declares its Table A-1 fields`() {
        val header = formatIR().structs.getValue(rootStruct)
        val names = header.fields.map { it.name }
        assertTrue(names.contains("FHDR"), "fields: $names")
        assertTrue(names.contains("FVER"))
        assertTrue(names.contains("FSCLAS"))
        assertTrue(names.contains("NUMI"))
    }

    @Test fun `a conformant synthesized header parses with no diagnostics`() {
        val diags = ParseDiagnostics()
        @Suppress("UNCHECKED_CAST")
        val parsed = Metaparser(formatIR(), recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse(NitfFileBuilder.minimalHeaderOnly()) as Map<String, Any>

        assertEquals(0, diags.entries.size, "diagnostics: ${diags.entries}")
        assertEquals("NITF", (parsed["FHDR"] as String).trim())
        assertEquals("02.10", (parsed["FVER"] as String).trim())
        assertEquals("U", (parsed["FSCLAS"] as String).trim())
    }

    @Test fun `a wrong FHDR is now caught by the profile's declared fixed value`() {
        val diags = ParseDiagnostics()
        Metaparser(formatIR(), recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse(NitfFileBuilder.minimalHeaderOnly(fhdr = "BIIF"))
        assertTrue(diags.entries.any { it.fieldName == "FHDR" }, "diagnostics: ${diags.entries}")
    }
}
```

- [ ] **Step 3: Run test to verify it fails, then iterate**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.nitf.NitfProfileParseTest"`

This is the integration point where the four blocker fixes are proven together. Expect to iterate. When a test fails, diagnose which blocker is still biting before changing anything:
- compile error mentioning an enumeration → Tasks 1-2 incomplete;
- `HelEvaluationException` mentioning `end`, `of` or `region` → Task 4's profile edit did not reach the copied resource; re-copy;
- bounds error on a conformant file → the builder's widths disagree with the profile; reconcile against `nitf.ttl` and fix the BUILDER, not the profile;
- field names differ (e.g. `FH_FHDR` vs `FHDR`) → the profile names fields with a prefix; update the test's expected names to whatever `nitf.ttl` actually declares and report the naming.

Do NOT weaken an assertion to make it pass. Report anything you cannot resolve.

Expected after iteration: PASS — all four tests.

- [ ] **Step 4: Run the full suite**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — both modules green.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/test/resources/nitf/nitf.ttl \
        core/src/test/kotlin/io/hexplain/core/nitf/NitfProfileParseTest.kt
git commit -m "test(nitf): compile and parse the real NITF 2.1 profile"
```

---

### Task 9: Transcribe the file-header requirements

**Repo:** `hexplain.io`

**Files:**
- Create: `specification/profiles/nitf/nitf-req.ttl`
- Test: `specification/profiles/nitf/test/nitf-req-valid.ttl` is not needed — the requirements file is itself validated against the `req` shapes.

**Interfaces:**
- Consumes: `hx-req` vocabulary (`req:Requirement`, `req:requirementId`, `req:fromStandard`, `req:statement`, `req:discrepancyType`, `req:appliesToVersion`).
- Produces: ten `req:Requirement` individuals with ids `MIL-STD-2500C-A1-FHDR`, `-FVER`, `-STYPE`, `-CLEVEL`, `-OSTAID`, `-FDT`, `-FSCLAS`, `-FL`, `-HL`, `-NUMI`, consumed by Task 10.

**CRITICAL staging note:** stage only the one new file.

- [ ] **Step 1: Write the requirements**

Create `specification/profiles/nitf/nitf-req.ttl`:

```turtle
@prefix req:  <https://hexplain.io/ns/req#> .
@prefix nreq: <https://hexplain.io/formats/nitf/req#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Requirements transcribed from MIL-STD-2500C, 01 May 2006, Table A-1 (NITF File Header).
# Statements are paraphrased field constraints from the table's Value Range column; where a
# statement is a paraphrase rather than a quotation the wording stays close to the source.

nreq:FHDR a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-FHDR" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "FHDR shall contain the value NITF." ;
    req:discrepancyType req:Syntactic ;
    req:appliesToVersion "NITF 2.1" .

nreq:FVER a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-FVER" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "FVER shall contain the value 02.10." ;
    req:discrepancyType req:Syntactic ;
    req:appliesToVersion "NITF 2.1" .

nreq:STYPE a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-STYPE" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "STYPE shall contain the value BF01." ;
    req:discrepancyType req:Syntactic ;
    req:appliesToVersion "NITF 2.1" .

nreq:CLEVEL a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-CLEVEL" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "CLEVEL shall be a two-digit value in the range 01 to 99 identifying the complexity level of the file." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "NITF 2.1" .

nreq:OSTAID a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-OSTAID" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "OSTAID shall not be all spaces; it identifies the originating station." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "NITF 2.1" .

nreq:FDT a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-FDT" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "FDT shall be formatted CCYYMMDDhhmmss in Zulu time." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "NITF 2.1" .

nreq:FSCLAS a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-FSCLAS" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "FSCLAS shall be one of T, S, C, R or U." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "NITF 2.1" .

nreq:FL a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-FL" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "FL shall record the total length of the file in bytes." ;
    req:discrepancyType req:Functional ;
    req:appliesToVersion "NITF 2.1" .

nreq:HL a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-HL" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "HL shall record the length of the file header in bytes and shall not exceed FL." ;
    req:discrepancyType req:Functional ;
    req:appliesToVersion "NITF 2.1" .

nreq:NUMI a req:Requirement ;
    req:requirementId "MIL-STD-2500C-A1-NUMI" ;
    req:fromStandard "MIL-STD-2500C, 01 May 2006, Table A-1" ;
    req:statement "NUMI shall be a three-digit count of image segments in the range 000 to 999." ;
    req:discrepancyType req:Semantic ;
    req:appliesToVersion "NITF 2.1" .
```

- [ ] **Step 2: Validate against the req shapes**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/req/shapes.ttl -d specification/profiles/nitf/nitf-req.ttl -f human
```

Expected: `Conforms: True`, exit 0. A failure means a requirement is missing a mandatory property — fix the data, not the shapes.

- [ ] **Step 3: Confirm the ids are unique**

Run: `grep -c 'req:requirementId' specification/profiles/nitf/nitf-req.ttl` → 10, and
`grep -o '"MIL-STD-2500C-A1-[A-Z]*"' specification/profiles/nitf/nitf-req.ttl | sort -u | wc -l` → 10.
A duplicate id would be rejected at load time by `ConformanceRdfLoader`.

- [ ] **Step 4: Commit**

```bash
cd /d/work/hexplain.io
git add specification/profiles/nitf/nitf-req.ttl
git commit -m "feat(nitf): transcribe MIL-STD-2500C Table A-1 file-header requirements"
```

---

### Task 10: Author the file-header constraints

**Repo:** `hexplain.io`

**Files:**
- Create: `specification/profiles/nitf/nitf-conf.ttl`

**Interfaces:**
- Consumes: the ten requirement ids from Task 9; `hx-conf` (`conf:Constraint`, `conf:scope`, `conf:assertion`, `conf:satisfies`, `conf:message`); HEL functions `matches`, `trim`, `datetime`, `substr`.
- Produces: ten `conf:Constraint` individuals scoped to `nitf:FileHeader`, consumed by Task 11.

Field names in assertions MUST match what `nitf.ttl` actually declares — Task 8 Step 3 recorded whether they are `FHDR` or `FH_FHDR`. Use the recorded names verbatim.

- [ ] **Step 1: Confirm the field names**

Run: `cd /d/work/hexplain.io && grep -oE 'rdfs:label "(FHDR|FVER|STYPE|CLEVEL|OSTAID|FDT|FSCLAS|FL|HL|NUMI)[^"]*"' specification/profiles/nitf/nitf.ttl | head -12`

The parsed map is keyed by the field's local name as the compiler produces it. If Task 8 recorded a prefix, apply it consistently below.

- [ ] **Step 2: Write the constraints**

Create `specification/profiles/nitf/nitf-conf.ttl` (substituting the confirmed field names if they carry a prefix):

```turtle
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix nreq: <https://hexplain.io/formats/nitf/req#> .
@prefix nitf: <https://hexplain.io/formats/nitf#> .
@prefix ncon: <https://hexplain.io/formats/nitf/conf#> .

# Executable rules for MIL-STD-2500C Table A-1, scoped to the file header.
# Fixed-width BCS-A fields are space-padded, so text comparisons trim first.

ncon:FHDR a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "trim(FHDR) == 'NITF'" ;
    conf:satisfies nreq:FHDR ;
    conf:message "FHDR must be 'NITF'." .

ncon:FVER a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "trim(FVER) == '02.10'" ;
    conf:satisfies nreq:FVER ;
    conf:message "FVER must be '02.10' for NITF 2.1." .

ncon:STYPE a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "trim(STYPE) == 'BF01'" ;
    conf:satisfies nreq:STYPE ;
    conf:message "STYPE must be 'BF01'." .

ncon:CLEVEL a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "matches(CLEVEL, '[0-9]{2}') and CLEVEL != '00'" ;
    conf:satisfies nreq:CLEVEL ;
    conf:message "CLEVEL must be two digits in 01-99." .

ncon:OSTAID a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "len(trim(OSTAID)) > 0" ;
    conf:satisfies nreq:OSTAID ;
    conf:message "OSTAID must identify the originating station and must not be blank." .

ncon:FDT a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "matches(FDT, '[0-9]{14}')" ;
    conf:satisfies nreq:FDT ;
    conf:message "FDT must be formatted CCYYMMDDhhmmss." .

ncon:FDTNotFuture a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "datetime(FDT, 'yyyyMMddHHmmss') <= evaluationInstant()" ;
    conf:satisfies nreq:FDT ;
    conf:message "FDT states a time in the future." .

ncon:FSCLAS a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "matches(trim(FSCLAS), 'T|S|C|R|U')" ;
    conf:satisfies nreq:FSCLAS ;
    conf:message "FSCLAS must be one of T, S, C, R, U." .

ncon:FL a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "matches(FL, '[0-9]{12}')" ;
    conf:satisfies nreq:FL ;
    conf:message "FL must be a twelve-digit total file length." .

ncon:HL a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "matches(HL, '[0-9]{6}')" ;
    conf:satisfies nreq:HL ;
    conf:message "HL must be a six-digit header length." .

ncon:NUMI a conf:Constraint ;
    conf:scope nitf:FileHeader ;
    conf:assertion "matches(NUMI, '[0-9]{3}')" ;
    conf:satisfies nreq:NUMI ;
    conf:message "NUMI must be a three-digit image-segment count." .
```

**Why `HL <= FL` is not expressed here.** The obvious rule — the header cannot be longer than the file — is deliberately absent. `HL` and `FL` parse as zero-padded strings of *different* widths (6 and 12), and HEL orders strings by code point, so `HL <= FL` would compare `"000404"` against `"000000000404"` and silently give the wrong answer for most inputs. HEL has no string-to-number coercion, so the rule is not expressible today without either a `toNumber()` builtin or a numeric data type on those fields. Record this in the Task 12 outcomes note as a named P2 candidate; do not approximate it with substring arithmetic, which would be a rule that looks right and is wrong.

- [ ] **Step 3: Validate against the conf shapes**

Run:

```bash
cd /d/work/hexplain.io
python -m pyshacl -s specification/conf/shapes.ttl \
  -d specification/profiles/nitf/nitf-conf.ttl \
  -e specification/req/req.ttl \
  -e specification/profiles/nitf/nitf-req.ttl -f human
```

Expected: `Conforms: True`. A `sh:class req:Requirement` violation means a cited requirement is missing from the supplied graphs.

- [ ] **Step 4: Commit**

```bash
cd /d/work/hexplain.io
git add specification/profiles/nitf/nitf-conf.ttl
git commit -m "feat(nitf): author executable rules for the Table A-1 file header"
```

---

### Task 11: Run the rules against real NITF bytes

**Repo:** `hexplain-tools`

**Files:**
- Create: `core/src/test/resources/nitf/nitf-req.ttl`, `core/src/test/resources/nitf/nitf-conf.ttl` (copies)
- Create: `core/src/test/kotlin/io/hexplain/core/nitf/NitfConformanceTest.kt`

**Interfaces:**
- Consumes: `ConformanceRdfLoader`, `ConformanceEngine`, `ParseDiagnosticBridge`, `CoverageReport`, `NitfFileBuilder`, and the profile from Task 8.
- Produces: the P1 gate — genuine NITF conformance findings from a real profile against real bytes.

- [ ] **Step 1: Copy the rule files**

```bash
cd /d/work/hexplain-tools
cp /d/work/hexplain.io/specification/profiles/nitf/nitf-req.ttl core/src/test/resources/nitf/
cp /d/work/hexplain.io/specification/profiles/nitf/nitf-conf.ttl core/src/test/resources/nitf/
```

- [ ] **Step 2: Write the failing test**

Create `core/src/test/kotlin/io/hexplain/core/nitf/NitfConformanceTest.kt`:

```kotlin
package io.hexplain.core.nitf

import io.hexplain.core.conformance.ConformanceEngine
import io.hexplain.core.conformance.CoverageReport
import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.metacodec.ParseDiagnostics
import io.hexplain.core.metacodec.RecoveryPolicy
import io.hexplain.core.rdf.ConformanceRdfLoader
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import org.apache.jena.rdf.model.ModelFactory
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/** The P1 gate: real profile, real rules, real NITF bytes, real findings. */
class NitfConformanceTest {

    private val rootStruct = "https://hexplain.io/formats/nitf#FileHeader"
    private val instant = 1785587400L // 2026-08-01T12:30:00Z, fixed for reproducibility

    private fun res(name: String) = checkNotNull(javaClass.getResourceAsStream("/nitf/$name"))

    private fun formatIR() = RdfToIrCompiler(ProfileLoader().load(res("nitf.ttl"))).compile(rootStruct)

    private fun conformanceIR() = ConformanceRdfLoader().load(
        ModelFactory.createDefaultModel().apply {
            add(ProfileLoader().load(res("nitf-req.ttl")))
            add(ProfileLoader().load(res("nitf-conf.ttl")))
        }
    )

    private fun report(bytes: ByteArray) = run {
        val ir = formatIR()
        val diags = ParseDiagnostics()
        @Suppress("UNCHECKED_CAST")
        val parsed = Metaparser(ir, recoveryPolicy = RecoveryPolicy.COLLECT, diagnostics = diags)
            .parse(bytes) as Map<String, Any>
        ConformanceEngine(conformanceIR(), ir, evaluationInstant = instant).evaluate(parsed)
    }

    @Test fun `a conformant header produces no findings`() {
        val r = report(NitfFileBuilder.minimalHeaderOnly())
        assertTrue(r.isConformant(), "findings: ${r.findings.map { it.message }}")
    }

    @Test fun `a wrong FHDR is reported against its requirement`() {
        val r = report(NitfFileBuilder.minimalHeaderOnly(fhdr = "BIIF"))
        assertEquals(1, r.findings.size, "findings: ${r.findings.map { it.message }}")
        assertEquals("MIL-STD-2500C-A1-FHDR", r.findings[0].requirementId)
    }

    @Test fun `a malformed FDT is reported`() {
        val r = report(NitfFileBuilder.minimalHeaderOnly(fdt = "21JAN011230150"))
        assertTrue(r.findings.any { it.requirementId == "MIL-STD-2500C-A1-FDT" },
            "findings: ${r.findings.map { it.requirementId }}")
    }

    @Test fun `an out-of-set FSCLAS is reported`() {
        val r = report(NitfFileBuilder.minimalHeaderOnly(fsclas = "X"))
        assertTrue(r.findings.any { it.requirementId == "MIL-STD-2500C-A1-FSCLAS" },
            "findings: ${r.findings.map { it.requirementId }}")
    }

    @Test fun `several independent defects are all reported in one run`() {
        val r = report(NitfFileBuilder.minimalHeaderOnly(fhdr = "BIIF", fsclas = "X", fdt = "21JAN011230150"))
        val ids = r.findings.map { it.requirementId }.toSet()
        assertTrue(ids.contains("MIL-STD-2500C-A1-FHDR"), "ids: $ids")
        assertTrue(ids.contains("MIL-STD-2500C-A1-FSCLAS"), "ids: $ids")
        assertTrue(ids.contains("MIL-STD-2500C-A1-FDT"), "ids: $ids")
        assertFalse(r.isConformant())
    }

    @Test fun `every transcribed requirement has an enforcing rule`() {
        val uncovered = CoverageReport.uncovered(conformanceIR())
        assertEquals(emptyList<String>(), uncovered, "requirements with no constraint: $uncovered")
    }

    @Test fun `coverage lists one row per transcribed requirement`() {
        assertEquals(10, CoverageReport.rows(conformanceIR()).size)
    }
}
```

- [ ] **Step 3: Run and iterate**

Run: `cd /d/work/hexplain-tools && ./gradlew :core:test --tests "io.hexplain.core.nitf.NitfConformanceTest"`

Diagnose failures in this order before changing anything:
- a finding on the conformant file → the builder and a rule disagree; decide which is wrong against MIL-STD-2500C Table A-1 and fix that one, reporting which;
- `IllegalStateException` naming a scope → `conf:scope` does not match the struct IRI the profile declares; fix `nitf-conf.ttl` in hexplain.io, re-copy;
- an unresolvable field name in an assertion → apply the naming recorded in Task 8 Step 3;
- an unexpected extra finding → report which rule fired and why before suppressing anything.

Never weaken an assertion to get green. Expected after iteration: PASS — all seven tests.

- [ ] **Step 4: Run the full suite**

Run: `cd /d/work/hexplain-tools && ./gradlew test`
Expected: PASS — both modules green.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools
git add core/src/test/resources/nitf/nitf-req.ttl \
        core/src/test/resources/nitf/nitf-conf.ttl \
        core/src/test/kotlin/io/hexplain/core/nitf/NitfConformanceTest.kt
git commit -m "test(nitf): first real NITF conformance findings from real bytes"
```

---

### Task 12: Record P1 outcomes and update the handoff

**Repo:** `hexplain.io`

**Files:**
- Modify: `docs/superpowers/notes/2026-08-01-p0-handoff-known-gaps.md`
- Create: `docs/superpowers/notes/2026-08-01-p1-outcomes.md`

**Interfaces:**
- Consumes: results from Tasks 1-11.
- Produces: an accurate statement of what NITF conformance now exists, so P2 is planned from fact.

- [ ] **Step 1: Mark the four gaps closed or still open**

In the handoff note, annotate each of P1-GAP-1 through P1-GAP-4 with `CLOSED in P1 (commit <sha>)` or, if any remains, `STILL OPEN — <reason>`. Do not delete the original text; the mechanism descriptions stay useful.

- [ ] **Step 2: Write the outcomes note**

Create `docs/superpowers/notes/2026-08-01-p1-outcomes.md` recording, with exact numbers taken from the test run rather than from memory:
- which of the four blockers closed, with the commit that closed each;
- how many requirements are transcribed and how many rules enforce them (from `CoverageReport.rows`);
- what the NITF profile can now do: compiles to a FormatIR, parses a synthesized header, reports attributed findings;
- what it still cannot do — explicitly: no image segment is exercised, no TRE is parsed against real bytes, no pixel data is read, only the file header has rules, and Table A-3 is untouched;
- the fixture caveat: the corpus is a synthesized header from `NitfFileBuilder`, not an accredited sample, and a JITC test-data request should be filed before P2 claims anything broader.

- [ ] **Step 3: Commit**

```bash
cd /d/work/hexplain.io
git add docs/superpowers/notes/2026-08-01-p0-handoff-known-gaps.md \
        docs/superpowers/notes/2026-08-01-p1-outcomes.md
git commit -m "docs(nitf): record P1 outcomes and close out the P0 gap list"
```

---

## Completion criteria for P1

1. `./gradlew test` green in hexplain-tools, both modules, with the exact counts recorded.
2. All four P0 blockers annotated CLOSED, or any survivor documented with its reason.
3. `nitf.ttl` compiles to a `FormatIR` and parses a synthesized NITF 2.1 header with zero diagnostics.
4. A header with three independent defects yields findings citing all three requirement ids.
5. `CoverageReport.uncovered()` returns empty over the transcribed requirement set.
6. The outcomes note states plainly what is still untested — image segments, TREs, pixels, Table A-3.

At that point the claim "NITF 2.1 file-header conformance, verified against real bytes" is defensible, and P2 can begin on the geospatial, temporal and security rule families.
