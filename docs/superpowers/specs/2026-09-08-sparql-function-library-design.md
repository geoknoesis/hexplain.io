# SPARQL function library: reaching bytes, cells and coordinates from a query

**Date:** 2026-09-08
**Status:** approved design, implementation in progress (plan: docs/superpowers/plans/2026-09-09-sparql-function-library.md)
**Repos touched:** `hexplain.io` (spec: `specification/fn/`), `hexplain-tools` (engine: new `query` module)

## Why

The graph Hexplain lifts from a file describes the file. It does not contain the file. A
query can ask for a raster's width, its band count, its georeferencing and the byte range of
its sample grid, but it cannot ask for the value of the pixel at column 412, row 97. The
samples are never triples, and they should not be: a modest 2000 x 2000 three-band image is
twelve million cell values before a single subject or coordinate triple is added.

The engine can already produce those values. The metaparser walks any described format, the
`MultiDimensionalData` accessor addresses cells through a `DataLayoutIR`, the codec registry
inverts encoding chains, and the raster path is being moved onto the descriptors (see
`2026-09-06-descriptor-driven-raster-design.md`). What is missing is a SPARQL surface over
that machinery, so that a query stays over the description graph and reaches into the bytes
only for the values it names.

This document designs that surface as a **library of custom SPARQL functions**. The
governing requirement is reuse across formats: a function must be written once against the
description vocabularies (BDDO, DLV, core, the aspects) and work for every profile that uses
them. No function in this library knows what TIFF, NITF, PNG, Zarr, WAV or a shapefile is.

## Assumptions

You were not available for a question-by-question design loop, so the following choices are
made explicitly and are the first things to challenge in review.

1. **Engine is Jena ARQ.** The tools repo already depends on `jena-arq` and `jena-shacl`, and
   `BundleProcessor` runs a SHACL-AF rule through ARQ. Functions are registered in ARQ's
   `FunctionRegistry` and `PropertyFunctionRegistry`. Fuseki hosting is a packaging concern,
   not a design one.
2. **Instance graphs come from the Semantic Lifter as it is today.** Every lifted resource has
   a named IRI `<baseUri>#<path>` (no blank nodes), and carries `hexplain:byteOffset` and
   `hexplain:byteLength` because `ExtractOptions.includeByteRange` defaults to true. The
   library depends on both facts.
3. **Read only.** Nothing here writes bytes. The Metawriter path is untouched.
4. **Phase 1 executes what the engine executes.** A function over a chunked, bit-packed or
   stride-from-field layout fails cleanly until the descriptor-driven raster work lands; the
   function contract does not change when it does.

## Approaches considered

**A. Materialise cells as triples on demand.** A CONSTRUCT service lifts a requested window
into cell resources and the query runs over them. Rejected: it rebuilds the graph for every
window, the per-cell triple cost is exactly what made materialisation impractical, and it
invents a cell vocabulary the aspects deliberately do not have.

**B. Per-format functions.** `tiff:pixel`, `png:pixel`, `shp:geometry`. Rejected: this is the
`RasterDecoder.kt` when-on-magic-bytes problem restated in SPARQL. Each new format adds
functions, and none of the work transfers.

**C. A layered library keyed on the description vocabularies (recommended).** Functions are
organised by the layer of the description they bind to: the byte range of a lifted node, the
parsed value of a node, the cells of a `dlv:DataLayout`, and finally the coordinates an aspect
defines (raster x/y/band, spatialref world coordinates, signal time, geometry). Each layer is
usable alone and each higher layer is a thin composition of the one below. A profile that lifts
its sample grid through DLV and `araster:` gets pixel access for free, whatever its bytes look
like.

C is recommended because it is the only approach in which adding a format costs nothing at
the query layer, which is the thesis of the project applied to querying.

## Design

### 1. Two kinds of function

The library contains **pure** and **native** functions, and the distinction is part of the
specification.

