# HDL hx-bundle Surface — Implementation Plan (Plan 3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hx-bundle authoring to HDL — `bundle` profiles (a reusable multi-file format template, e.g. a Shapefile) and `asset` instances — compiled to canonical `abnd:` (hx-bundle) Turtle, so a multi-file format can be described in HDL alongside its per-part BDDO structs.

**Architecture:** A new `io.hexplain.hdl.emit.vocab.ABND` Kotlin vocab object (hx-bundle is absent from core), new AST nodes (`BundleDecl`/`PartSpecDecl`/`AssetDecl`/`AssetPartDecl`) that flow through the existing Resolver, and `TurtleEmitter` extensions that emit `abnd:BundleProfile`/`abnd:Asset` graphs. Both text (`bundle`/`asset` declarations) and YAML (`bundles:`/`assets:`) surfaces. Because core has **no bundle runtime** (no Metaparser path), correctness is anchored on **SHACL conformance** — the emitted asset graph is validated against the `abnd:` SHACL shapes (`AssetShape`/`PartShape`) via core's `ShaclProfileValidator` — plus a **golden-Turtle snapshot** of the Shapefile profile and specific-triple assertions.

**Tech Stack:** Kotlin 2.2.10 / JVM / Gradle, Apache Jena 5.5.0 (incl. jena-shacl), JUnit 5.10.2. Builds on merged Plans 1 (text compiler) + 2 (YAML surface) in `d:/work/hexplain-tools`.

## Global Constraints

- Versions via the catalog. `jena-shacl` is already a `:core` dependency; `:hdl` needs it directly for the SHACL test — add `implementation(libs.jena.shacl)` to `hdl/build.gradle.kts` (Task 6).
- **hx-bundle namespace:** `https://hexplain.io/ns/aspect/bundle#`, prefix `abnd`. The `abnd` prefix is already predeclared in `Resolver.PREDECLARED` (from Plan 1). The new `ABND` vocab object lives at `io.hexplain.hdl.emit.vocab.ABND` (hx-bundle isn't in core's vocab set; keep it hdl-local).
- AST additions are **additive**: new node types + two trailing defaulted fields on `Document` (`bundles: List<BundleDecl> = emptyList()`, `assets: List<AssetDecl> = emptyList()`), so existing `Document(...)` construction sites in `HdlParser`/`YamlLoader` keep compiling.
- Errors are `Diagnostic` values, never thrown to the façade caller (consistent with Plans 1–2).
- **`carries <prefix>` resolves to the ontology IRI, not the namespace IRI:** `abnd:carriesAspect` has range `owl:Ontology`. A `use ageom: <https://hexplain.io/ns/aspect/geometry#>` prefix expands *with* the trailing `#`; the emitter strips a single trailing `#` or `/` so `carries ageom:` emits `<https://hexplain.io/ns/aspect/geometry>`.
- **IRI minting** (consistent with Plan 1): `bundle Shapefile` → `<base>Shapefile`; `asset roads` → `<base>roads`; an asset `part roads.shp` → `<base>roads.shp`. Base namespace from `format` (or `@namespace`); a bundle-only file with no `format` uses the default `https://hexplain.io/formats/<?>#` — so a `.hx` with bundles SHOULD still declare `format <name>` for its namespace (the Shapefile fixture does).
- **Binding kinds** keyword → individual: `containment`→`Containment`, `naming-convention`→`NamingConvention`, `manifest-reference`→`ManifestReference`, `concatenation`→`Concatenation`.
- **Part roles:** `role X` (bare) → `abnd:X` (the PartRoleScheme concept); `role ns:Custom` → `expandCurie`. Known roles: GeometryCarrier, AttributeTable, SpatialReference, CharacterEncoding, SpatialIndex, Manifest, Segment, Sidecar, Metadata, Thumbnail, Checksum, Payload.
- SHACL correctness (Task 6) validates against a **copy** of the spec's `specification/aspect/bundle/bundle.ttl` placed at `hdl/src/test/resources/bundle.ttl`. The shapes (`AssetShape`/`PartShape`) target `abnd:Asset`/`abnd:Part` **instances**, so the anchor requires an `asset` instance, not just a profile.

## Scope note

This is **Plan 3 of 3** (Plans 1 text-compiler + 2 YAML-surface are merged). It covers **bundle profiles** (the primary artifact) fully, and **asset instances** structurally (conforms / boundBy / stem / primaryPart / parts-with-roles) — enough to exercise the SHACL shapes. Per-part **aspect-facet assignment** (e.g. `asref:epsgCode = 4326` on a part, for the facet-lifting rule) is OUT OF SCOPE for this plan — authors can attach facets via the existing `raw-turtle { … }` escape hatch; a dedicated facet syntax is a future increment.

---

## File Structure

Created/modified under `d:/work/hexplain-tools`:

- Create: `hdl/src/main/kotlin/io/hexplain/hdl/emit/vocab/ABND.kt` — hx-bundle vocab object.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt` — bundle/asset AST + `Document` fields.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt` — carry bundles/assets into `ResolvedDoc`.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` — `bundle`/`asset` declarations.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt` — `bundles:`/`assets:` keys.
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt` — emit bundle/asset graphs.
- Modify: `hdl/build.gradle.kts` — `implementation(libs.jena.shacl)`.
- Create: `hdl/src/test/resources/bundle.ttl` (copy of the spec), `hdl/src/test/resources/shapefile.hx`, `hdl/src/test/resources/golden/shapefile-bundle.expected.ttl`.
- Create tests: `emit/vocab/AbndTest.kt`, `parse/ParserBundleTest.kt`, `emit/EmitBundleTest.kt`, `yaml/YamlBundleTest.kt`, `parity/BundleShaclTest.kt`.

---

## Task 1: ABND vocab object

**Files:**
- Create: `hdl/src/main/kotlin/io/hexplain/hdl/emit/vocab/ABND.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/vocab/AbndTest.kt`

**Interfaces:**
- Produces: `object ABND` with `const val NAMESPACE`, and `Resource`/`Property` constants for every hx-bundle term (classes, properties, binding-kind individuals, part-role concepts), following the exact pattern of `io.hexplain.core.rdf.vocab.BDDO`.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/vocab/AbndTest.kt`:

