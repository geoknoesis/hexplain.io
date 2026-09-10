# GDAL Profile Wave 2a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a raster written as whitespace-separated ASCII describable and round-trippable, then describe five GDAL drivers that use one.

**Architecture:** Two engine changes in `hexplain-tools/core`. E2 accepts Fortran `D` exponents in an ASCII decimal. E1 adds a third element-extent rule — a *separator* (a run of bytes between tokens) alongside the existing *size* and *terminator* — available only to a repeated text-number field, and a `TextNumberToken` value that carries the raw token and the run that followed it so the writer reproduces the file byte for byte. `MultiDimensionalData` is not touched: an ASCII grid is a flat token array plus declared dimensions, not a 2-D addressable object. Five `.hx` profiles then consume E1, four of them copied into `hexplain-tools` as parity fixtures.

**Tech Stack:** Kotlin 2.2.10 / JUnit 5 (hexplain-tools, Gradle offline), HDL (`.hx`), Python 3 + pyshacl (hexplain-profiles gates, hexplain.io spec tooling), Jena (RDF lowering).

**Spec:** `docs/superpowers/specs/2026-09-09-gdal-profile-wave-2a-design.md` (in `hexplain.io`)

## Global Constraints

- Three sibling checkouts: `d:/work/hexplain-profiles`, `d:/work/hexplain-tools`, `d:/work/hexplain.io`. Every command below names the repo it runs in.
- Profile namespaces are `https://hexplain.io/ns/profile/<name>#`; a file format uses `format <name>`.
- Every profile header carries a `Verification status:` line and ends with a `LIMITS OF THIS DESCRIPTION` block.
- No hand-written `.ttl` beside an `.hx`; the gate compiles the `.hx`.
- **The BDDO vocabulary is owned by `hexplain.io`.** Edit `hexplain.io/specification/bddo/bddo.ttl` FIRST, then run `python tools/sync_spec.py` in `hexplain-tools` to copy it into `core/src/main/resources/bddo.ttl`. `SpecSyncTest` fails if the two drift. Never hand-edit the bundled copy.
- Parity tests that need the corpus start with `assumeTrue(Files.exists(...))` so a checkout without `tests/gdal/cache` skips rather than fails.
- The corpus root, relative to `hexplain-tools/hdl`, is `../tests/gdal/cache/upstream/autotest`.
- The GDAL oracle is `hexplain-tools/tests/gdal/results/oracle.jsonl`, one JSON object per line with `path`, `status`, `driver`, `width`, `height`, `bands`, `data_types`, `pixels_sha256`.
- Gate commands: engine `.\gradlew.bat --offline :core:test --tests "<FQCN>"` and `:hdl:test`; library `python tools/run_gates.py` (hexplain-profiles); spec `python tools/test_gdal_inventory.py` (hexplain.io).
- Commit messages end with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- **Known pre-existing failure:** `core:test`'s `SpecSyncTest` fails when `hexplain.io`'s working tree has uncommitted `specification/` edits from other sessions. Check `git status` in `hexplain.io` before blaming a change in this plan.

---

## File structure

| Repo | Path | Responsibility |
|---|---|---|
| hexplain.io | `specification/bddo/bddo.ttl` | declare `bddo:separatedBy`; widen the `asciiDecimal` comment (modify) |
| hexplain-tools | `core/src/main/resources/bddo.ttl` | synced copy, never hand-edited (generated) |
| hexplain-tools | `core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt` | expose `separatedBy` (modify) |
| hexplain-tools | `core/src/main/kotlin/io/hexplain/core/ir/Model.kt` | `FieldIR.separatedBy` (modify) |
| hexplain-tools | `core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt` | lower `bddo:separatedBy` (modify) |
| hexplain-tools | `core/src/main/kotlin/io/hexplain/core/metacodec/TextNumberToken.kt` | a Number that remembers its bytes (create) |
| hexplain-tools | `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` | `D` exponents; separated element extent (modify) |
| hexplain-tools | `core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt` | emit token + run verbatim (modify) |
| hexplain-tools | `core/src/test/kotlin/io/hexplain/core/metacodec/SeparatedTextArrayTest.kt` | E1 unit tests (create) |
| hexplain-tools | `core/src/test/kotlin/io/hexplain/core/metacodec/FortranExponentTest.kt` | E2 unit tests (create) |
| hexplain-tools | `hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` | `@separated` clause (modify) |
| hexplain-tools | `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt` | emit `bddo:separatedBy` (modify) |
| hexplain-profiles | `profiles/{aaigrid,gsag,grassasciigrid,isg,usgsdem}/<name>.hx` | one format each (create) |
| hexplain-tools | `hdl/src/test/resources/profiles/{aaigrid,gsag,grassasciigrid,usgsdem}/<name>.hx` | byte-identical fixture copies |
| hexplain-tools | `hdl/src/test/kotlin/io/hexplain/hdl/parity/{AaiGrid,Gsag,GrassAsciiGrid,UsgsDem,Isg}ParityTest.kt` | behavioural verification |
| hexplain-tools | `hdl/src/test/kotlin/io/hexplain/hdl/parity/GdalOracle.kt` | read `oracle.jsonl` (create) |
| hexplain.io | `specification/coverage/gdal-drivers.json` | five `profiles` lists (modify) |

---

### Task 1: E2 — Fortran `D` exponents in an ASCII decimal

USGSDEM record A writes doubles as `0.000000000000000D+000` and `6.070921250000000D+005`. `textNumber` parses decimals with `toDoubleOrNull()`, which rejects a `D` exponent, so record A cannot be read without this. E2 is independent of everything else in the plan and ships first.

**Files:**
- Modify: `hexplain.io/specification/bddo/bddo.ttl:317-318`
- Modify: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt:398`, `:1514`
- Create: `hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/FortranExponentTest.kt`

**Interfaces:**
- Produces: `Metaparser` reads `bddo:asciiDecimal` text containing `D`/`d` as an exponent marker. No new API. Task 10 (`usgsdem`) is the only consumer in this plan.

- [ ] **Step 1: Write the failing test**

`hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/FortranExponentTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/**
 * USGSDEM record A writes every double in Fortran's D-exponent form. A field DECLARED an ascii
 * decimal that holds "6.070921250000000D+005" has exactly one valid reading; refusing it means
 * refusing the format.
 */
class FortranExponentTest {

    private val asciiDecimal = DataTypeIR(
        name = "https://hexplain.io/ns/bddo#asciiDecimal",
        baseType = BaseType.FLOAT,
        bitWidth = 0)

    private fun formatOf(width: Long): FormatIR {
        val field = FieldIR(name = "value", dataType = asciiDecimal, size = width)
        val struct = StructIR(name = "Root", fields = listOf(field))
        return FormatIR(name = "test", rootStruct = "Root", structs = mapOf("Root" to struct))
    }

    private fun readValue(text: String): Any? {
        val ir = formatOf(text.length.toLong())
        val parsed = Metaparser(ir).parse(text.toByteArray()) as Map<*, *>
        return parsed["value"]
    }

    @Test
    fun `reads an uppercase D exponent as a power of ten`() {
        assertEquals(607092.125, (readValue("6.070921250000000D+005") as Number).toDouble())
    }

    @Test
    fun `reads a lowercase d exponent`() {
        assertEquals(0.03, (readValue("3.0d-002") as Number).toDouble())
    }

    @Test
    fun `reads a zero with a D exponent`() {
        assertEquals(0.0, (readValue("0.000000000000000D+000") as Number).toDouble())
    }

    @Test
    fun `still reads an ordinary E exponent`() {
        assertEquals(50.0, (readValue(".500E+02") as Number).toDouble())
    }

    @Test
    fun `still reads a plain decimal`() {
        assertEquals(-1.234567890123, (readValue("-1.234567890123") as Number).toDouble())
    }
}
```

- [ ] **Step 2: Run the test and confirm it fails**

Run, in `hexplain-tools`:

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.metacodec.FortranExponentTest"
```

Expected: the three `D`-exponent tests FAIL with a `HexplainParsingException` saying the field "is declared as a number written as text (asciiDecimal) but holds '6.070921250000000D+005', which is not a finite decimal". The two `E`/plain tests PASS — they are the regression guard.

If `FormatIR`/`StructIR`/`DataTypeIR` constructor arguments do not match, read `core/src/main/kotlin/io/hexplain/core/ir/Model.kt` and correct the test's construction. Do NOT change the assertions.

- [ ] **Step 3: Make the decimal reader accept a D exponent**

In `Metaparser.kt`, `textNumber` (around line 1514), the decimal branch currently reads:

```kotlin
            text.toDoubleOrNull()?.takeIf { it.isFinite() }
```

Replace it with:

```kotlin
            fortranDouble(text)?.takeIf { it.isFinite() }
```

Add this private helper immediately after `textNumber`:

```kotlin
    /**
     * Fortran writes a double-precision exponent with D where C writes E, and USGSDEM record A is
     * written by Fortran. The marker carries no other meaning inside a field DECLARED an ascii
     * decimal, so it is accepted rather than described by a vocabulary term of its own. A single
     * marker is required: "1D2D3" stays an error.
     */
    private fun fortranDouble(text: String): Double? {
        val marker = text.indexOfFirst { it == 'D' || it == 'd' }
        if (marker < 0) return text.toDoubleOrNull()
        if (text.indexOfLast { it == 'D' || it == 'd' } != marker) return null
        return (text.substring(0, marker) + "E" + text.substring(marker + 1)).toDoubleOrNull()
    }
```

- [ ] **Step 4: Apply the same rule to the delimited-table path**

`Metaparser.kt:398` coerces a delimited text value to the field's type:

```kotlin
        BaseType.FLOAT -> raw.trim().toDoubleOrNull() ?: raw
```

Replace with:

```kotlin
        BaseType.FLOAT -> fortranDouble(raw.trim()) ?: raw
```

A delimited column declared a decimal is the same declaration as a fixed-width field declared a decimal; leaving one of the two behind would be an inconsistency a profile author would trip over.