- **Pure functions** compute over values that are already in the graph: an affine
  georeference applied to a column and row, a calibration scale applied to a raw sample, a
  no-data comparison. They are published as SHACL-AF `sh:SPARQLFunction` definitions in
  `specification/fn/fn.ttl`, so any SHACL-AF engine (Jena, TopBraid) can run them without
  Hexplain code. The Kotlin module also registers native implementations of the same IRIs for
  speed; both must agree, and a test asserts it.
- **Native functions** need bytes: they open the asset, parse, decode and address cells. They
  are implemented in Kotlin against the engine and declared in the same `fn.ttl` with their
  signature, argument types, return type and failure conditions, but without a SPARQL body.

Every function lives in one namespace, `https://hexplain.io/ns/fn#`, prefix `hxf:`. The aspect
ontologies stay purely descriptive; functions are not OWL and do not belong in them. A
function's documentation names the aspect terms it reads (for example `hxf:sampleAt` reads
`araster:hasBand`, `araster:bandIndex`, `dlv:hasAxis`).

### 2. Argument and result conventions

- **Nodes are lifted instance IRIs.** A function that touches bytes takes the IRI of a lifted
  resource (`<baseUri>#root/Chunks/3/ChunkData`), never a file path. The query never learns
  where the bytes live.
- **Indices are zero-based** and given in the layout's declared dimension order for the array
  layer. The raster layer uses logical `x` (column) and `y` (row) and identifies a band either
  by its `araster:RasterBand` IRI or by its one-based `araster:bandIndex`, matching the aspect
  and GDAL. The two conventions are documented side by side rather than harmonised, because
  each matches the vocabulary it serves.
- **Results are typed by the cell type.** Integer cells return `xsd:integer`, float cells
  `xsd:double`, string cells `xsd:string`, byte cells `xsd:hexBinary`. Geometry returns
  `geo:wktLiteral` so GeoSPARQL's `geof:` functions apply directly.
- **Failure is unbound, never a query error.** Out-of-range index, unresolvable asset, layout
  the engine cannot execute, or an oversize request all raise ARQ's `ExprEvalException`, which
  leaves the variable unbound or makes the FILTER false. The reason is logged with the function
  IRI and the node, and is exposed through `hxf:explain` (section 3.5) for debugging.
- **Limits are enforced, not advisory.** Bytes returned by a single call, cells visited by a
  window, and parse work all have runtime caps (section 4.4).

### 3. The function catalogue

#### 3.1 Layer 0: assets and bytes

| Function | Signature | Returns |
|---|---|---|
| `hxf:bytes` | `(node)` | `xsd:hexBinary` of the node's recorded byte range |
| `hxf:bytes` | `(node, offset, length)` | slice relative to the node's range, bounds-checked |
| `hxf:decodedBytes` | `(node)` | bytes after inverting the node's `hexplain:isEncodedWith` or `hexplain:hasEncodingStep` chain through the codec registry |
| `hxf:digest` | `(node, algorithmIri)` | hex digest of the node's raw bytes; algorithm from the `checksum` register, so it pairs with `aintegrity:checksum` |

These work for any node of any format because they use only `hexplain:byteOffset`,
`hexplain:byteLength` and the encoding properties, all from core. `hxf:digest` gives the
integrity aspect a query-time verification without a format-specific line of code.

#### 3.2 Layer 1: parsed values

| Function | Signature | Returns |
|---|---|---|
| `hxf:value` | `(node)` | the node's parsed scalar value, typed as the lifter would type it |
| `hxf:hel` | `(node, expression)` | a HEL expression evaluated with the node as `instance` |
| `hxf:decode` | `(hexBinary, dataTypeIri)` | a scalar decoded from bytes by a `bddo:DataType` from the profile |

`hxf:value` matters more than it looks. The lifter only emits triples for fields with a
semantic mapping. Every other field is reachable in the parse tree and now in a query, so a
profile author can inspect a header field without first mapping it, and an analyst can read
a vendor tag nobody modelled. `hxf:hel` reuses the expression language the descriptors are
written in, so `hxf:hel(?ifd, "Entries[3].Count * 2")` needs no new syntax.

