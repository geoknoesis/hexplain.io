# Design — `hx-bundle`: Modeling Multi-File Formats as Unified Assets

**Status:** Draft for review · **Date:** 2026-07-26 · **Author:** Stephane Fellah
**Family:** Hexplain aspect-oriented ontology (pre-release, all modules v1.0)

## 1. Problem

Some formats are not a single file. A **shapefile** is a set of sibling files bound
only by a shared basename:

| file | carries | aspect |
|------|---------|--------|
| `.shp` | geometry | `ageom` |
| `.shx` | spatial index | (auxiliary) |
| `.dbf` | attribute table (dBASE) | `atab` |
| `.prj` | coordinate reference system (WKT) | `asref` |
| `.cpg` | code page for the `.dbf` | `aenc` (charset) |

No file contains the others. Yet together they are **one logical dataset**, and a
consumer wants to ask *"what is the CRS of this shapefile?"* against a single subject.

The existing `apkg` (packaging) aspect models only **containment** — a ZIP/TAR that
physically holds its entries inside one byte stream. It does not cover sibling-file
bundles, manifest-referenced bundles (glTF, DASH), or split/segmented streams. We need
a general model for **"N physical carriers → one logical Asset, whose unified semantics
are the merged aspect facets of its parts."**

## 2. Locked decisions (from brainstorming)

1. **General binding model** (not shapefile-only, not an in-place `apkg` hack). One
   abstraction covers every way parts bind: containment, naming-convention,
   manifest-reference, concatenation. `apkg` containment becomes one binding kind.
2. **Lift facets onto the Asset via inference.** Physical truth stays on the part
   (`crs` on `.prj`, columns on `.dbf`); a generic rule lifts *content-aspect*
   properties up to the single Asset node, so the Asset is queryable as one file while
   part-level provenance is preserved.
3. **Full `apkg` fold-in** (chosen over align-only): `apkg:Container`/`Entry` become
   subclasses of the new bundle terms. Touches AXV, but yields true unification. See
   §10 for the blast radius and the align-only fallback if review rejects it.

## 3. Where it sits — a fourth composition level

Hexplain already composes data at three levels. This adds one **below** the aspects:

```
BDDO        bytes of ONE part                 (.shp bytes, .dbf bytes …)
   ▲
hx-bundle   compose N parts → 1 Asset  ◀ NEW  (roads.* = one dataset)
   ▲
aspects     each part carries a facet; facets lift onto the Asset
            (ageom + atab + asref all become properties of the Asset)
```

`hx-bundle` is a **base aspect**: it imports nothing (preserving zero sideways
coupling). It composes with `afs` (fsmeta) and BDDO at the *instance* level without
importing them.

## 4. The `hx-bundle` aspect

- **Namespace:** `https://hexplain.io/ns/aspect/bundle#`
- **Label / prefix:** `hx-bundle` / `abnd` (collision-free against existing `a*` prefixes)
- **Path:** `specification/aspect/bundle/`

### 4.1 Classes

| term | meaning |
|------|---------|
| `abnd:Asset` | A logical resource realized by ≥1 physical part. The single unified semantic subject. `skos:closeMatch dcat:Dataset`. |
| `abnd:Part` | One physical carrier (a byte stream / file). Composes with `afs`/BDDO at instance level. |
| `abnd:BindingKind` | The mechanism binding parts (closed enum, §5). |
| `abnd:BundleProfile` | Reusable format template (§7). |
| `abnd:PartSpec` | One expected member within a profile (§7). |

### 4.2 Properties

Core properties below; the profile/PartSpec properties (`abnd:partSpec`,
`abnd:carriesAspect`, `abnd:describedBy`, `abnd:required`, `abnd:extension`,
`abnd:primary`) are defined with their classes in §7.

| term | domain → range | notes |
|------|----------------|-------|
| `abnd:hasPart` | Asset → Part | inverse `abnd:partOf` |
| `abnd:primaryPart` | Asset → Part | ⊑ `hasPart`; the recognition anchor / manifest |
| `abnd:partRole` | Part → `skos:Concept` | role register (§6) |
| `abnd:boundBy` | Asset → `abnd:BindingKind` | §5 |
| `abnd:partIndex` | Part → `xsd:nonNegativeInteger` | order, for segmented/concatenation |
| `abnd:stem` | Asset → `xsd:string` | convenience for naming-convention bundles |
| `abnd:liftsToAsset` | (annotation on a predicate) → `xsd:boolean` | marks a predicate as content-aspect that rolls up to the Asset (§8) |