- [ ] **Step 5: Run the test and confirm it passes**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.metacodec.FortranExponentTest"
```

Expected: 5 PASS.

- [ ] **Step 6: Run the surrounding regression suites**

```
.\gradlew.bat --offline :core:test --tests "*TextNumber*" --tests "*Delimited*" --tests "*Metaparser*"
```

Expected: all PASS. These cover the two call sites just changed.

- [ ] **Step 7: Widen the specification comment**

In `hexplain.io`, `specification/bddo/bddo.ttl:317-318`, the `asciiDecimal` comment says "Accepts leading sign, decimal point and exponent." Replace that sentence with:

```
Accepts leading sign, decimal point and an exponent introduced by E, e, D or d -- Fortran writes a double-precision exponent with D, and formats written by Fortran (USGSDEM record A) use it.
```

- [ ] **Step 8: Sync the vocabulary into the engine and verify**

In `hexplain-tools`:

```
python tools/sync_spec.py
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.rdf.SpecSyncTest"
```

Expected: PASS, and `git diff --stat core/src/main/resources/bddo.ttl` shows the comment change only.

- [ ] **Step 9: Commit, in both repos**

In `hexplain.io`:

```bash
git add specification/bddo/bddo.ttl
git commit -m "spec(bddo): an ascii decimal accepts the D exponent Fortran writes

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

In `hexplain-tools`:

```bash
git add core/src/main/resources/bddo.ttl core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt core/src/test/kotlin/io/hexplain/core/metacodec/FortranExponentTest.kt
git commit -m "feat(core): read the D exponent Fortran writes in an ascii decimal

USGSDEM record A writes every double as 0.000000000000000D+000. A field
declared an ascii decimal that holds one has a single valid reading, so the
marker is accepted at both text-number call sites rather than described by a
vocabulary term of its own.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---


### Task 2: E1 vocabulary and IR — `bddo:separatedBy`

A third element-extent rule beside `bddo:size` and `bddo:terminator`. **A separator is a run; a terminator is a sequence.** The distinction is load-bearing: in a delimited table an empty field between two delimiters is meaningful, so a separator must never be implemented by widening `readUntilTerminator`.

**Files:**
- Modify: `hexplain.io/specification/bddo/bddo.ttl` (property near `:repeatUntil`, line ~203; `bddo:FieldShape` constraint, line ~390)
- Modify: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt`
- Modify: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/ir/Model.kt` (`FieldIR`)
- Modify: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt` (~line 403 and ~459)
- Test: `hexplain-tools/core/src/test/kotlin/io/hexplain/core/rdf/SeparatedByLoweringTest.kt`

**Interfaces:**
- Produces: `FieldIR.separatedBy: String?` — `"whitespace"` or null. Tasks 3, 4 and 5 all consume this exact property name and value.

- [ ] **Step 1: Declare the property in the specification**

In `hexplain.io`, `specification/bddo/bddo.ttl`, immediately after the `:repeatUntil` line (~203):

```
:separatedBy            a owl:DatatypeProperty ; rdfs:label "separated by" ; rdfs:range xsd:string ;
    rdfs:comment "The element extent of a repeated field whose elements are separated rather than sized or terminated: each element is preceded and followed by a run of separator bytes, and the run belongs to the element that owns it so the byte sequence can be rebuilt exactly. The only defined value is \"whitespace\" (space, tab, CR, LF). A separator is a RUN and a terminator is a SEQUENCE: between two delimiters of a delimited table an empty value is meaningful, whereas an empty run is not a value at all. Permitted only on a repeated field whose data type is a number written as text." .
```

- [ ] **Step 2: Constrain it in `bddo:FieldShape`**

In the same file, inside `bddo:FieldShape` beside the `bddo:terminator` constraint (~line 390):

```
    sh:property [ sh:path bddo:separatedBy ; sh:datatype xsd:string ; sh:maxCount 1 ; sh:in ( "whitespace" ) ] ;
    sh:not [ sh:and (
        [ sh:property [ sh:path bddo:separatedBy ; sh:minCount 1 ] ]
        [ sh:property [ sh:path bddo:size ; sh:minCount 1 ] ] ) ] ;
    sh:not [ sh:and (
        [ sh:property [ sh:path bddo:separatedBy ; sh:minCount 1 ] ]
        [ sh:property [ sh:path bddo:terminator ; sh:minCount 1 ] ] ) ] ;
```

An extent is one thing or another; declaring two contradicts the bytes.

- [ ] **Step 3: Sync and confirm the vocabulary still validates**

In `hexplain-tools`:

```
python tools/sync_spec.py
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.rdf.SpecSyncTest"
```

Expected: PASS.

- [ ] **Step 4: Write the failing lowering test**

`hexplain-tools/core/src/test/kotlin/io/hexplain/core/rdf/SeparatedByLoweringTest.kt`:

```kotlin
package io.hexplain.core.rdf

import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

/** bddo:separatedBy must survive lowering, or a profile that declares it is silently read as a zero-width field. */
class SeparatedByLoweringTest {

    private val turtle = """
        @prefix bddo: <https://hexplain.io/ns/bddo#> .
        @prefix ex:   <https://example.org/t#> .
        ex:Root a bddo:Struct ; bddo:hasField ( ex:cells ex:plain ) .
        ex:cells a bddo:Field ; bddo:name "cells" ; bddo:dataType bddo:asciiDecimal ;
            bddo:repeatCount 4 ; bddo:separatedBy "whitespace" .
        ex:plain a bddo:Field ; bddo:name "plain" ; bddo:dataType bddo:asciiInteger ; bddo:size 3 .
    """.trimIndent()

    private fun compile(): io.hexplain.core.ir.FormatIR {
        val model = ModelFactory.createDefaultModel()
        RDFDataMgr.read(model, turtle.byteInputStream(), Lang.TTL)
        for (vocab in listOf("/bddo.ttl", "/core.ttl", "/dlv.ttl")) {
            val s = javaClass.getResourceAsStream(vocab) ?: error("bundled $vocab missing")
            s.use { RDFDataMgr.read(model, it, Lang.TTL) }
        }
        return RdfToIrCompiler(model).compile("https://example.org/t#Root")
    }

    @Test
    fun `lowers separatedBy onto the field that declares it`() {
        val fields = compile().structs.getValue("https://example.org/t#Root").fields
        assertEquals("whitespace", fields.single { it.name == "cells" }.separatedBy)
    }

    @Test
    fun `leaves a field that does not declare it alone`() {
        val fields = compile().structs.getValue("https://example.org/t#Root").fields
        assertNull(fields.single { it.name == "plain" }.separatedBy)
    }
}
```

- [ ] **Step 5: Run it and confirm it fails to compile**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.rdf.SeparatedByLoweringTest"
```

Expected: COMPILE FAILURE — `separatedBy` is not a member of `FieldIR`. That is the correct failure.

If `FormatIR.structs` is keyed differently than by root IRI, read `Model.kt` and adjust the lookup. Do NOT weaken the assertions.

- [ ] **Step 6: Add the vocabulary constant**

In `BDDO.kt`, beside `repeatUntil`:

```kotlin
    val separatedBy: Property = m_property("separatedBy")
```

- [ ] **Step 7: Add the IR property**

In `Model.kt`, in `FieldIR`, immediately after `numericBase`:

```kotlin
    /**
     * Element extent for a repeated text-number field whose elements are separated rather than
     * sized or terminated (bddo:separatedBy). Only "whitespace" is defined. Mutually exclusive
     * with size and terminator, which SHACL enforces.
     */
    val separatedBy: String? = null,
```

Add the matching `@property` line to the `FieldIR` KDoc block above the class.

- [ ] **Step 8: Lower it**

In `RdfToIrCompiler.kt`, beside the `trimNull` read (~line 403):

```kotlin
        val separatedBy = fieldRes.getProperty(BDDO.separatedBy)?.literal?.string?.also {
            if (it != "whitespace") throw IllegalArgumentException(
                "bddo:separatedBy on ${fieldRes.uri ?: fieldRes} is \"$it\"; the specification defines only \"whitespace\".")
        }
```

and pass it in the `FieldIR(...)` construction beside `numericBase = numericBase,` (~line 458):

```kotlin
            separatedBy = separatedBy,
```

- [ ] **Step 9: Run the test and confirm it passes**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.rdf.SeparatedByLoweringTest"
```

Expected: 2 PASS.

- [ ] **Step 10: Commit, in both repos**

In `hexplain.io`:

```bash
git add specification/bddo/bddo.ttl
git commit -m "spec(bddo): a separated element extent, for a raster written as text

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

In `hexplain-tools`:

```bash
git add core/src/main/resources/bddo.ttl core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt core/src/main/kotlin/io/hexplain/core/ir/Model.kt core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt core/src/test/kotlin/io/hexplain/core/rdf/SeparatedByLoweringTest.kt
git commit -m "feat(core): lower bddo:separatedBy onto the field that declares it

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: E1 parser — the separated element read