#### 3.3 Layer 2: arrays (DLV)

Applies to any node whose field carries a `dlv:DataLayout`: raster grids, netCDF and Zarr
variables, PCM audio, point records, lookup tables.

| Function | Signature | Returns |
|---|---|---|
| `hxf:rank` | `(array)` | number of dimensions |
| `hxf:extent` | `(array, dim)` | size of dimension `dim`, given as a zero-based position or a `dlv:Axis` IRI |
| `hxf:cell` | `(array, i1, ..., in)` | the cell at those indices |
| `hxf:stat` | `(array, kind)` | `"min"`, `"max"`, `"sum"`, `"mean"`, `"count"` over the whole array |
| `hxf:stat` | `(array, kind, lo1, hi1, ..., lon, hin)` | the same over a half-open window |

Property function, for enumeration:

```
(?array ?lo1 ?hi1 ... ?lon ?hin) hxf:window (?i1 ... ?in ?v)
```

The subject list carries the array and one half-open range per dimension; the object list
binds one index per dimension and the value. A window is refused above the cell cap. There is
deliberately no unbounded "all cells" form.

`hxf:extent` accepting a `dlv:Axis` is the hinge for layer 3: `hxf:extent(?a, dlv:axisBand)`
answers "how many bands" without knowing where the band dimension sits.

#### 3.4 Layer 3: aspect coordinates

Each function here is a small composition of layers 0 to 2 with an aspect's vocabulary. This
is where format independence pays out: a function reads aspect triples, finds the physical
array through the graph, and maps aspect coordinates onto `dlv:Axis` positions.

**Raster (`araster:`)**

| Function | Signature | Kind | Returns |
|---|---|---|---|
| `hxf:sampleAt` | `(grid, x, y, band?)` | native | raw sample; `band` is a `RasterBand` IRI or one-based index, optional for single-band grids |
| `hxf:calibrate` | `(band, raw)` | pure | `raw * araster:sampleScale + araster:sampleOffset`, identity when neither is asserted |
| `hxf:isNoData` | `(band, value)` | pure | true when `value` equals `araster:noDataValue` on the band or its grid |
| `hxf:physicalAt` | `(grid, x, y, band?)` | native | calibrated sample; unbound when the raw sample is no-data |

Resolution rule for `hxf:sampleAt`: find the sample array by `?grid araster:hasArray ?a` or,
failing that, `?band araster:hasArray ?a`; map `x` to the dimension with `dlv:axisX`, `y` to
`dlv:axisY`, and the band to `dlv:axisBand` when the array has one (interleaved layouts) or to
the band's own array when it does not (planar layouts). Any other dimension must have extent
one or the call is unbound with an explanation.

**Spatial reference (`asref:`)**

| Function | Signature | Kind | Returns |
|---|---|---|---|
| `hxf:worldX`, `hxf:worldY` | `(transform, col, row)` | pure | world coordinate from an affine `asref:GeoTransform`, honouring `asref:pixelRegistration` |
| `hxf:column`, `hxf:row` | `(transform, wx, wy)` | pure | inverse affine, truncated to the containing cell |
| `hxf:sampleAtWorld` | `(dataset, wx, wy, band?)` | native | `hxf:sampleAt` at the cell containing a world point, via the dataset's `asref:hasGeoTransform` |

Rational polynomial transforms (`asref:CubicRationalTransform`) are out of phase 1: the forward
form is pure and cheap, the inverse needs iteration, and neither has a consumer yet.

**Geometry (`ageom:`)**

| Function | Signature | Kind | Returns |
|---|---|---|---|
| `hxf:wkt` | `(node)` | native | `geo:wktLiteral` built from a geometry-typed field, with the CRS from the enclosing dataset's `asref:hasCRS` when present |

