# Descriptor-driven raster: retiring the hand-written decoders

**Date:** 2026-09-06
**Status:** approved design, implementation started
**Repos touched:** `hexplain.io` (spec), `hexplain-tools` (engine)

## Why

Hexplain's thesis is that a declarative description plus a generic metaengine can read and
write a binary format. The raster path does not honour it. `TiffRasterDecoder.kt` hand-walks
the TIFF header, IFD, 12-byte entries, tag dispatch and the inline-vs-pointer value rule in
`ByteBuffer` code; `RasterDecoder.kt` inlines PNG chunk assembly and Paeth/Sub/Up/Average row
filtering, and dispatches formats on magic bytes in a Kotlin `when`. `tiff-profile.ttl` is not
used by the pixel path at all.

The consequence is that the 611 GDAL pixel-parity comparisons prove the Kotlin is correct.
They prove nothing about the descriptors, which is what the project exists to demonstrate.

This was not a shortcut taken for speed. It is where a previous attempt hit a wall:
`RdfToIrCompiler.rejectUnsupportedLayout` refuses every DLV capability a real raster needs, so
whoever tried the descriptor path found the IR could not carry the layout and wrote Kotlin
instead. The wall is one layer thick.

## What is already in place

The gap is narrower than it appears, because two of the three layers are done.

**The specification already models everything except one case.** DLV defines `chunkSize`,
`chunkSizeFromField`, `chunkOffsetsFromField`, `chunkLengthsFromField`, `chunkOffsetBase`,
`chunkOrder` and `ChunkedLayoutShape` — the `chunkOffsetsFromField` comment literally names
"TIFF TileOffsets, NITF block offsets". It also defines `cellBitWidth`, `cellBitWidthFromField`,
`cellPackingOrder`, `hasConditionalCellDataType` and `hasConditionalDimensionOrder`. `core.ttl`
defines `EncodingStep`, `CodecParameter`, `hasEncodingStep`, `parameterName` and
`parameterValue`, with `"predictor"` given as an example parameter name.

**HDL already has the authoring keywords**: `chunk`, `chunks`, `lengths`, `order`, `row-major`,
`column-major`, `morton`, `hilbert`, `cell-bits`, `packing`, `stride`, `dim`, plus `ascii`,
`anum` and `adec` for text headers. BDDO has `asciiInteger`, `whitespaceSeparated`,
`trimWhitespace`, `DelimitedRecords`, `fieldDelimiter` and `terminator`.

**`DLV.kt` already exposes every property as a Jena constant.**

So the missing pieces are: lowering those properties into the IR, one generic executor that
acts on them, codec-registry parameterisation, the descriptors themselves, and one new
normative term for chunk-per-file arrays.

## The boundary

Settled explicitly, because it determines what "no custom code" means:

- **The descriptor owns** structure, layout, and the *names* of codecs.
- **The engine owns** three generic mechanisms: `Metaparser`, a new `LayoutExecutor`, and codec
  lookup. No format knowledge in Kotlin.
- **Codec algorithms are named primitives.** A descriptor says `@encoded-with menc:LZW`; the
  engine supplies LZW. This is the same boundary Kaitai, DFDL and 010 draw, and BDDO already
  encodes it. Describing a DEFLATE state machine declaratively would require turning HEL into a
  bytecode VM; that is not the goal.

What this rules out is hand-written *structure* parsing, which is the part that actually
defeats the purpose.

## Architecture

```
descriptor.hx ──HdlCompiler──▶ BDDO/DLV Turtle ──ProfileLoader──▶ RdfToIrCompiler ──▶ FormatIR
                                                                                          │
bytes ────────────────────────────────────────────────────────▶ Metaparser ◀──────────────┘
                                                                     │  structs, fields, chunk tables
                                                                     ▼
                                                    LayoutExecutor  ◀── CodecRegistry (named codecs)
                                                       (new, generic over DataLayoutIR)
                                                                     ▼
                                                       MultiDimensionalData / RasterPixels
```