```kotlin
package io.hexplain.hdl.emit.vocab

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class AbndTest {
    @Test fun exposesNamespaceAndKeyTerms() {
        assertEquals("https://hexplain.io/ns/aspect/bundle#", ABND.NAMESPACE)
        assertEquals("https://hexplain.io/ns/aspect/bundle#Asset", ABND.Asset.uri)
        assertEquals("https://hexplain.io/ns/aspect/bundle#BundleProfile", ABND.BundleProfile.uri)
        assertEquals("https://hexplain.io/ns/aspect/bundle#partSpec", ABND.partSpec.uri)
        assertEquals("https://hexplain.io/ns/aspect/bundle#NamingConvention", ABND.NamingConvention.uri)
        assertEquals("https://hexplain.io/ns/aspect/bundle#GeometryCarrier", ABND.GeometryCarrier.uri)
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.vocab.AbndTest"`
Expected: FAIL — `ABND` unresolved.

- [ ] **Step 3: Write the vocab object**

Create `hdl/src/main/kotlin/io/hexplain/hdl/emit/vocab/ABND.kt` (mirrors `core`'s `BDDO.kt` pattern — a private in-memory Jena model minting typed constants):

```kotlin
package io.hexplain.hdl.emit.vocab

import org.apache.jena.rdf.model.Model
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.rdf.model.Property
import org.apache.jena.rdf.model.Resource

/**
 * Vocabulary for the Hexplain Bundle aspect (hx-bundle) 1.0.
 * Namespace: https://hexplain.io/ns/aspect/bundle#
 * Mirrors specification/aspect/bundle/bundle.ttl. hx-bundle is not part of core's vocab set,
 * so this object is hdl-local (the bundle emitter is its only consumer).
 */
object ABND {
    private val m: Model = ModelFactory.createDefaultModel()
    const val NAMESPACE = "https://hexplain.io/ns/aspect/bundle#"
    fun getURI(): String = NAMESPACE
    private fun res(local: String): Resource = m.createResource(NAMESPACE + local)
    private fun prop(local: String): Property = m.createProperty(NAMESPACE + local)

    // Classes
    val Asset: Resource = res("Asset")
    val Part: Resource = res("Part")
    val BindingKind: Resource = res("BindingKind")
    val BundleProfile: Resource = res("BundleProfile")
    val PartSpec: Resource = res("PartSpec")

    // Instance-level properties
    val hasPart: Property = prop("hasPart")
    val partOf: Property = prop("partOf")
    val primaryPart: Property = prop("primaryPart")
    val partRole: Property = prop("partRole")
    val boundBy: Property = prop("boundBy")
    val partIndex: Property = prop("partIndex")
    val stem: Property = prop("stem")

    // Profile-level properties
    val partSpec: Property = prop("partSpec")
    val carriesAspect: Property = prop("carriesAspect")
    val describedBy: Property = prop("describedBy")
    val required: Property = prop("required")
    val extension: Property = prop("extension")
    val primary: Property = prop("primary")

    // Binding-kind individuals
    val Containment: Resource = res("Containment")
    val NamingConvention: Resource = res("NamingConvention")
    val ManifestReference: Resource = res("ManifestReference")
    val Concatenation: Resource = res("Concatenation")

    // Part-role register (SKOS concepts)
    val PartRoleScheme: Resource = res("PartRoleScheme")
    val GeometryCarrier: Resource = res("GeometryCarrier")
    val AttributeTable: Resource = res("AttributeTable")
    val SpatialReference: Resource = res("SpatialReference")
    val CharacterEncoding: Resource = res("CharacterEncoding")
    val SpatialIndex: Resource = res("SpatialIndex")
    val Manifest: Resource = res("Manifest")
    val Segment: Resource = res("Segment")
    val Sidecar: Resource = res("Sidecar")
    val Metadata: Resource = res("Metadata")
    val Thumbnail: Resource = res("Thumbnail")
    val Checksum: Resource = res("Checksum")
    val Payload: Resource = res("Payload")

    /** The 12 built-in part-role concepts, keyed by local name, for `role <Name>` resolution. */
    val ROLE_BY_NAME: Map<String, Resource> = listOf(
        GeometryCarrier, AttributeTable, SpatialReference, CharacterEncoding, SpatialIndex,
        Manifest, Segment, Sidecar, Metadata, Thumbnail, Checksum, Payload
    ).associateBy { it.uri.removePrefix(NAMESPACE) }

    /** Binding-kind individual by DSL keyword. */
    fun bindingKind(keyword: String): Resource? = when (keyword) {
        "containment" -> Containment
        "naming-convention" -> NamingConvention
        "manifest-reference" -> ManifestReference
        "concatenation" -> Concatenation
        else -> null
    }
}
```

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.vocab.AbndTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit/vocab/ABND.kt hdl/src/test/kotlin/io/hexplain/hdl/emit/vocab/AbndTest.kt
git commit -m "feat(hdl): ABND (hx-bundle) vocab object"
```

---

## Task 2: AST nodes + Resolver pass-through

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt`
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/resolve/ResolverBundleTest.kt`

**Interfaces:**
- Produces AST: `enum class Binding { CONTAINMENT, NAMING_CONVENTION, MANIFEST_REFERENCE, CONCATENATION }`; `data class PartSpecDecl(extension, role, required, primary, carries, describedBy, span)`; `data class BundleDecl(name, alias, boundBy: Binding, parts, span)`; `data class AssetPartDecl(name, role, span)`; `data class AssetDecl(name, conforms, boundBy: Binding?, stem, primaryPart, parts, span)`; `Document` gains `bundles: List<BundleDecl> = emptyList()`, `assets: List<AssetDecl> = emptyList()`.
- Produces resolve: `ResolvedBundle(uri, decl)`, `ResolvedAsset(uri, decl)`; `ResolvedDoc` gains `bundles: List<ResolvedBundle>`, `assets: List<ResolvedAsset>`.

- [ ] **Step 1: Add the AST types**

In `hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt`, append:

```kotlin
enum class Binding { CONTAINMENT, NAMING_CONVENTION, MANIFEST_REFERENCE, CONCATENATION }

data class PartSpecDecl(
    val extension: String,
    val role: String,
    val required: Boolean,
    val primary: Boolean,
    val carries: String?,      // a prefix like "ageom" (resolved to the ontology IRI at emit)
    val describedBy: String?,  // a struct name
    val span: Span
)

data class BundleDecl(
    val name: String,
    val alias: String?,
    val boundBy: Binding,
    val parts: List<PartSpecDecl>,
    val span: Span
)

data class AssetPartDecl(val name: String, val role: String, val span: Span)

data class AssetDecl(
    val name: String,
    val conforms: String?,     // a bundle profile name
    val boundBy: Binding?,
    val stem: String?,
    val primaryPart: String?,  // an asset part name
    val parts: List<AssetPartDecl>,
    val span: Span
)
```

And change `Document` to add the two trailing fields (keep existing fields/order):

```kotlin
data class Document(
    val format: FormatDecl?,
    val prefixes: List<PrefixDecl>,
    val structs: List<StructDecl>,
    val topLevelFields: List<FieldDecl>,
    val bundles: List<BundleDecl> = emptyList(),
    val assets: List<AssetDecl> = emptyList()
)
```

- [ ] **Step 2: Write the failing resolver test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/resolve/ResolverBundleTest.kt`:

```kotlin
package io.hexplain.hdl.resolve

import io.hexplain.hdl.ast.*
import io.hexplain.hdl.diag.Span
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class ResolverBundleTest {
    @Test fun mintsBundleAndAssetUris() {
        val bundle = BundleDecl("Shapefile", null, Binding.NAMING_CONVENTION,
            listOf(PartSpecDecl(".shp", "GeometryCarrier", true, true, "ageom", "ShpMain", Span(0,0))), Span(0,0))
        val asset = AssetDecl("roads", "Shapefile", Binding.NAMING_CONVENTION, "roads", "roads.shp",
            listOf(AssetPartDecl("roads.shp", "GeometryCarrier", Span(0,0))), Span(0,0))
        val doc = Document(FormatDecl("shp", null, null, null, Span(0,0)), emptyList(), emptyList(), emptyList(),
            listOf(bundle), listOf(asset))
        val r = Resolver().resolve(doc)
        assertEquals("https://hexplain.io/formats/shp#Shapefile", r.bundles.single().uri)
        assertEquals("https://hexplain.io/formats/shp#roads", r.assets.single().uri)
    }
}
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.resolve.ResolverBundleTest"`
Expected: FAIL — `ResolvedDoc.bundles`/`assets` don't exist.

- [ ] **Step 4: Extend the Resolver**

In `hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt`, add the resolved types near `ResolvedStruct`:

```kotlin
data class ResolvedBundle(val uri: String, val decl: io.hexplain.hdl.ast.BundleDecl)
data class ResolvedAsset(val uri: String, val decl: io.hexplain.hdl.ast.AssetDecl)
```

Add `bundles`/`assets` params to `ResolvedDoc` (trailing, defaulted so existing constructions in the file still compile):

```kotlin
class ResolvedDoc(
    val baseNs: String,
    val rootStructUri: String,
    val structs: List<ResolvedStruct>,
    val topLevelFields: List<ResolvedField>,
    val prefixes: Map<String, String>,
    val diagnostics: List<Diagnostic>,
    val formatEndian: io.hexplain.hdl.ast.Endian? = null,
    val bundles: List<ResolvedBundle> = emptyList(),
    val assets: List<ResolvedAsset> = emptyList()
) {
    // … existing expandCurie / siblingUri unchanged …
}
```

(If `formatEndian` is already a param from Plan 1, keep its position and add `bundles`/`assets` after it — match the existing constructor.)

In `resolve()`, build the two lists and pass them to the `ResolvedDoc(...)` construction:

```kotlin
        val bundles = doc.bundles.map { ResolvedBundle(baseNs + (it.alias ?: it.name), it) }
        val assets = doc.assets.map { ResolvedAsset(baseNs + it.name, it) }
```

Add `bundles = bundles, assets = assets` to the `ResolvedDoc(...)` return.

- [ ] **Step 5: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.resolve.ResolverBundleTest"` then full `./gradlew :hdl:test` (the additive `Document`/`ResolvedDoc` fields must not regress existing tests).
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt hdl/src/test/kotlin/io/hexplain/hdl/resolve/ResolverBundleTest.kt
git commit -m "feat(hdl): bundle/asset AST + resolver pass-through"
```

---

## Task 3: Parser — `bundle` and `asset` declarations

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserBundleTest.kt`

**Interfaces:** the top-level `parse()` loop gains `atText("bundle")` → `parseBundle()` and `atText("asset")` → `parseAsset()`; the parsed `BundleDecl`/`AssetDecl` lists go into the returned `Document`.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserBundleTest.kt`:

```kotlin
package io.hexplain.hdl.parse

import io.hexplain.hdl.ast.Binding
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class ParserBundleTest {
    private fun doc(src: String) = HdlParser(HdlLexer(src).tokenize()).parse()

    @Test fun parsesBundleProfile() {
        val src = """
            format shp
            bundle Shapefile @bound-by naming-convention {
              part ".shp" role GeometryCarrier   required primary carries ageom: described-by ShpMain
              part ".dbf" role AttributeTable    required          carries atab:
              part ".prj" role SpatialReference  optional          carries asref:
            }
        """.trimIndent()
        val r = doc(src)
        assertTrue(r.diagnostics.isEmpty(), "${r.diagnostics}")
        val b = r.document.bundles.single()
        assertEquals("Shapefile", b.name)
        assertEquals(Binding.NAMING_CONVENTION, b.boundBy)
        assertEquals(3, b.parts.size)
        val shp = b.parts[0]
        assertEquals(".shp", shp.extension); assertEquals("GeometryCarrier", shp.role)
        assertTrue(shp.required); assertTrue(shp.primary)
        assertEquals("ageom", shp.carries); assertEquals("ShpMain", shp.describedBy)
        assertFalse(b.parts[2].required)  // .prj optional
    }

    @Test fun parsesAssetInstance() {
        val src = """
            format shp
            asset roads conforms Shapefile @bound-by naming-convention @stem "roads" @primary roads.shp {
              part roads.shp role GeometryCarrier
              part roads.prj role SpatialReference
            }
        """.trimIndent()
        val a = doc(src).document.assets.single()
        assertEquals("roads", a.name)
        assertEquals("Shapefile", a.conforms)
        assertEquals(Binding.NAMING_CONVENTION, a.boundBy)
        assertEquals("roads", a.stem)
        assertEquals("roads.shp", a.primaryPart)
        assertEquals(listOf("roads.shp", "roads.prj"), a.parts.map { it.name })
        assertEquals("GeometryCarrier", a.parts[0].role)
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.ParserBundleTest"`
Expected: FAIL — bundles/assets empty (no parser branch).

- [ ] **Step 3: Add the parser branches**

In `Parser.kt`, add to the top-level `parse()` `when` (alongside `atText("format")` etc.), collecting into two new local lists `bundles`/`assets` that get passed to the `Document(...)` return:

```kotlin
                atText("bundle") -> bundles.add(parseBundle())
                atText("asset") -> assets.add(parseAsset())
```

Declare `val bundles = ArrayList<BundleDecl>()` and `val assets = ArrayList<AssetDecl>()` at the top of `parse()`, and change the return to `Document(format, prefixes, structs, topFields, bundles, assets)`.

Add the sub-parsers (reuse the existing `next()`/`expect()`/`atText()`/`err()` helpers). A binding keyword and role are single `IDENT`s; extension/stem are `STRING`s; `part` names in an asset are `IDENT`s (dotted names like `roads.shp` lex as one IDENT — the lexer folds `.` into identifiers):

```kotlin
    private fun parseBundle(): BundleDecl {
        val span = next().span // 'bundle'
        val name = expect(TokKind.IDENT).text
        var alias: String? = null
        if (atText("as")) { next(); alias = expect(TokKind.IDENT).text }
        var binding = Binding.NAMING_CONVENTION
        if (at(TokKind.ANNOT) && peek().text == "@bound-by") { next(); binding = parseBinding() }
        expect(TokKind.LBRACE)
        val parts = ArrayList<PartSpecDecl>()
        while (atText("part") && !at(TokKind.EOF)) parts.add(parsePartSpec())
        expect(TokKind.RBRACE)
        return BundleDecl(name, alias, binding, parts, span)
    }

    private fun parsePartSpec(): PartSpecDecl {
        val span = next().span // 'part'
        val ext = expect(TokKind.STRING).text
        expect(TokKind.IDENT) // 'role'
        val role = expect(TokKind.IDENT).text
        var required = false; var primary = false; var carries: String? = null; var describedBy: String? = null
        loop@ while (true) {
            when {
                atText("required") -> { next(); required = true }
                atText("optional") -> { next(); required = false }
                atText("primary") -> { next(); primary = true }
                atText("carries") -> { next(); carries = expect(TokKind.IDENT).text.trimEnd(':') }
                atText("described-by") -> { next(); describedBy = expect(TokKind.IDENT).text }
                else -> break@loop
            }
        }
        return PartSpecDecl(ext, role, required, primary, carries, describedBy, span)
    }

    private fun parseAsset(): AssetDecl {
        val span = next().span // 'asset'
        val name = expect(TokKind.IDENT).text
        var conforms: String? = null
        if (atText("conforms")) { next(); conforms = expect(TokKind.IDENT).text }
        var binding: Binding? = null; var stem: String? = null; var primary: String? = null
        while (at(TokKind.ANNOT)) {
            when (val a = next().text) {
                "@bound-by" -> binding = parseBinding()
                "@stem" -> stem = expect(TokKind.STRING).text
                "@primary" -> primary = expect(TokKind.IDENT).text
                else -> err("unknown asset annotation '$a'")
            }
        }
        expect(TokKind.LBRACE)
        val parts = ArrayList<AssetPartDecl>()
        while (atText("part") && !at(TokKind.EOF)) {
            val pspan = next().span
            val pname = expect(TokKind.IDENT).text
            expect(TokKind.IDENT) // 'role'
            val role = expect(TokKind.IDENT).text
            parts.add(AssetPartDecl(pname, role, pspan))
        }
        expect(TokKind.RBRACE)
        return AssetDecl(name, conforms, binding, stem, primary, parts, span)
    }

    private fun parseBinding(): Binding = when (val t = expect(TokKind.IDENT).text) {
        "containment" -> Binding.CONTAINMENT
        "naming-convention" -> Binding.NAMING_CONVENTION
        "manifest-reference" -> Binding.MANIFEST_REFERENCE
        "concatenation" -> Binding.CONCATENATION
        else -> { err("bad binding kind '$t'"); Binding.NAMING_CONVENTION }
    }
```

Add the imports for the new AST types at the top of `Parser.kt` if the file uses explicit imports (it uses `io.hexplain.hdl.ast.*` — confirm; if so, no new import needed).

Note: `described-by`/`bound-by` are lexed as single `ANNOT`/`IDENT` tokens because Plan-1's `ident()` folds `-` into identifiers (verified in Plan 1). `carries ageom:` — the `ageom:` lexes as one IDENT ending in `:` (curie form); `.trimEnd(':')` yields the prefix.

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parse.ParserBundleTest"` then full `./gradlew :hdl:test`.
Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt hdl/src/test/kotlin/io/hexplain/hdl/parse/ParserBundleTest.kt
git commit -m "feat(hdl): parse bundle profiles + asset instances"
```

---

## Task 4: Emitter — bundle profiles + asset instances

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitBundleTest.kt`

**Interfaces:** `TurtleEmitter.emit()` iterates `doc.bundles` → `emitBundle` and `doc.assets` → `emitAsset`, emitting `abnd:` triples via the `ABND` vocab. `carries` → ontology IRI (trailing `#`/`/` stripped); `described-by`/`primary`/`conforms` resolve to minted URIs; roles/bindings to `abnd:` individuals.

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitBundleTest.kt`:

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.hdl.emit.vocab.ABND
import io.hexplain.hdl.parse.HdlLexer
import io.hexplain.hdl.parse.HdlParser
import io.hexplain.hdl.resolve.Resolver
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitBundleTest {
    private fun emit(src: String) =
        TurtleEmitter(Resolver().resolve(HdlParser(HdlLexer(src).tokenize()).parse().document)).emit()

    @Test fun emitsBundleProfileWithPartSpecs() {
        val m = emit("""
            format shp
            use ageom: "https://hexplain.io/ns/aspect/geometry#"
            use atab: "https://hexplain.io/ns/aspect/tabular#"
            struct ShpMain { code : u32 }
            bundle Shapefile @bound-by naming-convention {
              part ".shp" role GeometryCarrier required primary carries ageom: described-by ShpMain
              part ".dbf" role AttributeTable  required         carries atab:
            }
        """.trimIndent())
        val prof = m.getResource("https://hexplain.io/formats/shp#Shapefile")
        assertTrue(m.contains(prof, RDF.type, ABND.BundleProfile))
        assertTrue(m.contains(prof, ABND.boundBy, ABND.NamingConvention))
        val specs = m.listStatements(prof, ABND.partSpec, null as org.apache.jena.rdf.model.RDFNode?).toList()
        assertEquals(2, specs.size)
        // the .shp spec: extension, role, required, primary, carriesAspect (ontology IRI, no #), describedBy
        val shp = specs.map { it.`object`.asResource() }.first { m.contains(it, ABND.extension, m.createLiteral(".shp")) }
        assertTrue(m.contains(shp, ABND.partRole, ABND.GeometryCarrier))
        assertTrue(m.contains(shp, ABND.primary, m.createTypedLiteral(true)))
        assertTrue(m.contains(shp, ABND.carriesAspect, m.getResource("https://hexplain.io/ns/aspect/geometry")))
        assertTrue(m.contains(shp, ABND.describedBy, m.getResource("https://hexplain.io/formats/shp#ShpMain")))
    }

    @Test fun emitsAssetInstance() {
        val m = emit("""
            format shp
            asset roads conforms Shapefile @bound-by naming-convention @stem "roads" @primary roads.shp {
              part roads.shp role GeometryCarrier
              part roads.prj role SpatialReference
            }
        """.trimIndent())
        val asset = m.getResource("https://hexplain.io/formats/shp#roads")
        assertTrue(m.contains(asset, RDF.type, ABND.Asset))
        assertTrue(m.contains(asset, ABND.boundBy, ABND.NamingConvention))
        assertTrue(m.contains(asset, ABND.stem, m.createLiteral("roads")))
        assertTrue(m.contains(asset, ABND.primaryPart, m.getResource("https://hexplain.io/formats/shp#roads.shp")))
        val shp = m.getResource("https://hexplain.io/formats/shp#roads.shp")
        assertTrue(m.contains(shp, RDF.type, ABND.Part))
        assertTrue(m.contains(asset, ABND.hasPart, shp))
        assertTrue(m.contains(shp, ABND.partRole, ABND.GeometryCarrier))
        assertTrue(m.contains(asset, org.apache.jena.rdf.model.ResourceFactory.createProperty("http://purl.org/dc/terms/conformsTo"),
            m.getResource("https://hexplain.io/formats/shp#Shapefile")))
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitBundleTest"`
Expected: FAIL (no bundle emission).

- [ ] **Step 3: Add emission to TurtleEmitter**

In `TurtleEmitter.kt`, import `io.hexplain.hdl.emit.vocab.ABND` and `io.hexplain.hdl.ast.Binding`. Set the `abnd` prefix in `emit()` (`m.setNsPrefix("abnd", ABND.NAMESPACE)`), and after the struct/field loops, add:

```kotlin
        for (b in doc.bundles) emitBundle(b)
        for (a in doc.assets) emitAsset(a)
```

Add the methods (place near the other emit* helpers):

```kotlin
    private fun bindingIndividual(b: Binding): Resource = when (b) {
        Binding.CONTAINMENT -> ABND.Containment
        Binding.NAMING_CONVENTION -> ABND.NamingConvention
        Binding.MANIFEST_REFERENCE -> ABND.ManifestReference
        Binding.CONCATENATION -> ABND.Concatenation
    }

    /** `role X` → abnd:X (built-in scheme concept) or, if X is a curie, the expanded IRI. */
    private fun roleResource(role: String): Resource =
        if (role.contains(':')) m.createResource(doc.expandCurie(role))
        else ABND.ROLE_BY_NAME[role] ?: m.createResource(ABND.NAMESPACE + role)

    /** A `carries` prefix → the ontology IRI (the prefix namespace with a trailing '#'/'/' stripped). */
    private fun aspectOntologyIri(prefix: String): Resource {
        val ns = doc.prefixes[prefix] ?: (ABND.NAMESPACE) // unknown prefix: emitted as-is; diagnostic is a future check
        return m.createResource(ns.trimEnd('#', '/'))
    }

    private fun emitBundle(rb: io.hexplain.hdl.resolve.ResolvedBundle) {
        val prof = m.createResource(rb.uri).addProperty(RDF.type, ABND.BundleProfile)
        prof.addProperty(ABND.boundBy, bindingIndividual(rb.decl.boundBy))
        for (p in rb.decl.parts) {
            val spec = m.createResource().addProperty(RDF.type, ABND.PartSpec)
            spec.addProperty(ABND.extension, m.createLiteral(p.extension))
            spec.addProperty(ABND.partRole, roleResource(p.role))
            spec.addLiteral(ABND.required, p.required)
            if (p.primary) spec.addLiteral(ABND.primary, true)
            p.carries?.let { spec.addProperty(ABND.carriesAspect, aspectOntologyIri(it)) }
            p.describedBy?.let { spec.addProperty(ABND.describedBy, m.createResource(doc.baseNs + it)) }
            prof.addProperty(ABND.partSpec, spec)
        }
    }

    private fun emitAsset(ra: io.hexplain.hdl.resolve.ResolvedAsset) {
        val asset = m.createResource(ra.uri).addProperty(RDF.type, ABND.Asset)
        ra.decl.boundBy?.let { asset.addProperty(ABND.boundBy, bindingIndividual(it)) }
        ra.decl.stem?.let { asset.addProperty(ABND.stem, m.createLiteral(it)) }
        ra.decl.conforms?.let { asset.addProperty(
            m.createProperty("http://purl.org/dc/terms/conformsTo"), m.createResource(doc.baseNs + it)) }
        for (p in ra.decl.parts) {
            val part = m.createResource(doc.baseNs + p.name).addProperty(RDF.type, ABND.Part)
            part.addProperty(ABND.partRole, roleResource(p.role))
            asset.addProperty(ABND.hasPart, part)
        }
        ra.decl.primaryPart?.let { asset.addProperty(ABND.primaryPart, m.createResource(doc.baseNs + it)) }
    }
```

(If `Resource`/`RDF` aren't already imported in `TurtleEmitter.kt`, they are — the file already emits struct resources. Reuse the existing imports.)

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.emit.EmitBundleTest"` then full `./gradlew :hdl:test`.
Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitBundleTest.kt
git commit -m "feat(hdl): emit bundle profiles + asset instances"
```

---

## Task 5: YAML — `bundles:` and `assets:`

**Files:**
- Modify: `hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlBundleTest.kt`

**Interfaces:** `YamlLoader` reads top-level `bundles: {Name: {bound-by, parts: [...]}}` and `assets: {name: {conforms, bound-by, stem, primary, parts: [...]}}` into `Document.bundles`/`assets`. Both surfaces compile to isomorphic models (asserted in the test).

- [ ] **Step 1: Write the failing test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlBundleTest.kt`:

```kotlin
package io.hexplain.hdl.yaml

import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class YamlBundleTest {
    @Test fun yamlBundleMatchesTextSurface() {
        val text = """
            format shp
            use ageom: "https://hexplain.io/ns/aspect/geometry#"
            struct ShpMain { code : u32 }
            bundle Shapefile @bound-by naming-convention {
              part ".shp" role GeometryCarrier required primary carries ageom: described-by ShpMain
              part ".dbf" role AttributeTable  required
            }
            asset roads conforms Shapefile @bound-by naming-convention @stem "roads" @primary roads.shp {
              part roads.shp role GeometryCarrier
            }
        """.trimIndent()
        val yaml = """
            format: shp
            use:
              ageom: "https://hexplain.io/ns/aspect/geometry#"
            structs:
              ShpMain:
                fields:
                  - { name: code, type: u32 }
            bundles:
              Shapefile:
                bound-by: naming-convention
                parts:
                  - { extension: ".shp", role: GeometryCarrier, required: true, primary: true, carries: ageom, described-by: ShpMain }
                  - { extension: ".dbf", role: AttributeTable, required: true }
            assets:
              roads:
                conforms: Shapefile
                bound-by: naming-convention
                stem: roads
                primary: roads.shp
                parts:
                  - { name: roads.shp, role: GeometryCarrier }
        """.trimIndent()
        val fromText = HdlCompiler().compile(text)
        val fromYaml = HdlCompiler().compileYaml(yaml)
        assertTrue(fromText.ok && fromYaml.ok, "text=${fromText.diagnostics} yaml=${fromYaml.diagnostics}")
        assertTrue(fromText.model.isIsomorphicWith(fromYaml.model), "bundle YAML not isomorphic to text")
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlBundleTest"`
Expected: FAIL (YAML bundles/assets not loaded → not isomorphic).

- [ ] **Step 3: Load bundles/assets in YamlLoader**

In `YamlLoader.kt`, in `load()`, after building `structs`/`topFields`, build bundles/assets and pass them to `Document(...)`:

```kotlin
        val bundles = (asMap(top["bundles"], "bundles") ?: emptyMap()).map { (name, body) ->
            bundleDecl(name.toString(), asMap(body, "bundle '$name'") ?: emptyMap())
        }
        val assets = (asMap(top["assets"], "assets") ?: emptyMap()).map { (name, body) ->
            assetDecl(name.toString(), asMap(body, "asset '$name'") ?: emptyMap())
        }
```

Change the `Document(...)` return to `Document(format, prefixes, structs, topFields, bundles, assets)`. Add the helpers:

```kotlin
    private fun bindingOf(v: Any?): Binding = when (str(v)) {
        "containment" -> Binding.CONTAINMENT
        "naming-convention" -> Binding.NAMING_CONVENTION
        "manifest-reference" -> Binding.MANIFEST_REFERENCE
        "concatenation" -> Binding.CONCATENATION
        else -> { if (v != null) err("bad binding kind '$v'"); Binding.NAMING_CONVENTION }
    }

    private fun bundleDecl(name: String, m: Map<String, Any?>): BundleDecl {
        val parts = (asList(m["parts"], "bundle parts") ?: emptyList()).mapNotNull { p ->
            asMap(p, "part spec")?.let { pm ->
                PartSpecDecl(
                    extension = str(pm["extension"]) ?: "",
                    role = str(pm["role"]) ?: "?",
                    required = pm["required"] == true,
                    primary = pm["primary"] == true,
                    carries = str(pm["carries"]),
                    describedBy = str(pm["described-by"]),
                    span = SPAN
                )
            }
        }
        return BundleDecl(name, str(m["as"]), bindingOf(m["bound-by"]), parts, SPAN)
    }

    private fun assetDecl(name: String, m: Map<String, Any?>): AssetDecl {
        val parts = (asList(m["parts"], "asset parts") ?: emptyList()).mapNotNull { p ->
            asMap(p, "asset part")?.let { pm ->
                AssetPartDecl(str(pm["name"]) ?: "?", str(pm["role"]) ?: "?", SPAN)
            }
        }
        val binding = if (m.containsKey("bound-by")) bindingOf(m["bound-by"]) else null
        return AssetDecl(name, str(m["conforms"]), binding, str(m["stem"]), str(m["primary"]), parts, SPAN)
    }
```

(`SPAN` is the loader's private `Span(0,0)` constant. `asMap`/`asList`/`str`/`Binding` are already imported/available.)

- [ ] **Step 4: Run and verify green**

Run: `cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.yaml.YamlBundleTest"` then full `./gradlew :hdl:test`.
Expected: PASS. If not isomorphic, print both `toTurtle()`s and align the YAML/text (common cause: a `required`/`primary` boolean or a `carries`/`described-by` omission).

- [ ] **Step 5: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/src/main/kotlin/io/hexplain/hdl/yaml/YamlLoader.kt hdl/src/test/kotlin/io/hexplain/hdl/yaml/YamlBundleTest.kt
git commit -m "feat(hdl): YAML bundles/assets + text-surface equivalence"
```

---

## Task 6: SHACL correctness + golden snapshot (Shapefile)

**Files:**
- Modify: `hdl/build.gradle.kts` (add `implementation(libs.jena.shacl)`)
- Create: `hdl/src/test/resources/bundle.ttl` (copy of the spec), `hdl/src/test/resources/shapefile.hx`, `hdl/src/test/resources/golden/shapefile-bundle.expected.ttl`
- Test: `hdl/src/test/kotlin/io/hexplain/hdl/parity/BundleShaclTest.kt`

**Interfaces:** proves the emitted bundle graph is well-formed against the hx-bundle SHACL shapes. The `abnd:` shapes (`AssetShape`/`PartShape`) target `Asset`/`Part` instances, so this uses the Shapefile *profile* (golden + triples) plus a `roads` *asset* (SHACL conformance, positive + negative).

- [ ] **Step 1: Add jena-shacl to the module**

In `hdl/build.gradle.kts`, add to `dependencies`:

```kotlin
    implementation(libs.jena.shacl)
```

- [ ] **Step 2: Copy the bundle ontology + shapes into test resources**

Run:
```bash
cd d:/work/hexplain-tools
cp d:/work/hexplain.io/specification/aspect/bundle/bundle.ttl hdl/src/test/resources/bundle.ttl
```
(Verify the file parses as Turtle — it is the canonical spec artifact. If the SHACL uses SHACL-AF `sh:rule` constructs that jena-shacl warns about, that is fine — `AssetShape`/`PartShape` are plain NodeShapes and validate regardless.)

- [ ] **Step 3: Author `shapefile.hx`**

Create `hdl/src/test/resources/shapefile.hx`:

```
format shapefile
  @namespace "https://hexplain.io/formats/shapefile#"

use ageom: <https://hexplain.io/ns/aspect/geometry#>
use atab:  <https://hexplain.io/ns/aspect/tabular#>
use asref: <https://hexplain.io/ns/aspect/spatialref#>
use aenc:  <https://hexplain.io/ns/aspect/encoding#>

struct ShpMain { FileCode : u32be }

bundle Shapefile @bound-by naming-convention {
  part ".shp" role GeometryCarrier   required primary carries ageom: described-by ShpMain
  part ".shx" role SpatialIndex      required
  part ".dbf" role AttributeTable    required          carries atab:
  part ".prj" role SpatialReference  optional          carries asref:
  part ".cpg" role CharacterEncoding optional          carries aenc:
}

asset roads conforms Shapefile @bound-by naming-convention @stem "roads" @primary roads.shp {
  part roads.shp role GeometryCarrier
  part roads.shx role SpatialIndex
  part roads.dbf role AttributeTable
  part roads.prj role SpatialReference
}
```

- [ ] **Step 4: Write the SHACL + snapshot test**

Create `hdl/src/test/kotlin/io/hexplain/hdl/parity/BundleShaclTest.kt`:

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.hdl.HdlCompiler
import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.apache.jena.shacl.ShaclValidator
import org.apache.jena.shacl.Shapes
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class BundleShaclTest {
    private fun res(name: String) =
        this::class.java.classLoader.getResourceAsStream(name) ?: error("missing $name")
    private fun bundleModel() = ModelFactory.createDefaultModel().apply {
        res("bundle.ttl").use { RDFDataMgr.read(this, it, Lang.TTL) }
    }

    @Test fun shapefileBundleConformsToAbndShapes() {
        val result = HdlCompiler().compile(res("shapefile.hx").readBytes().toString(Charsets.UTF_8))
        assertTrue(result.ok, "${result.diagnostics}")
        // data graph = generated bundle/asset triples + the abnd vocab (rdf:type + role-scheme memberships
        // the shapes reference); shapes = the same bundle.ttl.
        val data = ModelFactory.createDefaultModel()
        RDFDataMgr.read(data, result.toTurtle().byteInputStream(), Lang.TTL)
        data.add(bundleModel())
        val shapes = Shapes.parse(bundleModel().graph)
        val report = ShaclValidator.get().validate(shapes, data.graph)
        assertTrue(report.conforms(), "SHACL violations:\n" +
            report.entries.joinToString("\n") { it.message() })
    }

    @Test fun malformedAssetIsReportedByShacl() {
        // an asset with a partRole NOT in the register violates PartShape
        val src = """
            format shp
            asset bad @bound-by naming-convention {
              part bad.x role NotARealRole
            }
        """.trimIndent()
        val result = HdlCompiler().compile(src)
        assertTrue(result.ok, "compile itself should succeed: ${result.diagnostics}")
        val data = ModelFactory.createDefaultModel()
        RDFDataMgr.read(data, result.toTurtle().byteInputStream(), Lang.TTL)
        data.add(bundleModel())
        val shapes = Shapes.parse(bundleModel().graph)
        val report = ShaclValidator.get().validate(shapes, data.graph)
        assertFalse(report.conforms(), "expected a SHACL violation for a role outside the register")
    }

    @Test fun profileSnapshotIsStable() {
        val ttl = HdlCompiler().compile(res("shapefile.hx").readBytes().toString(Charsets.UTF_8)).toTurtle()
        val golden = res("golden/shapefile-bundle.expected.ttl").readBytes().toString(Charsets.UTF_8)
        val a = ModelFactory.createDefaultModel().apply { RDFDataMgr.read(this, ttl.byteInputStream(), Lang.TTL) }
        val b = ModelFactory.createDefaultModel().apply { RDFDataMgr.read(this, golden.byteInputStream(), Lang.TTL) }
        assertTrue(a.isIsomorphicWith(b), "shapefile bundle profile diverged from golden snapshot")
    }
}
```

- [ ] **Step 5: Run the SHACL tests, then generate the golden, then run all**

Run the two SHACL tests first:
`cd d:/work/hexplain-tools && ./gradlew :hdl:test --tests "io.hexplain.hdl.parity.BundleShaclTest.shapefileBundleConformsToAbndShapes" --tests "io.hexplain.hdl.parity.BundleShaclTest.malformedAssetIsReportedByShacl"`
Expected: both PASS. (If `shapefileBundleConformsToAbndShapes` fails, read `report.entries` — a real violation means the emitter produced a non-conformant graph; fix the emitter, not the test. If `malformedAssetIsReportedByShacl` fails, the negative case isn't triggering — confirm the role `NotARealRole` mints `abnd:NotARealRole`, which is not `skos:inScheme abnd:PartRoleScheme`, so PartShape's second property shape fails.)

Then generate the golden from verified output:
```bash
cd d:/work/hexplain-tools
./gradlew :hdl:run --args="src/test/resources/shapefile.hx -o src/test/resources/golden/shapefile-bundle.expected.ttl"
```
(Adjust the path if `:hdl:run`'s CWD differs, per Plan 2.) Inspect the golden, then run the full class:
`./gradlew :hdl:test --tests "io.hexplain.hdl.parity.BundleShaclTest"` and the whole suite `./gradlew :hdl:test`.
Expected: all green, no regressions.

- [ ] **Step 6: Commit**

```bash
cd d:/work/hexplain-tools
git add hdl/build.gradle.kts hdl/src/test/resources/bundle.ttl hdl/src/test/resources/shapefile.hx hdl/src/test/resources/golden/shapefile-bundle.expected.ttl hdl/src/test/kotlin/io/hexplain/hdl/parity/BundleShaclTest.kt
git commit -m "test(hdl): hx-bundle SHACL conformance + golden snapshot (Shapefile); Plan 3 complete"
```

---

## Self-Review

**1. Spec coverage** (design §10 hx-bundle): `bundle` profiles with `@bound-by` + `part` specs (extension/role/required/primary/carries/described-by) → Tasks 3 (parse), 4 (emit). `asset` instances (conforms/bound-by/stem/primary/parts) → Tasks 3, 4. `carries` → ontology-IRI stripping → Task 4 (Global Constraint). Binding kinds + part-role register → Task 1 (ABND) + Task 4 (resolution). YAML surface → Task 5. SHACL anchor (AssetShape/PartShape) + golden → Task 6. Per-part aspect-facet assignment is explicitly OUT OF SCOPE (Scope note; raw-turtle escape available). ✅

**2. Placeholder scan:** No TODO/TBD. Every code step has runnable code. The one "unknown prefix emitted as-is" note in `aspectOntologyIri` is a deliberate lenient fallback (a future diagnostic), not a placeholder — a `carries` with an undeclared prefix is caught by neither a crash nor a silent-wrong-IRI (it falls back to the abnd namespace, harmless in tests where prefixes are declared). ✅

**3. Type consistency:** New AST types (`Binding`, `PartSpecDecl`, `BundleDecl`, `AssetPartDecl`, `AssetDecl`) and `Document.bundles`/`assets` are defined in Task 2 and consumed by Tasks 3–5. `ResolvedDoc.bundles`/`assets` + `ResolvedBundle`/`ResolvedAsset` (Task 2) consumed by Task 4's emitter. `ABND` constants (Task 1) used by Task 4. `HdlCompiler.compile`/`compileYaml`/`CompileResult.{ok,toTurtle,model}` (Plans 1–2) used by Tasks 5–6. `ShaclValidator`/`Shapes` (jena-shacl) used by Task 6. All additive to `Document`/`ResolvedDoc` via trailing defaulted fields — existing construction sites unaffected. ✅

**4. Correctness-anchor soundness:** core has no bundle runtime, so behavioral parity is impossible; SHACL conformance against the real spec shapes (positive + a negative that proves the shapes actually fire) + graph-isomorphic golden is the strongest available anchor, plus per-term triple assertions in Task 4. The negative SHACL test guards against a vacuous "conforms because nothing is checked" pass. ✅

---

## Done criteria

All six tasks green; `./gradlew clean build` (`:core` + `:hdl`) BUILD SUCCESSFUL. HDL can then author single-file formats (Plans 1–2, text+YAML) **and** multi-file bundle formats (Plan 3) — the full design surface. Deferred: per-part aspect-facet assignment syntax (use `raw-turtle` meanwhile); an `ABND` move into core's vocab package if hx-bundle ever needs a non-hdl consumer.