One function covers shapefile records, GeoPackage blobs, well-known-binary columns and any
future vector profile, because it reads the parsed coordinate lists the metaparser already
produces (the `HelGeometry` helpers validate them today). Everything else, distance, contains,
buffer, is GeoSPARQL's job.

**Signal (`asignal:`)**

| Function | Signature | Kind | Returns |
|---|---|---|---|
| `hxf:sampleAtTime` | `(signal, seconds, channel?)` | native | the cell at `round(seconds * asignal:sampleRate)` along `dlv:axisTime`, channel along `dlv:axisBand` |

Video frames are not in phase 1. A frame is a decoded picture, not a cell, and the video
codecs sit behind encoded containers.

#### 3.5 Diagnostics

| Function | Signature | Returns |
|---|---|---|
| `hxf:explain` | `(node)` | a string describing how the runtime resolved the node: asset, profile, path, layout, executable or not, and why a previous call on it failed |
| `hxf:layout` | `(array)` | a compact string of the resolved layout: dimension axes, extents, strides, cell type |

Both exist so that "unbound" is never a dead end.

### 4. Runtime

All functions are thin. The work is in one shared service, `HexplainQueryRuntime`, held by the
registered functions and configured once per JVM or per Fuseki dataset.

#### 4.1 Node resolution

Given a node IRI:

1. Split at `#`: the prefix is the asset IRI, the fragment is the lifter path
   (`root/Chunks/3/ChunkData`).
2. Find the asset's profile: `<asset> dcterms:conformsTo ?profile` in the query's active
   graph, else the runtime's default profile for that asset, else fail.
3. Load `FormatIR` for the profile through `ProfileLoader` and `RdfToIrCompiler`; cache by
   profile IRI.
4. Fetch bytes through the `AssetResolver` (section 4.2); cache by asset IRI.
5. Parse with `Metaparser` under the runtime's `ParseLimits`; cache the tree by
   (asset, profile).
6. Walk the fragment path to the node and its `FieldIR`. The lifter's path scheme is
   invertible by construction (names and zero-based list indices, slash separated).

Layer 0 functions skip steps 3, 5 and 6 when the graph carries `hexplain:byteOffset` and
`hexplain:byteLength` for the node, which it does by default. This is the cheap path and it is
why byte ranges are emitted at all.

#### 4.2 Asset resolution

`interface AssetResolver { fun open(assetIri: String): ByteSource? }`, with a
`ByteSource` that supports random access reads and length. Provided implementations:

- **File system**, mapping `file:` IRIs, gated by an allow-list of roots.
- **Explicit registry**, mapping any IRI to a path or in-memory bytes; the default for tests
  and CLI use.
- **HTTP(S)** with range requests, opt-in.

The SaaS deployment supplies its own resolver over its object store. The runtime never
touches a path a resolver did not hand it.

#### 4.3 Array resolution

For `hxf:cell` and everything above it: from the node's `FieldIR.hasDataLayout`, resolve
dimension sizes, strides and cell type against the parsed instance exactly as the parser
does, take the node's decoded bytes (layer 0), and build `MultiDimensionalData`. The accessor's
`requireExecutable` check is the contract boundary: layouts it refuses today (chunked,
bit-packed, stride-from-field) make the function unbound with the accessor's message in
`hxf:explain`. When the descriptor-driven raster work extends the accessor, the functions gain
those layouts without change.

Cell access is by index arithmetic on the decoded array, never by re-parsing per cell. The
decoded array is cached alongside the parse tree with the same eviction.

#### 4.4 Limits and safety

- `maxBytesPerCall` (default 1 MiB) for `hxf:bytes` and `hxf:decodedBytes`.
- `maxCellsPerWindow` (default 1,000,000) for `hxf:window` and windowed `hxf:stat`.
- `ParseLimits` as configured for the runtime; the metaparser's existing guards apply.
- Cache with a byte budget and least-recently-used eviction; a single asset larger than the
  budget is parsed and discarded per query.
- Resolver allow-lists; no `file:` access unless a root is configured.