`LayoutExecutor` is the only new component and is deliberately format-agnostic: it reads a
widened `DataLayoutIR` plus parsed field values and materialises cells. TIFF tiles, Zarr chunks
and NITF blocks are one mechanism with different field bindings. It lives in `metacodec` beside
`Metaparser` and `Metawriter` so the writer shares it — which is what makes chunked *write*
nearly free and keeps read/write symmetry intact.

**Deleted from `core/main` at the end of the migration:** `TiffRasterDecoder.kt`,
`ZarrRasterDecoder.kt`, and the `png`/`bmp`/`pnm` bodies plus magic-byte dispatch in
`RasterDecoder.kt`. **Survives:** `TiffLzwCodec.kt`, `PackBitsCodec.kt`, zlib in
`BuiltInCodecs.kt` — the algorithms only.

**Format identification stays out of scope.** The caller names the descriptor. That matches how
Zarr and HDF5 already work, how the SaaS works (a run always names a profile version), and how
the harness will work. A `bddo:FormatSignature` concept deserves its own design once there are
enough descriptors to see the pattern.

## Vocabulary neutrality is a hard constraint

`test_vocab_neutrality` enforces that BDDO, DLV, core and every aspect name no format or
jurisdiction. Nothing in this work may add a format-named term to a normative vocabulary. Where
a format needs something the neutral vocabulary cannot say, the answer is a neutral
generalisation plus profile-side binding — the way TIFF's `SampleFormat` binds to the neutral
`hasConditionalCellDataType`, and `TileOffsets` to `chunkOffsetsFromField`.

The media-encoding register holds itself to the same discipline. Its header states that it
carries "codec and compression identifiers as published by the relevant standards bodies" and
that wire codes belong to the profile's enum. All 26 existing concepts are algorithm names —
`Deflate`, `Zlib`, `LZ4`, `RunLength`, `Delta`, `Shuffle`, `Store`. None is format-scoped.

### Codecs: algorithms plus parameters, never new concepts

| Need | Approach |
|---|---|
| TIFF LZW | **new** `menc:LZW` + `EncodingStep` parameter `earlyChange=1`. The off-by-one variant is a parameter, not an algorithm |
| TIFF PackBits | **new** `menc:PackBits` — a published Apple algorithm used by TIFF, PSD, PICT and RTF |
| TIFF Predictor=2 | **reuse** `menc:Delta` + parameters `axis`, `sampleWidth` |
| PNG row filtering | **new** `menc:AdaptivePredictor` + parameter `sampleWidth`; the per-row selector byte is in-band |
| BMP RLE4/RLE8 | **reuse** `menc:RunLength` + parameter `bitsPerCode` |
| zlib, gzip | `menc:Zlib`, `menc:Gzip` already exist |

Three new register concepts, two reuses, zero format names. The engine's current bare strings
`"tiff-lzw"` and `"tiff-packbits"` are deleted — they are exactly the coupling the gate exists
to prevent, sitting where no gate can see them.

### The one new normative term

Zarr does not fit DLV's chunk model. `chunkOffsetsFromField` takes a repeating Field and
`chunkOffsetBase` defaults to `bddo:streamStart`: the model assumes an offset table inside one
byte stream. Zarr chunks are separate files named `0.0`, `0.1`, `1.0` in a directory.
`abnd:pathPattern` can glob-match them but cannot bind grid position to member name.

Add **`dlv:chunkMemberPattern`** — a template with positional dimension-index placeholders
(`"{0}.{1}"`) resolved against bundle members. It serves any directory-chunked array: Zarr,
tiled map caches, chunk-per-file scientific layouts. Nothing in it names Zarr. It sits beside
`chunkOffsetsFromField` as the second way to locate a chunk: offset table, or member name.

## The IR change

`DimensionIR` gains stride-from-field/expression and chunk extent. `DataLayoutIR` gains cell bit
width, packing order, the two conditional-rule lists, and the chunk-location properties.
`rejectUnsupportedLayout` shrinks to genuinely unimplemented *values* — Morton and Hilbert chunk
orders — rather than properties, and never disappears.

## Per-format requirements