**Files:**
- Create: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/TextNumberToken.kt`
- Modify: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (`readOneElement`, after the `charset` line ~1306)
- Test: `hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/SeparatedTextArrayTest.kt`

**Interfaces:**
- Produces: `TextNumberToken(value: Number, text: String, lead: String, trail: String) : Number()`. Task 4 writes it; the parity tests in Tasks 6-10 read it as a `Number`.
- **Ownership rule, relied on by Task 4:** an element consumes *leading run, then token, then trailing run*. Every separator byte is therefore owned by exactly one element — the first element owns a file's indentation, the last owns its final newline, and `lead` is empty on every element but the first.

- [ ] **Step 1: Write the failing test**

`hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/SeparatedTextArrayTest.kt`:

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/**
 * A raster written as whitespace-separated ASCII. The three bodies below are the three dialects
 * GDAL's own AAIGrid samples use, and a description is only worth having if one reading covers
 * all three AND can put each back exactly as it was found.
 */
class SeparatedTextArrayTest {

    private val asciiDecimal = DataTypeIR(
        name = "https://hexplain.io/ns/bddo#asciiDecimal",
        baseType = BaseType.FLOAT,
        bitWidth = 0)

    private fun gridOf(count: Long): FormatIR {
        val cells = FieldIR(
            name = "cells", dataType = asciiDecimal,
            repeatCount = count, separatedBy = "whitespace")
        val struct = StructIR(name = "Root", fields = listOf(cells))
        return FormatIR(name = "test", rootStruct = "Root", structs = mapOf("Root" to struct))
    }

    private fun cells(body: String, count: Long): List<*> {
        val parsed = Metaparser(gridOf(count)).parse(body.toByteArray()) as Map<*, *>
        return parsed["cells"] as List<*>
    }

    private fun values(body: String, count: Long): List<Double> =
        cells(body, count).map { (it as Number).toDouble() }

    @Test
    fun `reads single-space separators with a leading indent`() {
        assertEquals(listOf(1.0, 2.0, 3.0, 4.0), values("    1 2 3 4\n", 4))
    }

    @Test
    fun `reads column-padded separators`() {
        assertEquals(listOf(107.0, 123.0, 132.0), values("    107    123    132\n", 3))
    }

    @Test
    fun `reads one value per line with CRLF`() {
        assertEquals(listOf(0.0, 50.0), values("    .000E+00\r\n    .500E+02\r\n", 2))
    }

    @Test
    fun `reads across a blank line, as Surfer writes a grid`() {
        assertEquals(listOf(181.0, 115.0, 173.0), values("181 \r\n115 \r\n\r\n173 \r\n", 3))
    }

    @Test
    fun `the first element owns the leading run and the last owns the trailing one`() {
        val parsed = cells("    1 2\n", 2)
        val first = parsed[0] as TextNumberToken
        val last = parsed[1] as TextNumberToken
        assertEquals("    ", first.lead)
        assertEquals("1", first.text)
        assertEquals(" ", first.trail)
        assertEquals("", last.lead)
        assertEquals("2", last.text)
        assertEquals("\n", last.trail)
    }

    @Test
    fun `every separator byte is owned exactly once`() {
        val body = "    107    123\r\n\r\n  132   \n"
        val rebuilt = cells(body, 3).joinToString("") {
            val t = it as TextNumberToken; t.lead + t.text + t.trail
        }
        assertEquals(body, rebuilt)
    }
}
```

- [ ] **Step 2: Run it and confirm it fails**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.metacodec.SeparatedTextArrayTest"
```

Expected: COMPILE FAILURE — `TextNumberToken` does not exist. That is the correct failure.

- [ ] **Step 3: Create the value type**

`hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/TextNumberToken.kt`:

```kotlin
package io.hexplain.core.metacodec

/**
 * A number written as text that remembers the bytes it came from.
 *
 * A grid written as ASCII has no canonical spelling: GDAL's own AAIGrid samples pad to a column
 * width, separate with one space, and put one value per line with CRLF, and a description that
 * privileged any one of them could round trip only that one. So the value carries its own token
 * and the separator runs around it, and the writer replays them. This is the rule text numbers
 * already follow for a space-padded dialect, where the parser yields a String and the writer
 * emits it verbatim; here the value is a Number as well, so a consumer can still do arithmetic.
 *
 * [lead] is the separator run BEFORE the token and [trail] the run after it. An element consumes
 * lead, token, trail in that order, so every separator byte belongs to exactly one element: the
 * first owns a file's indentation and the last owns its final newline.
 */
class TextNumberToken(
    private val value: Number,
    val text: String,
    val lead: String,
    val trail: String
) : Number() {
    override fun toByte(): Byte = value.toByte()
    override fun toShort(): Short = value.toShort()
    override fun toInt(): Int = value.toInt()
    override fun toLong(): Long = value.toLong()
    override fun toFloat(): Float = value.toFloat()
    override fun toDouble(): Double = value.toDouble()

    /** The bytes this token was read from, lead and trail included. */
    fun rebuild(): String = lead + text + trail

    override fun equals(other: Any?): Boolean =
        other is TextNumberToken && text == other.text && lead == other.lead && trail == other.trail
    override fun hashCode(): Int = (31 * lead.hashCode() + text.hashCode()) * 31 + trail.hashCode()
    override fun toString(): String = text
}
```

If Kotlin 2.2.10 still requires `Number.toChar()` to be overridden, add:

```kotlin
    @Deprecated("Number.toChar() is deprecated", ReplaceWith("this.toInt().toChar()"))
    override fun toChar(): Char = value.toInt().toChar()
```

- [ ] **Step 4: Read a separated element**

In `Metaparser.kt`, inside `readOneElement`, immediately AFTER the line

```kotlin
        val charset: Charset = fieldDef.encoding?.let { Charset.forName(it) } ?: UTF_8
```

and BEFORE `val rawData: Any = if (fieldDef.terminator != null) {`, insert:

```kotlin
        if (fieldDef.separatedBy != null) return readSeparatedTextNumber(buffer, effectiveDataType, fieldDef, charset)
```

Then add these members to the class, next to `readUntilTerminator`:

```kotlin
    /** Space, tab, CR and LF: the only separator class bddo:separatedBy defines. */
    private fun isSeparator(b: Byte): Boolean =
        b == 0x20.toByte() || b == 0x09.toByte() || b == 0x0A.toByte() || b == 0x0D.toByte()

    private fun runOfSeparators(buffer: ByteBuffer): String {
        val start = buffer.position()
        while (buffer.hasRemaining() && isSeparator(buffer.get(buffer.position()))) buffer.get()
        val out = ByteArray(buffer.position() - start)
        buffer.duplicate().apply { position(start) }.get(out)
        return String(out, Charsets.US_ASCII)
    }

    /**
     * One element of a separated array: the run before it, the token, and the run after it. Taking
     * the trailing run here is what makes the ownership total -- the last element carries the
     * file's final newline, so the array alone accounts for every byte it spans.
     */
    private fun readSeparatedTextNumber(
        buffer: ByteBuffer, dataType: DataTypeIR, fieldDef: FieldIR, charset: Charset
    ): Any {
        if (!isTextNumber(dataType)) throw HexplainParsingException(
            "Field '${fieldDef.name}' declares bddo:separatedBy, which is the extent of a number " +
                "written as text; ${dataType.name} has a width of its own.",
            HexplainErrorKind.VALIDATION)
        val lead = runOfSeparators(buffer)
        val tokenStart = buffer.position()
        while (buffer.hasRemaining() && !isSeparator(buffer.get(buffer.position()))) buffer.get()
        val tokenBytes = ByteArray(buffer.position() - tokenStart)
        if (tokenBytes.isEmpty()) throw HexplainParsingException(
            "Field '${fieldDef.name}' ran out of values: a separated array needs one token per " +
                "repeat, and the stream held only separators.",
            HexplainErrorKind.BOUNDS)
        buffer.duplicate().apply { position(tokenStart) }.get(tokenBytes)
        budget.materialize(tokenBytes.size)
        val number = textNumber(tokenBytes, dataType, fieldDef, charset)
        return TextNumberToken(number, String(tokenBytes, charset), lead, runOfSeparators(buffer))
    }
```

- [ ] **Step 5: Run the test and confirm it passes**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.metacodec.SeparatedTextArrayTest"
```

Expected: 6 PASS.

- [ ] **Step 6: Prove the delimited-table path is untouched**

```
.\gradlew.bat --offline :core:test --tests "*Delimited*" --tests "*Terminator*" --tests "*TextNumber*"
```

Expected: all PASS. A separator must not have become a terminator; these suites are the guard.

- [ ] **Step 7: Commit**

```bash
git add core/src/main/kotlin/io/hexplain/core/metacodec/TextNumberToken.kt core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt core/src/test/kotlin/io/hexplain/core/metacodec/SeparatedTextArrayTest.kt
git commit -m "feat(core): a separated element extent for a raster written as text

An ASCII grid has no canonical spelling -- GDAL's own AAIGrid samples pad to a
column, separate with one space, and put one value per line with CRLF -- so the
token carries the separator runs around it and stays a Number besides. An
element consumes lead, token, trail in that order, which makes the ownership
total: the first element owns the indent and the last owns the final newline.

A separator is a run and a terminator is a sequence; readUntilTerminator is
untouched, because an empty value between two delimiters of a table is
meaningful and an empty run is not a value at all.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: E1 writer — replay the token and its runs

**Files:**
- Modify: `hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt` (before the `resolveSize` call, ~line 545)
- Test: `hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/SeparatedTextArrayTest.kt` (extend)

**Interfaces:**
- Consumes: `TextNumberToken` from Task 3, and its lead/token/trail ownership rule.
- Produces: `Metawriter` reproduces a separated array byte for byte. Tasks 6-10 assert this through `ProfileFixtures.writeBack`.

- [ ] **Step 1: Add the failing round-trip tests**

Append to `SeparatedTextArrayTest.kt`:

```kotlin
    private fun roundTrip(body: String, count: Long): String {
        val ir = gridOf(count)
        val parsed = Metaparser(ir).parse(body.toByteArray()) as Map<*, *>
        return String(Metawriter(ir).write(parsed))
    }

    @Test
    fun `round trips a single-space dialect`() {
        val body = "    1 2 3 4\n"
        assertEquals(body, roundTrip(body, 4))
    }

    @Test
    fun `round trips a column-padded dialect`() {
        val body = "    107    123    132\n"
        assertEquals(body, roundTrip(body, 3))
    }

    @Test
    fun `round trips one value per line with CRLF`() {
        val body = "    .000E+00\r\n    .500E+02\r\n"
        assertEquals(body, roundTrip(body, 2))
    }

    @Test
    fun `round trips Surfer's blank line between rows`() {
        val body = "181 156 \r\n115 107 \r\n\r\n173 255 \r\n"
        assertEquals(body, roundTrip(body, 6))
    }

    @Test
    fun `writes a grid it did not parse, from plain numbers`() {
        val ir = gridOf(3)
        val written = String(Metawriter(ir).write(mapOf("cells" to listOf(1, 2, 3))))
        assertEquals("1 2 3 ", written)
    }
```

- [ ] **Step 2: Run and confirm the round-trip tests fail**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.metacodec.SeparatedTextArrayTest"
```

Expected: the six Task 3 tests PASS; the five new ones FAIL — the writer does not know `TextNumberToken`, so it either renders a bare number without separators or rejects the value.

- [ ] **Step 3: Replay the token in the writer**

In `Metawriter.kt`, immediately BEFORE

```kotlin
        val size = resolveSize(fieldDef, value, context, parentContext, rootContext)
```

insert:

```kotlin
        if (fieldDef.separatedBy != null) {
            val charsetOf = fieldDef.encoding?.let(Charset::forName) ?: UTF_8
            // A token that came from a parse replays its own bytes; one supplied as a plain number
            // is rendered and given a single space, which is the only separator a writer can invent
            // without claiming to know a dialect it never read.
            val bytes = when (value) {
                is TextNumberToken -> value.rebuild()
                is Number -> java.math.BigDecimal(value.toString()).stripTrailingZeros().toPlainString()
                else -> throw HexplainWritingException(
                    "Separated field '" + fieldDef.name + "' requires a number or a parsed token")
            }
            buffer.put(bytes.toByteArray(charsetOf))
            return value
        }
```

`Metawriter` writes a repeated field one element at a time and cannot see where the array ends, so the `is Number` branch appends one trailing space to EVERY invented element:

```kotlin
                is Number -> java.math.BigDecimal(value.toString()).stripTrailingZeros().toPlainString() + " "
```

The result is `"1 2 3 "` — a trailing separator on the last element. That is correct rather than sloppy: a separated array's last element owns its trailing run (Task 3's ownership rule), and a writer that never read a file has no basis for inventing a different one. Update the Step 1 test expectation to `"1 2 3 "` accordingly. A parsed array is unaffected, because `TextNumberToken` replays its own run and never reaches this branch.

