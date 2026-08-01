# Hexplain Specification Improvements — Derived from the GDAL Coverage Survey

**Date:** 2026-08-01 · **Status:** Recommendations for review
**Input:** [GDAL format coverage in HDL](2026-08-01-gdal-hdl-coverage.md) — 245 driver entries classified.

Twelve proposals, ranked by formats unlocked per unit of specification change. Each records
the **evidence** (what the current vocabulary actually says), the **proposal**, and the
**payoff** against the survey's tiers.

Baseline: 65 ✅ Full · 48 ◐ Container · 43 ◑ Payload-only · 89 ✗ Out of scope.

---

## Summary

| # | Proposal | Module | Cost | Payoff |
|---|---|---|---|---|
| **P0-1** | Delimited-record primitive (line/`key = value`/CSV) | BDDO + HEL | M | **~35 ◑→✅, ~10 ✗→✅** |
| **P0-2** | Tiled / chunked data layout | DLV | M | Correctness for ~40 drivers; **blocks NITF conformance today** |
| **P0-3** | ASCII-numeric datatype | BDDO | **S** | Unblocks 10 already-listed ✅; **blocks NITF conformance today** |
| **P0-4** | Data-dependent endianness | BDDO | **S** | **The shipped TIFF profile is knowingly wrong without it** |
| **P1-5** | Encoding pipelines with parameters | core | S | HDF5/Zarr/TIFF-predictor/Blosc/Parquet |
| **P1-6** | Varint / zigzag datatypes | BDDO | **S** | MVT, PMTiles, OSM PBF, Parquet, OpenFileGDB |
| **P1-7** | Bundle path patterns & cardinality | hx-bundle | S | AIG, GRASS, SAFE, SENTINEL2, Zarr, ESRIC, ADRG |
| **P1-8** | Sub-byte cell packing in layouts | DLV | S | GRIB2, NITF 1/12-bit, 1-bit masks, 4-bit palettes |
| **P1-9** | `dimensionStride` from field/expression | DLV | **XS** | BMP padding, ENVI/EHdr line offsets — closes an asymmetry |
| **P2-10** | hx-raster: add classes and band model | aspect | M | `mapsToClass` has **no raster target at all** today |
| **P2-11** | hx-spatialref: full affine, GCPs, RPCs | aspect | M | Faithful georeferencing for most geospatial drivers |
| **P2-12** | Open the checksum register (SKOS) | BDDO | **XS** | DTED/CCITT sums; profile extensibility |

Cost: XS ≈ a few triples · S ≈ one property group + shapes · M ≈ a new class group + HDL surface.

---

## P0 — Blocking or highest-yield

### P0-1 · A delimited-record primitive

