# SPARQL Function Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Jena ARQ function library (`hxf:` namespace) that lets a SPARQL query over a Hexplain instance graph reach bytes, parsed values, array cells and aspect-level coordinates (raster, spatial reference, geometry, signal) of the described file, written once against BDDO/DLV/core/aspect vocabularies so every profile gets it for free.

**Architecture:** A new Gradle module `query` in `hexplain-tools` holds one shared `HexplainQueryRuntime` (asset resolution, profile registry, parse-tree cache, node-IRI walking) and thin function classes layered on it: bytes, values, DLV arrays, aspect coordinates. Pure functions (arithmetic over graph values) are declared as SHACL-AF `sh:SPARQLFunction` bodies in `fn.ttl` and also implemented natively; a test proves both agree. The core lifter gains one small extension so array fields become addressable graph nodes.

**Tech Stack:** Kotlin 2.2.10, Apache Jena 5.5.0 (ARQ `FunctionBase`, `PropertyFunctionEval`), JUnit 5, Gradle 8.7 wrapper, existing `io.hexplain.core` engine (Metaparser, SemanticLifter, MultiDimensionalData, CodecRegistry, HelEvaluator, GeometryDecoder).

**Spec:** `d:/work/hexplain.io/docs/superpowers/specs/2026-09-08-sparql-function-library-design.md`

## Global Constraints

- Two repos: engine work in `d:/work/hexplain-tools` (Gradle, Kotlin), spec work in `d:/work/hexplain.io`. Every task states which repo it commits to.
- Both working trees already contain unrelated uncommitted changes. Never `git add -A` or `git add .`; add only the files the task names.
- Namespace for every function: `https://hexplain.io/ns/fn#`, prefix `hxf:`.
- Failure contract: a function that cannot produce a value raises `ExprEvalException` (unbound / FILTER false), never a query error. Every such failure is recorded in the runtime so `hxf:explain` can report it.
- Limits: `maxBytesPerCall` default 1 MiB; `maxCellsPerWindow` default 1,000,000; parse limits are the core `ParseLimits` defaults.
- Indices are zero-based in the layout's declared dimension order (slowest-varying first). Raster `x` is the column, `y` the row; a band is a `RasterBand` IRI or a one-based `araster:bandIndex`. A signal channel is one-based too.
- Result typing: integer cells → `xsd:integer`, float cells → `xsd:double`, string cells → `xsd:string`, byte cells and byte ranges → `xsd:hexBinary`, geometry → `geo:wktLiteral` (`http://www.opengis.net/ont/geosparql#wktLiteral`).
- Read only. No function writes bytes.
- Gradle on this machine: run from `d:/work/hexplain-tools` with `./gradlew.bat`. Add `--offline` while only cached dependencies are used (everything except Task 15). Commit messages follow the repo's `type(scope): summary` style and end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Verified engine facts the plan relies on: the lifter mints `<baseUri>#root/...` IRIs and emits `hexplain:byteOffset`/`hexplain:byteLength` per struct; `Metaparser(recordByteRange = true)` stores `__byteOffset`, `__byteLength` and `__fieldRanges` (`name -> [start, end]`) per struct map and `recordStructName = true` stores `__struct`; a field with `hasDataLayout` parses to a `MultiDimensionalData`; `MultiDimensionalData.from` refuses chunked, packed and stride-from-field layouts with a message naming the DLV term; HEL is parsed with `HelParser(Lexer(text).tokenize()).parse()` and run with `HelEvaluator(context, parentContext, rootContext, selfContext = ...).evaluate(ast)`; the compiler is `RdfToIrCompiler(model).compile(rootStructUri)`; a struct-typed field is `DataTypeIR(structUri, BaseType.BYTES, 0)`.
- GDAL parity oracle: `tests/gdal/results/hexplain.jsonl` records `pixels_sha256 = b55a841b7b95be907f6bb0d358b8d10c9dce6e485381eb9accb71e653597d9a1` for both `autotest/gcore/data/byte.tif` and `autotest/gcore/data/gtiff/byte_envi.bin` (a 400-byte raw 20×20 uint8 export of the same image). The files live under `tests/gdal/cache/upstream/`.

## File Structure

`hexplain-tools` (new module `query`, package `io.hexplain.query`):

| File | Responsibility |
|---|---|
| `query/build.gradle.kts`, `settings.gradle.kts`, `build.gradle.kts` | module wiring |
| `query/src/main/kotlin/io/hexplain/query/HXF.kt` | function IRIs |
| `.../runtime/ByteSource.kt` | `ByteSource`, in-memory and file implementations |
| `.../runtime/AssetResolver.kt` | `AssetResolver`, registry, file-system (allow-listed), composite |
| `.../runtime/QueryLimits.kt` | caps |
| `.../runtime/HexplainQueryException.kt` | the one exception type functions translate to unbound |
| `.../runtime/NodeRef.kt` | node IRI ↔ (asset, path) |
| `.../runtime/ResolvedNode.kt` | what a path resolves to |
| `.../runtime/HexplainQueryRuntime.kt` | profiles, parse cache, path walking, failure log, explain |
| `.../runtime/ArrayAccess.kt` | rank/extent/cell/window/stat over `MultiDimensionalData` |
| `.../fn/HexplainFunction.kt` | ARQ base class, argument coercion, failure translation |
| `.../fn/Values.kt` | Kotlin value ↔ `NodeValue` |
| `.../fn/GraphView.kt` | small read helpers over the active graph |
| `.../fn/ByteFunctions.kt` | `bytes`, `decodedBytes`, `digest` |
| `.../fn/ValueFunctions.kt` | `value`, `hel`, `decode` (+ `BddoTypes`, `ScalarDecoder`) |
| `.../fn/ArrayFunctions.kt` | `rank`, `extent`, `cell`, `layout`, `stat` |
| `.../fn/WindowPropertyFunction.kt` | `hxf:window` |
| `.../fn/RasterFunctions.kt` | `RasterResolver`, `sampleAt`, `calibrate`, `isNoData`, `physicalAt` |
| `.../fn/SpatialRefFunctions.kt` | `Affine`, `worldX`, `worldY`, `column`, `row`, `sampleAtWorld` |
| `.../fn/GeometryFunctions.kt` | `WktWriter`, `wkt` |
| `.../fn/SignalFunctions.kt` | `sampleAtTime` |
| `.../fn/DiagnosticFunctions.kt` | `explain` |
| `.../HexplainFunctions.kt` | registration |
| `.../cli/Main.kt` | `hxq` |
| `query/src/main/resources/hxf/fn.ttl` | function declarations, pure bodies |
| `query/src/test/kotlin/io/hexplain/query/Fixtures.kt`, `Sparql.kt` | synthetic assets and query helper |
| `query/src/test/resources/envi-byte-profile.ttl` | raw-grid profile for GDAL parity |
| `query-fuseki/...` | Fuseki module |
| `core/.../semantic/SemanticLifter.kt` | array-field node emission (small extension) |
| `core/.../rdf/vocab/aspect/Raster.kt`, `SpatialRef.kt` | missing vocabulary terms |

`hexplain.io`: `specification/fn/fn.ttl`, `specification/fn/index.html`, `specification/index.html` (listing), spec doc status update.

---

### Task 1: Module scaffold and function IRIs

**Files:**
- Create: `query/build.gradle.kts`
- Create: `query/src/main/kotlin/io/hexplain/query/HXF.kt`
- Create: `query/src/test/kotlin/io/hexplain/query/HXFTest.kt`
- Modify: `settings.gradle.kts` (add `include("query")`)
- Modify: `build.gradle.kts` (add `"query"` to `publishableModules`)

**Interfaces:**
- Produces: `object HXF { const val NAMESPACE; fun iri(local: String): String; val bytes, decodedBytes, digest, value, hel, decode, rank, extent, cell, stat, window, layout, sampleAt, calibrate, isNoData, physicalAt, worldX, worldY, column, row, sampleAtWorld, wkt, sampleAtTime, explain: String }`

- [ ] **Step 1: Write the failing test**

`query/src/test/kotlin/io/hexplain/query/HXFTest.kt`:
```kotlin
package io.hexplain.query

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class HXFTest {
    @Test
    fun `function IRIs live in the fn namespace`() {
        assertEquals("https://hexplain.io/ns/fn#", HXF.NAMESPACE)
        assertEquals("https://hexplain.io/ns/fn#sampleAt", HXF.sampleAt)
        assertEquals("https://hexplain.io/ns/fn#window", HXF.window)
    }
}
```

- [ ] **Step 2: Wire the module**

`query/build.gradle.kts`:
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
    implementation(libs.slf4j.api)
    testImplementation(libs.junit.jupiter)
}

application { mainClass.set("io.hexplain.query.cli.MainKt") }

tasks.test {
    useJUnitPlatform()
    binaryResultsDirectory.set(layout.buildDirectory.dir("test-results-binary"))
}
```

`settings.gradle.kts`: add `include("query")` after `include("codegen-verify")`.

`build.gradle.kts`: change `val publishableModules = setOf("core", "hdl", "adapters", "runtime-kotlin", "codegen", "codegen-kotlin")` to include `"query"`.

- [ ] **Step 3: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q`
Expected: compilation error, `HXF` unresolved.

- [ ] **Step 4: Write the IRIs**

`query/src/main/kotlin/io/hexplain/query/HXF.kt`:
```kotlin
package io.hexplain.query

/** IRIs of the Hexplain SPARQL function library. Mirrors specification/fn/fn.ttl. */
object HXF {
    const val NAMESPACE = "https://hexplain.io/ns/fn#"
    fun iri(local: String): String = NAMESPACE + local

    // Layer 0: assets and bytes
    val bytes = iri("bytes")
    val decodedBytes = iri("decodedBytes")
    val digest = iri("digest")

    // Layer 1: parsed values
    val value = iri("value")
    val hel = iri("hel")
    val decode = iri("decode")

    // Layer 2: arrays
    val rank = iri("rank")
    val extent = iri("extent")
    val cell = iri("cell")
    val stat = iri("stat")
    val window = iri("window")
    val layout = iri("layout")

    // Layer 3: aspect coordinates
    val sampleAt = iri("sampleAt")
    val calibrate = iri("calibrate")
    val isNoData = iri("isNoData")
    val physicalAt = iri("physicalAt")
    val worldX = iri("worldX")
    val worldY = iri("worldY")
    val column = iri("column")
    val row = iri("row")
    val sampleAtWorld = iri("sampleAtWorld")
    val wkt = iri("wkt")
    val sampleAtTime = iri("sampleAtTime")

    // Diagnostics
    val explain = iri("explain")
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 6: Commit (hexplain-tools)**

```bash
git add settings.gradle.kts build.gradle.kts query/build.gradle.kts query/src/main/kotlin/io/hexplain/query/HXF.kt query/src/test/kotlin/io/hexplain/query/HXFTest.kt
git commit -m "feat(query): scaffold the SPARQL function module and its hxf: IRIs"
```

---

### Task 2: Core vocabulary terms and array-field nodes in the lifter

**Files:**
- Modify: `core/src/main/kotlin/io/hexplain/core/rdf/vocab/aspect/Raster.kt`
- Modify: `core/src/main/kotlin/io/hexplain/core/rdf/vocab/aspect/SpatialRef.kt`
- Modify: `core/src/main/kotlin/io/hexplain/core/semantic/SemanticLifter.kt` (the `else` branch of `processField`, currently starting at the `// G9:` comment)
- Test: `core/src/test/kotlin/io/hexplain/core/semantic/SemanticLifterTest.kt`

**Interfaces:**
- Produces: `Raster.RasterGrid, RasterBand, SampleArray: Resource`; `Raster.hasBand, bandCount, bandIndex, hasArray, sampleScale, sampleOffset: Property`; `SpatialRef.originX, originY, skewX, skewY, hasGeoTransform, hasCRS: Property`.
- Produces: for a field whose parsed value is a `MultiDimensionalData` and that declares `mapsToObjectProperty`, the lifter emits `<struct> <prop> <struct-iri>/<FieldName>` and, when byte ranges are on, `hexplain:byteOffset` / `hexplain:byteLength` on that node from `__fieldRanges`.

- [ ] **Step 1: Write the failing test**

Append to `SemanticLifterTest`:
```kotlin
    @Test
    fun `array field with mapsToObjectProperty emits an array node with its byte range`() {
        val u8 = DataTypeIR("https://hexplain.io/ns/bddo#uint8", BaseType.INTEGER, 8, isSigned = false)
        val layout = DataLayoutIR(
            listOf(DimensionIR("https://hexplain.io/ns/dlv#axisY", size = 2), DimensionIR("https://hexplain.io/ns/dlv#axisX", size = 3)),
            u8
        )
        val raster = io.hexplain.core.rdf.vocab.aspect.Raster
        val struct = StructIR(
            name = "https://example.org/Grid",
            fields = listOf(
                FieldIR("Width", u8, mapsToProperty = raster.width.uri),
                FieldIR(
                    "Samples", DataTypeIR("https://hexplain.io/ns/bddo#bytes", BaseType.BYTES, 0),
                    sizeToEndOfStream = true, hasDataLayout = layout, mapsToObjectProperty = raster.hasArray.uri
                )
            ),
            mapsToClass = raster.RasterGrid.uri
        )
        val fmt = FormatIR("F", struct.name, mapOf(struct.name to struct))
        val parsed = Metaparser(fmt, recordByteRange = true).parse(byteArrayOf(3, 1, 2, 3, 4, 5, 6))
        val model = SemanticLifter(fmt, "https://example.org/a").extract(parsed)
        val root = model.getResource("https://example.org/a#root")
        val array = model.getResource("https://example.org/a#root/Samples")
        assertTrue(model.contains(root, raster.hasArray, array))
        assertEquals(1, array.getProperty(io.hexplain.core.rdf.vocab.HEXPLAIN.byteOffset).int)
        assertEquals(6, array.getProperty(io.hexplain.core.rdf.vocab.HEXPLAIN.byteLength).int)
    }

    @Test
    fun `array field without an object property is still dropped`() {
        val u8 = DataTypeIR("https://hexplain.io/ns/bddo#uint8", BaseType.INTEGER, 8, isSigned = false)
        val layout = DataLayoutIR(listOf(DimensionIR("https://hexplain.io/ns/dlv#axisX", size = 3)), u8)
        val struct = StructIR(
            name = "https://example.org/Grid",
            fields = listOf(FieldIR("Samples", DataTypeIR("https://hexplain.io/ns/bddo#bytes", BaseType.BYTES, 0), sizeToEndOfStream = true, hasDataLayout = layout)),
            mapsToClass = "https://example.org/C"
        )
        val fmt = FormatIR("F", struct.name, mapOf(struct.name to struct))
        val model = SemanticLifter(fmt, "https://example.org/a").extract(Metaparser(fmt, recordByteRange = true).parse(byteArrayOf(1, 2, 3)))
        assertFalse(model.containsResource(model.getResource("https://example.org/a#root/Samples")))
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :core:test --offline -q --tests "io.hexplain.core.semantic.SemanticLifterTest"`
Expected: compilation error (`Raster.hasArray`, `Raster.RasterGrid` unresolved).

- [ ] **Step 3: Add the vocabulary terms**

`Raster.kt`, inside `object Raster` after the existing properties:
```kotlin
    // --- Classes ---
    val RasterGrid: Resource = m_resource("RasterGrid")
    val RasterBand: Resource = m_resource("RasterBand")
    val SampleArray: Resource = m_resource("SampleArray")

    // --- Band and array structure ---
    val hasBand: Property = m_property("hasBand")
    val bandCount: Property = m_property("bandCount")
    val bandIndex: Property = m_property("bandIndex")
    val hasArray: Property = m_property("hasArray")
    val sampleScale: Property = m_property("sampleScale")
    val sampleOffset: Property = m_property("sampleOffset")
```

`SpatialRef.kt`, after `pixelRegistration`:
```kotlin
    val originX: Property = m_property("originX")
    val originY: Property = m_property("originY")
    val skewX: Property = m_property("skewX")
    val skewY: Property = m_property("skewY")
    val hasGeoTransform: Property = m_property("hasGeoTransform")
    val hasCRS: Property = m_property("hasCRS")
```

- [ ] **Step 4: Emit the array node in the lifter**

In `SemanticLifter.processField`, at the very top of the `else ->` branch (before the `// G9:` comment), insert:
```kotlin
                // A DLV array is never a literal (Processing Model §7 keeps cell data out of the
                // graph), but it is addressable: when the profile names an object property for it,
                // emit the node so a query can reach the cells through hxf:cell / hxf:sampleAt.
                if (fieldValue is io.hexplain.core.metacodec.MultiDimensionalData) {
                    val prop = field.mapsToObjectProperty ?: return
                    val arrayNode = model.createResource(instanceUri("$path/${field.name}"))
                    model.add(currentSubject, ResourceFactory.createProperty(prop), arrayNode)
                    if (options.includeByteRange) {
                        val ranges = currentMap[Metaparser.FIELD_RANGES_KEY] as? Map<*, *>
                        val range = ranges?.get(field.name) as? List<*>
                        val start = (range?.getOrNull(0) as? Number)?.toLong()
                        val end = (range?.getOrNull(1) as? Number)?.toLong()
                        if (start != null && end != null) {
                            model.add(arrayNode, HEXPLAIN.byteOffset, ResourceFactory.createTypedLiteral(start.toString(), XSDDatatype.XSDinteger))
                            model.add(arrayNode, HEXPLAIN.byteLength, ResourceFactory.createTypedLiteral((end - start).toString(), XSDDatatype.XSDinteger))
                        }
                    }
                    return
                }
```

- [ ] **Step 5: Run the lifter tests**

Run: `./gradlew.bat :core:test --offline -q --tests "io.hexplain.core.semantic.*"`
Expected: PASS, including the two new tests.

- [ ] **Step 6: Commit (hexplain-tools)**

```bash
git add core/src/main/kotlin/io/hexplain/core/rdf/vocab/aspect/Raster.kt core/src/main/kotlin/io/hexplain/core/rdf/vocab/aspect/SpatialRef.kt core/src/main/kotlin/io/hexplain/core/semantic/SemanticLifter.kt core/src/test/kotlin/io/hexplain/core/semantic/SemanticLifterTest.kt
git commit -m "feat(core): lift DLV array fields as addressable nodes; add raster and spatialref vocab terms"
```

---
### Task 3: Query runtime — asset resolution, parse cache, node walking, fixtures

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/ByteSource.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/AssetResolver.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/QueryLimits.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/HexplainQueryException.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/NodeRef.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/ResolvedNode.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/HexplainQueryRuntime.kt`
- Create: `query/src/test/kotlin/io/hexplain/query/Fixtures.kt`
- Create: `query/src/test/kotlin/io/hexplain/query/Sparql.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/runtime/HexplainQueryRuntimeTest.kt`

**Interfaces:**
- Produces: `interface ByteSource { val length: Long; fun readAll(): ByteArray }`, `InMemoryByteSource(ByteArray)`, `FileByteSource(Path)`.
- Produces: `interface AssetResolver { fun open(assetIri: String): ByteSource? }`, `RegistryAssetResolver().register(iri, bytes|path|source)`, `FileSystemAssetResolver(roots: List<Path>)`, `CompositeAssetResolver(List<AssetResolver>)`.
- Produces: `data class QueryLimits(maxBytesPerCall: Int = 1 shl 20, maxCellsPerWindow: Long = 1_000_000, cacheBudgetBytes: Long = 256L shl 20, parseLimits: ParseLimits = ParseLimits())`.
- Produces: `class HexplainQueryException(message, cause = null) : RuntimeException`.
- Produces: `data class NodeRef(assetIri, path) { val segments; companion parse(nodeIri) }`, `data class ByteRange(start: Long, length: Long) { val end }`.
- Produces: `class ResolvedNode(ref, formatIR, assetBytes, value, struct, parent, root, structIR, field, byteRange) { val isStruct; fun rawBytes(): ByteArray }`.
- Produces: `class HexplainQueryRuntime(resolver, limits = QueryLimits(), codecRegistry = CodecRegistry.defaultRegistry()) { fun registerProfile(iri, FormatIR); fun registerProfile(iri, Model, rootStructUri); fun bindAsset(assetIri, profileIri); fun resolve(nodeIri, graph: Graph?): ResolvedNode; fun explain(nodeIri, graph: Graph?): String; fun recordFailure(nodeIri, message); fun lastFailure(nodeIri): String?; val codecs: CodecRegistry }`.
- Produces (test): `class Fixture(assetIri, profileIri, formatIR, bytes) { parsed, model, runtime, fun node(path) }`, `Fixtures.grid() / interleaved() / planar() / pcm() / zipped()`, `Sparql.select(model, query): List<QuerySolution>` with the standard prefixes prepended.

- [ ] **Step 1: Write the test fixtures**

`query/src/test/kotlin/io/hexplain/query/Fixtures.kt`:
```kotlin
package io.hexplain.query

import io.hexplain.core.ir.*
import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.vocab.aspect.Raster
import io.hexplain.core.rdf.vocab.aspect.Signal
import io.hexplain.core.semantic.SemanticLifter
import io.hexplain.query.runtime.HexplainQueryRuntime
import io.hexplain.query.runtime.QueryLimits
import io.hexplain.query.runtime.RegistryAssetResolver
import org.apache.jena.rdf.model.Model
import java.nio.ByteBuffer
import java.nio.ByteOrder

/** One synthetic asset: its IR, its bytes, the graph the lifter makes of it, and a runtime that can open it. */
class Fixture(val assetIri: String, val profileIri: String, val formatIR: FormatIR, val bytes: ByteArray, limits: QueryLimits = QueryLimits()) {
    val parsed: Any = Metaparser(formatIR, recordByteRange = true, recordStructName = true).parse(bytes)
    val model: Model = SemanticLifter(formatIR, assetIri).extract(parsed)
    val runtime: HexplainQueryRuntime = HexplainQueryRuntime(RegistryAssetResolver().register(assetIri, bytes), limits)
        .registerProfile(profileIri, formatIR)
        .bindAsset(assetIri, profileIri)
    fun node(path: String): String = "$assetIri#$path"
    /** The same asset with different caps. */
    fun withLimits(limits: QueryLimits) = Fixture(assetIri, profileIri, formatIR, bytes, limits)
}

object Fixtures {
    const val BDDO = "https://hexplain.io/ns/bddo#"
    const val DLV = "https://hexplain.io/ns/dlv#"
    const val XSD = "http://www.w3.org/2001/XMLSchema#"
    val u8 = DataTypeIR(BDDO + "uint8", BaseType.INTEGER, 8, isSigned = false, xsdType = XSD + "unsignedByte")
    val u16be = DataTypeIR(BDDO + "uint16be", BaseType.INTEGER, 16, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)
    val i16be = DataTypeIR(BDDO + "int16be", BaseType.INTEGER, 16, isSigned = true, hasEndianness = Endianness.BIG_ENDIAN)
    val i16le = DataTypeIR(BDDO + "int16le", BaseType.INTEGER, 16, isSigned = true, hasEndianness = Endianness.LITTLE_ENDIAN)
    val f32le = DataTypeIR(BDDO + "float32le", BaseType.FLOAT, 32, hasEndianness = Endianness.LITTLE_ENDIAN)
    val bytes = DataTypeIR(BDDO + "bytes", BaseType.BYTES, 0, xsdType = XSD + "hexBinary")
    fun dim(axis: String, size: Long? = null, sizeFromField: String? = null) = DimensionIR(DLV + axis, size = size, sizeFromField = sizeFromField)
    private fun format(name: String, vararg structs: StructIR) = FormatIR(name, structs.first().name, structs.associateBy { it.name })