- [ ] **Step 4: Run and confirm all pass**

```
.\gradlew.bat --offline :core:test --tests "io.hexplain.core.metacodec.SeparatedTextArrayTest"
```

Expected: 11 PASS.

- [ ] **Step 5: Run the writer regression suites**

```
.\gradlew.bat --offline :core:test --tests "*Metawriter*" --tests "*RoundTrip*"
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt core/src/test/kotlin/io/hexplain/core/metacodec/SeparatedTextArrayTest.kt
git commit -m "feat(core): replay a separated token's own bytes when writing

All three AAIGrid dialects now round trip byte for byte with none of them
privileged, because the token replays what it read rather than being rendered
from its value. A value supplied as a plain number is still writable.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---



### Task 5: HDL surface — the `@separated` clause

**Files:**
- Modify: `hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt` (beside `TrimNullClause`, line ~131)
- Modify: `hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` (annotation `when`, line ~467)
- Modify: `hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt` (clause `when`, line ~346)
- Modify: `hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` (line ~288)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/SeparatedClauseTest.kt`

**Interfaces:**
- Consumes: `BDDO.separatedBy` (Task 2).
- Produces: the HDL spelling `cells : adec repeat [n] @separated`, which emits `bddo:separatedBy "whitespace"`. Tasks 6-9 write exactly this.

- [ ] **Step 1: Write the failing test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/SeparatedClauseTest.kt`:

```kotlin
package io.hexplain.hdl

import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.nio.file.Files

/** `@separated` is the HDL spelling of bddo:separatedBy; without it a profile cannot say it. */
class SeparatedClauseTest {

    private fun compileToTurtle(source: String): String {
        val f = Files.createTempFile("sep", ".hx")
        Files.writeString(f, source)
        val r = HdlCompiler().compileFile(f)
        assertTrue(r.ok, "diagnostics: ${r.diagnostics}")
        val out = java.io.StringWriter()
        org.apache.jena.riot.RDFDataMgr.write(
            java.io.WriterOutputStream(out, Charsets.UTF_8), r.mergedModel(), org.apache.jena.riot.Lang.TTL)
        return out.toString()
    }

    @Test
    fun `emits separatedBy for a separated array`() {
        val ttl = compileToTurtle("""
            format t @namespace "https://example.org/t#"
            @root struct Root {
              n     : anum[2]
              cells : adec repeat [n] @separated
            }
        """.trimIndent())
        assertTrue(ttl.contains("separatedBy"), "no bddo:separatedBy in:\n$ttl")
        assertTrue(ttl.contains("\"whitespace\""), "separatedBy is not \"whitespace\" in:\n$ttl")
    }
}
```

If `RDFDataMgr.write` with a `WriterOutputStream` is awkward, serialise with
`r.mergedModel().write(java.io.StringWriter(), "TTL")` instead — the assertions are what matter.

- [ ] **Step 2: Run it and confirm it fails**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.SeparatedClauseTest"
```

Expected: FAIL — the compiler reports an unknown annotation `@separated`.

- [ ] **Step 3: Add the AST node**

In `Ast.kt`, beside `object TrimNullClause : Clause` (line ~131):

```kotlin
/** `@separated`: this repeated field's elements are separated by runs of whitespace (bddo:separatedBy). */
object SeparatedClause : Clause
```

- [ ] **Step 4: Parse it**

In `Parser.kt`, in the annotation `when` beside `"@trim-null"` (line ~467):

```kotlin
                        "@separated" -> { next(); out.add(SeparatedClause) }
```

- [ ] **Step 5: Emit it**

In `TurtleEmitter.kt`, in the clause `when` beside `TrimNullClause` (line ~346):

```kotlin
            SeparatedClause -> f.addLiteral(BDDO.separatedBy, "whitespace")
```

- [ ] **Step 6: Accept it from the YAML surface**

In `YamlLoader.kt`, beside the `trim-null` line (~288):

```kotlin
        if (m["separated"] == true) out.add(SeparatedClause)
```

The YAML and `.hx` surfaces are held equivalent by `YamlParityTest`; leaving one behind would fail it.

- [ ] **Step 7: Run and confirm it passes**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.SeparatedClauseTest" --tests "*YamlParity*"
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt hdl/src/test/kotlin/io/hexplain/hdl/SeparatedClauseTest.kt
git commit -m "feat(hdl): @separated, the surface spelling of bddo:separatedBy

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `aaigrid` — the profile E1 was built for

19 GDAL-decoded samples across three dialects. This is the task that proves E1 on real files; nothing after it may start until its round-trip passes.

**Files:**
- Create: `hexplain-profiles/profiles/aaigrid/aaigrid.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/aaigrid/aaigrid.hx` (byte-identical copy)
- Create: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GdalOracle.kt`
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/AaiGridParityTest.kt`

**Interfaces:**
- Consumes: `@separated` (Task 5), `ProfileFixtures.formatIR/parseFile/writeBack/sha256` (existing).
- Produces: `GdalOracle.entry(relPath: String): OracleEntry?` with `width: Int`, `height: Int`, `bands: Int`, `dataTypes: List<String>`, `pixelsSha256: String?`, `status: String`. Tasks 7-9 use exactly this.
- Produces the struct IRI `https://hexplain.io/ns/profile/aaigrid#AaiGrid` with fields `header` and `cells`.

- [ ] **Step 1: Settle the container shape before writing the profile**

An AAIGrid file is a key/value header followed by a body IN THE SAME STREAM. `idrisi.hx` uses a `header` container, but there the header is a whole sidecar file. Determine which of the two shapes below compiles AND round-trips, by trying shape A first.

**Shape A — `header` container plus a body field.** Write this to a scratch file and compile it:

```
format probe @namespace "https://example.org/probe#"

header Head @record-separator 0x0A @separator 0x20 @trim @ci {
  "ncols" as ncols : anum
  "nrows" as nrows : anum
}

@root struct Probe {
  head  : Head
  cells : adec repeat [head.ncols * head.nrows] @separated
}
```

Compile it in `hexplain-tools`:

```
.\gradlew.bat --offline :hdl:run --args="compile <path-to-probe.hx>"
```

(If no such task exists, drive `HdlCompiler().compileFile(...)` from a scratch JUnit test.)

**If Shape A compiles and a parse of `"ncols 2\nnrows 1\n1 2\n"` round-trips**, use it — go to Step 2.

**If it does not**, use **Shape B — every line a struct**, which uses only mechanisms proven before this wave plus `@separated`:

```
struct KeywordLine {
  keyword : str @terminator 0x20 @label "keyword, up to its first space"
  value   : adec @separated @label "the value, owning the padding before it and the newline after"
}
```

with the root reading a fixed count of `KeywordLine` and the body following. Shape B round-trips by construction: a terminated string writes back verbatim with its terminator, and a separated token replays its own runs. Its cost is that keywords are positional rather than named, which the profile states as a limit.

Record the choice in the profile header comment. Do NOT proceed until one shape parses and round-trips the three-line probe.

- [ ] **Step 2: Write the oracle reader**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GdalOracle.kt`:

```kotlin
package io.hexplain.hdl.parity

import java.nio.file.Files
import java.nio.file.Path

/**
 * GDAL 3.13.3's recorded decode of the autotest corpus, one JSON object per line. The parity
 * tests compare against what GDAL actually produced rather than against numbers a profile author
 * chose, which is the whole point of keeping it.
 */
object GdalOracle {
    data class Entry(
        val path: String, val status: String, val driver: String,
        val width: Int, val height: Int, val bands: Int,
        val dataTypes: List<String>, val pixelsSha256: String?)

    private val file: Path = Path.of("..", "tests", "gdal", "results", "oracle.jsonl")