**Evidence.** BDDO addresses bytes by offset and size only. Every sizing mechanism —
`size`, `sizeFromField`, `sizeFromExpression`, `sizeToEndOfStream`, `terminator`
([bddo.ttl:59-63](../../../specification/bddo/bddo.ttl#L59-L63)) — yields a byte extent.
There is no way to say "split this run of bytes on a delimiter and name the parts". That
single absence is what puts all 43 ◑ formats in tier 3 and most of the 40 ✗(d) formats out
of scope.

The ◑ formats are otherwise the *easiest* cases in GDAL: a raw grid (a trivial DLV block)
plus a header like

```
samples = 5000
lines   = 3000
bands   = 7
byte order = 0
```

**Proposal.** Add a bounded, two-level splitting primitive to BDDO — explicitly *not* a
general grammar:

- `bddo:DelimitedRecords` on a field: `recordDelimiter` (default `0x0A`), optional
  `fieldDelimiter`, `quoteChar`, `escapeChar`, `commentPrefix`, `skipRecords`.
- `bddo:KeyValueHeader` as the named special case: `keyValueSeparator`, plus
  `bddo:hasEntry [ bddo:key "samples" ; hexplain:mapsToProperty araster:width ]`.
- HEL gains the minimum needed to consume it: `trim`, `substringBefore`, `substringAfter`,
  `number()`.

HDL surface:

```
header EnviHeader @line-oriented @separator "=" @comment ";" {
  "samples"    : int means araster:width
  "lines"      : int means araster:height
  "bands"      : int means araster:bandCount
  "byte order" : int as byteOrder
}
```

**Deliberately excluded:** recursive grammars (XML, JSON). Those stay ✗ — see
[Non-goals](#non-goals).

**Payoff.** ~35 of 43 ◑ → ✅ (ENVI, EHdr, GenBin, PAux, MFF/MFF2, ERS, ILWIS, ISCE,
ROI_PAC, RRASTER, RST, SAGA, SNODAS, NDF, PDS/ISIS PVL labels, VICAR, DOQ1/2, PNM …), **plus**
~10 currently ✗(d) → ✅ (AAIGrid, GSAG, XYZ, ZMAP, GRASSASCIIGrid, GMT, WAsP, CSV, MAP).
**The single largest coverage change available.**

---

### P0-2 · Tiled / chunked data layout

**Evidence.** `dlv:DataLayout` describes exactly one contiguous strided N-d block:
`hasDimension` (an ordered list), `cellDataType`, `dimensionSize`, `dimensionStride`
([dlv.ttl:23-41](../../../specification/dlv/dlv.ttl#L23-L41)). There is no chunk extent, and
no way to point at a table of per-chunk offsets.

Tiling is the norm, not an edge case: tiled TIFF and **every COG**, NITF blocked images
(`NBPR`/`NBPC`/`NPPBH`/`NPPBV`), HDF5 and Zarr chunks, GPKG/MBTiles/ESRIC/MRF tile pyramids,
JPEG 2000 tiles, GRIB grids.

> **This is on the NITF certification critical path.** A blocked NITF image cannot be
> described at all today — only single-block images can.

**Proposal.** Reuse `dlv:Dimension`; add per-axis chunk extent and layout-level indirection:

- On `Dimension`: `dlv:chunkSize`, `dlv:chunkSizeFromField`.
- On `DataLayout`: `dlv:chunkOffsetsFromField` → `bddo:Field` (the array holding per-chunk
  byte offsets — TIFF `TileOffsets`), `dlv:chunkLengthsFromField` (TIFF `TileByteCounts`),
  `dlv:chunkOrder` → a small register (`rowMajor`, `columnMajor`, `morton`, `hilbert`).

HDL surface:

```
pixels : bytes[..] layout cell u8 {
  dim axis Y size imageHeight chunk tileLength
  dim axis X size imageWidth  chunk tileWidth
  chunks offsets TileOffsets lengths TileByteCounts order row-major
}
```

**Payoff.** Turns partial descriptions into complete ones for ~40 drivers, and is required
for COG and blocked NITF to be describable at all.

---

### P0-3 · An ASCII-numeric datatype

**Evidence.** BDDO's primitives are fixed-width binary plus `bddo:string`
([bddo.ttl:126-153](../../../specification/bddo/bddo.ttl#L126-L153)). HEL's coercion rules
make arithmetic on a non-numeric operand an error
([hel/index.html:165](../../../specification/hel/index.html#L165)), and its function set is
`sizeof`/`len`/`count`/`eof` only. The NITF design works around this at the *semantic* layer
— declare BCS-N as a string, coerce with `hexplain:valueExpression`
([nitf-profile-design.md:70-79](../specs/2026-07-26-nitf-profile-design.md#L70-L79)) — which
produces the mapped value but **not a sizing input**.

> **Also on the NITF critical path.** NITF's `LISH`/`LI` segment lengths are ASCII, and they
> determine where every subsequent segment starts. Segment offsets cannot be expressed today.

**Proposal.** Add datatypes that reuse the existing `bddo:size` for width:

```turtle
:asciiInteger a :DataType ; :baseType :baseInteger ; :encoding :ascii ; :xsdType xsd:integer .
:asciiDecimal a :DataType ; :baseType :baseFloat   ; :encoding :ascii ; :xsdType xsd:decimal .
```

A field is then `NROWS : asciiInteger[8]`, its HEL value is an Integer, and it can drive
`sizeFromExpression` / `atOffsetFromExpression` / `repeatCountFromExpression` directly.
Optional `bddo:numericBase` covers hex-in-ASCII and octal.

**Payoff.** Unblocks 10 formats already listed ✅ but not in fact authorable end-to-end:
NITF, FITS (`NAXISn` drive the array extent), USGSDEM, DTED, S-57, ESAT, FAST, CTG, TIGER,
UK .NTF, PCIDSK. Cost is roughly ten triples.

---

### P0-4 · Data-dependent endianness

**Evidence.** `bddo:endianness` ranges over two individuals
([bddo.ttl:51-52](../../../specification/bddo/bddo.ttl#L51-L52)); there is no
`endiannessFromField`. A file that *declares* its own byte order cannot be described.

The shipped TIFF profile documents the problem in its own comment and then hardcodes the
answer:

> *"Two-byte identifier: 4949h (II) = little-endian; 4D4Dh (MM) = big-endian. All multi-byte
> values in the file after this field use this byte order."*
> — [tiff-profile.ttl:40](../../../../hexplain-tools/core/src/main/resources/tiff-profile.ttl#L40)

…while every struct in the same file carries `bddo:endianness bddo:LittleEndian`
(lines 31, 65, 98). **The flagship profile is knowingly incorrect for big-endian TIFF.**

**Proposal.** `bddo:endiannessFromExpression` (range `xsd:string`, a HEL expression yielding
`"big"`/`"little"`), applicable at Struct and Field scope and inherited by descendants —
matching how static `endianness` already inherits.

```
struct TIFFHeader @endian-from `root.IFH.ByteOrder == 0x4D4D ? "big" : "little"` { … }
```

(A conditional operator would be needed in HEL, or express it as two `switch` arms over
struct variants — the latter needs no HEL change at all and is the cheaper first cut.)

**Payoff.** Correctness for TIFF/GeoTIFF/COG/BigTIFF/LIBERTIFF/SNAP_TIFF (6 drivers, the
most important format in the survey), plus netCDF, HDF4/5, ADRG, MFF, ENVI, ERS, and every
other format with a byte-order flag.

---

## P1 — High yield, contained scope

### P1-5 · Encoding pipelines with parameters

**Evidence.** `hexplain:isEncodedWith` takes a single `skos:Concept` and is capped at
`sh:maxCount 1` ([core.ttl:71](../../../specification/hexplain/core.ttl#L71)). Its comment
already specifies decode-then-reparse semantics, which is exactly right — but one codec, no
parameters.

Real formats chain and parameterise: TIFF horizontal predictor → Deflate; HDF5 filter
pipelines (shuffle → deflate); Zarr codec chains (delta → Blosc(zstd, shuffle, clevel));
Parquet page encodings (RLE/dictionary → Snappy).

**Proposal.** Add `hexplain:hasEncodingStep` → an ordered `rdf:List` of
`hexplain:EncodingStep [ hexplain:codec <concept> ; hexplain:codecParameter [ … ] ]`, applied
in order. Keep `isEncodedWith` as the single-step shorthand. The codec registers are already
open SKOS ([encoding.ttl:30-69](../../../specification/aspect/encoding/encoding.ttl#L30-L69)),
so no register change is needed.

---

### P1-6 · Varint / zigzag datatypes

**Evidence.** No variable-length integer type exists. Varints are describable structurally
(`repeat until (b & 0x80) == 0`) but HEL has no accumulator to reconstruct the value, so the
escape hatch is the only route.

**Proposal.** `bddo:varuint` (LEB128), `bddo:varint` (zigzag), with
`bddo:varintEncoding` selecting the flavour (LEB128, SQLite, Protobuf-group). Small, purely
additive.

**Payoff.** MVT, OSM PBF, PMTiles, Parquet, OpenFileGDB geometry, FlatGeobuf — 6 drivers
move materially toward ✅, and protobuf-framed formats generally become authorable.

---

### P1-7 · Bundle path patterns and cardinality

**Evidence.** `abnd:PartSpec` identifies a member **only by filename extension**
([bundle.ttl:66-67](../../../specification/aspect/bundle/bundle.ttl#L66-L67)). There is no
path pattern, no directory nesting, and no cardinality — a PartSpec is implicitly "zero or
one".

Directory-structured formats therefore cannot be profiled: AIG (`info/`, `w001001x.adf`),
GRASS mapsets, SAFE (`measurement/*.tiff`, `annotation/*.xml`), SENTINEL2, Zarr (nested
chunk keys), ESRIC (`_alllayers/Lxx/RxxxxCxxxx.bundle`), ADRG, RPFTOC.

**Proposal.** On `PartSpec`: `abnd:pathPattern` (glob, relative to the asset root),
`abnd:minCount` / `abnd:maxCount` (so `measurement/*.tiff` can be "one or more"), and
`abnd:nestedProfile` → `BundleProfile` for subdirectory structure. `abnd:extension` becomes
sugar for `pathPattern "*<ext>"`.

**Payoff.** ~10 directory formats become profileable; also unlocks a reusable ZIP/container
profile that composes with the existing `apkg:Container` / `apkg:Entry`
([packaging.ttl:22-30](../../../specification/aspect/packaging/packaging.ttl#L22-L30)) — which
in turn gives container-level description of KMZ, XLSX, ODS, GTFS, SAFE.

---

### P1-8 · Sub-byte cell packing in layouts

**Evidence.** `dlv:cellDataType` ranges over `bddo:DataType`, and `dimensionStride` is
documented as *"Bytes to advance per step"*
([dlv.ttl:33-34](../../../specification/dlv/dlv.ttl#L33-L34)). `bddo:bitWidth` exists on
DataType, so a 12-bit type can be *minted* — but a grid of them cannot be *addressed*,
because striding is byte-granular.

**Proposal.** `dlv:cellBitWidth` and `dlv:strideUnit` (`bits` | `bytes`), plus
`dlv:bitPackingOrder` reusing `bddo:BitOrder`.

**Payoff.** GRIB2 packed data sections, NITF 1-bit and 12-bit imagery, 1-bit masks, 4-bit
palettes (BMP/GIF), packed DEMs.

---

### P1-9 · `dimensionStride` from a field or expression

**Evidence.** A plain asymmetry: `dimensionSizeFromField` exists
([dlv.ttl:32](../../../specification/dlv/dlv.ttl#L32)) but `dimensionStride` is
`xsd:positiveInteger` — a literal only ([dlv.ttl:33](../../../specification/dlv/dlv.ttl#L33)).

Its own comment cites BMP 4-byte row padding as the motivating case — but BMP's row stride is
`((width * bpp + 31) / 32) * 4`, computed from a *field*, which the property cannot express.
The documented example does not work.

**Proposal.** Add `dlv:dimensionStrideFromField` and `dlv:dimensionStrideFromExpression`,
mirroring the size properties and the §6.3 field-form/expression-form rule already in HDL.

**Cost:** two properties and two SHACL clauses. **The cheapest item on this list.**

---

## P2 — Semantic layer (makes complete descriptions *useful*)

### P2-10 · hx-raster has no classes and no band model

**Evidence.** [raster.ttl](../../../specification/aspect/raster/raster.ttl) defines exactly
three properties — `width`, `height`, `noDataValue` — and **no `owl:Class` at all**.
Consequently `hexplain:mapsToClass` has no raster target to point at, while the HDL design's
own worked example writes `struct IHDR_ChunkData means araster:RasterImage`
([hdl-format-dsl-design.md:218](../specs/2026-07-26-hdl-format-dsl-design.md#L218)) —
referencing a class that does not exist.

**Proposal.** Add `araster:RasterGrid` and `araster:RasterBand`, plus the band model GDAL's
own data model needs: `bandCount`, `hasBand`/`bandIndex`, `sampleDataType`, `scale`/`offset`,
`colorInterpretation` (a SKOS register), `hasOverview`/`resolutionLevel`, `blockWidth`/
`blockHeight`, `categoryNames`. Fix the design doc's example either way.

---

### P2-11 · hx-spatialref cannot express a full georeference

**Evidence.** [spatialref.ttl:25-34](../../../specification/aspect/spatialref/spatialref.ttl#L25-L34)
offers `wktString`, `epsgCode`, `originLongitude`/`originLatitude`, `scaleX`/`scaleY`,
`pixelRegistration`. A `GeoTransform` class is declared but has no coefficient properties.

Missing: the **rotation/shear terms** (GDAL geotransform GT[2] and GT[4]) — so any rotated or
skewed raster is misdescribed; **GCPs**; **RPCs** (rational polynomial coefficients);
**vertical CRS / datum**; 3D.

RPCs and GCPs are not exotic here — they are the primary georeference for NITF, RS2, TSX,
RCM, DIMAP, SENTINEL2 and most of the SAR and satellite drivers in the survey.

**Proposal.** Give `GeoTransform` its six coefficients (or an ordered `rdf:List`); add
`asref:GroundControlPoint` (pixel/line/X/Y/Z/id), `asref:RPCModel` (the 20-coefficient
numerator/denominator sets plus scale/offset terms), and `asref:verticalCRS`.

---

### P2-12 · Open the checksum register

**Evidence.** `bddo:ChecksumAlgorithm` is an `owl:Class` with six hardcoded individuals —
crc16, crc32, adler32, md5, sha1, sha256
([bddo.ttl:118-123](../../../specification/bddo/bddo.ttl#L118-L123)). A profile cannot add an
algorithm without editing the core vocabulary. Contrast the codec register, which is open
SKOS and explicitly documented as extensible.

Missing algorithms that formats in the survey actually use: additive and XOR byte sums
(DTED's per-record checksum), Fletcher, CRC-8, CRC-32C, CRC-64.

**Proposal.** Restructure as a SKOS `bddo:ChecksumAlgorithmScheme`, mirroring
`aenc:CompressionScheme`; keep the six existing IRIs as concepts so nothing breaks. Add
optional `bddo:polynomial` / `initialValue` / `reflected` / `xorOut` for CRC parameterisation.

---

## Non-goals {#non-goals}

Worth stating explicitly so the boundary is principled rather than accidental:

1. **Recursive text grammars (XML, JSON, DXF group codes).** A production-rule parser does
   not belong in a byte-structure vocabulary, and the delimited-record primitive (P0-1) is
   deliberately non-recursive. Better answer: an annotation property
   (`hexplain:describedByExternalSchema` → an XSD/JSON-Schema/RelaxNG IRI) so a description can
   *reference* the grammar and still carry the aspect mapping. Keeps ~40 ✗(d) formats out of
   BDDO while letting them participate in the semantic layer.
2. **Data-driven schema** — HFA's embedded dictionary, flatbuffer vtables, Thrift metadata.
   The layout is defined by file content, not by the description. Genuinely out of scope.
3. **Codec internals.** `@encoded-with` identifies; it never describes. Correct as designed.
4. **Service and RDBMS drivers** (39 of the 89 ✗). No byte stream exists to describe.

With P0 and P1 implemented, the survey's ceiling moves from **65 ✅ / 156 expressible** to
roughly **115 ✅ / 165 expressible** — and, more importantly, the two formats the project has
already committed to certifying (NITF, GeoTIFF) become describable *correctly*, which today
they are not.

---

## Suggested order

1. **P0-3** (ASCII-numeric) and **P1-9** (stride from field) — hours, not days; both unblock
   things already claimed to work.
2. **P0-4** (endianness) — pick the `switch`-over-struct-variants formulation first; it needs
   no HEL change and fixes the TIFF profile immediately.
3. **P0-2** (tiling) — required for NITF blocked imagery and COG.
4. **P1-5**, **P1-6**, **P1-8**, **P2-12** — small additive vocabulary changes, batchable.
5. **P0-1** (delimited records) — the largest coverage win, and the one needing a new HDL
   surface plus HEL string functions. Worth a design doc of its own.
6. **P1-7** (bundle paths), then **P2-10**/**P2-11** — the semantic layer, once the physical
   layer is settled.
