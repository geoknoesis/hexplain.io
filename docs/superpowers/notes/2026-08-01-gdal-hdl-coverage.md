# GDAL Format Coverage in HDL

**Date:** 2026-08-01 · **Re-tallied:** 2026-08-09 · **Status:** Survey / roadmap input
**Scope:** all 245 driver entries in GDAL's raster (160) and vector (85) driver indexes,
classified by whether the underlying *format* can be described in HDL.

This answers: *which GDAL formats can I express in HDL?* It classifies the **format**, not
GDAL's implementation of it. Where several drivers read one format (five JPEG 2000 drivers,
four TIFF drivers), each driver row gets the same verdict.

---

## 1. What HDL can and cannot say

HDL compiles to BDDO (byte structure) + HEL (expressions) + hexplain core (semantic
mapping) + DLV (array layout) + hx-bundle (multi-file). Its expressive envelope is
therefore:

**Can express**

- Fixed-width binary fields — `u8`…`u64`, `i8`…`i64`, `f32`/`f64`, all with explicit
  endianness ([bddo.ttl:128-153](../../../specification/bddo/bddo.ttl#L128-L153)).
- Fixed-width **text** fields (`ascii`, `utf8`, `utf16le/be`, `latin1`) — so ASCII-coded
  record formats (NITF, DTED, FITS cards, USGSDEM, S-57) are first-class, not second-class.
- Variable sizing driven by a sibling field, an expression, a terminator, or end-of-stream.
- Absolute/relative seeking — `@at <expr> from stream-start|stream-end|parent-start|current`
  — which is what makes pointer-chasing formats (TIFF IFDs, tile-offset tables) work.
- Repetition by count, by expression, or `repeat until <cond>`.
- Conditional type dispatch (`switch`) — TLV chunk/box/marker/segment formats.
- Bit fields (`bits[N]`), bit order, alignment, fixed magic values, checksums with an
  explicit covered range.
- N-dimensional sample layout with per-axis size and stride (DLV) — the raster grid.
- Opaque encoded blocks via `@encoded-with <codec>` against the open SKOS codec/compression
  registers ([encoding.ttl:30-69](../../../specification/aspect/encoding/encoding.ttl#L30-L69)).
- Multi-file assets via `abnd:BundleProfile` with four binding kinds — `containment`,
  `naming-convention`, `manifest-reference`, `concatenation`
  ([bundle.ttl:72-95](../../../specification/aspect/bundle/bundle.ttl#L72-L95)).
- Anything else, via `raw-turtle { … }` / `@prop <curie> <value>`.

**Cannot express**

- **Delimiter-driven or recursive-grammar text.** BDDO addresses bytes by offset and size.
  CSV, XML, JSON, PVL/ODL labels and `key = value` headers have no fixed offsets and need a
  tokenizer + production rules. There is no HDL surface for this and no vocabulary under it.
- **Algorithmic decoding.** Entropy coding (Huffman, arithmetic, LZW, EBCOT), transforms
  (DCT, wavelet), and general-purpose compression are *identified* by `@encoded-with`, never
  *described*. HDL describes; it does not execute.
- **Data-driven schema.** Formats whose record layout is defined by a dictionary embedded in
  the file itself (HFA/Erdas `.img`, flatbuffer vtables, Thrift metadata) can have their
  framing described but not their per-record field layout.
- **No byte stream at all.** Network services, RDBMS connections, in-memory and virtual/meta
  drivers own no file layout to describe.

### 1.1 One real gap worth naming

HEL's function set is `sizeof`, `len`/`count`, `eof` only, and its coercion rules make
arithmetic on a non-numeric operand an error
([hel/index.html:126-172](../../../specification/hel/index.html#L126-L172)). BDDO has no
ASCII-numeric datatype — an ASCII-coded integer is `bddo:string`.

Consequence: **an ASCII-coded count/length field cannot currently drive
`sizeFromExpression`, `repeatCountFromExpression`, or `atOffsetFromExpression`.** The NITF
design works around this at the semantic layer — declare BCS-N as a string, then coerce with
`hexplain:valueExpression` + `valueDatatype xsd:integer`
([nitf-profile-design.md:70-79](../specs/2026-07-26-nitf-profile-design.md#L70-L79)) — but
that produces the mapped value, not a sizing input.

This affects a large share of the Tier-1 list below: FITS (`NAXIS1`/`NAXIS2` drive the array
extent), USGSDEM, DTED, S-57, ESAT, FAST, CTG, TIGER, UK .NTF, PCIDSK. Adding either an
ASCII-numeric datatype to BDDO or a numeric-coercion rule to HEL is the single
highest-leverage change for GDAL coverage.

---

## 2. Classification

| Tier | Symbol | Meaning |
|---|---|---|
| **Full** | ✅ | Every byte reachable. Header, metadata and the sample grid all described in BDDO + DLV. No opaque block needed to reach a cell or feature value. |
| **Container** | ◐ | Structure, framing and metadata fully described; one or more payload blocks stay opaque behind `@encoded-with`. You get complete metadata, provenance and integrity — not decoded samples. |
| **Payload-only** | ◑ | The binary payload is a clean DLV block, but the format's parameters live in a text/XML/PVL label BDDO cannot decompose. Describe the binary part + a bundle profile; the label needs `raw-turtle` or a future text-grammar surface. |
| **Out of scope** | ✗ | No byte stream owned by the format. Reason codes: **(a)** network service/API · **(b)** RDBMS connection · **(c)** in-memory/virtual/meta driver · **(d)** delimiter or grammar-driven text · **(e)** object/array store, not a file · **(f)** closed proprietary, SDK-only. |

**Bundle** column: ● means the format needs an `abnd:BundleProfile` (multi-file asset).

### Tally

Two columns: the survey as written on 2026-08-01, and a re-tally on 2026-08-09 after the
vocabulary work this survey prompted. §2.1 accounts for every driver that moved.

| | 2026-08-01 | 2026-08-09 | Change |
|---|---:|---:|---:|
| ✅ Full | 65 (27%) | **97 (40%)** | +32 |
| ◐ Container | 48 (20%) | **49 (20%)** | +1 |
| ◑ Payload-only | 43 (18%) | **22 (9%)** | −21 |
| ✗ Out of scope | 89 (36%) | **77 (31%)** | −12 |
| **Total drivers** | **245** | **245** | |

**168 of 245 driver entries (69%) are now expressible in HDL to some useful degree; 97 (40%)
fully** — up from 156 (64%) and 65 (27%).

The tier lists in §3–§6 below are the ORIGINAL classification and have deliberately not been
rewritten in place; §2.1 is the delta against them.

---

## 2.1 What changed, and why (re-tally, 2026-08-09)

This survey named two blockers. Both have shipped, which is what moved the numbers.

**§1.1's "one real gap worth naming" — ASCII-coded numerics.** BDDO gained
`bddo:asciiInteger` / `bddo:asciiDecimal` (+ `bddo:numericBase`), and HEL gained
`toNumber()`. An ASCII-coded count or length now drives `sizeFromExpression`,
`repeatCountFromExpression` and `atOffsetFromExpression` directly, instead of being a string
coerced at the semantic layer into a value that could not size anything.

**§1's "cannot express: delimiter-driven text ... `key = value` headers ... no vocabulary
under it".** BDDO gained `bddo:DelimitedRecords` and its two specialisations —
`KeyValueHeader` (line-oriented `key = value`) and `DelimitedTable` (separator- or
whitespace-separated rows) — with record/field delimiters, quoting, escaping, comment
prefixes, `skipRecords`, and `whitespaceSeparated` for column-aligned text.

The survey predicted this would be "the largest single unlock available ... ~35 drivers from
◑ to ✅". The re-tally puts it at 32 drivers moved to ✅ across both tiers, so that estimate
was close and slightly optimistic.

Four further changes contributed:

- **Cross-part references** — HEL's `asset` root plus hx-bundle's resolution rules — let a
  raw grid read its extents, sample type and byte order from a sibling header file. Without
  it, a sidecar pair could be *listed* but the payload could not be *sized*, so the whole
  raw-binary-plus-text-header class stayed ◑ no matter how well the header parsed.
- **Conditional cell type and dimension order** (`dlv:hasConditionalCellDataType`,
  `hasConditionalDimensionOrder`) handle interleave keywords (BIL/BIP/BSQ) and width
  keywords, which nearly every format in that class uses.
- **`partExtension()`** distinguishes alternatives within one PartSpec — the ESRI `.flt`
  case, where the filename rather than the header decides integer versus float.
- **Sub-byte cells, chunked layout, encoding pipelines and varints** improved fidelity
  broadly without moving tiers on their own. One exception is noted below.

### Drivers that moved

**◑ → ✅ (21).** Raw binary payload + a flat `key = value` text sidecar, now fully
describable as `KeyValueHeader` + `abnd:BundleProfile` + cross-part references:

> `EHdr`, `ENVI`, `GenBin`, `EIR`, `PAux`, `MFF`, `ILWIS`, `ISCE`, `ROI_PAC`, `RRASTER`,
> `RST`, `SAGA`, `SNODAS`, `NDF`, `COASP`, `CPG`, `ISG`, `DOQ1`, `DOQ2`, `PNM` (raster);
> `IDRISI` (vector).

`EHdr` and `ENVI` are not predictions — both are written, shipped and SHACL-conforming
([ehdr.ttl](../../../specification/profiles/ehdr/ehdr.ttl),
[envi.ttl](../../../specification/profiles/envi/envi.ttl)). They are the two hardest cases in
the group (conditional cell type, conditional dimension order, cross-part sizing), so the
rest of the class follows from a demonstrated pattern rather than an argued one.

**✗(d) → ✅ (11).** Delimited or whitespace-separated text that needs a tokenizer but no
recursive grammar:

> `AAIGrid`, `GRASSASCIIGrid`, `XYZ`, `GSAG`, `ZMAP`, `MAP` (OziExplorer), `PRF` (raster);
> `CSV`, `GMT`, `WAsP`, `GTFS` (vector).

`GTFS` moves for a different reason than the rest: it is a ZIP of CSVs, and the survey
already noted the ZIP container is fully expressible. `abnd:nestedProfile` supplies the
missing piece — a part described by another profile — so container and members are now both
in reach.

**✗(d) → ◐ (1).** `DXF` is alternating group-code/value lines, which `DelimitedRecords`
describes structurally; the entity grammar layered on top of those pairs is not expressible,
so it lands at container level rather than full.

### Drivers that did NOT move, and why

Being explicit, since the tempting error is to assume a text surface solves all text:

- **Nested or sectioned labels stay ◑.** `DelimitedRecords` is deliberately non-recursive.
  PVL/ODL (`OBJECT = … END_OBJECT`) keeps `PDS`, `ISIS2`, `ISIS3` and `VICAR` at ◑; ERMapper's
  `Begin/End` blocks keep `ERS`; sectioned INI keeps `MiraMonRaster`; directory-structured
  databases keep `GRASS`, `MFF2` and `MiraMonVector`.
- **XML and JSON labels stay ◑** — all eleven of them (`PDS4`, `DIMAP`, `SAFE`, `SENTINEL2`,
  `RS2`, `TSX`, `RCM`, `CPHD`, `E57`, `TIL`, `Zarr`). Nothing here addresses recursive markup,
  and `Zarr` is unchanged despite chunked layout and encoding pipelines both landing, because
  its blocker was always `.zarray`/`.zattrs` being JSON.
- **The ◐ tier is almost untouched**, as expected: its payloads are opaque because they are
  entropy-coded, and describing a codec chain more precisely does not decode one.
- **`MVT` is the one ◐ entry whose stated blocker is gone.** The survey recorded "varint
  framing is expressible but HEL has no accumulator to reconstruct the value — needs the
  escape hatch"; `bddo:varuint`/`varint`/`sqliteVarint` are now primitive types. It is left at
  ◐ pending a real look at whether protobuf's data-driven field ordering is separately
  blocking, rather than promoted on the strength of one removed obstacle.
- **Reason codes (a), (b), (c), (e), (f) are structurally unreachable** — 49 drivers with no
  byte stream to describe, or a closed one. No vocabulary change touches them, and the
  ceiling for this survey is therefore 196, not 245.

**What would move it further** is analysed separately, driver by driver, in
[2026-08-09-gdal-coverage-next-features.md](2026-08-09-gdal-coverage-next-features.md).

### Confidence

The 21 ◑ movements rest on a demonstrated pattern (two shipped profiles) and are the firm
part of this re-tally. The 11 ✗(d) movements are judgment calls made from each format's
general shape rather than a re-reading of its specification, and are where an error would be:
`ZMAP`, `PRF` and `MAP` are the three I would check first. `GXF`, `VDV`, `AVCE00` and `SOSI`
were left at ✗ under the same uncertainty, so the error is not systematically one-directional.

---

## 3. Tier 1 — Full (✅)

Everything is reachable. These are the formats HDL was designed for.

### 3.1 Raster (53)

| Driver | Format | Bundle | Notes |
|---|---|:--:|---|
| ACE2 | ACE2 elevation | | Headerless raw int16/float32 grid — pure DLV. Extent comes from the filename, so author one struct per tile variant. |
| ADRG | ARC Digitized Raster Graphics | ● | ISO 8211 fixed records; `.gen`/`.img`/`.thf` bound by naming convention. |
| AIG | Arc/Info Binary Grid | ● | Directory of big-endian `.adf` files (`hdr.adf`, `w001001x.adf` index, tile data). |
| AIRSAR | AIRSAR Polarimetric | | Fixed-length ASCII header records + binary scattering matrix. |
| BMP | Windows DIB | | `BITMAPFILEHEADER` + `BITMAPINFOHEADER` + palette + rows. Textbook BDDO. |
| BT | VTP Binary Terrain | | 256-byte fixed binary header + raw grid. Ideal reference example. |
| BYN | NRCan geoid `.byn` | | 80-byte binary header + scaled integer grid. |
| CEOS | CEOS Image | | Fixed-length record descriptors, binary + ASCII fields. |
| COG | Cloud Optimized GeoTIFF | | Same format as GTiff; creation-only driver. Tile-offset arrays and IFD ordering are expressible constraints. |
| COSAR | TerraSAR-X Complex SAR | | Documented fixed header + per-burst range-line blocks. |
| CTG | USGS LULC Composite Theme Grid | | Fixed-width ASCII logical records. See §1.1 on ASCII counts. |
| DTED | Military Elevation Data | | Fixed UHL/DSI/ACC records + fixed data blocks with per-block checksums — `@checksum` maps directly. |
| ESAT | Envisat Image Product | | Fixed 1247-byte MPH + SPH + DSD records, then binary MDS. Excellent fit. |
| FAST | EOSAT FAST | | Fixed 1536-byte ASCII header records + raw imagery. |
| FITS | Flexible Image Transport System | | 2880-byte blocks of 80-char card images + raw N-d array. Cards are fixed-width text; array via DLV. Blocked on §1.1 for `NAXISn`-driven extent. |
| GFF | Sandia GSAT | | Documented binary header + raw complex samples. |
| GRIB | WMO GRIB1/GRIB2 | | Length-prefixed sections, code tables, bit-packed data section. Simple/complex packing → `bits[N]` + DLV. JPEG2000-packed sections drop to ◐. |
| GS7BG | Surfer 7 Binary Grid | | Tagged binary sections (id/length/payload) — a `switch` over section ids. |
| GSBG | Surfer 6 Binary Grid | | Fixed 56-byte header + float grid. |
| GSC | GSC Geogrid | | Fixed binary header + grid. |
| GTA | Generic Tagged Arrays | | Self-describing tagged binary; uncompressed variant is fully reachable. |
| GTiff | GeoTIFF | | **Already profiled** — [tiff-profile.ttl](../../../../hexplain-tools/core/src/main/resources/tiff-profile.ttl). IFD pointer-chasing via `@at … from stream-start`. Compressed strips drop to ◐. |
| GTX | NOAA vertical datum grid shift | | 40-byte header + float grid. |
| IRIS | Vaisala radar | | Documented C-struct product/ingest headers. |
| JAXAPALSAR | JAXA PALSAR | | CEOS-style fixed records. |
| JDEM | Japanese DEM | | Fixed ASCII header + fixed-width ASCII samples. |
| KRO | KOLOR Raw | | 20-byte header + raw interleaved samples. |
| L1B | NOAA AVHRR Level 1b | | Fixed TBM/ARS header + fixed-length data records. |
| LAN | Erdas 7.x `.LAN`/`.GIS` | | 128-byte binary header + raw bands. |
| LCP | FARSITE v.4 LCP | | ~7316-byte fixed header + band-interleaved int16 — DLV with a Band axis. |
| Leveller | Daylon Leveller | | Chunked tag/length/value binary. |
| LIBERTIFF | GeoTIFF (alt. reader) | | Same as GTiff. |
| LOSLAS | NADCON `.los`/`.las` | ● | Paired binary grid-shift files, bound by naming convention. |
| MSGN | MSG Native `.nat` | | Documented fixed binary records. |
| netCDF | NetCDF classic (CDF-1/2/5) | | Magic `CDF\x01` + dim/attr/var lists with 4-byte-aligned records and explicit data offsets. Compact and fully specified — a strong showcase. **netCDF-4 is HDF5 → ◐.** |
| NGSGEOID | NOAA NGS geoid grids | | Fixed binary header + float grid. |
| NITF | NITF 2.0/2.1 (+ CIB/CADRG/ECRG/HRE) | | **Already profiled** — see [nitf-profile-design.md](../specs/2026-07-26-nitf-profile-design.md). The reference ASCII-record case. |
| NOAA_B | GEOCON/NADCON5 `.b` | | Fixed binary header + grid. |
| NSIDCbin | NSIDC sea ice concentration | | 300-byte header + byte grid. |
| NTv2 | NTv2 datum grid shift | | 16-byte name/value overview + subgrid records + float shifts. Clean nested-struct case. |
| NWT_GRD | Northwood/Vertical Mapper | | Documented binary header + raw grid. |
| PCIDSK | PCI `.pix` | | 512-byte block structure with ASCII header segments and a segment pointer table. |
| PCRaster | PCRaster CSF | | Documented fixed binary header + raw grid. |
| RMF | Raster Matrix Format | | Documented binary header + tile table. Compressed variants → ◐. |
| RPFTOC | RPF `A.TOC` + CADRG frames | ● | ISO 8211 TOC + NITF-framed image files, bound by manifest reference. |
| SAR_CEOS | CEOS SAR Image | | Fixed-length record structure. |
| SIGDEM | Scaled Integer Gridded DEM | | Documented fixed binary header + int grid. |
| SNAP_TIFF | SNAP GeoTIFF | | TIFF; the SNAP metadata lives in a private tag whose payload is XML (→ `raw-turtle` or ◑ for that tag only). |
| SRP | ASRP/USRP `.gen` | ● | ISO 8211 fixed records; multi-file. |
| SRTMHGT | SRTM HGT | | Pure raw big-endian int16 grid, extent from file size. The simplest possible HDL description. |
| Terragen | Terragen `.ter` | | Chunked binary (4-char tag + payload). |
| TGA | TARGA | | Fixed 18-byte header + raw samples. RLE variant → ◐. |
| USGSDEM | USGS ASCII DEM / CDED | | Fixed 1024-byte logical records with fixed-width Fortran-style A/I/D fields. Blocked on §1.1 for record counts. |

### 3.2 Vector (12)

| Driver | Format | Bundle | Notes |
|---|---|:--:|---|
| AVCBIN | Arc/Info Binary Coverage | ● | Directory of big-endian binary files (`arc.adf`, `pal.adf`, `tbl` …). |
| DGN | Microstation DGN v7 | | Fixed-length element headers with heavy bit-field packing — `bits[N]` throughout. |
| ESRI Shapefile | Shapefile / DBF | ● | **The canonical bundle case**, already worked in [the hx-bundle design](../specs/2026-07-26-multipart-asset-bundle-design.md) and [shapefile-profile.ttl](../../../../hexplain-tools/core/src/test/resources/shapefile-profile.ttl). `.shp` mixed-endian records, `.shx` index, `.dbf` fixed-width dBase records, `.prj`/`.cpg` sidecars. |
| MapInfo File | MapInfo TAB (binary side) | ● | `.map`/`.dat`/`.id`/`.ind` are documented binary; the `.tab` header is text (→ ◑ for that part). **MIF/MID is text → ✗(d).** |
| netCDF | NetCDF classic — vector | | As raster. |
| OpenFileGDB | Esri File Geodatabase | ● | `.gdbtable`/`.gdbtablx`/`.spx` layouts are documented by the OpenFileGDB reverse-engineering spec; geometries are varint-delta encoded (needs the escape hatch for value reconstruction, but the framing is clean). |
| S57 | IHO S-57 ENC | | ISO/IEC 8211 DDR/DR records with field and subfield directories. Thoroughly specified — arguably the best non-NITF showcase for HDL's ASCII-record support. |
| Selafin | Selafin / SERAFIN | | Fortran unformatted sequential: every record wrapped in 4-byte length markers. Trivially expressible and a nice `sizeFromField` example. |
| SXF | SXF (Russian) | | Documented binary header + typed object records. |
| TIGER | US Census TIGER/Line | ● | Fixed-width ASCII record types (RT1, RT2, RT6 …) across a file set. |
| UK .NTF | UK National Transfer Format | | Fixed-width ASCII record types with continuation markers. |
| XLS | MS Excel BIFF8 | | BIFF record stream (2-byte type + 2-byte length + payload) inside an OLE2/CFB compound file — both layers fully documented binary. **XLSX is ZIP+XML → ✗(d).** |

---

## 4. Tier 2 — Container (◐)

Framing, metadata and structure are fully expressible; sample/feature payloads stay opaque
behind `@encoded-with`. This is the right level for provenance, integrity, security-marking
and metadata use cases — just not for pixel values.

### 4.1 Raster (36)

| Driver | Opaque part | Notes |
|---|---|---|
| AVIF | AV1 OBU bitstream | ISOBMFF box tree fully expressible. |
| BAG | HDF5 datasets + XML metadata | HDF5 superblock/B-tree/object-header layout is specified; the embedded ISO 19115 metadata is XML. |
| BASISU | Transcodable texture payload | Container documented. |
| BSB | RLE-compressed raster | Text header portion is ◑. |
| CAD (raster) | DWG bit-packed object stream | Reverse-engineered; very high authoring cost. |
| CALS | CCITT Group 4 payload | 128-byte fixed ASCII record header is ✅. |
| DDS | BC/DXT block payload | Header ✅; BCn blocks are fixed 8/16 bytes, so even the block grid is describable — only the intra-block decode is opaque. |
| ESRIC | JPEG/PNG tiles, `conf.xml` | Bundle index files are binary ✅. |
| EXR | ZIP/PIZ/DWA-compressed blocks | Attribute list + chunk offset table fully expressible. |
| GIF | LZW image data | Block/sub-block structure is a clean `repeat until` case. |
| GPKG (raster) | SQLite B-tree + tile blobs | SQLite's page format is fully documented, but reaching a row needs B-tree traversal and SQL semantics — beyond HEL. Describe the file header + page framing; treat rows as opaque. |
| HDF4 | Compressed/chunked data elements | DD block + tag/ref structure expressible. |
| HDF5 | Filtered/chunked datasets | Superblock, B-trees, object headers all specified. Large but tractable; filters stay opaque. |
| HEIF | HEVC bitstream | ISOBMFF ✅. |
| HF2 | Block-differential / gzip (`.hfz`) | |
| HFA | Data-driven record layouts | The Erdas `.img` node tree is describable, but record layouts come from a dictionary string *inside the file* — schema-from-data, which HDL cannot express. |
| JP2ECW | EBCOT packet bitstream | JP2 box container ✅, codestream SIZ/COD/QCD markers ✅. |
| JP2Grok | " | Same format, different library. |
| JP2KAK | " | " |
| JP2MrSID | " | " |
| JP2OpenJPEG | " | " |
| JPEG | Entropy-coded scan | Marker segments are textbook TLV; DQT/DHT/SOF tables fully expressible. |
| JPEGXL | JXL codestream | |
| KEA | HDF5 payload | |
| KTX2 | BasisU/UASTC/Zstd payload | Container fully documented. |
| MBTiles | SQLite + tile blobs | As GPKG. |
| MRF | `.pjg`/`.ppg` tiles; `.mrf` is XML | The `.idx` binary tile index is ✅. |
| OpenFileGDB (raster) | Raster blobs in tables | Table framing ✅. |
| PDF | Object bodies, stream filters | The `xref` table and trailer are byte-addressable; PDF object syntax is a token grammar. |
| PNG | Deflate-compressed `IDAT` | **Already profiled** — [png-profile.ttl](../../../../hexplain-tools/core/src/main/resources/png-profile.ttl). Chunk structure, CRC coverage and conditional dispatch all reference-quality; only the filtered/deflated pixel stream is opaque. |
| RIK | LZW/RLE tiles | |
| S102 | HDF5 payload | IHO S-102 bathymetric surface. |
| S104 | HDF5 payload | |
| S111 | HDF5 payload | |
| SQLite (Rasterlite) | SQLite + tile blobs | |
| WEBP | VP8/VP8L bitstream | RIFF container ✅. |

### 4.2 Vector (12)

| Driver | Opaque part | Notes |
|---|---|---|
| Arrow | Flatbuffer vtable indirection | IPC framing (continuation marker, length prefix, aligned body buffers) is ✅; flatbuffer field resolution is data-driven. |
| CAD | DWG object stream | |
| DWG | DWG object stream | |
| FlatGeobuf | Flatbuffer bodies | Magic + header + packed Hilbert R-tree framing ✅. |
| GPKG (vector) | SQLite B-tree | The **GeoPackage Binary geometry blob** (magic `GP`, flags byte, envelope, WKB) *is* a clean ✅ HDL struct — worth profiling on its own. |
| MVT | Protobuf varints | Varint framing is expressible (`repeat until (b & 0x80) == 0`), but HEL has no accumulator to reconstruct the value — needs the escape hatch. |
| OSM | PBF: protobuf + zlib blobs | BlobHeader/Blob framing ✅. XML variant is ✗(d). |
| Parquet | Thrift-compact footer, encoded pages | `PAR1` magic, footer length, page headers ✅ at the framing level. |
| PDF | As raster. | |
| PGeo | Jet/MS Access `.mdb` pages | Reverse-engineered page structure. |
| PMTiles | Gzipped varint directories | Fixed 127-byte header is fully ✅. |
| SQLite / Spatialite | SQLite B-tree | |

---

## 5. Tier 3 — Payload-only (◑)

The raster/table payload is a clean DLV block — often the *easiest* possible DLV case — but
the parameters that give it meaning (extent, band count, data type, georeferencing) live in a
`key = value` text header, a PVL/ODL label, or XML. Author the binary part plus an
`abnd:BundleProfile` binding header to payload; carry the header semantics through
`raw-turtle` until a text-grammar surface exists.

**This is the largest single unlock available.** A `header` surface for line-oriented
`key = value` text would move ~35 drivers from ◑ to ✅ — more than any other change.

### 5.1 Raster (39)

**Raw binary + text sidecar** (bundle, naming convention): `EHdr` (ESRI `.hdr`), `ENVI`,
`GenBin`, `EIR`, `PAux` (PCI `.aux`), `MFF`, `MFF2`, `ERS` (ERMapper), `ILWIS`, `ISCE`,
`ROI_PAC` (`.rsc`), `RRASTER` (R `.grd`/`.gri`), `RST` (Idrisi `.rdc`), `SAGA`
(`.sgrd`/`.sdat`), `SNODAS`, `NDF` (NLAPS), `COASP`, `CPG`, `MiraMonRaster`, `GRASS`, `ISG`.

**PVL/ODL or embedded text label + raw array**: `PDS` (v3), `ISIS2`, `ISIS3`, `VICAR`
(`LBLSIZE` is at a fixed offset; the label body is text), `DOQ1`, `DOQ2`, `PNM` (whitespace-
delimited header).

**XML label/manifest + binary or TIFF/JP2 payload** (bundle, manifest reference): `PDS4`,
`DIMAP`, `SAFE` (Sentinel-1), `SENTINEL2`, `RS2` (RadarSat-2), `TSX` (TerraSAR-X), `RCM`,
`CPHD`, `E57` (the 1024-byte CRC-checked page structure *is* ✅; the XML section is not),
`TIL`, `Zarr` (chunk files are DLV blocks; `.zarray`/`.zattrs` are JSON).

### 5.2 Vector (4)

`GRASS` (vector directory), `IDRISI` (`.vct` binary + `.vdc` text), `MiraMonVector`
(binary geometry + `.rel` text), `PDS` (PVL label + fixed-width table rows — the **table
itself is ✅**).

---

## 6. Tier 4 — Out of scope (✗)

No byte stream the format owns. Listed by reason so the omission is auditable.

**(a) Network service / API — 18**
Raster: `DAAS`, `EEDAI`, `JPIPKAK`, `NGW`, `OGCAPI`, `PLMosaic`, `WCS`, `WMS`, `WMTS`.
Vector: `AmigoCloud`, `CARTO`, `CSW`, `EEDA`, `Elasticsearch`, `NGW`, `OAPIF`, `PLScenes`, `WFS`.

**(b) RDBMS connection — 11**
Raster: `GeoRaster` (Oracle), `PostGISRaster`.
Vector: `ADBC`, `HANA`, `IDB`, `MongoDBv3`, `MSSQLSpatial`, `MySQL`, `OCI`, `ODBC`, `PostgreSQL`.

**(c) In-memory, virtual, or meta driver — 13**
Raster: `DERIVED`, `GDALG`, `GTI`, `MEM`, `STACIT`, `STACTA`, `VRT`.
Vector: `AIVector`, `GDALG`, `GPSBabel`, `MEM`, `Memory`, `VRT`.

**(d) Delimiter- or grammar-driven text (CSV / XML / JSON / SQL) — 40**
Raster: `AAIGrid`, `ECRGTOC`, `GRASSASCIIGrid`, `GSAG`, `GXF`, `KMLSuperoverlay`, `MAP`
(OziExplorer), `PRF`, `XYZ`, `ZMAP`.
Vector: `AVCE00`, `CSV`, `DXF`, `EDIGEO`, `ESRIJSON`, `GeoJSON`, `GeoJSONSeq`, `GeoRSS`,
`GML`, `GMLAS`, `GMT`, `GPX`, `GTFS`, `INTERLIS 1`/`2`, `JML`, `JSONFG`, `KML`, `LIBKML`,
`LVBAG`, `MapML`, `NAS`, `ODS`, `PGDump`, `SOSI`, `TopoJSON`, `VDV`, `VFK`, `WAsP`, `XLSX`,
`XODR`.

> **Note on ZIP-based members.** `KMZ`, `XLSX`, `ODS`, `GTFS`, `SAFE`, `SENTINEL2` are ZIP
> or directory containers. The **ZIP format itself is fully expressible** (local file
> headers, data descriptors, central directory, EOCD) — so HDL can describe the container
> and enumerate members with `abnd:Part`. Only the XML/CSV member *content* is out of reach.
> A reusable `zip.hx` profile would be a good early addition to the profile library.

**(e) Object/array store, not a file — 2**
`TileDB` (raster and vector).

**(f) Closed proprietary, SDK-only — 5**
Raster: `ECW`, `MrSID`, `MSG` (EUMETSAT wavelet).
Vector: `DGNv8` (ODA SDK), `FileGDB` (Esri SDK).

Reason-code totals: 18 + 11 + 13 + 40 + 2 + 5 = **89**, matching §2.

*(Counts overlap slightly where a driver name appears in both the raster and vector index —
`GDALG`, `GRASS`, `MEM`, `netCDF`, `NGW`, `PDF`, `PDS`, `SQLite`, `TileDB`, `VRT`,
`GPKG`, `OpenFileGDB`. Each is counted once per index, matching GDAL's own listing.)*

---

## 7. Recommended profile order

Ranked by (showcase value × authoring cost⁻¹), given what is already profiled — TIFF, PNG,
NITF, Shapefile.

1. **SRTMHGT** — 10 lines. The minimal DLV example for documentation.
2. **BT** (VTP Binary Terrain) — fixed header + grid, no compression, no bundle. The clean
   "read the spec, type the struct" tutorial case.
3. **GeoPackage Binary geometry blob** — small, high-value, and unblocks GPKG/SQLite
   metadata work without touching the B-tree.
4. **S-57 / ISO 8211** — the highest-value vector target and a direct reuse of the NITF
   ASCII-record machinery. Also unlocks ADRG, SRP and RPFTOC.
5. **netCDF classic** — compact, fully specified, offset-driven; exercises `@at` and DLV
   together, and is the entry point to the whole climate/ocean stack.
6. **GRIB2** — section framing + bit-packed data; exercises `bits[N]`, code tables and
   `switch` harder than anything currently profiled.
7. **ZIP** — a reusable container profile that half the ✗(d) list depends on.
8. **JPEG** — marker-segment TLV; the reference ◐ example showing `@encoded-with` at the
   right granularity.

Before 4 and 5, resolve §1.1 (ASCII-numeric sizing) — both formats need it.

---

## 8. Sources

- GDAL raster driver index — <https://gdal.org/en/stable/drivers/raster/index.html> (160 entries)
- GDAL vector driver index — <https://gdal.org/en/stable/drivers/vector/index.html> (85 entries)
- [HDL design](../specs/2026-07-26-hdl-format-dsl-design.md) — capability envelope, §6 types and clauses
- [HEL specification](../../../specification/hel/index.html) — function set and coercion rules
- [BDDO](../../../specification/bddo/bddo.ttl) — `DataType` individuals
- [hx-bundle](../../../specification/aspect/bundle/bundle.ttl) — binding kinds and part roles
- [encoding aspect](../../../specification/aspect/encoding/encoding.ttl) — codec/compression registers

Format-structure verdicts are based on the published specification for each format, not on
inspection of GDAL's driver source. Where a format has both an open specification and a
proprietary reference implementation (JPEG 2000, DWG), the verdict follows the specification.