    private val entries: Map<String, Entry> by lazy {
        if (!Files.exists(file)) emptyMap() else Files.readAllLines(file)
            .filter { it.isNotBlank() }
            .mapNotNull { line ->
                fun str(k: String): String? =
                    Regex("\"$k\"\\s*:\\s*\"([^\"]*)\"").find(line)?.groupValues?.get(1)
                fun num(k: String): Int? =
                    Regex("\"$k\"\\s*:\\s*(-?\\d+)").find(line)?.groupValues?.get(1)?.toInt()
                val p = str("path") ?: return@mapNotNull null
                p to Entry(
                    path = p,
                    status = str("status") ?: "",
                    driver = str("driver") ?: "",
                    width = num("width") ?: 0,
                    height = num("height") ?: 0,
                    bands = num("bands") ?: 0,
                    dataTypes = Regex("\"data_types\"\\s*:\\s*\\[([^\\]]*)\\]").find(line)
                        ?.groupValues?.get(1)?.split(",")
                        ?.map { it.trim().trim('"') }?.filter { it.isNotEmpty() } ?: emptyList(),
                    pixelsSha256 = str("pixels_sha256"))
            }.toMap()
    }

    /** @param rel path below the corpus root, e.g. "gdrivers/data/aaigrid/float64.asc". */
    fun entry(rel: String): Entry? = entries["autotest/$rel"]

    fun decoded(rel: String): Entry = requireNotNull(entry(rel)) { "no oracle entry for $rel" }
        .also { require(it.status == "decoded") { "$rel is ${it.status}, not decoded" } }
}
```

If the repository already provides a JSON parser on the test classpath (check `hdl/build.gradle.kts` for a Jackson or kotlinx-serialization dependency), use it instead of the regexes above and delete them.

- [ ] **Step 3: Write the failing parity test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/AaiGridParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.DynamicTest
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestFactory
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path

/**
 * AAIGrid against GDAL 3.13.3's recorded decode. The samples disagree on dialect three ways --
 * a padded column layout, one space, and one value per line with CRLF -- so one description
 * covering all of them, and rebuilding each byte for byte, is the claim being tested.
 */
class AaiGridParityTest {
    private val ir by lazy {
        ProfileFixtures.formatIR("aaigrid/aaigrid.hx", "https://hexplain.io/ns/profile/aaigrid#AaiGrid")
    }

    private fun sample(name: String): Path =
        ProfileFixtures.corpus.resolve("gdrivers/data/aaigrid").resolve(name)
            .also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    private fun cellValues(parsed: Map<*, *>): List<Double> =
        (parsed["cells"] as List<*>).map { (it as Number).toDouble() }

    /** GDAL reports a raster band-sequentially in its own data type; pack the tokens the same way. */
    private fun pixels(values: List<Double>, dataType: String): ByteArray {
        val out = ByteArrayOutputStream()
        for (v in values) {
            val b = when (dataType) {
                "Byte" -> byteArrayOf(v.toInt().toByte())
                "Int16" -> ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(v.toInt().toShort()).array()
                "Int32" -> ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(v.toInt()).array()
                "Float32" -> ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putFloat(v.toFloat()).array()
                "Float64" -> ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putDouble(v).array()
                else -> error("unhandled GDAL data type $dataType")
            }
            out.write(b)
        }
        return out.toByteArray()
    }

    private fun checkPixels(name: String) {
        val oracle = GdalOracle.decoded("gdrivers/data/aaigrid/$name")
        val parsed = ProfileFixtures.parseFile(ir, sample(name))
        val values = cellValues(parsed)
        assertEquals(oracle.width * oracle.height, values.size, "$name cell count")
        assertEquals(oracle.pixelsSha256, ProfileFixtures.sha256(pixels(values, oracle.dataTypes.first())),
            "$name pixels")
    }

    @Test fun `single space dialect, float64`() = checkPixels("float64.asc")
    @Test fun `column padded dialect`() = checkPixels("nodata_int.asc")
    @Test fun `CRLF one value per line, scientific notation`() = checkPixels("case_sensitive.ASC")

    /**
     * Every AAIGrid sample in the corpus is rebuilt byte for byte. This is the test of the
     * engine change: only a token that replays its own separator runs can put three different
     * dialects back the way they were found.
     */
    @TestFactory
    fun `every sample round trips`(): List<DynamicTest> {
        val dir = ProfileFixtures.corpus.resolve("gdrivers/data/aaigrid")
        assumeTrue(Files.exists(dir), "corpus not fetched: $dir")
        return Files.list(dir).use { s -> s.toList() }
            .filter { it.toString().lowercase().endsWith(".asc") || it.toString().endsWith(".grd") }
            .map { f ->
                DynamicTest.dynamicTest(f.fileName.toString()) {
                    val original = Files.readAllBytes(f)
                    val parsed = ProfileFixtures.parse(ir, original)
                    assertEquals(
                        original.toList(), ProfileFixtures.writeBack(ir, parsed).toList(),
                        "${f.fileName} did not round trip")
                }
            }
    }
}
```

- [ ] **Step 4: Run it and confirm it fails**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.AaiGridParityTest"
```

Expected: FAIL — `src/test/resources/profiles/aaigrid/aaigrid.hx` does not exist.

- [ ] **Step 5: Write the profile**

`hexplain-profiles/profiles/aaigrid/aaigrid.hx`, using the shape chosen in Step 1 (Shape A shown):

```
// Hexplain Profile — ESRI ArcInfo ASCII Grid (AAIGrid)
//
// A keyword header, one `keyword value` line each, then the raster written as
// whitespace-separated ASCII numbers in row-major order, north row first:
//
//   ncols        5
//   nrows        5
//   xllcorner    440720.000000000000      (or xllcenter)
//   yllcorner    3750120.000000000000     (or yllcenter)
//   cellsize     60.000000000000
//   nodata_value -1.234567890123          (optional)
//       -1.234567890123 -1.234567890123 -1.234567890123 -1.234567890123 -1.234567890123
//
// The body is ONE field of ncols * nrows separated tokens, NOT a dlv layout. A layout cell
// occupies 1..64 bits; these occupy as many characters as they need, and the corpus disagrees
// on how many — a padded column, one space, or one value per line with CRLF. So the tokens
// carry their own separator runs and the grid shape is stated by ncols/nrows as metadata.
//
// Source: ESRI ArcInfo ASCII GRID; GDAL frmts/aaigrid/aaigriddataset.cpp.
// Verification status: parse-verified — AaiGridParityTest in hexplain-tools matches GDAL
// 3.13.3's pixel digest for float64.asc, nodata_int.asc and case_sensitive.ASC, and rebuilds
// every AAIGrid sample in the corpus byte for byte.

format aaigrid @namespace "https://hexplain.io/ns/profile/aaigrid#"

use araster: <https://hexplain.io/ns/aspect/raster#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

header Header @record-separator 0x0A @separator 0x20 @trim @ci
  @comment "One `keyword value` line each; a reader matches keywords case-insensitively."
{
  "ncols"        as ncols       : anum means araster:width  @label "columns"
  "nrows"        as nrows       : anum means araster:height @label "rows"
  "xllcorner"    as xllCorner   : adec means asref:originX  @label "west edge of the lower-left CELL"
  "yllcorner"    as yllCorner   : adec means asref:originY  @label "south edge of the lower-left CELL"
  "xllcenter"    as xllCenter   : adec @label "x of the lower-left cell's CENTRE; alternative to xllcorner"
  "yllcenter"    as yllCenter   : adec @label "y of the lower-left cell's CENTRE; alternative to yllcorner"
  "cellsize"     as cellSize    : adec means asref:scaleX @label "square cell size"
  "nodata_value" as noDataValue : adec means araster:noDataValue @label "optional"
}

@root struct AaiGrid
  @label "ESRI ASCII grid"
  @comment "Keyword header, then ncols * nrows values written as text."
{
  head  : Header
  cells : adec repeat [head.ncols * head.nrows] @separated
          @label "cells, row-major, north row first"
}

// LIMITS OF THIS DESCRIPTION
//
// 1. The body is a FLAT list of ncols * nrows values, not a two-dimensional object. Row r
//    column c is index r * ncols + c. DLV addresses cells of a fixed bit width and these have
//    none; saying otherwise would misdescribe the bytes.
// 2. A corner and a centre georeference are alternative spellings. Both are declared; a file
//    carries one pair, and the other reads as absent.
// 3. cellsize is one number, so a non-square cell cannot be expressed. GDAL's driver has the
//    same restriction.
// 4. The keyword header is matched case-insensitively, as GDAL does, but the profile does not
//    describe the keyword ABBREVIATIONS some writers emit.
// 5. Values are read as decimals whatever their spelling. A file whose body is all integers is
//    still described with a decimal type; the oracle comparison packs to the type GDAL reports.
```

- [ ] **Step 6: Copy the profile into the engine fixtures**

```
copy d:\work\hexplain-profiles\profiles\aaigrid\aaigrid.hx d:\work\hexplain-tools\hdl\src\test\resources\profiles\aaigrid\aaigrid.hx
```

The library gate `test_tools_fixtures` requires these to be byte-identical. Create the directory first.

- [ ] **Step 7: Run the parity test**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.AaiGridParityTest"
```

Expected: 3 pixel tests PASS and every dynamic round-trip test PASSES.

**If a round-trip fails**, the failure is in the ownership rule, not the profile: print the first differing offset and check whether a separator run was dropped at the header/body boundary. Fix `readSeparatedTextNumber` (Task 3) rather than relaxing the assertion.

**If a pixel digest fails**, check the reshape first: GDAL reports AAIGrid north row first, which is the file's own order, so no flip is needed. If the count matches but the digest does not, the data type is the likely cause — read `oracle.dataTypes.first()` for that sample.

- [ ] **Step 8: Run the library gate**

In `hexplain-profiles`:

```
python tools/run_gates.py aaigrid hx fixtures
```

Expected: PASS. (A full `python tools/run_gates.py` takes over ten minutes — one Gradle launch per `.hx` — so filter while iterating and run it whole in Task 10.)

