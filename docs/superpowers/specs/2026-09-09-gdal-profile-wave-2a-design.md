# GDAL profile wave 2a: numbers written as text, at grid scale

**Date:** 2026-09-09
**Status:** designed
**Repos touched:** `hexplain-tools` (two engine changes, parity tests), `hexplain-profiles` (five profiles), `hexplain.io` (coverage inventory)
**Predecessor:** `2026-09-09-gdal-profile-wave-design.md` (wave 1)

## Why

Wave 1 added ten profiles, and the engine work that followed made text numbers, packed
sub-byte cells, dynamic strides and conditional layouts executable. But the text-number fix
reached only two places: a fixed-width field inside a byte struct, and a column of a delimited
table. It never reached a raster.

That leaves a family of GDAL drivers describable in principle and undescribable in practice —
the ones that write an entire grid as whitespace-separated ASCII. `MultiDimensionalData.cellBits`
requires 1..64 bits per cell, and a number written as text is *defined* by having no bit width,
so an ASCII grid cannot be a `dlv:DataLayout` today. AAIGrid alone has 19 GDAL-decoded samples
in the cached corpus, and the profile library says nothing about any of them.

This wave closes that gap with the smallest change that is honest about how these formats are
actually read, and spends it on five profiles that exercise it on real files.

## What this wave is deliberately not

**It is not a new grid model.** The tempting design — a text-grid container, or a text cell type
in DLV — fails on the evidence. Within AAIGrid's own corpus:

| Sample | Dialect |
|---|---|
| `float64.asc` | 4-space indent, single-space separators, LF |
| `nodata_int.asc` | columns padded to width 7, LF |
| `case_sensitive.ASC` | one value per line, CRLF, scientific notation |

A profile declaring a canonical separator would parse all three and round-trip none. GSAG is
worse: ten values per line, a blank line between rows, CRLF — so "one row per line" is false
there too. `bddo:fieldDelimiter`/`recordDelimiter` do not rescue it for the same reason.

These formats are not grids-of-cells at the byte level. They are **token streams that a reader
consumes sequentially and reshapes**, which is exactly what GDAL itself does. The description
should say that, not pretend to a 2-D addressability the bytes do not have.

So `MultiDimensionalData` is not touched. Its "checked, byte-addressable view" invariant is
what makes packed cells sound, and bending it to admit variable-width tokens would put that at
risk to buy an abstraction these formats do not have.

## The two engine changes

### E1 — separated elements for a repeated text-number field

`Metaparser` already reads a repeated field by looping a sequential element read
(`repeat(repeatCount)`, Metaparser.kt:1031-1035), and an element's extent already comes from
either a fixed size or a terminator. E1 adds a third extent rule, available only to a text
number:

> **A separator is a run, a terminator is a sequence.** A separated element skips any leading
> separator bytes, takes the token that follows, then consumes the trailing run. A terminated
> element still reads to one fixed byte sequence and stops.

Conflating the two is what would break CSV, where an empty field between two delimiters is
meaningful. It is kept as a distinct concept for that reason.

The grid shape stays metadata, as it already is in `dted.hx`: `ncols`/`nrows` carry
`means araster:width` / `araster:height`, and the raster is one field of `ncols * nrows`
elements. A consumer reshapes row-major. The profiles say so in their limits block.

**Round-trip.** Each cell parses to a Number *and* retains its raw token; the separator run that
followed it is retained too. `Metawriter` emits the retained token and run when present, and
formats from the number when not. This is not a new mechanism — it is the rule text numbers
already follow, recorded in the wave-1 notes as "the writer zero-pads from a number, or writes
a String verbatim for an exact round trip of a space-padded dialect." All three AAIGrid
dialects then round-trip byte-for-byte with none of them privileged, and a profile can still
write a grid it did not parse.

**Blast radius:** `Metaparser` (element extent), `Metawriter` (emit retained token and run), one
BDDO term, and its SHACL shape. Not `MultiDimensionalData`, not the IR layout model.

### E2 — Fortran `D` exponents in an ASCII decimal

USGSDEM record A writes doubles as `0.000000000000000D+000` and `6.070921250000000D+005`, and packs them without separators:
`3.00000D+0013.00000D+0011.00000D+000` is three 12-character fields. `textNumber` parses
decimals with `toDoubleOrNull()` (Metaparser.kt:1514; the delimited-table coercion at Metaparser.kt:398 takes the same change), which rejects a `D` exponent, so record A
is unreadable without this.

