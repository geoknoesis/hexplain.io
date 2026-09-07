# Codec Generation Phase 1: CodecIR, Lowering, and the Kotlin Reference Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `codegen` module — CodecIR, the lowering pass from `FormatIR`, and a Kotlin backend emitting a format-specific reader and writer — proven by differential tests showing the generated codec agrees with `Metaparser` and `Metawriter` on the same fixtures.

**Architecture:** Four new flat Gradle modules in `hexplain-tools`. `codegen` holds the CodecIR data model, the lowering pass and the backend SPI; `runtime-kotlin` holds the hand-written primitives generated code links against; `codegen-kotlin` is the reference backend; `codegen-verify` generates codecs at build time from fixture profiles and differential-tests them against the metaengine. Nothing in `core` changes behaviour — only two `internal` declarations become `public`.

**Tech Stack:** Kotlin 2.2.10, Gradle with the `libs` version catalog, Apache Jena 5.5 (only via `core`), JUnit 5.10.2.

**Spec:** `docs/superpowers/specs/2026-09-06-pluggable-codec-generation-design.md`

## Global Constraints

- **Two repositories.** All code in this plan is in `d:\work\hexplain-tools`. The spec and this plan live in `d:\work\hexplain.io`. Never `git add -A` in either — both have unrelated modified files.
- **The metaengine is not modified.** `Metaparser.kt` and `Metawriter.kt` are read-only for this plan. They are the differential oracle; changing them invalidates every test here. The only permitted `core` change is widening visibility (Task 7), which changes no behaviour.
- **Proprietary, all rights reserved.** New modules must NOT be added to `publishableModules` in the root `build.gradle.kts`. Generated codecs and runtimes are not published anywhere in this phase.
- **Kotlin 2.2.10 via `libs.versions.kotlin`.** Every new module's build file uses `kotlin("jvm") version libs.versions.kotlin.get()`, matching `core/build.gradle.kts`.
- **Test style matches `core`:** JUnit 5, backtick test names, `org.junit.jupiter.api.Assertions.*`, `tasks.test { useJUnitPlatform() }`.
- Build/test offline: `./gradlew --offline :codegen:test`. Run all of this plan's tests with `./gradlew --offline :codegen:test :codegen-kotlin:test :runtime-kotlin:test :codegen-verify:test`.
- **Determinism is a requirement, not a nicety.** Emitted source must be byte-identical across runs for the same plan — no map iteration order leaking into output, no timestamps in headers. Task 9's golden-file tests depend on it.

## Deviations from the spec, decided here

The spec's §2.2 listed `PushRegion`/`PopRegion` and `SaveCursor`/`RestoreCursor` as paired steps. This plan uses **scoped steps carrying a body** instead — `Region(extent, body)` and `At(base, offset, body)`. A tree with nested bodies maps directly onto a target language's block structure, which is what keeps emitters small; paired push/pop steps would force every backend to track a stack. Same semantics, better shape.

The spec's §8 showed runtimes under `runtime/kotlin`. This plan uses flat module directories (`runtime-kotlin`) to match the existing `core` / `hdl` / `adapters` convention and avoid `projectDir` remapping in `settings.gradle.kts`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `settings.gradle.kts` | Register the four new modules | 1 |
| `codegen/build.gradle.kts` | Module build; depends on `core` | 1 |
| `codegen/.../ir/CodecIr.kt` | `CodecPlan`, `StructPlan`, `Step`, `Extent`, `Slot` | 1 |
| `codegen/.../ir/Capability.kt` | The capability enum and tier sets | 1 |
| `codegen/.../ir/PlanValidator.kt` | Well-formedness checks with located diagnostics | 1 |
| `codegen/.../lower/Diagnostics.kt` | `LoweringDiagnostic`, `LoweringException` | 2 |
| `codegen/.../lower/Lowering.kt` | `FormatIR` → `CodecPlan`; grows across tasks 2–6 | 2–6 |
| `codegen/.../lower/Extents.kt` | The extent precedence collapse | 3 |
| `codegen/.../lower/Demands.kt` | Capability demand computation | 6 |
| `runtime-kotlin/.../rt/ByteReader.kt` | Cursor, regions, scalars, bits, terminators | 7 |
| `runtime-kotlin/.../rt/WriteBuffer.kt` | Growing buffer + fixpoint `Infer` resolution | 12 |
| `runtime-kotlin/.../rt/Findings.kt` | Findings sink shared by reader and writer | 7 |
| `codegen/.../backend/CodecBackend.kt` | The backend SPI | 9 |
| `codegen/.../backend/SourceFile.kt` | Emitted file record | 9 |
| `codegen-kotlin/.../KotlinHelEmitter.kt` | HEL AST → Kotlin expression source | 8 |
| `codegen-kotlin/.../KotlinBackend.kt` | T0 reader emission | 9 |
| `codegen-kotlin/.../KotlinWriterEmitter.kt` | T1 writer emission | 13 |
| `codegen/.../cli/Hxc.kt` | `hxc gen` / `backends` / `explain` | 10, 15 |
| `codegen-verify/build.gradle.kts` | Build-time generation into a source set | 11 |
| `codegen-verify/src/test/.../*DifferentialTest.kt` | Equivalence against the metaengine | 11, 14 |

---

### Task 1: The `codegen` module and the CodecIR data model

**Files:**
- Modify: `settings.gradle.kts`
- Create: `codegen/build.gradle.kts`
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/ir/CodecIr.kt`
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/ir/Capability.kt`
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/ir/PlanValidator.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/ir/PlanValidatorTest.kt`

**Interfaces:**
- Consumes: `io.hexplain.core.ir.*` (`DataTypeIR`, `Endianness`, `BitOrder`, `OffsetBase`, `ChecksumIR`, `EnumerationIR`, `DataLayoutIR`, `HELExpression`) from `core`.
- Produces: `CodecPlan`, `StructPlan`, `Slot`, `SlotType`, `Extent`, `Step` (all variants), `Capability`, `Tier`, `PlanValidator.validate(plan): List<String>`.

- [ ] **Step 1: Register the modules**

Add to `settings.gradle.kts`:

```kotlin
rootProject.name = "hexplain-tools"
include("core")
include("hdl")
include("adapters")
include("codegen")
include("runtime-kotlin")
include("codegen-kotlin")
include("codegen-verify")
```

- [ ] **Step 2: Create `codegen/build.gradle.kts`**

```kotlin
plugins {
    kotlin("jvm") version libs.versions.kotlin.get()
}

repositories {
    mavenCentral()
}

dependencies {
    api(project(":core"))
    testImplementation(libs.junit.jupiter)
}

tasks.test {
    useJUnitPlatform()
}
```

`api` rather than `implementation`: `CodecPlan` exposes `DataTypeIR` and `HELExpression` in its public signatures, so every backend needs `core`'s IR types on its compile classpath transitively.

- [ ] **Step 3: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/ir/PlanValidatorTest.kt`:

```kotlin
package io.hexplain.codegen.ir

import io.hexplain.core.ir.BaseType
import io.hexplain.core.ir.DataTypeIR
import io.hexplain.core.ir.Endianness
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class PlanValidatorTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)

    private fun plan(vararg steps: Step, slots: List<Slot> = listOf(Slot("value", SlotType.INT))) =
        CodecPlan(
            format = "Test",
            root = "Root",
            structs = mapOf(
                "Root" to StructPlan(
                    name = "Root",
                    byteOrder = ByteOrderPlan.Fixed(Endianness.BIG_ENDIAN),
                    slots = slots,
                    steps = steps.toList()
                )
            )
        )

    @Test
    fun `a well-formed plan has no findings`() {
        val p = plan(ReadScalar("value", u8, Endianness.NOT_APPLICABLE))
        assertEquals(emptyList<String>(), PlanValidator.validate(p))
    }

    @Test
    fun `a step writing an undeclared slot is rejected`() {
        val p = plan(ReadScalar("missing", u8, Endianness.NOT_APPLICABLE))
        val findings = PlanValidator.validate(p)
        assertEquals(1, findings.size)
        assertTrue(findings[0].contains("missing"), "expected the slot name in: ${findings[0]}")
    }

    @Test
    fun `a nested step naming an unknown struct is rejected`() {
        val p = plan(Nested("value", "NoSuchStruct"), slots = listOf(Slot("value", SlotType.STRUCT)))
        val findings = PlanValidator.validate(p)
        assertEquals(1, findings.size)
        assertTrue(findings[0].contains("NoSuchStruct"), "expected the struct name in: ${findings[0]}")
    }

    @Test
    fun `an unknown root struct is rejected`() {
        val p = plan(ReadScalar("value", u8, Endianness.NOT_APPLICABLE)).copy(root = "Absent")
        val findings = PlanValidator.validate(p)
        assertTrue(findings.any { it.contains("Absent") }, "expected the root name in: $findings")
    }

    @Test
    fun `slots declared inside a nested body are visible to the validator`() {
        val p = CodecPlan(
            format = "Test",
            root = "Root",
            structs = mapOf(
                "Root" to StructPlan(
                    name = "Root",
                    byteOrder = ByteOrderPlan.Fixed(Endianness.BIG_ENDIAN),
                    slots = listOf(Slot("n", SlotType.INT), Slot("items", SlotType.LIST)),
                    steps = listOf(
                        ReadScalar("n", u8, Endianness.NOT_APPLICABLE),
                        RepeatCount(
                            slot = "items",
                            count = CountSource.FromSlot("n"),
                            body = listOf(ReadScalar("items", u8, Endianness.NOT_APPLICABLE))
                        )
                    )
                )
            )
        )
        assertEquals(emptyList<String>(), PlanValidator.validate(p))
    }
}
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test`
Expected: FAIL — compilation errors, `Unresolved reference: CodecPlan`.

- [ ] **Step 5: Write `Capability.kt`**

```kotlin
package io.hexplain.codegen.ir

/**
 * A thing a backend must be able to do. [CodecPlan.demands] states what one descriptor needs;
 * a backend states what it supplies. The generator refuses the pair when demands exceed supply.
 */
enum class Capability {
    // Tier capabilities, cumulative.
    WRITE,
    SEMANTIC,
    CONFORMANCE,

    // Structural feature capabilities.
    BITFIELDS,
    POINTERS,
    CHUNKED_LAYOUT,
    DELIMITED_TEXT,
    CONDITIONAL_ENDIANNESS,
    RECOVERY,

    // HEL builtin capabilities: each drags in real target-runtime support.
    REGEX,
    DATETIME,
    REGISTER_LOOKUP,
    GEOMETRY,
}

/** Cumulative tiers. A backend declaring [T3] supplies every capability of [T0]..[T2] too. */
enum class Tier(val implies: Set<Capability>) {
    T0(emptySet()),
    T1(setOf(Capability.WRITE)),
    T2(setOf(Capability.WRITE, Capability.SEMANTIC)),
    T3(setOf(Capability.WRITE, Capability.SEMANTIC, Capability.CONFORMANCE)),
}
```

- [ ] **Step 6: Write `CodecIr.kt`**

```kotlin
package io.hexplain.codegen.ir

import io.hexplain.core.ir.ChecksumIR
import io.hexplain.core.ir.DataLayoutIR
import io.hexplain.core.ir.DataTypeIR
import io.hexplain.core.ir.Endianness
import io.hexplain.core.ir.EnumerationIR
import io.hexplain.core.ir.HELExpression
import io.hexplain.core.ir.OffsetBase
import io.hexplain.core.ir.BitOrder

/**
 * A lowered, execution-ready description of one format. Every precedence rule the metaparser
 * decides per field at runtime has already been decided here, once: an [Extent] is singular, a
 * [Seek] base is resolved, a region bound is explicit. A backend spells steps; it does not judge.
 */
data class CodecPlan(
    val format: String,
    val root: String,
    val structs: Map<String, StructPlan>,
    val enums: Map<String, EnumerationIR> = emptyMap(),
    val demands: Set<Capability> = emptySet(),
)

/** How this struct's byte order is established. */
sealed interface ByteOrderPlan {
    data class Fixed(val order: Endianness) : ByteOrderPlan
    /** First matching rule wins, evaluated once its discriminator slot is filled. */
    data class Conditional(val rules: List<Pair<HELExpression, Endianness>>, val fallback: Endianness) : ByteOrderPlan
}

enum class SlotType { INT, FLOAT, TEXT, BYTES, STRUCT, LIST }

/** A named local of a generated struct reader/writer. */
data class Slot(val name: String, val type: SlotType)

data class StructPlan(
    val name: String,
    val byteOrder: ByteOrderPlan,
    val slots: List<Slot>,
    val steps: List<Step>,
    val bitOrder: BitOrder = BitOrder.MSB_FIRST,
)

/**
 * How many bytes a read or write occupies. Exactly one variant survives lowering — the metaparser's
 * five mutually exclusive sources (size / sizeFromField / sizeFromExpression / terminator /
 * sizeToEndOfStream) collapse to one node here, so no backend re-derives the precedence.
 */
sealed interface Extent {
    /** The data type's own width. */
    data object Intrinsic : Extent
    data class FixedBytes(val count: Long) : Extent
    data class FromSlot(val slot: String) : Extent
    data class FromExpr(val expr: HELExpression) : Extent
    data class Terminated(val terminator: ByteArray, val consume: Boolean = true, val include: Boolean = false) : Extent
    /** To the end of the enclosing [Region], or of the stream when there is none. */
    data object ToRegionEnd : Extent
}

/** How many times a repetition runs. */
sealed interface CountSource {
    data class Fixed(val count: Long) : CountSource
    data class FromSlot(val slot: String) : CountSource
    data class FromExpr(val expr: HELExpression) : CountSource
}

sealed interface Step

// --- Primitive reads/writes -------------------------------------------------
data class ReadScalar(val slot: String, val type: DataTypeIR, val order: Endianness) : Step
data class ReadBits(val slot: String, val width: Int, val order: BitOrder) : Step
data class ReadBytes(
    val slot: String,
    val extent: Extent,
    val charset: String? = null,
    val trimNull: Boolean = false,
    val asText: Boolean = false,
) : Step
data class ExpectFixed(val bytes: ByteArray) : Step
data class Skip(val extent: Extent) : Step
data class Align(val boundary: Long) : Step

// --- Aggregation ------------------------------------------------------------
data class Nested(val slot: String?, val struct: String) : Step
data class RepeatCount(val slot: String, val count: CountSource, val body: List<Step>) : Step
data class RepeatUntil(val slot: String, val condition: HELExpression, val body: List<Step>) : Step
data class RepeatToEnd(val slot: String, val body: List<Step>) : Step

// --- Scoping (bodies, not push/pop pairs: they map onto target-language blocks) ---
/** Bounds every read inside [body] to [extent]; skips trailing padding on exit. */
data class Region(val extent: Extent, val body: List<Step>) : Step
/** Runs [body] at a computed position. [restore] = true is a pointer read: the cursor is put back. */
data class At(val base: OffsetBase, val offset: HELExpression, val restore: Boolean, val body: List<Step>) : Step

// --- Control flow -----------------------------------------------------------
data class Branch(val condition: HELExpression, val then: List<Step>, val otherwise: List<Step> = emptyList()) : Step
data class Switch(val arms: List<Pair<HELExpression, List<Step>>>, val default: List<Step> = emptyList()) : Step

// --- Values and checks ------------------------------------------------------
/** A zero-byte derived value (bddo:valueFromExpression). */
data class Bind(val slot: String, val expr: HELExpression) : Step
/** The writer must compute this slot when the caller did not supply it. */
data class Infer(val slot: String, val kind: InferKind) : Step
enum class InferKind { SIZE, COUNT, OFFSET, CHECKSUM }
data class Assert(
    val condition: HELExpression,
    val message: String,
    val requirementId: String? = null,
    val constraintId: String? = null,
) : Step
data class Verify(val slot: String, val checksum: ChecksumIR) : Step
data class EnumMember(val slot: String, val enumId: String) : Step

// --- Transforms and bulk data ----------------------------------------------
data class Decode(val slot: String, val codecIds: List<String>) : Step
data class Cells(val slot: String, val layout: DataLayoutIR) : Step

// --- Semantic emission (tier 2; lowered now, emitted later) ------------------
data class EmitClass(val iri: String) : Step
data class EmitProperty(
    val iri: String,
    val value: HELExpression?,
    val fromSlot: String?,
    val datatype: String?,
    val unit: String? = null,
    val language: String? = null,
) : Step
data class EmitEdge(val objectProperty: String, val targetSlot: String) : Step
```

- [ ] **Step 7: Write `PlanValidator.kt`**

```kotlin
package io.hexplain.codegen.ir

/**
 * Well-formedness of a lowered plan. A plan that reaches a backend has passed this, so a backend
 * may assume every slot reference resolves and every struct reference exists.
 */
object PlanValidator {

    fun validate(plan: CodecPlan): List<String> {
        val findings = mutableListOf<String>()
        if (plan.root !in plan.structs) {
            findings += "root struct '${plan.root}' is not defined in the plan"
        }
        for ((name, struct) in plan.structs) {
            val declared = struct.slots.mapTo(mutableSetOf()) { it.name }
            walk(struct.steps) { step -> check(name, step, declared, plan, findings) }
        }
        return findings
    }

    /** Depth-first over every step, including step bodies. */
    private fun walk(steps: List<Step>, visit: (Step) -> Unit) {
        for (step in steps) {
            visit(step)
            for (body in bodies(step)) walk(body, visit)
        }
    }

    private fun bodies(step: Step): List<List<Step>> = when (step) {
        is RepeatCount -> listOf(step.body)
        is RepeatUntil -> listOf(step.body)
        is RepeatToEnd -> listOf(step.body)
        is Region -> listOf(step.body)
        is At -> listOf(step.body)
        is Branch -> listOf(step.then, step.otherwise)
        is Switch -> step.arms.map { it.second } + listOf(step.default)
        else -> emptyList()
    }

    private fun check(
        struct: String,
        step: Step,
        declared: Set<String>,
        plan: CodecPlan,
        findings: MutableList<String>,
    ) {
        fun slot(name: String?) {
            if (name != null && name !in declared) {
                findings += "$struct: step ${step::class.simpleName} references undeclared slot '$name'"
            }
        }
        when (step) {
            is ReadScalar -> slot(step.slot)
            is ReadBits -> slot(step.slot)
            is ReadBytes -> slot(step.slot)
            is Bind -> slot(step.slot)
            is Infer -> slot(step.slot)
            is Decode -> slot(step.slot)
            is Cells -> slot(step.slot)
            is Verify -> slot(step.slot)
            is EnumMember -> {
                slot(step.slot)
                if (step.enumId !in plan.enums) {
                    findings += "$struct: EnumMember references unknown enumeration '${step.enumId}'"
                }
            }
            is RepeatCount -> {
                slot(step.slot)
                (step.count as? CountSource.FromSlot)?.let { slot(it.slot) }
            }
            is RepeatUntil -> slot(step.slot)
            is RepeatToEnd -> slot(step.slot)
            is EmitEdge -> slot(step.targetSlot)
            is EmitProperty -> slot(step.fromSlot)
            is Nested -> {
                slot(step.slot)
                if (step.struct !in plan.structs) {
                    findings += "$struct: Nested references unknown struct '${step.struct}'"
                }
            }
            is Region -> (step.extent as? Extent.FromSlot)?.let { slot(it.slot) }
            else -> Unit
        }
    }
}
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test`
Expected: PASS — 5 tests in `PlanValidatorTest`.

- [ ] **Step 9: Commit**

```bash
git add settings.gradle.kts codegen/
git commit -m "feat(codegen): CodecIR data model and plan validator"
```

