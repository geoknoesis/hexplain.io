# GDAL Profile Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ten HDL profiles (bmp, dted, lan, gtx, bt, lcp, idrisi, saga, dbf, wkb) to the profile library, parse-verify four of them against the cached GDAL corpus, upgrade gpkgblob to decompose its WKB, and link profiles from the GDAL coverage inventory.

**Architecture:** Each profile is one `.hx` file under `hexplain-profiles/profiles/<name>/`, compiled by the real HDL compiler and SHACL-checked by the library gate. Four profiles are copied byte-for-byte into `hexplain-tools/hdl/src/test/resources/profiles/` and driven by JUnit parity tests that compile the `.hx` in-process, lower it with `RdfToIrCompiler`, parse corpus samples with `Metaparser`, and compare against GDAL's recorded digests or the pinned WKB oracle. The spec repo's `gdal-drivers.json` gains a `profiles` list that the coverage page renders.

**Tech Stack:** HDL (`.hx`), Kotlin/JUnit 5 (hexplain-tools, Gradle offline), Python 3 + pyshacl (library gates, spec tooling).

**Spec:** `docs/superpowers/specs/2026-09-09-gdal-profile-wave-design.md` (in `hexplain.io`)

## Global Constraints

- Three sibling checkouts: `d:/work/hexplain-profiles`, `d:/work/hexplain-tools`, `d:/work/hexplain.io`. All commands below name the repo they run in.
- Profile namespaces are `https://hexplain.io/ns/profile/<name>#`; a module uses `module <name>`, a file format uses `format <name>`.
- Every profile header carries a `Verification status:` line and ends with a `LIMITS OF THIS DESCRIPTION` block.
- No hand-written `.ttl` beside an `.hx`; the gate compiles the `.hx`.
- Multi-byte DLV cell types are written with explicit endianness (`u16le`, `f32be`, …); `cell switch` is NOT used in any engine-parsed profile because `RdfToIrCompiler` rejects `dlv:hasConditionalCellDataType` (variants are `if`-guarded fields instead). idrisi and saga (SHACL-only bundles) follow the ENVI template and may use `cell switch`.
- Parity tests that need the corpus start with `assumeTrue(Files.exists(...))` so a checkout without `tests/gdal/cache` skips rather than fails.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Gate commands: library `python tools/run_gates.py` (hexplain-profiles); engine `.\gradlew.bat --offline :hdl:test --tests "<FQCN>"` (hexplain-tools); spec `python tools/test_gdal_inventory.py` and `python tools/test_gdal_runtime.py` (hexplain.io).
- The corpus root, relative to `hexplain-tools/hdl`, is `../tests/gdal/cache/upstream/autotest`.

---

## File structure

| Repo | Path | Responsibility |
|---|---|---|
| hexplain-profiles | `profiles/wkb/wkb.hx` | recursive ISO WKB module (create) |
| hexplain-profiles | `profiles/gpkgblob/gpkgblob.hx` | import wkb, replace opaque payload (modify) |
| hexplain-profiles | `profiles/bmp/bmp.hx`, `profiles/dted/dted.hx`, `profiles/lan/lan.hx`, `profiles/gtx/gtx.hx`, `profiles/bt/bt.hx`, `profiles/lcp/lcp.hx`, `profiles/idrisi/idrisi.hx`, `profiles/saga/saga.hx`, `profiles/dbf/dbf.hx` | one format each (create) |
| hexplain-tools | `hdl/src/test/resources/profiles/{wkb,gpkgblob,bmp,dted,dbf}/<name>.hx` | byte-identical fixture copies |
| hexplain-tools | `hdl/src/test/kotlin/io/hexplain/hdl/parity/{WkbParityTest,GpkgBlobParityTest,BmpParityTest,DtedParityTest,DbfParityTest}.kt` | behavioural verification |
| hexplain-tools | `hdl/src/test/kotlin/io/hexplain/hdl/parity/ProfileFixtures.kt` | shared compile/parse helpers for the five tests |
| hexplain.io | `specification/coverage/gdal-drivers.json` | `profiles` lists (modify) |
| hexplain.io | `tools/_build_ontology_docs.py` | render the Profiles column (modify) |
| hexplain.io | `tools/test_gdal_inventory.py` | schema check for `profiles` (modify) |
| hexplain.io | `specification/coverage/index.html` | regenerated page |

---

### Task 1: Shared parity helpers and the `wkb` module

**Files:**
- Create: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/ProfileFixtures.kt`
- Create: `hexplain-profiles/profiles/wkb/wkb.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/wkb/wkb.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/WkbParityTest.kt`

**Interfaces:**
- Produces `ProfileFixtures.formatIR(fixture: String, root: String): FormatIR`, `ProfileFixtures.parse(ir, bytes): Map<*, *>`, `ProfileFixtures.corpus: Path`, `ProfileFixtures.sha256(bytes): String`. Later tasks use exactly these.
- Produces the struct IRIs `https://hexplain.io/ns/profile/wkb#Geometry` with fields `byteOrder`, `wkbType`, `axes`, `hasZ`, `hasM`, and body fields `point`, `lineString`, `polygon`, `collection`; bodies expose `coords` (flat `List<Number>`), `numPoints`, `rings` (`List<Map>` of `LinearRing` with `coords`), `geometries` (`List<Map>` of `Geometry`).

- [ ] **Step 1: Write the shared helper**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/ProfileFixtures.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.ir.FormatIR
import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.assertTrue
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/** Compile a library fixture under src/test/resources/profiles and lower it to IR; shared by the parity tests. */
object ProfileFixtures {
    /** GDAL autotest corpus as fetched by tests/gdal/fetch_corpus.py; tests assume it exists. */
    val corpus: Path = Path.of("..", "tests", "gdal", "cache", "upstream", "autotest")

    fun formatIR(fixture: String, root: String): FormatIR {
        val r = HdlCompiler().compileFile(Path.of("src/test/resources/profiles/$fixture"))
        assertTrue(r.ok, "compile diagnostics for $fixture: ${r.diagnostics}")
        return RdfToIrCompiler(r.mergedModel()).compile(root)
    }

    fun parse(ir: FormatIR, bytes: ByteArray): Map<*, *> =
        Metaparser(ir, recordByteRange = true).parse(bytes) as Map<*, *>

    fun parseFile(ir: FormatIR, file: Path): Map<*, *> = parse(ir, Files.readAllBytes(file))

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    fun long(m: Map<*, *>, key: String): Long = (m[key] as Number).toLong()
    fun int(m: Map<*, *>, key: String): Int = long(m, key).toInt()
    fun map(m: Map<*, *>, key: String): Map<*, *> = m[key] as Map<*, *>
    fun list(m: Map<*, *>, key: String): List<Map<*, *>> = (m[key] as List<*>).map { it as Map<*, *> }
}
```

- [ ] **Step 2: Write the failing WKB parity test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/WkbParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import com.google.gson.Gson
import com.google.gson.JsonParser
import io.hexplain.core.raster.GeometryValue
import io.hexplain.hdl.parity.ProfileFixtures.int
import io.hexplain.hdl.parity.ProfileFixtures.list
import io.hexplain.hdl.parity.ProfileFixtures.map
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.DynamicTest
import org.junit.jupiter.api.TestFactory
import java.nio.file.Files
import java.nio.file.Path
import java.util.Base64

/**
 * The wkb module against the same GDAL 3.13.3 oracle GdalVectorGeometryTest uses: 136 ISO WKB
 * cases (types 1-7, XY/XYZ/XYM/XYZM, both byte orders, empty and nonempty). The parsed tree is
 * folded into GeometryValue so the comparison is the one the hand-written decoder already passes.
 */
class WkbParityTest {
    private val oracle: Path = Path.of("..", "core", "src", "test", "resources", "gdal-vector-geometry.json")
    private val ir by lazy { ProfileFixtures.formatIR("wkb/wkb.hx", "https://hexplain.io/ns/profile/wkb#Geometry") }

    @TestFactory
    fun `every oracle geometry parses through the wkb module to GDAL's expected value`(): List<DynamicTest> =
        JsonParser.parseString(Files.readString(oracle)).asJsonObject["cases"].asJsonArray.map { item ->
            val c = item.asJsonObject
            DynamicTest.dynamicTest(c["name"].asString) {
                val bytes = Base64.getDecoder().decode(c["base64"].asString)
                assertEquals(c["sha256"].asString, ProfileFixtures.sha256(bytes))
                val parsed = ProfileFixtures.parse(ir, bytes)
                assertEquals(c["expected"], Gson().toJsonTree(fold(parsed)))
            }
        }

    companion object {
        /** Mirror of GeometryDecoder.wkb's output shape, built from the parsed field tree. */
        fun fold(g: Map<*, *>): GeometryValue {
            val code = int(g, "wkbType"); val type = code % 1000; val dims = code / 1000
            val axes = when (dims) { 3 -> 4; 0 -> 2; else -> 3 }
            val labels = listOf("XY", "XYZ", "XYM", "XYZM")[dims]
            fun coords(body: Map<*, *>): List<List<Double>> =
                (body["coords"] as List<*>).map { (it as Number).toDouble() }.chunked(axes)
            return when (type) {
                1 -> { val p = coords(map(g, "point")).single()
                       GeometryValue(1, labels, if (p.all { it.isNaN() }) emptyList() else listOf(p)) }
                2 -> GeometryValue(2, labels, coords(map(g, "lineString")))
                3 -> GeometryValue(3, labels, children = list(map(g, "polygon"), "rings").map { GeometryValue(2, labels, coords(it)) })
                else -> GeometryValue(type, labels, children = list(map(g, "collection"), "geometries").map { fold(it) })
            }
        }
    }
}
```

- [ ] **Step 3: Run it to verify it fails**

Run (hexplain-tools): `.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.WkbParityTest"`
Expected: FAIL — `compile diagnostics for wkb/wkb.hx` because the fixture file does not exist.

- [ ] **Step 4: Write the module**

`hexplain-profiles/profiles/wkb/wkb.hx`:

```
// Hexplain Profile module — ISO/OGC well-known binary geometry (ISO 19125-1; OGC 06-103r4 §8.2.8)
//
// A module rather than a format: nobody opens a bare .wkb, but GeoPackage geometry blobs,
// PostGIS, SpatiaLite, Parquet GEOMETRY columns and MySQL all carry one. `gpkgblob` imports it.
//
// Every geometry, at every nesting level, begins with its OWN byte-order byte and type code:
//
//   byteOrder  1  0 = XDR (big-endian), 1 = NDR (little-endian)
//   wkbType    4  1 Point, 2 LineString, 3 Polygon, 4 MultiPoint, 5 MultiLineString,
//                 6 MultiPolygon, 7 GeometryCollection; +1000 Z, +2000 M, +3000 ZM
//   body         type-dependent: a point is `axes` doubles; a line string is a count and
//                that many points; a polygon is a ring count and rings, each a count and
//                points; every collection is a count and that many complete geometries.
//
// The byte order applies to the type code and to everything in the body, including the rings
// of a polygon, which carry no byte-order byte of their own. Each body struct therefore starts
// with a zero-byte `derive` copy of the enclosing geometry's byteOrder and switches its own
// endianness on it before its first physical field. A collection member is a full Geometry,
// so it re-declares its order and may differ from its parent's.
//
// Source: OGC 06-103r4, "OpenGIS Implementation Standard for Geographic information -- Simple
// feature access -- Part 1: Common architecture", clause 8.2.8 (well-known binary).
// Verification status: parse-verified — WkbParityTest in hexplain-tools parses all 136 GDAL
// 3.13.3 oracle cases (types 1-7, four ordinate sets, both byte orders, empty and nonempty)
// and matches GDAL's decoded coordinates exactly.

module wkb @namespace "https://hexplain.io/ns/profile/wkb#"

use ageom: <https://hexplain.io/ns/aspect/geometry#>
use rgeo:  <https://hexplain.io/ns/register/geometry-type#>

// hx-geometry does not import a concept register; the profile says which one fills geometryType.
register ageom:geometryType from rgeo:GeometryTypeScheme

@root struct Geometry
  @label "WKB geometry"
  @comment "One well-known-binary geometry: byte order, type code, then a type-dependent body. Recursive through collections."
  @endian switch {
    when [byteOrder == 1] => little
    when [byteOrder == 0] => big
  }
{
  byteOrder : u8 enum { 0, 1 }
    @label "byte order"
    @comment "0 = XDR (big-endian), 1 = NDR (little-endian). Governs the type code and the whole body."

  // The raw code IS the geometry type: 28 arms rather than a derived kind, so the mapping needs no
  // arithmetic and a reader of the Turtle sees every code the module accepts.
  wkbType : u32 enum {
      1 => rgeo:Point,    2 => rgeo:LineString,    3 => rgeo:Polygon,    4 => rgeo:MultiPoint,
      5 => rgeo:MultiLineString,    6 => rgeo:MultiPolygon,    7 => rgeo:GeometryCollection,
      1001 => rgeo:Point, 1002 => rgeo:LineString, 1003 => rgeo:Polygon, 1004 => rgeo:MultiPoint,
      1005 => rgeo:MultiLineString, 1006 => rgeo:MultiPolygon, 1007 => rgeo:GeometryCollection,
      2001 => rgeo:Point, 2002 => rgeo:LineString, 2003 => rgeo:Polygon, 2004 => rgeo:MultiPoint,
      2005 => rgeo:MultiLineString, 2006 => rgeo:MultiPolygon, 2007 => rgeo:GeometryCollection,
      3001 => rgeo:Point, 3002 => rgeo:LineString, 3003 => rgeo:Polygon, 3004 => rgeo:MultiPoint,
      3005 => rgeo:MultiLineString, 3006 => rgeo:MultiPolygon, 3007 => rgeo:GeometryCollection
    } means ageom:geometryType
    @label "geometry type code"
    @comment "ISO WKB type: the base type plus 1000 for Z, 2000 for M, 3000 for ZM."

  // Ordinates per coordinate: 2 for XY, 3 for XYZ or XYM, 4 for XYZM. HEL integer division.
  axes : derive [2 + ((wkbType / 1000) == 3 ? 2 : ((wkbType / 1000) == 0 ? 0 : 1))]
    means ageom:dimensionality
    @label "ordinates per coordinate"

  hasZ : derive [(wkbType / 1000) == 1 || (wkbType / 1000) == 3] means ageom:hasZ
    @label "has Z"
  hasM : derive [(wkbType / 1000) >= 2] means ageom:hasM
    @label "has M"
    @comment "An M ordinate is a measure. It is not implicitly time and not elevation."

  // Exactly one body is present. A struct-typed field consumes what its struct reads, which is
  // why these are presence-guarded fields rather than a sized payload with a switch: no size
  // precedes a WKB body, so there is nothing to bound a `bytes[n] switch` with.
  point      : PointBody      if [wkbType % 1000 == 1] @label "point body"
  lineString : LineStringBody if [wkbType % 1000 == 2] @label "line string body"
  polygon    : PolygonBody    if [wkbType % 1000 == 3] @label "polygon body"
  collection : CollectionBody if [wkbType % 1000 >= 4] @label "collection body"
}

struct PointBody
  @label "point body"
  @endian switch { when [order == 1] => little  when [order == 0] => big }
{
  order  : derive [parent.byteOrder]
  coords : f64 repeat [parent.axes]
    @label "coordinates"
    @comment "An empty point is written as all-NaN ordinates."
}

struct LineStringBody
  @label "line string body"
  @endian switch { when [order == 1] => little  when [order == 0] => big }
{
  order     : derive [parent.byteOrder]
  axes      : derive [parent.axes]
  numPoints : u32 @label "point count"
  coords    : f64 repeat [numPoints * axes] @label "coordinates, point-major"
}

struct PolygonBody
  @label "polygon body"
  @endian switch { when [order == 1] => little  when [order == 0] => big }
{
  order    : derive [parent.byteOrder]
  axes     : derive [parent.axes]
  numRings : u32 @label "ring count"
    @comment "The first ring is the exterior; any others are holes."
  rings    : LinearRing repeat [numRings] @label "rings"
}

struct LinearRing
  @label "linear ring"
  @comment "A closed line without its own byte order or type code: it inherits the polygon's."
  @endian switch { when [order == 1] => little  when [order == 0] => big }
{
  order     : derive [parent.order]
  axes      : derive [parent.axes]
  numPoints : u32 @label "point count"
  coords    : f64 repeat [numPoints * axes] @label "coordinates, point-major"
}

struct CollectionBody
  @label "collection body"
  @endian switch { when [order == 1] => little  when [order == 0] => big }
{
  order         : derive [parent.byteOrder]
  numGeometries : u32 @label "member count"
  geometries    : Geometry repeat [numGeometries] @label "members"
    @comment "Each member is a complete geometry with its own byte order and type code."
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. Types 8 and above (CircularString, CompoundCurve, CurvePolygon, MultiCurve, MultiSurface,
//    PolyhedralSurface, TIN, Triangle) are not modelled. A code outside the 28 enumerated
//    values is a validation failure, not a silent skip.
// 2. EWKB (PostGIS) sets flag bits 0x80000000 / 0x40000000 / 0x20000000 in the type word and
//    may embed an SRID after it. Not modelled; such a value fails the enumeration.
// 3. Ring closure, ring orientation, minimum point counts and finite ordinates are semantic
//    rules the physical description does not check. The reference engine's decoder does.
// 4. Collection member consistency (a MultiPolygon member being a Polygon, members sharing
//    the parent's ordinate set) is not enforced here.
```

- [ ] **Step 5: Copy the fixture and run the test**

Run (from `d:/work`):
```
mkdir -p hexplain-tools/hdl/src/test/resources/profiles/wkb
cp hexplain-profiles/profiles/wkb/wkb.hx hexplain-tools/hdl/src/test/resources/profiles/wkb/wkb.hx
cd hexplain-tools && .\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.WkbParityTest"
```
Expected: 136 dynamic tests PASS.

If big-endian cases fail with mirrored coordinates while little-endian pass (or vice versa), the derive-first endianness trick did not fire. Apply the spec's fallback: move `numPoints`/`coords`/`numRings`/`numGeometries` into `Geometry` as `if [wkbType % 1000 == N]` fields, keep `LinearRing` but read each ring's `coords` under the polygon's order by making rings a `LinearRing repeat [numRings]` whose `order` derives from `parent.byteOrder`. Re-run until all 136 pass, and update the fixture copy after every edit to the canonical file.

- [ ] **Step 6: Run the library gate on the new directory**

Run (hexplain-profiles): `python tools/run_gates.py library`
Expected: `PASS  test_profile_library` with the compiled count one higher than before. If SHACL rejects `enum` on a `derive` field or the `register` line, fix the profile and re-copy the fixture.

- [ ] **Step 7: Commit both repos**

```
cd d:/work/hexplain-profiles && git add profiles/wkb && git commit -m "feat(wkb): ISO well-known binary module, parse-verified against the GDAL geometry oracle

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd d:/work/hexplain-tools && git add hdl/src/test/resources/profiles/wkb hdl/src/test/kotlin/io/hexplain/hdl/parity/ProfileFixtures.kt hdl/src/test/kotlin/io/hexplain/hdl/parity/WkbParityTest.kt && git commit -m "test(hdl): WKB module parity against the 136-case GDAL oracle; shared fixture helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: gpkgblob imports wkb

**Files:**
- Modify: `hexplain-profiles/profiles/gpkgblob/gpkgblob.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/gpkgblob/gpkgblob.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GpkgBlobParityTest.kt`

**Interfaces:**
- Consumes `WkbParityTest.fold`, `ProfileFixtures`.
- Produces root `https://hexplain.io/ns/profile/gpkgblob#GeoPackageBinary` with fields `magic`, `version`, `flags`, `srsId`, `envelope`, `geometry` (a wkb `Geometry` map).

- [ ] **Step 1: Extract a real blob from the corpus and pin it**

Run (from `d:/work/hexplain-tools/tests/gdal/cache/upstream/autotest`):
```
python - <<'EOF'
import sqlite3, base64, glob
path = glob.glob('**/2d_envelope.gpkg', recursive=True)[0]
db = sqlite3.connect(path)
table, column = db.execute("select table_name, column_name from gpkg_geometry_columns limit 1").fetchone()
blob = db.execute(f'select "{column}" from "{table}" where "{column}" is not null limit 1').fetchone()[0]
print(path); print(table, column, len(blob)); print(base64.b64encode(blob).decode())
EOF
```
Copy the printed path, table, length and base64 into the test below (replace `PIN_PATH`, `PIN_LEN`, `PIN_B64`).

- [ ] **Step 2: Write the failing test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/GpkgBlobParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.raster.GeometryDecoder
import io.hexplain.hdl.parity.ProfileFixtures.int
import io.hexplain.hdl.parity.ProfileFixtures.map
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import java.util.Base64

/** A GeoPackage geometry blob taken from PIN_PATH (table PIN_TABLE), decomposed through gpkgblob -> wkb. */
class GpkgBlobParityTest {
    private val blob: ByteArray = Base64.getDecoder().decode("PIN_B64")
    private val ir by lazy { ProfileFixtures.formatIR("gpkgblob/gpkgblob.hx", "https://hexplain.io/ns/profile/gpkgblob#GeoPackageBinary") }

    @Test fun `envelope header and nested geometry agree with the hand-written decoder`() {
        assertEquals(PIN_LEN, blob.size)
        val parsed = ProfileFixtures.parse(ir, blob)
        val reference = GeometryDecoder().geoPackage(blob)
        assertEquals(reference.srsId, int(parsed, "srsId"))
        assertEquals(reference.envelope.size * 8, (parsed["envelope"] as ByteArray).size)
        assertEquals(reference.geometry, WkbParityTest.fold(map(parsed, "geometry")))
    }
}
```

- [ ] **Step 3: Run it to verify it fails**

Run (hexplain-tools): `.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.GpkgBlobParityTest"`
Expected: FAIL — fixture `gpkgblob/gpkgblob.hx` does not exist under test resources.

- [ ] **Step 4: Modify the profile**

In `hexplain-profiles/profiles/gpkgblob/gpkgblob.hx`:

1. After `use xsd: ...` add:
```
import "../wkb/wkb.hx" as wkb
```
2. Replace the `wkb : bytes[..]` field and its comments with:
```
  geometry : wkb:Geometry
    @label "geometry"
    @comment "ISO/OGC well-known binary, decomposed by the wkb module. An empty geometry (flag bit 4) is still a complete WKB value with zero-length bodies; it is distinct from an absent envelope."
```
3. Replace limit 1 with:
```
// 1. THE WKB IS DECOMPOSED by the imported wkb module down to individual ordinates. Its own
//    limits (no curve types, no EWKB, no semantic ring checks) apply here unchanged.
```
4. Replace limit 3 with:
```
// 3. THE GEOMETRY'S TYPE AND ORDINATE SET ARE MAPPED (ageom:geometryType, hasZ, hasM,
//    dimensionality) by the wkb module. There is still no property meaning "this field IS the
//    geometry"; GeoSPARQL's geo:asWKB would be the target and remains unreachable for the
//    reason given before: hexplain:MapsToPropertyShape requires a loaded declaration.
```
5. Update the header's `Verification status:` line to:
```
// Verification status: parse-verified — GpkgBlobParityTest in hexplain-tools parses a blob
// from GDAL's 2d_envelope.gpkg fixture and agrees with the engine's hand-written decoder on
// SRS id, envelope size and every nested ordinate.
```

- [ ] **Step 5: Copy fixture, run test**

```
mkdir -p d:/work/hexplain-tools/hdl/src/test/resources/profiles/gpkgblob
cp d:/work/hexplain-profiles/profiles/gpkgblob/gpkgblob.hx d:/work/hexplain-tools/hdl/src/test/resources/profiles/gpkgblob/gpkgblob.hx
cd d:/work/hexplain-tools && .\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.GpkgBlobParityTest"
```
Expected: PASS. If `HdlCompiler.compileFile` cannot resolve `../wkb/wkb.hx` from the fixture directory, check how `heif/heif.hx` resolves `../iso-bmff/iso-bmff.hx` in `HeifModulesParityTest` and match it.

- [ ] **Step 6: Library gate and commit**

Run (hexplain-profiles): `python tools/run_gates.py library` — expected PASS.