E2 accepts `D` or `d` as an exponent marker in a `bddo:asciiDecimal`, equivalent to `E`. It is
universal rather than opt-in: a field *declared* a decimal that holds `3.00000D+001` has no
other valid reading, and the alternative — a new vocabulary term for a numeric dialect — buys
nothing but a term. `bddo:numericBase` remains rejected on a decimal, unchanged.

E2 is smaller than E1 and independent of it. It ships first, as its own commit.

## The five profiles

Every one has at least one GDAL-decoded sample in `tests/gdal/results/oracle.jsonl`.

| Profile | GDAL driver | Shape | Decoded samples | Engine changes used |
|---|---|---|---|---|
| `aaigrid` | `raster:aaigrid` | six `keyword value` header lines, then a token grid | 19 | E1 |
| `usgsdem` | `raster:usgsdem` | 1024-byte ASCII record A, then one record per profile | 8 | E1, E2 |
| `gsag` | `raster:gsag` | `DSAA` magic, four header lines, then a token grid | 1 | E1 |
| `grassasciigrid` | `raster:grassasciigrid` | six `key: value` header lines, then a token grid | 1 | E1 |
| `isg` | `raster:isg` | free-text preamble, `begin_of_head`/`end_of_head` block, then a token grid | 1 of 5 | E1 |

### `aaigrid`

`ncols`, `nrows`, `xllcorner`/`xllcenter`, `yllcorner`/`yllcenter`, `cellsize`, and an optional
`nodata_value` — each a keyword and a value separated by whitespace, one per line. The corner
and centre spellings are alternative georeferencing conventions, described as an `if`-guarded
pair. `nodata_value` is `present`-guarded. The body is
`cells : adec repeat [ncols * nrows] separated`.

`means`: `araster:width`, `araster:height`, `asref:scaleX`, `asref:scaleY`, and the nodata value
as `araster:noDataValue`.

This profile carries the wave. Its 19 samples span the three dialects and both integer and
double bodies, so it is the format E1 is developed against.

### `usgsdem`

Record A is 1024 bytes of fixed-width ASCII: a 144-character quadrangle name, a 6-character DEM
level code, counts, then fifteen `D`-exponent doubles for the polynomial coefficients, four
corner coordinate pairs, min/max elevation, and the row/column counts. Fields are `anum`/`adec`
at declared widths — the same form `dted.hx` uses, extended by E2.

Each following record is a profile: a fixed header (row/column index, the profile's element
count, its start coordinate as `D`-exponent doubles, its local datum elevation) then that many
elevations as separated tokens. The corpus's two dialect-edge samples are the reason the body is
tokenized rather than sliced at width 6: `usgsdem_with_extra_values_at_end_of_profile.dem` has
values a fixed-width reading would mis-attribute, and `usgsdem_with_spaces_after_byte_864.dem`
pads record A with spaces where a strict reading expects fields.

**Stated limit:** every corpus sample is truncated, so the profile is verified on the records
present rather than on a complete DEM.

### `gsag`

`DSAA` magic, then `nx ny`, `xlo xhi`, `ylo yhi`, `zlo zhi` — four lines of two tokens each —
then the grid. Its dialect is the hard one: ten values per line, a trailing space before each
CRLF, and a blank line between rows. E1's retained separator runs are what make it round-trip;
no declarative separator description would.

### `grassasciigrid`

`north:`, `south:`, `east:`, `west:`, `rows:`, `cols:` — a `key: value` header, then the grid.
The simplest consumer of E1, included because it costs one file and proves the mechanism is not
shaped around AAIGrid's particular header.

### `isg`

A variable-length free-text preamble read to the `begin_of_head` marker (an existing terminator
read), then a header block whose lines use `:` for text values and `=` for numbers, ending at
`end_of_head`. The body is separated tokens.

**Stated limit:** ISG 2.0 permits a sparse body and a binary body; the profile describes the
1.0 dense text body its decoded sample uses, and names the other two. Four of the five samples
are `oracle-rejected`, so verification rests on `test.isg`.

## Verification