    /** 3 wide x 2 high single-band uint8 grid: Width, Height, NoData header then six samples; 255 is the no-data value. Cells row-major: 10 20 255 / 40 50 60. */
    fun grid(): Fixture {
        val layout = DataLayoutIR(listOf(dim("axisY", sizeFromField = "Height"), dim("axisX", sizeFromField = "Width")), u8)
        val struct = StructIR(
            name = "https://example.org/fmt/grid#Grid",
            fields = listOf(
                FieldIR("Width", u8, mapsToProperty = Raster.width.uri),
                FieldIR("Height", u8, mapsToProperty = Raster.height.uri),
                FieldIR("NoData", u8, mapsToProperty = Raster.noDataValue.uri),
                FieldIR("Samples", bytes, sizeToEndOfStream = true, hasDataLayout = layout, mapsToObjectProperty = Raster.hasArray.uri)
            ),
            mapsToClass = Raster.RasterGrid.uri
        )
        val data = byteArrayOf(3, 2, -1, 10, 20, -1, 40, 50, 60)
        return Fixture("https://example.org/assets/grid", "https://example.org/fmt/grid", format("grid", struct), data)
    }

    /** 2 x 2 x 2 pixel-interleaved int16 big-endian grid, no header. Cell (y, x, band) = 100*y + 10*x + band + 1. */
    fun interleaved(): Fixture {
        val layout = DataLayoutIR(listOf(dim("axisY", 2), dim("axisX", 2), dim("axisBand", 2)), i16be)
        val struct = StructIR(
            name = "https://example.org/fmt/bip#Grid",
            fields = listOf(FieldIR("Samples", bytes, sizeToEndOfStream = true, hasDataLayout = layout, mapsToObjectProperty = Raster.hasArray.uri)),
            mapsToClass = Raster.RasterGrid.uri
        )
        val buf = ByteBuffer.allocate(16)
        for (y in 0..1) for (x in 0..1) for (b in 0..1) buf.putShort((100 * y + 10 * x + b + 1).toShort())
        return Fixture("https://example.org/assets/bip", "https://example.org/fmt/bip", format("bip", struct), buf.array())
    }

    /** Two planar float32 little-endian 2 x 2 bands; each band struct is its one-based index then 16 sample bytes. Band b cell i = 10*b + 0.5*i. */
    fun planar(): Fixture {
        val layout = DataLayoutIR(listOf(dim("axisY", 2), dim("axisX", 2)), f32le)
        val band = StructIR(
            name = "https://example.org/fmt/planar#Band",
            fields = listOf(
                FieldIR("Index", u8, mapsToProperty = Raster.bandIndex.uri),
                FieldIR("Samples", bytes, size = 16, hasDataLayout = layout, mapsToObjectProperty = Raster.hasArray.uri)
            ),
            mapsToClass = Raster.RasterBand.uri
        )
        val grid = StructIR(
            name = "https://example.org/fmt/planar#Grid",
            fields = listOf(
                FieldIR("Count", u8, mapsToProperty = Raster.bandCount.uri),
                FieldIR("Bands", DataTypeIR(band.name, BaseType.BYTES, 0), repeatCountFromField = "Count", mapsToObjectProperty = Raster.hasBand.uri)
            ),
            mapsToClass = Raster.RasterGrid.uri
        )
        val buf = ByteBuffer.allocate(1 + 2 * 17).order(ByteOrder.LITTLE_ENDIAN)
        buf.put(2)
        for (b in 1..2) { buf.put(b.toByte()); for (i in 0 until 4) buf.putFloat(10f * b + 0.5f * i) }
        return Fixture("https://example.org/assets/planar", "https://example.org/fmt/planar", format("planar", grid, band), buf.array())
    }

    /** Stereo int16 little-endian PCM at 4 Hz: four instants, two channels. Cell (t, c) = 1000*t + c + 1. */
    fun pcm(): Fixture {
        val layout = DataLayoutIR(listOf(dim("axisTime", 4), dim("axisBand", 2)), i16le)
        val struct = StructIR(
            name = "https://example.org/fmt/pcm#Signal",
            fields = listOf(
                FieldIR("Rate", u16be, mapsToProperty = Signal.sampleRate.uri),
                FieldIR("Samples", bytes, sizeToEndOfStream = true, hasDataLayout = layout, mapsToObjectProperty = Raster.hasArray.uri)
            ),
            mapsToClass = "https://example.org/fmt/pcm#Signal"
        )
        val buf = ByteBuffer.allocate(2 + 16)
        buf.putShort(4)
        buf.order(ByteOrder.LITTLE_ENDIAN)
        for (t in 0..3) for (c in 0..1) buf.putShort((1000 * t + c + 1).toShort())
        return Fixture("https://example.org/assets/pcm", "https://example.org/fmt/pcm", format("pcm", struct), buf.array())
    }

    /** One zlib-encoded payload field holding the text "hello". */
    fun zipped(): Fixture {
        val struct = StructIR(
            name = "https://example.org/fmt/zip#File",
            fields = listOf(FieldIR("Payload", bytes, sizeToEndOfStream = true, encodedWith = listOf("zlib"))),
            mapsToClass = "https://example.org/fmt/zip#File"
        )
        val deflater = java.util.zip.Deflater().apply { setInput("hello".toByteArray()); finish() }
        val out = ByteArray(64); val n = deflater.deflate(out); deflater.end()
        return Fixture("https://example.org/assets/zip", "https://example.org/fmt/zip", format("zip", struct), out.copyOf(n))
    }

    /** A single geometry payload (WKB or GeoPackage blob) as the only field. */
    fun geometry(payload: ByteArray): Fixture {
        val struct = StructIR(
            name = "https://example.org/fmt/geom#Feature",
            fields = listOf(FieldIR("Geom", bytes, sizeToEndOfStream = true)),
            mapsToClass = "https://example.org/fmt/geom#Feature"
        )
        return Fixture("https://example.org/assets/geom", "https://example.org/fmt/geom", format("geom", struct), payload)
    }
}
```

`query/src/test/kotlin/io/hexplain/query/Sparql.kt`:
```kotlin
package io.hexplain.query

import org.apache.jena.query.QueryExecution
import org.apache.jena.query.QuerySolution
import org.apache.jena.query.ResultSetFormatter
import org.apache.jena.rdf.model.Model

object Sparql {
    const val PREFIXES = """
        PREFIX hxf: <https://hexplain.io/ns/fn#>
        PREFIX araster: <https://hexplain.io/ns/aspect/raster#>
        PREFIX asref: <https://hexplain.io/ns/aspect/spatialref#>
        PREFIX asig: <https://hexplain.io/ns/aspect/signal#>
        PREFIX dlv: <https://hexplain.io/ns/dlv#>
        PREFIX bddo: <https://hexplain.io/ns/bddo#>
        PREFIX rck: <https://hexplain.io/ns/register/checksum#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX ex: <https://example.org/>
    """

    fun select(model: Model, query: String): List<QuerySolution> =
        QueryExecution.model(model).query(PREFIXES + query).build().use { ResultSetFormatter.toList(it.execSelect()) }

    /** The single value of the single row, or null when the row left it unbound. */
    fun one(model: Model, query: String, variable: String = "v"): org.apache.jena.rdf.model.RDFNode? {
        val rows = select(model, query)
        check(rows.size == 1) { "expected one row, got ${rows.size}" }
        return rows[0].get(variable)
    }
}
```

- [ ] **Step 2: Write the failing runtime test**

`query/src/test/kotlin/io/hexplain/query/runtime/HexplainQueryRuntimeTest.kt`:
```kotlin
package io.hexplain.query.runtime