## 5. Binding kinds — closed enum

Modeled as `owl:NamedIndividual`s of `abnd:BindingKind`, constrained by `sh:in` (per
the value-modeling rule for closed small enums with reasoning).

| individual | mechanism | examples |
|------------|-----------|----------|
| `abnd:Containment` | parts nested inside one byte stream | ZIP, TAR *(today's `apkg`)* |
| `abnd:NamingConvention` | sibling files, shared stem, role per extension | **Shapefile**, ENVI (`.hdr`+raw), GeoTIFF+`.tfw` |
| `abnd:ManifestReference` | a primary part references members by path/URI | glTF, DASH (`.mpd`), HLS (`.m3u8`), GDAL `.vrt` |
| `abnd:Concatenation` | parts are ordered fragments of ONE logical stream | multi-volume `.zip`/`.z01…`, split files |

### 5.1 `apkg` fold-in

```turtle
# apkg now owl:imports hx-bundle (downward edge — legal in the DAG)
apkg:Container rdfs:subClassOf    abnd:Asset .   # a Containment-bound Asset
apkg:Entry     rdfs:subClassOf    abnd:Part .
apkg:hasEntry  rdfs:subPropertyOf abnd:hasPart .
```

## 6. Part-role register (SKOS, open)

`abnd:PartRoleScheme` (`skos:ConceptScheme`) with initial concepts:
`GeometryCarrier`, `AttributeTable`, `SpatialReference`, `CharacterEncoding`,
`SpatialIndex`, `Manifest`, `Segment`, `Sidecar`, `Metadata`, `Thumbnail`,
`Checksum`, `Payload`. Open — new formats add roles without touching the aspect.

## 7. Format-definition vs instance

"Model the shapefile format" = a reusable **profile**; "describe `roads.*`" = an
**instance**.

- `abnd:BundleProfile` — `boundBy` kind + a set of `abnd:partSpec`.
- `abnd:PartSpec` — one expected member:
  - `abnd:partRole` (→ register), `abnd:extension` (e.g. `".dbf"`), `abnd:required`
    (`xsd:boolean`) / cardinality,
  - `abnd:carriesAspect` (→ the aspect ontology IRI this part contributes — annotation,
    **not** an `owl:import`, so orthogonality is preserved),
  - `abnd:describedBy` (→ `bddo:Struct` giving the part's byte layout — ties to the
    physical layer).

Instances link `Asset dcterms:conformsTo <profile>`; SHACL checks required parts.

## 8. Unification — lifting facets onto the Asset

Physical truth stays on the part. One generic SHACL-SPARQL rule lifts *marked*
predicates to the Asset, so physical/fs properties (`fileName`, `byteLength`) never
leak up.

```turtle
asref:crs          abnd:liftsToAsset true .
ageom:geometryType abnd:liftsToAsset true .
atab:columnSchema  abnd:liftsToAsset true .

abnd:LiftFacetsRule a sh:NodeShape ;
  sh:targetClass abnd:Asset ;
  sh:rule [ a sh:SPARQLRule ;
    sh:construct """
      CONSTRUCT { $this ?p ?v }
      WHERE { $this abnd:hasPart ?part . ?part ?p ?v . ?p abnd:liftsToAsset true }""" ] .
```

Result: `Asset asref:crs "EPSG:4326"` is queryable directly, **and**
`Asset hasPart / [role=SpatialReference]` still identifies the source file.
Cardinality conflicts (e.g. two CRSs) surface through each aspect's own SHACL shape at
the Asset level.

**Open refinement (deferred):** sidecar *override/precedence* — a `.prj` next to a
`.tif` should override the TIFF's internal CRS. Base design unions; a precedence order
on `PartSpec` can be added when a consumer needs it (lazy factoring).

## 9. Worked examples

### 9.1 Shapefile (`NamingConvention`)

```turtle
# PROFILE (authored once)
fmt:Shapefile a abnd:BundleProfile ;
  abnd:boundBy abnd:NamingConvention ;
  abnd:partSpec
    [ abnd:extension ".shp" ; abnd:partRole role:GeometryCarrier   ; abnd:required true ;
      abnd:carriesAspect ageom: ; abnd:primary true ] ,
    [ abnd:extension ".shx" ; abnd:partRole role:SpatialIndex      ; abnd:required true ] ,
    [ abnd:extension ".dbf" ; abnd:partRole role:AttributeTable    ; abnd:required true ;
      abnd:carriesAspect atab: ; abnd:describedBy bddo:DBaseTable ] ,
    [ abnd:extension ".prj" ; abnd:partRole role:SpatialReference  ; abnd:required false ;
      abnd:carriesAspect asref: ] ,
    [ abnd:extension ".cpg" ; abnd:partRole role:CharacterEncoding ; abnd:required false ;
      abnd:carriesAspect aenc: ] .

# INSTANCE
ex:roads a abnd:Asset ; dcterms:conformsTo fmt:Shapefile ;
  abnd:boundBy abnd:NamingConvention ; abnd:stem "roads" ;
  abnd:primaryPart ex:roads.shp ;
  abnd:hasPart ex:roads.shp, ex:roads.shx, ex:roads.dbf, ex:roads.prj, ex:roads.cpg .

ex:roads.prj a abnd:Part ; abnd:partRole role:SpatialReference ;
  afs:fileName "roads.prj" ; asref:crs "EPSG:4326" .
ex:roads.shp a abnd:Part ; abnd:partRole role:GeometryCarrier ;
  afs:fileName "roads.shp" ; ageom:geometryType ageom:Polyline .
# after LiftFacetsRule:
# ex:roads asref:crs "EPSG:4326" ; ageom:geometryType ageom:Polyline ; atab:columnSchema … .
```

### 9.2 glTF (`ManifestReference`)

`.gltf` = `primaryPart` (role `Manifest`) referencing `.bin` (role `Payload` →
geometry/buffers) + `.png` (role `Payload` → `araster`/`acolor`). Same Asset/Part/lift;
different `boundBy`.

### 9.3 Multi-volume ZIP (`Concatenation` nesting into `Containment`)

`.zip`/`.z01`/`.z02` are ordered `Part`s (`partIndex` 0,1,2), `boundBy Concatenation`.
Their concatenation *is* an `apkg:Container` — one Asset composes a Concatenation
bundle whose logical stream is a Containment bundle. The model nests without special
cases.

## 10. SHACL conformance

- `abnd:ProfileConformanceShape` — for an `Asset` with `dcterms:conformsTo` a profile:
  every `required` PartSpec's role is present among `hasPart`; exactly one
  `primaryPart`; `boundBy` set; roles drawn from the register.
- `abnd:PartShape` — `partRole` in scheme; if the profile fixes an extension,
  `afs:fileName` must match it.

## 11. Blast radius & fallback

**Full fold-in (chosen):** `apkg` gains `owl:imports hx-bundle` and three
subclass/subproperty axioms. AXV (which composes `apkg`) is unaffected at the term
level — its `apkg:Container`/`hasEntry` usage still validates; it simply also becomes
an `abnd:Asset` by inference. Validation gate: all TTL + embedded HTML turtle parse;
SHACL clean; no duplicated term.

**Align-only fallback (if review rejects the fold-in):** leave `apkg` untouched and add
`skos:closeMatch` between `apkg:Container`↔`abnd:Asset` and `apkg:Entry`↔`abnd:Part`.
Less unification (a Container is not *inferred* to be an Asset), zero blast radius.

## 12. Architecture-doc updates

`specification/architecture/index.html` §3.7 (Container & system) gains `hx-bundle` as
the base aspect of that tier, with `hx-packaging` shown importing it. §5 (Domains as
Compositions) can add a **Bundle profiles** note: Shapefile / glTF / DASH are *profiles*
(domain + format-unique binding), consistent with the existing PROFILES concept.

## 13. Out of scope (future / lazy-factoring)

- Sidecar override precedence (§8) — add when a consumer needs it.
- A full glTF / DASH / GeoTIFF profile library — this spec ships **Shapefile** as the
  one worked profile; others follow the same shape on demand.
- `hx-style`/`hx-typography` interplay — unrelated, unchanged.

## 14. Open questions for review

1. **Name:** `hx-bundle`/`abnd` vs `hx-composite`/`acmp` vs `hx-multipart`.
2. **Fold-in vs align-only** (§11) — confirm full fold-in.
3. **`liftsToAsset` marker granularity** — per-predicate (as drafted) vs per-aspect
   (lift *all* properties defined by a content-aspect ontology). Per-predicate is more
   explicit; per-aspect is less to annotate.