Five parity tests in `hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/`, following the
`BmpParityTest` pattern: compile the `.hx` in-process, lower it with `RdfToIrCompiler`, parse the
corpus sample with `Metaparser`, pack the parsed cells band-sequentially in the data type GDAL
reports, and compare SHA-256 against `oracle.jsonl`. Width, height and band count are asserted
against the oracle's own figures first, so a digest mismatch cannot be explained away as a
reshape.

Every profile is additionally held to `write(parse(f)) == f` via `ProfileFixtures.writeBack`.
For the five separated-text profiles that round-trip *is* the test of E1 — it is the only thing
that proves the retained tokens and separator runs are faithful rather than merely plausible.

E1 and E2 each also get unit tests in `core` beside the existing text-number ones, so the engine
change is verified independently of any profile.

Every test opens with `assumeTrue(Files.exists(...))` on the corpus, so a checkout without
`tests/gdal/cache` skips rather than fails.

## Coverage inventory

Five `profiles` entries added to `specification/coverage/gdal-drivers.json`, taking linked driver
rows from 17 to 22. No schema change and no renderer change: the `profiles` list, the Profiles
column and the `test_gdal_inventory.py` schema check all landed in wave 1.

**Recorded gap, not closed here:** the wave-1 design stated that `raster:gtiff` and `raster:png`
would gain `profiles` entries. Neither did, because TIFF and PNG have parity tests in
`hexplain-tools` but no `.hx` in the profile library, so there is nothing to link. This is noted
so the omission is explained rather than silently carried forward.

## Sequencing

1. **E2** alone, with its unit tests. Independent of everything else.
2. **E1**, developed against `aaigrid` only, with its unit tests and `AaiGridParityTest` over all
   19 samples in all three dialects. Nothing else proceeds until the round-trip holds.
3. `usgsdem`, which is the only profile needing both changes and the only one whose body is not
   a plain token grid.
4. `gsag`, `grassasciigrid`, `isg` — independent of each other once E1 is settled.
5. Coverage inventory and the regenerated page.
6. Full gate runs in all three repos; profile headers finalised with their test names.

## Risks

- **A dialect the retained-token scheme cannot reproduce.** Mitigated by developing E1 against
  the 19-sample AAIGrid set, which spans the widest dialect variation in the corpus, before any
  other profile depends on it. If a sample cannot round-trip, the profile states which and why
  rather than the test being relaxed.
- **Separator semantics leaking into terminated reads.** E1 is a distinct extent rule with its
  own code path; `readUntilTerminator` is not modified. The existing delimited-table tests are
  the regression guard, and are run before E1 is committed.
- **`usgsdem` verified only on truncated files.** Unavoidable — the corpus holds no complete
  DEM. Stated in the profile header rather than left implicit.
- **`isg` resting on one decoded sample.** Accepted; the other four are `oracle-rejected` for
  georeferencing reasons unrelated to the byte layout, so they are still parsed and round-tripped
  even though their pixels are not compared.
- **Scope creep from E2.** It is required by `usgsdem` and by nothing else in the wave. If it
  proves larger than one commit, `usgsdem` moves to wave 2b and the wave ships four profiles.

## Out of scope, and why

- **`xyz`** — no samples in the cached corpus.
- **`fast`** (6 samples) and **`l1b`** (1) — GDAL decoded none of them, so neither could ship
  parse-verified. Dropping `l1b` leaves 10-bit-packed-with-padding unproven on real data; wave
  2b's `rmf` covers packing at 1 and 4 bits on 15 decoded samples instead.
- **`gif`** — 2 decoded samples, but the body is LZW, so GDAL's digest is decoded output this
  engine will never reproduce. It would have been the wave's only header-only profile.
- **`gxf`** — dropped during spec review, on the samples rather than on principle. Of its two
  decoded samples only `small.gxf` (4×3) is a plain token grid; `small2.gxf` sets `#GTYPE 3`,
  GXF's compressed grid encoding. Worse, `small.gxf` writes `#POIN` where `small2.gxf` writes
  `#POINTS`: GXF permits abbreviating a keyword to any unique prefix, and a keyed dispatch table
  matches exact strings. Describing GXF honestly therefore needs prefix dispatch, and what it
  would buy is one verified 4×3 grid.
- **`rmf`, `gsbg`, `gs7bg`, `nsidcbin`** — deferred to wave 2b. They need no engine change and
  share no code with this wave, so they can proceed in parallel under their own design.
- **A 2-D addressable ASCII grid.** Argued above: the bytes do not support it, and claiming it
  would misdescribe the format.

