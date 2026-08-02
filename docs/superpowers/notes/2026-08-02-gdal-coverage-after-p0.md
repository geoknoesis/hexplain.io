# GDAL Coverage After P0 — What Hexplain Can Describe Now

**Date:** 2026-08-02 · **Branch state:** `main` (P0 merged; no P1 items landed)
**Supersedes the baseline in:** [GDAL format coverage in HDL](2026-08-01-gdal-hdl-coverage.md)
**Implements:** [P0-1..P0-4](2026-08-01-spec-improvements-from-gdal-survey.md)

**Read "support" precisely.** This measures what the *vocabulary can describe*. The HDL
compiler in `hexplain-tools` has not been updated for any P0 surface, and no existing format
profile has been rewritten to use one. Nothing below has been validated against a real file
by a running parser.

---

## 1. The headline

| Tier | Before P0 | After P0 | Δ |
|---|---:|---:|---:|
| ✅ **Full** — every byte reachable | 65 (27%) | **92 (38%)** | **+27** |
| ◐ **Container** — structure described, payload opaque | 48 | 48 | 0 |
| ◑ **Payload-only** — binary reachable, metadata not | 43 | 27 | −16 |
| ✗ **Out of scope** | 89 | 78 | −11 |
| **Expressible (✅+◐+◑)** | 156 (64%) | **167 (68%)** | **+11** |

Of 245 GDAL driver entries. The ◐ tier did not move because the two changes that would move
it — varint datatypes (P1-6) and codec pipelines (P1-5) — did not land.

### The change that matters most isn't in the table

Eleven formats were counted ✅ in the baseline but were **not actually authorable
end-to-end**: their record sizes and segment offsets are ASCII-coded, and HEL errored on
arithmetic with a non-numeric operand. `bddo:asciiInteger` fixed that. These are now
genuinely describable rather than optimistically counted:

**NITF · FITS · USGSDEM · DTED · S-57 · ESAT · FAST · CTG · TIGER · UK .NTF · PCIDSK**

Two more capabilities arrived that no tier count reflects:

- **Tiled and blocked rasters are describable at all for the first time.** Every Cloud
  Optimized GeoTIFF, blocked NITF imagery (`NBPR`/`NBPC`/`NPPBH`/`NPPBV`), and tile pyramid
  previously had no expression. `dlv:chunkSize` + `chunkOffsetsFromField` now covers them.
- **TIFF byte order can be described correctly.** `bddo:hasConditionalEndianness` replaces
  the hardcoded `bddo:LittleEndian` that made big-endian (MM) TIFF misdescribed.

---

## 2. Newly ✅ — the 27 formats P0 unlocked

All are "raw binary payload + flat `key = value` text sidecar", now reachable through
`bddo:KeyValueHeader`, or flat delimited grids through `bddo:DelimitedTable`.

### 2.1 Raster, from ◑ (21)

| Driver | Header form now expressible |
|---|---|
| **EHdr** | ESRI `.hdr` — `NROWS 400`, space-separated |
| **ENVI** | `.hdr` — `samples = 5000` (brace-enclosed multi-line values remain a gap) |
| **GenBin** | Generic `.hdr` |
| **EIR** | Erdas Imagine Raw header |
| **PAux** | PCI `.aux` — `key: value` |
| **MFF** | Vexcel `.hdr` — `key = value` |
| **MFF2** | Vexcel HKV header |
| **ILWIS** | `.mpr` INI-style (section headers are a mild limitation) |
| **ROI_PAC** | `.rsc` — `WIDTH 1000` |
| **RRASTER** | R `.grd` INI-style |
| **RST** | Idrisi `.rdc` — `file title  : xxx` |
| **SAGA** | `.sgrd` — `key = value` |
| **SNODAS** | `.Hdr` — `key: value` |
| **NDF** | NLAPS — `key=value` |
| **COASP** | DRDC config text |
| **CPG** | Convair PolGASP header |
| **MiraMonRaster** | `.rel` INI-style |
| **ISG** | Geoid header — `key : value` |
| **VICAR** | `LBLSIZE=` at a fixed offset, then flat `KEY=VALUE` |
| **DOQ1** | First-generation USGS DOQ keyword header |
| **DOQ2** | Labelled USGS DOQ keyword header |

### 2.2 Vector, from ◑ (2)

| Driver | Header form |
|---|---|
| **IDRISI** | `.vdc` — `key : value` beside binary `.vct` |
| **MiraMonVector** | `.rel` INI-style beside binary geometry |

### 2.3 From ✗ — flat delimited text (4)

| Driver | Why it works now |
|---|---|
| **CSV** | `DelimitedTable` with `fieldDelimiter`, `quoteChar`, `escapeChar`, `skipRecords` — the full CSV quoting model shipped |
| **XYZ** | One point per line with a consistent single-byte delimiter |
| **ZMAP** | `@`-prefixed header records plus FORTRAN fixed-width numeric fields |
| **MAP** | OziExplorer `.MAP` — comma-separated lines |

---

## 3. Improved but still short of ✅

### 3.1 ✗ → ◑ — header now describable, grid is not (7)

`AAIGrid` · `GRASSASCIIGrid` · `GSAG` · `GXF` · `GMT` · `WAsP` · `VDV`

All of these blocked on the same thing. Their `key value` headers now parse fine — a
`keyValueSeparator` splits at the first occurrence and `trimWhitespace` absorbs the padding,
so `ncols        100` reads correctly. **Their data sections do not**, because
`bddo:fieldDelimiter` is `xsd:hexBinary` — an exact byte sequence. A run of spaces of
unpredictable width is not expressible, and neither is a grid whose rows wrap arbitrarily
across lines.