```
cd d:/work/hexplain-profiles && git add profiles/gpkgblob && git commit -m "feat(gpkgblob): decompose the WKB payload through the wkb module

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd d:/work/hexplain-tools && git add hdl/src/test/resources/profiles/gpkgblob hdl/src/test/kotlin/io/hexplain/hdl/parity/GpkgBlobParityTest.kt && git commit -m "test(hdl): GeoPackage blob parity through gpkgblob and the wkb module

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `bmp`

**Files:**
- Create: `hexplain-profiles/profiles/bmp/bmp.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/bmp/bmp.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/BmpParityTest.kt`

**Interfaces:**
- Produces root `https://hexplain.io/ns/profile/bmp#BmpFile` with `fileHeader{bfType,bfSize,bfOffBits}`, `info{biSize,biWidth,biHeight,biPlanes,biBitCount,biCompression,...}`, derived `height`, `bands`, `rowStride`, `paletteEntries`, `palette` (list), `rows` (list of `Row` with `samples`/`samples16`/`samples32` as `MultiDimensionalData.IntData`, or `packed`).

- [ ] **Step 1: Write the failing test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/BmpParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.hdl.parity.ProfileFixtures.corpus
import io.hexplain.hdl.parity.ProfileFixtures.int
import io.hexplain.hdl.parity.ProfileFixtures.list
import io.hexplain.hdl.parity.ProfileFixtures.map
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import java.io.ByteArrayOutputStream
import java.nio.file.Files

/**
 * bmp against GDAL 3.13.3's recorded decode of the autotest samples (tests/gdal/results/oracle.jsonl):
 * width, height, band count and the SHA-256 of every pixel in band-sequential order, top row first.
 */
class BmpParityTest {
    private val ir by lazy { ProfileFixtures.formatIR("bmp/bmp.hx", "https://hexplain.io/ns/profile/bmp#BmpFile") }
    private fun sample(rel: String) = corpus.resolve("gcore/data").resolve(rel).also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    private fun header(p: Map<*, *>) = Triple(int(map(p, "info"), "biWidth"), int(p, "height"), int(p, "bands"))

    /** Band-sequential samples, top row first, BGR reordered to RGB, as GDAL reports them. */
    private fun pixels(p: Map<*, *>): ByteArray {
        val (w, h, bands) = header(p)
        val rows = list(p, "rows")
        val topDown = int(map(p, "info"), "biHeight") < 0
        val out = ByteArrayOutputStream()
        for (b in 0 until bands) {
            val source = if (bands == 3) 2 - b else 0 // B G R stored -> R G B reported
            for (r in 0 until h) {
                val row = rows[if (topDown) r else h - 1 - r]
                val data = row["samples"] as MultiDimensionalData.IntData
                for (x in 0 until w) out.write(data.getInt(x, source))
            }
        }
        return out.toByteArray()
    }

    @Test fun `8bit_pal - 20x20 palette indices`() {
        val p = ProfileFixtures.parseFile(ir, sample("8bit_pal.bmp"))
        assertEquals(Triple(20, 20, 1), header(p))
        assertEquals(256, list(p, "palette").size)
        assertEquals(1078, int(map(p, "fileHeader"), "bfOffBits"))
        assertEquals("b55a841b7b95be907f6bb0d358b8d10c9dce6e485381eb9accb71e653597d9a1", ProfileFixtures.sha256(pixels(p)))
    }

    @Test fun `red_rgb_1x1 - 24-bit BGR triple with row padding`() {
        val p = ProfileFixtures.parseFile(ir, sample("bmp/red_rgb_1x1.bmp"))
        assertEquals(Triple(1, 1, 3), header(p))
        assertEquals(4, int(p, "rowStride"))
        assertEquals("7fa54a42524916a1648ec76ce75d295024840b7a3a4f4bbaf3e43155d0014767", ProfileFixtures.sha256(pixels(p)))
    }

    @Test fun `sub-byte samples are described but the accessor refuses to execute them`() {
        for (name in listOf("1bit.bmp", "4bit_pal.bmp")) {
            val outcome = runCatching { ProfileFixtures.parseFile(ir, sample(name)) }
            val message = outcome.exceptionOrNull()?.message ?: ""
            assertTrue(message.contains("dlv:cellBitWidthFromField"), "$name: expected the packed layout to be refused by name, got $outcome")
        }
    }