import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.query.Fixtures
import org.apache.jena.graph.NodeFactory
import org.apache.jena.graph.Triple
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class HexplainQueryRuntimeTest {
    private val g = Fixtures.grid()

    @Test
    fun `resolves the root struct with its byte range`() {
        val n = g.runtime.resolve(g.node("root"), null)
        assertTrue(n.isStruct)
        assertEquals(ByteRange(0, 9), n.byteRange)
        assertEquals(9, n.rawBytes().size)
    }

    @Test
    fun `resolves a scalar field with its owning struct and range`() {
        val n = g.runtime.resolve(g.node("root/Width"), null)
        assertEquals(3, (n.value as Number).toInt())
        assertEquals("Width", n.field!!.name)
        assertEquals(ByteRange(0, 1), n.byteRange)
        assertSame(n.root, n.struct)
        assertNull(n.parent)
    }

    @Test
    fun `resolves an array field to its multi-dimensional data`() {
        val n = g.runtime.resolve(g.node("root/Samples"), null)
        assertTrue(n.value is MultiDimensionalData)
        assertEquals(ByteRange(3, 6), n.byteRange)
        assertEquals("0a14ff28323c", n.rawBytes().joinToString("") { "%02x".format(it) })
    }

    @Test
    fun `resolves list elements and nested structs`() {
        val p = Fixtures.planar()
        val n = p.runtime.resolve(p.node("root/Bands/1"), null)
        assertTrue(n.isStruct)
        assertEquals(2, (n.struct["Index"] as Number).toInt())
        assertNotNull(n.parent)
        assertSame(n.root, n.parent)
        assertEquals("https://example.org/fmt/planar#Band", n.structIR!!.name)
    }

    @Test
    fun `finds the profile through dcterms conformsTo when no binding exists`() {
        val runtime = HexplainQueryRuntime(RegistryAssetResolver().register(g.assetIri, g.bytes)).registerProfile(g.profileIri, g.formatIR)
        val graph = g.model.graph
        graph.add(Triple.create(NodeFactory.createURI(g.assetIri), NodeFactory.createURI("http://purl.org/dc/terms/conformsTo"), NodeFactory.createURI(g.profileIri)))
        assertTrue(runtime.resolve(g.node("root"), graph).isStruct)
        assertThrows(HexplainQueryException::class.java) { runtime.resolve(g.node("root"), null) }
    }

    @Test
    fun `unknown asset, unknown path, bad index and malformed IRIs fail with HexplainQueryException`() {
        assertThrows(HexplainQueryException::class.java) { g.runtime.resolve("https://example.org/nowhere#root", null) }
        assertThrows(HexplainQueryException::class.java) { g.runtime.resolve(g.node("root/Nope"), null) }
        assertThrows(HexplainQueryException::class.java) { g.runtime.resolve(g.node("root/Width/0"), null) }
        assertThrows(HexplainQueryException::class.java) { g.runtime.resolve("https://example.org/no-fragment", null) }
        assertThrows(HexplainQueryException::class.java) { g.runtime.resolve("https://example.org/a#notroot/x", null) }
        val p = Fixtures.planar()
        assertThrows(HexplainQueryException::class.java) { p.runtime.resolve(p.node("root/Bands/7"), null) }
    }

    @Test
    fun `file system resolver only opens files below its roots`() {
        val dir = java.nio.file.Files.createTempDirectory("hxq")
        val inside = dir.resolve("a.bin"); java.nio.file.Files.write(inside, byteArrayOf(1, 2, 3))
        val outside = java.nio.file.Files.createTempFile("hxq", ".bin")
        val resolver = FileSystemAssetResolver(listOf(dir))
        assertEquals(3L, resolver.open(inside.toUri().toString())!!.length)
        assertNull(resolver.open(outside.toUri().toString()))
        assertNull(resolver.open("https://example.org/x"))
    }

    @Test
    fun `explain never throws and names what went wrong`() {
        assertTrue(g.runtime.explain(g.node("root/Samples"), null).contains("kind=array"))
        assertTrue(g.runtime.explain(g.node("root/Nope"), null).contains("error="))
        g.runtime.recordFailure(g.node("root"), "boom")
        assertTrue(g.runtime.explain(g.node("root"), null).contains("lastFailure=boom"))
    }

    @Test
    fun `the parse tree is cached per asset and evicted when over budget`() {
        val a = g.runtime.resolve(g.node("root"), null)
        val b = g.runtime.resolve(g.node("root/Width"), null)
        assertSame(a.root, b.root)
        val tiny = g.withLimits(QueryLimits(cacheBudgetBytes = 1))
        val c = tiny.runtime.resolve(g.node("root"), null)
        val d = tiny.runtime.resolve(g.node("root"), null)
        assertNotSame(c.root, d.root)
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.runtime.HexplainQueryRuntimeTest"`
Expected: compilation errors (runtime package missing).

- [ ] **Step 4: Implement the runtime**

`ByteSource.kt`:
```kotlin
package io.hexplain.query.runtime

import java.nio.file.Files
import java.nio.file.Path

/** The bytes of one asset. Implementations must be safe to call from several query threads. */
interface ByteSource {
    val length: Long
    fun readAll(): ByteArray
}

class InMemoryByteSource(private val bytes: ByteArray) : ByteSource {
    override val length: Long get() = bytes.size.toLong()
    override fun readAll(): ByteArray = bytes.copyOf()
}

class FileByteSource(private val path: Path) : ByteSource {
    override val length: Long get() = Files.size(path)
    override fun readAll(): ByteArray = Files.readAllBytes(path)
}
```

`AssetResolver.kt`:
```kotlin
package io.hexplain.query.runtime

import java.net.URI
import java.nio.file.Files
import java.nio.file.Path
import java.util.concurrent.ConcurrentHashMap

/** Turns an asset IRI into bytes. Returning null means "not mine"; a composite tries the next resolver. */
interface AssetResolver {
    fun open(assetIri: String): ByteSource?
}

/** Explicit IRI -> bytes bindings; the default for tests, the CLI and embedding. */
class RegistryAssetResolver : AssetResolver {
    private val sources = ConcurrentHashMap<String, ByteSource>()
    fun register(assetIri: String, source: ByteSource): RegistryAssetResolver { sources[assetIri] = source; return this }
    fun register(assetIri: String, bytes: ByteArray): RegistryAssetResolver = register(assetIri, InMemoryByteSource(bytes))
    fun register(assetIri: String, path: Path): RegistryAssetResolver = register(assetIri, FileByteSource(path))
    override fun open(assetIri: String): ByteSource? = sources[assetIri]
}

/** Maps file: IRIs to regular files, but only below one of the configured roots. */
class FileSystemAssetResolver(roots: List<Path>) : AssetResolver {
    private val roots = roots.map { it.toAbsolutePath().normalize() }
    override fun open(assetIri: String): ByteSource? {
        if (!assetIri.startsWith("file:")) return null
        val path = try { Path.of(URI(assetIri)).toAbsolutePath().normalize() } catch (e: Exception) { return null }
        if (roots.none { path.startsWith(it) } || !Files.isRegularFile(path)) return null
        return FileByteSource(path)
    }
}

class CompositeAssetResolver(private val resolvers: List<AssetResolver>) : AssetResolver {
    override fun open(assetIri: String): ByteSource? = resolvers.firstNotNullOfOrNull { it.open(assetIri) }
}
```

`QueryLimits.kt`:
```kotlin
package io.hexplain.query.runtime

import io.hexplain.core.metacodec.ParseLimits

/** Hard caps enforced by every function; see the design's §4.4. */
data class QueryLimits(
    val maxBytesPerCall: Int = 1 shl 20,
    val maxCellsPerWindow: Long = 1_000_000,
    val cacheBudgetBytes: Long = 256L shl 20,
    val parseLimits: ParseLimits = ParseLimits()
)
```

`HexplainQueryException.kt`:
```kotlin
package io.hexplain.query.runtime

/** The one failure type a function raises; the ARQ base class turns it into an unbound result. */
class HexplainQueryException(message: String, cause: Throwable? = null) : RuntimeException(message, cause)
```

`NodeRef.kt`:
```kotlin
package io.hexplain.query.runtime

/** A lifted node IRI split into the asset IRI and the lifter path ("root/Chunks/3/ChunkData"). */
data class NodeRef(val assetIri: String, val path: String) {
    val segments: List<String> get() = path.split('/').map { it.replace("%20", " ") }

    companion object {
        fun parse(nodeIri: String): NodeRef {
            val hash = nodeIri.indexOf('#')
            if (hash < 0 || hash == nodeIri.length - 1) throw HexplainQueryException("<$nodeIri> is not a lifted node IRI (expected <asset>#<path>)")
            val path = nodeIri.substring(hash + 1)
            if (path != "root" && !path.startsWith("root/")) throw HexplainQueryException("<$nodeIri>: a lifted path starts with 'root'")
            return NodeRef(nodeIri.substring(0, hash), path)
        }
    }
}

/** An absolute byte extent inside an asset: [start, start + length). */
data class ByteRange(val start: Long, val length: Long) {
    val end: Long get() = start + length
}
```

`ResolvedNode.kt`:
```kotlin
package io.hexplain.query.runtime

import io.hexplain.core.codec.PreservedEncodedBytes
import io.hexplain.core.ir.FieldIR
import io.hexplain.core.ir.FormatIR
import io.hexplain.core.ir.StructIR
import io.hexplain.core.metacodec.MultiDimensionalData

/** What a lifted path points at inside a parsed asset. */
class ResolvedNode(
    val ref: NodeRef,
    val formatIR: FormatIR,
    val assetBytes: ByteArray,
    /** The value at the path: a struct map, a list, a scalar, a ByteArray, PreservedEncodedBytes or MultiDimensionalData. */
    val value: Any?,
    /** The struct map that owns the node: the node itself for a struct, its container for a field or list. */
    val struct: Map<String, Any>,
    val parent: Map<String, Any>?,
    val root: Map<String, Any>,
    val structIR: StructIR?,
    /** Set when the path ends at a field of [struct]. */
    val field: FieldIR?,
    /** Absolute extent in the asset, when the parser recorded one. */
    val byteRange: ByteRange?
) {
    val isStruct: Boolean get() = value is Map<*, *>

    val kind: String get() = when (value) {
        null -> "absent"
        is Map<*, *> -> "struct"
        is List<*> -> "list"
        is MultiDimensionalData -> "array"
        is ByteArray, is PreservedEncodedBytes -> "bytes"
        else -> "scalar"
    }

    /** The node's bytes as they sit in the file (encoded, if the field is encoded). */
    fun rawBytes(): ByteArray {
        byteRange?.let { return assetBytes.copyOfRange(it.start.toInt(), it.end.toInt()) }
        return when (val v = value) {
            is ByteArray -> v
            is PreservedEncodedBytes -> v.raw
            else -> throw HexplainQueryException("${ref.path} has no recorded byte range")
        }
    }
}
```

`HexplainQueryRuntime.kt`:
```kotlin
package io.hexplain.query.runtime

import io.hexplain.core.codec.CodecRegistry
import io.hexplain.core.ir.FormatIR
import io.hexplain.core.ir.StructIR
import io.hexplain.core.metacodec.HexplainParsingException
import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.core.rdf.RdfToIrCompiler
import org.apache.jena.graph.Graph
import org.apache.jena.graph.Node
import org.apache.jena.graph.NodeFactory
import org.apache.jena.rdf.model.Model
import java.util.Collections
import java.util.concurrent.ConcurrentHashMap

/**
 * The shared service every hxf: function is a thin wrapper over: which profile describes an
 * asset, its bytes, its parse tree (cached), and what a lifted path points at.
 */
class HexplainQueryRuntime(
    val resolver: AssetResolver,
    val limits: QueryLimits = QueryLimits(),
    private val codecRegistry: CodecRegistry = CodecRegistry.defaultRegistry()
) {
    private val profiles = ConcurrentHashMap<String, FormatIR>()
    private val assetProfiles = ConcurrentHashMap<String, String>()
    private val cache = ParsedAssetCache(limits.cacheBudgetBytes)
    private val failures: MutableMap<String, String> = Collections.synchronizedMap(
        object : LinkedHashMap<String, String>(64, 0.75f, true) {
            override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, String>?): Boolean = size > 256
        }
    )

    val codecs: CodecRegistry get() = codecRegistry

    fun registerProfile(profileIri: String, formatIR: FormatIR): HexplainQueryRuntime { profiles[profileIri] = formatIR; return this }
    fun registerProfile(profileIri: String, profile: Model, rootStructUri: String): HexplainQueryRuntime =
        registerProfile(profileIri, RdfToIrCompiler(profile).compile(rootStructUri))
    fun bindAsset(assetIri: String, profileIri: String): HexplainQueryRuntime {
        if (!profiles.containsKey(profileIri)) throw HexplainQueryException("profile <$profileIri> is not registered")
        assetProfiles[assetIri] = profileIri
        return this
    }

    fun recordFailure(nodeIri: String, message: String) { failures[nodeIri] = message }
    fun lastFailure(nodeIri: String): String? = failures[nodeIri]

    fun resolve(nodeIri: String, graph: Graph?): ResolvedNode {
        val ref = NodeRef.parse(nodeIri)
        return walk(ref, parsedAsset(ref.assetIri, graph))
    }

    /** Never throws: a description of how [nodeIri] resolves, or why it does not. */
    fun explain(nodeIri: String, graph: Graph?): String {
        val sb = StringBuilder()
        try {
            val ref = NodeRef.parse(nodeIri)
            sb.append("asset=<").append(ref.assetIri).append("> path=").append(ref.path)
            sb.append(" profile=<").append(profileFor(ref.assetIri, graph)).append('>')
            val node = resolve(nodeIri, graph)
            sb.append(" kind=").append(node.kind)
            node.byteRange?.let { sb.append(" bytes=[").append(it.start).append(',').append(it.end).append(')') }
            node.field?.hasDataLayout?.let { sb.append(" layout=declared") }
            (node.value as? MultiDimensionalData)?.let { sb.append(" shape=").append(it.shape) }
        } catch (e: HexplainQueryException) {
            sb.append(" error=").append(e.message)
        }
        lastFailure(nodeIri)?.let { sb.append(" lastFailure=").append(it) }
        return sb.toString()
    }

    private fun profileFor(assetIri: String, graph: Graph?): String {
        assetProfiles[assetIri]?.let { return it }
        if (graph != null) {
            val it = graph.find(NodeFactory.createURI(assetIri), CONFORMS_TO, Node.ANY)
            while (it.hasNext()) { val p = it.next().`object`; if (p.isURI && profiles.containsKey(p.uri)) return p.uri }
        }
        throw HexplainQueryException("no profile is bound for <$assetIri>: call bindAsset() or assert <$assetIri> dcterms:conformsTo <a registered profile>")
    }

    private fun parsedAsset(assetIri: String, graph: Graph?): ParsedAsset {
        val profileIri = profileFor(assetIri, graph)
        cache.get(assetIri, profileIri)?.let { return it }
        val source = resolver.open(assetIri) ?: throw HexplainQueryException("no resolver can open <$assetIri>")
        val bytes = source.readAll()
        val formatIR = profiles.getValue(profileIri)
        val tree = try {
            Metaparser(formatIR, codecRegistry, recordByteRange = true, recordStructName = true, limits = limits.parseLimits).parse(bytes)
        } catch (e: HexplainParsingException) {
            throw HexplainQueryException("parsing <$assetIri> against <$profileIri> failed: ${e.message}", e)
        }
        return ParsedAsset(assetIri, profileIri, formatIR, bytes, tree).also { cache.put(it) }
    }

    @Suppress("UNCHECKED_CAST")
    private fun walk(ref: NodeRef, parsed: ParsedAsset): ResolvedNode {
        val rootMap: Map<String, Any> = (parsed.tree as? Map<String, Any>)
            ?: ((parsed.tree as? List<*>)?.firstOrNull() as? Map<String, Any>)
            ?: emptyMap()
        var current: Any? = parsed.tree
        var struct: Map<String, Any>? = null
        var parent: Map<String, Any>? = null
        var field: io.hexplain.core.ir.FieldIR? = null
        var owner: Map<String, Any>? = null
        fun enter(map: Map<String, Any>) { parent = struct; struct = map }
        if (current is Map<*, *>) enter(current as Map<String, Any>)
        for (seg in ref.segments.drop(1)) {
            val c = current
            current = when (c) {
                is Map<*, *> -> {
                    val map = c as Map<String, Any>
                    val v = map[seg] ?: throw HexplainQueryException("path '${ref.path}': no field or value named '$seg'")
                    field = structIrOf(map, parsed.formatIR)?.fields?.firstOrNull { it.name == seg }
                    owner = map
                    v
                }
                is List<*> -> {
                    val i = seg.toIntOrNull() ?: throw HexplainQueryException("path '${ref.path}': expected a list index, got '$seg'")
                    if (i !in c.indices) throw HexplainQueryException("path '${ref.path}': index $i is outside a list of ${c.size}")
                    c[i]
                }
                else -> throw HexplainQueryException("path '${ref.path}': '$seg' descends below a scalar value")
            }
            if (current is Map<*, *>) { enter(current as Map<String, Any>); field = null }
        }
        val owning = struct ?: throw HexplainQueryException("path '${ref.path}': the asset has no root struct")
        val byteRange = when {
            current is Map<*, *> -> rangeOfStruct(current as Map<String, Any>)
            field != null && owner != null -> rangeOfField(owner!!, field!!.name)
            else -> null
        }
        return ResolvedNode(ref, parsed.formatIR, parsed.bytes, current, owning, parent, rootMap, structIrOf(owning, parsed.formatIR), field, byteRange)
    }

    private fun structIrOf(map: Map<String, Any>, formatIR: FormatIR): StructIR? =
        (map[Metaparser.STRUCT_NAME_KEY] as? String)?.let { formatIR.structs[it] }

    private fun rangeOfStruct(map: Map<String, Any>): ByteRange? {
        val offset = (map[Metaparser.BYTE_OFFSET_KEY] as? Number)?.toLong() ?: return null
        val length = (map[Metaparser.BYTE_LENGTH_KEY] as? Number)?.toLong() ?: return null
        return ByteRange(offset, length)
    }

    private fun rangeOfField(owner: Map<String, Any>, name: String): ByteRange? {
        val range = (owner[Metaparser.FIELD_RANGES_KEY] as? Map<*, *>)?.get(name) as? List<*> ?: return null
        val start = (range.getOrNull(0) as? Number)?.toLong() ?: return null
        val end = (range.getOrNull(1) as? Number)?.toLong() ?: return null
        return ByteRange(start, end - start)
    }

    private companion object {
        val CONFORMS_TO: Node = NodeFactory.createURI("http://purl.org/dc/terms/conformsTo")
    }
}

internal class ParsedAsset(val assetIri: String, val profileIri: String, val formatIR: FormatIR, val bytes: ByteArray, val tree: Any) {
    /** Bytes plus a rough factor for the boxed parse tree. */
    val cost: Long = bytes.size.toLong() * 3 + 1024
}

/** Least-recently-used cache under a byte budget. An asset dearer than the whole budget is never kept. */
internal class ParsedAssetCache(private val budget: Long) {
    private val entries = LinkedHashMap<String, ParsedAsset>(16, 0.75f, true)
    private var used = 0L

    @Synchronized fun get(assetIri: String, profileIri: String): ParsedAsset? =
        entries[assetIri]?.takeIf { it.profileIri == profileIri }

    @Synchronized fun put(parsed: ParsedAsset) {
        if (parsed.cost > budget) return
        entries.remove(parsed.assetIri)?.let { used -= it.cost }
        entries[parsed.assetIri] = parsed
        used += parsed.cost
        val it = entries.entries.iterator()
        while (used > budget && it.hasNext()) { used -= it.next().value.cost; it.remove() }
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.runtime.HexplainQueryRuntimeTest"`
Expected: PASS (9 tests). If `resolves list elements and nested structs` fails because the parser names the nested struct differently, print `n.struct.keys` and adjust the fixture's struct-typed field (`DataTypeIR(band.name, BaseType.BYTES, 0)` is how the compiler represents it) rather than the assertion.

- [ ] **Step 6: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/runtime query/src/test/kotlin/io/hexplain/query/Fixtures.kt query/src/test/kotlin/io/hexplain/query/Sparql.kt query/src/test/kotlin/io/hexplain/query/runtime/HexplainQueryRuntimeTest.kt
git commit -m "feat(query): runtime that resolves lifted node IRIs to bytes, parse trees and layouts"
```

---
### Task 4: ARQ function base, registration, byte layer and explain

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/fn/HexplainFunction.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/fn/Values.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/fn/ByteFunctions.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/fn/DiagnosticFunctions.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/ByteFunctionsTest.kt`

**Interfaces:**
- Produces: `abstract class HexplainFunction(runtime, minArgs, maxArgs = minArgs) : FunctionBase { abstract fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue; protected fun node(args, i, env): ResolvedNode; iri(args, i): String; int(args, i): Int; long(args, i): Long; double(args, i): Double; string(args, i): String }`. Any `HexplainQueryException`, `HexplainParsingException`, `IllegalArgumentException`, `IndexOutOfBoundsException` or `ArithmeticException` thrown from `exec` becomes an `ExprEvalException` after being recorded against the first IRI argument.
- Produces: `object Values { fun hex(bytes): NodeValue; fun hexToBytes(nv): ByteArray; fun ofKotlin(value: Any?, maxBytes: Int): NodeValue }`.
- Produces: `object HexplainFunctions { fun register(runtime, functions = FunctionRegistry.get(), propertyFunctions = PropertyFunctionRegistry.get()) }`. Later tasks add one `put` line each.

- [ ] **Step 1: Write the failing test**

`query/src/test/kotlin/io/hexplain/query/fn/ByteFunctionsTest.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import io.hexplain.query.runtime.QueryLimits
import org.apache.jena.datatypes.xsd.XSDDatatype
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import java.security.MessageDigest

class ByteFunctionsTest {
    private val g = Fixtures.grid()
    @BeforeEach fun install() = HexplainFunctions.register(g.runtime)

    @Test
    fun `bytes of a struct, of a field, and a slice`() {
        val row = Sparql.select(g.model, """
            SELECT (hxf:bytes(<${g.node("root")}>) AS ?all) (hxf:bytes(<${g.node("root/Samples")}>) AS ?s) (hxf:bytes(<${g.node("root")}>, 3, 2) AS ?slice) WHERE {}
        """).single()
        assertEquals("0302ff0a14ff28323c", row.getLiteral("all").lexicalForm)
        assertEquals(XSDDatatype.XSDhexBinary.uri, row.getLiteral("all").datatypeURI)
        assertEquals("0a14ff28323c", row.getLiteral("s").lexicalForm)
        assertEquals("0a14", row.getLiteral("slice").lexicalForm)
    }

    @Test
    fun `an out-of-range slice, a two-argument call and a non-IRI are unbound`() {
        assertNull(Sparql.one(g.model, "SELECT (hxf:bytes(<${g.node("root")}>, 8, 5) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:bytes(<${g.node("root")}>, 8) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:bytes(\"x\") AS ?v) WHERE {}"))
    }

    @Test
    fun `the byte cap makes the call unbound and explain says why`() {
        val capped = g.withLimits(QueryLimits(maxBytesPerCall = 4))
        HexplainFunctions.register(capped.runtime)
        assertNull(Sparql.one(capped.model, "SELECT (hxf:bytes(<${g.node("root")}>) AS ?v) WHERE {}"))
        val why = Sparql.one(capped.model, "SELECT (hxf:explain(<${g.node("root")}>) AS ?v) WHERE {}")!!.asLiteral().string
        assertTrue(why.contains("maxBytesPerCall"), why)
        assertTrue(why.contains("kind=struct"), why)
    }

    @Test
    fun `digest accepts a register concept or an algorithm name`() {
        val expected = MessageDigest.getInstance("SHA-256").digest(g.bytes).joinToString("") { "%02x".format(it) }
        val row = Sparql.select(g.model, """
            SELECT (hxf:digest(<${g.node("root")}>, rck:SHA256) AS ?a) (hxf:digest(<${g.node("root")}>, "SHA-256") AS ?b) (hxf:digest(<${g.node("root")}>, rck:CRC32) AS ?c) WHERE {}
        """).single()
        assertEquals(expected, row.getLiteral("a").string)
        assertEquals(expected, row.getLiteral("b").string)
        val crc = java.util.zip.CRC32().apply { update(g.bytes) }.value
        assertEquals("%08x".format(crc), row.getLiteral("c").string)
        assertNull(Sparql.one(g.model, "SELECT (hxf:digest(<${g.node("root")}>, \"whirlpool\") AS ?v) WHERE {}"))
    }

    @Test
    fun `decodedBytes inverts the codec chain while bytes stays raw`() {
        val z = Fixtures.zipped()
        HexplainFunctions.register(z.runtime)
        val row = Sparql.select(z.model, "SELECT (hxf:bytes(<${z.node("root/Payload")}>) AS ?raw) (hxf:decodedBytes(<${z.node("root/Payload")}>) AS ?dec) WHERE {}").single()
        assertEquals(z.bytes.joinToString("") { "%02x".format(it) }, row.getLiteral("raw").lexicalForm)
        assertEquals("68656c6c6f", row.getLiteral("dec").lexicalForm)
        assertEquals("0a14ff28323c", Sparql.one(g.model.also { HexplainFunctions.register(g.runtime) }, "SELECT (hxf:decodedBytes(<${g.node("root/Samples")}>) AS ?v) WHERE {}")!!.asLiteral().lexicalForm)
    }

    @Test
    fun `explain on a nonexistent node reports the error instead of failing the query`() {
        val why = Sparql.one(g.model, "SELECT (hxf:explain(<${g.node("root/Nope")}>) AS ?v) WHERE {}")!!.asLiteral().string
        assertTrue(why.contains("error="), why)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.ByteFunctionsTest"`
Expected: compilation errors (`HexplainFunctions` missing).

- [ ] **Step 3: Implement the base class and value helpers**

`fn/HexplainFunction.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.metacodec.HexplainParsingException
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import io.hexplain.query.runtime.ResolvedNode
import org.apache.jena.query.QueryBuildException
import org.apache.jena.sparql.engine.binding.Binding
import org.apache.jena.sparql.expr.ExprEvalException
import org.apache.jena.sparql.expr.ExprList
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionBase
import org.apache.jena.sparql.function.FunctionEnv

/**
 * Base of every hxf: function. Evaluates arguments itself so [exec] can see the active graph,
 * checks arity at build time, and turns every engine failure into an unbound result after
 * recording it against the node argument, so hxf:explain can say what happened.
 */
abstract class HexplainFunction(
    protected val runtime: HexplainQueryRuntime,
    private val minArgs: Int,
    private val maxArgs: Int = minArgs
) : FunctionBase() {

    override fun checkBuild(uri: String, args: ExprList) {
        if (args.size() < minArgs || args.size() > maxArgs)
            throw QueryBuildException("$uri takes $minArgs..$maxArgs arguments, got ${args.size()}")
    }

    override fun exec(binding: Binding, args: ExprList, uri: String, env: FunctionEnv): NodeValue {
        val values = args.list.map { it.eval(binding, env) }
        return try {
            exec(values, env)
        } catch (e: ExprEvalException) {
            throw e
        } catch (e: HexplainQueryException) {
            fail(values, e.message ?: "failed")
        } catch (e: HexplainParsingException) {
            fail(values, e.message ?: "parse failed")
        } catch (e: IllegalArgumentException) {
            fail(values, e.message ?: "bad argument")
        } catch (e: IndexOutOfBoundsException) {
            fail(values, e.message ?: "out of range")
        } catch (e: ArithmeticException) {
            fail(values, e.message ?: "arithmetic overflow")
        }
    }

    /** The list-only entry point of [FunctionBase] is bypassed: the graph-aware form above is used instead. */
    override fun exec(args: List<NodeValue>): NodeValue = throw IllegalStateException("exec(List<NodeValue>) is not used")

    abstract fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue

    private fun fail(values: List<NodeValue>, message: String): Nothing {
        val first = values.firstOrNull()
        if (first != null && first.isIRI) runtime.recordFailure(first.asNode().uri, message)
        throw ExprEvalException(message)
    }

    protected fun node(args: List<NodeValue>, i: Int, env: FunctionEnv): ResolvedNode = runtime.resolve(iri(args, i), env.activeGraph)

    protected fun iri(args: List<NodeValue>, i: Int): String {
        val v = args[i]
        if (!v.isIRI) throw HexplainQueryException("argument ${i + 1} must be an IRI, got $v")
        return v.asNode().uri
    }

    protected fun int(args: List<NodeValue>, i: Int): Int {
        val v = args[i]
        if (!v.isInteger) throw HexplainQueryException("argument ${i + 1} must be an integer, got $v")
        return v.integer.intValueExact()
    }

    protected fun long(args: List<NodeValue>, i: Int): Long {
        val v = args[i]
        if (!v.isInteger) throw HexplainQueryException("argument ${i + 1} must be an integer, got $v")
        return v.integer.longValueExact()
    }

    protected fun double(args: List<NodeValue>, i: Int): Double {
        val v = args[i]
        if (!v.isNumber) throw HexplainQueryException("argument ${i + 1} must be a number, got $v")
        return v.double
    }

    protected fun string(args: List<NodeValue>, i: Int): String {
        val v = args[i]
        if (!v.isString) throw HexplainQueryException("argument ${i + 1} must be a string, got $v")
        return v.string
    }
}
```

`fn/Values.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.codec.PreservedEncodedBytes
import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.query.runtime.HexplainQueryException
import org.apache.jena.datatypes.xsd.XSDDatatype
import org.apache.jena.graph.NodeFactory
import org.apache.jena.sparql.expr.NodeValue
import java.math.BigDecimal
import java.math.BigInteger

/** Kotlin parse-tree values to SPARQL values and back. */
object Values {
    fun hex(bytes: ByteArray): NodeValue =
        NodeValue.makeNode(NodeFactory.createLiteralDT(bytes.joinToString("") { "%02x".format(it) }, XSDDatatype.XSDhexBinary))

    fun hexToBytes(nv: NodeValue): ByteArray {
        val node = nv.asNode()
        if (!node.isLiteral || node.literalDatatypeURI != XSDDatatype.XSDhexBinary.uri)
            throw HexplainQueryException("expected an xsd:hexBinary literal, got $nv")
        val lex = node.literalLexicalForm
        if (lex.length % 2 != 0) throw HexplainQueryException("odd-length hexBinary literal")
        return ByteArray(lex.length / 2) { lex.substring(2 * it, 2 * it + 2).toInt(16).toByte() }
    }

    fun ofKotlin(value: Any?, maxBytes: Int): NodeValue = when (value) {
        null -> throw HexplainQueryException("the value is absent")
        is Boolean -> NodeValue.makeBoolean(value)
        is Int, is Long, is Short, is Byte -> NodeValue.makeInteger((value as Number).toLong())
        is BigInteger -> NodeValue.makeInteger(value)
        is Float -> NodeValue.makeDouble(value.toDouble())
        is Double -> NodeValue.makeDouble(value)
        is BigDecimal -> NodeValue.makeDecimal(value)
        is String -> NodeValue.makeString(value)
        is ByteArray -> {
            if (value.size > maxBytes) throw HexplainQueryException("a byte value of ${value.size} bytes exceeds maxBytesPerCall $maxBytes")
            hex(value)
        }
        is PreservedEncodedBytes -> ofKotlin(value.decoded, maxBytes)
        is MultiDimensionalData -> throw HexplainQueryException("an array has no scalar value; use hxf:cell")
        is Map<*, *> -> throw HexplainQueryException("a struct has no scalar value; name one of its fields")
        is List<*> -> throw HexplainQueryException("a list has no scalar value; index an element")
        else -> NodeValue.makeString(value.toString())
    }
}
```

- [ ] **Step 4: Implement the byte functions and explain**

`fn/ByteFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.codec.PreservedEncodedBytes
import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv
import java.security.MessageDigest
import java.util.zip.CRC32

/** hxf:bytes(node) / hxf:bytes(node, offset, length): the node's bytes as they sit in the file. */
class BytesFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1, 3) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        if (args.size == 2) throw HexplainQueryException("hxf:bytes takes a node, or a node with offset and length")
        val raw = node(args, 0, env).rawBytes()
        val offset = if (args.size == 3) int(args, 1) else 0
        val length = if (args.size == 3) int(args, 2) else raw.size
        if (offset < 0 || length < 0 || offset.toLong() + length > raw.size)
            throw HexplainQueryException("slice [$offset, ${offset + length}) is outside the node's ${raw.size} bytes")
        checkCap(length)
        return Values.hex(raw.copyOfRange(offset, offset + length))
    }
    private fun checkCap(length: Int) {
        if (length > runtime.limits.maxBytesPerCall)
            throw HexplainQueryException("$length bytes exceed maxBytesPerCall ${runtime.limits.maxBytesPerCall}")
    }
}

/** hxf:decodedBytes(node): the node's bytes after the codec chain the profile declares has been inverted. */
class DecodedBytesFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val node = node(args, 0, env)
        val decoded = when (val v = node.value) {
            is PreservedEncodedBytes -> v.decoded
            is MultiDimensionalData -> v.data
            is ByteArray -> v                           // the parser already stores decoded bytes
            else -> {
                val raw = node.rawBytes()
                val chain = node.field?.encodedWith.orEmpty()
                if (chain.isEmpty()) raw else runtime.codecs.decode(raw, chain)
            }
        }
        if (decoded.size > runtime.limits.maxBytesPerCall)
            throw HexplainQueryException("${decoded.size} decoded bytes exceed maxBytesPerCall ${runtime.limits.maxBytesPerCall}")
        return Values.hex(decoded)
    }
}

/** hxf:digest(node, algorithm): lower-case hex digest of the node's raw bytes; algorithm is a checksum-register concept or a name. */
class DigestFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val raw = node(args, 0, env).rawBytes()
        val name = when {
            args[1].isIRI -> args[1].asNode().uri.substringAfterLast('#').substringAfterLast('/')
            args[1].isString -> args[1].string
            else -> throw HexplainQueryException("argument 2 must be a register concept IRI or an algorithm name")
        }
        val hex = when (name.uppercase().replace("-", "")) {
            "CRC32" -> "%08x".format(CRC32().apply { update(raw) }.value)
            "MD5" -> digest("MD5", raw)
            "SHA1" -> digest("SHA-1", raw)
            "SHA256" -> digest("SHA-256", raw)
            "SHA512" -> digest("SHA-512", raw)
            else -> throw HexplainQueryException("unknown digest algorithm '$name' (CRC32, MD5, SHA1, SHA256, SHA512)")
        }
        return NodeValue.makeString(hex)
    }
    private fun digest(algorithm: String, raw: ByteArray) =
        MessageDigest.getInstance(algorithm).digest(raw).joinToString("") { "%02x".format(it) }
}
```

`fn/DiagnosticFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv

/** hxf:explain(node): how the runtime resolves the node and why the last call on it failed. Never unbound. */
class ExplainFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val target = if (args[0].isIRI) args[0].asNode().uri else return NodeValue.makeString("argument is not an IRI: ${args[0]}")
        return NodeValue.makeString(runtime.explain(target, env.activeGraph))
    }
}
```

`HexplainFunctions.kt`:
```kotlin
package io.hexplain.query

import io.hexplain.query.fn.*
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.sparql.function.FunctionFactory
import org.apache.jena.sparql.function.FunctionRegistry
import org.apache.jena.sparql.pfunction.PropertyFunctionRegistry

/** Registers every hxf: function against one runtime. Registering again replaces the previous runtime. */
object HexplainFunctions {
    fun register(
        runtime: HexplainQueryRuntime,
        functions: FunctionRegistry = FunctionRegistry.get(),
        propertyFunctions: PropertyFunctionRegistry = PropertyFunctionRegistry.get()
    ) {
        fun put(uri: String, make: () -> HexplainFunction) = functions.put(uri, FunctionFactory { make() })
        // Layer 0
        put(HXF.bytes) { BytesFunction(runtime) }
        put(HXF.decodedBytes) { DecodedBytesFunction(runtime) }
        put(HXF.digest) { DigestFunction(runtime) }
        // Diagnostics
        put(HXF.explain) { ExplainFunction(runtime) }
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.ByteFunctionsTest"`
Expected: PASS (6 tests). If `FunctionBase.exec(Binding, ExprList, String, FunctionEnv)` cannot be overridden in this Jena version, make `HexplainFunction` implement `org.apache.jena.sparql.function.Function` directly with `build(uri, args, context)` calling `checkBuild` and the same `exec` body; the tests do not change.

- [ ] **Step 6: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/fn/HexplainFunction.kt query/src/main/kotlin/io/hexplain/query/fn/Values.kt query/src/main/kotlin/io/hexplain/query/fn/ByteFunctions.kt query/src/main/kotlin/io/hexplain/query/fn/DiagnosticFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/ByteFunctionsTest.kt
git commit -m "feat(query): hxf:bytes, decodedBytes, digest and explain on an ARQ function base"
```

---

### Task 5: Value layer — hxf:value, hxf:hel, hxf:decode

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/fn/ValueFunctions.kt`
- Modify: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/ValueFunctionsTest.kt`

**Interfaces:**
- Produces: `ValueFunction`, `HelFunction`, `DecodeFunction`, `object BddoTypes { fun resolve(iri): DataTypeIR }`, `object ScalarDecoder { fun decode(bytes, type): NodeValue }`.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fn

import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class ValueFunctionsTest {
    private val g = Fixtures.grid()
    @BeforeEach fun install() = HexplainFunctions.register(g.runtime)

    @Test
    fun `value reads any parsed scalar, mapped or not`() {
        assertEquals(3, Sparql.one(g.model, "SELECT (hxf:value(<${g.node("root/Width")}>) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(255, Sparql.one(g.model, "SELECT (hxf:value(<${g.node("root/NoData")}>) AS ?v) WHERE {}")!!.asLiteral().int)
    }

    @Test
    fun `value of a struct or an array is unbound`() {
        assertNull(Sparql.one(g.model, "SELECT (hxf:value(<${g.node("root")}>) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:value(<${g.node("root/Samples")}>) AS ?v) WHERE {}"))
    }

    @Test
    fun `hel evaluates in the node's struct context`() {
        assertEquals(6, Sparql.one(g.model, "SELECT (hxf:hel(<${g.node("root")}>, \"Width * Height\") AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(6, Sparql.one(g.model, "SELECT (hxf:hel(<${g.node("root/Samples")}>, \"instance.Width * instance.Height\") AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(true, Sparql.one(g.model, "SELECT (hxf:hel(<${g.node("root")}>, \"Width > Height\") AS ?v) WHERE {}")!!.asLiteral().boolean)
        val p = Fixtures.planar(); HexplainFunctions.register(p.runtime)
        assertEquals(2, Sparql.one(p.model, "SELECT (hxf:hel(<${p.node("root/Bands/1")}>, \"parent.Count\") AS ?v) WHERE {}")!!.asLiteral().int)
    }

    @Test
    fun `a HEL error is unbound and explained`() {
        assertNull(Sparql.one(g.model, "SELECT (hxf:hel(<${g.node("root")}>, \"Width +\") AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:hel(<${g.node("root")}>, \"NoSuchField * 2\") AS ?v) WHERE {}"))
        assertTrue(g.runtime.explain(g.node("root"), null).contains("lastFailure="))
    }

    @Test
    fun `decode reads a scalar from bytes by BDDO datatype`() {
        val row = Sparql.select(g.model, """
            SELECT (hxf:decode("0102"^^xsd:hexBinary, bddo:uint16be) AS ?a)
                   (hxf:decode("ffff"^^xsd:hexBinary, bddo:int16be) AS ?b)
                   (hxf:decode("0000803f"^^xsd:hexBinary, bddo:float32le) AS ?c)
                   (hxf:decode("ff"^^xsd:hexBinary, bddo:uint8) AS ?d)
                   (hxf:decode("6869"^^xsd:hexBinary, bddo:string) AS ?e)
            WHERE {}
        """).single()
        assertEquals(258, row.getLiteral("a").int)
        assertEquals(-1, row.getLiteral("b").int)
        assertEquals(1.0, row.getLiteral("c").double, 0.0)
        assertEquals(255, row.getLiteral("d").int)
        assertEquals("hi", row.getLiteral("e").string)
        assertNull(Sparql.one(g.model, "SELECT (hxf:decode(\"010203\"^^xsd:hexBinary, bddo:uint16be) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:decode(\"01\"^^xsd:hexBinary, <https://example.org/NotAType>) AS ?v) WHERE {}"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.ValueFunctionsTest"`
Expected: every test fails with "Unknown function" errors surfacing as query build failures (`QueryException`), or unbound results.

- [ ] **Step 3: Implement**

`fn/ValueFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.hel.AstNode
import io.hexplain.core.hel.HelEvaluationException
import io.hexplain.core.hel.HelEvaluator
import io.hexplain.core.hel.HelParser
import io.hexplain.core.hel.Lexer
import io.hexplain.core.ir.BaseType
import io.hexplain.core.ir.DataTypeIR
import io.hexplain.core.ir.Endianness
import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.ConcurrentHashMap

/** hxf:value(node): the parsed scalar at the path, typed as the lifter would type it. */
class ValueFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        Values.ofKotlin(node(args, 0, env).value, runtime.limits.maxBytesPerCall)
}

/** hxf:hel(node, expression): a HEL expression evaluated with the node's struct as `instance`. */
class HelFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val node = node(args, 0, env)
        val ast = parse(string(args, 1))
        val result = try {
            HelEvaluator(node.struct, node.parent, node.root, selfContext = node.value).evaluate(ast)
        } catch (e: HelEvaluationException) {
            throw HexplainQueryException("HEL: ${e.message}", e)
        }
        return Values.ofKotlin(result, runtime.limits.maxBytesPerCall)
    }

    private fun parse(expression: String): AstNode = asts.computeIfAbsent(expression) {
        try { HelParser(Lexer(it).tokenize()).parse() } catch (e: RuntimeException) { throw HexplainQueryException("HEL syntax: ${e.message}", e) }
    }

    private companion object { val asts = ConcurrentHashMap<String, AstNode>() }
}

/** hxf:decode(hexBinary, dataTypeIri): one scalar decoded from bytes by a bddo:DataType. */
class DecodeFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        ScalarDecoder.decode(Values.hexToBytes(args[0]), BddoTypes.resolve(iri(args, 1)))
}

/** The primitive datatypes of bddo.ttl, read once from the core classpath. */
object BddoTypes {
    private val model: Model by lazy {
        ModelFactory.createDefaultModel().also { m ->
            val stream = BddoTypes::class.java.classLoader.getResourceAsStream("bddo.ttl")
                ?: throw IllegalStateException("bddo.ttl is not on the classpath")
            RDFDataMgr.read(m, stream, Lang.TTL)
        }
    }

    fun resolve(iri: String): DataTypeIR {
        val res = model.getResource(iri)
        val base = res.getProperty(BDDO.baseType)?.`object`?.asResource()
            ?: throw HexplainQueryException("<$iri> is not a bddo:DataType with a bddo:baseType")
        val baseType = when (base) {
            BDDO.baseInteger -> BaseType.INTEGER
            BDDO.baseFloat -> BaseType.FLOAT
            BDDO.baseString -> BaseType.STRING
            BDDO.baseBytes -> BaseType.BYTES
            else -> throw HexplainQueryException("<$iri> has an unsupported base type <${base.uri}>")
        }
        val endianness = when (res.getProperty(BDDO.endianness)?.`object`?.asResource()) {
            BDDO.BigEndian -> Endianness.BIG_ENDIAN
            BDDO.LittleEndian -> Endianness.LITTLE_ENDIAN
            else -> Endianness.NOT_APPLICABLE
        }
        return DataTypeIR(
            name = iri,
            baseType = baseType,
            bitWidth = res.getProperty(BDDO.bitWidth)?.int ?: 0,
            isSigned = res.getProperty(BDDO.isSigned)?.boolean,
            hasEndianness = endianness,
            xsdType = res.getProperty(BDDO.xsdType)?.`object`?.asResource()?.uri
        )
    }
}

object ScalarDecoder {
    fun decode(data: ByteArray, type: DataTypeIR): NodeValue {
        val order = if (type.hasEndianness == Endianness.LITTLE_ENDIAN) ByteOrder.LITTLE_ENDIAN else ByteOrder.BIG_ENDIAN
        return when (type.baseType) {
            BaseType.INTEGER -> {
                val n = type.bitWidth / 8
                if (n !in 1..8 || data.size != n) throw HexplainQueryException("${type.name} needs $n bytes, got ${data.size}")
                val bytes = data.copyOf()
                if (order == ByteOrder.LITTLE_ENDIAN) bytes.reverse()
                NodeValue.makeInteger(if (type.isSigned == true) BigInteger(bytes) else BigInteger(1, bytes))
            }
            BaseType.FLOAT -> {
                val buf = ByteBuffer.wrap(data).order(order)
                when (data.size) {
                    4 -> NodeValue.makeDouble(buf.float.toDouble())
                    8 -> NodeValue.makeDouble(buf.double)
                    else -> throw HexplainQueryException("${type.name} needs 4 or 8 bytes, got ${data.size}")
                }
            }
            BaseType.STRING -> NodeValue.makeString(String(data, Charsets.UTF_8))
            BaseType.BYTES -> Values.hex(data)
        }
    }
}
```

Add to `HexplainFunctions.register` after the layer-0 lines:
```kotlin
        // Layer 1
        put(HXF.value) { ValueFunction(runtime) }
        put(HXF.hel) { HelFunction(runtime) }
        put(HXF.decode) { DecodeFunction(runtime) }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.ValueFunctionsTest"`
Expected: PASS (5 tests). If `Width +` parses without error and only fails at evaluation, the assertion still holds because evaluation errors are also unbound. If `HelEvaluator` rejects `NoSuchField` only when `contextSchema` is given, pass `contextSchema = node.structIR?.fields?.map { it.name }?.toSet()` so undefined names raise.

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/fn/ValueFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/ValueFunctionsTest.kt
git commit -m "feat(query): hxf:value, hxf:hel and hxf:decode"
```

---
### Task 6: Array access and hxf:rank, extent, cell, layout

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/runtime/ArrayAccess.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/fn/ArrayFunctions.kt`
- Modify: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/ArrayFunctionsTest.kt`

**Interfaces:**
- Produces: `class ArrayAccess { val data; val shape: List<Int>; val rank: Int; val axes: List<String>; fun dimensionOf(axisIri): Int; fun check(indices: IntArray); fun cell(indices): NodeValue; fun number(indices): Number; fun window(lo: IntArray, hi: IntArray, cap: Long): Sequence<IntArray>; fun count(lo, hi): Long; fun describe(): String; companion fun of(node: ResolvedNode): ArrayAccess }`.
- Produces: `RankFunction`, `ExtentFunction`, `CellFunction`, `LayoutFunction`.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fn

import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class ArrayFunctionsTest {
    private val g = Fixtures.grid()
    private val samples = "<${g.node("root/Samples")}>"
    @BeforeEach fun install() = HexplainFunctions.register(g.runtime)

    @Test
    fun `rank and extent by position or by axis`() {
        val row = Sparql.select(g.model, "SELECT (hxf:rank($samples) AS ?r) (hxf:extent($samples, 0) AS ?e0) (hxf:extent($samples, dlv:axisX) AS ?ex) (hxf:extent($samples, dlv:axisY) AS ?ey) WHERE {}").single()
        assertEquals(2, row.getLiteral("r").int)
        assertEquals(2, row.getLiteral("e0").int)
        assertEquals(3, row.getLiteral("ex").int)
        assertEquals(2, row.getLiteral("ey").int)
        assertNull(Sparql.one(g.model, "SELECT (hxf:extent($samples, dlv:axisBand) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:extent($samples, 2) AS ?v) WHERE {}"))
    }

    @Test
    fun `cell reads by zero-based indices in layout order`() {
        assertEquals(60, Sparql.one(g.model, "SELECT (hxf:cell($samples, 1, 2) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(255, Sparql.one(g.model, "SELECT (hxf:cell($samples, 0, 2) AS ?v) WHERE {}")!!.asLiteral().int)
        assertNull(Sparql.one(g.model, "SELECT (hxf:cell($samples, 2, 0) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:cell($samples, 0) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:cell(<${g.node("root")}>, 0, 0) AS ?v) WHERE {}"))
    }

    @Test
    fun `cell types follow the cell datatype`() {
        val i = Fixtures.interleaved(); HexplainFunctions.register(i.runtime)
        assertEquals(112, Sparql.one(i.model, "SELECT (hxf:cell(<${i.node("root/Samples")}>, 1, 1, 1) AS ?v) WHERE {}")!!.asLiteral().int)
        val p = Fixtures.planar(); HexplainFunctions.register(p.runtime)
        val v = Sparql.one(p.model, "SELECT (hxf:cell(<${p.node("root/Bands/1/Samples")}>, 0, 1) AS ?v) WHERE {}")!!.asLiteral()
        assertEquals(20.5, v.double, 0.0)
        assertEquals("http://www.w3.org/2001/XMLSchema#double", v.datatypeURI)
    }

    @Test
    fun `layout describes the resolved dimensions`() {
        val s = Sparql.one(g.model, "SELECT (hxf:layout($samples) AS ?v) WHERE {}")!!.asLiteral().string
        assertTrue(s.contains("rank=2"), s)
        assertTrue(s.contains("axisY:2"), s)
        assertTrue(s.contains("axisX:3"), s)
        assertTrue(s.contains("uint8"), s)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.ArrayFunctionsTest"`
Expected: failures (unknown functions).

- [ ] **Step 3: Implement**

`runtime/ArrayAccess.kt`:
```kotlin
package io.hexplain.query.runtime

import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.query.fn.Values
import org.apache.jena.sparql.expr.NodeValue

/** Index arithmetic over one parsed DLV array; the executor is [MultiDimensionalData], this adds bounds, windows and typing. */
class ArrayAccess private constructor(val data: MultiDimensionalData) {
    val shape: List<Int> = data.shape
    val rank: Int get() = shape.size
    val axes: List<String> = data.layout.dimensions.map { it.axis }

    fun dimensionOf(axisIri: String): Int {
        val d = axes.indexOf(axisIri)
        if (d < 0) throw HexplainQueryException("the array has no dimension on axis <$axisIri>; its axes are ${axes.map { it.substringAfter('#') }}")
        return d
    }

    fun check(indices: IntArray) {
        if (indices.size != rank) throw HexplainQueryException("expected $rank indices, got ${indices.size}")
        for (d in indices.indices) if (indices[d] !in 0 until shape[d])
            throw HexplainQueryException("index ${indices[d]} is outside dimension $d (${axes[d].substringAfter('#')}, extent ${shape[d]})")
    }

    fun cell(indices: IntArray): NodeValue {
        check(indices)
        return when (val d = data) {
            is MultiDimensionalData.IntData -> NodeValue.makeInteger(d.getInteger(*indices))
            is MultiDimensionalData.FloatData -> NodeValue.makeDouble(d.getDouble(*indices))
            is MultiDimensionalData.StringData -> NodeValue.makeString(d.getString(*indices))
            is MultiDimensionalData.BytesData -> Values.hex(d.getBytes(*indices))
        }
    }

    fun number(indices: IntArray): Number {
        check(indices)
        return when (val d = data) {
            is MultiDimensionalData.IntData -> d.getInteger(*indices)
            is MultiDimensionalData.FloatData -> d.getDouble(*indices)
            else -> throw HexplainQueryException("statistics need numeric cells; this array holds ${d.layout.cellDataType.name.substringAfter('#')}")
        }
    }

    /** Cells in the half-open window [lo, hi) per dimension; null if it is empty. */
    fun count(lo: IntArray, hi: IntArray): Long {
        if (lo.size != rank || hi.size != rank) throw HexplainQueryException("a window needs $rank (lo, hi) pairs")
        var count = 1L
        for (d in 0 until rank) {
            if (lo[d] < 0 || hi[d] > shape[d] || lo[d] > hi[d])
                throw HexplainQueryException("window [${lo[d]}, ${hi[d]}) is outside dimension $d (extent ${shape[d]})")
            count = Math.multiplyExact(count, (hi[d] - lo[d]).toLong())
        }
        return count
    }

    /** Row-major walk (last dimension fastest) of the window; refuses windows over [cap] cells. */
    fun window(lo: IntArray, hi: IntArray, cap: Long): Sequence<IntArray> {
        val total = count(lo, hi)
        if (total > cap) throw HexplainQueryException("a window of $total cells exceeds maxCellsPerWindow $cap")
        if (total == 0L) return emptySequence()
        return sequence {
            val idx = lo.copyOf()
            while (true) {
                yield(idx.copyOf())
                var d = rank - 1
                while (d >= 0) {
                    idx[d]++
                    if (idx[d] < hi[d]) break
                    idx[d] = lo[d]
                    d--
                }
                if (d < 0) break
            }
        }
    }

    fun describe(): String {
        val dims = data.layout.dimensions.mapIndexed { i, dim ->
            dim.axis.substringAfter('#') + ":" + shape[i] + (dim.stride?.let { "/stride=$it" } ?: "")
        }
        return "rank=$rank dims=[${dims.joinToString(",")}] cell=${data.layout.cellDataType.name.substringAfter('#')}"
    }

    companion object {
        fun of(node: ResolvedNode): ArrayAccess = when (val v = node.value) {
            is MultiDimensionalData -> ArrayAccess(v)
            else -> throw HexplainQueryException(
                "${node.ref.path} is not an array (it is a ${node.kind})" +
                    if (node.field?.hasDataLayout != null) ", although its field declares a layout the engine did not execute" else ""
            )
        }
    }
}
```

`fn/ArrayFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.query.runtime.ArrayAccess
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv

/** hxf:rank(array) */
class RankFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeInteger(ArrayAccess.of(node(args, 0, env)).rank.toLong())
}

/** hxf:extent(array, dim): dim is a zero-based position or a dlv:Axis IRI. */
class ExtentFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val access = ArrayAccess.of(node(args, 0, env))
        val d = when {
            args[1].isIRI -> access.dimensionOf(args[1].asNode().uri)
            args[1].isInteger -> int(args, 1)
            else -> throw HexplainQueryException("argument 2 must be a dimension position or a dlv:Axis IRI")
        }
        if (d !in 0 until access.rank) throw HexplainQueryException("dimension $d is outside rank ${access.rank}")
        return NodeValue.makeInteger(access.shape[d].toLong())
    }
}

/** hxf:cell(array, i1, ..., in) */
class CellFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2, 1 + MAX_RANK) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val access = ArrayAccess.of(node(args, 0, env))
        val indices = IntArray(args.size - 1) { int(args, it + 1) }
        return access.cell(indices)
    }
    companion object { const val MAX_RANK = 16 }
}

/** hxf:layout(array): the resolved layout, for diagnostics. */
class LayoutFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeString(ArrayAccess.of(node(args, 0, env)).describe())
}
```

Add to `HexplainFunctions.register`:
```kotlin
        // Layer 2
        put(HXF.rank) { RankFunction(runtime) }
        put(HXF.extent) { ExtentFunction(runtime) }
        put(HXF.cell) { CellFunction(runtime) }
        put(HXF.layout) { LayoutFunction(runtime) }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.ArrayFunctionsTest"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/runtime/ArrayAccess.kt query/src/main/kotlin/io/hexplain/query/fn/ArrayFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/ArrayFunctionsTest.kt
git commit -m "feat(query): hxf:rank, extent, cell and layout over DLV arrays"
```

---

### Task 7: hxf:window property function and hxf:stat

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/fn/WindowPropertyFunction.kt`
- Modify: `query/src/main/kotlin/io/hexplain/query/fn/ArrayFunctions.kt` (add `StatFunction`)
- Modify: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/WindowAndStatTest.kt`

**Interfaces:**
- Produces: property function `(?array lo1 hi1 ... lon hin) hxf:window (?i1 ... ?in ?v)`; `StatFunction` for `hxf:stat(array, kind)` and `hxf:stat(array, kind, lo1, hi1, ...)` with kinds `min max sum mean count`.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fn

import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import io.hexplain.query.runtime.QueryLimits
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class WindowAndStatTest {
    private val g = Fixtures.grid()
    private val samples = "<${g.node("root/Samples")}>"
    @BeforeEach fun install() = HexplainFunctions.register(g.runtime)

    @Test
    fun `window enumerates cells in row-major order with their indices`() {
        val rows = Sparql.select(g.model, "SELECT ?y ?x ?v WHERE { ($samples 0 2 0 3) hxf:window (?y ?x ?v) }")
        assertEquals(listOf(10, 20, 255, 40, 50, 60), rows.map { it.getLiteral("v").int })
        assertEquals(listOf(0, 0, 0, 1, 1, 1), rows.map { it.getLiteral("y").int })
        assertEquals(listOf(0, 1, 2, 0, 1, 2), rows.map { it.getLiteral("x").int })
    }

    @Test
    fun `window respects bounds, joins with bound variables, and matches constants`() {
        assertEquals(2, Sparql.select(g.model, "SELECT ?v WHERE { ($samples 0 1 1 3) hxf:window (?y ?x ?v) }").size)
        assertEquals(listOf(40, 50, 60), Sparql.select(g.model, "SELECT ?v WHERE { VALUES ?y { 1 } ($samples 0 2 0 3) hxf:window (?y ?x ?v) }").map { it.getLiteral("v").int })
        assertEquals(listOf(2), Sparql.select(g.model, "SELECT ?x WHERE { ($samples 0 2 0 3) hxf:window (0 ?x 255) }").map { it.getLiteral("x").int })
        assertEquals(0, Sparql.select(g.model, "SELECT ?v WHERE { ($samples 0 2) hxf:window (?y ?x ?v) }").size)
        assertEquals(0, Sparql.select(g.model, "SELECT ?v WHERE { ($samples 0 5 0 3) hxf:window (?y ?x ?v) }").size)
    }

    @Test
    fun `window refuses more cells than the cap and explains`() {
        val capped = g.withLimits(QueryLimits(maxCellsPerWindow = 4))
        HexplainFunctions.register(capped.runtime)
        assertEquals(0, Sparql.select(capped.model, "SELECT ?v WHERE { ($samples 0 2 0 3) hxf:window (?y ?x ?v) }").size)
        assertEquals(4, Sparql.select(capped.model, "SELECT ?v WHERE { ($samples 0 2 0 2) hxf:window (?y ?x ?v) }").size)
        assertTrue(capped.runtime.explain(g.node("root/Samples"), null).contains("maxCellsPerWindow"))
    }

    @Test
    fun `stat over the whole array and over a window`() {
        val row = Sparql.select(g.model, """
            SELECT (hxf:stat($samples, "min") AS ?min) (hxf:stat($samples, "max") AS ?max) (hxf:stat($samples, "sum") AS ?sum)
                   (hxf:stat($samples, "mean") AS ?mean) (hxf:stat($samples, "count") AS ?count) (hxf:stat($samples, "mean", 1, 2, 0, 3) AS ?row1)
            WHERE {}
        """).single()
        assertEquals(10, row.getLiteral("min").int)
        assertEquals(255, row.getLiteral("max").int)
        assertEquals(435, row.getLiteral("sum").int)
        assertEquals(72.5, row.getLiteral("mean").double, 1e-9)
        assertEquals(6, row.getLiteral("count").int)
        assertEquals(50.0, row.getLiteral("row1").double, 1e-9)
        assertNull(Sparql.one(g.model, "SELECT (hxf:stat($samples, \"median\") AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:stat($samples, \"mean\", 0, 0, 0, 3) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:stat($samples, \"mean\", 0, 1) AS ?v) WHERE {}"))
    }

    @Test
    fun `stat on float cells keeps doubles`() {
        val p = Fixtures.planar(); HexplainFunctions.register(p.runtime)
        val row = Sparql.select(p.model, "SELECT (hxf:stat(<${p.node("root/Bands/0/Samples")}>, \"max\") AS ?max) (hxf:stat(<${p.node("root/Bands/0/Samples")}>, \"mean\") AS ?mean) WHERE {}").single()
        assertEquals(11.5, row.getLiteral("max").double, 1e-9)
        assertEquals(10.75, row.getLiteral("mean").double, 1e-9)
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.WindowAndStatTest"`
Expected: failures.

- [ ] **Step 3: Implement the property function**

`fn/WindowPropertyFunction.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.query.runtime.ArrayAccess
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.graph.Node
import org.apache.jena.sparql.core.Var
import org.apache.jena.sparql.engine.ExecutionContext
import org.apache.jena.sparql.engine.QueryIterator
import org.apache.jena.sparql.engine.binding.Binding
import org.apache.jena.sparql.engine.binding.BindingBuilder
import org.apache.jena.sparql.engine.iterator.QueryIterNullIterator
import org.apache.jena.sparql.engine.iterator.QueryIterPlainWrapper
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.pfunction.PropFuncArg
import org.apache.jena.sparql.pfunction.PropFuncArgType
import org.apache.jena.sparql.pfunction.PropertyFunctionEval

/**
 * `(?array lo1 hi1 ... lon hin) hxf:window (?i1 ... ?in ?v)`: every cell of a half-open window,
 * row-major. Object positions may be variables (bound per cell), already-bound variables
 * (joined) or constants (filtered). A window over the cap yields nothing and is explained.
 */
class WindowPropertyFunction(private val runtime: HexplainQueryRuntime) :
    PropertyFunctionEval(PropFuncArgType.PF_ARG_LIST, PropFuncArgType.PF_ARG_LIST) {

    override fun execEvaluated(binding: Binding, subject: PropFuncArg, predicate: Node, obj: PropFuncArg, execCxt: ExecutionContext): QueryIterator {
        val subj = subject.argList
        val objs = obj.argList
        val arrayNode = subj.firstOrNull()
        return try {
            if (arrayNode == null || !arrayNode.isURI) throw HexplainQueryException("hxf:window needs (<array> lo hi ...) as its subject list")
            val access = ArrayAccess.of(runtime.resolve(arrayNode.uri, execCxt.activeGraph))
            val rank = access.rank
            if (subj.size != 1 + 2 * rank) throw HexplainQueryException("hxf:window subject needs the array plus $rank (lo, hi) pairs, got ${subj.size - 1} values")
            if (objs.size != rank + 1) throw HexplainQueryException("hxf:window object needs $rank index positions and one value position, got ${objs.size}")
            val lo = IntArray(rank) { intOf(subj[1 + 2 * it]) }
            val hi = IntArray(rank) { intOf(subj[2 + 2 * it]) }
            val cells = access.window(lo, hi, runtime.limits.maxCellsPerWindow).mapNotNull { idx ->
                val b = Binding.builder(binding)
                var ok = true
                for (d in 0 until rank) ok = ok && bindOrMatch(b, objs[d], NodeValue.makeInteger(idx[d].toLong()).asNode())
                ok = ok && bindOrMatch(b, objs[rank], access.cell(idx).asNode())
                if (ok) b.build() else null
            }
            QueryIterPlainWrapper.create(cells.iterator(), execCxt)
        } catch (e: HexplainQueryException) {
            if (arrayNode != null && arrayNode.isURI) runtime.recordFailure(arrayNode.uri, e.message ?: "window failed")
            QueryIterNullIterator(execCxt)
        }
    }

    private fun intOf(node: Node): Int {
        if (Var.isVar(node)) throw HexplainQueryException("window bounds must be bound integers")
        val nv = NodeValue.makeNode(node)
        if (!nv.isInteger) throw HexplainQueryException("window bound $node is not an integer")
        return nv.integer.intValueExact()
    }

    private fun bindOrMatch(b: BindingBuilder, target: Node, value: Node): Boolean {
        if (!Var.isVar(target)) return target.sameValueAs(value)
        val v = Var.alloc(target)
        val existing = b.get(v)
        if (existing != null) return existing.sameValueAs(value)
        b.add(v, value)
        return true
    }
}
```

`StatFunction`, appended to `fn/ArrayFunctions.kt`:
```kotlin
/** hxf:stat(array, kind) / hxf:stat(array, kind, lo1, hi1, ...): min, max, sum, mean or count over a window. */
class StatFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2, 2 + 2 * CellFunction.MAX_RANK) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val access = ArrayAccess.of(node(args, 0, env))
        val kind = string(args, 1).lowercase()
        val rank = access.rank
        val lo: IntArray
        val hi: IntArray
        if (args.size == 2) {
            lo = IntArray(rank); hi = access.shape.toIntArray()
        } else {
            if (args.size != 2 + 2 * rank) throw HexplainQueryException("hxf:stat needs $rank (lo, hi) pairs after the kind, got ${args.size - 2} values")
            lo = IntArray(rank) { int(args, 2 + 2 * it) }
            hi = IntArray(rank) { int(args, 3 + 2 * it) }
        }
        val count = access.count(lo, hi)
        if (kind == "count") return NodeValue.makeInteger(count)
        if (kind !in setOf("min", "max", "sum", "mean")) throw HexplainQueryException("unknown statistic '$kind' (min, max, sum, mean, count)")
        if (count == 0L) throw HexplainQueryException("the window is empty")
        val cells = access.window(lo, hi, runtime.limits.maxCellsPerWindow)
        return if (access.data is io.hexplain.core.metacodec.MultiDimensionalData.IntData) {
            var min: java.math.BigInteger? = null; var max: java.math.BigInteger? = null; var sum = java.math.BigInteger.ZERO
            for (idx in cells) {
                val v = access.number(idx) as java.math.BigInteger
                if (min == null || v < min) min = v
                if (max == null || v > max) max = v
                sum += v
            }
            when (kind) {
                "min" -> NodeValue.makeInteger(min!!)
                "max" -> NodeValue.makeInteger(max!!)
                "sum" -> NodeValue.makeInteger(sum)
                else -> NodeValue.makeDouble(java.math.BigDecimal(sum).divide(java.math.BigDecimal(count), java.math.MathContext.DECIMAL64).toDouble())
            }
        } else {
            var min = Double.POSITIVE_INFINITY; var max = Double.NEGATIVE_INFINITY; var sum = 0.0
            for (idx in cells) {
                val v = access.number(idx).toDouble()
                if (v < min) min = v
                if (v > max) max = v
                sum += v
            }
            NodeValue.makeDouble(when (kind) { "min" -> min; "max" -> max; "sum" -> sum; else -> sum / count })
        }
    }
}
```

Add to `HexplainFunctions.register`:
```kotlin
        put(HXF.stat) { StatFunction(runtime) }
        propertyFunctions.put(HXF.window, PropertyFunctionFactory { WindowPropertyFunction(runtime) })
```
with `import org.apache.jena.sparql.pfunction.PropertyFunctionFactory`.

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.WindowAndStatTest"`
Expected: PASS (5 tests). If ARQ reports the object list as a single node rather than a list, check that the query writes the object as `( ... )` with spaces and that `PropFuncArgType.PF_ARG_LIST` is declared for both sides.

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/fn/WindowPropertyFunction.kt query/src/main/kotlin/io/hexplain/query/fn/ArrayFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/WindowAndStatTest.kt
git commit -m "feat(query): hxf:window property function and hxf:stat"
```

---
### Task 8: Raster layer — hxf:sampleAt, calibrate, isNoData, physicalAt

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/fn/GraphView.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/fn/RasterFunctions.kt`
- Modify: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/RasterFunctionsTest.kt`

**Interfaces:**
- Produces: `class GraphView(graph) { fun objects(s, p): List<Node>; fun subjects(p, o: Node): List<Node>; fun iri(s, p): String?; fun double(s, p): Double?; fun integer(s, p): Long?; companion fun of(env: FunctionEnv): GraphView; fun of(graph: Graph?): GraphView }`.
- Produces: `class RasterTarget(access, xDim, yDim, bandDim, bandPos) { fun indices(x, y): IntArray }`, `class RasterResolver(runtime) { fun resolve(gridIri, band: NodeValue?, view, graph): RasterTarget; fun bandIri(gridIri, band: NodeValue?, view): String? }`.
- Produces: `SampleAtFunction`, `CalibrateFunction`, `IsNoDataFunction`, `PhysicalAtFunction`.
- Resolution rule (design §3.4): array = band's `araster:hasArray`, else grid's `araster:hasArray`, else the single field of the grid struct holding a `MultiDimensionalData`. `x` → `dlv:axisX`, `y` → `dlv:axisY`. Band position along `dlv:axisBand` when the array has that axis (interleaved), otherwise the band's own array (planar). Every other dimension must have extent one.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fn

import io.hexplain.core.rdf.vocab.aspect.Raster
import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import org.apache.jena.rdf.model.ResourceFactory
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class RasterFunctionsTest {
    private val g = Fixtures.grid()
    private val grid = "<${g.node("root")}>"
    @BeforeEach fun install() = HexplainFunctions.register(g.runtime)

    @Test
    fun `sampleAt on a single-band grid needs no band argument`() {
        assertEquals(60, Sparql.one(g.model, "SELECT (hxf:sampleAt($grid, 2, 1) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(255, Sparql.one(g.model, "SELECT (hxf:sampleAt($grid, 2, 0) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(40, Sparql.one(g.model, "SELECT (hxf:sampleAt($grid, 0, 1, 1) AS ?v) WHERE {}")!!.asLiteral().int)
        assertNull(Sparql.one(g.model, "SELECT (hxf:sampleAt($grid, 3, 0) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:sampleAt($grid, 0, 0, 2) AS ?v) WHERE {}"))
    }

    @Test
    fun `sampleAt finds the array through the graph, by struct scan when no edge exists`() {
        val model = org.apache.jena.rdf.model.ModelFactory.createDefaultModel().add(g.model)
        model.removeAll(null, Raster.hasArray, null)
        assertEquals(50, Sparql.one(model, "SELECT (hxf:sampleAt($grid, 1, 1) AS ?v) WHERE {}")!!.asLiteral().int)
    }

    @Test
    fun `interleaved bands are addressed along the band axis by index or by band IRI`() {
        val i = Fixtures.interleaved(); HexplainFunctions.register(i.runtime)
        val gridRes = i.model.getResource(i.node("root"))
        val b1 = i.model.createResource("https://example.org/b1"); val b2 = i.model.createResource("https://example.org/b2")
        i.model.add(gridRes, Raster.hasBand, b1).add(gridRes, Raster.hasBand, b2)
        i.model.add(b1, Raster.bandIndex, i.model.createTypedLiteral(1)).add(b2, Raster.bandIndex, i.model.createTypedLiteral(2))
        val ig = "<${i.node("root")}>"
        assertEquals(112, Sparql.one(i.model, "SELECT (hxf:sampleAt($ig, 1, 1, 2) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(112, Sparql.one(i.model, "SELECT (hxf:sampleAt($ig, 1, 1, <https://example.org/b2>) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(101, Sparql.one(i.model, "SELECT (hxf:sampleAt($ig, 0, 1) AS ?v) WHERE {}")!!.asLiteral().int)
        assertNull(Sparql.one(i.model, "SELECT (hxf:sampleAt($ig, 0, 0, 3) AS ?v) WHERE {}"))
    }

    @Test
    fun `planar bands use their own arrays`() {
        val p = Fixtures.planar(); HexplainFunctions.register(p.runtime)
        val pg = "<${p.node("root")}>"
        assertEquals(20.5, Sparql.one(p.model, "SELECT (hxf:sampleAt($pg, 1, 0, 2) AS ?v) WHERE {}")!!.asLiteral().double, 0.0)
        assertEquals(10.0, Sparql.one(p.model, "SELECT (hxf:sampleAt($pg, 0, 0, <${p.node("root/Bands/0")}>) AS ?v) WHERE {}")!!.asLiteral().double, 0.0)
        assertEquals(11.5, Sparql.one(p.model, "SELECT ?v WHERE { $pg araster:hasBand ?b . ?b araster:bandIndex 1 . BIND(hxf:sampleAt($pg, 1, 1, ?b) AS ?v) }")!!.asLiteral().double, 0.0)
        assertNull(Sparql.one(p.model, "SELECT (hxf:sampleAt($pg, 0, 0, 3) AS ?v) WHERE {}"))
    }

    @Test
    fun `calibrate and isNoData read the band, falling back to the grid for no-data`() {
        val b = g.model.createResource("https://example.org/band")
        g.model.add(g.model.getResource(g.node("root")), Raster.hasBand, b)
        g.model.add(b, Raster.sampleScale, g.model.createTypedLiteral(0.5)).add(b, Raster.sampleOffset, g.model.createTypedLiteral(2))
        val row = Sparql.select(g.model, """
            SELECT (hxf:calibrate(ex:band, 10) AS ?c) (hxf:calibrate($grid, 10) AS ?identity)
                   (hxf:isNoData(ex:band, 255) AS ?nd) (hxf:isNoData(ex:band, 3) AS ?ok) (hxf:isNoData($grid, 255) AS ?gnd)
            WHERE {}
        """).single()
        assertEquals(7.0, row.getLiteral("c").double, 1e-12)
        assertEquals(10.0, row.getLiteral("identity").double, 1e-12)
        assertTrue(row.getLiteral("nd").boolean)
        assertFalse(row.getLiteral("ok").boolean)
        assertTrue(row.getLiteral("gnd").boolean)
    }

    @Test
    fun `physicalAt calibrates and is unbound on no-data`() {
        val gridRes = g.model.getResource(g.node("root"))
        g.model.add(gridRes, Raster.sampleScale, g.model.createTypedLiteral(0.5)).add(gridRes, Raster.sampleOffset, g.model.createTypedLiteral(1))
        assertEquals(6.0, Sparql.one(g.model, "SELECT (hxf:physicalAt($grid, 0, 0) AS ?v) WHERE {}")!!.asLiteral().double, 1e-12)
        assertEquals(31.0, Sparql.one(g.model, "SELECT (hxf:physicalAt($grid, 2, 1) AS ?v) WHERE {}")!!.asLiteral().double, 1e-12)
        assertNull(Sparql.one(g.model, "SELECT (hxf:physicalAt($grid, 2, 0) AS ?v) WHERE {}"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.RasterFunctionsTest"`
Expected: failures.

- [ ] **Step 3: Implement the graph helper**

`fn/GraphView.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.query.runtime.HexplainQueryException
import org.apache.jena.graph.Graph
import org.apache.jena.graph.Node
import org.apache.jena.graph.NodeFactory
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv

/** Small read helpers over the query's active graph, so functions read aspect triples the way a query would. */
class GraphView(private val graph: Graph) {
    fun objects(s: String, p: String): List<Node> =
        graph.find(NodeFactory.createURI(s), NodeFactory.createURI(p), Node.ANY).mapWith { it.`object` }.toList()

    fun subjects(p: String, o: Node): List<Node> =
        graph.find(Node.ANY, NodeFactory.createURI(p), o).mapWith { it.subject }.toList()

    fun iri(s: String, p: String): String? = objects(s, p).firstOrNull { it.isURI }?.uri

    fun literal(s: String, p: String): NodeValue? = objects(s, p).firstOrNull { it.isLiteral }?.let { NodeValue.makeNode(it) }

    fun double(s: String, p: String): Double? = literal(s, p)?.takeIf { it.isNumber }?.double

    fun integer(s: String, p: String): Long? = literal(s, p)?.takeIf { it.isInteger }?.integer?.longValueExact()

    companion object {
        fun of(env: FunctionEnv): GraphView = of(env.activeGraph)
        fun of(graph: Graph?): GraphView = GraphView(graph ?: throw HexplainQueryException("no active graph"))
    }
}
```

- [ ] **Step 4: Implement the raster functions**

`fn/RasterFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.core.rdf.vocab.DLV
import io.hexplain.core.rdf.vocab.aspect.Raster
import io.hexplain.query.runtime.ArrayAccess
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.graph.Graph
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv

/** A raster array with its x, y and band dimensions located. */
class RasterTarget(val access: ArrayAccess, val xDim: Int, val yDim: Int, val bandDim: Int?, val bandPos: Int?) {
    fun indices(x: Int, y: Int): IntArray = IntArray(access.rank) { d ->
        when (d) {
            xDim -> x
            yDim -> y
            bandDim -> bandPos ?: 0
            else -> {
                if (access.shape[d] != 1) throw HexplainQueryException("dimension ${access.axes[d].substringAfter('#')} has extent ${access.shape[d]} and no coordinate was given")
                0
            }
        }
    }
}

/** Finds a grid's sample array and band position from the aspect triples, per design §3.4. */
class RasterResolver(private val runtime: HexplainQueryRuntime) {

    /** The band node for [band] (an IRI or a one-based index), or null when none is named or found. */
    fun bandIri(gridIri: String, band: NodeValue?, view: GraphView): String? = when {
        band == null -> null
        band.isIRI -> band.asNode().uri
        band.isInteger -> {
            val n = band.integer.longValueExact()
            view.objects(gridIri, Raster.hasBand.uri).firstOrNull { it.isURI && view.integer(it.uri, Raster.bandIndex.uri) == n }?.uri
        }
        else -> throw HexplainQueryException("a band is a RasterBand IRI or a one-based index, got $band")
    }

    fun resolve(gridIri: String, band: NodeValue?, view: GraphView, graph: Graph?): RasterTarget {
        val bandIri = bandIri(gridIri, band, view)
        val bandIndex: Int? = when {
            band == null -> null
            band.isInteger -> band.integer.intValueExact()
            else -> bandIri?.let { view.integer(it, Raster.bandIndex.uri)?.toInt() }
        }
        val fromBand = bandIri?.let { view.iri(it, Raster.hasArray.uri) }
        val arrayIri = fromBand ?: view.iri(gridIri, Raster.hasArray.uri) ?: scan(gridIri, graph)
        val access = ArrayAccess.of(runtime.resolve(arrayIri, graph))
        val xDim = access.dimensionOf(DLV.axisX.uri)
        val yDim = access.dimensionOf(DLV.axisY.uri)
        val bandDim = access.axes.indexOf(DLV.axisBand.uri).takeIf { it >= 0 }
        val bandPos = when {
            bandDim != null -> {
                val pos = (bandIndex ?: 1) - 1
                if (pos !in 0 until access.shape[bandDim]) throw HexplainQueryException("band ${pos + 1} is outside the array's ${access.shape[bandDim]} bands")
                pos
            }
            fromBand == null && bandIndex != null && bandIndex != 1 && bandIri == null ->
                throw HexplainQueryException("band $bandIndex: the grid has no such araster:RasterBand and its array has no band axis")
            else -> null
        }
        return RasterTarget(access, xDim, yDim, bandDim, bandPos)
    }

    private fun scan(gridIri: String, graph: Graph?): String {
        val node = runtime.resolve(gridIri, graph)
        val arrays = node.struct.filterValues { it is MultiDimensionalData }.keys
        return when (arrays.size) {
            1 -> "$gridIri/${arrays.single()}"
            0 -> throw HexplainQueryException("<$gridIri> has no araster:hasArray edge and no array field")
            else -> throw HexplainQueryException("<$gridIri> has several array fields ($arrays); add araster:hasArray to the profile")
        }
    }
}

/** hxf:sampleAt(grid, x, y, band?) */
class SampleAtFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3, 4) {
    private val resolver = RasterResolver(runtime)
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val target = resolver.resolve(iri(args, 0), args.getOrNull(3), GraphView.of(env), env.activeGraph)
        return target.access.cell(target.indices(int(args, 1), int(args, 2)))
    }
}

/** Calibration terms read from a band (or grid) node. Pure: only graph values. */
internal object Calibration {
    fun apply(view: GraphView, subject: String, raw: Double): Double {
        val scale = view.double(subject, Raster.sampleScale.uri) ?: 1.0
        val offset = view.double(subject, Raster.sampleOffset.uri) ?: 0.0
        return raw * scale + offset
    }

    fun isNoData(view: GraphView, subject: String, value: Double): Boolean {
        val own = view.literal(subject, Raster.noDataValue.uri)
        val nd = own ?: view.subjects(Raster.hasBand.uri, org.apache.jena.graph.NodeFactory.createURI(subject))
            .firstOrNull { it.isURI }?.let { view.literal(it.uri, Raster.noDataValue.uri) }
            ?: return false
        val ndValue = if (nd.isNumber) nd.double else nd.asNode().literalLexicalForm.toDoubleOrNull() ?: return false
        return ndValue == value
    }
}

/** hxf:calibrate(band, raw) — pure; also declared as sh:SPARQLFunction in fn.ttl. */
class CalibrateFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeDouble(Calibration.apply(GraphView.of(env), iri(args, 0), double(args, 1)))
}

/** hxf:isNoData(band, value) — pure; also declared as sh:SPARQLFunction in fn.ttl. */
class IsNoDataFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeBoolean(Calibration.isNoData(GraphView.of(env), iri(args, 0), double(args, 1)))
}

/** hxf:physicalAt(grid, x, y, band?): calibrated sample, unbound on no-data. */
class PhysicalAtFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3, 4) {
    private val resolver = RasterResolver(runtime)
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val view = GraphView.of(env)
        val gridIri = iri(args, 0)
        val target = resolver.resolve(gridIri, args.getOrNull(3), view, env.activeGraph)
        val raw = target.access.cell(target.indices(int(args, 1), int(args, 2)))
        if (!raw.isNumber) throw HexplainQueryException("physical values need numeric samples")
        val subject = resolver.bandIri(gridIri, args.getOrNull(3), view)
            ?: view.objects(gridIri, Raster.hasBand.uri).singleOrNull { it.isURI }?.uri
            ?: gridIri
        if (Calibration.isNoData(view, subject, raw.double)) throw HexplainQueryException("no-data at ($args)")
        return NodeValue.makeDouble(Calibration.apply(view, subject, raw.double))
    }
}
```

Add to `HexplainFunctions.register`:
```kotlin
        // Layer 3: raster
        put(HXF.sampleAt) { SampleAtFunction(runtime) }
        put(HXF.calibrate) { CalibrateFunction(runtime) }
        put(HXF.isNoData) { IsNoDataFunction(runtime) }
        put(HXF.physicalAt) { PhysicalAtFunction(runtime) }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.RasterFunctionsTest"`
Expected: PASS (6 tests). Watch the planar case `hxf:sampleAt(grid, 0, 0, 3)`: band 3 has no node and no band axis, so `resolve` must throw (the `fromBand == null && bandIndex != 1` arm).

- [ ] **Step 6: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/fn/GraphView.kt query/src/main/kotlin/io/hexplain/query/fn/RasterFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/RasterFunctionsTest.kt
git commit -m "feat(query): raster layer — hxf:sampleAt, calibrate, isNoData, physicalAt"
```

---

### Task 9: Spatial reference layer — hxf:worldX, worldY, column, row, sampleAtWorld

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/fn/SpatialRefFunctions.kt`
- Modify: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/SpatialRefFunctionsTest.kt`

**Interfaces:**
- Produces: `data class Affine(ox, oy, sx, sy, kx, ky, center: Boolean) { fun worldX(col, row): Double; fun worldY(col, row): Double; fun column(wx, wy): Long; fun row(wx, wy): Long; companion fun read(view, transformIri): Affine }`.
- Semantics: `worldX = ox + col*sx + row*kx`, `worldY = oy + col*ky + row*sy`. Inverse with `det = sx*sy - kx*ky`: `c = (sy*(wx-ox) - kx*(wy-oy))/det`, `r = (-ky*(wx-ox) + sx*(wy-oy))/det`; `column = floor(c)` for `asref:PixelCorner` (default), `floor(c + 0.5)` for `asref:PixelCenter`; same for `row`. Missing `skewX`/`skewY` read as 0.
- Produces: `WorldXFunction`, `WorldYFunction`, `ColumnFunction`, `RowFunction`, `SampleAtWorldFunction` (`dataset` must carry `asref:hasGeoTransform` and be resolvable as a grid).

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fn

import io.hexplain.core.rdf.vocab.aspect.SpatialRef
import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test

class SpatialRefFunctionsTest {
    private val g = Fixtures.grid()
    private val grid = "<${g.node("root")}>"

    @BeforeEach
    fun install() {
        HexplainFunctions.register(g.runtime)
        val m = g.model
        val t1 = m.createResource("https://example.org/t1")
        m.add(t1, SpatialRef.originX, m.createTypedLiteral(100.0)).add(t1, SpatialRef.originY, m.createTypedLiteral(200.0))
        m.add(t1, SpatialRef.scaleX, m.createTypedLiteral(2.0)).add(t1, SpatialRef.scaleY, m.createTypedLiteral(-2.0))
        val t2 = m.createResource("https://example.org/t2")
        m.add(t2, SpatialRef.originX, m.createTypedLiteral(100.0)).add(t2, SpatialRef.originY, m.createTypedLiteral(200.0))
        m.add(t2, SpatialRef.scaleX, m.createTypedLiteral(2.0)).add(t2, SpatialRef.scaleY, m.createTypedLiteral(-2.0))
        m.add(t2, SpatialRef.skewX, m.createTypedLiteral(1.0)).add(t2, SpatialRef.skewY, m.createTypedLiteral(-1.0))
        m.add(t2, SpatialRef.pixelRegistration, SpatialRef.PixelCenter)
        m.add(m.getResource(g.node("root")), SpatialRef.hasGeoTransform, t1)
    }

    @Test
    fun `forward transform with and without skew`() {
        val row = Sparql.select(g.model, "SELECT (hxf:worldX(ex:t1, 1, 0) AS ?x1) (hxf:worldY(ex:t1, 0, 1) AS ?y1) (hxf:worldX(ex:t2, 1, 1) AS ?x2) (hxf:worldY(ex:t2, 1, 1) AS ?y2) WHERE {}").single()
        assertEquals(102.0, row.getLiteral("x1").double, 1e-12)
        assertEquals(198.0, row.getLiteral("y1").double, 1e-12)
        assertEquals(103.0, row.getLiteral("x2").double, 1e-12)
        assertEquals(197.0, row.getLiteral("y2").double, 1e-12)
    }

    @Test
    fun `inverse transform truncates to the containing cell, or rounds to the nearest centre`() {
        val row = Sparql.select(g.model, "SELECT (hxf:column(ex:t1, 103.9, 197.0) AS ?c1) (hxf:row(ex:t1, 103.9, 197.0) AS ?r1) (hxf:column(ex:t2, 103.9, 197.0) AS ?c2) (hxf:row(ex:t2, 103.9, 197.0) AS ?r2) WHERE {}").single()
        assertEquals(1, row.getLiteral("c1").int)
        assertEquals(1, row.getLiteral("r1").int)
        assertEquals(2, row.getLiteral("c2").int)   // c = 1.6 → floor(2.1)
        assertEquals(1, row.getLiteral("r2").int)   // r = 0.7 → floor(1.2)
        assertEquals("http://www.w3.org/2001/XMLSchema#integer", row.getLiteral("c1").datatypeURI)
    }

    @Test
    fun `a transform missing its origin, or a singular one, is unbound`() {
        val m = g.model
        val bad = m.createResource("https://example.org/bad")
        m.add(bad, SpatialRef.scaleX, m.createTypedLiteral(1.0)).add(bad, SpatialRef.scaleY, m.createTypedLiteral(1.0))
        assertNull(Sparql.one(m, "SELECT (hxf:worldX(ex:bad, 0, 0) AS ?v) WHERE {}"))
        val flat = m.createResource("https://example.org/flat")
        m.add(flat, SpatialRef.originX, m.createTypedLiteral(0.0)).add(flat, SpatialRef.originY, m.createTypedLiteral(0.0))
        m.add(flat, SpatialRef.scaleX, m.createTypedLiteral(0.0)).add(flat, SpatialRef.scaleY, m.createTypedLiteral(1.0))
        assertNull(Sparql.one(m, "SELECT (hxf:column(ex:flat, 1, 1) AS ?v) WHERE {}"))
    }

    @Test
    fun `sampleAtWorld goes through the dataset's geotransform to the cell`() {
        assertEquals(60, Sparql.one(g.model, "SELECT (hxf:sampleAtWorld($grid, 104.5, 197.5) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(10, Sparql.one(g.model, "SELECT (hxf:sampleAtWorld($grid, 100.0, 200.0, 1) AS ?v) WHERE {}")!!.asLiteral().int)
        assertNull(Sparql.one(g.model, "SELECT (hxf:sampleAtWorld($grid, 99.0, 200.0) AS ?v) WHERE {}"))
        assertNull(Sparql.one(g.model, "SELECT (hxf:sampleAtWorld(ex:t1, 100.0, 200.0) AS ?v) WHERE {}"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.SpatialRefFunctionsTest"`
Expected: failures.

- [ ] **Step 3: Implement**

`fn/SpatialRefFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.rdf.vocab.aspect.SpatialRef
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv
import kotlin.math.floor

/** An affine asref:GeoTransform. Pure arithmetic; the SHACL-AF bodies in fn.ttl compute the same. */
data class Affine(val ox: Double, val oy: Double, val sx: Double, val sy: Double, val kx: Double, val ky: Double, val center: Boolean) {
    fun worldX(col: Double, row: Double): Double = ox + col * sx + row * kx
    fun worldY(col: Double, row: Double): Double = oy + col * ky + row * sy

    private fun det(): Double {
        val d = sx * sy - kx * ky
        if (d == 0.0 || d.isNaN()) throw HexplainQueryException("the geotransform is singular")
        return d
    }
    private fun snap(v: Double): Long = floor(if (center) v + 0.5 else v).toLong()

    fun column(wx: Double, wy: Double): Long = snap((sy * (wx - ox) - kx * (wy - oy)) / det())
    fun row(wx: Double, wy: Double): Long = snap((-ky * (wx - ox) + sx * (wy - oy)) / det())

    companion object {
        fun read(view: GraphView, transform: String): Affine {
            fun need(p: org.apache.jena.rdf.model.Property) = view.double(transform, p.uri)
                ?: throw HexplainQueryException("<$transform> has no ${p.localName}")
            return Affine(
                ox = need(SpatialRef.originX), oy = need(SpatialRef.originY),
                sx = need(SpatialRef.scaleX), sy = need(SpatialRef.scaleY),
                kx = view.double(transform, SpatialRef.skewX.uri) ?: 0.0,
                ky = view.double(transform, SpatialRef.skewY.uri) ?: 0.0,
                center = view.iri(transform, SpatialRef.pixelRegistration.uri) == SpatialRef.PixelCenter.uri
            )
        }
    }
}

class WorldXFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeDouble(Affine.read(GraphView.of(env), iri(args, 0)).worldX(double(args, 1), double(args, 2)))
}

class WorldYFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeDouble(Affine.read(GraphView.of(env), iri(args, 0)).worldY(double(args, 1), double(args, 2)))
}

class ColumnFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeInteger(Affine.read(GraphView.of(env), iri(args, 0)).column(double(args, 1), double(args, 2)))
}

class RowFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue =
        NodeValue.makeInteger(Affine.read(GraphView.of(env), iri(args, 0)).row(double(args, 1), double(args, 2)))
}

/** hxf:sampleAtWorld(dataset, wx, wy, band?): the sample under a world point via the dataset's asref:hasGeoTransform. */
class SampleAtWorldFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 3, 4) {
    private val resolver = RasterResolver(runtime)
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val view = GraphView.of(env)
        val dataset = iri(args, 0)
        val transform = view.iri(dataset, SpatialRef.hasGeoTransform.uri)
            ?: throw HexplainQueryException("<$dataset> has no asref:hasGeoTransform")
        val affine = Affine.read(view, transform)
        val wx = double(args, 1); val wy = double(args, 2)
        val col = affine.column(wx, wy); val row = affine.row(wx, wy)
        if (col < 0 || row < 0) throw HexplainQueryException("($wx, $wy) lies before the grid origin (column $col, row $row)")
        val target = resolver.resolve(dataset, args.getOrNull(3), view, env.activeGraph)
        return target.access.cell(target.indices(col.toInt(), row.toInt()))
    }
}
```

Add to `HexplainFunctions.register`:
```kotlin
        // Layer 3: spatial reference
        put(HXF.worldX) { WorldXFunction(runtime) }
        put(HXF.worldY) { WorldYFunction(runtime) }
        put(HXF.column) { ColumnFunction(runtime) }
        put(HXF.row) { RowFunction(runtime) }
        put(HXF.sampleAtWorld) { SampleAtWorldFunction(runtime) }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.SpatialRefFunctionsTest"`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/fn/SpatialRefFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/SpatialRefFunctionsTest.kt
git commit -m "feat(query): spatial reference layer — affine world/grid functions and hxf:sampleAtWorld"
```

---
### Task 10: Geometry and signal — hxf:wkt, hxf:sampleAtTime

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/fn/GeometryFunctions.kt`
- Create: `query/src/main/kotlin/io/hexplain/query/fn/SignalFunctions.kt`
- Modify: `query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/fn/GeometryAndSignalTest.kt`

**Interfaces:**
- Produces: `object WktWriter { fun write(g: GeometryValue): String }`, `WktFunction` (phase 1 reads WKB and GeoPackage blobs through the core `GeometryDecoder`; the CRS comes from the GeoPackage header, else from `asref:hasCRS/asref:epsgCode` on the node or any ancestor path), `SampleAtTimeFunction(signal, seconds, channel?)`.
- WKT rules: type names POINT, LINESTRING, POLYGON, MULTIPOINT, MULTILINESTRING, MULTIPOLYGON, GEOMETRYCOLLECTION; dimension suffix ` Z`, ` M`, ` ZM`; `EMPTY` for empty geometries; numbers rendered with `BigDecimal.valueOf(v).stripTrailingZeros().toPlainString()`; a CRS prefixes the literal as `<http://www.opengis.net/def/crs/EPSG/0/{code}> `.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fn

import io.hexplain.core.rdf.vocab.aspect.SpatialRef
import io.hexplain.query.Fixtures
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.Sparql
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class GeometryAndSignalTest {
    private fun point(x: Double, y: Double): ByteArray =
        ByteBuffer.allocate(21).order(ByteOrder.LITTLE_ENDIAN).put(1).putInt(1).putDouble(x).putDouble(y).array()

    private fun square(): ByteArray {
        val b = ByteBuffer.allocate(1 + 4 + 4 + 4 + 5 * 16).order(ByteOrder.LITTLE_ENDIAN)
        b.put(1).putInt(3).putInt(1).putInt(5)
        for ((x, y) in listOf(0.0 to 0.0, 4.0 to 0.0, 4.0 to 4.0, 0.0 to 4.0, 0.0 to 0.0)) { b.putDouble(x); b.putDouble(y) }
        return b.array()
    }

    @Test
    fun `wkt renders a WKB point and polygon as a geosparql literal`() {
        val f = Fixtures.geometry(point(-2.5, 8.0)); HexplainFunctions.register(f.runtime)
        val lit = Sparql.one(f.model, "SELECT (hxf:wkt(<${f.node("root/Geom")}>) AS ?v) WHERE {}")!!.asLiteral()
        assertEquals("POINT (-2.5 8)", lit.lexicalForm)
        assertEquals("http://www.opengis.net/ont/geosparql#wktLiteral", lit.datatypeURI)
        val p = Fixtures.geometry(square()); HexplainFunctions.register(p.runtime)
        assertEquals("POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0))", Sparql.one(p.model, "SELECT (hxf:wkt(<${p.node("root/Geom")}>) AS ?v) WHERE {}")!!.asLiteral().lexicalForm)
    }

    @Test
    fun `the CRS comes from an ancestor's asref hasCRS`() {
        val f = Fixtures.geometry(point(1.0, 2.0)); HexplainFunctions.register(f.runtime)
        val crs = f.model.createResource("https://example.org/crs")
        f.model.add(f.model.getResource(f.node("root")), SpatialRef.hasCRS, crs).add(crs, SpatialRef.epsgCode, f.model.createTypedLiteral(4326))
        assertEquals("<http://www.opengis.net/def/crs/EPSG/0/4326> POINT (1 2)", Sparql.one(f.model, "SELECT (hxf:wkt(<${f.node("root/Geom")}>) AS ?v) WHERE {}")!!.asLiteral().lexicalForm)
    }

    @Test
    fun `a GeoPackage blob carries its own SRS`() {
        val header = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN).put("GP".toByteArray()).put(0).put(1).putInt(3857).array()
        val f = Fixtures.geometry(header + point(10.0, 20.0)); HexplainFunctions.register(f.runtime)
        assertEquals("<http://www.opengis.net/def/crs/EPSG/0/3857> POINT (10 20)", Sparql.one(f.model, "SELECT (hxf:wkt(<${f.node("root/Geom")}>) AS ?v) WHERE {}")!!.asLiteral().lexicalForm)
    }

    @Test
    fun `garbage bytes are unbound`() {
        val f = Fixtures.geometry(byteArrayOf(9, 9, 9)); HexplainFunctions.register(f.runtime)
        assertNull(Sparql.one(f.model, "SELECT (hxf:wkt(<${f.node("root/Geom")}>) AS ?v) WHERE {}"))
    }

    @Test
    fun `sampleAtTime rounds seconds to a sample instant and picks the channel`() {
        val s = Fixtures.pcm(); HexplainFunctions.register(s.runtime)
        val sig = "<${s.node("root")}>"
        assertEquals(2002, Sparql.one(s.model, "SELECT (hxf:sampleAtTime($sig, 0.5, 2) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(1, Sparql.one(s.model, "SELECT (hxf:sampleAtTime($sig, 0.0) AS ?v) WHERE {}")!!.asLiteral().int)
        assertEquals(3001, Sparql.one(s.model, "SELECT (hxf:sampleAtTime($sig, 0.74) AS ?v) WHERE {}")!!.asLiteral().int)
        assertNull(Sparql.one(s.model, "SELECT (hxf:sampleAtTime($sig, 2.0) AS ?v) WHERE {}"))
        assertNull(Sparql.one(s.model, "SELECT (hxf:sampleAtTime($sig, 0.0, 3) AS ?v) WHERE {}"))
    }
}
```
(`0.74 * 4 = 2.96` rounds to instant 3, channel 1 → `3001`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.GeometryAndSignalTest"`
Expected: failures.

- [ ] **Step 3: Implement geometry**

`fn/GeometryFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.codec.PreservedEncodedBytes
import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.core.raster.GeometryDecoder
import io.hexplain.core.raster.GeometryValue
import io.hexplain.core.rdf.vocab.aspect.SpatialRef
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import io.hexplain.query.runtime.NodeRef
import io.hexplain.query.runtime.ResolvedNode
import org.apache.jena.datatypes.TypeMapper
import org.apache.jena.graph.NodeFactory
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv
import java.math.BigDecimal

/** Renders the core decoder's geometry tree as WKT. */
object WktWriter {
    private val names = mapOf(1 to "POINT", 2 to "LINESTRING", 3 to "POLYGON", 4 to "MULTIPOINT", 5 to "MULTILINESTRING", 6 to "MULTIPOLYGON", 7 to "GEOMETRYCOLLECTION")

    fun write(g: GeometryValue): String {
        val tag = names[g.type] ?: throw HexplainQueryException("unsupported geometry type ${g.type}")
        val dim = when (g.dimensions) { "XYZ" -> " Z"; "XYM" -> " M"; "XYZM" -> " ZM"; else -> "" }
        return if (g.empty) "$tag$dim EMPTY" else "$tag$dim ${body(g)}"
    }

    private fun body(g: GeometryValue): String = when (g.type) {
        1 -> "(" + coords(g.coordinates.single()) + ")"
        2 -> "(" + g.coordinates.joinToString(", ") { coords(it) } + ")"
        3 -> "(" + g.children.joinToString(", ") { body(it) } + ")"
        4, 5, 6 -> "(" + g.children.joinToString(", ") { if (it.empty) "EMPTY" else body(it) } + ")"
        7 -> "(" + g.children.joinToString(", ") { write(it) } + ")"
        else -> throw HexplainQueryException("unsupported geometry type ${g.type}")
    }

    private fun coords(p: List<Double>) = p.joinToString(" ") { BigDecimal.valueOf(it).stripTrailingZeros().toPlainString() }
}

/** hxf:wkt(node): a geo:wktLiteral from a WKB or GeoPackage payload, with the CRS when one is known. */
class WktFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 1) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val node = node(args, 0, env)
        val bytes = payload(node)
        val decoder = GeometryDecoder()
        val (geometry, srs) = try {
            if (bytes.size > 2 && bytes[0] == 'G'.code.toByte() && bytes[1] == 'P'.code.toByte()) {
                val gp = decoder.geoPackage(bytes); gp.geometry to gp.srsId.takeIf { it > 0 }
            } else decoder.wkb(bytes) to null
        } catch (e: RuntimeException) {
            throw HexplainQueryException("not a WKB or GeoPackage geometry: ${e.message}", e)
        }
        val epsg = srs ?: epsgFromGraph(node, GraphView.of(env))
        val lex = (epsg?.let { "<http://www.opengis.net/def/crs/EPSG/0/$it> " } ?: "") + WktWriter.write(geometry)
        return NodeValue.makeNode(NodeFactory.createLiteralDT(lex, TypeMapper.getInstance().getSafeTypeByName(WKT)))
    }

    private fun payload(node: ResolvedNode): ByteArray = when (val v = node.value) {
        is ByteArray -> v
        is PreservedEncodedBytes -> v.decoded
        is MultiDimensionalData -> v.data
        else -> node.rawBytes()
    }

    /** asref:hasCRS/asref:epsgCode on the node or the nearest ancestor path that has one. */
    private fun epsgFromGraph(node: ResolvedNode, view: GraphView): Long? {
        var path = node.ref.path
        while (true) {
            val subject = "${node.ref.assetIri}#$path"
            view.iri(subject, SpatialRef.hasCRS.uri)?.let { crs -> view.integer(crs, SpatialRef.epsgCode.uri)?.let { return it } }
            if (!path.contains('/')) return null
            path = path.substringBeforeLast('/')
        }
    }

    private companion object { const val WKT = "http://www.opengis.net/ont/geosparql#wktLiteral" }
}
```

- [ ] **Step 4: Implement signal**

`fn/SignalFunctions.kt`:
```kotlin
package io.hexplain.query.fn

import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.core.rdf.vocab.DLV
import io.hexplain.core.rdf.vocab.aspect.Raster
import io.hexplain.core.rdf.vocab.aspect.Signal
import io.hexplain.query.runtime.ArrayAccess
import io.hexplain.query.runtime.HexplainQueryException
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.sparql.expr.NodeValue
import org.apache.jena.sparql.function.FunctionEnv
import kotlin.math.roundToLong

/** hxf:sampleAtTime(signal, seconds, channel?): the cell at round(seconds * asig:sampleRate) along dlv:axisTime. */
class SampleAtTimeFunction(runtime: HexplainQueryRuntime) : HexplainFunction(runtime, 2, 3) {
    override fun exec(args: List<NodeValue>, env: FunctionEnv): NodeValue {
        val view = GraphView.of(env)
        val signal = iri(args, 0)
        val rate = view.double(signal, Signal.sampleRate.uri) ?: throw HexplainQueryException("<$signal> has no asig:sampleRate")
        val arrayIri = view.iri(signal, Raster.hasArray.uri) ?: run {
            val fields = runtime.resolve(signal, env.activeGraph).struct.filterValues { it is MultiDimensionalData }.keys
            if (fields.size != 1) throw HexplainQueryException("<$signal> has no araster:hasArray edge and ${fields.size} array fields")
            "$signal/${fields.single()}"
        }
        val access = ArrayAccess.of(runtime.resolve(arrayIri, env.activeGraph))
        val tDim = access.dimensionOf(DLV.axisTime.uri)
        val instant = (double(args, 1) * rate).roundToLong()
        if (instant < 0 || instant >= access.shape[tDim]) throw HexplainQueryException("instant $instant is outside the ${access.shape[tDim]} samples")
        val channel = if (args.size == 3) int(args, 2) else 1
        val cDim = access.axes.indexOf(DLV.axisBand.uri).takeIf { it >= 0 }
        if (cDim == null && channel != 1) throw HexplainQueryException("the signal has no channel axis")
        val indices = IntArray(access.rank) { d ->
            when (d) {
                tDim -> instant.toInt()
                cDim -> channel - 1
                else -> { if (access.shape[d] != 1) throw HexplainQueryException("dimension ${access.axes[d].substringAfter('#')} has extent ${access.shape[d]}"); 0 }
            }
        }
        return access.cell(indices)
    }
}
```

Add to `HexplainFunctions.register`:
```kotlin
        // Layer 3: geometry and signal
        put(HXF.wkt) { WktFunction(runtime) }
        put(HXF.sampleAtTime) { SampleAtTimeFunction(runtime) }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.fn.GeometryAndSignalTest"`
Expected: PASS (5 tests). If the GeoPackage header needs an envelope flag other than 1 for a header with no envelope, set the flags byte to `0x01` (little-endian, no envelope, per the GeoPackage spec) — the core `geoPackage()` test in `ExtendedDecoderTest` uses `put(3)` with an envelope; mirror that layout if the no-envelope form is rejected.

- [ ] **Step 6: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/fn/GeometryFunctions.kt query/src/main/kotlin/io/hexplain/query/fn/SignalFunctions.kt query/src/main/kotlin/io/hexplain/query/HexplainFunctions.kt query/src/test/kotlin/io/hexplain/query/fn/GeometryAndSignalTest.kt
git commit -m "feat(query): hxf:wkt over WKB/GeoPackage payloads and hxf:sampleAtTime"
```

---

### Task 11: fn.ttl — function declarations and pure bodies, with the agreement test

**Files:**
- Create: `query/src/main/resources/hxf/fn.ttl`
- Test: `query/src/test/kotlin/io/hexplain/query/PureFunctionAgreementTest.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/FunctionCatalogueTest.kt`

**Interfaces:**
- Produces: `fn.ttl` declaring one `hxf:Function` per IRI in `HXF` with `hxf:kind hxf:Pure|hxf:Native`, `hxf:signature`, `rdfs:comment`, `hxf:reads` (aspect terms); pure ones also `a sh:SPARQLFunction` with `sh:parameter` (paths `hxf:arg1`...) and `sh:select` binding `?result`.
- The same file is copied verbatim into the spec repo in Task 15.

- [ ] **Step 1: Write the failing tests**

`FunctionCatalogueTest.kt` (every registered IRI is declared, and vice versa):
```kotlin
package io.hexplain.query

import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class FunctionCatalogueTest {
    @Test
    fun `fn ttl declares exactly the functions the code registers`() {
        val model = ModelFactory.createDefaultModel()
        RDFDataMgr.read(model, javaClass.getResourceAsStream("/hxf/fn.ttl")!!, Lang.TTL)
        val declared = model.listSubjectsWithProperty(RDF.type, model.getResource(HXF.iri("Function"))).mapWith { it.uri }.toSet()
        val coded = listOf(
            HXF.bytes, HXF.decodedBytes, HXF.digest, HXF.value, HXF.hel, HXF.decode, HXF.rank, HXF.extent, HXF.cell, HXF.stat,
            HXF.window, HXF.layout, HXF.sampleAt, HXF.calibrate, HXF.isNoData, HXF.physicalAt, HXF.worldX, HXF.worldY, HXF.column,
            HXF.row, HXF.sampleAtWorld, HXF.wkt, HXF.sampleAtTime, HXF.explain
        ).toSet()
        assertEquals(coded, declared)
    }
}
```

`PureFunctionAgreementTest.kt`:
```kotlin
package io.hexplain.query

import io.hexplain.core.rdf.vocab.aspect.Raster
import io.hexplain.core.rdf.vocab.aspect.SpatialRef
import org.apache.jena.query.QueryExecution
import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.rdf.model.RDFNode
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.apache.jena.shacl.vocabulary.SHACL
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

/** Every sh:SPARQLFunction body in fn.ttl and its Kotlin twin must agree on the same inputs. */
class PureFunctionAgreementTest {
    private val fn: Model = ModelFactory.createDefaultModel().also { RDFDataMgr.read(it, javaClass.getResourceAsStream("/hxf/fn.ttl")!!, Lang.TTL) }
    private val data: Model = ModelFactory.createDefaultModel().also { m ->
        val b1 = m.createResource("https://example.org/b1"); val b2 = m.createResource("https://example.org/b2"); val g = m.createResource("https://example.org/g")
        m.add(b1, Raster.sampleScale, m.createTypedLiteral(0.5)).add(b1, Raster.sampleOffset, m.createTypedLiteral(2))
        m.add(g, Raster.hasBand, b2).add(g, Raster.noDataValue, m.createTypedLiteral(255))
        val t1 = m.createResource("https://example.org/t1"); val t2 = m.createResource("https://example.org/t2")
        for (t in listOf(t1, t2)) {
            m.add(t, SpatialRef.originX, m.createTypedLiteral(100.0)).add(t, SpatialRef.originY, m.createTypedLiteral(200.0))
            m.add(t, SpatialRef.scaleX, m.createTypedLiteral(2.0)).add(t, SpatialRef.scaleY, m.createTypedLiteral(-2.0))
        }
        m.add(t2, SpatialRef.skewX, m.createTypedLiteral(1.0)).add(t2, SpatialRef.skewY, m.createTypedLiteral(-1.0)).add(t2, SpatialRef.pixelRegistration, SpatialRef.PixelCenter)
    }

    /** function local name -> argument lists, written as SPARQL terms. */
    private val cases = mapOf(
        "calibrate" to listOf(listOf("ex:b1", "10"), listOf("ex:b2", "10"), listOf("ex:b1", "-3.5")),
        "isNoData" to listOf(listOf("ex:b2", "255"), listOf("ex:b2", "3"), listOf("ex:b1", "255")),
        "worldX" to listOf(listOf("ex:t1", "1", "0"), listOf("ex:t2", "1", "1"), listOf("ex:t2", "0.5", "2")),
        "worldY" to listOf(listOf("ex:t1", "0", "1"), listOf("ex:t2", "1", "1")),
        "column" to listOf(listOf("ex:t1", "103.9", "197.0"), listOf("ex:t2", "103.9", "197.0"), listOf("ex:t1", "100.0", "200.0")),
        "row" to listOf(listOf("ex:t1", "103.9", "197.0"), listOf("ex:t2", "103.9", "197.0"))
    )

    @Test
    fun `every SHACL-AF body agrees with its native implementation`() {
        HexplainFunctions.register(Fixtures.grid().runtime)
        val pure = fn.listSubjectsWithProperty(RDF.type, SHACL.SPARQLFunction).toList()
        assertTrue(pure.isNotEmpty())
        for (f in pure) {
            val local = f.uri.substringAfter('#')
            val body = f.getProperty(SHACL.select).string
            val params = f.listProperties(SHACL.parameter).mapWith { it.`object`.asResource() }.toList()
                .sortedBy { it.getProperty(SHACL.order).int }
                .map { it.getProperty(SHACL.path).`object`.asResource().uri.substringAfter('#') }
            val argSets = cases[local] ?: fail("no agreement cases for hxf:$local")
            for (args in argSets) {
                assertEquals(params.size, args.size, "arity of hxf:$local")
                val bindings = params.indices.joinToString(" ") { "BIND(${args[it]} AS ?${params[it]})" }
                val shacl = Sparql.select(data, body.replace("SELECT ?result WHERE {", "SELECT ?result WHERE { $bindings").replace("\$", "?")).single().get("result")
                val native = Sparql.select(data, "SELECT (hxf:$local(${args.joinToString(", ")}) AS ?result) WHERE {}").single().get("result")
                assertSame(shacl, native, "hxf:$local(${args.joinToString(", ")})")
            }
        }
    }

    private fun assertSame(shacl: RDFNode?, native: RDFNode?, label: String) {
        assertNotNull(shacl, "SHACL body of $label unbound"); assertNotNull(native, "native $label unbound")
        val a = shacl!!.asLiteral(); val b = native!!.asLiteral()
        if (a.datatypeURI == "http://www.w3.org/2001/XMLSchema#boolean") assertEquals(a.boolean, b.boolean, label)
        else assertEquals(a.double, b.double, 1e-9, label)
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.FunctionCatalogueTest" --tests "io.hexplain.query.PureFunctionAgreementTest"`
Expected: fail (resource missing). Note `jena-shacl` is needed for `SHACL` vocabulary constants: add `testImplementation(libs.jena.shacl)` to `query/build.gradle.kts`.

- [ ] **Step 3: Write fn.ttl**

`query/src/main/resources/hxf/fn.ttl`:
```turtle
# Hexplain SPARQL function library (hxf) 0.1
# One IRI per function. Pure functions carry a SHACL-AF body any SHACL-AF engine can run;
# native functions need the Hexplain engine (io.hexplain.query) behind the query.
@prefix :        <https://hexplain.io/ns/fn#> .
@prefix hxf:     <https://hexplain.io/ns/fn#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix sh:      <http://www.w3.org/ns/shacl#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann:    <http://purl.org/vocab/vann/> .
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix dlv:     <https://hexplain.io/ns/dlv#> .
@prefix araster: <https://hexplain.io/ns/aspect/raster#> .
@prefix asref:   <https://hexplain.io/ns/aspect/spatialref#> .
@prefix asig:    <https://hexplain.io/ns/aspect/signal#> .
@prefix ageom:   <https://hexplain.io/ns/aspect/geometry#> .

<https://hexplain.io/ns/fn> a owl:Ontology ;
    owl:versionIRI <https://hexplain.io/ns/fn/0.1> ; owl:versionInfo "0.1" ;
    rdfs:label "Hexplain SPARQL function library (hxf)" ;
    rdfs:comment "Custom SPARQL functions that reach the bytes, parsed values, array cells and aspect coordinates of a file described by a Hexplain profile. Functions bind to the description vocabularies, never to a format." ;
    dcterms:created "2026-09-09"^^xsd:date ; dcterms:creator <https://geoknoesis.com> ;
    vann:preferredNamespacePrefix "hxf" ; vann:preferredNamespaceUri "https://hexplain.io/ns/fn#" .

:Function a owl:Class ; rdfs:label "Function" ; rdfs:isDefinedBy <https://hexplain.io/ns/fn> ;
    rdfs:comment "A SPARQL extension function of this library." .
:Kind a owl:Class ; rdfs:label "Function kind" ; rdfs:isDefinedBy <https://hexplain.io/ns/fn> .
:Pure a :Kind ; rdfs:label "pure" ; rdfs:comment "Computes over values already in the graph; published as a SHACL-AF sh:SPARQLFunction body." .
:Native a :Kind ; rdfs:label "native" ; rdfs:comment "Needs the bytes of the asset; implemented against the Hexplain engine." .
:kind a owl:ObjectProperty ; rdfs:range :Kind ; rdfs:isDefinedBy <https://hexplain.io/ns/fn> .
:signature a owl:DatatypeProperty ; rdfs:range xsd:string ; rdfs:isDefinedBy <https://hexplain.io/ns/fn> ;
    rdfs:comment "Argument list and result, in the notation name(arg: type, ...) -> type. A trailing ? marks an optional argument." .
:reads a owl:ObjectProperty ; rdfs:isDefinedBy <https://hexplain.io/ns/fn> ;
    rdfs:comment "A vocabulary term the function reads from the graph." .
:layer a owl:DatatypeProperty ; rdfs:range xsd:integer ; rdfs:isDefinedBy <https://hexplain.io/ns/fn> ;
    rdfs:comment "0 bytes, 1 parsed values, 2 arrays, 3 aspect coordinates, 9 diagnostics." .

# Parameters of pure functions, shared across bodies.
:arg1 a rdfs:Resource . :arg2 a rdfs:Resource . :arg3 a rdfs:Resource .

# ---- Layer 0: assets and bytes ----
:bytes a :Function ; :kind :Native ; :layer 0 ; rdfs:label "bytes" ;
    :signature "bytes(node: IRI) -> xsd:hexBinary | bytes(node: IRI, offset: integer, length: integer) -> xsd:hexBinary" ;
    :reads hexplain:byteOffset, hexplain:byteLength ;
    rdfs:comment "The node's bytes as they sit in the file, whole or a slice relative to the node. Unbound when the slice leaves the node or exceeds maxBytesPerCall." .
:decodedBytes a :Function ; :kind :Native ; :layer 0 ; rdfs:label "decoded bytes" ;
    :signature "decodedBytes(node: IRI) -> xsd:hexBinary" ;
    :reads hexplain:isEncodedWith, hexplain:hasEncodingStep ;
    rdfs:comment "The node's bytes after the codec chain the profile declares has been inverted." .
:digest a :Function ; :kind :Native ; :layer 0 ; rdfs:label "digest" ;
    :signature "digest(node: IRI, algorithm: IRI | string) -> xsd:string" ;
    rdfs:comment "Lower-case hex digest of the node's raw bytes. The algorithm is a checksum-register concept (rck:SHA256, rck:CRC32, ...) or a name." .

# ---- Layer 1: parsed values ----
:value a :Function ; :kind :Native ; :layer 1 ; rdfs:label "value" ;
    :signature "value(node: IRI) -> literal" ;
    rdfs:comment "The node's parsed scalar, mapped by the profile or not. Unbound for structs, lists and arrays." .
:hel a :Function ; :kind :Native ; :layer 1 ; rdfs:label "HEL" ;
    :signature "hel(node: IRI, expression: string) -> literal" ;
    rdfs:comment "A HEL expression evaluated with the node's struct as instance, its container as parent and the file as root." .
:decode a :Function ; :kind :Native ; :layer 1 ; rdfs:label "decode" ;
    :signature "decode(bytes: xsd:hexBinary, type: bddo:DataType) -> literal" ;
    rdfs:comment "One scalar decoded from bytes by a BDDO primitive datatype." .

# ---- Layer 2: arrays (DLV) ----
:rank a :Function ; :kind :Native ; :layer 2 ; rdfs:label "rank" ; :signature "rank(array: IRI) -> xsd:integer" ;
    :reads dlv:hasDimension ; rdfs:comment "Number of dimensions of the array." .
:extent a :Function ; :kind :Native ; :layer 2 ; rdfs:label "extent" ;
    :signature "extent(array: IRI, dimension: integer | dlv:Axis) -> xsd:integer" ;
    :reads dlv:hasAxis, dlv:dimensionSize ; rdfs:comment "Size of one dimension, named by zero-based position or by axis." .
:cell a :Function ; :kind :Native ; :layer 2 ; rdfs:label "cell" ;
    :signature "cell(array: IRI, i1: integer, ..., in: integer) -> literal" ;
    rdfs:comment "The cell at zero-based indices given in the layout's dimension order. Typed by the cell datatype." .
:stat a :Function ; :kind :Native ; :layer 2 ; rdfs:label "statistic" ;
    :signature "stat(array: IRI, kind: string) -> literal | stat(array: IRI, kind: string, lo1, hi1, ..., lon, hin: integer) -> literal" ;
    rdfs:comment "min, max, sum, mean or count over the whole array or a half-open window. Refused above maxCellsPerWindow." .
:window a :Function ; :kind :Native ; :layer 2 ; rdfs:label "window" ;
    :signature "(array: IRI, lo1, hi1, ..., lon, hin: integer) hxf:window (i1, ..., in, value)" ;
    rdfs:comment "Property function enumerating every cell of a half-open window, row-major, binding its indices and value. Refused above maxCellsPerWindow." .
:layout a :Function ; :kind :Native ; :layer 2 ; rdfs:label "layout" ; :signature "layout(array: IRI) -> xsd:string" ;
    rdfs:comment "The resolved layout: axes, extents, strides and cell type." .

# ---- Layer 3: raster ----
:sampleAt a :Function ; :kind :Native ; :layer 3 ; rdfs:label "sample at" ;
    :signature "sampleAt(grid: IRI, x: integer, y: integer, band?: IRI | integer) -> literal" ;
    :reads araster:hasArray, araster:hasBand, araster:bandIndex, dlv:axisX, dlv:axisY, dlv:axisBand ;
    rdfs:comment "Raw sample at column x, row y. The array is the band's araster:hasArray, else the grid's, else the grid struct's single array field. A band is a RasterBand IRI or a one-based index and is applied along dlv:axisBand when the array has one." .
:calibrate a :Function , sh:SPARQLFunction ; :kind :Pure ; :layer 3 ; rdfs:label "calibrate" ;
    :signature "calibrate(band: IRI, raw: number) -> xsd:double" ;
    :reads araster:sampleScale, araster:sampleOffset ;
    rdfs:comment "raw * araster:sampleScale + araster:sampleOffset; identity when neither is asserted." ;
    sh:parameter [ sh:path :arg1 ; sh:order 0 ; sh:description "band" ] , [ sh:path :arg2 ; sh:order 1 ; sh:description "raw" ] ;
    sh:returnType xsd:double ;
    sh:prefixes <https://hexplain.io/ns/fn> ;
    sh:select """SELECT ?result WHERE {
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/raster#sampleScale> ?scale }
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/raster#sampleOffset> ?offset }
  BIND ( xsd:double($arg2) * COALESCE(xsd:double(?scale), 1.0) + COALESCE(xsd:double(?offset), 0.0) AS ?result )
}""" .
:isNoData a :Function , sh:SPARQLFunction ; :kind :Pure ; :layer 3 ; rdfs:label "is no-data" ;
    :signature "isNoData(band: IRI, value: number) -> xsd:boolean" ;
    :reads araster:noDataValue, araster:hasBand ;
    rdfs:comment "True when value equals araster:noDataValue on the band, or on the grid that has the band. False when no no-data value is declared." ;
    sh:parameter [ sh:path :arg1 ; sh:order 0 ; sh:description "band" ] , [ sh:path :arg2 ; sh:order 1 ; sh:description "value" ] ;
    sh:returnType xsd:boolean ;
    sh:select """SELECT ?result WHERE {
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/raster#noDataValue> ?own }
  OPTIONAL { ?grid <https://hexplain.io/ns/aspect/raster#hasBand> $arg1 . ?grid <https://hexplain.io/ns/aspect/raster#noDataValue> ?inherited }
  BIND ( COALESCE(?own, ?inherited) AS ?nd )
  BIND ( IF(BOUND(?nd), xsd:double(?nd) = xsd:double($arg2), false) AS ?result )
}""" .
:physicalAt a :Function ; :kind :Native ; :layer 3 ; rdfs:label "physical value at" ;
    :signature "physicalAt(grid: IRI, x: integer, y: integer, band?: IRI | integer) -> xsd:double" ;
    :reads araster:sampleScale, araster:sampleOffset, araster:noDataValue ;
    rdfs:comment "calibrate(sampleAt(...)); unbound when the raw sample is no-data." .

# ---- Layer 3: spatial reference (affine asref:GeoTransform) ----
# worldX = originX + col*scaleX + row*skewX ; worldY = originY + col*skewY + row*scaleY.
# Inverse: det = scaleX*scaleY - skewX*skewY ; c = (scaleY*(wx-originX) - skewX*(wy-originY))/det ;
# r = (-skewY*(wx-originX) + scaleX*(wy-originY))/det ; floor(c) for PixelCorner, floor(c+0.5) for PixelCenter.
:worldX a :Function , sh:SPARQLFunction ; :kind :Pure ; :layer 3 ; rdfs:label "world X" ;
    :signature "worldX(transform: IRI, col: number, row: number) -> xsd:double" ;
    :reads asref:originX, asref:scaleX, asref:skewX ;
    rdfs:comment "World X of grid position (col, row) under an affine geotransform; a missing skew reads as 0." ;
    sh:parameter [ sh:path :arg1 ; sh:order 0 ] , [ sh:path :arg2 ; sh:order 1 ] , [ sh:path :arg3 ; sh:order 2 ] ;
    sh:returnType xsd:double ;
    sh:select """SELECT ?result WHERE {
  $arg1 <https://hexplain.io/ns/aspect/spatialref#originX> ?ox ; <https://hexplain.io/ns/aspect/spatialref#scaleX> ?sx .
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#skewX> ?kx }
  BIND ( xsd:double(?ox) + xsd:double($arg2) * xsd:double(?sx) + xsd:double($arg3) * COALESCE(xsd:double(?kx), 0.0) AS ?result )
}""" .
:worldY a :Function , sh:SPARQLFunction ; :kind :Pure ; :layer 3 ; rdfs:label "world Y" ;
    :signature "worldY(transform: IRI, col: number, row: number) -> xsd:double" ;
    :reads asref:originY, asref:scaleY, asref:skewY ;
    rdfs:comment "World Y of grid position (col, row) under an affine geotransform; a missing skew reads as 0." ;
    sh:parameter [ sh:path :arg1 ; sh:order 0 ] , [ sh:path :arg2 ; sh:order 1 ] , [ sh:path :arg3 ; sh:order 2 ] ;
    sh:returnType xsd:double ;
    sh:select """SELECT ?result WHERE {
  $arg1 <https://hexplain.io/ns/aspect/spatialref#originY> ?oy ; <https://hexplain.io/ns/aspect/spatialref#scaleY> ?sy .
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#skewY> ?ky }
  BIND ( xsd:double(?oy) + xsd:double($arg2) * COALESCE(xsd:double(?ky), 0.0) + xsd:double($arg3) * xsd:double(?sy) AS ?result )
}""" .
:column a :Function , sh:SPARQLFunction ; :kind :Pure ; :layer 3 ; rdfs:label "column" ;
    :signature "column(transform: IRI, wx: number, wy: number) -> xsd:integer" ;
    :reads asref:originX, asref:originY, asref:scaleX, asref:scaleY, asref:skewX, asref:skewY, asref:pixelRegistration ;
    rdfs:comment "Column of the cell containing world point (wx, wy): floor for asref:PixelCorner (default), nearest centre for asref:PixelCenter." ;
    sh:parameter [ sh:path :arg1 ; sh:order 0 ] , [ sh:path :arg2 ; sh:order 1 ] , [ sh:path :arg3 ; sh:order 2 ] ;
    sh:returnType xsd:integer ;
    sh:select """SELECT ?result WHERE {
  $arg1 <https://hexplain.io/ns/aspect/spatialref#originX> ?ox ; <https://hexplain.io/ns/aspect/spatialref#originY> ?oy ;
        <https://hexplain.io/ns/aspect/spatialref#scaleX> ?sx ; <https://hexplain.io/ns/aspect/spatialref#scaleY> ?sy .
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#skewX> ?kx }
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#skewY> ?ky }
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#pixelRegistration> ?reg }
  BIND ( COALESCE(xsd:double(?kx), 0.0) AS ?kxv ) BIND ( COALESCE(xsd:double(?ky), 0.0) AS ?kyv )
  BIND ( xsd:double(?sx) * xsd:double(?sy) - ?kxv * ?kyv AS ?det )
  FILTER ( ?det != 0.0 )
  BIND ( ( xsd:double(?sy) * (xsd:double($arg2) - xsd:double(?ox)) - ?kxv * (xsd:double($arg3) - xsd:double(?oy)) ) / ?det AS ?c )
  BIND ( xsd:integer(FLOOR(IF(BOUND(?reg) && ?reg = <https://hexplain.io/ns/aspect/spatialref#PixelCenter>, ?c + 0.5, ?c))) AS ?result )
}""" .
:row a :Function , sh:SPARQLFunction ; :kind :Pure ; :layer 3 ; rdfs:label "row" ;
    :signature "row(transform: IRI, wx: number, wy: number) -> xsd:integer" ;
    :reads asref:originX, asref:originY, asref:scaleX, asref:scaleY, asref:skewX, asref:skewY, asref:pixelRegistration ;
    rdfs:comment "Row of the cell containing world point (wx, wy): floor for asref:PixelCorner (default), nearest centre for asref:PixelCenter." ;
    sh:parameter [ sh:path :arg1 ; sh:order 0 ] , [ sh:path :arg2 ; sh:order 1 ] , [ sh:path :arg3 ; sh:order 2 ] ;
    sh:returnType xsd:integer ;
    sh:select """SELECT ?result WHERE {
  $arg1 <https://hexplain.io/ns/aspect/spatialref#originX> ?ox ; <https://hexplain.io/ns/aspect/spatialref#originY> ?oy ;
        <https://hexplain.io/ns/aspect/spatialref#scaleX> ?sx ; <https://hexplain.io/ns/aspect/spatialref#scaleY> ?sy .
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#skewX> ?kx }
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#skewY> ?ky }
  OPTIONAL { $arg1 <https://hexplain.io/ns/aspect/spatialref#pixelRegistration> ?reg }
  BIND ( COALESCE(xsd:double(?kx), 0.0) AS ?kxv ) BIND ( COALESCE(xsd:double(?ky), 0.0) AS ?kyv )
  BIND ( xsd:double(?sx) * xsd:double(?sy) - ?kxv * ?kyv AS ?det )
  FILTER ( ?det != 0.0 )
  BIND ( ( - ?kyv * (xsd:double($arg2) - xsd:double(?ox)) + xsd:double(?sx) * (xsd:double($arg3) - xsd:double(?oy)) ) / ?det AS ?r )
  BIND ( xsd:integer(FLOOR(IF(BOUND(?reg) && ?reg = <https://hexplain.io/ns/aspect/spatialref#PixelCenter>, ?r + 0.5, ?r))) AS ?result )
}""" .
:sampleAtWorld a :Function ; :kind :Native ; :layer 3 ; rdfs:label "sample at world point" ;
    :signature "sampleAtWorld(dataset: IRI, wx: number, wy: number, band?: IRI | integer) -> literal" ;
    :reads asref:hasGeoTransform ;
    rdfs:comment "sampleAt at (column(t, wx, wy), row(t, wx, wy)) where t is the dataset's asref:hasGeoTransform." .

# ---- Layer 3: geometry and signal ----
:wkt a :Function ; :kind :Native ; :layer 3 ; rdfs:label "WKT" ;
    :signature "wkt(node: IRI) -> geo:wktLiteral" ;
    :reads asref:hasCRS, asref:epsgCode ;
    rdfs:comment "A GeoSPARQL WKT literal from a WKB or GeoPackage payload. The CRS is the GeoPackage SRS id, else asref:hasCRS/asref:epsgCode on the node or the nearest ancestor." .
:sampleAtTime a :Function ; :kind :Native ; :layer 3 ; rdfs:label "sample at time" ;
    :signature "sampleAtTime(signal: IRI, seconds: number, channel?: integer) -> literal" ;
    :reads asig:sampleRate, araster:hasArray, dlv:axisTime, dlv:axisBand ;
    rdfs:comment "The cell at round(seconds * asig:sampleRate) along dlv:axisTime; the one-based channel is applied along dlv:axisBand." .

# ---- Diagnostics ----
:explain a :Function ; :kind :Native ; :layer 9 ; rdfs:label "explain" ; :signature "explain(node: IRI) -> xsd:string" ;
    rdfs:comment "How the runtime resolves the node (asset, profile, path, kind, byte range, layout) and why the last call on it failed. Never unbound." .
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.FunctionCatalogueTest" --tests "io.hexplain.query.PureFunctionAgreementTest"`
Expected: PASS. The agreement test rewrites `$argN` to `?argN` and injects `BIND`s at the start of the body, so a body must keep the exact opening `SELECT ?result WHERE {`. If the SHACL `column`/`row` results differ from native on the `PixelCenter` case, compare the `FLOOR(?c + 0.5)` arm against `Affine.snap` before touching either.

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add query/build.gradle.kts query/src/main/resources/hxf/fn.ttl query/src/test/kotlin/io/hexplain/query/FunctionCatalogueTest.kt query/src/test/kotlin/io/hexplain/query/PureFunctionAgreementTest.kt
git commit -m "feat(query): fn.ttl catalogue with SHACL-AF bodies for the pure functions, and the agreement test"
```

---
### Task 12: GDAL parity through a real profile

**Files:**
- Create: `query/src/test/resources/envi-byte-profile.ttl`
- Test: `query/src/test/kotlin/io/hexplain/query/GdalParityTest.kt`

**Interfaces:**
- Consumes: `processToSemanticGraph(profile: Model, rootStructUri, baseUri, data: ByteArray)` from `io.hexplain.core.semantic`; `ProfileLoader().load(InputStream)`; `TiffDatasetDecoder().decode(bytes).pixels.data` (the GDAL-verified Kotlin path).
- Both tests skip (JUnit assumption) when the GDAL corpus is not fetched.

- [ ] **Step 1: Write the profile**

`query/src/test/resources/envi-byte-profile.ttl`:
```turtle
# A raw ENVI byte grid: no header in the file, 20 x 20 x 1 uint8 band-interleaved-by-pixel.
# The .hdr sidecar gives the shape; this profile fixes it so the .bin alone is readable.
@prefix rdfs:     <http://www.w3.org/2000/01/rdf-schema#> .
@prefix bddo:     <https://hexplain.io/ns/bddo#> .
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix dlv:      <https://hexplain.io/ns/dlv#> .
@prefix araster:  <https://hexplain.io/ns/aspect/raster#> .
@prefix envi:     <https://example.org/formats/envi-byte#> .

envi:File a bddo:Struct ;
    rdfs:label "ENVI raw byte grid, 20 x 20, one band, BIP" ;
    hexplain:mapsToClass araster:RasterGrid ;
    bddo:hasField ( envi:Samples ) .

envi:Samples a bddo:Field ;
    rdfs:label "Samples" ;
    bddo:dataType bddo:bytes ;
    bddo:sizeToEndOfStream true ;
    hexplain:mapsToObjectProperty araster:hasArray ;
    hexplain:hasDataLayout [
        a dlv:DataLayout ;
        dlv:cellDataType bddo:uint8 ;
        dlv:hasDimension (
            [ a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSize 20 ]
            [ a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSize 20 ]
            [ a dlv:Dimension ; dlv:hasAxis dlv:axisBand ; dlv:dimensionSize 1 ]
        )
    ] .
```

- [ ] **Step 2: Write the failing test**

```kotlin
package io.hexplain.query

import io.hexplain.core.raster.TiffDatasetDecoder
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.semantic.processToSemanticGraph
import io.hexplain.query.runtime.HexplainQueryRuntime
import io.hexplain.query.runtime.RegistryAssetResolver
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/** The query layer against the same oracle as the decoders: GDAL's digest of byte.tif / byte_envi.bin. */
class GdalParityTest {
    private val corpus = Path.of("..", "tests", "gdal", "cache", "upstream", "autotest", "gcore", "data")
    private val envi = corpus.resolve("gtiff").resolve("byte_envi.bin")
    private val tif = corpus.resolve("byte.tif")
    private val asset = "https://example.org/assets/byte_envi.bin"
    private val profileIri = "https://example.org/fmt/envi-byte"
    private val root = "https://example.org/formats/envi-byte#File"
    /** tests/gdal/results/hexplain.jsonl, pixels_sha256 of autotest/gcore/data/gtiff/byte_envi.bin (and of byte.tif). */
    private val gdalDigest = "b55a841b7b95be907f6bb0d358b8d10c9dce6e485381eb9accb71e653597d9a1"

    private fun setUp(): org.apache.jena.rdf.model.Model {
        assumeTrue(Files.exists(envi), "GDAL corpus not fetched; run tests/gdal/fetch_corpus.py")
        val profile = ProfileLoader().load(javaClass.getResourceAsStream("/envi-byte-profile.ttl")!!)
        val runtime = HexplainQueryRuntime(RegistryAssetResolver().register(asset, envi))
            .registerProfile(profileIri, profile, root).bindAsset(asset, profileIri)
        HexplainFunctions.register(runtime)
        return processToSemanticGraph(profile, root, asset, Files.readAllBytes(envi))
    }

    @Test
    fun `every cell read through hxf window hashes to GDAL's pixel digest`() {
        val graph = setUp()
        val rows = Sparql.select(graph, "SELECT ?y ?x ?v WHERE { (<$asset#root/Samples> 0 20 0 20 0 1) hxf:window (?y ?x ?b ?v) } ORDER BY ?y ?x")
        assertEquals(400, rows.size)
        val bytes = ByteArray(400) { rows[it].getLiteral("v").int.toByte() }
        assertEquals(gdalDigest, sha256(bytes))
    }

    @Test
    fun `hxf sampleAt agrees with the GDAL-verified TIFF decoder on every pixel`() {
        val graph = setUp()
        assumeTrue(Files.exists(tif))
        val expected = TiffDatasetDecoder().decode(Files.readAllBytes(tif)).pixels.data
        assertEquals(gdalDigest, sha256(expected))
        val values = (0 until 20).joinToString(" ") { it.toString() }
        val rows = Sparql.select(graph, "SELECT ?y ?x (hxf:sampleAt(<$asset#root>, ?x, ?y) AS ?v) WHERE { VALUES ?y { $values } VALUES ?x { $values } } ORDER BY ?y ?x")
        assertEquals(400, rows.size)
        for (r in rows) {
            val y = r.getLiteral("y").int; val x = r.getLiteral("x").int
            assertEquals(expected[y * 20 + x].toInt() and 0xff, r.getLiteral("v").int, "pixel ($x, $y)")
        }
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
```

- [ ] **Step 3: Run the test**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.GdalParityTest"`
Expected: PASS (2 tests). If the profile loader rejects `bddo:sizeToEndOfStream true` or the layout, read the compiler's message: `compileDataLayout` requires `dlv:cellDataType` and each dimension `dlv:hasAxis`. If `araster:hasArray` is missing from the lifted graph, Task 2 is not on the classpath (rebuild `:core`). If the ORDER BY over 400 rows is slow, it is not; the whole test runs in well under a second.

- [ ] **Step 4: Commit (hexplain-tools)**

```bash
git add query/src/test/resources/envi-byte-profile.ttl query/src/test/kotlin/io/hexplain/query/GdalParityTest.kt
git commit -m "test(query): pixel parity with GDAL through a raw-grid profile and hxf:window / hxf:sampleAt"
```

---

### Task 13: `hxq` command line

**Files:**
- Create: `query/src/main/kotlin/io/hexplain/query/cli/Main.kt`
- Test: `query/src/test/kotlin/io/hexplain/query/cli/MainTest.kt`

**Interfaces:**
- Produces: `fun run(args: Array<String>, out: PrintStream, err: PrintStream): Int` and `fun main(args)`.
- Usage: `hxq <instance.ttl> <query.rq> [--asset <iri> <file> --profile <profile.ttl> <rootStructIri>]...` Each `--asset ... --profile ...` pair binds one file to one profile. Results print as a text table. Exit 0 on success, 2 on usage error, 1 on failure.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.cli

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.io.ByteArrayOutputStream
import java.io.PrintStream
import java.nio.file.Files

class MainTest {
    @Test
    fun `runs a query with one asset bound to a profile`() {
        val dir = Files.createTempDirectory("hxq")
        val bin = dir.resolve("grid.bin"); Files.write(bin, ByteArray(400) { (it % 20).toByte() })
        val profile = dir.resolve("profile.ttl"); Files.copy(javaClass.getResourceAsStream("/envi-byte-profile.ttl")!!, profile)
        val asset = "https://example.org/assets/grid.bin"
        val graph = dir.resolve("graph.ttl")
        Files.writeString(graph, """
            @prefix araster: <https://hexplain.io/ns/aspect/raster#> .
            <$asset#root> a araster:RasterGrid ; araster:hasArray <$asset#root/Samples> .
        """.trimIndent())
        val query = dir.resolve("q.rq")
        Files.writeString(query, "PREFIX hxf: <https://hexplain.io/ns/fn#> SELECT (hxf:cell(<$asset#root/Samples>, 1, 7, 0) AS ?v) (hxf:sampleAt(<$asset#root>, 3, 0) AS ?s) WHERE {}")
        val out = ByteArrayOutputStream(); val err = ByteArrayOutputStream()
        val code = run(arrayOf(graph.toString(), query.toString(), "--asset", asset, bin.toString(), "--profile", profile.toString(), "https://example.org/formats/envi-byte#File"), PrintStream(out), PrintStream(err))
        assertEquals(0, code, err.toString())
        val text = out.toString()
        assertTrue(text.contains("7"), text)
        assertTrue(text.contains("3"), text)
    }

    @Test
    fun `usage errors exit 2`() {
        val err = ByteArrayOutputStream()
        assertEquals(2, run(arrayOf(), PrintStream(ByteArrayOutputStream()), PrintStream(err)))
        assertTrue(err.toString().contains("usage"))
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.cli.MainTest"`
Expected: compilation error.

- [ ] **Step 3: Implement**

`cli/Main.kt`:
```kotlin
package io.hexplain.query.cli

import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.runtime.HexplainQueryRuntime
import io.hexplain.query.runtime.RegistryAssetResolver
import org.apache.jena.query.QueryExecution
import org.apache.jena.query.QueryFactory
import org.apache.jena.query.ResultSetFormatter
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.RDFDataMgr
import java.io.PrintStream
import java.nio.file.Files
import java.nio.file.Path
import kotlin.system.exitProcess

private const val USAGE = "usage: hxq <instance.ttl> <query.rq> [--asset <iri> <file> --profile <profile.ttl> <rootStructIri>]..."

/**
 * `hxq`: run one SPARQL query over an instance graph with the hxf: functions registered and
 * each named asset bound to its profile. A demo and fixture tool, not a server.
 */
fun run(args: Array<String>, out: PrintStream, err: PrintStream): Int {
    if (args.size < 2) { err.println(USAGE); return 2 }
    val resolver = RegistryAssetResolver()
    val runtime = HexplainQueryRuntime(resolver)
    var i = 2
    var pendingAsset: Pair<String, Path>? = null
    while (i < args.size) {
        when (args[i]) {
            "--asset" -> {
                if (i + 2 >= args.size) { err.println(USAGE); return 2 }
                pendingAsset = args[i + 1] to Path.of(args[i + 2]); i += 3
            }
            "--profile" -> {
                if (i + 2 >= args.size || pendingAsset == null) { err.println(USAGE); return 2 }
                val (assetIri, file) = pendingAsset
                val profilePath = Path.of(args[i + 1]); val rootStruct = args[i + 2]
                try {
                    val profile = Files.newInputStream(profilePath).use { ProfileLoader().load(it) }
                    val profileIri = profilePath.toUri().toString()
                    resolver.register(assetIri, file)
                    runtime.registerProfile(profileIri, profile, rootStruct).bindAsset(assetIri, profileIri)
                } catch (e: Exception) {
                    err.println("hxq: cannot bind <$assetIri>: ${e.message}"); return 1
                }
                pendingAsset = null; i += 3
            }
            else -> { err.println(USAGE); return 2 }
        }
    }
    if (pendingAsset != null) { err.println("hxq: --asset ${pendingAsset.first} has no --profile"); return 2 }
    return try {
        val model = ModelFactory.createDefaultModel().also { RDFDataMgr.read(it, args[0]) }
        val query = QueryFactory.create(Files.readString(Path.of(args[1])))
        HexplainFunctions.register(runtime)
        QueryExecution.model(model).query(query).build().use { qexec ->
            when {
                query.isSelectType -> ResultSetFormatter.out(out, qexec.execSelect(), query)
                query.isAskType -> out.println(qexec.execAsk())
                else -> RDFDataMgr.write(out, qexec.execConstruct(), org.apache.jena.riot.Lang.TTL)
            }
        }
        0
    } catch (e: Exception) {
        err.println("hxq: ${e.message}"); 1
    }
}

fun main(args: Array<String>) {
    exitProcess(run(args, System.out, System.err))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat :query:test --offline -q --tests "io.hexplain.query.cli.MainTest"`
Expected: PASS (2 tests). `hxf:cell(..., 1, 7, 0)` on bytes `i % 20` in row-major 20×20×1 is byte index 27, value 7; `sampleAt(grid, 3, 0)` is byte 3, value 3.

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add query/src/main/kotlin/io/hexplain/query/cli/Main.kt query/src/test/kotlin/io/hexplain/query/cli/MainTest.kt
git commit -m "feat(query): hxq command line for running hxf: queries over bound assets"
```

---

### Task 14: Fuseki module

**Files:**
- Create: `query-fuseki/build.gradle.kts`
- Create: `query-fuseki/src/main/kotlin/io/hexplain/query/fuseki/HexplainFusekiModule.kt`
- Create: `query-fuseki/src/main/resources/META-INF/services/org.apache.jena.fuseki.main.sys.FusekiAutoModule`
- Modify: `settings.gradle.kts` (add `include("query-fuseki")`), `gradle/libs.versions.toml` (add `jena-fuseki-main = { module = "org.apache.jena:jena-fuseki-main", version.ref = "jena" }`)
- Test: `query-fuseki/src/test/kotlin/io/hexplain/query/fuseki/HexplainFusekiModuleTest.kt`

**Interfaces:**
- Produces: `class HexplainFusekiModule : FusekiAutoModule { override fun name(); override fun start() }` and `companion fun runtimeFromProperties(props: Properties): HexplainQueryRuntime`.
- System properties: `hexplain.query.roots` (path list separated by `;`) → `FileSystemAssetResolver`; `hexplain.query.profiles` (entries `<profileIri>|<profile.ttl>|<rootStructIri>` separated by `;`) → registered profiles. Assets are bound through `dcterms:conformsTo` triples in the dataset.
- Jena 5.5 names to verify against the downloaded jar (the executor should open `jena-fuseki-main-5.5.0.jar` and confirm): `org.apache.jena.fuseki.main.sys.FusekiAutoModule` (`name()`, `start()`), `org.apache.jena.fuseki.main.FusekiServer.create().port(0).add(name, DatasetGraph).fusekiModules(FusekiModules.create(module)).build()`, `org.apache.jena.fuseki.main.sys.FusekiModules`, `org.apache.jena.sparql.exec.http.QueryExecutionHTTP.service(url).query(q).build()`.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.query.fuseki

import org.apache.jena.fuseki.main.FusekiServer
import org.apache.jena.fuseki.main.sys.FusekiModules
import org.apache.jena.graph.NodeFactory
import org.apache.jena.graph.Triple
import org.apache.jena.sparql.core.DatasetGraphFactory
import org.apache.jena.sparql.exec.http.QueryExecutionHTTP
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.util.Properties

class HexplainFusekiModuleTest {
    @Test
    fun `a server with the module answers hxf queries over HTTP`() {
        val dsg = DatasetGraphFactory.createTxnMem()
        val t = NodeFactory.createURI("https://example.org/t")
        fun lit(d: Double) = NodeFactory.createLiteralDT(d.toString(), org.apache.jena.datatypes.xsd.XSDDatatype.XSDdouble)
        dsg.executeWrite {
            dsg.defaultGraph.add(Triple.create(t, NodeFactory.createURI("https://hexplain.io/ns/aspect/spatialref#originX"), lit(100.0)))
            dsg.defaultGraph.add(Triple.create(t, NodeFactory.createURI("https://hexplain.io/ns/aspect/spatialref#originY"), lit(200.0)))
            dsg.defaultGraph.add(Triple.create(t, NodeFactory.createURI("https://hexplain.io/ns/aspect/spatialref#scaleX"), lit(2.0)))
            dsg.defaultGraph.add(Triple.create(t, NodeFactory.createURI("https://hexplain.io/ns/aspect/spatialref#scaleY"), lit(-2.0)))
        }
        val server = FusekiServer.create().port(0).add("/ds", dsg).fusekiModules(FusekiModules.create(HexplainFusekiModule())).build().start()
        try {
            val url = "http://localhost:${server.port}/ds"
            QueryExecutionHTTP.service(url).query("PREFIX hxf: <https://hexplain.io/ns/fn#> SELECT (hxf:worldX(<https://example.org/t>, 1, 0) AS ?v) WHERE {}").build().use {
                assertEquals(102.0, it.execSelect().next().getLiteral("v").double, 1e-12)
            }
        } finally { server.stop() }
    }

    @Test
    fun `runtime is configured from properties`() {
        val props = Properties()
        props["hexplain.query.roots"] = System.getProperty("java.io.tmpdir")
        val runtime = HexplainFusekiModule.runtimeFromProperties(props)
        assertNotNull(runtime)
        assertNull(runtime.resolver.open("https://example.org/not-a-file"))
    }
}
```

- [ ] **Step 2: Wire the module and run the test to see it fail**

`query-fuseki/build.gradle.kts`:
```kotlin
plugins { kotlin("jvm") version libs.versions.kotlin.get() }
repositories { mavenCentral() }
dependencies {
    implementation(project(":core"))
    implementation(project(":query"))
    implementation(libs.jena.arq)
    implementation(libs.jena.fuseki.main)
    testImplementation(libs.junit.jupiter)
}
tasks.test { useJUnitPlatform() }
```
Add `include("query-fuseki")` to `settings.gradle.kts` and the catalog entry to `gradle/libs.versions.toml`.

Run: `./gradlew.bat :query-fuseki:test -q` (no `--offline`: Fuseki jars download once).
Expected: compilation error (module class missing).

- [ ] **Step 3: Implement**

`HexplainFusekiModule.kt`:
```kotlin
package io.hexplain.query.fuseki

import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.query.HexplainFunctions
import io.hexplain.query.runtime.FileSystemAssetResolver
import io.hexplain.query.runtime.HexplainQueryRuntime
import org.apache.jena.fuseki.main.sys.FusekiAutoModule
import java.nio.file.Files
import java.nio.file.Path
import java.util.Properties

/**
 * Registers the hxf: functions in a Fuseki server. Configured from system properties:
 *  - hexplain.query.roots     directories (';'-separated) below which file: assets may be opened
 *  - hexplain.query.profiles  entries "<profileIri>|<profile.ttl>|<rootStructIri>" (';'-separated)
 * Assets are bound to profiles through dcterms:conformsTo triples in the queried dataset.
 */
class HexplainFusekiModule : FusekiAutoModule {
    override fun name(): String = "hexplain-query-functions"

    override fun start() {
        HexplainFunctions.register(runtimeFromProperties(System.getProperties()))
    }

    companion object {
        fun runtimeFromProperties(props: Properties): HexplainQueryRuntime {
            val roots = props.getProperty("hexplain.query.roots", "").split(';').filter { it.isNotBlank() }.map { Path.of(it.trim()) }
            val runtime = HexplainQueryRuntime(FileSystemAssetResolver(roots))
            for (entry in props.getProperty("hexplain.query.profiles", "").split(';').filter { it.isNotBlank() }) {
                val parts = entry.split('|')
                require(parts.size == 3) { "hexplain.query.profiles entry must be <iri>|<ttl>|<rootStruct>: $entry" }
                val model = Files.newInputStream(Path.of(parts[1].trim())).use { ProfileLoader().load(it) }
                runtime.registerProfile(parts[0].trim(), model, parts[2].trim())
            }
            return runtime
        }
    }
}
```

`META-INF/services/org.apache.jena.fuseki.main.sys.FusekiAutoModule`:
```
io.hexplain.query.fuseki.HexplainFusekiModule
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./gradlew.bat :query-fuseki:test -q`
Expected: PASS (2 tests). If `FusekiAutoModule` has a different lifecycle method name in 5.5.0, use the one the interface declares for "module loaded" and keep `HexplainFunctions.register` there; the HTTP test is the contract.

- [ ] **Step 5: Commit (hexplain-tools)**

```bash
git add settings.gradle.kts gradle/libs.versions.toml query-fuseki
git commit -m "feat(query-fuseki): Fuseki module registering the hxf: functions from system properties"
```

---
### Task 15: Specification artefacts and design-doc reconciliation (hexplain.io)

**Files:**
- Create: `specification/fn/fn.ttl` (byte-identical copy of `hexplain-tools/query/src/main/resources/hxf/fn.ttl`)
- Create: `specification/fn/index.html`
- Modify: `specification/index.html` (module listing near the `dlv/index.html` entry at line ~99, and the prefix table near line ~151)
- Modify: `docs/superpowers/specs/2026-09-08-sparql-function-library-design.md` (status and deviations)

**Interfaces:**
- The spec repo's gates discover a module when a directory has both `<mod>.ttl` and `index.html`, and `tools/test_html_sync.py` requires the page's `<section id="normative-owl">` to embed the same triples (HTML-escaped Turtle inside `<pre class="nohighlight">`). Other gates in `tools/` may impose term-documentation rules; run them all and fix what they report.

- [ ] **Step 1: Copy fn.ttl and write the page**

```bash
cp d:/work/hexplain-tools/query/src/main/resources/hxf/fn.ttl d:/work/hexplain.io/specification/fn/fn.ttl
```

`specification/fn/index.html` — same skeleton as `specification/aspect/signal/index.html`: `<!doctype html>`, the shared `<style>`, a `<header>` with the back link to `../index.html`, title "Hexplain SPARQL function library (hxf)", and these sections:

1. `<section id="overview">`: one paragraph per layer (bytes, values, arrays, aspect coordinates, diagnostics), the argument conventions (zero-based indices in layout order; raster x = column, y = row; band as `araster:RasterBand` IRI or one-based `araster:bandIndex`; one-based channel), result typing, and the failure contract (unbound, never a query error; `hxf:explain` says why).
2. `<section id="catalogue">`: a table with columns Function, Kind, Signature, Reads, Description — one row per function, values copied from `fn.ttl`.
3. `<section id="examples">`: the four worked queries from the design doc, with the third rewritten to `?grid araster:hasArray ?a` (see Step 3).
4. `<section id="normative-owl"><h2>Canonical vocabulary and function bodies</h2><pre class="nohighlight">` … the entire `fn.ttl` HTML-escaped (`&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`) … `</pre></section>`.

Generate the escaped block rather than typing it:
```bash
cd d:/work/hexplain.io && python - <<'PY'
import html, pathlib
ttl = pathlib.Path("specification/fn/fn.ttl").read_text(encoding="utf-8")
pathlib.Path("specification/fn/_escaped.txt").write_text(html.escape(ttl, quote=False), encoding="utf-8")
PY
```
Paste `_escaped.txt` into the `<pre>` and delete the temp file.

- [ ] **Step 2: List the module in the specification index**

In `specification/index.html`, after the DLV `<dt>` entry add:
```html
<dt><a href="fn/index.html"><b>hxf (SPARQL function library)</b></a></dt>
<dd>Custom SPARQL functions that reach bytes, parsed values, array cells and aspect coordinates of a described file; pure functions ship as SHACL-AF bodies.</dd>
```
and in the prefix table add `<tr><td>Functions</td><td><code>hxf</code></td><td><code>https://hexplain.io/ns/fn#</code></td></tr>`.

- [ ] **Step 3: Reconcile the design document**

Edit `docs/superpowers/specs/2026-09-08-sparql-function-library-design.md`:
- Status line → `**Status:** approved design, implementation in progress (plan: docs/superpowers/plans/2026-09-09-sparql-function-library.md)`.
- Section 7, third worked query: replace `?a a araster:SampleArray .` with `?grid araster:hasArray ?a .` (the lifter links arrays by edge; it does not type them).
- Add a section `## Phase 1 deviations` before "Out of scope for phase 1":
  - `hxf:wkt` reads WKB and GeoPackage payloads through the core `GeometryDecoder`; shapefile shape records are not decoded in phase 1 because no record decoder exists in the engine.
  - No GeoSPARQL round trip test: `jena-geosparql` is not a dependency; the test asserts the `geo:wktLiteral` datatype and the CRS prefix instead.
  - The aspect ontologies are not edited to point at the functions; the function page and the specification index carry the cross-references, to keep the aspect pages' generated term documentation untouched.
  - A layout the accessor cannot execute fails at parse time, so every function on that asset is unbound (not only the array ones); `hxf:explain` carries the accessor's message.
  - Profiles are bound to assets explicitly (`bindAsset`, `hxq --asset/--profile`, Fuseki properties) or through `dcterms:conformsTo` triples; the lifter does not emit `conformsTo` itself.

- [ ] **Step 4: Run the spec gates**

```bash
cd d:/work/hexplain.io && python tools/run_gates.py
```
Expected: every gate PASS, including `test_html_sync` for the new `fn` module. If a term-documentation gate demands `skos:definition` blocks or `rdfs:isDefinedBy` on every named term, add them to `fn.ttl` in **both** repos (keep the copies identical: `diff` them) and re-run the Kotlin catalogue and agreement tests.

- [ ] **Step 5: Commit (hexplain.io)**

```bash
git add specification/fn/fn.ttl specification/fn/index.html specification/index.html docs/superpowers/specs/2026-09-08-sparql-function-library-design.md
git commit -m "spec(fn): publish the hxf SPARQL function library; record phase-1 deviations in the design"
```
If Step 4 changed the tools copy of `fn.ttl`, also commit that in `hexplain-tools`:
```bash
cd d:/work/hexplain-tools && git add query/src/main/resources/hxf/fn.ttl && git commit -m "spec(query): align fn.ttl with the published specification copy"
```

---

### Task 16: Full verification

**Files:** none new.

- [ ] **Step 1: Run every test of the touched modules**

```bash
cd d:/work/hexplain-tools && ./gradlew.bat :core:test :query:test :query-fuseki:test -q
```
Expected: BUILD SUCCESSFUL. The core suite must still pass in full (the lifter change is additive).

- [ ] **Step 2: Run the adapters isolation check**

```bash
./gradlew.bat :adapters:verifyCoreIsolation -q
```
Expected: PASS (the new modules add no native dependency to core).

- [ ] **Step 3: Smoke-run the CLI against the GDAL fixture**

```bash
cd d:/work/hexplain-tools && printf 'PREFIX hxf: <https://hexplain.io/ns/fn#>\nSELECT (hxf:sampleAt(<https://example.org/assets/byte#root>, 0, 0) AS ?v) (hxf:stat(<https://example.org/assets/byte#root/Samples>, "mean") AS ?mean) WHERE {}\n' > build/q.rq
printf '@prefix araster: <https://hexplain.io/ns/aspect/raster#> .\n<https://example.org/assets/byte#root> a araster:RasterGrid ; araster:hasArray <https://example.org/assets/byte#root/Samples> .\n' > build/g.ttl
./gradlew.bat :query:run -q --args="build/g.ttl build/q.rq --asset https://example.org/assets/byte tests/gdal/cache/upstream/autotest/gcore/data/gtiff/byte_envi.bin --profile query/src/test/resources/envi-byte-profile.ttl https://example.org/formats/envi-byte#File"
```
Expected: a two-column table with an integer sample and a mean around 100 (byte.tif's mean); no stack trace.

- [ ] **Step 4: Report**

State in the final message: which tests ran and their counts, the GDAL parity outcome, whether the spec gates passed, and every deviation recorded in Task 15.

---

## Self-review notes (already applied)

- **Spec coverage.** Layer 0 (Task 4), layer 1 (Task 5), layer 2 (Tasks 6–7), raster (Task 8), spatialref (Task 9), geometry and signal (Task 10), diagnostics (Tasks 4 and 6), pure/native split and agreement (Task 11), runtime and limits (Task 3, caps exercised in Tasks 4 and 7), registration/CLI/Fuseki (Tasks 4, 13, 14), GDAL parity (Task 12), spec artefacts (Task 15), the "note in the aspect ontologies" and the shapefile/GeoSPARQL items are recorded as deviations rather than silently dropped.
- **Type consistency.** `ResolvedNode.byteRange` is `ByteRange(start, length)` everywhere; `ArrayAccess.of(ResolvedNode)`; `RasterResolver.resolve(gridIri, band: NodeValue?, view, graph)`; `HexplainFunctions.register(runtime, functions, propertyFunctions)`; `Fixture.withLimits(QueryLimits)`; `Sparql.one(model, query, variable = "v")`.
- **Ordering.** Tasks 4–10 each append to `HexplainFunctions.register`; Task 11's catalogue test fails until all of them are in, so it is placed after Task 10.