#### 4.5 Registration and packaging

New Gradle module `hexplain-tools/query`, package `io.hexplain.query`, depending on `core`:

- `HexplainQueryRuntime(resolver, limits, cache)`.
- `HexplainFunctions.register(runtime)` populates ARQ's global registries; an overload takes
  explicit registries for embedding.
- `HexplainFusekiModule` implementing Fuseki's module SPI, configured from an assembler
  description, for the SaaS endpoint.
- A `hxq` CLI subcommand that loads an instance graph, registers the functions against a
  registry resolver and runs a query file, for fixtures and demos.

### 5. Specification artefacts

- `specification/fn/fn.ttl`: one resource per function with `rdfs:label`, `rdfs:comment`,
  a `hxf:signature` literal, `hxf:kind` (`hxf:Pure` or `hxf:Native`), the aspect terms it
  reads, and for pure functions the `sh:SPARQLFunction` body with `sh:parameter` and
  `sh:returnType`.
- `specification/fn/index.html`: rendered catalogue in the style of the other modules, with
  one worked query per layer.
- A note in the raster aspect and the spatialref aspect pointing at the functions that consume
  them, so a reader of the ontology learns the values are reachable.

### 6. Testing

- **Pure functions agree with themselves.** For each pure function, the SHACL-AF body and the
  Kotlin implementation are run on the same inputs and must produce equal results.
- **Synthetic layouts.** Tiny hand-written profiles (raw u8 grid 3 x 2, i16 big-endian 2 x 2
  x 2 interleaved, float32 little-endian planar, PCM s16 stereo) with known bytes; every layer
  0 to 3 function is asserted on them, including every failure mode (out of range, oversize,
  non-executable layout, unresolvable asset).
- **GDAL parity, reused.** The 611 pixel-parity fixtures already compare the Kotlin raster path
  to GDAL. A new test picks a sample of coordinates per fixture, evaluates `hxf:sampleAt` and
  `hxf:sampleAtWorld` through ARQ, and compares to the GDAL value. This proves the query layer
  against the same oracle as the decoder, and it is the demonstration query for the paper.
- **Geometry.** `hxf:wkt` on the shapefile and GeoPackage fixtures, compared with GDAL's WKT
  after normalisation, then piped through `geof:sfContains` to prove interoperability.
- **Limits.** A window over the cap and a byte request over the cap are unbound and explained.

### 7. Worked queries

Pixel at a coordinate, calibrated, for any raster format:

```sparql
PREFIX hxf: <https://hexplain.io/ns/fn#>
PREFIX araster: <https://hexplain.io/ns/aspect/raster#>
SELECT ?grid ?value WHERE {
  ?grid a araster:RasterGrid ; araster:hasBand ?band .
  ?band araster:bandIndex 1 .
  BIND(hxf:physicalAt(?grid, 412, 97, ?band) AS ?value)
}
```

Value under a world point across a folder of mixed NITF, GeoTIFF and raw grids:

```sparql
SELECT ?dataset ?v WHERE {
  ?dataset a geo:RasterDataset .
  BIND(hxf:sampleAtWorld(?dataset, -122.41, 37.77, 1) AS ?v)
  FILTER(bound(?v))
}
```

Mean of a window on a netCDF variable, by axis rather than by position:

```sparql
SELECT (hxf:stat(?a, "mean", 0, 1, 100, 200, 100, 200) AS ?m) WHERE {
  ?grid araster:hasArray ?a .
  FILTER(hxf:extent(?a, dlv:axisTime) > 0)
}
```

Read an unmapped header field:

```sparql
SELECT ?tag ?count WHERE {
  ?entry a tiff:IfdEntry .
  BIND(hxf:hel(?entry, "Tag") AS ?tag)
  BIND(hxf:value(?entry) AS ?count)
}
```

## Phase 1 deviations

- `hxf:wkt` reads WKB and GeoPackage payloads through the core `GeometryDecoder`; shapefile
  shape records are not decoded in phase 1 because no record decoder exists in the engine.