---

### Task 2: Lowering — scalars, structs, endianness

**Files:**
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Diagnostics.kt`
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Lowering.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringScalarTest.kt`

**Interfaces:**
- Consumes: Task 1's `CodecPlan`, `StructPlan`, `Step`, `Slot`, `SlotType`, `ByteOrderPlan`, `PlanValidator`.
- Produces: `Lowering.lower(formatIR: FormatIR): CodecPlan`, `LoweringException(message)`, `slotTypeFor(dataType: DataTypeIR): SlotType`.

- [ ] **Step 1: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringScalarTest.kt`:

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class LoweringScalarTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val u32be = DataTypeIR("uint32be", BaseType.INTEGER, 32, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)

    private fun format(vararg fields: FieldIR, endianness: Endianness = Endianness.BIG_ENDIAN) =
        FormatIR(
            name = "Test",
            rootStruct = "Root",
            structs = mapOf("Root" to StructIR("Root", fields.toList(), endianness = endianness))
        )

    @Test
    fun `a scalar field becomes one ReadScalar step and one slot`() {
        val plan = Lowering.lower(format(FieldIR(name = "width", dataType = u32be)))
        val root = plan.structs.getValue("Root")
        assertEquals(listOf(Slot("width", SlotType.INT)), root.slots)
        assertEquals(listOf(ReadScalar("width", u32be, Endianness.BIG_ENDIAN)), root.steps)
    }

    @Test
    fun `a field without its own endianness inherits the struct's`() {
        val plan = Lowering.lower(format(FieldIR(name = "n", dataType = u8), endianness = Endianness.LITTLE_ENDIAN))
        val step = plan.structs.getValue("Root").steps.single() as ReadScalar
        assertEquals(Endianness.LITTLE_ENDIAN, step.order)
    }

    @Test
    fun `a fixed-value field becomes ExpectFixed and declares no slot`() {
        val magic = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47)
        val plan = Lowering.lower(format(FieldIR(name = "magic", dataType = u8, fixedValue = magic)))
        val root = plan.structs.getValue("Root")
        assertEquals(emptyList<Slot>(), root.slots)
        val step = root.steps.single()
        assertTrue(step is ExpectFixed, "expected ExpectFixed, got $step")
        assertArrayEquals(magic, (step as ExpectFixed).bytes)
    }

    @Test
    fun `a nested struct field becomes a Nested step referring to the struct by name`() {
        val ir = FormatIR(
            name = "Test",
            rootStruct = "Root",
            structs = mapOf(
                "Root" to StructIR("Root", listOf(FieldIR(name = "header", dataType = DataTypeIR("Header", BaseType.BYTES, 0)))),
                "Header" to StructIR("Header", listOf(FieldIR(name = "n", dataType = u8)))
            )
        )
        val plan = Lowering.lower(ir)
        assertEquals(listOf(Nested("header", "Header")), plan.structs.getValue("Root").steps)
        assertEquals(listOf(Slot("header", SlotType.STRUCT)), plan.structs.getValue("Root").slots)
    }

    @Test
    fun `conditional endianness lowers to a ByteOrderPlan, not to a step`() {
        val rule = EndiannessRuleIR(condition = literal(true), endianness = Endianness.LITTLE_ENDIAN)
        val ir = FormatIR(
            name = "Test",
            rootStruct = "Root",
            structs = mapOf(
                "Root" to StructIR("Root", listOf(FieldIR(name = "n", dataType = u8)), conditionalEndianness = listOf(rule))
            )
        )
        val order = Lowering.lower(ir).structs.getValue("Root").byteOrder
        assertTrue(order is ByteOrderPlan.Conditional, "expected Conditional, got $order")
        assertEquals(1, (order as ByteOrderPlan.Conditional).rules.size)
        assertTrue(Capability.CONDITIONAL_ENDIANNESS in Lowering.lower(ir).demands)
    }

    @Test
    fun `an unknown root struct is a lowering error, not a silent empty plan`() {
        val ir = FormatIR(name = "Test", rootStruct = "Absent", structs = emptyMap())
        val ex = assertThrows<LoweringException> { Lowering.lower(ir) }
        assertTrue(ex.message!!.contains("Absent"), "expected the struct name in: ${ex.message}")
    }

    private fun literal(value: Any): HELExpression = io.hexplain.core.hel.LiteralNode(value)
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*LoweringScalarTest*'`
Expected: FAIL — `Unresolved reference: Lowering`.

- [ ] **Step 3: Write `Diagnostics.kt`**

```kotlin
package io.hexplain.codegen.lower

/**
 * A descriptor that cannot be lowered. Thrown rather than collected: a half-lowered plan is not a
 * useful artefact, and every message names the struct, the field and the reason.
 */
class LoweringException(message: String) : IllegalArgumentException(message)

internal fun lowerFail(struct: String, field: String?, reason: String): Nothing =
    throw LoweringException(if (field == null) "$struct: $reason" else "$struct.$field: $reason")
```

- [ ] **Step 4: Write `Lowering.kt` (scalars, structs, endianness)**

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.ir.*

/**
 * FormatIR -> CodecPlan. Every judgement the metaparser makes per field at runtime is made here
 * once, statically: which extent source wins, what an offset is relative to, where a region ends.
 */
object Lowering {

    fun lower(formatIR: FormatIR): CodecPlan {
        if (formatIR.rootStruct !in formatIR.structs) {
            throw LoweringException("root struct '${formatIR.rootStruct}' is not defined in the format")
        }
        val demands = mutableSetOf<Capability>()
        val enums = mutableMapOf<String, EnumerationIR>()
        val structs = formatIR.structs.mapValues { (_, struct) ->
            lowerStruct(struct, formatIR, demands, enums)
        }
        val plan = CodecPlan(
            format = formatIR.name,
            root = formatIR.rootStruct,
            structs = structs,
            enums = enums,
            demands = demands,
        )
        val findings = PlanValidator.validate(plan)
        if (findings.isNotEmpty()) {
            throw LoweringException("lowering produced an invalid plan:\n  " + findings.joinToString("\n  "))
        }
        return plan
    }

    private fun lowerStruct(
        struct: StructIR,
        formatIR: FormatIR,
        demands: MutableSet<Capability>,
        enums: MutableMap<String, EnumerationIR>,
    ): StructPlan {
        val byteOrder = if (struct.conditionalEndianness.isNotEmpty()) {
            demands += Capability.CONDITIONAL_ENDIANNESS
            ByteOrderPlan.Conditional(
                rules = struct.conditionalEndianness.map { it.condition to it.endianness },
                fallback = struct.endianness,
            )
        } else {
            ByteOrderPlan.Fixed(struct.endianness)
        }

        val slots = mutableListOf<Slot>()
        val steps = mutableListOf<Step>()
        for (field in struct.fields) {
            lowerField(struct, field, formatIR, byteOrder, slots, steps, demands, enums)
        }
        return StructPlan(
            name = struct.name,
            byteOrder = byteOrder,
            slots = slots,
            steps = steps,
            bitOrder = struct.bitOrder,
        )
    }

    private fun lowerField(
        struct: StructIR,
        field: FieldIR,
        formatIR: FormatIR,
        byteOrder: ByteOrderPlan,
        slots: MutableList<Slot>,
        steps: MutableList<Step>,
        demands: MutableSet<Capability>,
        enums: MutableMap<String, EnumerationIR>,
    ) {
        // A constant contributes no value: it is checked, not stored.
        if (field.fixedValue != null) {
            steps += ExpectFixed(field.fixedValue!!)
            return
        }
        val nested = formatIR.structs[field.dataType.name]
        if (nested != null) {
            slots += Slot(field.name, SlotType.STRUCT)
            steps += Nested(field.name, nested.name)
            return
        }
        slots += Slot(field.name, slotTypeFor(field.dataType))
        steps += ReadScalar(field.name, field.dataType, effectiveOrder(field.dataType, byteOrder))
    }

    /** A field's own byte order wins; otherwise it takes the struct's fixed order. */
    private fun effectiveOrder(type: DataTypeIR, byteOrder: ByteOrderPlan): Endianness =
        when {
            type.hasEndianness != Endianness.NOT_APPLICABLE -> type.hasEndianness
            byteOrder is ByteOrderPlan.Fixed -> byteOrder.order
            else -> Endianness.NOT_APPLICABLE // resolved at run time from the discriminator
        }

    fun slotTypeFor(dataType: DataTypeIR): SlotType = when (dataType.baseType) {
        BaseType.INTEGER -> SlotType.INT
        BaseType.FLOAT -> SlotType.FLOAT
        BaseType.STRING -> SlotType.TEXT
        BaseType.BYTES -> SlotType.BYTES
    }
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test --tests '*LoweringScalarTest*'`
Expected: PASS — 6 tests.

- [ ] **Step 6: Commit**

```bash
git add codegen/
git commit -m "feat(codegen): lower scalars, nested structs and endianness"
```

---

### Task 3: Lowering — the extent precedence collapse

This is the task the whole design exists for. `Metaparser` decides per field, at runtime, which of five mutually exclusive extent sources applies. Lowering decides it once and rejects descriptors that state more than one.

**Files:**
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Extents.kt`
- Modify: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Lowering.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringExtentTest.kt`

**Interfaces:**
- Consumes: `Extent`, `LoweringException`, Task 2's `Lowering`.
- Produces: `Extents.of(struct: StructIR, field: FieldIR): Extent`; `Lowering` now emits `ReadBytes` with a resolved `Extent` for non-scalar fields.

- [ ] **Step 1: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringExtentTest.kt`:

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.hel.LiteralNode
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class LoweringExtentTest {

    private val bytes = DataTypeIR("bytes", BaseType.BYTES, 0)
    private val text = DataTypeIR("string", BaseType.STRING, 0)
    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)

    private fun extentOf(field: FieldIR, vararg others: FieldIR): Extent {
        val ir = FormatIR("Test", "Root", mapOf("Root" to StructIR("Root", others.toList() + field)))
        val step = Lowering.lower(ir).structs.getValue("Root").steps.last()
        return (step as ReadBytes).extent
    }

    @Test
    fun `a fixed size lowers to FixedBytes`() {
        assertEquals(Extent.FixedBytes(4), extentOf(FieldIR(name = "data", dataType = bytes, size = 4)))
    }

    @Test
    fun `sizeFromField lowers to FromSlot`() {
        val extent = extentOf(
            FieldIR(name = "data", dataType = bytes, sizeFromField = "len"),
            FieldIR(name = "len", dataType = u8),
        )
        assertEquals(Extent.FromSlot("len"), extent)
    }

    @Test
    fun `sizeFromExpression lowers to FromExpr`() {
        val expr = LiteralNode(7L)
        assertEquals(Extent.FromExpr(expr), extentOf(FieldIR(name = "data", dataType = bytes, sizeFromExpression = expr)))
    }

    @Test
    fun `a terminator lowers to Terminated`() {
        val nul = byteArrayOf(0)
        val extent = extentOf(FieldIR(name = "name", dataType = text, terminator = nul))
        assertTrue(extent is Extent.Terminated, "expected Terminated, got $extent")
        assertArrayEquals(nul, (extent as Extent.Terminated).terminator)
    }

    @Test
    fun `sizeToEndOfStream lowers to ToRegionEnd`() {
        assertEquals(Extent.ToRegionEnd, extentOf(FieldIR(name = "rest", dataType = bytes, sizeToEndOfStream = true)))
    }

    @Test
    fun `sizeFromField naming a field that does not exist is rejected`() {
        val ex = assertThrows<LoweringException> {
            extentOf(FieldIR(name = "data", dataType = bytes, sizeFromField = "nope"))
        }
        assertTrue(ex.message!!.contains("nope"), "expected the field name in: ${ex.message}")
    }

    @Test
    fun `two extent sources on one field are rejected rather than silently ranked`() {
        val ex = assertThrows<LoweringException> {
            extentOf(FieldIR(name = "data", dataType = bytes, size = 4, sizeToEndOfStream = true))
        }
        assertTrue(
            ex.message!!.contains("size") && ex.message!!.contains("sizeToEndOfStream"),
            "expected both sources named in: ${ex.message}",
        )
    }

    @Test
    fun `a bytes field with no extent source at all is rejected`() {
        val ex = assertThrows<LoweringException> { extentOf(FieldIR(name = "data", dataType = bytes)) }
        assertTrue(ex.message!!.contains("no extent"), "expected 'no extent' in: ${ex.message}")
    }

