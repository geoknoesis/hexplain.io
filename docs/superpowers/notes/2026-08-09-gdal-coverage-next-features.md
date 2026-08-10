# What Would Raise GDAL Coverage Further

**Date:** 2026-08-09 · **Status:** Roadmap input
**Input:** [2026-08-01-gdal-hdl-coverage.md](2026-08-01-gdal-hdl-coverage.md) §2.1 (re-tally)

Coverage stands at **97 of 245 drivers fully expressible (40%), 168 (69%) to some useful
degree**. This note asks what is left and what would move it, working from the drivers still
blocked rather than from a wishlist of vocabulary.

---

## 1. The ceiling

Of the 245 drivers, **49 are structurally unreachable**: they own no byte stream, or a closed
one — 18 network services, 11 RDBMS connections, 13 in-memory/virtual/meta drivers, 2 object
stores, 5 SDK-only proprietary formats. No vocabulary change touches any of them.

**The real denominator is 196.** At 97 full, HDL covers about half of what is reachable at all.

The remaining 99 reachable-but-not-full drivers partition exactly — each counted once, with
the per-tier subtotals adding back to ◐ 49, ◑ 22 and ✗(d) 28:

| Blocked by | Drivers | from ◐ | from ◑ | from ✗(d) |
|---|---:|---:|---:|---:|
| Entropy coding / transforms (decode, not describe) | **34** | 34 | | |
| XML labels and XML-grammar formats | **25** | | 10 | 15 |
| Nested or sectioned text labels | **9** | | 7 | 2 |
| Self-describing (data-driven) record schemas | **8** | 8 | | |
| Keyed container traversal (SQLite B-tree) | **7** | 7 | | |
| JSON labels and JSON-grammar formats | **6** | | 1 | 5 |
| Directory-structured databases | **4** | | 4 | |
| Bespoke line grammars (one-off tokenizers) | **6** | | | 6 |
| | **99** | **49** | **22** | **28** |

The largest bucket is out of scope on purpose: **HDL describes, it does not execute.**
Entropy coding stays identified by `@encoded-with` and never decoded. Setting it and the
bespoke grammars aside, the addressable remainder is **59 drivers**, which would take full
coverage to **156 of 196**.

---

## 2. Features, ranked by drivers unlocked

### F1 — XML element addressing · 25 drivers · the largest remaining unlock

The direct analogue of what `bddo:DelimitedRecords` did for `key = value`. A vocabulary for
addressing an element or attribute by path, and binding it to a field, so an XML label can
supply the parameters a binary payload needs.

Unlocks (◑ → ✅): `PDS4`, `DIMAP`, `SAFE`, `SENTINEL2`, `RS2`, `TSX`, `RCM`, `CPHD`, `E57`,
`TIL` — every one is an XML manifest over a payload that is *already* describable.
Unlocks (✗ → ✅/◐): `ECRGTOC`, `KMLSuperoverlay`, `GML`, `GMLAS`, `KML`, `LIBKML`, `GPX`,
`GeoRSS`, `JML`, `MapML`, `NAS`, `LVBAG`, `XODR`, and the two ZIP-of-XML office
formats `ODS` and `XLSX` (the ZIP container is already expressible; only the members are not).

The precedent is encouraging: the ten ◑ entries need only enough XML to *read parameters*,
which is a far smaller surface than describing XML in general. The fifteen ✗ entries are
XML all the way down and are the harder half.

**Watch for:** the same non-recursion trap as F3. An XML surface that cannot express nesting
would unlock the manifests and none of the grammars.

### F2 — JSON element addressing · 6 drivers

Distinct grammar from XML, same shape of problem, much smaller. `Zarr` (◑ — its
`.zarray`/`.zattrs` are the only thing keeping it there, since chunked layout and encoding
pipelines already cover its chunk store), plus `ESRIJSON`, `GeoJSON`, `GeoJSONSeq`, `JSONFG`,
`TopoJSON`.

Worth designing alongside F1 rather than after it: both are "address a node in a tree and
bind it to a field", and two unrelated designs for that would be a mistake.

### F3 — Nested delimited records · 9 drivers · cheapest per driver

`bddo:DelimitedRecords` is deliberately non-recursive. Lifting that — a record that may
contain records, with an explicit open/close delimiter pair — unlocks the label formats that
are otherwise exactly the `key = value` case already solved.