- [ ] **Step 9: Commit, in both repos**

In `hexplain-profiles`:

```bash
git add profiles/aaigrid/aaigrid.hx
git commit -m "feat: AAIGrid, a raster written as whitespace-separated text

Parse-verified against GDAL's pixel digests for all three dialects the corpus
holds, and every sample is rebuilt byte for byte.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

In `hexplain-tools`:

```bash
git add hdl/src/test/resources/profiles/aaigrid/aaigrid.hx hdl/src/test/kotlin/io/hexplain/hdl/parity/GdalOracle.kt hdl/src/test/kotlin/io/hexplain/hdl/parity/AaiGridParityTest.kt
git commit -m "test(hdl): AAIGrid parity against the GDAL oracle, and a reader for it

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `gsag` — Golden Software ASCII, the hardest dialect

Ten values per line, a trailing space before each CRLF, and a blank line between rows. If E1 round-trips this, it round-trips anything in the wave.

**Files:**
- Create: `hexplain-profiles/profiles/gsag/gsag.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/gsag/gsag.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GsagParityTest.kt`

**Interfaces:**
- Consumes: `@separated` (Task 5), `GdalOracle.decoded` (Task 6).
- Produces the struct IRI `https://hexplain.io/ns/profile/gsag#GsagFile` with fields `magic`, `nx`, `ny`, `xlo`, `xhi`, `ylo`, `yhi`, `zlo`, `zhi`, `cells`.

- [ ] **Step 1: Confirm a SCALAR separated field works**

`gsag`'s header is separated tokens that are NOT repeated (`nx`, then `ny`, …). Task 3 placed the separated branch in `readOneElement`, which the repeat loop calls; a field with no `repeat` may take a different path. Verify with a scratch test:

```kotlin
    @Test
    fun `reads a scalar separated field`() {
        val nx = FieldIR(name = "nx", dataType = asciiDecimal, separatedBy = "whitespace")
        val ny = FieldIR(name = "ny", dataType = asciiDecimal, separatedBy = "whitespace")
        val ir = FormatIR(name = "t", rootStruct = "Root",
            structs = mapOf("Root" to StructIR(name = "Root", fields = listOf(nx, ny))))
        val p = Metaparser(ir).parse("20 20\r\n".toByteArray()) as Map<*, *>
        assertEquals(20.0, (p["nx"] as Number).toDouble())
        assertEquals(20.0, (p["ny"] as Number).toDouble())
    }
```

Add it to `SeparatedTextArrayTest`. If it fails because the single-field path never reaches `readOneElement`, add the same one-line branch

```kotlin
        if (fieldDef.separatedBy != null) return readSeparatedTextNumber(buffer, effectiveDataType, fieldDef, charset)
```

to that path too, immediately after its own `charset` line, and commit it with this task.

- [ ] **Step 2: Write the failing parity test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GsagParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path

/**
 * Golden Software ASCII grid. Surfer writes ten values to a line with a trailing space, a CRLF,
 * and a blank line between rows -- the dialect no declarative separator could describe -- so
 * this file is the strongest evidence that a token replaying its own runs is the right model.
 */
class GsagParityTest {
    private val ir by lazy {
        ProfileFixtures.formatIR("gsag/gsag.hx", "https://hexplain.io/ns/profile/gsag#GsagFile")
    }

    private fun sample(): Path =
        ProfileFixtures.corpus.resolve("gdrivers/data/gsg/gsg_ascii.grd")
            .also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    private fun pixelsFloat64(values: List<Double>): ByteArray {
        val out = ByteArrayOutputStream()
        for (v in values) out.write(ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).putDouble(v).array())
        return out.toByteArray()
    }

    @Test
    fun `header and pixels match GDAL`() {
        val oracle = GdalOracle.decoded("gdrivers/data/gsg/gsg_ascii.grd")
        val p = ProfileFixtures.parseFile(ir, sample())
        assertEquals(20, (p["nx"] as Number).toInt())
        assertEquals(20, (p["ny"] as Number).toInt())
        assertEquals(oracle.width * oracle.height, (p["cells"] as List<*>).size)
        val values = (p["cells"] as List<*>).map { (it as Number).toDouble() }
        assertEquals(oracle.pixelsSha256, ProfileFixtures.sha256(pixelsFloat64(values)), "pixels")
    }

    @Test
    fun `rebuilds the file byte for byte, blank lines included`() {
        val original = Files.readAllBytes(sample())
        val parsed = ProfileFixtures.parse(ir, original)
        assertEquals(original.toList(), ProfileFixtures.writeBack(ir, parsed).toList())
    }
}
```

**Note on row order:** GSAG stores the SOUTH row first, and GDAL reports north first. If the digest fails but the count matches, reverse the rows in `values` before packing — `values.chunked(oracle.width).reversed().flatten()` — and say so in the profile's limits block rather than silently in the test.

- [ ] **Step 3: Run it and confirm it fails**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.GsagParityTest"
```

Expected: FAIL — the fixture does not exist.

- [ ] **Step 4: Write the profile**

`hexplain-profiles/profiles/gsag/gsag.hx`:

```
// Hexplain Profile — Golden Software ASCII Grid (GSAG, Surfer 6)
//
//   DSAA          magic
//   nx ny         column and row counts
//   xlo xhi       west and east edges
//   ylo yhi       south and north edges
//   zlo zhi       minimum and maximum value
//   ...           nx * ny values, SOUTH row first, ten to a line with a blank line between rows
//
// Every number in the file, header included, is a separated token: the header's own layout is
// as free as the body's, and describing it any other way would privilege one writer's spacing.
//
// Source: Golden Software Surfer 6 ASCII grid (.grd); GDAL frmts/gsg/gsagdataset.cpp.
// Verification status: parse-verified — GsagParityTest in hexplain-tools matches GDAL 3.13.3's
// pixel digest for autotest/gdrivers/data/gsg/gsg_ascii.grd (20 x 20, Float64) and rebuilds the
// file byte for byte, blank lines and trailing spaces included.

format gsag @namespace "https://hexplain.io/ns/profile/gsag#"

use araster: <https://hexplain.io/ns/aspect/raster#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

@root struct GsagFile
  @label "Surfer 6 ASCII grid"
  @comment "DSAA magic, four header lines of two numbers each, then nx * ny values as text."
{
  magic : ascii[4] @fixed "DSAA" @label "identifies the ASCII generation"
  nx    : anum @separated means araster:width  @label "columns"
  ny    : anum @separated means araster:height @label "rows"
  xlo   : adec @separated means asref:originX  @label "west edge"
  xhi   : adec @separated @label "east edge"
  ylo   : adec @separated means asref:originY  @label "south edge"
  yhi   : adec @separated @label "north edge"
  zlo   : adec @separated @label "minimum value"
  zhi   : adec @separated @label "maximum value"
  cells : adec repeat [nx * ny] @separated @label "cells, row-major, SOUTH row first"
}

// LIMITS OF THIS DESCRIPTION
//
// 1. The body is a FLAT list of nx * ny values. Row r column c is index r * nx + c, counting
//    rows from the SOUTH. A north-up raster is that list reversed by row; the profile states
//    the order rather than performing the flip, because DLV declares dimension order and this
//    is not a DLV layout at all.
// 2. Surfer's blank line between rows is not structural here — it is separator run like any
//    other, owned by the token that precedes it. A file without the blank lines parses the
//    same way and rebuilds without them.
// 3. Surfer's no-data sentinel (1.70141e38) is not declared as araster:noDataValue: it is a
//    convention of the writer, not a field of the file.
// 4. The binary generations of this format (GSBG, Surfer 6; GS7BG, Surfer 7) are different
//    formats with their own headers and are not described here.
```

- [ ] **Step 5: Copy to the fixtures and run**

```
copy d:\work\hexplain-profiles\profiles\gsag\gsag.hx d:\work\hexplain-tools\hdl\src\test\resources\profiles\gsag\gsag.hx
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.GsagParityTest"
```

Expected: 2 PASS.

- [ ] **Step 6: Commit, in both repos**

```bash
# hexplain-profiles
git add profiles/gsag/gsag.hx
git commit -m "feat: Golden Software ASCII grid, header and body both separated tokens

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
# hexplain-tools
git add hdl/src/test/resources/profiles/gsag/gsag.hx hdl/src/test/kotlin/io/hexplain/hdl/parity/GsagParityTest.kt
git commit -m "test(hdl): GSAG parity — Surfer's blank lines rebuild byte for byte

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: `grassasciigrid`

**Files:**
- Create: `hexplain-profiles/profiles/grassasciigrid/grassasciigrid.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/grassasciigrid/grassasciigrid.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GrassAsciiGridParityTest.kt`

**Interfaces:**
- Consumes: `@separated` (Task 5), `GdalOracle.decoded` (Task 6), and the container shape chosen in Task 6 Step 1.
- Produces the struct IRI `https://hexplain.io/ns/profile/grassasciigrid#GrassAsciiGrid`.

- [ ] **Step 1: Write the failing parity test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GrassAsciiGridParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files
import java.nio.file.Path

/** GRASS ASCII grid: a `key: value` header over the same token body, on GDAL's 4 x 6 Int32 sample. */
class GrassAsciiGridParityTest {
    private val ir by lazy {
        ProfileFixtures.formatIR(
            "grassasciigrid/grassasciigrid.hx",
            "https://hexplain.io/ns/profile/grassasciigrid#GrassAsciiGrid")
    }

    private fun sample(): Path =
        ProfileFixtures.corpus.resolve("gdrivers/data/grassasciigrid/grassascii.txt")
            .also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    @Test
    fun `pixels match GDAL`() {
        val oracle = GdalOracle.decoded("gdrivers/data/grassasciigrid/grassascii.txt")
        val p = ProfileFixtures.parseFile(ir, sample())
        val values = (p["cells"] as List<*>).map { (it as Number).toDouble() }
        assertEquals(oracle.width * oracle.height, values.size)
        val out = ByteArrayOutputStream()
        for (v in values) out.write(ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(v.toInt()).array())
        assertEquals(oracle.pixelsSha256, ProfileFixtures.sha256(out.toByteArray()), "pixels")
    }

