# GDAL profile wave 1: raw grids and binary vector records

**Date:** 2026-09-09
**Status:** implemented. A follow-up wave then closed the four engine gaps this design worked
around; see "Engine gaps closed after implementation" at the end.
**Repos touched:** `hexplain-profiles` (the profiles), `hexplain-tools` (parity fixtures and tests), `hexplain.io` (coverage inventory link)

## Why

The GDAL coverage page inventories 246 GDAL documentation pages and the profile library covers
about ten of them. The formats already profiled (GeoTIFF, PNG, NITF, ENVI, EHdr, SRTM HGT, the
ISO BMFF family, the GeoPackage blob envelope) were chosen to exercise *mechanisms*. This wave
chooses formats to widen the *mapping* from GDAL drivers to descriptions, using only mechanisms
the specification and compiler already have, and it uses the locally cached GDAL 3.13.3
autotest corpus so that four of the ten ship as `parse-verified` rather than as assertions.

The selection rule, applied to every GDAL raster and vector page: an open specification; a
byte-addressed, delimited-text or sibling-bundle shape that HDL expresses today; and, where
possible, a sample in the cached corpus with a GDAL-recorded pixel digest.

## Scope

| Profile | GDAL driver key | Shape | Corpus samples | Ships as |
|---|---|---|---|---|
| `bmp` | `raster:bmp` | 14-byte file header, 40/108/124-byte info header, palette, padded bottom-up rows | 5 in `gcore/data` (4 GDAL-decoded) | parse-verified |
| `dted` | `raster:dted` | UHL/DSI/ACC fixed ASCII headers, then one record per longitude column | 7 in `gdrivers/data/dted` (1 GDAL-decoded intact) | parse-verified |
| `lan` | `raster:lan` | 128-byte Erdas 7.x header, BIL grid | 2 | not parse-verified |
| `gtx` | `raster:gtx` | 40-byte big-endian header, float32 grid | 1 | not parse-verified |
| `bt` | `raster:bt` | 256-byte header, column-major grid | 0 | not parse-verified |
| `lcp` | `raster:lcp` | 7316-byte FARSITE header, int16 BIL, 5/8/10 bands | 2 | not parse-verified |
| `idrisi` | `raster:idrisi` | `.rdc` key : value sidecar + `.rst` raw grid (ENVI template) | 2 pairs | not parse-verified |
| `saga` | `raster:sdat` | `.sgrd` key = value sidecar + `.sdat` raw grid (ENVI template) | 1 pair | not parse-verified |
| `dbf` | `vector:shapefile`, `vector:mitab` | xBase header, 32-byte field descriptors, fixed-length records | 200+ | parse-verified |
| `wkb` | `vector:gpkg` (via `gpkgblob`) | recursive ISO well-known binary module | 136 pinned oracle cases | parse-verified |

`gpkgblob` is upgraded to `import` the `wkb` module in place of its opaque `wkb : bytes[..]`
payload, which closes limit 1 of its header.

### Out of scope, and why

- **DGN v7 and S-57 (ISO 8211)**: each is a large specification on its own; deferred to a
  second wave so this one stays reviewable.
- **FlatGeobuf, MVT**: FlatBuffers vtables and protobuf varints are not expressible in HDL.
- **DXF**: group code and value alternate on separate lines; the delimited-table container
  cannot pair two records into one row.
- **PNM**: a whitespace-token text header and binary samples in one file; HDL's text
  containers and byte structs do not share a stream.
- **BMP compressed variants** (RLE4, RLE8, BITFIELDS, 12-byte CORE header), **dBASE 7**
  48-byte descriptors, **EWKB** flag bits and **curve/surface WKB types** are stated limits of
  the profiles that touch them, not silent omissions.
- **DBF record values**: a record's columns are sized by the descriptors it follows, which is a
  data-driven schema the coverage page already names as a gap. Records are described as
  `deletionFlag + bytes[recordLength - 1]`.

## Where each artefact lives

`hexplain-profiles/profiles/<name>/<name>.hx` for all ten, with the library's header
convention: source citation, layout sketch, verification status line, `LIMITS OF THIS
DESCRIPTION` trailer. No hand-written `.ttl` beside an `.hx`; the gate compiles it.