| Format | Layout capability | Codecs | Notes |
|---|---|---|---|
| **PNM** P5/P6 | contiguous, size-from-field, ASCII header | none | needs no IR change; proves the lane |
| **BMP** | `cellBitWidth`, `cellPackingOrder`, `dimensionStrideFromExpression`, bottom-up rows | `RunLength` | 3 properties |
| **TIFF** stripped | `chunkOffsetsFromField`, `chunkLengthsFromField`, `hasConditionalCellDataType`, `cellBitWidthFromField`, `hasConditionalDimensionOrder` | Zlib, LZW, PackBits, Delta | strips are chunks spanning full width |
| **TIFF** tiled | + `chunkSize`/`chunkSizeFromField`, `chunkOrder` | same | |
| **PNG** | contiguous | Zlib, AdaptivePredictor | concatenating repeated IDAT payloads into one decode stream needs a probe — possible BDDO gap |
| **Zarr** | `chunkMemberPattern`, JSON metadata, directory bundle | Zlib, Gzip | carries the spec addition |

**HDF5 is out of milestone 1.** Its 81-line adapter wraps jHDF; replacing it means describing
the superblock, object headers, B-tree v1 chunk index, heaps and filter pipeline from scratch —
a separate project. Until then the jHDF adapter is labelled a third-party bridge and dropped
from any Hexplain coverage claim. That costs 12 of 611 comparisons.

## Verification

**Three-way harness.** `compare.py` gains a descriptor lane: GDAL oracle, legacy Kotlin,
descriptor. Descriptor-vs-GDAL is the result that matters; Kotlin-vs-GDAL is the incumbent
baseline.

**The deletion gate is machine-checked.** A Kotlin decoder may be deleted only when, on every
fixture where Kotlin equalled GDAL, the descriptor also equals GDAL. A gate fails the build if a
decoder is removed while any fixture regresses. Nobody gets to decide "close enough".

**Rejections must survive with their reasons.** The 11 retained GTiff rejections are pinned in
`expected-deviations.json` with specific messages. A descriptor that rejects those files with a
generic "constraint failed" is a diagnostic regression even though the outcome matches. Each
descriptor carries named HEL post-parse constraints routed through `ParseDiagnosticBridge`, and
the gate compares reason strings. `int24.tif` must still produce `Int32` against GDAL's
`UInt32`, pinned by input SHA-256.

**Writer symmetry is new evidence.** The Kotlin decoders were read-only, so nothing ever proved
a description bidirectional. Because `LayoutExecutor` is shared with `Metawriter`, every
descriptor gets a round-trip test: parse → write → byte-identical where the format is canonical,
GDAL-readable otherwise. The current architecture cannot produce this evidence at all.

**Error handling — fail loudly, four rules.**

- `rejectUnsupportedLayout` shrinks but never disappears; Morton and Hilbert stay rejected.
- An unknown `codecParameter` name is an error, never silently ignored. Silent parameter drop is
  how you get plausible-looking wrong pixels.
- `LayoutExecutor` bounds chunk-count × chunk-extent with checked arithmetic before allocating,
  charges the existing decoded-byte budget, and handles partial edge and absent chunks
  explicitly rather than by zero-fill default.
- Descriptor compile failures keep the resolver's span-and-suggestion diagnostics.

## Sequencing

1. **PNM** — no IR change; proves the descriptor lane, the harness and the deletion mechanic end to end at zero risk.
2. **BMP** — bit packing and stride.
3. **TIFF stripped** — the chunk executor against vocabulary that already exists.
4. **TIFF tiled** — chunk extents and order.
5. **PNG** — the two codecs, plus the IDAT concatenation probe.
6. **Zarr** — last, carrying `dlv:chunkMemberPattern`.

Existing regression cover — the 36 instance contracts and the PNG/TIFF/Shapefile round trips —
stays green throughout, since `DataLayoutIR` is load-bearing for profiles already in use.
`dlv:chunkMemberPattern` is a normative addition and must clear `test_vocab_neutrality`,
`test_shapes`, `test_term_reference` and `test_html_sync` in the same change.

## Out of scope

Format identification; HDF5; vector formats; CRS and georeferencing semantics; the remaining 240
GDAL driver pages. Breadth comes after the thesis is proven on six formats with evidence that
already exists.