Unlocks (◑ → ✅): `PDS` (raster and vector), `ISIS2`, `ISIS3`, `VICAR` — all PVL/ODL
`OBJECT = … END_OBJECT`; `ERS` (ERMapper `Begin`/`End` blocks); `MiraMonRaster` (sectioned
INI). Possibly `GXF` and `VDV` from ✗.

**Highest leverage per unit of work.** The vocabulary, the parser surface and the emitter all
exist; this is a constraint to relax and a nesting rule to specify, not a new subsystem. It
should probably go first even though F1 unlocks more, because it also settles how nesting is
spelled before F1/F2 have to answer the same question.

### F4 — Self-describing record schemas · 8 drivers · architecturally the hardest

Formats whose record layout is defined by a dictionary *inside the file*: `HFA` (Erdas `.img`
dictionary string), `Arrow` and `FlatGeobuf` (flatbuffer vtables), `Parquet` (Thrift
metadata), `MVT` (protobuf field ordering), and arguably `CAD`/`DWG`/`PGeo`.

These are all ◐ → ✅ moves: framing is already describable, per-record layout is not.

**This one challenges a design boundary rather than just needing work.** Everything HDL says
today is fixed at authoring time. A schema read from the file is a description that does not
exist until the file is open. That may be expressible as a level of indirection — a struct
whose field list comes from a parsed value — or it may be the point where description honestly
ends. Worth a design note before any implementation.

### F5 — Keyed container traversal · 7 drivers · same boundary question

`GPKG` (raster and vector), `MBTiles`, `SQLite`/`Spatialite`, `Rasterlite`,
`OpenFileGDB` (raster), `PGeo`. SQLite's page format is fully documented and already
describable; reaching a *row* needs B-tree traversal, which is an algorithm.

The survey's own note is the right framing: "describe the file header + page framing; treat
rows as opaque." Moving these to ✅ means HDL can express a search, which is a bigger
commitment than any vocabulary here. **Note the shared payoff:** F5 plus F1 would make the
whole OGC GeoPackage stack fully expressible, which is disproportionate showcase value for
seven drivers.

### F6 — Directory-tree assets · 4 drivers

`GRASS` (raster and vector), `MFF2`, `MiraMonVector`. hx-bundle already has `pathPattern`,
part alternatives and `nestedProfile`; what is missing is hierarchy — a part that is itself a
directory with its own internal structure.

Small, self-contained, and the vocabulary is nearly there.

### F7 — Bespoke line grammars · 6 drivers · probably not worth it

`AVCE00`, `SOSI`, `EDIGEO`, `VFK`, `INTERLIS 1`/`2`, `PGDump` (SQL text). Each is a one-off grammar
with its own record typing. A general surface for these is close to "embed a parser
generator", and the payoff is six drivers nobody has asked for. **Recommend leaving at ✗**
and revisiting only if one is specifically needed.

---

## 3. Suggested order

1. **F3 (nested records)** — cheapest, and it settles the nesting question F1 and F2 both need.
2. **F1 + F2 (XML/JSON addressing)** — largest unlock; design as one "address a node, bind a
   field" mechanism with two grammars.
3. **F6 (directory assets)** — small, isolated, finishes hx-bundle.
4. **F4 / F5** — only after a design note on whether HDL is willing to describe indirection
   and search. These are the two that push on "describe, don't execute", and deciding that
   deliberately is worth more than the 15 drivers.

Doing 1–3 takes full coverage from **97 to 141 of 196**. Adding step 4 reaches **156**. The
residue is then 34 entropy-coded ◐ drivers and 6 bespoke grammars — 40 drivers that are out of
scope by design rather than by omission.

---

## 4. A correction to the source survey

While bucketing the ✗ list I found a bookkeeping error in
[the original survey](2026-08-01-gdal-hdl-coverage.md). Reason code **(d)** names **31**
vector drivers, but its count says 30, and the vector totals require 30 (57 out-of-scope
minus 27 across codes a/b/c/e/f). The extra name is `INTERLIS 1`/`2`, written as one slashed
line but naming two GDAL drivers.

Left uncorrected rather than silently adjusted: fixing it means either ✗ becomes 90 and the
grand total 246, or GDAL's vector index is 86 rather than 85 — and I cannot check GDAL's
index from here. It is a ±1 discrepancy that changes no conclusion in either document, but it
should not be discovered a third time without a note.