- No GeoSPARQL round trip test: `jena-geosparql` is not a dependency; the test asserts the
  `geo:wktLiteral` datatype and the CRS prefix instead.
- The aspect ontologies are not edited to point at the functions; the function page and the
  specification index carry the cross-references, to keep the aspect pages' generated term
  documentation untouched.
- A layout the accessor cannot execute fails at parse time, so every function on that asset
  is unbound (not only the array ones); `hxf:explain` carries the accessor's message.
- Profiles are bound to assets explicitly (`bindAsset`, `hxq --asset/--profile`, Fuseki
  properties) or through `dcterms:conformsTo` triples; the lifter does not emit `conformsTo`
  itself.
- The GDAL parity fixture: `autotest/gcore/data/gtiff/byte_envi.bin` is byte-identical to
  `byte.tif` (a 736-byte classic TIFF whose single uncompressed strip begins at offset 8), not
  a bare 400-byte grid; the parity profile therefore declares an 8-byte header field followed
  by a 400-byte `Samples` array, and the digest matches GDAL's for the strip.
- Fuseki: `FusekiAutoModule.start()` does not fire for a module supplied through
  `FusekiModules.create(...)`, so the module registers the functions in `prepare(...)` instead.
- Layer-0 cheap path: `hxf:bytes` and `hxf:digest` read `hexplain:byteOffset`/
  `hexplain:byteLength` from the graph when present and then only need the asset's bytes (no
  profile, no parse); `hxf:decodedBytes` still needs the parse because the codec chain lives in
  the profile. `hexplain:byteOffset` and `hexplain:byteLength` were not yet declared terms in
  `specification/hexplain/core.ttl` when this library was designed; they are now (an
  `owl:DatatypeProperty` pair, range `xsd:nonNegativeInteger`, documented next to
  `hexplain:isEncodedWith`), since a `:reads` reference to an undefined term fails the
  specification's term-existence gate.
- `ByteSource` offers `readAll()` only (no random-access reads, no HTTP range resolver); an
  asset larger than `cacheBudgetBytes / 3` (about 85 MB at the default) is never cached and is
  re-read and re-parsed on every function call, and assets above 2 GiB cannot be read at all.
  Phase 1 ceiling; per-query memoisation is deferred.
- The SHACL-AF bodies are proven equal to the native functions by formula agreement, not by
  executing them in a SHACL-AF engine: `jena-shacl` 5.5.0 has no `sh:SPARQLFunction` executor,
  so the portability claim stands on the agreement test until a run in TopBraid or another
  SHACL-AF engine.
- Array precedence: `hxf:sampleAt` prefers the named band's `araster:hasArray` over the grid's
  (the design text in section 3.4 listed the grid first); the band-specific array is the more
  specific description.
- `hxf:isNoData` compares numerically, so a NaN no-data value never matches; and
  `hxf:sampleAtTime` finds a signal's samples through `araster:hasArray` because the signal
  aspect has no array-linking term of its own.
- `hexplain:byteOffset` and `hexplain:byteLength` are declared in `core.ttl` for the first
  time in this change (the lifter has emitted them since the semantic-graph extraction
  design); a 1.x vocabulary addition to mention in migration notes.

## Out of scope for phase 1

- Writing through functions.
- Rational polynomial inverse transforms.
- Video frame access.
- Cross-asset aggregates (mosaics); each call addresses one asset.
- A federated `SERVICE` form for remote engines; the Fuseki module covers remote access.

## Open questions for review

1. Is `hxf:` as a single function namespace right, or do you want the aspect-level
   functions under the aspect namespaces they serve?
2. One-based bands next to zero-based x, y: keep as the aspect dictates, or make everything
   zero-based and document the offset from `araster:bandIndex`?
3. Should `hxf:value` and `hxf:hel` be exposed in the SaaS endpoint, given they reach fields
   the profile did not choose to publish?