    @Test
    fun `rebuilds the file byte for byte`() {
        val original = Files.readAllBytes(sample())
        assertEquals(original.toList(), ProfileFixtures.writeBack(ir, ProfileFixtures.parse(ir, original)).toList())
    }
}
```

- [ ] **Step 2: Run it and confirm it fails**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.GrassAsciiGridParityTest"
```

Expected: FAIL — the fixture does not exist.

- [ ] **Step 3: Write the profile**

`hexplain-profiles/profiles/grassasciigrid/grassasciigrid.hx`:

```
// Hexplain Profile — GRASS GIS ASCII Grid
//
//   north: 250.000000
//   south: 0.000000
//   east: 150.000000
//   west: -100.000000
//   rows: 6
//   cols: 4
//   -9999 -9999 5 2
//   ...
//
// A `key: value` header over rows * cols values written as text, NORTH row first.
//
// Source: GRASS GIS r.out.ascii; GDAL frmts/aaigrid/aaigriddataset.cpp (the GRASS branch).
// Verification status: parse-verified — GrassAsciiGridParityTest in hexplain-tools matches GDAL
// 3.13.3's pixel digest for autotest/gdrivers/data/grassasciigrid/grassascii.txt (4 x 6, Int32)
// and rebuilds the file byte for byte.

format grassasciigrid @namespace "https://hexplain.io/ns/profile/grassasciigrid#"

use araster: <https://hexplain.io/ns/aspect/raster#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

header Header @record-separator 0x0A @separator 0x3A @trim @ci
  @comment "Six `key: value` lines; the colon is the key separator and the value is trimmed."
{
  "north" as north : adec means asref:originY @label "north edge"
  "south" as south : adec @label "south edge"
  "east"  as east  : adec @label "east edge"
  "west"  as west  : adec means asref:originX @label "west edge"
  "rows"  as rows  : anum means araster:height
  "cols"  as cols  : anum means araster:width
}

@root struct GrassAsciiGrid
  @label "GRASS ASCII grid"
  @comment "A key: value header, then rows * cols values written as text."
{
  head  : Header
  cells : adec repeat [head.rows * head.cols] @separated
          @label "cells, row-major, north row first"
}

// LIMITS OF THIS DESCRIPTION
//
// 1. The body is a FLAT list of rows * cols values; row r column c is index r * cols + c.
// 2. GRASS's `null:` keyword, which names the no-data spelling, is not declared. The sample
//    does not carry it, so describing it would be an assertion rather than a reading.
// 3. A multi-band GRASS export is a directory of files, not this file, and is out of scope.
```

If Task 6 Step 1 chose Shape B, express this header the same way rather than with a `header` container, and say so in the profile comment.

- [ ] **Step 4: Copy to the fixtures and run**

```
copy d:\work\hexplain-profiles\profiles\grassasciigrid\grassasciigrid.hx d:\work\hexplain-tools\hdl\src\test\resources\profiles\grassasciigrid\grassasciigrid.hx
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.GrassAsciiGridParityTest"
```

Expected: 2 PASS.

- [ ] **Step 5: Commit, in both repos**

```bash
# hexplain-profiles
git add profiles/grassasciigrid/grassasciigrid.hx
git commit -m "feat: GRASS ASCII grid

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
# hexplain-tools
git add hdl/src/test/resources/profiles/grassasciigrid/grassasciigrid.hx hdl/src/test/kotlin/io/hexplain/hdl/parity/GrassAsciiGridParityTest.kt
git commit -m "test(hdl): GRASS ASCII grid parity against the GDAL oracle

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: `usgsdem` — fixed-width ASCII and a tokenized body

The only profile needing both engine changes, and the only one whose body is not a plain grid.

**Files:**
- Create: `hexplain-profiles/profiles/usgsdem/usgsdem.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/usgsdem/usgsdem.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/UsgsDemParityTest.kt`

**Interfaces:**
- Consumes: `@separated` (Task 5), E2 (Task 1), `GdalOracle` (Task 6).
- Produces the struct IRI `https://hexplain.io/ns/profile/usgsdem#UsgsDem` with fields `recordA` and `profiles`.

- [ ] **Step 1: Confirm record A's field offsets against the sample**

Record A is 1024 bytes of fixed-width Fortran output. These offsets were read from
`autotest/gdrivers/data/usgsdem/39079G6_truncated.dem` and must be re-checked against
GDAL's `frmts/usgsdem/usgsdemdataset.cpp` before the profile is trusted:

| Bytes (1-based) | Width | Field |
|---|---|---|
| 1-144 | A144 | quadrangle name and free text |
| 145-150 | I6 | DEM level code |
| 151-156 | I6 | elevation pattern |
| 157-162 | I6 | ground planimetric reference system |
| 163-168 | I6 | zone |
| 169-528 | 15 × D24.15 | map projection parameters |
| 529-534 | I6 | ground units |
| 535-540 | I6 | elevation units |
| 541-546 | I6 | number of sides |
| 547-738 | 8 × D24.15 | four corner coordinate pairs |
| 739-762 | D24.15 | minimum elevation |
| 763-786 | D24.15 | maximum elevation |
| 787-810 | D24.15 | counterclockwise rotation angle |
| 811-816 | I6 | accuracy code |
| 817-852 | 3 × E12.6 | x, y, z resolution |
| 853-858 | I6 | rows |
| 859-864 | I6 | columns |
| 865-1024 | A160 | filler, and in some dialects extra fields |

Verify by reading the sample's bytes at each offset. `usgsdem_with_spaces_after_byte_864.dem`
exists precisely because byte 865 onward varies; describing 865-1024 as filler is what makes
both dialects readable.

- [ ] **Step 2: Write the failing parity test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/UsgsDemParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.DynamicTest
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestFactory
import java.nio.file.Files
import java.nio.file.Path

/**
 * USGSDEM record A is Fortran output -- every double carries a D exponent -- and each following
 * record is one profile of elevations written as text. Every corpus sample is truncated, so the
 * claim tested here is the RECORDS PRESENT, not a complete DEM.
 */
class UsgsDemParityTest {
    private val ir by lazy {
        ProfileFixtures.formatIR("usgsdem/usgsdem.hx", "https://hexplain.io/ns/profile/usgsdem#UsgsDem")
    }

    private fun sample(name: String): Path =
        ProfileFixtures.corpus.resolve("gdrivers/data/usgsdem").resolve(name)
            .also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    @Test
    fun `record A reads its Fortran doubles`() {
        val p = ProfileFixtures.parseFile(ir, sample("39079G6_truncated.dem"))
        val a = p["recordA"] as Map<*, *>
        assertEquals(2, (a["demLevel"] as Number).toInt())
        assertEquals(17, (a["zone"] as Number).toInt())
        // 6.070921250000000D+005 -- unreadable before E2.
        assertEquals(607092.125, (a["swEasting"] as Number).toDouble(), 1e-6)
        assertEquals(310.0, (a["minElevation"] as Number).toDouble(), 1e-6)
        assertEquals(847.0, (a["maxElevation"] as Number).toDouble(), 1e-6)
    }

    @Test
    fun `the first profile's elevations are read as numbers`() {
        val p = ProfileFixtures.parseFile(ir, sample("39079G6_truncated.dem"))
        val first = (p["profiles"] as List<*>).first() as Map<*, *>
        val elevations = (first["elevations"] as List<*>).map { (it as Number).toInt() }
        assertEquals(listOf(349, 349, 354, 353, 353, 355, 357, 360), elevations.take(8))
        assertEquals((first["elevationCount"] as Number).toInt(), elevations.size)
    }

    /** Every sample the profile can parse must also rebuild; a truncated file is still exact bytes. */
    @TestFactory
    fun `every readable sample round trips`(): List<DynamicTest> {
        val dir = ProfileFixtures.corpus.resolve("gdrivers/data/usgsdem")
        assumeTrue(Files.exists(dir), "corpus not fetched: $dir")
        return Files.list(dir).use { s -> s.toList() }.filter { Files.isRegularFile(it) }.map { f ->
            DynamicTest.dynamicTest(f.fileName.toString()) {
                val original = Files.readAllBytes(f)
                val parsed = ProfileFixtures.parse(ir, original)
                assertEquals(original.toList(), ProfileFixtures.writeBack(ir, parsed).toList())
            }
        }
    }
}
```

**If a sample cannot be parsed at all** (a dialect record A does not cover), do NOT delete it from the factory: wrap that one file in an `assumeTrue(false, "<reason>")` and name the reason in the profile's limits block. A skipped, explained sample is evidence; a silently dropped one is not.

- [ ] **Step 3: Run it and confirm it fails**

```
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.UsgsDemParityTest"
```

Expected: FAIL — the fixture does not exist.

- [ ] **Step 4: Write the profile**

`hexplain-profiles/profiles/usgsdem/usgsdem.hx`, using the offsets confirmed in Step 1:

```
// Hexplain Profile — USGS DEM (ASCII, "record A / record B")
//
// A 1024-byte logical record A of fixed-width Fortran fields, then one record per PROFILE
// (a column of elevations running south to north). Every double is written in Fortran's
// D-exponent form; every elevation is written as text.
//
//   record A   1024  name, level, projection parameters, corners, min/max, resolution, counts
//   record B    ...  row, column, element counts, start coordinate, local datum elevation,
//                    min/max, then that many elevations
//
// Source: USGS National Mapping Program, Standards for Digital Elevation Models, part 2;
// GDAL frmts/usgsdem/usgsdemdataset.cpp.
// Verification status: parse-verified — UsgsDemParityTest in hexplain-tools reads record A's
// Fortran doubles and the first profile's elevations on
// autotest/gdrivers/data/usgsdem/39079G6_truncated.dem, and rebuilds every readable sample
// byte for byte. NO sample in the corpus is a complete DEM; see limit 1.