`hexplain-tools/hdl/src/test/resources/profiles/{bmp,dted,dbf,wkb}/<name>.hx` are byte-for-byte
copies (the library's `test_tools_fixtures` gate enforces this) with parity tests beside the
existing ISO BMFF ones in `hdl/src/test/kotlin/io/hexplain/hdl/parity/`. `gpkgblob.hx` is
copied too because the WKB test parses a GeoPackage blob through it.

`hexplain.io/specification/coverage/gdal-drivers.json` gains an optional `profiles` list per
driver; the inventory page renders it as a fifth column.

## Profile designs

Conventions shared by all ten: `format <name> @namespace "https://hexplain.io/ns/profile/<name>#"`;
`use` only the aspects actually mapped; raster grids map `araster:width`/`height`,
`asamp:componentCount`, `asamp:bitDepth` and, where the header carries it, `asref:originX`/
`originY`/`scaleX`/`scaleY` or `asref:originLongitude`/`originLatitude`; the pixel field carries
a `layout` so the sample block is an executable `dlv:DataLayout`.

### bmp

`FileHeader` (14 bytes, little-endian): `bfType ascii[2] @fixed "BM"`, `bfSize u32`, two
reserved `u16`, `bfOffBits u32`. `InfoHeader`: `biSize u32` then the 36 BITMAPINFOHEADER
fields; V4/V5 extensions are consumed as `bytes[biSize - 40]` so a 108- or 124-byte header
parses without being decomposed. `biHeight` is `i32`: negative means top-down. `palette :
Rgbq repeat [biClrUsed == 0 ? (biBitCount <= 8 ? (1 << biBitCount) : 0) : biClrUsed]` is
present only when `biBitCount <= 8`. `pixels : bytes[..] @at bfOffBits from stream-start if
[biCompression == 0]` with:

```
layout {
  cell switch {
    when biBitCount == 16 => u16
    when biBitCount == 32 => u32
    when biBitCount <= 8  => u8      // cell-bits from biBitCount, packing msb
    when biBitCount == 24 => u8      // Band 3, B G R order
  }
  dim axis Y size [abs(biHeight)] stride [((biWidth * biBitCount + 31) / 32) * 4]
  dim axis X size biWidth
  dim axis Band size [biBitCount == 24 ? 3 : 1]
}
```

`cell-bits from biBitCount` and `packing msb` are what make the 1-bit and 4-bit samples
addressable. DLV has no row-orientation term, so the bottom-up convention is a stated limit;
the parity test flips rows. Mapping: `araster:width`, `araster:height` (through a derived
`abs` field), `asamp:bitDepth` from `biBitCount`, `asamp:componentCount` from the band count.

### dted

MIL-PRF-89020B. Three fixed ASCII blocks, all `ascii[N]`/`anum[N]`: `UHL` (80 bytes, sentinel
`"UHL1"`, longitude and latitude of origin as `DDDMMSSH`/`DDMMSSH`, intervals in tenths of
arc-seconds, `NLON anum[4]`, `NLAT anum[4]`), `DSI` (648 bytes, sentinel `"DSI"`, the
significant fields named, the rest `bytes`), `ACC` (2700 bytes, sentinel `"ACC"`). Then
`columns : DataRecord repeat NLON` where:

```
struct DataRecord @endian big {
  sentinel   : u8 @fixed 0xAA
  blockCount : bytes[3]
  lonCount   : u16
  latCount   : u16
  elevations : bytes[NLAT * 2] layout cell u16 { dim axis Y size parent.NLAT }
  checksum   : u32
}
```

Elevations are 16-bit signed-magnitude, which no BDDO datatype names; the profile reads them
as `u16` and states the conversion in the limits. Columns run south to north and the file is
column-major; DLV orders dimensions but does not flip axes, so the record form is the primary
description and the parity test transposes and flips before hashing. Mapping: `NLON` to
`araster:width`, `NLAT` to `araster:height`, UHL origin to `asref:originLongitude`/
`originLatitude` through `derive` fields that turn `DDDMMSSH` into decimal degrees, intervals
to `asref:scaleX`/`scaleY`, `asref:epsgCode 4326` in `raw-turtle`, `araster:noDataValue -32767`.

### lan

Erdas 7.x `.lan`/`.gis`. `Header @endian little` 128 bytes: `magic ascii[6] @fixed "HEAD74"`,
`ipack i16 enum {0=>Byte, 1=>FourBit, 2=>Int16}`, `nbands i16`, `bytes[6]`, `ncols i32`,
`nrows i32`, `xstart i32`, `ystart i32`, `bytes[56]`, `maptyp i16`, `nclass i16`, `bytes[16]`,
`area f32`, `ml f32`, `mb f32`, `xcell f32`, `ycell f32`. Grid `bytes[..]` with `cell switch`
on `ipack` (u8; u8 with `cell-bits 4`; u16), order `Y Band X`. Field offsets are confirmed
against `fakelan.lan` (`AREA` at 108, `XCELL` at 120) and GDAL's `landataset.cpp` during
implementation. Mapping: width, height, componentCount, `ml`/`mb` to `asref:originX`/`originY`
and `xcell`/`ycell` to `scaleX`/`scaleY` when `maptyp` is UTM or State Plane.

### gtx

NOAA VDatum. `Header @endian big`: `lat0 f64`, `lon0 f64`, `dlat f64`, `dlon f64`, `nrows
i32`, `ncols i32`. Grid `bytes[..] layout cell f32 { dim axis Y size nrows dim axis X size
ncols }`, rows south to north (limit, as DTED). `hydroc1.gtx` is 40 + 21 × 11 × 4 bytes,
which the profile's size arithmetic must reproduce. Mapping: origin and scale to `asref:`,
`epsgCode 4326`, `araster:noDataValue -88.8888`.

### bt

VTBuilder Binary Terrain 1.3. `Header @endian little` 256 bytes: `marker ascii[10] @fixed
"binterr1.3"`, `columns i32`, `rows i32`, `dataSize i16`, `floatingPoint i16`, `hUnits i16`,
`utmZone i16`, `datum i16`, four `f64` extents, `extScale i16`, `vertScale f32`, padding
`bytes[190]`. Grid `cell switch` on `(floatingPoint, dataSize)`: f32, i32, i16; `order` column-
major (`X Y`), columns bottom to top. No corpus sample; ships not parse-verified with the
header offsets cross-checked against GDAL's `btdataset.cpp`.

### lcp

FARSITE v4 landscape. `Header @endian little` 7316 bytes: `crownFuels i32`, `groundFuels
i32`, `latitude i32`, four `f64` extents, ten `BandStats` (`lo i32`, `hi i32`, `numClasses
i32`, `values i32 repeat 100`), `numEast i32`, `numNorth i32`, four `f64` UTM extents,
`gridUnits i32`, `xRes f64`, `yRes f64`, ten `i16` unit codes, ten `ascii[256]` file names,
`ascii[512]` description. Band count is `derive [5 + (crownFuels == 21 ? 3 : 0) + (groundFuels
== 21 ? 2 : 0)]`. Grid `bytes[..] layout cell i16 { dim axis Y size numNorth dim axis Band size
bandCount dim axis X size numEast }`. Mapping: width, height, componentCount, `asref:originX`/
`originY` from west/north UTM, `xRes`/`yRes` to scale.

### idrisi and saga

Both follow the ENVI/EHdr bundle template, written in HDL's `bundle` + `header` surface rather
than hand Turtle. `idrisi`: `part ".rdc"` header with `@separator 0x3A @trim @ci` and keys
`"file format"`, `"data type"`, `"columns"`, `"rows"`, `"min. X"`, `"max. X"`, `"min. Y"`,
`"max. Y"`, `"flag value"`; `part ".rst"` raw grid whose `cell switch` reads the header's
`data type` (`byte`, `integer`, `real`, `rgb24`), little-endian. `saga`: `part ".sgrd"` header
with `@separator 0x3D @trim @ci` and keys `DATAFORMAT`, `DATAFILE_OFFSET`, `BYTEORDER_BIG`,
`POSITION_XMIN`, `POSITION_YMIN`, `CELLCOUNT_X`, `CELLCOUNT_Y`, `CELLSIZE`, `NODATA_VALUE`,
`TOPTOBOTTOM`; `part ".sdat"` raw grid with `@endian switch` on `BYTEORDER_BIG` and `cell
switch` on `DATAFORMAT`. Grid expressions reach the header through `asset.Header.<field>`
exactly as `ehdr.ttl` does. Mapping: width, height, `noDataValue`, `asref:originX`/`originY`/
`scaleX`/`scaleY`.

These two are the first `.hx` bundle rasters in the library. If the compiler's `header`/
`bundle` surface turns out to lack something `ehdr.ttl` uses, the profile is written as hand
Turtle from the EHdr template instead, and the spec notes the gap; that is a fallback, not a
scope change.

### dbf

xBase (dBASE III+/IV/5, FoxPro). `Header @endian little` 32 bytes: `version u8` (enum of the
common signatures), `lastUpdate` (`yy u8`, `mm u8`, `dd u8`), `numRecords u32`, `headerLength
u16`, `recordLength u16`, `bytes[16]`, `tableFlags u8`, `codePage u8`, `bytes[2]`.
`descriptors : FieldDescriptor repeat [(headerLength - 33) / 32]` where `FieldDescriptor` is
`name ascii[11] @trim-null`, `type ascii[1] enum {C, N, F, L, D, M, I, Y, T, B, ...}`, `bytes[4]`,
`length u8`, `decimalCount u8`, `bytes[14]`. `terminator u8 @fixed 0x0D`. `records : Record
repeat numRecords @at headerLength from stream-start`, `Record = { deleted ascii[1], data
bytes[parent.recordLength - 1] }`. Mapping: `numRecords` to `atab:rowCount`; each descriptor
to `atab:hasField` with `atab:fieldName` and `atab:fieldDataType`. The trailing `0x1A` EOF
marker is optional and not consumed. dBASE 7 (version 4, 48-byte descriptors) is a limit.

### wkb

A `module wkb`, root `Geometry`, imported by `gpkgblob`:

```
struct Geometry
  @endian switch { when [byteOrder == 1] => little  when [byteOrder == 0] => big }
{
  byteOrder : u8 enum { 0 => XDR, 1 => NDR }
  wkbType   : u32
  kind      : derive [wkbType % 1000]   means ageom:geometryType via map { when kind == 1 => rgeo:Point ... }
  axes      : derive [2 + ((wkbType / 1000) == 3 ? 2 : ((wkbType / 1000) == 0 ? 0 : 1))]
  hasZ      : derive [(wkbType / 1000) == 1 || (wkbType / 1000) == 3] means ageom:hasZ
  hasM      : derive [(wkbType / 1000) >= 2] means ageom:hasM
  body      : bytes[..] switch kind {
    1 => PointBody   2 => LineStringBody   3 => PolygonBody
    4 => CollectionBody  5 => CollectionBody  6 => CollectionBody  7 => CollectionBody
  }
}
struct PointBody      { order : derive [parent.byteOrder]  coords : f64 repeat [parent.axes] }
struct LineStringBody { order : derive [parent.byteOrder]  numPoints : u32  coords : f64 repeat [numPoints * parent.axes] }
struct PolygonBody    { order : derive [parent.byteOrder]  numRings : u32  rings : LinearRing repeat numRings }
struct LinearRing     { order : derive [parent.parent.byteOrder]  numPoints : u32  coords : f64 repeat [numPoints * parent.parent.axes] }
struct CollectionBody { order : derive [parent.byteOrder]  numGeometries : u32  geometries : Geometry repeat numGeometries }
```

Every body struct carries the same `@endian switch` keyed on its zero-byte `order` field. This
is the one mechanism risk in the wave: the Metaparser evaluates a struct's endianness rules
after each field is read, so a `derive` first field must be enough to fix the byte order before
the first physical field. The WKB parity test settles it on the first run. If it does not hold,
the fallback is to flatten the bodies into `Geometry` behind `if kind == N` presence clauses,
which keeps every physical field in the struct that owns the `byteOrder` byte; `LinearRing`
then becomes a `bytes[..]` sized by a preceding `numPoints`, and rings lose their per-ring
decomposition. The parity test is unchanged either way.

Empty geometries (count 0) parse as zero-length repeats. `gpkgblob.hx` replaces `wkb :
bytes[..]` with `wkb : wkb:Geometry` after `import "../wkb/wkb.hx" as wkb`, and limit 1 of its
header is rewritten to say the WKB is decomposed and where its own limits are.

## Verification

### Library gates (all ten)

`python tools/run_gates.py` in `hexplain-profiles` must pass: every `.hx` compiles with the
real compiler and conforms to the specification's SHACL; `test_tools_fixtures` holds the four
copied fixtures byte-identical.

### Parity tests (bmp, dted, dbf, wkb)

All four follow `IsobmffParityTest`: compile the fixture `.hx` in-process with `HdlCompiler`,
lower with `RdfToIrCompiler`, parse with `Metaparser`. Corpus-dependent tests use
`assumeTrue(Files.exists(...))` like `GdalParityTest`, so a checkout without the cached corpus
skips them rather than failing.

- **`BmpParityTest`**: for `1bit.bmp`, `4bit_pal.bmp`, `8bit_pal.bmp`, `bmp/red_rgb_1x1.bmp`,
  read every cell through `MultiDimensionalData` from the parsed layout, flip rows when
  `biHeight > 0`, emit band-sequential bytes (B, G, R reordered to R, G, B for the 24-bit
  case, which is what GDAL reports) and assert the SHA-256 recorded in
  `tests/gdal/results/oracle.jsonl` for that file. Width, height and band count are asserted
  from the parsed header. `4bit_rle4.bmp` and `byte_rle8.bmp` assert that `pixels` is absent
  because `biCompression != 0`.
- **`DtedParityTest`**: `n43_wgs72.dt0` parses to 121 columns of 121 elevations; transpose to
  north-up rows, convert signed-magnitude to two's complement, and assert GDAL's digest
  `338756b7…`. The origin derived from UHL is asserted against the values GDAL reports for the
  file. `n43_bad_crc.dt0` parses (the profile does not verify checksums; stated limit).
- **`DbfParityTest`**: for four corpus `.dbf` files with different versions and column
  types, assert `numRecords`, `headerLength`, `recordLength`, descriptor names, types,
  lengths and decimals against values pinned from an independent 30-line Python `struct`
  reader kept in the test's comment, and assert `headerLength + numRecords * recordLength`
  equals the file size or the file size minus one.
- **`WkbParityTest`**: a `@TestFactory` over the 136 cases in `gdal-vector-geometry.json`
  (the same oracle `GdalVectorGeometryTest` uses). The parsed tree is folded into the
  `GeometryValue` shape (type, dimensions, coordinates, children) and compared with the case's
  `expected`. A second test parses the `2d_envelope.gpkg` blob fixture through `gpkgblob.hx`
  and checks the nested geometry.

Each verified profile's header states `Verification status: parse-verified — <TestName>` and
names the samples; the other six say `NOT parse-verified` and name the corpus sample they were
written against, if any.

## Coverage inventory

`gdal-drivers.json` driver entries gain an optional `profiles` list:

```json
"profiles": [ { "name": "bmp", "iri": "https://hexplain.io/ns/profile/bmp", "verification": "parse-verified" } ]
```

`verification` is `parse-verified` or `not-parse-verified`. The link target is the profile's
ontology IRI, which the profile itself declares; no repository URL is asserted. Entries are
added for the ten new profiles and for the existing ones (`raster:gtiff`, `raster:png`,
`raster:nitf`, `raster:envi`, `raster:ehdr`, `raster:srtmhgt`, `raster:heif`, `raster:avif`,
`vector:shapefile`, `vector:gpkg`) so the column is complete rather than only new.
`_build_ontology_docs.py` renders a `Profiles` column; the existing `Evidence status` column
is untouched, because a profile is a description and not runtime evidence.
`test_gdal_inventory.py` asserts the schema of every `profiles` entry and that every named
profile directory exists in the sibling `hexplain-profiles` checkout when one is present.

## Sequencing

1. `wkb` first, because it carries the one mechanism risk and everything else is independent
   of its outcome.
2. `bmp`, `dted`, `dbf` with their parity tests, then the fixture copies.
3. `lan`, `gtx`, `bt`, `lcp` (single-file rasters, no tests beyond the gates).
4. `idrisi`, `saga` (the two bundle rasters; fallback to hand Turtle if the `.hx` surface
   lacks something).
5. `gpkgblob` upgrade and its test.
6. Coverage inventory and page.
7. Full gate runs in all three repos; profile headers finalised with test names.

## Risks

- **Nested-struct byte order in WKB** — covered above with a fallback that preserves the
  parity contract.
- **Sub-byte BMP cells through `MultiDimensionalData`**: `cellBitWidth` layouts may not be
  executable by the core reader. If so, the 1-bit and 4-bit samples are asserted at header
  level and their pixel digests at a smaller scope, and the profile header says which
  samples the pixel comparison covers.
- **`header`/`bundle` `.hx` surface for idrisi and saga** — fallback to hand Turtle.
- **Fixed-offset arithmetic** in `lan`, `bt`, `lcp` has no runtime check; each header offset
  is cross-referenced to the GDAL driver source line in the profile comment so a reviewer
  can verify without a sample.

## Engine gaps closed after implementation

The profiles above were first written to the subset the reference engine executed, with each
workaround recorded as a limit. A follow-up wave closed four gaps in `hexplain-tools`, and the
affected profiles now use the exact declared form. Every profile is additionally held to
`write(parse(file)) == file`.

| Declared capability | Was | Now |
|---|---|---|
| `bddo:asciiInteger` / `asciiDecimal` in a byte struct | Failed with "Unsupported integer bit width: 0"; DTED used `ascii[N]` plus derived `toNumber` siblings | A numeric type with no bit width is text: reads to Long or Double, drives sizes, offsets and counts. DTED uses `anum` and maps directly |
| `dlv:cellBitWidth` / `cellBitWidthFromField` | Refused by the array accessor; BMP's 1-bit and 4-bit samples were described but unverified | Packed cells are addressed and read at their own width, MSB-first by default, signed cells sign-extending. Both BMP samples are pixel-verified against GDAL |
| `dlv:dimensionStrideFromField` / `FromExpression` | Refused; BMP described one record per row to keep every layout contiguous | Resolved against the parse context, so BMP is one pixel array with the real pitch `((width * bits + 31) / 32) * 4` |
| `dlv:hasConditionalCellDataType` / `hasConditionalDimensionOrder` | Rejected at load, so no engine-parsed profile could use `cell switch` or `order switch` | Lowered and resolved at parse time, first matching arm wins; arms must permute the same axes, and no matching arm is an error |

Two design decisions from this wave are superseded as a result: the constraint that engine-parsed
profiles avoid `cell switch`, and BMP's row-record form.

The Idrisi and SAGA bundles keep their `cell switch` layouts and stay NOT parse-verified, for a
different reason than before. The construct now lowers and resolves, but their arms are conditioned
on a field in the *sibling header part* (`asset.GridHeader.dataFormat`), and a standalone part parse
has no asset context to reach it. The engine now reports that by name instead of letting a later arm
win by default, so what those two profiles need is bundle-aware parsing, not a layout capability.
The same holds for SAGA's struct-level `@endian switch`.

Resolution is now in one place. The parser fixes every size, stride, packed width, cell type and
dimension order against the parse context before wrapping bytes; the accessor refuses an
*unresolved* declaration by name rather than refusing the capability. Chunked layouts
(`chunkOffsetsFromField` and friends) remain declared but unexecuted, which is the next gap.

One writer defect surfaced and was fixed: a derived (`derive`) field referenced as a size was
mistaken for an automatic back-patched length, so any profile computing its own payload size could
not be written. A computed size needs no measurement of the payload it sizes.