> **This is the single cheapest remaining win.** A `bddo:whitespaceDelimited` boolean (or a
> delimiter register admitting "one or more whitespace bytes") would move all seven to ✅ and
> firm up `XYZ` and `PNM`. It is smaller than anything on the P1 list.

### 3.2 Still ◑ — 27 remaining

**Nested text labels (5)** — `PDS` · `ISIS2` · `ISIS3` (raster) · `PDS` (vector) · `ERS`
PVL `OBJECT`/`END_OBJECT` groups and ERS's `DatasetHeader Begin … End` blocks are recursive.
`DelimitedRecords` is non-recursive **by design**; the flat subset of each label parses, the
nesting does not.

**XML labels and manifests (12)** — `PDS4` · `DIMAP` · `SAFE` · `SENTINEL2` · `RS2` · `TSX` ·
`RCM` · `CPHD` · `E57` · `TIL` · `ISCE` · `Zarr` (JSON)
Untouched by P0 and deliberately out of scope. The [non-goals](2026-08-01-spec-improvements-from-gdal-survey.md#non-goals)
section proposes an external-schema annotation instead of a grammar.

**Directory structures (3)** — `GRASS` (raster and vector) · `AIG`-style trees
`abnd:PartSpec` still identifies members by `abnd:extension` only. No `pathPattern`, no
cardinality, no nested profiles — **P1-7 did not land**, so `measurement/*.tiff` and nested
mapsets cannot be profiled.

**Whitespace-delimited (2)** — `PNM` · the residue of §3.1.

Plus the balance of the original ◑ list whose blockers are unchanged.

### 3.3 Still ◐ — 48, unchanged

No ◐ format moved, because both relevant P1 items are outstanding:

- **P1-6 varints** would materially advance `MVT`, `PMTiles`, `OSM` (PBF), `Parquet`,
  `FlatGeobuf`, `OpenFileGDB`. Protobuf/flatbuffer framing is describable; reconstructing a
  LEB128 value still needs the escape hatch.
- **P1-5 codec pipelines** would help `HDF5`, `KEA`, `BAG`, `S102`/`S104`/`S111`, `Zarr`,
  `GTiff` (predictor + deflate). `hexplain:isEncodedWith` remains `sh:maxCount 1`, so filter
  chains cannot be expressed.

Chunked layout (P0-2) *did* improve this tier's descriptions — tile offset tables in
`GTiff`, `MBTiles`, `MRF`, `ESRIC`, JPEG 2000 are now expressible — but the sample payloads
stay opaque, so the tier is unchanged.

---

## 4. What "✅" now covers, in full (92)

The 65 from the baseline, plus the 27 in §2. Grouped by why they are reachable:

**Fixed-width binary** (unchanged, 40-odd) — `BMP` `BT` `BYN` `GTX` `NTv2` `SRTMHGT` `ACE2`
`KRO` `LAN` `LCP` `GSBG` `GS7BG` `GSC` `NOAA_B` `NGSGEOID` `NSIDCbin` `SIGDEM` `NWT_GRD`
`PCRaster` `RMF` `GFF` `COSAR` `IRIS` `MSGN` `Terragen` `TGA` `Leveller` `GTA` `DGN`
`Selafin` `SXF` `XLS` `AVCBIN` `OpenFileGDB` `MapInfo File` `netCDF` `AIG` `ADRG` `SRP` `RPFTOC` `LOSLAS`

**ASCII-record formats** (now genuinely authorable via `asciiInteger`) — `NITF` `FITS`
`USGSDEM` `DTED` `S57` `ESAT` `FAST` `CTG` `TIGER` `UK .NTF` `PCIDSK` `CEOS` `SAR_CEOS`
`JAXAPALSAR` `L1B` `AIRSAR` `JDEM`

**Self-declaring byte order** (now correct via `hasConditionalEndianness`) — `GTiff` `COG`
`LIBERTIFF` `SNAP_TIFF` `GRIB`

**Sidecar `key = value` + raw grid** (new — §2.1, §2.2) — 23 drivers

**Flat delimited text** (new — §2.3) — `CSV` `XYZ` `ZMAP` `MAP`

---

## 5. Ranked next steps, by formats-per-unit-effort

1. **Whitespace-run delimiter** — smaller than any P1 item; moves 7 ◑→✅ and firms up 2 more.
2. **P1-7 bundle path patterns** — unlocks the directory formats (`SAFE`, `SENTINEL2`,
   `GRASS`, `Zarr`, `ESRIC`, `AIG`) and a reusable ZIP profile.
3. **P1-6 varints** — 6 modern vector formats move decisively toward ✅.
4. **P1-5 codec pipelines** — the HDF5/Zarr/Parquet family.
5. **Nested-group support in `DelimitedRecords`** — would take PVL (`PDS`, `ISIS2`, `ISIS3`)
   and `ERS`. Weigh carefully: it erodes the deliberate non-recursion boundary.

Note that none of these is the gating item for *using* any of this. The HDL compiler still
emits and consumes none of the P0 surfaces, and no profile has been rewritten to use them —
that work is the actual path from "describable" to "supported".

---

## 6. Method

Verified against `main` at merge of the P0 branch: P0-1..P0-4 present in
`specification/bddo/bddo.ttl`, `specification/dlv/dlv.ttl`, `specification/hel/index.html`;
`specification/aspect/bundle/bundle.ttl` still exposes `abnd:extension` only; no
`hasEncodingStep`, `varint`, `cellBitWidth`, or `dimensionStrideFrom*` anywhere.

Tier assignments follow each format's published specification, not GDAL's driver source.
Judgments about text-header shape (`key = value` vs nested vs whitespace-run) determine most
of the movement in §2 and §3.1 and are the least certain part of this analysis — a format
whose header turns out to use nesting or variable whitespace belongs one tier lower.