    @Test
    fun `an integer field keeps its intrinsic width and stays a ReadScalar`() {
        val ir = FormatIR("Test", "Root", mapOf("Root" to StructIR("Root", listOf(FieldIR(name = "n", dataType = u8)))))
        assertTrue(Lowering.lower(ir).structs.getValue("Root").steps.single() is ReadScalar)
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*LoweringExtentTest*'`
Expected: FAIL — `Unresolved reference: Extents`, and the existing cases fail because `Lowering` still emits `ReadScalar` for `BYTES` fields.

- [ ] **Step 3: Write `Extents.kt`**

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.Extent
import io.hexplain.core.ir.FieldIR
import io.hexplain.core.ir.StructIR

/**
 * Collapses a field's five mutually exclusive extent sources to one [Extent].
 *
 * The metaparser resolves this per field at run time by null-checking in a fixed order, which
 * means the order is knowledge held only in its source. Here it is a single decision with an
 * explicit error when a descriptor states more than one source — a descriptor that would have
 * been silently ranked by the interpreter is a descriptor whose author did not mean what they wrote.
 */
object Extents {

    fun of(struct: StructIR, field: FieldIR): Extent {
        val sources = buildList {
            if (field.size != null) add("size" to Extent.FixedBytes(field.size!!))
            if (field.sizeFromField != null) add("sizeFromField" to Extent.FromSlot(field.sizeFromField!!))
            if (field.sizeFromExpression != null) add("sizeFromExpression" to Extent.FromExpr(field.sizeFromExpression!!))
            if (field.terminator != null) add("terminator" to Extent.Terminated(field.terminator!!))
            if (field.sizeToEndOfStream) add("sizeToEndOfStream" to Extent.ToRegionEnd)
        }
        when (sources.size) {
            0 -> lowerFail(struct.name, field.name, "no extent: a non-scalar field needs one of size, sizeFromField, sizeFromExpression, terminator or sizeToEndOfStream")
            1 -> Unit
            else -> lowerFail(
                struct.name,
                field.name,
                "conflicting extent sources: ${sources.joinToString(", ") { it.first }}",
            )
        }
        val (name, extent) = sources.single()
        if (extent is Extent.FromSlot && struct.fields.none { it.name == extent.slot }) {
            lowerFail(struct.name, field.name, "$name names '${extent.slot}', which is not a field of ${struct.name}")
        }
        return extent
    }
}
```

- [ ] **Step 4: Route non-scalar fields through `Extents` in `Lowering.kt`**

Replace the final two lines of `lowerField` (the `slots +=` / `steps += ReadScalar` pair) with:

```kotlin
        val isScalar = field.dataType.baseType == BaseType.INTEGER || field.dataType.baseType == BaseType.FLOAT
        slots += Slot(field.name, slotTypeFor(field.dataType))
        if (isScalar && field.size == null && field.sizeFromField == null &&
            field.sizeFromExpression == null && field.terminator == null && !field.sizeToEndOfStream
        ) {
            steps += ReadScalar(field.name, field.dataType, effectiveOrder(field.dataType, byteOrder))
            return
        }
        steps += ReadBytes(
            slot = field.name,
            extent = Extents.of(struct, field),
            charset = field.encoding,
            trimNull = field.trimNull,
            asText = field.dataType.baseType == BaseType.STRING,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test`
Expected: PASS — `LoweringExtentTest` (9 tests) and `LoweringScalarTest` (6) both green.

- [ ] **Step 6: Commit**

```bash
git add codegen/
git commit -m "feat(codegen): collapse the five extent sources to one Extent at lower time"
```

---

### Task 4: Lowering — offsets, pointers and regions

**Files:**
- Modify: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Lowering.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringOffsetTest.kt`

**Interfaces:**
- Consumes: `At`, `Region`, `Align`, `Extent`, `Capability.POINTERS`.
- Produces: `Lowering` wraps offset-addressed fields in `At(base, offset, restore = true, body)` and sized structs in `Region(extent, body)`.

- [ ] **Step 1: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringOffsetTest.kt`:

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.hel.AccessorNode
import io.hexplain.core.hel.Key
import io.hexplain.core.hel.LiteralNode
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class LoweringOffsetTest {

    private val u32 = DataTypeIR("uint32be", BaseType.INTEGER, 32, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)
    private val bytes = DataTypeIR("bytes", BaseType.BYTES, 0)

    private fun rootOf(vararg fields: FieldIR, structSize: Long? = null): StructPlan {
        val ir = FormatIR("Test", "Root", mapOf("Root" to StructIR("Root", fields.toList(), size = structSize)))
        return Lowering.lower(ir).structs.getValue("Root")
    }

    @Test
    fun `a fixed atOffset becomes an At step with a literal offset and a restored cursor`() {
        val root = rootOf(FieldIR(name = "tag", dataType = u32, atOffset = 16))
        val at = root.steps.single() as At
        assertEquals(OffsetBase.STREAM_START, at.base)
        assertEquals(LiteralNode(16L), at.offset)
        assertTrue(at.restore, "an offset-addressed read must not advance the sequential cursor")
        assertEquals(listOf(ReadScalar("tag", u32, Endianness.BIG_ENDIAN)), at.body)
    }

    @Test
    fun `atOffsetFromField becomes an accessor expression over the sibling slot`() {
        val root = rootOf(
            FieldIR(name = "ptr", dataType = u32),
            FieldIR(name = "target", dataType = bytes, size = 2, atOffsetFromField = "ptr"),
        )
        val at = root.steps.last() as At
        assertEquals(AccessorNode(listOf(Key("self"), Key("ptr"))), at.offset)
    }

    @Test
    fun `the declared offsetBase is carried through, not normalised away`() {
        val root = rootOf(FieldIR(name = "trailer", dataType = u32, atOffset = -8, offsetBase = OffsetBase.STREAM_END))
        assertEquals(OffsetBase.STREAM_END, (root.steps.single() as At).base)
    }

    @Test
    fun `an offset-addressed field demands the POINTERS capability`() {
        val ir = FormatIR("Test", "Root", mapOf("Root" to StructIR("Root", listOf(FieldIR(name = "tag", dataType = u32, atOffset = 16)))))
        assertTrue(Capability.POINTERS in Lowering.lower(ir).demands)
    }

    @Test
    fun `alignment becomes an Align step before the read`() {
        val root = rootOf(FieldIR(name = "n", dataType = u32, alignment = 4))
        assertEquals(Align(4), root.steps.first())
        assertTrue(root.steps[1] is ReadScalar)
    }

    @Test
    fun `a struct-level size wraps the whole body in a Region`() {
        val root = rootOf(FieldIR(name = "n", dataType = u32), structSize = 64)
        val region = root.steps.single() as Region
        assertEquals(Extent.FixedBytes(64), region.extent)
        assertEquals(listOf(ReadScalar("n", u32, Endianness.BIG_ENDIAN)), region.body)
    }

    @Test
    fun `a struct without a size emits no Region`() {
        val root = rootOf(FieldIR(name = "n", dataType = u32))
        assertTrue(root.steps.none { it is Region }, "unexpected Region in ${root.steps}")
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*LoweringOffsetTest*'`
Expected: FAIL — `class io.hexplain.codegen.ir.ReadScalar cannot be cast to class io.hexplain.codegen.ir.At`.

- [ ] **Step 3: Add offset and region lowering to `Lowering.kt`**

Add these helpers to the `Lowering` object:

```kotlin
    /** The offset expression of an addressed field, or null when the field is read sequentially. */
    private fun offsetExpr(field: FieldIR): HELExpression? = when {
        field.atOffset != null -> io.hexplain.core.hel.LiteralNode(field.atOffset!!)
        field.atOffsetFromField != null ->
            io.hexplain.core.hel.AccessorNode(
                listOf(io.hexplain.core.hel.Key("self"), io.hexplain.core.hel.Key(field.atOffsetFromField!!))
            )
        field.atOffsetFromExpression != null -> field.atOffsetFromExpression
        else -> null
    }

    /** The struct's own byte extent, when it declares one. */
    private fun structExtent(struct: StructIR): Extent? = when {
        struct.size != null -> Extent.FixedBytes(struct.size!!)
        struct.sizeFromField != null -> Extent.FromSlot(struct.sizeFromField!!)
        struct.sizeFromExpression != null -> Extent.FromExpr(struct.sizeFromExpression!!)
        else -> null
    }
```

In `lowerStruct`, wrap the assembled steps before constructing the `StructPlan`:

```kotlin
        val body: List<Step> = structExtent(struct)?.let { listOf(Region(it, steps.toList())) } ?: steps.toList()
        return StructPlan(
            name = struct.name,
            byteOrder = byteOrder,
            slots = slots,
            steps = body,
            bitOrder = struct.bitOrder,
        )
```

In `lowerField`, collect each field's steps into a local list and wrap it, replacing direct `steps +=` calls. Restructure the tail of `lowerField` as:

```kotlin
        val emitted = mutableListOf<Step>()
        // ... existing ExpectFixed / Nested / ReadScalar / ReadBytes logic appends to `emitted` ...

        if (field.alignment != null) steps += Align(field.alignment!!)
        val offset = offsetExpr(field)
        if (offset != null) {
            demands += Capability.POINTERS
            steps += At(base = field.offsetBase, offset = offset, restore = true, body = emitted)
        } else {
            steps += emitted
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test`
Expected: PASS — `LoweringOffsetTest` (7 tests) plus tasks 2–3 still green.

- [ ] **Step 5: Commit**

```bash
git add codegen/
git commit -m "feat(codegen): lower offsets, pointer reads, alignment and struct regions"
```

---

### Task 5: Lowering — repetition, conditionals and dispatch

**Files:**
- Modify: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Lowering.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringControlFlowTest.kt`

**Interfaces:**
- Consumes: `RepeatCount`, `RepeatUntil`, `RepeatToEnd`, `Branch`, `Switch`, `CountSource`.
- Produces: `Lowering` emits repetition and control flow; `Slot` type for a repeated field is `SlotType.LIST`.

- [ ] **Step 1: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringControlFlowTest.kt`:

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.hel.LiteralNode
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class LoweringControlFlowTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val u16 = DataTypeIR("uint16be", BaseType.INTEGER, 16, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)

    private fun rootOf(vararg fields: FieldIR): StructPlan {
        val ir = FormatIR("Test", "Root", mapOf("Root" to StructIR("Root", fields.toList())))
        return Lowering.lower(ir).structs.getValue("Root")
    }

    @Test
    fun `repeatCount lowers to RepeatCount with a fixed count and a LIST slot`() {
        val root = rootOf(FieldIR(name = "items", dataType = u8, repeatCount = 3))
        assertEquals(listOf(Slot("items", SlotType.LIST)), root.slots)
        val repeat = root.steps.single() as RepeatCount
        assertEquals(CountSource.Fixed(3), repeat.count)
        assertEquals(listOf(ReadScalar("items", u8, Endianness.NOT_APPLICABLE)), repeat.body)
    }

    @Test
    fun `repeatCountFromField lowers to a slot-sourced count`() {
        val root = rootOf(
            FieldIR(name = "n", dataType = u8),
            FieldIR(name = "items", dataType = u16, repeatCountFromField = "n"),
        )
        assertEquals(CountSource.FromSlot("n"), (root.steps.last() as RepeatCount).count)
    }

    @Test
    fun `repeatUntil lowers to RepeatUntil carrying the condition`() {
        val cond = LiteralNode(true)
        val root = rootOf(FieldIR(name = "items", dataType = u8, repeatUntil = cond))
        assertEquals(cond, (root.steps.single() as RepeatUntil).condition)
    }

    @Test
    fun `isPresentIf wraps the field's steps in a Branch`() {
        val cond = LiteralNode(true)
        val root = rootOf(FieldIR(name = "opt", dataType = u8, isPresentIf = cond))
        val branch = root.steps.single() as Branch
        assertEquals(cond, branch.condition)
        assertEquals(listOf(ReadScalar("opt", u8, Endianness.NOT_APPLICABLE)), branch.then)
        assertEquals(emptyList<Step>(), branch.otherwise)
    }

    @Test
    fun `conditional data types lower to a Switch with one arm per rule`() {
        val ruleA = ConditionalDataTypeRuleIR(LiteralNode(true), u8)
        val ruleB = ConditionalDataTypeRuleIR(LiteralNode(false), u16)
        val root = rootOf(FieldIR(name = "v", dataType = u8, conditionalDataTypes = listOf(ruleA, ruleB)))
        val switch = root.steps.single() as Switch
        assertEquals(2, switch.arms.size)
        assertEquals(listOf(ReadScalar("v", u8, Endianness.NOT_APPLICABLE)), switch.arms[0].second)
        assertEquals(listOf(ReadScalar("v", u16, Endianness.BIG_ENDIAN)), switch.arms[1].second)
        assertEquals(listOf(ReadScalar("v", u8, Endianness.NOT_APPLICABLE)), switch.default)
    }

    @Test
    fun `valueFromExpression lowers to Bind and reads no bytes`() {
        val expr = LiteralNode(42L)
        val root = rootOf(FieldIR(name = "derived", dataType = u8, valueFromExpression = expr))
        assertEquals(listOf(Bind("derived", expr)), root.steps)
    }

    @Test
    fun `validIf lowers to an Assert after the read`() {
        val cond = LiteralNode(true)
        val root = rootOf(FieldIR(name = "n", dataType = u8, validIf = cond))
        assertTrue(root.steps[0] is ReadScalar)
        val assertion = root.steps[1] as Assert
        assertEquals(cond, assertion.condition)
        assertTrue(assertion.message.contains("n"), "expected the field name in: ${assertion.message}")
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*LoweringControlFlowTest*'`
Expected: FAIL — cast exceptions; `Lowering` still emits bare `ReadScalar`.

- [ ] **Step 3: Add control flow to `lowerField`**

Insert before the alignment/offset wrapping added in Task 4, so wrapping order is: repetition inside, then presence, then offset. Replace the read-emission block with:

```kotlin
        // A derived field consumes no bytes.
        if (field.valueFromExpression != null) {
            slots += Slot(field.name, slotTypeFor(field.dataType))
            steps += Bind(field.name, field.valueFromExpression!!)
            return
        }

        val read: List<Step> = when {
            field.conditionalDataTypes.isNotEmpty() -> listOf(
                Switch(
                    arms = field.conditionalDataTypes.map { rule ->
                        rule.condition to listOf(ReadScalar(field.name, rule.dataType, effectiveOrder(rule.dataType, byteOrder)))
                    },
                    default = listOf(ReadScalar(field.name, field.dataType, effectiveOrder(field.dataType, byteOrder))),
                )
            )
            else -> emitted  // the ExpectFixed / Nested / ReadScalar / ReadBytes list from tasks 2-3
        }

        val repeated: List<Step> = when {
            field.repeatCount != null ->
                listOf(RepeatCount(field.name, CountSource.Fixed(field.repeatCount!!), read))
            field.repeatCountFromField != null ->
                listOf(RepeatCount(field.name, CountSource.FromSlot(field.repeatCountFromField!!), read))
            field.repeatCountFromExpression != null ->
                listOf(RepeatCount(field.name, CountSource.FromExpr(field.repeatCountFromExpression!!), read))
            field.repeatUntil != null ->
                listOf(RepeatUntil(field.name, field.repeatUntil!!, read))
            else -> read
        }
        val isRepeated = repeated !== read
        if (isRepeated) {
            // Replace the scalar slot this field contributed with a list slot.
            slots.removeAll { it.name == field.name }
            slots += Slot(field.name, SlotType.LIST)
        }

        val guarded: List<Step> =
            if (field.isPresentIf != null) listOf(Branch(field.isPresentIf!!, repeated)) else repeated

        val checked: List<Step> =
            if (field.validIf != null) guarded + Assert(field.validIf!!, "field '${field.name}' failed validIf")
            else guarded
```

Then feed `checked` (rather than `emitted`) into the alignment/offset wrapping from Task 4.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test`
Expected: PASS — `LoweringControlFlowTest` (7 tests) plus tasks 2–4 green.

- [ ] **Step 5: Commit**

```bash
git add codegen/
git commit -m "feat(codegen): lower repetition, presence conditions, type dispatch and validIf"
```

---

### Task 6: Lowering — bits, enums, checksums, codecs and demands

**Files:**
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Demands.kt`
- Modify: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Lowering.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringDemandsTest.kt`

**Interfaces:**
- Consumes: `ReadBits`, `EnumMember`, `Verify`, `Decode`, `Cells`, `Capability`.
- Produces: `Demands.ofHel(expr: HELExpression): Set<Capability>`; `CodecPlan.demands` fully populated; `CodecPlan.enums` populated with one entry per enumerated field, keyed `"<struct>.<field>"`.

- [ ] **Step 1: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringDemandsTest.kt`:

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.hel.FunctionCallNode
import io.hexplain.core.hel.LiteralNode
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class LoweringDemandsTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val bytes = DataTypeIR("bytes", BaseType.BYTES, 0)

    private fun planOf(vararg fields: FieldIR): CodecPlan =
        Lowering.lower(FormatIR("Test", "Root", mapOf("Root" to StructIR("Root", fields.toList()))))

    @Test
    fun `a bit-level field becomes ReadBits and demands BITFIELDS`() {
        val plan = planOf(FieldIR(name = "flag", dataType = u8, bitLength = 3))
        assertEquals(ReadBits("flag", 3, BitOrder.MSB_FIRST), plan.structs.getValue("Root").steps.single())
        assertTrue(Capability.BITFIELDS in plan.demands)
    }

    @Test
    fun `an enumerated field registers the enumeration and emits EnumMember`() {
        val enumeration = EnumerationIR(listOf(EnumValueIR(1L, "https://example.org/One")))
        val plan = planOf(FieldIR(name = "kind", dataType = u8, enumeration = enumeration))
        assertEquals(enumeration, plan.enums["Root.kind"])
        assertEquals(EnumMember("kind", "Root.kind"), plan.structs.getValue("Root").steps.last())
    }

    @Test
    fun `an encoded field emits Decode with the codec ids in declaration order`() {
        val plan = planOf(FieldIR(name = "payload", dataType = bytes, size = 8, encodedWith = listOf("zlib", "delta")))
        assertEquals(Decode("payload", listOf("zlib", "delta")), plan.structs.getValue("Root").steps.last())
    }

    @Test
    fun `a checksum field emits Verify`() {
        val checksum = ChecksumIR(algorithm = "crc32", coversFromField = "a", coversToField = "b")
        val plan = planOf(
            FieldIR(name = "a", dataType = u8),
            FieldIR(name = "b", dataType = u8),
            FieldIR(name = "crc", dataType = u8, checksum = checksum),
        )
        assertEquals(Verify("crc", checksum), plan.structs.getValue("Root").steps.last())
    }

    @Test
    fun `a data layout emits Cells and demands CHUNKED_LAYOUT when the layout is chunked`() {
        val layout = DataLayoutIR(
            dimensions = listOf(DimensionIR(axis = "img:axisX", size = 4, chunkSize = 2)),
            cellDataType = u8,
            chunkOffsetsFromField = "offsets",
        )
        val plan = planOf(
            FieldIR(name = "offsets", dataType = u8, repeatCount = 2),
            FieldIR(name = "pixels", dataType = bytes, sizeToEndOfStream = true, hasDataLayout = layout),
        )
        assertTrue(plan.structs.getValue("Root").steps.any { it is Cells })
        assertTrue(Capability.CHUNKED_LAYOUT in plan.demands)
    }

    @Test
    fun `HEL builtins contribute their own capability demands`() {
        assertEquals(setOf(Capability.REGEX), Demands.ofHel(FunctionCallNode("matches", listOf(LiteralNode("x")))))
        assertEquals(setOf(Capability.DATETIME), Demands.ofHel(FunctionCallNode("datetime", listOf(LiteralNode("x")))))
        assertEquals(setOf(Capability.REGISTER_LOOKUP), Demands.ofHel(FunctionCallNode("inRegister", listOf(LiteralNode("x")))))
        assertEquals(setOf(Capability.GEOMETRY), Demands.ofHel(FunctionCallNode("ringOrientation", listOf(LiteralNode("x")))))
        assertEquals(emptySet<Capability>(), Demands.ofHel(FunctionCallNode("len", listOf(LiteralNode("x")))))
    }

    @Test
    fun `a HEL demand inside a field expression reaches the plan`() {
        val plan = planOf(FieldIR(name = "n", dataType = u8, validIf = FunctionCallNode("matches", listOf(LiteralNode("x")))))
        assertTrue(Capability.REGEX in plan.demands, "expected REGEX in ${plan.demands}")
    }

    @Test
    fun `a delimited struct demands DELIMITED_TEXT`() {
        val ir = FormatIR(
            "Test", "Root",
            mapOf("Root" to StructIR("Root", listOf(FieldIR(name = "n", dataType = u8)), delimited = DelimitedIR(DelimitedKind.RECORDS)))
        )
        assertTrue(Capability.DELIMITED_TEXT in Lowering.lower(ir).demands)
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*LoweringDemandsTest*'`
Expected: FAIL — `Unresolved reference: Demands`.

- [ ] **Step 3: Write `Demands.kt`**

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.Capability
import io.hexplain.core.hel.AstNode
import io.hexplain.core.hel.BinaryOpNode
import io.hexplain.core.hel.ConditionalNode
import io.hexplain.core.hel.FunctionCallNode
import io.hexplain.core.hel.UnaryOpNode

/**
 * What a HEL expression asks of a target runtime. The trivial builtins need nothing beyond the
 * runtime's own types; these four each drag in real support and so are declared, not assumed.
 */
object Demands {

    private val byFunction = mapOf(
        "matches" to Capability.REGEX,
        "datetime" to Capability.DATETIME,
        "evaluationInstant" to Capability.DATETIME,
        "inRegister" to Capability.REGISTER_LOOKUP,
        "ringOrientation" to Capability.GEOMETRY,
        "isSelfIntersecting" to Capability.GEOMETRY,
    )

    fun ofHel(expr: AstNode?): Set<Capability> {
        if (expr == null) return emptySet()
        val found = mutableSetOf<Capability>()
        collect(expr, found)
        return found
    }

    private fun collect(node: AstNode, into: MutableSet<Capability>) {
        when (node) {
            is FunctionCallNode -> {
                byFunction[node.name]?.let { into += it }
                node.args.forEach { collect(it, into) }
            }
            is BinaryOpNode -> { collect(node.left, into); collect(node.right, into) }
            is UnaryOpNode -> collect(node.operand, into)
            is ConditionalNode -> {
                collect(node.condition, into); collect(node.thenBranch, into); collect(node.elseBranch, into)
            }
            else -> Unit
        }
    }
}
```

- [ ] **Step 4: Add bits, enums, checksums, codecs, cells and demand collection to `Lowering.kt`**

In `lowerField`, before the scalar/bytes decision:

```kotlin
        if (field.bitLength != null) {
            demands += Capability.BITFIELDS
            slots += Slot(field.name, SlotType.INT)
            steps += ReadBits(field.name, field.bitLength!!, struct.bitOrder)
            return
        }
```

After the read steps are assembled (append to `checked` from Task 5, before offset wrapping):

```kotlin
        val decorated = buildList {
            addAll(checked)
            if (field.encodedWith.isNotEmpty()) add(Decode(field.name, field.encodedWith))
            field.hasDataLayout?.let { layout ->
                if (layout.dimensions.any { it.chunkSize != null || it.chunkSizeFromField != null } ||
                    layout.chunkOffsetsFromField != null
                ) demands += Capability.CHUNKED_LAYOUT
                add(Cells(field.name, layout))
            }
            field.enumeration?.let { enumeration ->
                val id = "${struct.name}.${field.name}"
                enums[id] = enumeration
                add(EnumMember(field.name, id))
            }
            field.checksum?.let { add(Verify(field.name, it)) }
        }
```

Collect HEL demands for every expression a field carries, at the top of `lowerField`:

```kotlin
        for (expr in listOf(
            field.isPresentIf, field.sizeFromExpression, field.repeatCountFromExpression,
            field.repeatUntil, field.valueFromExpression, field.validIf, field.atOffsetFromExpression,
            field.valueExpression,
        )) demands += Demands.ofHel(expr)
```

And in `lowerStruct`, before lowering fields:

```kotlin
        if (struct.delimited != null) demands += Capability.DELIMITED_TEXT
        demands += Demands.ofHel(struct.repeatUntil)
        demands += Demands.ofHel(struct.sizeFromExpression)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test`
Expected: PASS — `LoweringDemandsTest` (8 tests) plus tasks 2–5 green.

- [ ] **Step 6: Commit**

```bash
git add codegen/
git commit -m "feat(codegen): lower bitfields, enums, codecs, checksums, layouts and capability demands"
```

---

### Task 7: `runtime-kotlin` — the reader primitives

The contract every target runtime mirrors. **`runtime-kotlin` must not depend on `:core`.** A generated codec that needed the metaengine on its classpath would defeat the reach driver, and the Rust and C runtimes will have no such fallback — so the Kotlin one is held to the same standard, and its small duplication of `Finding` is the price.

**Files:**
- Create: `runtime-kotlin/build.gradle.kts`
- Create: `runtime-kotlin/src/main/kotlin/io/hexplain/rt/ByteReader.kt`
- Create: `runtime-kotlin/src/main/kotlin/io/hexplain/rt/Findings.kt`
- Test: `runtime-kotlin/src/test/kotlin/io/hexplain/rt/ByteReaderTest.kt`

**Interfaces:**
- Consumes: nothing from this repo.
- Produces: `ByteReader(data, pos)` with `position()`, `seek(Int)`, `regionEnd()`, `remaining()`, `region(size, body)`, `at(position, restore, body)`, `align(Long)`, `u8()`, `u16(be)`, `u32(be)`, `i8()`, `i16(be)`, `i32(be)`, `i64(be)`, `f32(be)`, `f64(be)`, `bytes(Int)`, `until(term, consume, include)`, `toRegionEnd()`, `expect(bytes, what)`, `bits(count, msbFirst)`, `alignToByte()`; `RtFinding`, `FindingSink`; `CodecFailure`.

- [ ] **Step 1: Create `runtime-kotlin/build.gradle.kts`**

```kotlin
plugins {
    kotlin("jvm") version libs.versions.kotlin.get()
}

repositories {
    mavenCentral()
}

dependencies {
    // Deliberately no project(":core"). A generated codec links this runtime alone.
    testImplementation(libs.junit.jupiter)
}

tasks.test {
    useJUnitPlatform()
}
```

- [ ] **Step 2: Write the failing test**

Create `runtime-kotlin/src/test/kotlin/io/hexplain/rt/ByteReaderTest.kt`:

```kotlin
package io.hexplain.rt

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class ByteReaderTest {

    @Test
    fun `reads unsigned scalars in both byte orders`() {
        val r = ByteReader(byteArrayOf(0xFF.toByte(), 0x01, 0x02))
        assertEquals(255, r.u8())
        assertEquals(0x0102, r.u16(be = true))
        val l = ByteReader(byteArrayOf(0x01, 0x02))
        assertEquals(0x0201, l.u16(be = false))
    }

    @Test
    fun `u32 does not sign-extend`() {
        val r = ByteReader(byteArrayOf(0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte()))
        assertEquals(4294967295L, r.u32(be = true))
    }

    @Test
    fun `a region bounds reads and skips trailing padding on exit`() {
        val r = ByteReader(byteArrayOf(1, 2, 3, 4, 9))
        val seen = r.region(4) { r.u8() }
        assertEquals(1, seen)
        assertEquals(4, r.position(), "the region must consume its full extent")
        assertEquals(9, r.u8())
    }

    @Test
    fun `reading past a region end fails rather than reading the next field`() {
        val r = ByteReader(byteArrayOf(1, 2, 3, 4))
        assertThrows<CodecFailure> { r.region(2) { r.bytes(3) } }
    }

    @Test
    fun `toRegionEnd stops at the region end, not the stream end`() {
        val r = ByteReader(byteArrayOf(1, 2, 3, 4))
        val inner = r.region(2) { r.toRegionEnd() }
        assertArrayEquals(byteArrayOf(1, 2), inner)
        assertArrayEquals(byteArrayOf(3, 4), r.toRegionEnd())
    }

    @Test
    fun `a restoring at() leaves the cursor where it was`() {
        val r = ByteReader(byteArrayOf(1, 2, 3, 4))
        r.u8()
        val v = r.at(position = 3, restore = true) { r.u8() }
        assertEquals(4, v)
        assertEquals(1, r.position())
    }

    @Test
    fun `until returns the value without the terminator and consumes it`() {
        val r = ByteReader(byteArrayOf('h'.code.toByte(), 'i'.code.toByte(), 0, 7))
        assertArrayEquals(byteArrayOf('h'.code.toByte(), 'i'.code.toByte()), r.until(byteArrayOf(0), consume = true, include = false))
        assertEquals(7, r.u8())
    }

    @Test
    fun `a missing terminator is a failure, not a silent read to end`() {
        val r = ByteReader(byteArrayOf(1, 2, 3))
        assertThrows<CodecFailure> { r.until(byteArrayOf(0), consume = true, include = false) }
    }

    @Test
    fun `bits read MSB-first by default and LSB-first on request`() {
        assertEquals(0b101L, ByteReader(byteArrayOf(0b10100000.toByte())).bits(3, msbFirst = true))
        assertEquals(0b101L, ByteReader(byteArrayOf(0b00000101.toByte())).bits(3, msbFirst = false))
    }

    @Test
    fun `align advances to the next boundary`() {
        val r = ByteReader(byteArrayOf(1, 2, 3, 4, 5))
        r.u8()
        r.align(4)
        assertEquals(4, r.position())
    }

    @Test
    fun `expect names the field when the constant does not match`() {
        val r = ByteReader(byteArrayOf(1, 2))
        val ex = assertThrows<CodecFailure> { r.expect(byteArrayOf(9, 9), "magic") }
        assertTrue(ex.message!!.contains("magic"), "expected the field name in: ${ex.message}")
    }
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./gradlew --offline :runtime-kotlin:test`
Expected: FAIL — `Unresolved reference: ByteReader`.

- [ ] **Step 4: Write `Findings.kt`**

```kotlin
package io.hexplain.rt

/** A codec could not proceed. Distinct from a finding: a failure stops, a finding is recorded. */
class CodecFailure(message: String) : RuntimeException(message)

/**
 * One discrepancy located in the stream. Deliberately not the metaengine's
 * `io.hexplain.core.conformance.Finding`: this runtime has no dependency on the engine, and the
 * Rust and C runtimes will carry the same five fields.
 */
data class RtFinding(
    val requirementId: String?,
    val constraintId: String?,
    val message: String,
    val byteOffset: Int?,
    val scope: String?,
)

/** Where a generated codec records findings. */
class FindingSink {
    private val items = mutableListOf<RtFinding>()
    fun add(finding: RtFinding) { items += finding }
    fun findings(): List<RtFinding> = items.toList()
    fun isConformant(): Boolean = items.isEmpty()
}
```

- [ ] **Step 5: Write `ByteReader.kt`**

```kotlin
package io.hexplain.rt

/**
 * The cursor a generated reader drives. Holds a region stack so a bounded container stops its
 * children at its own end, and a bit cursor for sub-byte fields.
 *
 * Every out-of-bounds condition raises [CodecFailure] with a message naming what was being read.
 * Silent truncation is never correct here: the generated C runtime will mirror this contract, and
 * there a permissive read is a memory-safety bug rather than a wrong value.
 */
class ByteReader(private val data: ByteArray, private var pos: Int = 0) {

    private val regionEnds = ArrayDeque<Int>()
    private var bitBuffer = 0
    private var bitCount = 0

    fun position(): Int = pos

    fun seek(position: Int) {
        require(position >= 0 && position <= data.size) { "seek out of range: $position" }
        alignToByte()
        pos = position
    }

    fun regionEnd(): Int = regionEnds.lastOrNull() ?: data.size

    fun remaining(): Int = regionEnd() - pos

    fun atEnd(): Boolean = remaining() <= 0

    /** Bounds [body] to [size] bytes from the current position, then advances past the whole extent. */
    fun <T> region(size: Int, body: () -> T): T {
        val start = pos
        val end = start + size
        if (end > regionEnd()) fail("region of $size bytes at $start exceeds its container")
        regionEnds.addLast(end)
        try {
            return body()
        } finally {
            regionEnds.removeLast()
            alignToByte()
            pos = end
        }
    }

    /** Runs [body] at [position]; with [restore], the cursor returns to where it was. */
    fun <T> at(position: Int, restore: Boolean, body: () -> T): T {
        val saved = pos
        seek(position)
        try {
            return body()
        } finally {
            if (restore) pos = saved
        }
    }

    fun align(boundary: Long) {
        alignToByte()
        val b = boundary.toInt()
        if (b > 1) {
            val overshoot = pos % b
            if (overshoot != 0) pos += b - overshoot
        }
    }

    private fun need(count: Int, what: String) {
        if (pos + count > regionEnd()) fail("$what needs $count bytes at $pos, only ${remaining()} available")
    }

    private fun fail(message: String): Nothing = throw CodecFailure(message)

    fun u8(): Int { need(1, "u8"); return data[pos++].toInt() and 0xFF }
    fun i8(): Int { need(1, "i8"); return data[pos++].toInt() }

    private fun read(count: Int, be: Boolean, what: String): Long {
        need(count, what)
        var acc = 0L
        if (be) for (i in 0 until count) acc = (acc shl 8) or (data[pos + i].toLong() and 0xFF)
        else for (i in count - 1 downTo 0) acc = (acc shl 8) or (data[pos + i].toLong() and 0xFF)
        pos += count
        return acc
    }

    fun u16(be: Boolean): Int = read(2, be, "u16").toInt()
    fun u32(be: Boolean): Long = read(4, be, "u32")
    fun u64(be: Boolean): Long = read(8, be, "u64")
    fun i16(be: Boolean): Int = read(2, be, "i16").toShort().toInt()
    fun i32(be: Boolean): Int = read(4, be, "i32").toInt()
    fun i64(be: Boolean): Long = read(8, be, "i64")
    fun f32(be: Boolean): Float = Float.fromBits(read(4, be, "f32").toInt())
    fun f64(be: Boolean): Double = Double.fromBits(read(8, be, "f64"))

    fun bytes(count: Int): ByteArray {
        need(count, "bytes")
        val out = data.copyOfRange(pos, pos + count)
        pos += count
        return out
    }

    fun toRegionEnd(): ByteArray = bytes(remaining())

    fun until(terminator: ByteArray, consume: Boolean, include: Boolean): ByteArray {
        val end = regionEnd()
        var scan = pos
        while (scan + terminator.size <= end) {
            var hit = true
            for (i in terminator.indices) if (data[scan + i] != terminator[i]) { hit = false; break }
            if (hit) {
                val valueEnd = if (include) scan + terminator.size else scan
                val out = data.copyOfRange(pos, valueEnd)
                pos = if (consume) scan + terminator.size else scan
                return out
            }
            scan++
        }
        fail("terminator not found before end of region at $pos")
    }

    fun expect(expected: ByteArray, what: String) {
        val actual = bytes(expected.size)
        if (!actual.contentEquals(expected)) {
            fail("$what: expected ${expected.toHex()}, found ${actual.toHex()}")
        }
    }

    fun bits(count: Int, msbFirst: Boolean): Long {
        require(count in 1..64) { "bit width out of range: $count" }
        var out = 0L
        var left = count
        while (left > 0) {
            if (bitCount == 0) {
                need(1, "bits")
                bitBuffer = data[pos++].toInt() and 0xFF
                bitCount = 8
            }
            val take = minOf(left, bitCount)
            val chunk = if (msbFirst) {
                val v = (bitBuffer shr (bitCount - take)) and ((1 shl take) - 1)
                bitCount -= take
                v
            } else {
                val v = bitBuffer and ((1 shl take) - 1)
                bitBuffer = bitBuffer shr take
                bitCount -= take
                v
            }
            out = if (msbFirst) (out shl take) or chunk.toLong() else out or (chunk.toLong() shl (count - left))
            left -= take
        }
        return out
    }

    /** Discards a partially consumed byte. Called before any byte-level operation. */
    fun alignToByte() { bitBuffer = 0; bitCount = 0 }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it) }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./gradlew --offline :runtime-kotlin:test`
Expected: PASS — 11 tests in `ByteReaderTest`.

- [ ] **Step 7: Commit**

```bash
git add runtime-kotlin/
git commit -m "feat(runtime-kotlin): reader primitives — cursor, regions, bits, terminators"
```

---

### Task 8: The Kotlin HEL emitter

**Files:**
- Create: `codegen-kotlin/build.gradle.kts`
- Create: `codegen-kotlin/src/main/kotlin/io/hexplain/codegen/kotlin/KotlinHelEmitter.kt`
- Test: `codegen-kotlin/src/test/kotlin/io/hexplain/codegen/kotlin/KotlinHelEmitterTest.kt`

**Interfaces:**
- Consumes: `io.hexplain.core.hel.*` AST nodes via `codegen`'s `api(project(":core"))`.
- Produces: `KotlinHelEmitter.emit(expr: HELExpression): String` — a Kotlin expression string. Slot access convention: `self.x` and a bare `x` both emit `slot("x")`; `root.x` emits `root("x")`; `stream.x` emits `stream("x")`. Task 9's emitted readers define those three helpers.

- [ ] **Step 1: Create `codegen-kotlin/build.gradle.kts`**

```kotlin
plugins {
    kotlin("jvm") version libs.versions.kotlin.get()
}

repositories {
    mavenCentral()
}

dependencies {
    api(project(":codegen"))
    testImplementation(libs.junit.jupiter)
}

tasks.test {
    useJUnitPlatform()
}
```

- [ ] **Step 2: Write the failing test**

Create `codegen-kotlin/src/test/kotlin/io/hexplain/codegen/kotlin/KotlinHelEmitterTest.kt`:

```kotlin
package io.hexplain.codegen.kotlin

import io.hexplain.core.hel.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class KotlinHelEmitterTest {

    private fun emit(expr: AstNode) = KotlinHelEmitter.emit(expr)

    @Test
    fun `literals keep their Kotlin type suffixes`() {
        assertEquals("42L", emit(LiteralNode(42L)))
        assertEquals("3.5", emit(LiteralNode(3.5)))
        assertEquals("true", emit(LiteralNode(true)))
        assertEquals("\"png\"", emit(LiteralNode("png")))
    }

    @Test
    fun `a string literal with a quote or backslash is escaped`() {
        assertEquals("\"a\\\"b\"", emit(LiteralNode("a\"b")))
        assertEquals("\"a\\\\b\"", emit(LiteralNode("a\\b")))
    }

    @Test
    fun `a bare accessor reads a slot of the current struct`() {
        assertEquals("""slot("width")""", emit(AccessorNode(listOf(Key("width")))))
    }

    @Test
    fun `self, root and stream select their scope`() {
        assertEquals("""slot("w")""", emit(AccessorNode(listOf(Key("self"), Key("w")))))
        assertEquals("""root("w")""", emit(AccessorNode(listOf(Key("root"), Key("w")))))
        assertEquals("""stream("size")""", emit(AccessorNode(listOf(Key("stream"), Key("size")))))
    }

    @Test
    fun `a nested path chains member lookups`() {
        assertEquals(
            """member(slot("header"), "width")""",
            emit(AccessorNode(listOf(Key("header"), Key("width")))),
        )
    }

    @Test
    fun `an index step emits element access with the index expression`() {
        assertEquals(
            """element(slot("items"), 2L)""",
            emit(AccessorNode(listOf(Key("items"), Index(LiteralNode(2L))))),
        )
    }

    @Test
    fun `binary operators are parenthesised so precedence cannot drift`() {
        val expr = BinaryOpNode(LiteralNode(1L), Token(TokenType.PLUS, "+"), LiteralNode(2L))
        assertEquals("(num(1L) + num(2L))", emit(expr))
    }

    @Test
    fun `equality compares values rather than boxed identities`() {
        val expr = BinaryOpNode(AccessorNode(listOf(Key("t"))), Token(TokenType.EQ, "=="), LiteralNode("IHDR"))
        assertEquals("""eq(slot("t"), "IHDR")""", emit(expr))
    }

    @Test
    fun `a conditional becomes a Kotlin if expression`() {
        val expr = ConditionalNode(LiteralNode(true), LiteralNode(1L), LiteralNode(2L))
        assertEquals("(if (bool(true)) 1L else 2L)", emit(expr))
    }

    @Test
    fun `trivial builtins map onto runtime helpers`() {
        assertEquals("""helLen(slot("s"))""", emit(FunctionCallNode("len", listOf(AccessorNode(listOf(Key("s")))))))
        assertEquals("""helEof()""", emit(FunctionCallNode("eof", emptyList())))
    }

    @Test
    fun `an unsupported builtin is refused by name rather than emitted as broken source`() {
        val ex = assertThrows<IllegalArgumentException> { emit(FunctionCallNode("partExtension", emptyList())) }
        assertTrue(ex.message!!.contains("partExtension"), "expected the function name in: ${ex.message}")
    }
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./gradlew --offline :codegen-kotlin:test`
Expected: FAIL — `Unresolved reference: KotlinHelEmitter`.

- [ ] **Step 4: Write `KotlinHelEmitter.kt`**

```kotlin
package io.hexplain.codegen.kotlin

import io.hexplain.core.hel.*

/**
 * HEL AST -> a Kotlin expression. Every value flows as `Any?` through helper functions the
 * generated reader defines, because a HEL slot may hold a Long, a Double, a String or a ByteArray
 * depending on the descriptor, and static Kotlin types would need the full type inference the
 * metaengine deliberately does without.
 *
 * The helpers (`slot`, `root`, `stream`, `member`, `element`, `num`, `bool`, `eq`, `hel*`) are
 * emitted once per generated file by [KotlinBackend].
 */
object KotlinHelEmitter {

    private val comparison = setOf(TokenType.EQ, TokenType.NEQ)

    private val builtins = mapOf(
        "len" to "helLen", "count" to "helLen", "sizeof" to "helSizeof", "eof" to "helEof",
        "substr" to "helSubstr", "substring" to "helSubstring", "startsWith" to "helStartsWith",
        "trim" to "helTrim", "toNumber" to "helToNumber", "concat" to "helConcat",
    )

    fun emit(expr: AstNode): String = when (expr) {
        is LiteralNode -> literal(expr.value)
        is AccessorNode -> accessor(expr)
        is UnaryOpNode -> unary(expr)
        is BinaryOpNode -> binary(expr)
        is ConditionalNode -> "(if (bool(${emit(expr.condition)})) ${emit(expr.thenBranch)} else ${emit(expr.elseBranch)})"
        is FunctionCallNode -> call(expr)
        else -> throw IllegalArgumentException("unsupported HEL node: ${expr::class.simpleName}")
    }

    private fun literal(value: Any): String = when (value) {
        is Long -> "${value}L"
        is Int -> "${value}L"
        is Double -> value.toString()
        is Boolean -> value.toString()
        is String -> "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
        else -> throw IllegalArgumentException("unsupported HEL literal: ${value::class.simpleName}")
    }

    private fun accessor(node: AccessorNode): String {
        val steps = node.path
        require(steps.isNotEmpty()) { "empty HEL accessor path" }
        val first = steps.first()
        require(first is Key) { "a HEL path must start with a name, not an index" }
        val scoped = when ((first as Key).name) {
            "self" -> "slot" to steps.drop(1)
            "root" -> "root" to steps.drop(1)
            "stream" -> "stream" to steps.drop(1)
            else -> "slot" to steps
        }
        val (scope, rest) = scoped
        require(rest.isNotEmpty()) { "a HEL path needs a name after '${(first as Key).name}'" }
        val head = rest.first()
        require(head is Key) { "a HEL path needs a name after its scope" }
        var out = "$scope(\"${(head as Key).name}\")"
        for (step in rest.drop(1)) {
            out = when (step) {
                is Key -> "member($out, \"${step.name}\")"
                is Index -> "element($out, ${emit(step.expr)})"
            }
        }
        return out
    }

    private fun unary(node: UnaryOpNode): String = when (node.op.type) {
        TokenType.NOT -> "(!bool(${emit(node.operand)}))"
        TokenType.MINUS -> "(-num(${emit(node.operand)}))"
        else -> throw IllegalArgumentException("unsupported HEL unary operator: ${node.op.value}")
    }

    private fun binary(node: BinaryOpNode): String {
        val left = emit(node.left)
        val right = emit(node.right)
        if (node.op.type in comparison) {
            val call = "eq($left, $right)"
            return if (node.op.type == TokenType.NEQ) "(!$call)" else call
        }
        return when (node.op.type) {
            TokenType.AND -> "(bool($left) && bool($right))"
            TokenType.OR -> "(bool($left) || bool($right))"
            TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
            TokenType.LT, TokenType.LTE, TokenType.GT, TokenType.GTE ->
                "(num($left) ${node.op.value} num($right))"
            else -> throw IllegalArgumentException("unsupported HEL operator: ${node.op.value}")
        }
    }

    private fun call(node: FunctionCallNode): String {
        val fn = builtins[node.name]
            ?: throw IllegalArgumentException(
                "the Kotlin backend does not support the HEL function '${node.name}'"
            )
        return "$fn(" + node.args.joinToString(", ") { emit(it) } + ")"
    }
}
```

- [ ] **Step 5: Reconcile the emitter with the real token names**

`TokenType` constant names in `core/src/main/kotlin/io/hexplain/core/hel/HelParser.kt` may differ from those used above (`PLUS`, `EQ`, `NOT`, …). Read that file and correct every `TokenType.X` reference in both the emitter and the test to the actual names before proceeding — do not add aliases to `core`.

Run: `./gradlew --offline :codegen-kotlin:compileKotlin`
Expected: PASS once the names match.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen-kotlin:test`
Expected: PASS — 11 tests in `KotlinHelEmitterTest`.

- [ ] **Step 7: Commit**

```bash
git add codegen-kotlin/
git commit -m "feat(codegen-kotlin): transpile HEL expressions to Kotlin source"
```

---

### Task 9: Backend SPI and T0 reader emission

**Scope decision:** a generated reader returns `MutableMap<String, Any>`, the same shape `Metaparser` produces. Typed data classes per struct are a real improvement and explicitly deferred — in phase 1 the map shape makes the differential assertion of Task 11 a direct `assertEquals`, which is the point of the phase.

**Files:**
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/backend/CodecBackend.kt`
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/backend/SourceFile.kt`
- Create: `codegen-kotlin/src/main/kotlin/io/hexplain/codegen/kotlin/KotlinBackend.kt`
- Create: `codegen-kotlin/src/main/resources/META-INF/services/io.hexplain.codegen.backend.CodecBackend`
- Test: `codegen-kotlin/src/test/kotlin/io/hexplain/codegen/kotlin/KotlinBackendTest.kt`
- Test resource: `codegen-kotlin/src/test/resources/golden/minimal-reader.kt.txt`

**Interfaces:**
- Consumes: `CodecPlan`, `Step` variants, `KotlinHelEmitter.emit`, `io.hexplain.rt.ByteReader` (by name only — `codegen-kotlin` emits `import io.hexplain.rt.*` but does not depend on `runtime-kotlin`).
- Produces: `interface CodecBackend { val id: String; val capabilities: Set<Capability>; fun emit(plan: CodecPlan, options: EmitOptions): List<SourceFile> }`; `data class SourceFile(val path: String, val content: String)`; `data class EmitOptions(val packageName: String, val className: String, val tier: Tier)`; `KotlinBackend`.

- [ ] **Step 1: Write `SourceFile.kt` and `CodecBackend.kt`**

```kotlin
package io.hexplain.codegen.backend

import io.hexplain.codegen.ir.Capability
import io.hexplain.codegen.ir.CodecPlan
import io.hexplain.codegen.ir.Tier

/** One emitted file. [path] is relative to the output directory and uses forward slashes. */
data class SourceFile(val path: String, val content: String)

data class EmitOptions(
    val packageName: String,
    val className: String,
    val tier: Tier = Tier.T0,
)

/**
 * A target language. Implementations are discovered by ServiceLoader, so adding a backend is
 * adding a module. A backend spells steps; it never re-derives what lowering decided.
 */
interface CodecBackend {
    val id: String
    val capabilities: Set<Capability>
    fun emit(plan: CodecPlan, options: EmitOptions): List<SourceFile>
}

/** The capabilities [plan] needs that [backend] does not supply. Empty means the pair is viable. */
fun unmetDemands(plan: CodecPlan, backend: CodecBackend, tier: Tier): Set<Capability> =
    (plan.demands + tier.implies) - backend.capabilities
```

- [ ] **Step 2: Write the failing test**

Create `codegen-kotlin/src/test/kotlin/io/hexplain/codegen/kotlin/KotlinBackendTest.kt`:

```kotlin
package io.hexplain.codegen.kotlin

import io.hexplain.codegen.backend.EmitOptions
import io.hexplain.codegen.ir.Tier
import io.hexplain.codegen.lower.Lowering
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class KotlinBackendTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val u32be = DataTypeIR("uint32be", BaseType.INTEGER, 32, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)

    private fun emit(ir: FormatIR): String {
        val plan = Lowering.lower(ir)
        val files = KotlinBackend().emit(plan, EmitOptions("gen.test", "MinimalCodec", Tier.T0))
        return files.single().content
    }

    private val minimal = FormatIR(
        name = "Minimal",
        rootStruct = "Root",
        structs = mapOf(
            "Root" to StructIR(
                "Root",
                listOf(
                    FieldIR(name = "magic", dataType = u8, fixedValue = byteArrayOf(0x4D, 0x49)),
                    FieldIR(name = "width", dataType = u32be),
                    FieldIR(name = "name", dataType = DataTypeIR("string", BaseType.STRING, 0), terminator = byteArrayOf(0)),
                ),
            )
        ),
    )

    @Test
    fun `the emitted file declares the requested package and class`() {
        val src = emit(minimal)
        assertTrue(src.startsWith("package gen.test\n"), "unexpected header:\n${src.take(120)}")
        assertTrue(src.contains("object MinimalCodec {"), "expected the object declaration in:\n$src")
    }

    @Test
    fun `the emitted file imports the runtime and nothing from core`() {
        val src = emit(minimal)
        assertTrue(src.contains("import io.hexplain.rt."), "expected a runtime import in:\n$src")
        assertFalse(src.contains("io.hexplain.core"), "generated code must not reference the engine:\n$src")
    }

    @Test
    fun `a fixed value emits an expect call naming the field`() {
        assertTrue(emit(minimal).contains("""r.expect(byteArrayOf(77, 73), "magic")"""), emit(minimal))
    }

    @Test
    fun `a big-endian u32 emits u32 with be = true`() {
        assertTrue(emit(minimal).contains("""out["width"] = r.u32(be = true)"""), emit(minimal))
    }

    @Test
    fun `a terminated string emits until and decodes it`() {
        assertTrue(emit(minimal).contains("""r.until(byteArrayOf(0), consume = true, include = false)"""), emit(minimal))
    }

    @Test
    fun `emission is deterministic across runs`() {
        assertEquals(emit(minimal), emit(minimal))
    }

    @Test
    fun `the emitted source matches the golden file`() {
        val golden = checkNotNull(javaClass.getResourceAsStream("/golden/minimal-reader.kt.txt")) {
            "golden file missing"
        }.readBytes().decodeToString().replace("\r\n", "\n")
        assertEquals(golden, emit(minimal))
    }

    @Test
    fun `a nested struct emits a call to that struct's read function`() {
        val ir = FormatIR(
            "N", "Root",
            mapOf(
                "Root" to StructIR("Root", listOf(FieldIR(name = "hdr", dataType = DataTypeIR("Header", BaseType.BYTES, 0)))),
                "Header" to StructIR("Header", listOf(FieldIR(name = "n", dataType = u8))),
            ),
        )
        val src = emit(ir)
        assertTrue(src.contains("""out["hdr"] = readHeader(r)"""), src)
        assertTrue(src.contains("private fun readHeader(r: ByteReader)"), src)
    }
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./gradlew --offline :codegen-kotlin:test --tests '*KotlinBackendTest*'`
Expected: FAIL — `Unresolved reference: KotlinBackend`.

- [ ] **Step 4: Write `KotlinBackend.kt`**

```kotlin
package io.hexplain.codegen.kotlin

import io.hexplain.codegen.backend.CodecBackend
import io.hexplain.codegen.backend.EmitOptions
import io.hexplain.codegen.backend.SourceFile
import io.hexplain.codegen.ir.*
import io.hexplain.core.ir.BaseType
import io.hexplain.core.ir.Endianness

/**
 * The reference backend. It exists to prove the lowering is complete before a second language can
 * be broken by a gap in it, so it stays as literal as possible: one Kotlin statement per step,
 * one private function per struct, no cleverness that a Rust or C emitter could not mirror.
 */
class KotlinBackend : CodecBackend {

    override val id: String = "kotlin"

    override val capabilities: Set<Capability> = setOf(
        Capability.BITFIELDS,
        Capability.POINTERS,
        Capability.CONDITIONAL_ENDIANNESS,
    )

    override fun emit(plan: CodecPlan, options: EmitOptions): List<SourceFile> {
        val out = StringBuilder()
        out.append("package ${options.packageName}\n\n")
        out.append("import io.hexplain.rt.ByteReader\n")
        out.append("import io.hexplain.rt.CodecFailure\n\n")
        out.append("// Generated from the Hexplain descriptor \"${plan.format}\". Do not edit.\n")
        out.append("object ${options.className} {\n\n")
        out.append("    fun read(data: ByteArray): MutableMap<String, Any> = ${fn(plan.root)}(ByteReader(data))\n\n")
        for (name in plan.structs.keys.sorted()) {
            emitStruct(plan.structs.getValue(name), out)
        }
        emitHelpers(out)
        out.append("}\n")
        return listOf(SourceFile("${options.packageName.replace('.', '/')}/${options.className}.kt", out.toString()))
    }

    /** Struct IRIs are not Kotlin identifiers; the local part is, after sanitising. */
    private fun fn(structName: String): String =
        "read" + structName.substringAfterLast('#').substringAfterLast('/')
            .replaceFirstChar { it.uppercase() }
            .filter { it.isLetterOrDigit() || it == '_' }

    private fun emitStruct(struct: StructPlan, out: StringBuilder) {
        out.append("    private fun ${fn(struct.name)}(r: ByteReader): MutableMap<String, Any> {\n")
        out.append("        val out = LinkedHashMap<String, Any>()\n")
        emitSteps(struct.steps, struct, out, indent = 2)
        out.append("        return out\n")
        out.append("    }\n\n")
    }

    private fun emitSteps(steps: List<Step>, struct: StructPlan, out: StringBuilder, indent: Int) {
        val pad = "    ".repeat(indent)
        for (step in steps) emitStep(step, struct, out, pad, indent)
    }

    private fun emitStep(step: Step, struct: StructPlan, out: StringBuilder, pad: String, indent: Int) {
        when (step) {
            is ExpectFixed ->
                out.append("$pad r.expect(${byteArrayLiteral(step.bytes)}, \"constant\")\n".trimStart(' ').prependIndent(pad).trimEnd() + "\n")
            is ReadScalar ->
                out.append("${pad}out[\"${step.slot}\"] = ${scalarCall(step)}\n")
            is ReadBits ->
                out.append("${pad}out[\"${step.slot}\"] = r.bits(${step.width}, msbFirst = ${struct.bitOrder == io.hexplain.core.ir.BitOrder.MSB_FIRST})\n")
            is ReadBytes ->
                out.append("${pad}out[\"${step.slot}\"] = ${bytesCall(step)}\n")
            is Skip -> out.append("${pad}${extentCall(step.extent)}\n")
            is Align -> out.append("${pad}r.align(${step.boundary}L)\n")
            is Nested -> {
                val call = "${fn(step.struct)}(r)"
                if (step.slot == null) out.append("$pad$call\n")
                else out.append("${pad}out[\"${step.slot}\"] = $call\n")
            }
            is Region -> {
                out.append("${pad}r.region(${intOf(extentBytes(step.extent))}) {\n")
                emitSteps(step.body, struct, out, indent + 1)
                out.append("$pad}\n")
            }
            is At -> {
                out.append("${pad}r.at(${offsetOf(step)}, restore = ${step.restore}) {\n")
                emitSteps(step.body, struct, out, indent + 1)
                out.append("$pad}\n")
            }
            is Branch -> {
                out.append("${pad}if (bool(${KotlinHelEmitter.emit(step.condition)})) {\n")
                emitSteps(step.then, struct, out, indent + 1)
                if (step.otherwise.isEmpty()) out.append("$pad}\n")
                else {
                    out.append("$pad} else {\n")
                    emitSteps(step.otherwise, struct, out, indent + 1)
                    out.append("$pad}\n")
                }
            }
            is Switch -> {
                out.append("${pad}when {\n")
                for ((condition, body) in step.arms) {
                    out.append("$pad    bool(${KotlinHelEmitter.emit(condition)}) -> {\n")
                    emitSteps(body, struct, out, indent + 2)
                    out.append("$pad    }\n")
                }
                out.append("$pad    else -> {\n")
                emitSteps(step.default, struct, out, indent + 2)
                out.append("$pad    }\n")
                out.append("$pad}\n")
            }
            is RepeatCount -> {
                out.append("${pad}run {\n")
                out.append("$pad    val items = ArrayList<Any>()\n")
                out.append("$pad    repeat(${countExpr(step.count)}) {\n")
                emitSteps(step.body, struct, out, indent + 2)
                out.append("$pad        out.remove(\"${step.slot}\")?.let { v -> items.add(v) }\n")
                out.append("$pad    }\n")
                out.append("$pad    out[\"${step.slot}\"] = items\n")
                out.append("$pad}\n")
            }
            is RepeatUntil -> {
                out.append("${pad}run {\n")
                out.append("$pad    val items = ArrayList<Any>()\n")
                out.append("$pad    while (true) {\n")
                emitSteps(step.body, struct, out, indent + 2)
                out.append("$pad        out.remove(\"${step.slot}\")?.let { v -> items.add(v) }\n")
                out.append("$pad        if (bool(${KotlinHelEmitter.emit(step.condition)})) break\n")
                out.append("$pad    }\n")
                out.append("$pad    out[\"${step.slot}\"] = items\n")
                out.append("$pad}\n")
            }
            is RepeatToEnd -> {
                out.append("${pad}run {\n")
                out.append("$pad    val items = ArrayList<Any>()\n")
                out.append("$pad    while (!r.atEnd()) {\n")
                emitSteps(step.body, struct, out, indent + 2)
                out.append("$pad        out.remove(\"${step.slot}\")?.let { v -> items.add(v) }\n")
                out.append("$pad    }\n")
                out.append("$pad    out[\"${step.slot}\"] = items\n")
                out.append("$pad}\n")
            }
            is Bind -> out.append("${pad}out[\"${step.slot}\"] = ${KotlinHelEmitter.emit(step.expr)} as Any\n")
            is Assert ->
                out.append("${pad}if (!bool(${KotlinHelEmitter.emit(step.condition)})) throw CodecFailure(${quote(step.message)})\n")
            // Tier-gated steps are not emitted at T0; lowering refuses the pair before we get here.
            is Infer, is Verify, is EnumMember, is Decode, is Cells,
            is EmitClass, is EmitProperty, is EmitEdge -> Unit
        }
    }

    private fun scalarCall(step: ReadScalar): String {
        val be = step.order != Endianness.LITTLE_ENDIAN
        val t = step.type
        return when (t.baseType) {
            BaseType.INTEGER -> when (t.bitWidth) {
                8 -> if (t.isSigned == true) "r.i8()" else "r.u8()"
                16 -> if (t.isSigned == true) "r.i16(be = $be)" else "r.u16(be = $be)"
                32 -> if (t.isSigned == true) "r.i32(be = $be)" else "r.u32(be = $be)"
                64 -> "r.i64(be = $be)"
                else -> throw IllegalArgumentException("unsupported integer width ${t.bitWidth} for '${step.slot}'")
            }
            BaseType.FLOAT -> if (t.bitWidth == 32) "r.f32(be = $be)" else "r.f64(be = $be)"
            else -> throw IllegalArgumentException("ReadScalar on a non-scalar type for '${step.slot}'")
        }
    }

    private fun bytesCall(step: ReadBytes): String {
        val raw = extentCall(step.extent)
        if (!step.asText) return raw
        val charset = step.charset ?: "UTF-8"
        val trimmed = if (step.trimNull) "trimNull($raw)" else raw
        return "String($trimmed, charset(\"$charset\"))"
    }

    private fun extentCall(extent: Extent): String = when (extent) {
        is Extent.FixedBytes -> "r.bytes(${extent.count.toInt()})"
        is Extent.FromSlot -> "r.bytes(num(slot(\"${extent.slot}\")).toInt())"
        is Extent.FromExpr -> "r.bytes(num(${KotlinHelEmitter.emit(extent.expr)}).toInt())"
        is Extent.Terminated ->
            "r.until(${byteArrayLiteral(extent.terminator)}, consume = ${extent.consume}, include = ${extent.include})"
        Extent.ToRegionEnd -> "r.toRegionEnd()"
        Extent.Intrinsic -> throw IllegalArgumentException("Intrinsic extent reached the byte reader")
    }

    private fun extentBytes(extent: Extent): String = when (extent) {
        is Extent.FixedBytes -> "${extent.count}L"
        is Extent.FromSlot -> "num(slot(\"${extent.slot}\"))"
        is Extent.FromExpr -> "num(${KotlinHelEmitter.emit(extent.expr)})"
        else -> throw IllegalArgumentException("a region needs a byte count, not $extent")
    }

    private fun intOf(expr: String) = "($expr).toInt()"

    private fun offsetOf(step: At): String {
        val raw = "num(${KotlinHelEmitter.emit(step.offset)}).toInt()"
        return when (step.base) {
            io.hexplain.core.ir.OffsetBase.STREAM_START -> raw
            io.hexplain.core.ir.OffsetBase.STREAM_END -> "(r.regionEnd() + $raw)"
            io.hexplain.core.ir.OffsetBase.CURRENT_POSITION -> "(r.position() + $raw)"
            io.hexplain.core.ir.OffsetBase.PARENT_START -> "(parentStart + $raw)"
        }
    }

    private fun countExpr(count: CountSource): String = when (count) {
        is CountSource.Fixed -> "${count.count.toInt()}"
        is CountSource.FromSlot -> "num(slot(\"${count.slot}\")).toInt()"
        is CountSource.FromExpr -> "num(${KotlinHelEmitter.emit(count.expr)}).toInt()"
    }

    private fun byteArrayLiteral(bytes: ByteArray): String =
        "byteArrayOf(" + bytes.joinToString(", ") { it.toString() } + ")"

    private fun quote(s: String) = "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

    /** The helper surface KotlinHelEmitter's output calls. Emitted once per file. */
    private fun emitHelpers(out: StringBuilder) {
        out.append(
            """
    private fun MutableMap<String, Any>.slotOf(name: String): Any? = this[name]
    private fun num(v: Any?): Long = when (v) {
        is Long -> v
        is Int -> v.toLong()
        is Double -> v.toLong()
        is String -> v.trim().toLong()
        else -> throw CodecFailure("expected a number, found ${'$'}{v?.javaClass?.simpleName}")
    }
    private fun bool(v: Any?): Boolean = when (v) {
        is Boolean -> v
        is Long -> v != 0L
        is Int -> v != 0
        else -> throw CodecFailure("expected a boolean, found ${'$'}{v?.javaClass?.simpleName}")
    }
    private fun eq(a: Any?, b: Any?): Boolean = when {
        a is ByteArray && b is ByteArray -> a.contentEquals(b)
        a is Number && b is Number -> a.toLong() == b.toLong()
        else -> a == b
    }
    private fun member(v: Any?, name: String): Any? = (v as? Map<*, *>)?.get(name)
    private fun element(v: Any?, index: Long): Any? = (v as? List<*>)?.getOrNull(index.toInt())
    private fun helLen(v: Any?): Long = when (v) {
        is ByteArray -> v.size.toLong()
        is String -> v.length.toLong()
        is List<*> -> v.size.toLong()
        is Map<*, *> -> v.size.toLong()
        else -> throw CodecFailure("len() needs a sized value")
    }
    private fun trimNull(b: ByteArray): ByteArray {
        val end = b.indexOfFirst { it == 0.toByte() }
        return if (end < 0) b else b.copyOfRange(0, end)
    }

"""
        )
    }
}
```

- [ ] **Step 5: Register the backend for ServiceLoader**

Create `codegen-kotlin/src/main/resources/META-INF/services/io.hexplain.codegen.backend.CodecBackend` containing exactly:

```
io.hexplain.codegen.kotlin.KotlinBackend
```

- [ ] **Step 6: Generate the golden file, then read it before trusting it**

Run the test once with the golden assertion disabled (comment out that one test), print the emitted source, and write it verbatim to `codegen-kotlin/src/test/resources/golden/minimal-reader.kt.txt` with LF line endings.

**Read the file you just wrote.** A golden file adopted without reading locks in whatever the emitter did, including bugs. Check: the `expect` call names the field, the `u32` call passes `be = true`, the terminated read appears, no `io.hexplain.core` reference survives, and indentation is consistent. Fix the emitter, not the golden file, for anything wrong.

Then re-enable the golden test.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen-kotlin:test`
Expected: PASS — 8 tests in `KotlinBackendTest`, 11 in `KotlinHelEmitterTest`.

- [ ] **Step 8: Commit**

```bash
git add codegen/ codegen-kotlin/
git commit -m "feat(codegen-kotlin): backend SPI and T0 reader emission"
```

---

### Task 10: The `hxc` CLI and capability refusal

**Files:**
- Create: `codegen/src/main/kotlin/io/hexplain/codegen/cli/Hxc.kt`
- Modify: `codegen/build.gradle.kts` (add the `application` plugin and a `runtimeOnly` on `codegen-kotlin`)
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/cli/HxcTest.kt`

**Interfaces:**
- Consumes: `ProfileLoader`, `RdfToIrCompiler` from `core`; `Lowering`; `CodecBackend`, `unmetDemands`, `EmitOptions`, `SourceFile`.
- Produces: `Hxc.run(args: List<String>, out: Appendable): Int` returning a process exit code; `Hxc.backends(): List<CodecBackend>`.

- [ ] **Step 1: Add the application wiring to `codegen/build.gradle.kts`**

```kotlin
plugins {
    kotlin("jvm") version libs.versions.kotlin.get()
    application
}

repositories {
    mavenCentral()
}

dependencies {
    api(project(":core"))
    // Backends are discovered by ServiceLoader at run time, never referenced at compile time.
    runtimeOnly(project(":codegen-kotlin"))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly(project(":codegen-kotlin"))
}

application {
    mainClass.set("io.hexplain.codegen.cli.HxcKt")
}

tasks.test {
    useJUnitPlatform()
}
```

`runtimeOnly` and not `implementation`: a compile-time reference from `codegen` to `codegen-kotlin` would invert the SPI and make `codegen` depend on every backend.

- [ ] **Step 2: Write the failing test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/cli/HxcTest.kt`:

```kotlin
package io.hexplain.codegen.cli

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Path
import kotlin.io.path.exists
import kotlin.io.path.readText

class HxcTest {

    private fun run(vararg args: String): Pair<Int, String> {
        val out = StringBuilder()
        val code = Hxc.run(args.toList(), out)
        return code to out.toString()
    }

    @Test
    fun `backends lists the kotlin backend and its capabilities`() {
        val (code, text) = run("backends")
        assertEquals(0, code)
        assertTrue(text.contains("kotlin"), text)
        assertTrue(text.contains("POINTERS"), text)
    }

    @Test
    fun `an unknown backend is refused by name`() {
        val (code, text) = run("gen", "--backend", "cobol", "--root", "urn:x", "x.ttl")
        assertEquals(2, code)
        assertTrue(text.contains("cobol"), text)
        assertTrue(text.contains("kotlin"), "the message should list what is available: $text")
    }

    @Test
    fun `gen writes a source file for the png profile`(@TempDir dir: Path) {
        val profile = Path.of("..", "core", "src", "test", "resources", "png-profile.ttl").toAbsolutePath()
        val (code, text) = run(
            "gen", "--backend", "kotlin",
            "--root", "https://hexplain.io/formats/png#File",
            "--package", "gen.png", "--class", "PngCodec",
            "--out", dir.toString(), profile.toString(),
        )
        assertEquals(0, code, text)
        val emitted = dir.resolve("gen/png/PngCodec.kt")
        assertTrue(emitted.exists(), "expected $emitted; output was:\n$text")
        assertTrue(emitted.readText().startsWith("package gen.png"), emitted.readText().take(80))
    }

    @Test
    fun `a missing required argument is reported rather than defaulted`() {
        val (code, text) = run("gen", "--backend", "kotlin", "x.ttl")
        assertEquals(2, code)
        assertTrue(text.contains("--root"), text)
    }
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*HxcTest*'`
Expected: FAIL — `Unresolved reference: Hxc`.

- [ ] **Step 4: Write `Hxc.kt`**

```kotlin
package io.hexplain.codegen.cli

import io.hexplain.codegen.backend.CodecBackend
import io.hexplain.codegen.backend.EmitOptions
import io.hexplain.codegen.backend.unmetDemands
import io.hexplain.codegen.ir.Tier
import io.hexplain.codegen.lower.Lowering
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import java.io.File
import java.util.ServiceLoader

/**
 * `hxc` — compile a descriptor to a codec.
 *
 * Refusal is a first-class outcome: a descriptor demanding a capability the chosen backend does
 * not supply exits non-zero naming both, rather than emitting source that silently drops a field.
 */
object Hxc {

    fun backends(): List<CodecBackend> =
        ServiceLoader.load(CodecBackend::class.java).toList().sortedBy { it.id }

    fun run(args: List<String>, out: Appendable): Int {
        if (args.isEmpty()) {
            out.append("usage: hxc <gen|backends|explain> [options] <profile.ttl>\n")
            return 2
        }
        return when (args.first()) {
            "backends" -> listBackends(out)
            "gen" -> generate(args.drop(1), out, write = true)
            "explain" -> generate(args.drop(1), out, write = false)
            else -> { out.append("unknown command '${args.first()}'\n"); 2 }
        }
    }

    private fun listBackends(out: Appendable): Int {
        for (backend in backends()) {
            out.append("${backend.id}: ${backend.capabilities.map { it.name }.sorted().joinToString(", ")}\n")
        }
        return 0
    }

    private fun generate(args: List<String>, out: Appendable, write: Boolean): Int {
        val flags = mutableMapOf<String, String>()
        val positional = mutableListOf<String>()
        var i = 0
        while (i < args.size) {
            val a = args[i]
            if (a.startsWith("--")) {
                if (i + 1 >= args.size) { out.append("$a needs a value\n"); return 2 }
                flags[a] = args[i + 1]; i += 2
            } else { positional += a; i += 1 }
        }

        val profile = positional.firstOrNull() ?: run { out.append("a profile path is required\n"); return 2 }
        val root = flags["--root"] ?: run { out.append("--root <struct IRI> is required\n"); return 2 }
        val backendId = flags["--backend"] ?: "kotlin"
        val available = backends()
        val backend = available.firstOrNull { it.id == backendId } ?: run {
            out.append("unknown backend '$backendId'; available: ${available.joinToString(", ") { it.id }}\n")
            return 2
        }
        val tier = Tier.valueOf(flags["--tier"] ?: "T0")

        val model = ProfileLoader().load(File(profile).inputStream())
        val formatIR = RdfToIrCompiler(model).compile(root)
        val plan = Lowering.lower(formatIR)

        val unmet = unmetDemands(plan, backend, tier)
        if (unmet.isNotEmpty()) {
            out.append(
                "backend '${backend.id}' cannot compile this descriptor at $tier.\n" +
                    "  missing: ${unmet.map { it.name }.sorted().joinToString(", ")}\n" +
                    "  supplied: ${backend.capabilities.map { it.name }.sorted().joinToString(", ")}\n"
            )
            return 3
        }
        if (!write) { out.append("ok: '${backend.id}' can compile '${plan.format}' at $tier\n"); return 0 }

        val options = EmitOptions(
            packageName = flags["--package"] ?: "gen",
            className = flags["--class"] ?: "Codec",
            tier = tier,
        )
        val outDir = File(flags["--out"] ?: "build/generated/codecs")
        for (file in backend.emit(plan, options)) {
            val target = File(outDir, file.path)
            target.parentFile.mkdirs()
            target.writeText(file.content)
            out.append("wrote ${target.path}\n")
        }
        return 0
    }
}

fun main(args: Array<String>) {
    val out = StringBuilder()
    val code = Hxc.run(args.toList(), out)
    print(out)
    if (code != 0) kotlin.system.exitProcess(code)
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test`
Expected: PASS — 4 tests in `HxcTest`. If `gen writes a source file for the png profile` fails with an unmet-capability exit code 3, that is a **correct** refusal telling you PNG needs a capability the T0 backend lacks: change that test to assert the refusal names the missing capability, and record which one in the commit message. Do not weaken the backend's declared capabilities to make it pass.

- [ ] **Step 6: Commit**

```bash
git add codegen/
git commit -m "feat(codegen): hxc CLI with backend discovery and capability refusal"
```

---

### Task 11: `codegen-verify` — build-time generation and the T0 differential

The task the phase exists to reach: the generated reader and `Metaparser` must produce the same tree.

**Files:**
- Create: `codegen-verify/build.gradle.kts`
- Create: `codegen-verify/src/main/kotlin/io/hexplain/verify/Fixtures.kt`
- Create: `codegen-verify/src/main/kotlin/io/hexplain/verify/GenerateMain.kt`
- Test: `codegen-verify/src/test/kotlin/io/hexplain/verify/ReaderDifferentialTest.kt`

**Interfaces:**
- Consumes: `Lowering`, `KotlinBackend`, `Metaparser`, `ByteReader`.
- Produces: `Fixtures.all: Map<String, Fixture>` where `Fixture(formatIR: FormatIR, bytes: ByteArray, className: String)`; generated objects `gen.verify.<ClassName>` each with `read(ByteArray): MutableMap<String, Any>`.

**Build order:** `:codegen-verify:main` compiles → `generateCodecs` runs `GenerateMain` on main's runtime classpath → the emitted sources land in the **test** source set → `compileTestKotlin` compiles them. No cycle.

- [ ] **Step 1: Create `codegen-verify/build.gradle.kts`**

```kotlin
plugins {
    kotlin("jvm") version libs.versions.kotlin.get()
}

repositories {
    mavenCentral()
}

val generatedDir = layout.buildDirectory.dir("generated/codecs")

dependencies {
    implementation(project(":codegen"))
    implementation(project(":codegen-kotlin"))
    implementation(project(":core"))
    testImplementation(project(":runtime-kotlin"))
    testImplementation(libs.junit.jupiter)
}

val generateCodecs by tasks.registering(JavaExec::class) {
    group = "verification"
    description = "Emit codecs for every differential fixture into the test source set."
    classpath = sourceSets["main"].runtimeClasspath
    mainClass.set("io.hexplain.verify.GenerateMainKt")
    args(generatedDir.get().asFile.absolutePath)
    outputs.dir(generatedDir)
}

sourceSets["test"].kotlin.srcDir(generatedDir)
tasks.named("compileTestKotlin") { dependsOn(generateCodecs) }

tasks.test {
    useJUnitPlatform()
}
```

- [ ] **Step 2: Write `Fixtures.kt`**

```kotlin
package io.hexplain.verify

import io.hexplain.core.hel.*
import io.hexplain.core.ir.*

/** One descriptor plus a byte sequence it describes, fed to both the metaengine and the codec. */
data class Fixture(val className: String, val formatIR: FormatIR, val bytes: ByteArray)

/**
 * Descriptors authored for differential testing, not borrowed from a real format. Phase 1's
 * Kotlin backend emits no codec or conformance steps, so a real format carrying zlib payloads
 * would compare unequal for a reason that says nothing about the lowering. PNG arrives in Task 15,
 * once the codec registry exists.
 */
object Fixtures {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val u16be = DataTypeIR("uint16be", BaseType.INTEGER, 16, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)
    private val u32be = DataTypeIR("uint32be", BaseType.INTEGER, 32, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)
    private val u32le = DataTypeIR("uint32le", BaseType.INTEGER, 32, isSigned = false, hasEndianness = Endianness.LITTLE_ENDIAN)
    private val text = DataTypeIR("string", BaseType.STRING, 0)
    private val blob = DataTypeIR("bytes", BaseType.BYTES, 0)

    /** Scalars in both orders, a counted repeat, a length-prefixed blob and a terminated string. */
    private val record: Fixture = Fixture(
        className = "DemoRecordCodec",
        formatIR = FormatIR(
            name = "DemoRecord",
            rootStruct = "Record",
            structs = mapOf(
                "Record" to StructIR(
                    name = "Record",
                    endianness = Endianness.BIG_ENDIAN,
                    fields = listOf(
                        FieldIR(name = "magic", dataType = u8, fixedValue = byteArrayOf(0x44, 0x52)),
                        FieldIR(name = "version", dataType = u8),
                        FieldIR(name = "width", dataType = u32be),
                        FieldIR(name = "heightLe", dataType = u32le),
                        FieldIR(name = "count", dataType = u8),
                        FieldIR(name = "samples", dataType = u16be, repeatCountFromField = "count"),
                        FieldIR(name = "payloadLen", dataType = u8),
                        FieldIR(name = "payload", dataType = blob, sizeFromField = "payloadLen"),
                        FieldIR(name = "label", dataType = text, terminator = byteArrayOf(0)),
                    ),
                )
            ),
        ),
        bytes = byteArrayOf(
            0x44, 0x52,                                     // magic "DR"
            0x01,                                           // version
            0x00, 0x00, 0x01, 0x00,                         // width = 256 (BE)
            0x80.toByte(), 0x00, 0x00, 0x00,                // heightLe = 128 (LE)
            0x02,                                           // count
            0x00, 0x0A, 0x00, 0x14,                         // samples = [10, 20]
            0x03,                                           // payloadLen
            0x07, 0x08, 0x09,                               // payload
            'o'.code.toByte(), 'k'.code.toByte(), 0x00,     // label "ok"
        ),
    )

    /** A nested struct inside an explicit region, plus a pointer read that must not move the cursor. */
    private val pointer: Fixture = Fixture(
        className = "DemoPointerCodec",
        formatIR = FormatIR(
            name = "DemoPointer",
            rootStruct = "File",
            structs = mapOf(
                "File" to StructIR(
                    name = "File",
                    endianness = Endianness.BIG_ENDIAN,
                    fields = listOf(
                        FieldIR(name = "header", dataType = DataTypeIR("Header", BaseType.BYTES, 0)),
                        FieldIR(
                            name = "far",
                            dataType = u16be,
                            atOffsetFromField = "farPtr",
                            offsetBase = OffsetBase.STREAM_START,
                        ),
                        FieldIR(name = "afterPointer", dataType = u8),
                    ),
                ),
                "Header" to StructIR(
                    name = "Header",
                    endianness = Endianness.BIG_ENDIAN,
                    size = 4,
                    fields = listOf(
                        FieldIR(name = "kind", dataType = u8),
                        FieldIR(name = "farPtr", dataType = u8),
                    ),
                ),
            ),
        ),
        bytes = byteArrayOf(
            0x11, 0x06, 0x00, 0x00,   // header: kind, farPtr = 6, then two padding bytes in the region
            0x22,                     // afterPointer, read sequentially right after the header
            0x00,                     // filler
            0xAB.toByte(), 0xCD.toByte(), // the pointer target at offset 6
        ),
    )

    val all: Map<String, Fixture> = mapOf("record" to record, "pointer" to pointer)
}
```

Note the pointer fixture: `farPtr` lives in a nested struct, so the lowered `At` offset expression resolves through the header slot. If lowering cannot express that today, Task 4's accessor emits `self.farPtr` against the wrong scope — fix the lowering, and add the scope resolution to `Lowering.offsetExpr`, rather than reshaping the fixture to dodge it.

- [ ] **Step 3: Write `GenerateMain.kt`**

```kotlin
package io.hexplain.verify

import io.hexplain.codegen.backend.EmitOptions
import io.hexplain.codegen.ir.Tier
import io.hexplain.codegen.kotlin.KotlinBackend
import io.hexplain.codegen.lower.Lowering
import java.io.File

/** Emits one codec per fixture into [args]`[0]`. Run by the `generateCodecs` Gradle task. */
fun main(args: Array<String>) {
    val outDir = File(args.first())
    outDir.mkdirs()
    val backend = KotlinBackend()
    for ((name, fixture) in Fixtures.all) {
        val plan = Lowering.lower(fixture.formatIR)
        val files = backend.emit(plan, EmitOptions("gen.verify", fixture.className, Tier.T0))
        for (file in files) {
            val target = File(outDir, file.path)
            target.parentFile.mkdirs()
            target.writeText(file.content)
            println("generated $name -> ${target.path}")
        }
    }
}
```

- [ ] **Step 4: Write the failing test**

Create `codegen-verify/src/test/kotlin/io/hexplain/verify/ReaderDifferentialTest.kt`:

```kotlin
package io.hexplain.verify

import io.hexplain.core.metacodec.Metaparser
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

/**
 * The acceptance gate. The generated reader and the metaparser must produce the same tree, so a
 * difference is a lowering or emission bug — never an acceptable variation.
 */
class ReaderDifferentialTest {

    /** Normalises so the comparison is about values, not about which collection type carries them. */
    private fun normalise(value: Any?): Any? = when (value) {
        is Map<*, *> -> value.entries
            .filterNot { (it.key as String).startsWith("__") }
            .associate { (it.key as String) to normalise(it.value) }
        is List<*> -> value.map { normalise(it) }
        is ByteArray -> value.toList()
        is Number -> value.toLong()
        else -> value
    }

    private fun assertSameTree(fixtureKey: String, generated: Any?) {
        val fixture = Fixtures.all.getValue(fixtureKey)
        val expected = Metaparser(fixture.formatIR).parse(fixture.bytes)
        assertEquals(normalise(expected), normalise(generated), "generated codec diverged from the metaparser")
    }

    @Test
    fun `the generated record reader agrees with the metaparser`() {
        assertSameTree("record", gen.verify.DemoRecordCodec.read(Fixtures.all.getValue("record").bytes))
    }

    @Test
    fun `the generated pointer reader agrees with the metaparser`() {
        assertSameTree("pointer", gen.verify.DemoPointerCodec.read(Fixtures.all.getValue("pointer").bytes))
    }

    @Test
    fun `the record fixture actually exercises every construct it claims to`() {
        val tree = Metaparser(Fixtures.all.getValue("record").formatIR).parse(Fixtures.all.getValue("record").bytes) as Map<*, *>
        assertEquals(256L, (tree["width"] as Number).toLong(), "big-endian scalar")
        assertEquals(128L, (tree["heightLe"] as Number).toLong(), "little-endian scalar")
        assertEquals(2, (tree["samples"] as List<*>).size, "counted repeat")
        assertEquals(3, (tree["payload"] as ByteArray).size, "length-prefixed blob")
        assertEquals("ok", tree["label"], "terminated string")
    }
}
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `./gradlew --offline :codegen-verify:test`
Expected: FAIL — generation runs, then either the generated sources do not compile or the trees differ.

- [ ] **Step 6: Make it pass, one divergence at a time**

Each failure is a real defect in Task 2–9 code. Work them in this order, re-running `./gradlew --offline :codegen-verify:test` after each:

1. **Compilation errors in generated source** — fix `KotlinBackend`'s emission, then regenerate the Task 9 golden file and re-read it.
2. **Wrong scalar values** — check `scalarCall`'s `be` derivation against `effectiveOrder`; a field-level `LITTLE_ENDIAN` must beat a struct-level `BIG_ENDIAN`.
3. **A repeat producing the wrong shape** — the metaparser stores a list under the field name; the emitted `RepeatCount` must too.
4. **The pointer read advancing the cursor** — `afterPointer` reads the wrong byte when `restore` is not honoured.
5. **The region not skipping its padding** — `header` must consume all 4 bytes.

Do not add special cases to `normalise` to hide a difference. Widening the normaliser to make a test pass converts the gate into decoration.

- [ ] **Step 7: Commit**

```bash
git add codegen-verify/
git commit -m "test(codegen-verify): T0 differential — generated readers agree with the metaparser"
```

---

### Task 12: `runtime-kotlin` — the writer primitives

**Files:**
- Create: `runtime-kotlin/src/main/kotlin/io/hexplain/rt/WriteBuffer.kt`
- Test: `runtime-kotlin/src/test/kotlin/io/hexplain/rt/WriteBufferTest.kt`

**Interfaces:**
- Consumes: `CodecFailure`.
- Produces: `WriteBuffer(maxBytes)` with `position()`, `size()`, `seek(Int)`, `u8(Int)`, `u16(Int, be)`, `u32(Long, be)`, `i32(Int, be)`, `i64(Long, be)`, `f32(Float, be)`, `f64(Double, be)`, `bytes(ByteArray)`, `bits(value, count, msbFirst)`, `alignToByte()`, `align(Long)`, `span(body)`, `toByteArray()`; `LayoutResolver.resolve(maxPasses, attempt)`.

- [ ] **Step 1: Write the failing test**

Create `runtime-kotlin/src/test/kotlin/io/hexplain/rt/WriteBufferTest.kt`:

```kotlin
package io.hexplain.rt

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class WriteBufferTest {

    @Test
    fun `writes scalars in both byte orders`() {
        val b = WriteBuffer()
        b.u8(0xFF)
        b.u16(0x0102, be = true)
        b.u16(0x0102, be = false)
        assertArrayEquals(byteArrayOf(0xFF.toByte(), 0x01, 0x02, 0x02, 0x01), b.toByteArray())
    }

    @Test
    fun `seek back and overwrite leaves the extent unchanged`() {
        val b = WriteBuffer()
        b.bytes(byteArrayOf(1, 2, 3, 4))
        b.seek(0)
        b.u8(9)
        assertArrayEquals(byteArrayOf(9, 2, 3, 4), b.toByteArray())
    }

    @Test
    fun `span reports the byte count written inside it`() {
        val b = WriteBuffer()
        b.u8(1)
        val written = b.span { b.bytes(byteArrayOf(1, 2, 3)) }
        assertEquals(3, written)
    }

    @Test
    fun `bits pack MSB-first and flush on alignment`() {
        val b = WriteBuffer()
        b.bits(0b101, 3, msbFirst = true)
        b.bits(0b11, 2, msbFirst = true)
        b.alignToByte()
        assertArrayEquals(byteArrayOf(0b10111000.toByte()), b.toByteArray())
    }

    @Test
    fun `exceeding the output limit fails rather than growing without bound`() {
        val b = WriteBuffer(maxBytes = 4)
        assertThrows<CodecFailure> { b.bytes(ByteArray(5)) }
    }

    @Test
    fun `the layout resolver reaches a fixed point when a length feeds a later write`() {
        var passes = 0
        val sizes = mutableMapOf<String, Int>()
        val result = LayoutResolver.resolve(maxPasses = 8) {
            passes++
            val b = WriteBuffer()
            b.u8(sizes["payload"] ?: 0)          // the length field, unknown on the first pass
            val n = b.span { b.bytes(byteArrayOf(7, 7, 7)) }
            val stable = sizes["payload"] == n
            sizes["payload"] = n
            LayoutResolver.Attempt(bytes = b.toByteArray(), stable = stable)
        }
        assertArrayEquals(byteArrayOf(3, 7, 7, 7), result)
        assertEquals(2, passes, "one pass to learn the length, one to write it")
    }

    @Test
    fun `a layout that never stabilises fails instead of looping`() {
        var n = 0
        val ex = assertThrows<CodecFailure> {
            LayoutResolver.resolve(maxPasses = 4) {
                LayoutResolver.Attempt(bytes = ByteArray(n++), stable = false)
            }
        }
        assertTrue(ex.message!!.contains("4"), "expected the pass limit in: ${ex.message}")
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./gradlew --offline :runtime-kotlin:test --tests '*WriteBufferTest*'`
Expected: FAIL — `Unresolved reference: WriteBuffer`.

- [ ] **Step 3: Write `WriteBuffer.kt`**

```kotlin
package io.hexplain.rt

/**
 * A seek-capable growing output buffer. Generated writers write forward and seek back to fill in
 * values they could not know yet; [LayoutResolver] runs the whole write repeatedly until the
 * lengths and offsets stop changing.
 *
 * This mirrors the metawriter's bounded deterministic passes. It lives here, not in generated
 * code, because reimplementing fixpoint layout resolution once per target language is the largest
 * avoidable risk on the write path.
 */
class WriteBuffer(private val maxBytes: Int = 256 * 1024 * 1024) {

    private var data = ByteArray(256)
    private var pos = 0
    private var extent = 0
    private var bitBuffer = 0
    private var bitCount = 0

    fun position(): Int = pos
    fun size(): Int = extent

    fun seek(position: Int) {
        alignToByte()
        require(position >= 0) { "negative seek: $position" }
        ensure(position)
        pos = position
    }

    private fun ensure(end: Int) {
        if (end > maxBytes) throw CodecFailure("output exceeds the $maxBytes byte limit")
        if (end > data.size) {
            var size = data.size
            while (size < end) size *= 2
            data = data.copyOf(minOf(size, maxBytes))
        }
        if (end > extent) extent = end
    }

    private fun put(byte: Int) {
        ensure(pos + 1)
        data[pos++] = byte.toByte()
    }

    fun u8(value: Int) { alignToByte(); put(value and 0xFF) }

    private fun write(value: Long, count: Int, be: Boolean) {
        alignToByte()
        ensure(pos + count)
        if (be) for (i in count - 1 downTo 0) put(((value shr (8 * i)) and 0xFF).toInt())
        else for (i in 0 until count) put(((value shr (8 * i)) and 0xFF).toInt())
    }

    fun u16(value: Int, be: Boolean) = write(value.toLong(), 2, be)
    fun u32(value: Long, be: Boolean) = write(value, 4, be)
    fun i32(value: Int, be: Boolean) = write(value.toLong(), 4, be)
    fun i64(value: Long, be: Boolean) = write(value, 8, be)
    fun f32(value: Float, be: Boolean) = write(value.toRawBits().toLong() and 0xFFFFFFFFL, 4, be)
    fun f64(value: Double, be: Boolean) = write(value.toRawBits(), 8, be)

    fun bytes(value: ByteArray) {
        alignToByte()
        ensure(pos + value.size)
        value.copyInto(data, pos)
        pos += value.size
    }

    fun align(boundary: Long) {
        alignToByte()
        val b = boundary.toInt()
        if (b > 1) {
            val overshoot = pos % b
            if (overshoot != 0) {
                val padding = b - overshoot
                ensure(pos + padding)
                pos += padding
            }
        }
    }

    fun bits(value: Long, count: Int, msbFirst: Boolean) {
        require(count in 1..64) { "bit width out of range: $count" }
        for (i in 0 until count) {
            val bit = if (msbFirst) (value shr (count - 1 - i)) and 1L else (value shr i) and 1L
            bitBuffer = if (msbFirst) (bitBuffer shl 1) or bit.toInt() else bitBuffer or (bit.toInt() shl bitCount)
            bitCount++
            if (bitCount == 8) { put(bitBuffer); bitBuffer = 0; bitCount = 0 }
        }
    }

    /** Flushes a partially filled byte, zero-padding it. */
    fun alignToByte() {
        if (bitCount > 0) {
            put(bitBuffer shl (8 - bitCount))
            bitBuffer = 0
            bitCount = 0
        }
    }

    /** Runs [body] and returns how many bytes it wrote — the value an `Infer(SIZE)` needs. */
    fun span(body: () -> Unit): Int {
        alignToByte()
        val start = pos
        body()
        alignToByte()
        return pos - start
    }

    fun toByteArray(): ByteArray {
        alignToByte()
        return data.copyOf(extent)
    }
}

/**
 * Runs a whole write repeatedly until the lengths and offsets it computes stop changing.
 * Deterministic and bounded: an oscillating descriptor fails loudly rather than looping.
 */
object LayoutResolver {

    data class Attempt(val bytes: ByteArray, val stable: Boolean)

    fun resolve(maxPasses: Int = 32, attempt: () -> Attempt): ByteArray {
        var last: ByteArray? = null
        for (pass in 1..maxPasses) {
            val result = attempt()
            last = result.bytes
            if (result.stable) return result.bytes
        }
        throw CodecFailure(
            "layout did not stabilise within $maxPasses passes" +
                (last?.let { " (last attempt was ${it.size} bytes)" } ?: "")
        )
    }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./gradlew --offline :runtime-kotlin:test`
Expected: PASS — 7 tests in `WriteBufferTest`, 11 in `ByteReaderTest`.

- [ ] **Step 5: Commit**

```bash
git add runtime-kotlin/
git commit -m "feat(runtime-kotlin): write buffer and bounded fixpoint layout resolution"
```

---

### Task 13: T1 writer emission

The same `CodecPlan`, walked in write mode. `Infer` steps are where the writer computes what the caller did not supply.

**Files:**
- Create: `codegen-kotlin/src/main/kotlin/io/hexplain/codegen/kotlin/KotlinWriterEmitter.kt`
- Modify: `codegen-kotlin/src/main/kotlin/io/hexplain/codegen/kotlin/KotlinBackend.kt` (emit a writer when `options.tier >= T1`; add `Capability.WRITE` to `capabilities`)
- Modify: `codegen/src/main/kotlin/io/hexplain/codegen/lower/Lowering.kt` (emit `Infer` for fields another field's extent or count depends on)
- Test: `codegen-kotlin/src/test/kotlin/io/hexplain/codegen/kotlin/KotlinWriterEmitterTest.kt`
- Test: `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringInferTest.kt`

**Interfaces:**
- Consumes: `WriteBuffer`, `LayoutResolver` (by import name only), `CodecPlan`.
- Produces: `KotlinWriterEmitter.emit(plan, options): String`; the generated object gains `fun write(value: Map<String, Any>): ByteArray`.

- [ ] **Step 1: Write the failing lowering test**

Create `codegen/src/test/kotlin/io/hexplain/codegen/lower/LoweringInferTest.kt`:

```kotlin
package io.hexplain.codegen.lower

import io.hexplain.codegen.ir.*
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class LoweringInferTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val blob = DataTypeIR("bytes", BaseType.BYTES, 0)

    private fun rootOf(vararg fields: FieldIR): StructPlan =
        Lowering.lower(FormatIR("T", "Root", mapOf("Root" to StructIR("Root", fields.toList())))).structs.getValue("Root")

    @Test
    fun `a field used as another field's size is marked Infer SIZE`() {
        val root = rootOf(
            FieldIR(name = "len", dataType = u8),
            FieldIR(name = "data", dataType = blob, sizeFromField = "len"),
        )
        assertTrue(root.steps.any { it == Infer("len", InferKind.SIZE) }, "no Infer(len) in ${root.steps}")
    }

    @Test
    fun `a field used as a repeat count is marked Infer COUNT`() {
        val root = rootOf(
            FieldIR(name = "n", dataType = u8),
            FieldIR(name = "items", dataType = u8, repeatCountFromField = "n"),
        )
        assertTrue(root.steps.any { it == Infer("n", InferKind.COUNT) }, "no Infer(n) in ${root.steps}")
    }

    @Test
    fun `a field nothing depends on is not marked Infer`() {
        val root = rootOf(FieldIR(name = "version", dataType = u8))
        assertTrue(root.steps.none { it is Infer }, "unexpected Infer in ${root.steps}")
    }

    @Test
    fun `the Infer step sits immediately before the read it annotates`() {
        val root = rootOf(
            FieldIR(name = "len", dataType = u8),
            FieldIR(name = "data", dataType = blob, sizeFromField = "len"),
        )
        val i = root.steps.indexOfFirst { it is Infer }
        assertTrue(root.steps[i + 1] is ReadScalar, "expected the read after the Infer, got ${root.steps[i + 1]}")
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./gradlew --offline :codegen:test --tests '*LoweringInferTest*'`
Expected: FAIL — no `Infer` steps are produced.

- [ ] **Step 3: Emit `Infer` in `Lowering.lowerStruct`**

Compute the dependency set once per struct, before lowering fields, and pass it into `lowerField`:

```kotlin
        val inferred: Map<String, InferKind> = buildMap {
            for (f in struct.fields) {
                f.sizeFromField?.let { put(it, InferKind.SIZE) }
                f.repeatCountFromField?.let { put(it, InferKind.COUNT) }
                f.atOffsetFromField?.let { put(it, InferKind.OFFSET) }
            }
            struct.sizeFromField?.let { put(it, InferKind.SIZE) }
        }
```

In `lowerField`, immediately before appending the field's steps:

```kotlin
        inferred[field.name]?.let { kind -> steps += Infer(field.name, kind) }
```

- [ ] **Step 4: Write the failing writer-emitter test**

Create `codegen-kotlin/src/test/kotlin/io/hexplain/codegen/kotlin/KotlinWriterEmitterTest.kt`:

```kotlin
package io.hexplain.codegen.kotlin

import io.hexplain.codegen.backend.EmitOptions
import io.hexplain.codegen.ir.Tier
import io.hexplain.codegen.lower.Lowering
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class KotlinWriterEmitterTest {

    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)
    private val u32be = DataTypeIR("uint32be", BaseType.INTEGER, 32, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)
    private val blob = DataTypeIR("bytes", BaseType.BYTES, 0)

    private val ir = FormatIR(
        "W", "Root",
        mapOf(
            "Root" to StructIR(
                "Root",
                listOf(
                    FieldIR(name = "magic", dataType = u8, fixedValue = byteArrayOf(0x57)),
                    FieldIR(name = "width", dataType = u32be),
                    FieldIR(name = "len", dataType = u8),
                    FieldIR(name = "data", dataType = blob, sizeFromField = "len"),
                ),
            )
        ),
    )

    private fun emit(tier: Tier): String =
        KotlinBackend().emit(Lowering.lower(ir), EmitOptions("gen.w", "WCodec", tier)).single().content

    @Test
    fun `T0 emits no writer`() {
        assertFalse(emit(Tier.T0).contains("fun write("), "T0 must not emit a writer")
    }

    @Test
    fun `T1 emits a write entry point returning bytes`() {
        assertTrue(emit(Tier.T1).contains("fun write(value: Map<String, Any>): ByteArray"), emit(Tier.T1))
    }

    @Test
    fun `the writer runs inside the layout resolver`() {
        assertTrue(emit(Tier.T1).contains("LayoutResolver.resolve("), emit(Tier.T1))
    }

    @Test
    fun `a fixed value is written from the descriptor, not from the caller's map`() {
        assertTrue(emit(Tier.T1).contains("w.bytes(byteArrayOf(87))"), emit(Tier.T1))
    }

    @Test
    fun `an inferred length is computed from the span rather than read from the map`() {
        val src = emit(Tier.T1)
        assertTrue(src.contains("""inferred["len"]"""), src)
        assertTrue(src.contains("w.span {"), src)
    }

    @Test
    fun `the kotlin backend declares the WRITE capability`() {
        assertTrue(io.hexplain.codegen.ir.Capability.WRITE in KotlinBackend().capabilities)
    }
}
```

- [ ] **Step 5: Run it to verify it fails**

Run: `./gradlew --offline :codegen-kotlin:test --tests '*KotlinWriterEmitterTest*'`
Expected: FAIL — no `write` function is emitted.

- [ ] **Step 6: Write `KotlinWriterEmitter.kt`**

```kotlin
package io.hexplain.codegen.kotlin

import io.hexplain.codegen.backend.EmitOptions
import io.hexplain.codegen.ir.*
import io.hexplain.core.ir.BaseType
import io.hexplain.core.ir.Endianness

/**
 * Write mode over the same plan. Two rules make this tractable:
 *
 *  - a value the descriptor fixes (a constant, an inferred length or count) comes from the plan,
 *    never from the caller's map — a caller cannot make a file inconsistent with its descriptor;
 *  - every `Infer` slot is resolved by the runtime's fixpoint passes, so the emitted code measures
 *    spans and re-runs, it does not compute layout arithmetic itself.
 */
object KotlinWriterEmitter {

    fun emit(plan: CodecPlan, options: EmitOptions, fn: (String) -> String): String {
        val out = StringBuilder()
        out.append("    fun write(value: Map<String, Any>): ByteArray {\n")
        out.append("        val inferred = HashMap<String, Any>()\n")
        out.append("        return LayoutResolver.resolve(maxPasses = 32) {\n")
        out.append("            val w = WriteBuffer()\n")
        out.append("            val before = HashMap(inferred)\n")
        out.append("            ${fn(plan.root)}(w, value, inferred)\n")
        out.append("            LayoutResolver.Attempt(bytes = w.toByteArray(), stable = before == inferred)\n")
        out.append("        }\n")
        out.append("    }\n\n")
        for (name in plan.structs.keys.sorted()) {
            emitStruct(plan.structs.getValue(name), out, fn)
        }
        return out.toString()
    }

    private fun emitStruct(struct: StructPlan, out: StringBuilder, fn: (String) -> String) {
        out.append("    private fun ${fn(struct.name)}(w: WriteBuffer, value: Map<String, Any>, inferred: MutableMap<String, Any>) {\n")
        emitSteps(struct.steps, struct, out, indent = 2, fn = fn)
        out.append("    }\n\n")
    }

    private fun emitSteps(steps: List<Step>, struct: StructPlan, out: StringBuilder, indent: Int, fn: (String) -> String) {
        val pad = "    ".repeat(indent)
        for (step in steps) emitStep(step, struct, out, pad, indent, fn)
    }

    /** The value written for [slot]: an inferred value wins over whatever the caller supplied. */
    private fun source(slot: String) = """(inferred["$slot"] ?: value["$slot"])"""

    private fun emitStep(step: Step, struct: StructPlan, out: StringBuilder, pad: String, indent: Int, fn: (String) -> String) {
        when (step) {
            is ExpectFixed -> out.append("${pad}w.bytes(${byteArrayLiteral(step.bytes)})\n")
            is ReadScalar -> out.append("${pad}${scalarWrite(step)}\n")
            is ReadBits ->
                out.append("${pad}w.bits(num(${source(step.slot)}), ${step.width}, msbFirst = ${struct.bitOrder == io.hexplain.core.ir.BitOrder.MSB_FIRST})\n")
            is ReadBytes -> out.append("${pad}w.bytes(asBytes(${source(step.slot)}))\n")
            is Align -> out.append("${pad}w.align(${step.boundary}L)\n")
            is Nested -> out.append("${pad}${fn(step.struct)}(w, asMap(${source(step.slot!!)}), inferred)\n")
            is Infer -> {
                // The value is measured, not supplied. A SIZE is the span of what follows; a COUNT
                // is the length of the list the dependent field carries.
                when (step.kind) {
                    InferKind.SIZE, InferKind.OFFSET -> Unit // filled by the enclosing span/Region below
                    InferKind.COUNT -> Unit
                    InferKind.CHECKSUM -> Unit
                }
                out.append("${pad}// inferred: ${step.slot} (${step.kind})\n")
            }
            is Region -> {
                out.append("${pad}run {\n")
                out.append("$pad    val n = w.span {\n")
                emitSteps(step.body, struct, out, indent + 2, fn)
                out.append("$pad    }\n")
                (step.extent as? Extent.FromSlot)?.let {
                    out.append("$pad    inferred[\"${it.slot}\"] = n.toLong()\n")
                }
                out.append("$pad}\n")
            }
            is RepeatCount -> {
                out.append("${pad}run {\n")
                out.append("$pad    val items = asList(${source(step.slot)})\n")
                (step.count as? CountSource.FromSlot)?.let {
                    out.append("$pad    inferred[\"${it.slot}\"] = items.size.toLong()\n")
                }
                out.append("$pad    for (item in items) {\n")
                out.append("$pad        val value = asMapOrSelf(item, \"${step.slot}\")\n")
                emitSteps(step.body, struct, out, indent + 2, fn)
                out.append("$pad    }\n")
                out.append("$pad}\n")
            }
            is RepeatUntil, is RepeatToEnd -> {
                out.append("${pad}run {\n")
                out.append("$pad    for (item in asList(${source(step.slot)})) {\n")
                out.append("$pad        val value = asMapOrSelf(item, \"${step.slot}\")\n")
                emitSteps(bodyOf(step), struct, out, indent + 2, fn)
                out.append("$pad    }\n")
                out.append("$pad}\n")
            }
            is Branch -> {
                out.append("${pad}if (${source(step.condition.let { "" }).let { "true" }}) {\n") // replaced below
                out.append("$pad}\n")
            }
            else -> Unit
        }
    }

    private fun bodyOf(step: Step): List<Step> = when (step) {
        is RepeatUntil -> step.body
        is RepeatToEnd -> step.body
        else -> emptyList()
    }

    private fun scalarWrite(step: ReadScalar): String {
        val be = step.order != Endianness.LITTLE_ENDIAN
        val v = "num(${source(step.slot)})"
        val t = step.type
        return when (t.baseType) {
            BaseType.INTEGER -> when (t.bitWidth) {
                8 -> "w.u8($v.toInt())"
                16 -> "w.u16($v.toInt(), be = $be)"
                32 -> "w.u32($v, be = $be)"
                64 -> "w.i64($v, be = $be)"
                else -> throw IllegalArgumentException("unsupported integer width ${t.bitWidth} for '${step.slot}'")
            }
            BaseType.FLOAT -> if (t.bitWidth == 32) "w.f32(dbl(${source(step.slot)}).toFloat(), be = $be)"
                              else "w.f64(dbl(${source(step.slot)}), be = $be)"
            else -> throw IllegalArgumentException("scalar write on a non-scalar type for '${step.slot}'")
        }
    }

    private fun byteArrayLiteral(bytes: ByteArray): String =
        "byteArrayOf(" + bytes.joinToString(", ") { it.toString() } + ")"
}
```

- [ ] **Step 7: Fix the `Branch` case you just saw**

The `Branch` arm above is deliberately broken — a placeholder that compiles but writes nothing, left visible rather than hidden. Replace it with the real emission, mirroring the reader:

```kotlin
            is Branch -> {
                out.append("${pad}if (bool(${KotlinHelEmitter.emit(step.condition)})) {\n")
                emitSteps(step.then, struct, out, indent + 1, fn)
                if (step.otherwise.isEmpty()) out.append("$pad}\n")
                else {
                    out.append("$pad} else {\n")
                    emitSteps(step.otherwise, struct, out, indent + 1, fn)
                    out.append("$pad}\n")
                }
            }
```

HEL accessors in write mode read from the caller's map, so the writer's helper block must define `slot(name)` as `(inferred[name] ?: value[name])` rather than `out[name]`. Add that variant to the emitted helpers.

- [ ] **Step 8: Wire the writer into `KotlinBackend`**

Add `Capability.WRITE` to `capabilities`, add the writer's helpers (`asBytes`, `asMap`, `asList`, `asMapOrSelf`, `dbl`) to `emitHelpers`, and in `emit`, after the reader functions:

```kotlin
        if (options.tier != Tier.T0) {
            out.append("import io.hexplain.rt.WriteBuffer\n")  // hoist this to the import block
            out.append(KotlinWriterEmitter.emit(plan, options, ::fn))
        }
```

Imports must stay at the top of the file: collect them into a set before emitting the body, then write them into the header. Re-run the Task 9 golden test afterwards; if the header changed, regenerate the golden file **and read it again**.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `./gradlew --offline :codegen:test :codegen-kotlin:test`
Expected: PASS — `LoweringInferTest` (4), `KotlinWriterEmitterTest` (6), and every earlier test.

- [ ] **Step 10: Commit**

```bash
git add codegen/ codegen-kotlin/
git commit -m "feat(codegen-kotlin): T1 writer emission with inferred lengths and counts"
```

---

### Task 14: The T1 differential and round-trip

**Files:**
- Modify: `codegen-verify/src/main/kotlin/io/hexplain/verify/GenerateMain.kt` (emit at `Tier.T1`)
- Test: `codegen-verify/src/test/kotlin/io/hexplain/verify/WriterDifferentialTest.kt`

**Interfaces:**
- Consumes: `Metawriter`, generated `write(Map): ByteArray`.
- Produces: no new API.

- [ ] **Step 1: Switch generation to T1**

In `GenerateMain.kt`, change `Tier.T0` to `Tier.T1`.

- [ ] **Step 2: Write the failing test**

Create `codegen-verify/src/test/kotlin/io/hexplain/verify/WriterDifferentialTest.kt`:

```kotlin
package io.hexplain.verify

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.metacodec.Metawriter
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class WriterDifferentialTest {

    @Suppress("UNCHECKED_CAST")
    private fun tree(key: String): Map<String, Any> =
        Metaparser(Fixtures.all.getValue(key).formatIR).parse(Fixtures.all.getValue(key).bytes) as Map<String, Any>

    @Test
    fun `the generated record writer produces the same bytes as the metawriter`() {
        val fixture = Fixtures.all.getValue("record")
        val expected = Metawriter(fixture.formatIR).write(tree("record"))
        assertArrayEquals(expected, gen.verify.DemoRecordCodec.write(tree("record")))
    }

    @Test
    fun `the generated record writer round-trips the original bytes`() {
        val fixture = Fixtures.all.getValue("record")
        assertArrayEquals(fixture.bytes, gen.verify.DemoRecordCodec.write(tree("record")))
    }

    @Test
    fun `parse then write then parse is stable`() {
        val once = gen.verify.DemoRecordCodec.write(tree("record"))
        val reparsed = gen.verify.DemoRecordCodec.read(once)
        assertArrayEquals(once, gen.verify.DemoRecordCodec.write(reparsed))
    }

    @Test
    fun `a length the caller got wrong is corrected by inference, not written through`() {
        val edited = tree("record").toMutableMap()
        edited["payloadLen"] = 99L                       // deliberately inconsistent
        edited["payload"] = byteArrayOf(1, 2, 3, 4)      // four bytes, not 99
        val bytes = gen.verify.DemoRecordCodec.write(edited)
        val reparsed = gen.verify.DemoRecordCodec.read(bytes)
        assertEquals(4L, (reparsed["payloadLen"] as Number).toLong(), "the writer must infer the real length")
    }

    @Test
    fun `the generated pointer writer produces the same bytes as the metawriter`() {
        val fixture = Fixtures.all.getValue("pointer")
        val expected = Metawriter(fixture.formatIR).write(tree("pointer"))
        assertArrayEquals(expected, gen.verify.DemoPointerCodec.write(tree("pointer")))
    }
}
```

- [ ] **Step 3: Run it to verify it fails**

Run: `./gradlew --offline :codegen-verify:test`
Expected: FAIL — byte mismatches, or a compile error in the generated writer.

- [ ] **Step 4: Make it pass**

Work the failures in order. Expected causes, in likelihood order:

1. **`payloadLen` written as 0** — the `Region`/`span` that measures the payload does not record into `inferred`; a `sizeFromField` extent needs its span measured by the *dependent* field's write, not by an enclosing region. Add a `span` around a `ReadBytes` whose extent is `Extent.FromSlot`, recording `inferred[slot]`.
2. **The pointer fixture's `far` value written at the wrong place** — `At` in write mode must seek, write and restore, exactly as the reader does.
3. **A trailing byte difference** — `Region` in write mode must pad to its declared extent, mirroring the reader skipping to the region end.

If the metawriter and the generated writer disagree and **the generated one looks right**, stop and report it rather than changing either. The metaengine is the oracle for this phase; a genuine metawriter bug is a finding for a separate change, not something to fix here.

- [ ] **Step 5: Commit**

```bash
git add codegen-verify/
git commit -m "test(codegen-verify): T1 differential — generated writers agree with the metawriter"
```

---

### Task 15: Codecs, and the first real format

The capstone: a codec registry in the runtime, `Decode`/`Encode` emission, and PNG compared against the metaengine end to end.

**Files:**
- Create: `runtime-kotlin/src/main/kotlin/io/hexplain/rt/Codecs.kt`
- Modify: `codegen-kotlin/.../KotlinBackend.kt` and `KotlinWriterEmitter.kt` (emit `Decode`/`Encode`; add `Capability` entries)
- Modify: `codegen-verify/src/main/kotlin/io/hexplain/verify/Fixtures.kt` (add PNG from the profile)
- Test: `runtime-kotlin/src/test/kotlin/io/hexplain/rt/CodecsTest.kt`
- Test: `codegen-verify/src/test/kotlin/io/hexplain/verify/PngDifferentialTest.kt`

**Interfaces:**
- Produces: `RtCodec { fun decode(ByteArray): ByteArray; fun encode(ByteArray): ByteArray }`; `RtCodecs.get(id): RtCodec?`; `RtCodecs.decode(bytes, ids)`; `RtCodecs.encode(bytes, ids)`.

- [ ] **Step 1: Write the failing runtime test**

Create `runtime-kotlin/src/test/kotlin/io/hexplain/rt/CodecsTest.kt`:

```kotlin
package io.hexplain.rt

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class CodecsTest {

    @Test
    fun `zlib round-trips`() {
        val original = "hexplain".repeat(20).toByteArray()
        val encoded = RtCodecs.encode(original, listOf("zlib"))
        assertArrayEquals(original, RtCodecs.decode(encoded, listOf("zlib")))
    }

    @Test
    fun `a codec chain decodes in reverse order`() {
        val original = byteArrayOf(1, 2, 3, 4, 5)
        val encoded = RtCodecs.encode(original, listOf("zlib", "store"))
        assertArrayEquals(original, RtCodecs.decode(encoded, listOf("zlib", "store")))
    }

    @Test
    fun `an unknown codec id fails by name`() {
        val ex = assertThrows<CodecFailure> { RtCodecs.decode(byteArrayOf(1), listOf("nope")) }
        assertTrue(ex.message!!.contains("nope"), ex.message)
    }

    @Test
    fun `a full IRI resolves to the same codec as its short name`() {
        assertSame(RtCodecs.get("zlib"), RtCodecs.get("https://hexplain.io/register/media-encoding#Zlib"))
    }
}
```

- [ ] **Step 2: Write `Codecs.kt`**

```kotlin
package io.hexplain.rt

import java.io.ByteArrayOutputStream
import java.util.zip.Deflater
import java.util.zip.Inflater

/** A named algorithm. The descriptor names it; the runtime supplies it. */
interface RtCodec {
    fun decode(input: ByteArray): ByteArray
    fun encode(input: ByteArray): ByteArray
}

private object StoreCodec : RtCodec {
    override fun decode(input: ByteArray) = input
    override fun encode(input: ByteArray) = input
}

private class ZlibCodec(private val raw: Boolean) : RtCodec {
    override fun decode(input: ByteArray): ByteArray {
        val inflater = Inflater(raw)
        inflater.setInput(input)
        val out = ByteArrayOutputStream(input.size * 4)
        val buffer = ByteArray(8192)
        try {
            while (!inflater.finished()) {
                val n = inflater.inflate(buffer)
                if (n == 0 && (inflater.needsInput() || inflater.needsDictionary())) {
                    throw CodecFailure("truncated deflate stream")
                }
                out.write(buffer, 0, n)
            }
        } finally {
            inflater.end()
        }
        return out.toByteArray()
    }

    override fun encode(input: ByteArray): ByteArray {
        val deflater = Deflater(Deflater.DEFAULT_COMPRESSION, raw)
        deflater.setInput(input)
        deflater.finish()
        val out = ByteArrayOutputStream(input.size)
        val buffer = ByteArray(8192)
        try {
            while (!deflater.finished()) out.write(buffer, 0, deflater.deflate(buffer))
        } finally {
            deflater.end()
        }
        return out.toByteArray()
    }
}

/**
 * The codec registry a generated codec links against. Ids are the register's short names plus the
 * full IRIs, so a descriptor may name either. Adding an algorithm here is the only way a generated
 * codec gains one — the emitted source never contains an algorithm.
 */
object RtCodecs {

    private const val REGISTER = "https://hexplain.io/register/media-encoding#"

    private val byId: Map<String, RtCodec> = buildMap {
        fun register(shortName: String, iriLocal: String, codec: RtCodec) {
            put(shortName, codec)
            put(REGISTER + iriLocal, codec)
        }
        register("store", "Store", StoreCodec)
        register("zlib", "Zlib", ZlibCodec(raw = false))
        register("deflate", "Deflate", ZlibCodec(raw = true))
    }

    fun get(id: String): RtCodec? = byId[id]

    private fun require(id: String): RtCodec = get(id) ?: throw CodecFailure("unknown codec '$id'")

    /** Decodes by applying [ids] in reverse: the first encoding applied when writing is decoded last. */
    fun decode(input: ByteArray, ids: List<String>): ByteArray =
        ids.asReversed().fold(input) { acc, id -> require(id).decode(acc) }

    fun encode(input: ByteArray, ids: List<String>): ByteArray =
        ids.fold(input) { acc, id -> require(id).encode(acc) }
}
```

- [ ] **Step 3: Run the runtime test**

Run: `./gradlew --offline :runtime-kotlin:test --tests '*CodecsTest*'`
Expected: PASS — 4 tests.

- [ ] **Step 4: Emit `Decode` and `Encode`**

In `KotlinBackend.emitStep`, replace the `is Decode -> Unit` arm with:

```kotlin
            is Decode ->
                out.append("${pad}out[\"${step.slot}\"] = RtCodecs.decode(asBytes(out[\"${step.slot}\"]), listOf(${step.codecIds.joinToString(", ") { quote(it) }}))\n")
```

In `KotlinWriterEmitter`, encode before writing the field's bytes: emit the `w.bytes(...)` for an encoded slot as

```kotlin
            "w.bytes(RtCodecs.encode(asBytes(${source(step.slot)}), listOf(${ids.joinToString(", ") { quote(it) }})))"
```

Add `import io.hexplain.rt.RtCodecs` to the emitted header when any `Decode` or `Encode` step is present. Add a `CODECS` value to `Capability`, have `Lowering` add it whenever `field.encodedWith` is non-empty, and add it to `KotlinBackend.capabilities`.

- [ ] **Step 5: Add PNG to the fixtures**

In `Fixtures.kt`, add a fixture built from the real profile rather than from a literal:

```kotlin
    private fun fromProfile(className: String, profile: java.io.File, root: String, data: java.io.File): Fixture {
        val model = io.hexplain.core.rdf.ProfileLoader().load(profile.inputStream())
        return Fixture(className, io.hexplain.core.rdf.RdfToIrCompiler(model).compile(root), data.readBytes())
    }

    private val png: Fixture = fromProfile(
        className = "PngCodec",
        profile = java.io.File("../core/src/test/resources/png-profile.ttl"),
        root = "https://hexplain.io/formats/png#File",
        data = java.io.File("../core/src/test/resources/sample1.png"),
    )
```

Add `"png" to png` to `Fixtures.all`.

- [ ] **Step 6: Write the PNG differential test**

Create `codegen-verify/src/test/kotlin/io/hexplain/verify/PngDifferentialTest.kt`:

```kotlin
package io.hexplain.verify

import io.hexplain.core.metacodec.Metaparser
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

/** The claim the phase exists to support: a real format, read by generated code, agreeing exactly. */
class PngDifferentialTest {

    private fun normalise(value: Any?): Any? = when (value) {
        is Map<*, *> -> value.entries
            .filterNot { (it.key as String).startsWith("__") }
            .associate { (it.key as String) to normalise(it.value) }
        is List<*> -> value.map { normalise(it) }
        is ByteArray -> value.toList()
        is Number -> value.toLong()
        else -> value
    }

    @Test
    fun `the generated PNG reader agrees with the metaparser on sample1`() {
        val fixture = Fixtures.all.getValue("png")
        val expected = Metaparser(fixture.formatIR).parse(fixture.bytes)
        assertEquals(normalise(expected), normalise(gen.verify.PngCodec.read(fixture.bytes)))
    }

    @Test
    fun `the generated PNG reader recovers the declared image dimensions`() {
        val fixture = Fixtures.all.getValue("png")
        val tree = gen.verify.PngCodec.read(fixture.bytes)
        val expected = Metaparser(fixture.formatIR).parse(fixture.bytes)
        assertEquals(normalise(expected), normalise(tree), "trees differ; compare field by field")
    }
}
```

- [ ] **Step 7: Run it, and treat a refusal as information**

Run: `./gradlew --offline :codegen-verify:test`

Three outcomes, all legitimate:

- **PASS** — phase 1 is done and the claim holds on a real format.
- **`LoweringException`** — PNG uses a construct lowering does not handle. Add it, with a test in `codegen`'s lowering suite first.
- **Unmet capability** — PNG needs something the Kotlin backend does not supply at T1 (a checksum verify, a data layout). **Do not stub it.** Record the missing capability in the commit message, mark the PNG test `@Disabled` with that reason in the annotation, and leave it for phase 2. A disabled test naming a real gap is worth more than a passing test that skipped it.

- [ ] **Step 8: Run the whole suite**

Run: `./gradlew --offline :core:test :codegen:test :codegen-kotlin:test :runtime-kotlin:test :codegen-verify:test`
Expected: PASS. `:core:test` must be unchanged from before this plan — if it is not, something modified the metaengine and needs reverting.

- [ ] **Step 9: Commit**

```bash
git add runtime-kotlin/ codegen/ codegen-kotlin/ codegen-verify/
git commit -m "feat(codegen): codec registry, Decode/Encode emission, and the PNG differential"
```

---

## Self-review

**Spec coverage.** §1 architecture → tasks 1–9. §2.1 structured plan → task 1. §2.2 step families → tasks 1–6. §2.3 lowering decides → tasks 3–6, with the extent collapse as task 3. §2.4 shared plan and runtime-side fixpoint → tasks 12–14. §3 HEL transpiled, builtins capability-gated → tasks 6 and 8. §4 runtime library → tasks 7, 12, 15. §5 in-process SPI → task 9; **out-of-process JSON protocol is not in phase 1** — it belongs with the second backend, where it can be tested against a non-Kotlin consumer, and is deliberately deferred. §6 tiers and refusal → tasks 9, 10, 13. §7 equivalence → tasks 11, 14, 15; **negative and fuzz fixtures are not in phase 1** — the spec ties them to the C backend, and they are listed below as carried forward. §8 module layout → task 1, with the flat-directory deviation recorded above. §9 sequencing → this plan is step 1 of that sequence.

**Carried to phase 2:** the out-of-process backend protocol, `hxc explain`'s per-construct attribution, T2 semantic emission, T3 conformance, negative/fuzz corpora, and typed data classes in place of `Map<String, Any>`.

**Known sharp edges an executor will hit.** Task 8 step 5 exists because `TokenType`'s constant names are read from `core` rather than assumed. Task 9's `emitStep` has one `ExpectFixed` line with awkward indentation handling that should be simplified when written. Task 13 step 6 contains a deliberately broken `Branch` arm, fixed in step 7 — it is visible rather than hidden so it cannot be skipped. Task 11's pointer fixture will likely expose that `Lowering.offsetExpr` resolves `atOffsetFromField` in the wrong scope when the naming field sits in a nested struct; fixing the lowering is the intended outcome.

---

## Execution

Plan complete and saved to `docs/superpowers/plans/2026-09-06-codec-generation-phase-1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — a fresh subagent per task, with review between tasks and fast iteration.

**2. Inline Execution** — tasks executed in this session with checkpoints for review.

Which approach?