    @Test fun `compressed files parse their headers and carry no pixel rows`() {
        val p = ProfileFixtures.parseFile(ir, sample("4bit_rle4.bmp"))
        assertEquals(2, int(map(p, "info"), "biCompression"))
        assertTrue(p["rows"] == null, "rows must be absent when biCompression != 0")
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run (hexplain-tools): `.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.BmpParityTest"`
Expected: FAIL — fixture missing.

- [ ] **Step 3: Write the profile**

`hexplain-profiles/profiles/bmp/bmp.hx`:

```
// Hexplain Profile — Windows device-independent bitmap (BMP)
//
// The simplest raster with a real header, and GDAL's BMP driver reads it. Everything is
// little-endian. Two headers, an optional palette, then rows of pixels:
//
//   BITMAPFILEHEADER  14  "BM", file size, two reserved words, offset of the pixel array
//   BITMAPINFOHEADER  40  biSize (40, or 108/124 for the V4/V5 extensions), width, height
//                         (NEGATIVE = top-down), planes, bits per pixel, compression, ...
//   palette            4 x N  B G R reserved, only when bits per pixel <= 8
//   pixel rows            each row padded to a multiple of 4 bytes; BOTTOM row first unless
//                         the height is negative
//
// Rows are described as records, not as one strided grid. A row is a padded record -- the
// padding is real bytes with a real position -- and describing it that way makes every row an
// executable DLV layout with contiguous cells, which is the subset the reference accessor
// runs. A single `dim axis Y ... stride rowStride` grid would say the same thing more tersely
// and is not executable today (dlv:dimensionStrideFromExpression is declared but refused).
//
// Source: Microsoft, "Bitmap Storage" / BITMAPFILEHEADER, BITMAPINFOHEADER (Windows GDI docs).
// Verification status: parse-verified — BmpParityTest in hexplain-tools matches GDAL 3.13.3's
// pixel digests for autotest/gcore/data/8bit_pal.bmp (8-bit palette) and
// bmp/red_rgb_1x1.bmp (24-bit with row padding); 1bit.bmp and 4bit_pal.bmp parse their
// headers and are refused, by name, at the packed row layout (see limit 1).

format bmp @namespace "https://hexplain.io/ns/profile/bmp#" @endian little

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>

@root struct BmpFile
  @label "BMP file"
  @comment "File header, info header, optional palette, then padded pixel rows located by bfOffBits."
{
  fileHeader : FileHeader @label "BITMAPFILEHEADER"
  info       : InfoHeader @label "BITMAPINFOHEADER (with any V4/V5 extension)"

  // Negative height means top-down rows; the magnitude is the row count either way.
  height : derive [info.biHeight < 0 ? 0 - info.biHeight : info.biHeight] means araster:height
    @label "row count"
  bands : derive [info.biBitCount == 24 ? 3 : 1] means asamp:componentCount
    @label "samples per pixel"
    @comment "24-bit rows carry B, G, R triples. Every other depth is one sample: an index into the palette, or a packed 16/32-bit value whose channel masks are not decomposed here."
  rowStride : derive [((info.biWidth * info.biBitCount + 31) / 32) * 4]
    @label "bytes per row, padded to a multiple of 4"

  // A zero biClrUsed means "the full table for this depth": 2^bits entries.
  paletteEntries : derive [info.biClrUsed == 0 ? (1 << info.biBitCount) : info.biClrUsed]
    @label "palette entry count"
  palette : PaletteEntry repeat [paletteEntries] if [info.biBitCount <= 8]
    @label "colour table"

  // Only uncompressed pixel arrays are described (limit 2). The rows sit at bfOffBits, which is
  // usually right after the palette but need not be.
  rows : Row repeat [height] @at fileHeader.bfOffBits from stream-start if [info.biCompression == 0]
    @label "pixel rows, in file order"
}

struct FileHeader @label "BITMAPFILEHEADER" {
  bfType      : ascii[2] @fixed "BM" @label "signature"
  bfSize      : u32 @label "file size in bytes"
  bfReserved1 : u16
  bfReserved2 : u16
  bfOffBits   : u32 @label "offset of the pixel array from the start of the file"
}

struct InfoHeader
  @label "BITMAPINFOHEADER"
  @comment "The 40-byte Windows 3.x header. A V4 (108) or V5 (124) header keeps these fields at the same offsets and appends colour-space data, consumed as `extension`."
{
  biSize          : u32 @label "header size" @comment "40, 108 or 124. The 12-byte OS/2 BITMAPCOREHEADER is not modelled (limit 3)."
  biWidth         : i32 means araster:width @label "width in pixels"
  biHeight        : i32 @label "height in pixels; negative means top-down"
  biPlanes        : u16 @label "colour planes, always 1"
  biBitCount      : u16 enum { 1, 4, 8, 16, 24, 32 } means asamp:bitDepth @label "bits per pixel"
  biCompression   : u32 enum { 0, 1, 2, 3, 4, 5, 6 } @label "compression" @comment "0 BI_RGB, 1 BI_RLE8, 2 BI_RLE4, 3 BI_BITFIELDS, 4 BI_JPEG, 5 BI_PNG, 6 BI_ALPHABITFIELDS."
  biSizeImage     : u32 @label "pixel array size; may be 0 for BI_RGB"
  biXPelsPerMeter : i32 @label "horizontal resolution"
  biYPelsPerMeter : i32 @label "vertical resolution"
  biClrUsed       : u32 @label "palette entries used; 0 means all for the depth"
  biClrImportant  : u32 @label "palette entries required"
  extension       : bytes[biSize - 40] @label "V4/V5 fields (masks, colour space, gamma, intent)"
}

struct PaletteEntry @label "RGBQUAD" {
  blue     : u8
  green    : u8
  red      : u8
  reserved : u8
}

struct Row
  @label "one scan line"
  @comment "Pixels then zero padding to a 4-byte boundary. Exactly one of the sample fields is present, chosen by depth."
{
  width : derive [parent.info.biWidth]
  bits  : derive [parent.info.biBitCount]
  bands : derive [parent.bands]
  used  : derive [(width * bits + 7) / 8] @label "bytes carrying pixels"

  packed : bytes[used] layout cell u8 { cell-bits from bits  packing msb  dim axis X size width } if [bits < 8]
    @label "packed 1- or 4-bit palette indices, most significant bits first"
  samples : bytes[used] layout cell u8 { dim axis X size width  dim axis Band size bands } if [bits == 8 || bits == 24]
    @label "8-bit indices, or 24-bit B G R triples"
  samples16 : bytes[used] layout cell u16le { dim axis X size width } if [bits == 16]
    @label "16-bit packed pixels (5-5-5 or per bitfield masks)"
  samples32 : bytes[used] layout cell u32le { dim axis X size width } if [bits == 32]
    @label "32-bit packed pixels (8-8-8-8 or per bitfield masks)"
  padding : bytes[parent.rowStride - used] @label "row padding"
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. SUB-BYTE ROWS ARE DESCRIBED, NOT EXECUTED. `packed` states cell-bits from biBitCount with
//    MSB-first packing, which is exact; the reference accessor refuses dlv:cellBitWidthFromField
//    by name rather than reading wrong values. The 1-bit and 4-bit samples in the corpus stop
//    there. Nothing in the description is wrong for them; the engine has not caught up.
// 2. COMPRESSED PIXEL ARRAYS (RLE4, RLE8, BI_JPEG, BI_PNG) are not described: `rows` is absent
//    when biCompression != 0. BI_BITFIELDS masks in the V4/V5 extension are consumed as bytes,
//    so a 16/32-bit pixel is a packed integer here, not decomposed channels.
// 3. The 12-byte OS/2 BITMAPCOREHEADER (biSize == 12) is rejected by `extension`'s negative size,
//    which is the correct outcome for a header this description does not model.
// 4. ROW ORDER IS A CONVENTION DLV CANNOT STATE. Rows are in file order; bottom-up unless
//    biHeight is negative. A consumer flips; the parity test does.
// 5. Palette entries are not lifted to a colour aspect; hx-color has no palette term yet.
```

- [ ] **Step 4: Copy the fixture and run the test**

```
mkdir -p d:/work/hexplain-tools/hdl/src/test/resources/profiles/bmp
cp d:/work/hexplain-profiles/profiles/bmp/bmp.hx d:/work/hexplain-tools/hdl/src/test/resources/profiles/bmp/bmp.hx
cd d:/work/hexplain-tools && .\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.BmpParityTest"
```
Expected: 4 tests PASS. Known adjustments if a test fails:
- `1 << info.biBitCount` unsupported in HEL: replace with `(info.biBitCount == 1 ? 2 : (info.biBitCount == 4 ? 16 : 256))`.
- The refusal test fails because the parser recovers and returns a tree: assert instead that the returned row map has no `packed` key and that `Metaparser` diagnostics (see `MetaparserRecoveryTest` for the accessor) mention `dlv:cellBitWidthFromField`.
- `data.getInt(x, source)` index order: the accessor takes indices in declared dimension order (X, Band); if it fails, print `data.describe()` and adjust.

- [ ] **Step 5: Library gate and commit**

Run (hexplain-profiles): `python tools/run_gates.py library` — expected PASS.

```
cd d:/work/hexplain-profiles && git add profiles/bmp && git commit -m "feat(bmp): Windows bitmap profile, pixel-verified against GDAL for 8-bit and 24-bit samples

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd d:/work/hexplain-tools && git add hdl/src/test/resources/profiles/bmp hdl/src/test/kotlin/io/hexplain/hdl/parity/BmpParityTest.kt && git commit -m "test(hdl): BMP parity against GDAL pixel digests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `dted`

**Files:**
- Create: `hexplain-profiles/profiles/dted/dted.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/dted/dted.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/DtedParityTest.kt`

**Interfaces:**
- Produces root `https://hexplain.io/ns/profile/dted#DtedFile` with `uhl{lonOrigin,latOrigin,lonInterval,latInterval,nlon,nlat,originLongitude,originLatitude}`, `dsi{...}`, `acc{...}`, `columns` (list of `DataRecord` with `elevations` as `MultiDimensionalData.IntData` indexed by Y).

- [ ] **Step 1: Write the failing test**

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/DtedParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.metacodec.MultiDimensionalData
import io.hexplain.hdl.parity.ProfileFixtures.corpus
import io.hexplain.hdl.parity.ProfileFixtures.int
import io.hexplain.hdl.parity.ProfileFixtures.list
import io.hexplain.hdl.parity.ProfileFixtures.map
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.Files

/**
 * dted against GDAL 3.13.3's decode of autotest/gdrivers/data/dted/n43_wgs72.dt0: 121 x 121 Int16,
 * digest over little-endian samples, north row first. DTED stores columns south-to-north in
 * signed-magnitude; the test performs both conversions the profile states as limits.
 */
class DtedParityTest {
    private val ir by lazy { ProfileFixtures.formatIR("dted/dted.hx", "https://hexplain.io/ns/profile/dted#DtedFile") }
    private fun sample(name: String) = corpus.resolve("gdrivers/data/dted").resolve(name).also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    private fun signedMagnitude(raw: Int): Int = if (raw and 0x8000 != 0) -(raw and 0x7FFF) else raw

    @Test fun `n43_wgs72 - header, origin and every elevation`() {
        val p = ProfileFixtures.parseFile(ir, sample("n43_wgs72.dt0"))
        val uhl = map(p, "uhl")
        assertEquals(121, int(uhl, "nlon")); assertEquals(121, int(uhl, "nlat"))
        assertEquals("0800000W", uhl["lonOrigin"]); assertEquals("0430000N", uhl["latOrigin"])
        assertEquals(-80.0, (uhl["originLongitude"] as Number).toDouble(), 1e-9)
        assertEquals(43.0, (uhl["originLatitude"] as Number).toDouble(), 1e-9)
        val columns = list(p, "columns")
        assertEquals(121, columns.size)
        val nlat = 121; val nlon = 121
        val out = ByteBuffer.allocate(nlat * nlon * 2).order(ByteOrder.LITTLE_ENDIAN)
        for (r in 0 until nlat) for (c in 0 until nlon) {
            val col = columns[c]["elevations"] as MultiDimensionalData.IntData
            out.putShort(signedMagnitude(col.getInt(nlat - 1 - r)).toShort())
        }
        assertEquals("338756b72409f50c2b961a4ec79807cdfc77eaa099b900cdbe6312195a8bc778", ProfileFixtures.sha256(out.array()))
    }

    @Test fun `a bad checksum still parses - checksums are not verified`() {
        val p = ProfileFixtures.parseFile(ir, sample("n43_bad_crc.dt0"))
        assertEquals(121, list(p, "columns").size)
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run (hexplain-tools): `.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.DtedParityTest"`
Expected: FAIL — fixture missing.

- [ ] **Step 3: Write the profile**

`hexplain-profiles/profiles/dted/dted.hx`:

```
// Hexplain Profile — Digital Terrain Elevation Data (DTED), MIL-PRF-89020B
//
// Three fixed-width ASCII header records, then one binary record per LONGITUDE column:
//
//   UHL   80  user header label: origin (DDDMMSSH), intervals (tenths of arc-seconds),
//             accuracy, security, NLON / NLAT counts
//   DSI  648  data set identification: datums, edition, corners, orientation, counts again
//   ACC 2700  accuracy description
//   NLON x    data record: 0xAA sentinel, 3-byte block count, longitude count (column
//             index), latitude count (starting row), NLAT big-endian 16-bit elevations in
//             SIGNED-MAGNITUDE, 4-byte checksum. Each column runs SOUTH to NORTH.
//
// The record form is the primary description. Each column's elevation block is an executable
// one-dimensional layout; assembling a north-up grid is a transpose and a flip, both stated
// below as limits because DLV declares dimension order and cell width, not orientation. The
// per-column overhead (12 bytes) would otherwise be a stride expression, which the reference
// accessor does not execute.
//
// Source: MIL-PRF-89020B, Performance Specification, Digital Terrain Elevation Data (DTED),
// section 3.9 (UHL), 3.10 (DSI), 3.11 (ACC), 3.12 (data records).
// Verification status: parse-verified — DtedParityTest in hexplain-tools matches GDAL 3.13.3's
// pixel digest for autotest/gdrivers/data/dted/n43_wgs72.dt0 (121 x 121, DTED level 0) after
// the two conversions named in limits 1 and 2, and checks the decimal origin derived from UHL.

format dted @namespace "https://hexplain.io/ns/profile/dted#" @endian big

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>
use xsd:     <http://www.w3.org/2001/XMLSchema#>

@root struct DtedFile
  @label "DTED cell"
  @comment "UHL, DSI and ACC header records followed by NLON longitude-column data records."
{
  uhl     : UserHeaderLabel @label "UHL"
  dsi     : DataSetIdentification @label "DSI"
  acc     : AccuracyDescription @label "ACC"
  columns : DataRecord repeat [uhl.nlon] @label "data records, one per longitude column, west to east"

  raw-turtle {
    :DtedFile araster:noDataValue -32767 ;
        asamp:bitDepth 16 ;
        asref:epsgCode 4326 .
  }
}

struct UserHeaderLabel @label "User Header Label (UHL), 80 bytes" {
  sentinel : ascii[3] @fixed "UHL"
  version  : ascii[1] @fixed "1"
  lonOrigin : ascii[8] @label "longitude of origin, DDDMMSSH" @comment "South-west corner of the cell."
  latOrigin : ascii[8] @label "latitude of origin, DDDMMSSH"
  lonInterval : anum[4] means asref:scaleX value lonInterval / 36000.0 @datatype xsd:double
    @label "longitude data interval, tenths of arc-seconds"
  latInterval : anum[4] means asref:scaleY value latInterval / 36000.0 @datatype xsd:double
    @label "latitude data interval, tenths of arc-seconds"
  absoluteVerticalAccuracy : ascii[4] @label "absolute vertical accuracy in metres, or NA"
  securityCode : ascii[3] @label "security code"
  uniqueReference : ascii[12] @label "unique reference number"
  nlon : anum[4] means araster:width @label "number of longitude lines (columns)"
  nlat : anum[4] means araster:height @label "number of latitude points per column (rows)"
  multipleAccuracy : ascii[1] @label "multiple accuracy flag"
  reserved : bytes[24]

  // DDDMMSSH -> signed decimal degrees, computed once here so the mapping carries a number.
  originLongitude : derive [ (toNumber(substring(lonOrigin, 0, 3)) + toNumber(substring(lonOrigin, 3, 2)) / 60.0
                              + toNumber(substring(lonOrigin, 5, 2)) / 3600.0)
                             * (substring(lonOrigin, 7, 1) == "W" ? 0 - 1 : 1) ]
    means asref:originLongitude @label "origin longitude, decimal degrees"
  originLatitude : derive [ (toNumber(substring(latOrigin, 0, 3)) + toNumber(substring(latOrigin, 3, 2)) / 60.0
                             + toNumber(substring(latOrigin, 5, 2)) / 3600.0)
                            * (substring(latOrigin, 7, 1) == "S" ? 0 - 1 : 1) ]
    means asref:originLatitude @label "origin latitude, decimal degrees"
}

struct DataSetIdentification @label "Data Set Identification (DSI), 648 bytes" {
  sentinel : ascii[3] @fixed "DSI"
  securityClassification : ascii[1]
  securityControl : ascii[2]
  securityHandling : ascii[27]
  reserved1 : bytes[26]
  seriesDesignator : ascii[5] @label "NIMA series designator (DTED0/DTED1/DTED2)"
  uniqueReference : ascii[15]
  reserved2 : bytes[8]
  dataEdition : ascii[2]
  matchMergeVersion : ascii[1]
  maintenanceDate : ascii[4] @label "YYMM"
  matchMergeDate : ascii[4] @label "YYMM"
  maintenanceDescription : ascii[4]
  producerCode : ascii[8]
  reserved3 : bytes[16]
  productSpecification : ascii[9]
  productSpecificationAmendment : ascii[2]
  productSpecificationDate : ascii[4] @label "YYMM"
  verticalDatum : ascii[3] @label "MSL or E96"
  horizontalDatum : ascii[5] @label "WGS84 or WGS72"
  digitizingSystem : ascii[10]
  compilationDate : ascii[4] @label "YYMM"
  reserved4 : bytes[22]
  latOrigin : ascii[9] @label "DDMMSS.SH"
  lonOrigin : ascii[10] @label "DDDMMSS.SH"
  swLatitude : ascii[7] @label "DDMMSSH"
  swLongitude : ascii[8] @label "DDDMMSSH"
  nwLatitude : ascii[7]
  nwLongitude : ascii[8]
  neLatitude : ascii[7]
  neLongitude : ascii[8]
  seLatitude : ascii[7]
  seLongitude : ascii[8]
  orientation : ascii[9] @label "clockwise orientation angle, DDDMMSS.S, always 0"
  latInterval : anum[4] @label "tenths of arc-seconds"
  lonInterval : anum[4] @label "tenths of arc-seconds"
  nlat : anum[4] @label "rows"
  nlon : anum[4] @label "columns"
  partialCellIndicator : ascii[2] @label "00 = full cell, else percent coverage"
  reserved5 : bytes[357] @label "101 NIMA + 100 producer + 156 reserved"
}

struct AccuracyDescription @label "Accuracy Description (ACC), 2700 bytes" {
  sentinel : ascii[3] @fixed "ACC"
  absoluteHorizontal : ascii[4] @label "metres, or NA"
  absoluteVertical : ascii[4]
  relativeHorizontal : ascii[4]
  relativeVertical : ascii[4]
  reserved : bytes[2681] @label "accuracy sub-regions and reserved space"
}

struct DataRecord
  @label "longitude column"
  @comment "One column of elevations, south to north, framed by a sentinel, counts and a checksum."
{
  sentinel   : u8 @fixed 0xAA @label "recognition sentinel"
  blockCount : bytes[3] @label "data block count, 24-bit"
  lonCount   : u16 @label "longitude count (column index from the west edge)"
  latCount   : u16 @label "latitude count (starting row, 0)"
  nlat       : derive [root.uhl.nlat]
  elevations : bytes[nlat * 2] layout cell u16be { dim axis Y size nlat }
    @label "elevations, signed-magnitude 16-bit, south to north"
  checksum   : u32 @label "sum of the record's bytes from the sentinel through the elevations"
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. ELEVATIONS ARE SIGNED-MAGNITUDE: bit 15 is the sign, bits 0-14 the magnitude, and
//    0xFFFF (-32767) is the void value. BDDO has no signed-magnitude datatype, so the cell is
//    declared u16 and the conversion is stated here: v = (raw & 0x8000) ? -(raw & 0x7FFF) : raw.
// 2. ORIENTATION. Columns run west to east and each column runs SOUTH to NORTH. A north-up
//    row-major grid is the transpose with rows reversed. DLV declares order and width, not
//    direction, so a consumer applies the flip; the parity test does.
// 3. THE CHECKSUM IS NOT VERIFIED. bddo has a checksum clause, but the DTED sum is an
//    unsigned 32-bit byte sum, which is not one of the registered algorithms.
// 4. Partial cells (DSI partialCellIndicator != "00") and sparse columns are carried as
//    written; nothing here fills or validates coverage.
// 5. Heights are relative to the vertical datum named in DSI (MSL or EGM96). asref models the
//    horizontal CRS only, so epsgCode 4326 understates the vertical reference.
```

- [ ] **Step 4: Copy the fixture and run the test**

```
mkdir -p d:/work/hexplain-tools/hdl/src/test/resources/profiles/dted
cp d:/work/hexplain-profiles/profiles/dted/dted.hx d:/work/hexplain-tools/hdl/src/test/resources/profiles/dted/dted.hx
cd d:/work/hexplain-tools && .\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.DtedParityTest"
```
Expected: 2 tests PASS. Known adjustments:
- If `@fixed 0xAA` on a `u8` is rejected by the compiler, write `@fixed 170`.
- If HEL rejects mixing `toNumber(...)` integers with `60.0`, write `/ 60` and `/ 3600` and compare with a tolerance of 1e-9 (the sample origin is whole degrees). If HEL rejects the `derive` altogether, delete `originLongitude`/`originLatitude`, drop the two assertions, and add limit 6: "The origin is DDDMMSSH text; asref:originLongitude/originLatitude are not derived."
- If `value lonInterval / 36000.0 @datatype xsd:double` fails SHACL, remove the `value ... @datatype` clause and keep `means asref:scaleX`, adding a comment that the unit is tenths of arc-seconds.

- [ ] **Step 5: Library gate and commit**

Run (hexplain-profiles): `python tools/run_gates.py library` — expected PASS.

```
cd d:/work/hexplain-profiles && git add profiles/dted && git commit -m "feat(dted): DTED profile, elevation-verified against GDAL for n43_wgs72.dt0

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd d:/work/hexplain-tools && git add hdl/src/test/resources/profiles/dted hdl/src/test/kotlin/io/hexplain/hdl/parity/DtedParityTest.kt && git commit -m "test(hdl): DTED parity against GDAL's pixel digest

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `dbf`

**Files:**
- Create: `hexplain-profiles/profiles/dbf/dbf.hx`
- Create: `hexplain-tools/hdl/src/test/resources/profiles/dbf/dbf.hx` (copy)
- Test: `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/DbfParityTest.kt`

**Interfaces:**
- Produces root `https://hexplain.io/ns/profile/dbf#DbfFile` with `header{version,yy,mm,dd,numRecords,headerLength,recordLength,tableFlags,codePage}`, `descriptors` (list of `FieldDescriptor{name,type,length,decimalCount}`), `terminator`, `records` (list of `Record{deleted,data}`).

- [ ] **Step 1: Write the failing test**

Expected values were computed independently with this reader, which is kept in the test's comment:

```python
import struct
b = open(path, 'rb').read()
ver, yy, mm, dd, n, hl, rl = struct.unpack_from('<BBBBIHH', b, 0)
fields = [(b[o:o+11].split(b'\0')[0].decode('latin1'), chr(b[o+11]), b[o+16], b[o+17])
          for o in range(32, hl - 1, 32)]
```

`hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/DbfParityTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.hdl.parity.ProfileFixtures.corpus
import io.hexplain.hdl.parity.ProfileFixtures.int
import io.hexplain.hdl.parity.ProfileFixtures.list
import io.hexplain.hdl.parity.ProfileFixtures.map
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assumptions.assumeTrue
import org.junit.jupiter.api.Test
import java.nio.file.Files
import java.nio.file.Path

/**
 * dbf against four GDAL autotest tables. Expected values were computed with an independent
 * Python struct reader (see the plan, Task 5) rather than with any Hexplain code:
 *
 *   import struct
 *   b = open(path, 'rb').read()
 *   ver, yy, mm, dd, n, hl, rl = struct.unpack_from('<BBBBIHH', b, 0)
 *   fields = [(b[o:o+11].split(b'\0')[0].decode('latin1'), chr(b[o+11]), b[o+16], b[o+17]) for o in range(32, hl - 1, 32)]
 */
class DbfParityTest {
    private val ir by lazy { ProfileFixtures.formatIR("dbf/dbf.hx", "https://hexplain.io/ns/profile/dbf#DbfFile") }
    private fun sample(rel: String): Path = corpus.resolve(rel).also { assumeTrue(Files.exists(it), "corpus not fetched: $it") }

    private data class Field(val name: String, val type: String, val length: Int, val decimals: Int)
    private fun fields(p: Map<*, *>) = list(p, "descriptors").map { Field(it["name"] as String, it["type"] as String, int(it, "length"), int(it, "decimalCount")) }

    private fun check(rel: String, size: Int, date: Triple<Int, Int, Int>, n: Int, hl: Int, rl: Int, terminator: Int, expected: List<Field>) {
        val file = sample(rel)
        assertEquals(size.toLong(), Files.size(file))
        val p = ProfileFixtures.parseFile(ir, file)
        val h = map(p, "header")
        assertEquals(3, int(h, "version"))
        assertEquals(date, Triple(int(h, "yy"), int(h, "mm"), int(h, "dd")))
        assertEquals(n, int(h, "numRecords")); assertEquals(hl, int(h, "headerLength")); assertEquals(rl, int(h, "recordLength"))
        assertEquals(terminator, int(p, "terminator"))
        assertEquals(expected, fields(p).take(expected.size))
        assertEquals((hl - 33) / 32, fields(p).size)
        assertEquals(n, list(p, "records").size)
        assertTrue(hl + n * rl == size || hl + n * rl == size - 1, "record span must fill the file, less an optional 0x1A")
    }

    @Test fun `miramon categories`() = check("gdrivers/data/miramon/normal/2x3_6_categs.dbf", 409, Triple(125, 4, 7), 6, 97, 52, 0x0D,
        listOf(Field("VALUE", "N", 1, 0), Field("CATEGORY", "C", 50, 0)))

    @Test fun `raster attribute table with decimals`() = check("gcore/data/gtiff/testrat.tif.vat.dbf", 890, Triple(124, 12, 10), 2, 321, 284, 0x0D,
        listOf(Field("VALUE", "N", 9, 0), Field("COUNT", "N", 9, 0), Field("CLASS", "C", 80, 0), Field("Red", "N", 24, 15), Field("Green", "N", 24, 15), Field("Blue", "N", 24, 15)))

    @Test fun `ogr poly`() = check("ogr/data/poly.dbf", 529, Triple(118, 8, 2), 10, 129, 40, 0x0D,
        listOf(Field("AREA", "N", 12, 3), Field("EAS_ID", "N", 11, 0), Field("PRFEDEA", "C", 16, 0)))

    @Test fun `multipatch - descriptor terminator written as 0x0A`() = check("ogr/data/shp/multipatch.dbf", 78, Triple(98, 6, 8), 1, 65, 12, 0x0A,
        listOf(Field("ID", "N", 11, 0)))
}
```

- [ ] **Step 2: Run it to verify it fails**

Run (hexplain-tools): `.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.DbfParityTest"`
Expected: FAIL — fixture missing.

- [ ] **Step 3: Write the profile**

`hexplain-profiles/profiles/dbf/dbf.hx`:

```
// Hexplain Profile — xBase table file (.dbf: dBASE III+/IV/5, FoxPro, Clipper)
//
// The attribute table of every Shapefile and of every MapInfo .tab, and a raster attribute
// table beside a GeoTIFF (.vat.dbf). Three parts, all little-endian:
//
//   header        32  version byte, last-update date, record count, header length, record length
//   descriptors   32 x N  one per column: name, type letter, length, decimals; N is implied by
//                 the header length: (headerLength - 33) / 32
//   terminator     1  0x0D
//   records       recordLength x numRecords: a deletion flag (space or '*') then the columns,
//                 each of exactly the length its descriptor declares, as text
//
// The records are described as flag + bytes. Slicing a record into its columns needs the
// descriptors that precede it -- a data-driven schema, which the coverage survey names as the
// gap it is. The descriptors ARE described, so a consumer that wants columns has the widths.
//
// Source: dBASE table file format (dBASE III/IV/5 header layouts, "Xbase File Format
// Description", Erik Bachmann); Esri Shapefile Technical Description, .dbf notes.
// Verification status: parse-verified — DbfParityTest in hexplain-tools checks header fields,
// every descriptor and the record span of four GDAL autotest tables against values computed
// by an independent Python reader.

format dbf @namespace "https://hexplain.io/ns/profile/dbf#" @endian little

use atab: <https://hexplain.io/ns/aspect/tabular#>

@root struct DbfFile
  @label "xBase table"
  @comment "Header, field descriptors, terminator, then fixed-length records at headerLength."
{
  header      : Header @label "table header"
  descriptors : FieldDescriptor repeat [(header.headerLength - 33) / 32] @label "column descriptors"
    @comment "Count implied by the header length: 32 for the header, 32 per descriptor, 1 for the terminator."
  terminator  : u8 @label "descriptor terminator"
    @comment "0x0D by specification. Not pinned with @fixed: writers exist that emit 0x0A, and GDAL reads those; the value is exposed so a consumer can see the deviation."
  records     : Record repeat [header.numRecords] @at header.headerLength from stream-start @label "records"
    @comment "Located by headerLength rather than by position, so a header longer than its descriptors (dBASE 7 properties, Visual FoxPro backlinks) is skipped correctly."
}

struct Header @label "table header, 32 bytes" {
  version      : u8 enum { 2, 3, 4, 5, 7, 48, 49, 50, 67, 99, 131, 139, 203, 229, 235, 245, 251 }
    @label "version signature"
    @comment "0x03 dBASE III+/IV/5 without memo, 0x83 with .dbt memo; 0x30/0x31/0x32 Visual FoxPro; 0x04 dBASE 7 (limit 1); 0x8B dBASE IV memo; 0xF5 FoxPro memo. Upper bits encode memo and SQL-table flags."
  yy           : u8 @label "last update, years since 1900"
  mm           : u8 @label "last update, month"
  dd           : u8 @label "last update, day"
  numRecords   : u32 means atab:rowCount @label "record count"
  headerLength : u16 @label "bytes from the start of the file to the first record"
  recordLength : u16 @label "bytes per record, including the deletion flag"
  reserved1    : bytes[16]
  tableFlags   : u8 @label "0x01 structural CDX, 0x02 memo, 0x04 database container (FoxPro)"
  codePage     : u8 @label "language driver id"
  reserved2    : bytes[2]
}

struct FieldDescriptor
  @label "column descriptor, 32 bytes"
  means atab:Field
{
  name         : ascii[11] @trim-null means atab:fieldName @label "column name, NUL-padded"
  type         : ascii[1] enum { "C", "N", "F", "L", "D", "M", "I", "Y", "T", "B", "G", "P", "V", "O", "+", "@", "0" }
    means atab:fieldDataType
    @label "type letter"
    @comment "C character, N numeric text, F float text, L logical, D date YYYYMMDD, M memo pointer, I int32, Y currency, T datetime, B double (FoxPro) or binary memo (dBASE), G OLE, P picture, V varchar, O double, + autoincrement, @ timestamp, 0 nullflags."
  reserved1    : bytes[4] @label "field data address (memory-resident dBASE only)"
  length       : u8 @label "field length in bytes"
  decimalCount : u8 @label "decimal places, or the high byte of length for C fields over 255 in some writers"
  reserved2    : bytes[14] @label "work area id, MDX flag, FoxPro flags, autoincrement"
}

struct Record @label "one record" {
  deleted : ascii[1] @label "deletion flag: space = live, * = deleted"
  data    : bytes[parent.header.recordLength - 1] @label "column values, each at its descriptor's width, as text"
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. dBASE 7 (version 0x04) uses 48-byte descriptors with 32-byte names. This description
//    computes the descriptor count for 32-byte entries and would misread a version-7 table;
//    the version enumeration admits 4 so the header still parses and the mismatch is visible.
// 2. RECORD COLUMNS ARE NOT SLICED. Each record is a flag and recordLength - 1 bytes; the
//    descriptors give the widths a consumer needs to split it. Encoding is the code page named
//    by codePage (or a .cpg sidecar), not asserted here.
// 3. Memo (.dbt/.fpt) contents are outside this file.
// 4. The optional 0x1A end-of-file marker after the last record is not consumed.
// 5. atab:fieldDataType receives the raw type letter, not a datatype IRI; the tabular aspect's
//    range is a string and no register of xBase types exists yet.
```

- [ ] **Step 4: Copy the fixture and run the test**

```
mkdir -p d:/work/hexplain-tools/hdl/src/test/resources/profiles/dbf
cp d:/work/hexplain-profiles/profiles/dbf/dbf.hx d:/work/hexplain-tools/hdl/src/test/resources/profiles/dbf/dbf.hx
cd d:/work/hexplain-tools && .\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.DbfParityTest"
```
Expected: 4 tests PASS. Known adjustments:
- If `means atab:Field` on the struct fails SHACL because `atab:Field` is not a class, remove that clause.
- If the enum on `type` rejects `"+"`, `"@"`, `"0"`, keep only the letters.
- If the deleted `ascii[1]` field yields a trimmed string, that is fine; only counts are asserted.

- [ ] **Step 5: Library gate and commit**

Run (hexplain-profiles): `python tools/run_gates.py library` — expected PASS.

```
cd d:/work/hexplain-profiles && git add profiles/dbf && git commit -m "feat(dbf): xBase table profile, header and descriptors verified on four GDAL tables

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd d:/work/hexplain-tools && git add hdl/src/test/resources/profiles/dbf hdl/src/test/kotlin/io/hexplain/hdl/parity/DbfParityTest.kt && git commit -m "test(hdl): DBF parity against independently computed header values

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `lan`, `gtx`, `bt`, `lcp`

**Files:**
- Create: `hexplain-profiles/profiles/lan/lan.hx`, `profiles/gtx/gtx.hx`, `profiles/bt/bt.hx`, `profiles/lcp/lcp.hx`

**Interfaces:** none consumed by later tasks beyond the directory names.

- [ ] **Step 1: Write `lan.hx`**

```
// Hexplain Profile — Erdas 7.x LAN / GIS raster
//
// A 128-byte little-endian header and a band-interleaved-by-line grid. Erdas Imagine's
// predecessor format; .lan is a multi-band image, .gis a single-band thematic layer with the
// same layout. Header offsets follow GDAL's landataset.cpp, which is the surviving public
// reference; the fakelan.lan fixture (AREA at 108, XCELL at 120) confirms the two float blocks.
//
//   0   6  "HEAD74"
//   6   2  IPACK   0 = 8-bit, 1 = 4-bit packed, 2 = 16-bit
//   8   2  NBANDS
//  10   6  unused
//  16   4  ICOLS
//  20   4  IROWS
//  24   4  XSTART   upper-left column number of the image within its parent
//  28   4  YSTART
//  32  56  unused
//  88   2  MAPTYP   0 lat/long, 1 UTM, 2 State Plane, 99 unknown
//  90   2  NCLASS
//  92  16  unused
// 108   4  AREA     float32, area of one pixel
// 112   4  ML       float32, map X of the upper-left pixel
// 116   4  MB       float32, map Y of the upper-left pixel
// 120   4  XCELL    float32, pixel width in map units
// 124   4  YCELL    float32, pixel height
//
// Source: GDAL frmts/raw/landataset.cpp header comment (Erdas 7.x LAN/GIS);
// Erdas Field Guide, 7.x file formats.
// Verification status: NOT parse-verified. Written against autotest/gdrivers/data/lan/fakelan.lan
// (2 x 2, 8-bit; GDAL digest 9f64a747…) without a comparison test.

format lan @namespace "https://hexplain.io/ns/profile/lan#" @endian little

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

@root struct LanFile
  @label "Erdas 7.x LAN/GIS file"
{
  magic   : ascii[6] @fixed "HEAD74" @label "signature"
  ipack   : i16 enum { 0, 1, 2 } @label "packing: 0 = 8-bit, 1 = 4-bit, 2 = 16-bit"
  nbands  : i16 means asamp:componentCount @label "band count"
  unused1 : bytes[6]
  ncols   : i32 means araster:width @label "columns"
  nrows   : i32 means araster:height @label "rows"
  xstart  : i32 @label "column offset within the parent image"
  ystart  : i32 @label "row offset within the parent image"
  unused2 : bytes[56]
  maptyp  : i16 @label "map type: 0 lat/long, 1 UTM, 2 State Plane, 99 none"
  nclass  : i16 @label "class count (thematic layers)"
  unused3 : bytes[16]
  area    : f32 @label "area of one pixel in map units"
  ml      : f32 means asref:originX @label "map X of the upper-left pixel"
  mb      : f32 means asref:originY @label "map Y of the upper-left pixel"
  xcell   : f32 means asref:scaleX @label "pixel width in map units"
  ycell   : f32 means asref:scaleY @label "pixel height in map units"

  // BIL: for each row, each band's samples for that row. One field per packing.
  samples8  : bytes[..] layout cell u8 { dim axis Y size nrows  dim axis Band size nbands  dim axis X size ncols } if [ipack == 0]
    @label "8-bit samples, band-interleaved by line"
  samples4  : bytes[..] layout cell u8 { cell-bits 4  packing msb  dim axis Y size nrows  dim axis Band size nbands  dim axis X size ncols } if [ipack == 1]
    @label "4-bit samples, two per byte, band-interleaved by line"
  samples16 : bytes[..] layout cell i16le { dim axis Y size nrows  dim axis Band size nbands  dim axis X size ncols } if [ipack == 2]
    @label "16-bit signed samples, band-interleaved by line"
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. ml/mb are mapped as the upper-left pixel's map coordinate as the header defines them;
//    whether that is the pixel centre or corner is a reader convention (GDAL treats it as the
//    centre and shifts by half a cell). Not asserted here.
// 2. 4-bit rows: each row of each band is padded to a whole byte; the layout states packing but
//    not the per-row padding, which needs a stride the accessor does not execute.
// 3. Projection parameters beyond maptyp (zone, datum) are not in the file; a .pro or .trl
//    sidecar carries them and is not described.
```

- [ ] **Step 2: Write `gtx.hx`**

```
// Hexplain Profile — NOAA VDatum / NGS GTX vertical-offset grid
//
// Forty big-endian header bytes, then a float32 grid of offsets in metres. The grid starts at
// the SOUTH-WEST sample and runs east along a row, then north row by row -- south-up, which
// is why every reader flips it.
//
//    0  8  f64  latitude of the south-west sample (cell centre)
//    8  8  f64  longitude of the south-west sample, 0..360 or -180..180
//   16  8  f64  latitude spacing, degrees
//   24  8  f64  longitude spacing, degrees
//   32  4  i32  rows
//   36  4  i32  columns
//   40     f32  rows x columns offsets; -88.8888 is the no-data value
//
// Source: NOAA VDatum, "GTX grid file format"; GDAL frmts/raw/gtxdataset.cpp.
// Verification status: NOT parse-verified. Written against autotest/gdrivers/data/gtx/hydroc1.gtx
// (21 x 11, 964 bytes = 40 + 21 x 11 x 4) without a comparison test.

format gtx @namespace "https://hexplain.io/ns/profile/gtx#" @endian big

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

@root struct GtxFile
  @label "GTX vertical-offset grid"
{
  latitude0  : f64 means asref:originLatitude @label "latitude of the south-west sample"
  longitude0 : f64 means asref:originLongitude @label "longitude of the south-west sample"
  deltaLat   : f64 means asref:scaleY @label "row spacing, degrees"
  deltaLon   : f64 means asref:scaleX @label "column spacing, degrees"
  rows       : i32 means araster:height @label "rows"
  columns    : i32 means araster:width @label "columns"
  offsets    : bytes[..] layout cell f32be { dim axis Y size rows  dim axis X size columns }
    @label "vertical offsets in metres, south row first"

  raw-turtle {
    :GtxFile araster:noDataValue -88.8888 ;
        asamp:bitDepth 32 ;
        asref:epsgCode 4326 .
  }
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. ROWS RUN SOUTH TO NORTH. DLV cannot state direction; a north-up consumer reverses rows.
// 2. The origin is the CENTRE of the south-west cell; asref:originLatitude/Longitude receive
//    it as written. A corner-registered transform subtracts half a spacing.
// 3. Longitude may be written 0..360; no normalisation is applied.
```

- [ ] **Step 3: Write `bt.hx`**

```
// Hexplain Profile — VTP Binary Terrain 1.3 (.bt)
//
// A 256-byte little-endian header and a column-major grid: the file holds the WEST column
// first, and within a column the SOUTH cell first. Cells are int16, int32 or float32 by two
// header fields.
//
//    0  10  "binterr1.3"
//   10   4  i32  columns
//   14   4  i32  rows
//   18   2  i16  data size: 2 or 4 bytes
//   20   2  i16  floating point: 1 = float32, 0 = integer
//   22   2  i16  horizontal units: 0 degrees, 1 metres, 2 feet (international), 3 feet (US)
//   24   2  i16  UTM zone, 0 when not UTM
//   26   2  i16  datum, EPSG code - 6000 (e.g. 326 = WGS 84)
//   28   8  f64  left extent
//   36   8  f64  right extent
//   44   8  f64  bottom extent
//   52   8  f64  top extent
//   60   2  i16  external projection: 1 = a .prj sidecar carries the CRS
//   62   4  f32  vertical scale (1.3), metres per unit
//   66 190  unused
//
// Source: Virtual Terrain Project, "BT Binary Terrain Format" 1.3; GDAL frmts/raw/btdataset.cpp.
// Verification status: NOT parse-verified. No .bt sample exists in the GDAL autotest corpus;
// offsets were cross-checked against the two references above only.

format bt @namespace "https://hexplain.io/ns/profile/bt#" @endian little

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

@root struct BtFile
  @label "Binary Terrain file"
{
  marker        : ascii[10] @fixed "binterr1.3" @label "signature and version"
  columns       : i32 means araster:width @label "columns"
  rows          : i32 means araster:height @label "rows"
  dataSize      : i16 enum { 2, 4 } @label "bytes per cell"
  floatingPoint : i16 enum { 0, 1 } @label "1 = float32 cells, 0 = integer cells"
  hUnits        : i16 enum { 0, 1, 2, 3 } @label "horizontal units: 0 degrees, 1 m, 2 ft, 3 US ft"
  utmZone       : i16 @label "UTM zone, negative for the southern hemisphere, 0 if not UTM"
  datum         : i16 @label "EPSG datum code minus 6000"
  leftExtent    : f64 means asref:originX @label "west edge"
  rightExtent   : f64 @label "east edge"
  bottomExtent  : f64 @label "south edge"
  topExtent     : f64 means asref:originY @label "north edge"
  externalProjection : i16 @label "1 = CRS in a .prj sidecar"
  verticalScale : f32 means araster:sampleScale @label "metres per cell unit"
  unused        : bytes[190]

  // Column-major: X is the slow axis, Y the fast one, south cell first.
  cellsF32 : bytes[..] layout cell f32le { dim axis X size columns  dim axis Y size rows } if [floatingPoint == 1]
    @label "float32 heights, column-major"
  cellsI32 : bytes[..] layout cell i32le { dim axis X size columns  dim axis Y size rows } if [floatingPoint == 0 && dataSize == 4]
    @label "int32 heights, column-major"
  cellsI16 : bytes[..] layout cell i16le { dim axis X size columns  dim axis Y size rows } if [floatingPoint == 0 && dataSize == 2]
    @label "int16 heights, column-major"

  raw-turtle { :BtFile asamp:componentCount 1 . }
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. ORIENTATION: columns west to east, cells south to north. DLV states order and width, not
//    direction; a north-up row-major consumer transposes and flips.
// 2. Pixel size is (right - left) / columns and (top - bottom) / rows; asref:scaleX/scaleY are
//    not derived because the datatype of a division of two doubles in HEL has not been pinned
//    by a test here. originX/originY carry the west and north edges.
// 3. The CRS is (hUnits, utmZone, datum) or an external .prj; neither is lifted to asref:hasCRS.
// 4. No corpus sample: every offset above is from the two named references only.
```

- [ ] **Step 4: Write `lcp.hx`**

```
// Hexplain Profile — FARSITE v4 landscape file (.lcp)
//
// A 7316-byte little-endian header and an int16 band-interleaved-by-line grid of 5, 7, 8 or
// 10 bands: elevation, slope, aspect, fuel model, canopy cover, then optionally the three
// crown-fuel bands (height, base height, bulk density) and the two ground-fuel bands (duff,
// coarse woody). Which are present is declared by the first two header words (21 = present).
//
//      0    4  i32  crown fuels: 20 absent, 21 present
//      4    4  i32  ground fuels: 20 absent, 21 present
//      8    4  i32  latitude, degrees
//     12   32  f64  loEast, hiEast, loNorth, hiNorth
//     44 4120       ten band-statistics blocks (lo, hi, class count, 100 class values)
//   4164    4  i32  columns (numEast)
//   4168    4  i32  rows (numNorth)
//   4172   32  f64  east, west, north, south UTM extents
//   4204    4  i32  grid units: 0 metres, 1 feet, 2 kilometres
//   4208   16  f64  x resolution, y resolution
//   4224   20  i16  ten unit codes
//   4244 2560       ten 256-byte source file names
//   6804  512       description
//   7316            samples
//
// Source: FARSITE 4 landscape file structure (Finney, M.A., USDA Forest Service RMRS);
// GDAL frmts/raw/lcpdataset.cpp.
// Verification status: NOT parse-verified. Written against autotest/gdrivers/data/lcp/
// test_FARSITE_UTM12.LCP (57 x 55 x 8 bands, 57476 bytes = 7316 + 57 x 55 x 8 x 2) without a
// comparison test.

format lcp @namespace "https://hexplain.io/ns/profile/lcp#" @endian little

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

struct BandStats @label "band statistics block, 412 bytes" {
  lo         : i32 @label "minimum"
  hi         : i32 @label "maximum"
  numClasses : i32 @label "distinct values, or -1 when over 100"
  values     : i32 repeat 100 @label "class values"
}

@root struct LcpFile
  @label "FARSITE landscape"
{
  crownFuels  : i32 enum { 20, 21 } @label "crown fuel bands present when 21"
  groundFuels : i32 enum { 20, 21 } @label "ground fuel bands present when 21"
  latitude    : i32 @label "latitude of the landscape, degrees"
  loEast      : f64
  hiEast      : f64
  loNorth     : f64
  hiNorth     : f64
  elevation   : BandStats
  slope       : BandStats
  aspect      : BandStats
  fuelModel   : BandStats
  canopyCover : BandStats
  canopyHeight : BandStats
  canopyBase  : BandStats
  bulkDensity : BandStats
  duff        : BandStats
  coarseWoody : BandStats
  numEast     : i32 means araster:width @label "columns"
  numNorth    : i32 means araster:height @label "rows"
  eastUtm     : f64 @label "east edge"
  westUtm     : f64 means asref:originX @label "west edge"
  northUtm    : f64 means asref:originY @label "north edge"
  southUtm    : f64 @label "south edge"
  gridUnits   : i32 enum { 0, 1, 2 } @label "0 metres, 1 feet, 2 kilometres"
  xResolution : f64 means asref:scaleX @label "cell width"
  yResolution : f64 means asref:scaleY @label "cell height"
  elevationUnits   : i16
  slopeUnits       : i16
  aspectUnits      : i16
  fuelModelOptions : i16
  canopyCoverUnits : i16
  canopyHeightUnits : i16
  canopyBaseUnits  : i16
  bulkDensityUnits : i16
  duffUnits        : i16
  coarseWoodyUnits : i16
  elevationFile   : ascii[256] @trim-null
  slopeFile       : ascii[256] @trim-null
  aspectFile      : ascii[256] @trim-null
  fuelModelFile   : ascii[256] @trim-null
  canopyCoverFile : ascii[256] @trim-null
  canopyHeightFile : ascii[256] @trim-null
  canopyBaseFile  : ascii[256] @trim-null
  bulkDensityFile : ascii[256] @trim-null
  duffFile        : ascii[256] @trim-null
  coarseWoodyFile : ascii[256] @trim-null
  description     : ascii[512] @trim-null

  bandCount : derive [5 + (crownFuels == 21 ? 3 : 0) + (groundFuels == 21 ? 2 : 0)]
    means asamp:componentCount @label "bands present"

  samples : bytes[..] layout cell i16le { dim axis Y size numNorth  dim axis Band size bandCount  dim axis X size numEast }
    @label "int16 samples, band-interleaved by line, north row first"

  raw-turtle { :LcpFile asamp:bitDepth 16 . }
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. The band ORDER when only one optional group is present (crown bands precede ground
//    bands) is stated by the header layout, not by the DLV band axis, which is unlabelled.
// 2. Units per band are integer codes whose meaning (metres/feet, percent/fraction, ...) is
//    carried in the FARSITE documentation, not lifted here.
// 3. The CRS is a .prj sidecar (see test_FARSITE_UTM12.prj); only the extents are mapped.
```

- [ ] **Step 5: Run the library gate**

Run (hexplain-profiles): `python tools/run_gates.py library`
Expected: PASS with four more compiled profiles. Known adjustments:
- `dim axis X size columns  dim axis Y size rows` on one line: if the parser needs each `dim` on its own line, split them.
- `raw-turtle { :BtFile asamp:componentCount 1 . }`: if SHACL rejects a literal on a struct with no `means` class, drop the block.

- [ ] **Step 6: Commit**

```
cd d:/work/hexplain-profiles && git add profiles/lan profiles/gtx profiles/bt profiles/lcp && git commit -m "feat: LAN, GTX, BT and LCP raw-grid profiles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `idrisi` and `saga` bundles

**Files:**
- Create: `hexplain-profiles/profiles/idrisi/idrisi.hx`, `profiles/saga/saga.hx`

- [ ] **Step 1: Look at the two sidecars to confirm the keys**

Run (from the corpus root `d:/work/hexplain-tools/tests/gdal/cache/upstream/autotest`):
```
cat gdrivers/data/rst/byte.rdc; echo ---; cat gdrivers/data/saga/4byteFloat.sgrd
```
Use the exact key spellings printed; the keys below are from the Idrisi and SAGA documentation and must match what the files show (case-insensitive, whitespace-trimmed).

- [ ] **Step 2: Write `idrisi.hx`**

```
// Hexplain Profile — Idrisi raster (.rst + .rdc)
//
// The ENVI/EHdr shape again: a headerless little-endian grid beside a text label, bound by
// stem. The label is `key : value` lines whose keys contain spaces and dots
// ("min. X", "flag value"), padded to a fixed width before the colon -- splitting at the FIRST
// separator and trimming is what makes them read cleanly.
//
//   file format : IDRISI Raster A.1
//   data type   : byte            byte | integer | real | rgb24
//   file type   : binary
//   columns     : 21
//   rows        : 21
//   ref. system : plane
//   min. X      : 0.0000000
//   max. X      : 21.0000000
//   min. Y      : 0.0000000
//   max. Y      : 21.0000000
//   flag value  : none
//
// Source: Clark Labs, Idrisi file formats (RDC raster documentation file); GDAL frmts/idrisi.
// Verification status: NOT parse-verified. Written against autotest/gdrivers/data/rst/byte.rst
// and real.rst with their .rdc labels, without a comparison test.

format idrisi @namespace "https://hexplain.io/ns/profile/idrisi#"

use abnd:    <https://hexplain.io/ns/aspect/bundle#>
use rpr:     <https://hexplain.io/ns/register/part-role#>
use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

register abnd:partRole from rpr:PartRoleScheme

header Documentation @record-separator 0x0A @separator 0x3A @trim @ci
  @label "Idrisi raster documentation (.rdc)"
{
  "file format" as fileFormat : str @label "IDRISI Raster A.1"
  "data type"   as dataType   : str enum { "byte", "integer", "real", "rgb24" } @label "cell type"
  "file type"   as fileType   : str @label "binary or ascii"
  "columns"     as columns    : anum means araster:width
  "rows"        as rows       : anum means araster:height
  "ref. system" as refSystem  : str @label "reference system name or plane/latlong"
  "ref. units"  as refUnits   : str
  "unit dist."  as unitDistance : adec
  "min. X"      as minX       : adec means asref:originX @label "west edge"
  "max. X"      as maxX       : adec
  "min. Y"      as minY       : adec
  "max. Y"      as maxY       : adec means asref:originY @label "north edge"
  "resolution"  as resolution : adec means asref:scaleX
  "min. value"  as minValue   : adec
  "max. value"  as maxValue   : adec
  "value units" as valueUnits : str
  "flag value"  as flagValue  : str @label "no-data value, or none"
}

struct Raster @endian little
  @label "Idrisi raster data (.rst)"
  @comment "Headerless grid, north row first, little-endian; the cell type comes from the label."
{
  samples : bytes[..] layout {
    cell switch {
      when asset.Documentation.dataType == "byte"    => u8
      when asset.Documentation.dataType == "integer" => i16le
      when asset.Documentation.dataType == "real"    => f32le
      when asset.Documentation.dataType == "rgb24"   => u8
    }
    dim axis Y size asset.Documentation.rows
    dim axis X size asset.Documentation.columns
  }
}

bundle IdrisiRaster @bound-by naming-convention {
  part ".rst" role Payload  required primary carries araster: described-by Raster
  part ".rdc" role Metadata required         carries asref:  described-by Documentation
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. rgb24 packs three bytes per cell; the layout above reads it as one u8 per cell and is
//    wrong for that type by a factor of three. Stated rather than hidden: a Band dimension
//    conditioned on the type needs an `order switch` over a dimension that is absent for the
//    other three types, which DLV cannot express.
// 2. "file type : ascii" labels a text grid this description does not cover.
// 3. resolution is mapped to scaleX only; Idrisi cells are square, so scaleY is the same value.
// 4. flagValue is text ("none" or a number) and is not lifted to araster:noDataValue.
```

- [ ] **Step 3: Write `saga.hx`**

```
// Hexplain Profile — SAGA GIS binary grid (.sdat + .sgrd)
//
// The same two-part shape as ENVI: a headerless grid beside a `KEY = value` label, bound by
// stem. The label declares the cell type, byte order and whether rows run top-to-bottom.
//
//   NAME            = grid
//   DESCRIPTION     =
//   DATAFORMAT      = FLOAT          BIT | BYTE_UNSIGNED | BYTE | SHORTINT_UNSIGNED | SHORTINT
//                                    | INTEGER_UNSIGNED | INTEGER | FLOAT | DOUBLE
//   DATAFILE_OFFSET = 0
//   BYTEORDER_BIG   = FALSE
//   POSITION_XMIN   = 0.5
//   POSITION_YMIN   = 0.5
//   CELLCOUNT_X     = 10
//   CELLCOUNT_Y     = 10
//   CELLSIZE        = 1
//   Z_FACTOR        = 1
//   NODATA_VALUE    = -99999
//   TOPTOBOTTOM     = FALSE
//
// Source: SAGA GIS, "Grid file format" (sgrd header specification); GDAL frmts/saga.
// Verification status: NOT parse-verified. Written against autotest/gdrivers/data/saga/
// 4byteFloat.sgrd + .sdat (10 x 10 float32) without a comparison test.

format saga @namespace "https://hexplain.io/ns/profile/saga#"

use abnd:    <https://hexplain.io/ns/aspect/bundle#>
use rpr:     <https://hexplain.io/ns/register/part-role#>
use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>

register abnd:partRole from rpr:PartRoleScheme

header GridHeader @record-separator 0x0A @separator 0x3D @trim @ci
  @label "SAGA grid header (.sgrd)"
{
  "NAME"            as name          : str
  "DESCRIPTION"     as description   : str
  "DATAFORMAT"      as dataFormat    : str enum { "BIT", "BYTE_UNSIGNED", "BYTE", "SHORTINT_UNSIGNED", "SHORTINT", "INTEGER_UNSIGNED", "INTEGER", "FLOAT", "DOUBLE" }
  "DATAFILE_OFFSET" as dataOffset    : anum @label "bytes to skip in the data file"
  "BYTEORDER_BIG"   as byteOrderBig  : str enum { "TRUE", "FALSE" }
  "POSITION_XMIN"   as xMin          : adec means asref:originX @label "centre of the west-most column"
  "POSITION_YMIN"   as yMin          : adec @label "centre of the south-most row"
  "CELLCOUNT_X"     as columns       : anum means araster:width
  "CELLCOUNT_Y"     as rows          : anum means araster:height
  "CELLSIZE"        as cellSize      : adec means asref:scaleX
  "Z_FACTOR"        as zFactor       : adec means araster:sampleScale
  "NODATA_VALUE"    as noData        : adec means araster:noDataValue
  "TOPTOBOTTOM"     as topToBottom   : str enum { "TRUE", "FALSE" } @label "row direction; FALSE means the south row is first"
}

struct Raster
  @label "SAGA grid data (.sdat)"
  @comment "Headerless grid after DATAFILE_OFFSET bytes; byte order and cell type from the header."
  @endian switch {
    when [asset.GridHeader.byteOrderBig == "TRUE"]  => big
    when [asset.GridHeader.byteOrderBig == "FALSE"] => little
  }
{
  skipped : bytes[asset.GridHeader.dataOffset] @label "DATAFILE_OFFSET bytes"
  samples : bytes[..] layout {
    cell switch {
      when asset.GridHeader.dataFormat == "BYTE_UNSIGNED"     => u8
      when asset.GridHeader.dataFormat == "BYTE"              => i8
      when asset.GridHeader.dataFormat == "SHORTINT_UNSIGNED" => u16
      when asset.GridHeader.dataFormat == "SHORTINT"          => i16
      when asset.GridHeader.dataFormat == "INTEGER_UNSIGNED"  => u32
      when asset.GridHeader.dataFormat == "INTEGER"           => i32
      when asset.GridHeader.dataFormat == "FLOAT"             => f32
      when asset.GridHeader.dataFormat == "DOUBLE"            => f64
    }
    dim axis Y size asset.GridHeader.rows
    dim axis X size asset.GridHeader.columns
  }
}

bundle SagaGrid @bound-by naming-convention {
  part ".sdat" role Payload  required primary carries araster: described-by Raster
  part ".sgrd" role Metadata required         carries asref:  described-by GridHeader
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. DATAFORMAT = BIT (one bit per cell) is admitted by the enumeration but has no cell arm;
//    it needs cell-bits 1 and is not described.
// 2. TOPTOBOTTOM is exposed, not applied: DLV cannot state row direction.
// 3. POSITION_XMIN/YMIN are CELL CENTRES; asref:originX receives xMin as written and the
//    north edge is not derived (yMin + rows x cellSize - cellSize / 2 needs a HEL datatype
//    guarantee this profile does not pin).
// 4. A .prj sidecar may carry the CRS; not described.
```

- [ ] **Step 4: Run the library gate**

Run (hexplain-profiles): `python tools/run_gates.py library`
Expected: PASS. Known adjustments:
- If the parser does not accept `enum` on a header field, remove the enum and list the values in the `@comment`.
- If `@endian switch` is not accepted on a struct with `asset.` conditions, replace with `@prop bddo:hasConditionalEndianness` is NOT available in `.hx`; instead drop the switch, declare `@endian little`, and add limit 5: "BYTEORDER_BIG = TRUE grids are read with the wrong byte order; ehdr.ttl's hasConditionalEndianness is the hand-Turtle form this surface lacks."
- If `described-by Documentation` is rejected because a `header` is not a struct, drop `described-by` on the `.rdc`/`.sgrd` parts and note it in a comment.
- If anything else in the `header`/`bundle` surface blocks compilation, apply the spec's fallback: write `idrisi.ttl`/`saga.ttl` by hand from `profiles/ehdr/ehdr.ttl`, delete the `.hx`, and record the compiler gap in the profile header.

- [ ] **Step 5: Commit**

```
cd d:/work/hexplain-profiles && git add profiles/idrisi profiles/saga && git commit -m "feat: Idrisi and SAGA sidecar-plus-grid bundle profiles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Full gate runs and fixture parity

**Files:** none new; verifies Tasks 1–7.

- [ ] **Step 1: Run every library gate**

Run (hexplain-profiles): `python tools/run_gates.py`
Expected: `PASS test_profile_library` (19 profiles), `PASS test_hx_roundtrip`, `PASS test_tools_fixtures` (11 verified fixtures: the six ISO BMFF ones plus wkb, gpkgblob, bmp, dted, dbf).

- [ ] **Step 2: Run the whole hdl parity package**

Run (hexplain-tools): `.\gradlew.bat --offline :hdl:test --tests "io.hexplain.hdl.parity.*"`
Expected: PASS, including the pre-existing ISO BMFF, PNG and TIFF parity tests.

- [ ] **Step 3: Run the core tests that touch the geometry oracle**

Run (hexplain-tools): `.\gradlew.bat --offline :core:test --tests "io.hexplain.core.raster.GdalVectorGeometryTest"`
Expected: PASS (unchanged; confirms the oracle file the WKB test reads is the one the decoder is held to).

- [ ] **Step 4: If any header's Verification status line no longer matches a test name, fix it, re-copy the fixture, and commit**

```
cd d:/work/hexplain-profiles && git status --short
```
Expected: clean. Otherwise `git add profiles && git commit -m "docs(profiles): align verification status lines with the parity tests"` and re-copy any changed fixture into hexplain-tools, then commit there too.

---

### Task 9: Coverage inventory links

**Files:**
- Modify: `hexplain.io/specification/coverage/gdal-drivers.json`
- Modify: `hexplain.io/tools/_build_ontology_docs.py:56,61`
- Modify: `hexplain.io/tools/test_gdal_inventory.py`
- Regenerate: `hexplain.io/specification/coverage/index.html`

**Interfaces:**
- Produces per-driver `profiles: [{name, iri, verification}]` with `verification ∈ {parse-verified, not-parse-verified}`.

- [ ] **Step 1: Extend the inventory test first (failing)**

Append to `hexplain.io/tools/test_gdal_inventory.py` before the final `print`:

```python
profiles_root=Path('../hexplain-profiles/profiles')
linked=0
for r in rows:
    for p in r.get('profiles',[]):
        assert set(p)=={'name','iri','verification'},(r['key'],p)
        assert re.fullmatch('[a-z0-9-]+',p['name']),p
        assert p['iri']==f"https://hexplain.io/ns/profile/{p['name']}",p
        assert p['verification'] in ['parse-verified','not-parse-verified'],p
        if profiles_root.is_dir():assert (profiles_root/p['name']).is_dir(),f"{p['name']} is not a library profile"
        linked+=1
assert linked>=20,linked
```
and change the final print to:
```python
print(f'PASS: {len(rows)} uniquely keyed GDAL documentation pages ({dict(counts)}); pinned sources, evidence policy and {linked} profile links valid')
```

Run (hexplain.io): `python tools/test_gdal_inventory.py`
Expected: FAIL with `AssertionError: 0` (no links yet).

- [ ] **Step 2: Add the links**

Run (hexplain.io):
```
python - <<'EOF'
import json
from pathlib import Path
p=Path('specification/coverage/gdal-drivers.json')
d=json.loads(p.read_text(encoding='utf-8'))
V='parse-verified'; N='not-parse-verified'
links={
 'raster:bmp':[('bmp',V)], 'raster:dted':[('dted',V)], 'raster:lan':[('lan',N)], 'raster:gtx':[('gtx',N)],
 'raster:bt':[('bt',N)], 'raster:lcp':[('lcp',N)], 'raster:idrisi':[('idrisi',N)], 'raster:sdat':[('saga',N)],
 'vector:shapefile':[('shapefile',N),('dbf',V)], 'vector:mitab':[('dbf',V)], 'vector:gpkg':[('gpkgblob',V),('wkb',V)],
 'raster:gtiff':[('tiff',V)], 'raster:png':[('png',V)], 'raster:nitf':[('nitf',V)], 'raster:envi':[('envi',N)],
 'raster:ehdr':[('ehdr',N)], 'raster:srtmhgt':[('srtmhgt',N)], 'raster:heif':[('heif',V),('heic',V),('iso-bmff',V)],
 'raster:avif':[('avif',V),('codec-av1',V)],
}
by={r['key']:r for r in d['drivers']}
for key,items in links.items():
    by[key]['profiles']=[{'name':n,'iri':f'https://hexplain.io/ns/profile/{n}','verification':v} for n,v in items]
p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
print('linked',sum(len(r.get('profiles',[])) for r in d['drivers']))
EOF
```
Note: `tiff` and `png` name the engine's bundled `tiff-profile.ttl`/`png-profile.ttl`, which are not library directories. Before running, check `ls ../hexplain-profiles/profiles`; if `tiff`/`png` are absent there, drop those two entries (the test asserts directory existence when the checkout is present) and keep the count above 20 with the others.

Run: `python tools/test_gdal_inventory.py` — expected PASS with the link count.

- [ ] **Step 3: Render the column**

In `hexplain.io/tools/_build_ontology_docs.py`, replace line 56 (the `rows=` expression) with:

```python
def profile_cell(r):
    ps=r.get('profiles',[])
    if not ps:return '<span class="muted">—</span>'
    return ', '.join(f'<a href="{esc(p["iri"])}">{esc(p["name"])}</a> <small>({esc(p["verification"])})</small>' for p in ps)
rows=''.join(f'<tr data-search="{esc((r["name"]+" "+r["key"]+" "+" ".join(r["capability_families"])+" "+" ".join(p["name"] for p in r.get("profiles",[]))).lower())}"><td>{esc(r["kind"])}</td><td><a href="{esc(r["source"])}">{esc(r["name"])}</a></td><td>{esc(", ".join(r["capability_families"]) or "Unassessed")}</td><td>{profile_cell(r)}</td><td>Not runtime verified</td></tr>' for r in inventory['drivers'])
```

and in line 61 change the table head to:

```html
<thead><tr><th>Kind</th><th>Released source</th><th>Planning tags</th><th>Profiles</th><th>Evidence status</th></tr></thead>
```

and, in the same line, change the filter label text to `Filter by driver, capability family or profile`. Add after the `<p class="muted">Sources are pinned…</p>` sentence (same line 61, inside the f-string) the sentence: `A profile link names a description in the profile library by its ontology IRI; parse-verified means a behavioural test in hexplain-tools parses corpus samples with it. A profile is a description, not runtime evidence, so the evidence column is unchanged.`

- [ ] **Step 4: Regenerate and check only the expected files changed**

Run (hexplain.io):
```
python tools/_build_ontology_docs.py
git status --short specification/coverage tools
git diff --stat
```
Expected: `specification/coverage/index.html` and `gdal-drivers.json` modified plus the two tools files. If the builder also rewrites the three aspect reference pages and those diffs are non-empty, inspect them; commit them only if the change is a byte-identical regeneration artefact (whitespace) — otherwise leave them out of the commit.

- [ ] **Step 5: Run the spec gates that read the inventory**

Run (hexplain.io): `python tools/test_gdal_inventory.py && python tools/test_gdal_runtime.py`
Expected: both PASS (runtime test compares key sets only).

- [ ] **Step 6: Commit**

```
cd d:/work/hexplain.io && git add specification/coverage/gdal-drivers.json specification/coverage/index.html tools/_build_ontology_docs.py tools/test_gdal_inventory.py docs/superpowers/plans/2026-09-09-gdal-profile-wave.md && git commit -m "coverage: link GDAL driver rows to profile-library descriptions with their verification status

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Self-review

**Spec coverage.** Ten profiles: Tasks 1, 3, 4, 5, 6 (four), 7 (two) — all present. gpkgblob upgrade: Task 2. Parity tests for bmp, dted, dbf, wkb: Tasks 3, 4, 5, 1; the spec's extra GeoPackage-blob test: Task 2. Fixture copies + `test_tools_fixtures`: each task copies, Task 8 verifies. Coverage inventory, column, test: Task 9. Verification status lines: in each profile, checked in Task 8. Sequencing matches the spec (wkb first).

**Placeholders.** `PIN_PATH`/`PIN_LEN`/`PIN_B64`/`PIN_TABLE` in Task 2 are filled from Step 1's output before the test is written; they are inputs the executor produces, not omissions. Every other code block is complete.

**Type consistency.** `ProfileFixtures.formatIR/parse/parseFile/sha256/int/long/map/list` are used with the same signatures in Tasks 1–5. `WkbParityTest.fold` is `companion` so Task 2 can call it. Field names in tests match the profiles: `wkbType`, `point/lineString/polygon/collection`, `coords`, `rings`, `geometries`; `fileHeader.bfOffBits`, `info.biWidth/biHeight/biCompression`, `height`, `bands`, `rowStride`, `palette`, `rows[].samples`; `uhl.nlon/nlat/lonOrigin/latOrigin/originLongitude/originLatitude`, `columns[].elevations`; `header.version/yy/mm/dd/numRecords/headerLength/recordLength`, `descriptors[].name/type/length/decimalCount`, `terminator`, `records`.