format usgsdem @namespace "https://hexplain.io/ns/profile/usgsdem#"

use araster: <https://hexplain.io/ns/aspect/raster#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

struct RecordA
  @label "logical record A"
  @comment "1024 bytes of fixed-width Fortran fields describing the whole DEM."
{
  quadName     : ascii[144] @label "quadrangle name and free text"
  demLevel     : anum[6]  @label "DEM level code: 1, 2 or 3"
  elevPattern  : anum[6]  @label "elevation pattern: 1 regular, 2 random"
  refSystem    : anum[6]  @label "ground planimetric reference system"
  zone         : anum[6]  @label "reference system zone"
  projParams   : adec[24] repeat [15] @label "map projection parameters, D24.15"
  groundUnits  : anum[6]  @label "0 radians, 1 feet, 2 metres, 3 arc-seconds"
  elevUnits    : anum[6]  @label "1 feet, 2 metres"
  numSides     : anum[6]  @label "sides of the coverage polygon"
  swEasting    : adec[24] @label "SW corner x"
  swNorthing   : adec[24] @label "SW corner y"
  nwEasting    : adec[24] @label "NW corner x"
  nwNorthing   : adec[24] @label "NW corner y"
  neEasting    : adec[24] @label "NE corner x"
  neNorthing   : adec[24] @label "NE corner y"
  seEasting    : adec[24] @label "SE corner x"
  seNorthing   : adec[24] @label "SE corner y"
  minElevation : adec[24] @label "minimum elevation in the file"
  maxElevation : adec[24] @label "maximum elevation in the file"
  rotation     : adec[24] @label "counterclockwise rotation, normally 0"
  accuracy     : anum[6]  @label "0 unknown, 1 record C present"
  xResolution  : adec[12] means asref:scaleX @label "E12.6"
  yResolution  : adec[12] means asref:scaleY @label "E12.6"
  zResolution  : adec[12] @label "E12.6"
  rows         : anum[6]  @label "rows; 1 for a profile-organised DEM"
  columns      : anum[6]  means araster:width @label "number of profiles"
  filler       : bytes[160] @label "unused in level 1; some dialects place extra fields here"
}

struct Profile
  @label "logical record B"
  @comment "One column of elevations, south to north."
{
  rowIndex        : anum[6]  @label "row index of the first elevation, normally 1"
  columnIndex     : anum[6]  @label "profile index, west to east"
  elevationCount  : anum[6]  means araster:height @label "elevations in this profile"
  columnCount     : anum[6]  @label "columns in this record, normally 1"
  startEasting    : adec[24] @label "ground x of the first elevation"
  startNorthing   : adec[24] @label "ground y of the first elevation"
  localDatumElev  : adec[24] @label "local datum elevation"
  minElevation    : adec[24] @label "minimum in this profile"
  maxElevation    : adec[24] @label "maximum in this profile"
  elevations      : anum repeat [elevationCount] @separated
                    @label "elevations, south to north, written as text"
}

@root struct UsgsDem
  @label "USGS DEM"
  @comment "Record A, then one record per profile."
{
  recordA  : RecordA
  profiles : Profile repeat until [eof] @label "one per profile, west to east"
}

// LIMITS OF THIS DESCRIPTION
//
// 1. Every sample in the GDAL corpus is TRUNCATED: the profile is verified on the records
//    present, not on a complete DEM. A full file's profile count equals recordA.columns.
// 2. Elevations are read as separated tokens, not sliced at width 6. That is what the format
//    means -- usgsdem_with_extra_values_at_end_of_profile.dem carries values a fixed-width
//    reading would mis-attribute -- and it is why the body needs bddo:separatedBy.
// 3. Bytes 865-1024 of record A are described as filler. Some dialects place extra fields
//    there; usgsdem_with_spaces_after_byte_864.dem pads them with spaces. Reading them as
//    filler is what lets both dialects parse.
// 4. Record C (accuracy) is not described. accuracy = 1 says one follows; no corpus sample
//    carries it, so describing it would be an assertion rather than a reading.
// 5. The elevations of a profile are a FLAT list running south to north. A north-up raster is
//    the profiles transposed and each reversed; the profile states the order rather than
//    performing it.
```

`repeat until [eof]` must match the spelling this codebase actually uses — check `nitf.hx`'s
`repeat until [...]` guards and `Parser.kt`'s `repeat until` branch, and use whatever predicate
means end-of-stream there. If none exists, size the repeat with `recordA.columns` and note in
limit 1 that a truncated file then fails; prefer the eof form if it is available.

- [ ] **Step 5: Copy to the fixtures and run**

```
copy d:\work\hexplain-profiles\profiles\usgsdem\usgsdem.hx d:\work\hexplain-tools\hdl\src\test\resources\profiles\usgsdem\usgsdem.hx
.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.UsgsDemParityTest"
```

Expected: the two named tests PASS and each round-trip case either passes or is skipped with a stated reason.

- [ ] **Step 6: Commit, in both repos**

```bash
# hexplain-profiles
git add profiles/usgsdem/usgsdem.hx
git commit -m "feat: USGS DEM — Fortran record A, and profiles of elevations as text

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
# hexplain-tools
git add hdl/src/test/resources/profiles/usgsdem/usgsdem.hx hdl/src/test/kotlin/io/hexplain/hdl/parity/UsgsDemParityTest.kt
git commit -m "test(hdl): USGSDEM parity — D exponents and tokenized elevations

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Coverage inventory

**Files:**
- Modify: `hexplain.io/specification/coverage/gdal-drivers.json`
- Regenerate: `hexplain.io/specification/coverage/index.html`

**Interfaces:**
- Consumes: the four profile names and their verification status from Tasks 6-9.
- Produces: nothing later in this plan depends on it.

- [ ] **Step 1: Add the four `profiles` entries**

In `gdal-drivers.json`, add a `profiles` list to each of `raster:aaigrid`, `raster:gsag`,
`raster:grassasciigrid` and `raster:usgsdem`, in the shape wave 1 established:

```json
"profiles": [ { "name": "aaigrid", "iri": "https://hexplain.io/ns/profile/aaigrid", "verification": "parse-verified" } ]
```

All four are `parse-verified`. Do NOT touch the `assessment` field: a profile is a description
and `assessment` records runtime evidence, which this wave does not change.

- [ ] **Step 2: Run the inventory gate**

```
python tools/test_gdal_inventory.py
```

Expected: PASS. The gate asserts each entry's schema and that every named profile directory
exists in the sibling `hexplain-profiles` checkout.

- [ ] **Step 3: Regenerate the coverage page**

```
python tools/_build_ontology_docs.py
```

Expected: `specification/coverage/index.html` gains four Profiles cells; `git diff --stat`
shows that file and nothing else unexpected.

- [ ] **Step 4: Confirm the count**

Linked driver rows go from 17 to 21. Verify:

```
python -c "import json; d=json.load(open('specification/coverage/gdal-drivers.json')); print(sum(1 for x in d['drivers'] if x.get('profiles')))"
```

Expected: `21`.

- [ ] **Step 5: Commit**

```bash
git add specification/coverage/gdal-drivers.json specification/coverage/index.html
git commit -m "coverage: link the four text-raster profiles wave 2a added

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Full gate runs and final headers

**Files:**
- Modify: the four profile headers, if any verification claim changed during implementation.

- [ ] **Step 1: Run every engine test**

In `hexplain-tools`:

```
.\gradlew.bat --offline :core:test :hdl:test
```

Expected: all PASS. If `SpecSyncTest` fails, check `git status` in `hexplain.io` for
uncommitted `specification/` edits from another session before investigating anything else.

- [ ] **Step 2: Run every library gate**

In `hexplain-profiles`:

```
python tools/run_gates.py
```

Expected: every gate PASSES. This takes over ten minutes.

- [ ] **Step 3: Run the spec gates**

In `hexplain.io`:

```
python tools/test_gdal_inventory.py
python tools/test_gdal_runtime.py
```

Expected: PASS.

- [ ] **Step 4: Reconcile every `Verification status:` line**

Read all four profile headers. Each must name the test that verifies it, the samples it was
verified on, and any sample that is skipped with the reason. A header claiming more than the
tests actually assert is the one defect this plan cannot catch automatically — check each
claim against the test it names.

- [ ] **Step 5: Commit any header corrections**

```bash
git add profiles/
git commit -m "docs(profiles): reconcile the wave 2a verification claims with their tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage.** E1 → Tasks 2, 3, 4, 5. E2 → Task 1. `aaigrid` → Task 6. `gsag` → Task 7.
`grassasciigrid` → Task 8. `usgsdem` → Task 9. Coverage inventory → Task 10. Sequencing
("E2 alone, then E1 against aaigrid, then the rest") → task order. The spec's recorded gap
about `raster:gtiff`/`raster:png` is deliberately NOT a task: it needs profiles that do not
exist.

**Type consistency.** `FieldIR.separatedBy: String?` is declared in Task 2 and consumed by
Tasks 3, 4 and 5 under that exact name. `TextNumberToken(value, text, lead, trail)` with
`rebuild()` is created in Task 3 and consumed in Task 4. `GdalOracle.Entry`/`decoded(rel)` is
created in Task 6 and consumed in Tasks 7, 8 and 9. The HDL spelling is `@separated`
throughout.

**Known open questions, each with a decision step rather than a placeholder.** The container
shape for a key/value header followed by a body is settled by Task 6 Step 1 with two spelled-out
alternatives. Whether a scalar `@separated` field reaches `readOneElement` is settled by Task 7
Step 1 with the one-line remedy. Record A's offsets are confirmed against the sample in Task 9
Step 1. `repeat until [eof]` spelling is checked against `nitf.hx` in Task 9 Step 4.

**Risk carried from the spec:** if a `header` container cannot round-trip, Task 6 Step 1's
Shape B is the fallback and Tasks 6 and 8 both use it.
