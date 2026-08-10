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

### F1 — XML element addressing · 25 drivers · ✅ DONE

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

**Shipped 2026-08-10, together with F2 as one mechanism.** `bddo:TreeDocument` addresses nodes
in the tree a conforming parser produces — it does NOT describe the syntax of these documents,
which is what keeps it from becoming an XML specification. One `bddo:nodePath` property, read
according to `bddo:treeSyntax`: an abbreviated XPath (child, attribute and positional steps
only) for `bddo:xml`, and RFC 6901 JSON Pointers for `bddo:json`. Both adopted rather than
invented; the two index conventions (1-based predicates, 0-based pointers) are kept as their
standards define them rather than normalised, which would surprise everyone who knows either.

`bddo:hasNamespaceBinding` is the part that decides whether this works at all in practice: PDS4,
DIMAP and SAFE are namespaced, and an unprefixed path against a namespaced document matches
nothing rather than failing. An empty prefix binds the default namespace, which an abbreviated
XPath cannot otherwise reach. A binding on a JSON document is rejected rather than ignored,
because it signals a misunderstanding of what the paths will match.

HDL gains a `document` container with `@xml`/`@json` and `@ns`. The field syntax is unchanged
across all three container forms — a quoted name is a key, a key path or a node path according
to the container, never according to the field.

### F2 — JSON element addressing · 6 drivers · ✅ DONE

Distinct grammar from XML, same shape of problem, much smaller. `Zarr` (◑ — its
`.zarray`/`.zattrs` are the only thing keeping it there, since chunked layout and encoding
pipelines already cover its chunk store), plus `ESRIJSON`, `GeoJSON`, `GeoJSONSeq`, `JSONFG`,
`TopoJSON`.

Worth designing alongside F1 rather than after it: both are "address a node in a tree and
bind it to a field", and two unrelated designs for that would be a mistake.

### F3 — Nested delimited records · 9 drivers · ✅ DONE (7 of 9)

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

**Shipped 2026-08-10.** `bddo:RecordGrouping` with three styles — `keyedGroup` (PVL/ODL
`OBJECT = … END_OBJECT`), `valuedGroup` (ERMapper `Name Begin … Name End`) and `sectionHeaded`
(INI brackets) — plus `bddo:keyPath` / `bddo:pathSeparator` for addressing into the nesting, an
HDL `@group` surface, and SHACL rejecting a half-declared grouping or a path in a flat
container. Three styles rather than one grammar because each is fully described by two tokens
plus where the group's name comes from; a general nested-grammar surface would be a parser
generator.

Reaches **7 of the 9**: PDS (raster and vector), ISIS2, ISIS3, VICAR on `keyedGroup`; ERS on
`valuedGroup`; MiraMonRaster on `sectionHeaded`. `GXF` and `VDV` stay at ✗ — they are sectioned
too, but with TYPED record kinds per section, which is a grammar rather than a nesting rule and
belongs with F7.

**Coverage: 97 → 104 of 196 reachable.**

### F4 — Self-describing record schemas · 8 drivers · ◐ PARTLY DONE (3 of 8)

Formats whose record layout is defined by a dictionary *inside the file*: `HFA` (Erdas `.img`
dictionary string), `Arrow` and `FlatGeobuf` (flatbuffer vtables), `Parquet` (Thrift
metadata), `MVT` (protobuf field ordering), and arguably `CAD`/`DWG`/`PGeo`.

These are all ◐ → ✅ moves: framing is already describable, per-record layout is not.

**Shipped 2026-08-10: the 3 drivers that were not the hard part.** The
[design note](2026-08-10-f4-f5-design-note.md) split this bucket into three problems. Dynamic
offsets with a static field set (Arrow, FlatGeobuf) turned out to be expressible already —
HEL's array subscript inside `bddo:atOffsetFromExpression` reads a flatbuffer vtable as
written. Protobuf skip-unknown (MVT) needed one HDL change and no vocabulary: `switch` in the
TYPE position, so the dispatched struct determines the extent, which BDDO always permitted.

The remaining 5 — HFA, Parquet, CAD, DWG, PGeo — are the schema-in-the-file case, and are the
part that genuinely challenges the boundary. **Coverage: 139 → 142.**

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

### F6 — Directory-tree assets · 4 drivers · ✅ DONE (2 new, 2 already reachable)

`GRASS` (raster and vector), `MFF2`, `MiraMonVector`. hx-bundle already has `pathPattern`,
part alternatives and `nestedProfile`; what is missing is hierarchy — a part that is itself a
directory with its own internal structure.

Small, self-contained, and the vocabulary is nearly there.

**Shipped 2026-08-10 — and the diagnosis above was wrong in an instructive way.** hx-bundle was
not missing hierarchy: `abnd:nestedProfile` has meant "a member that is itself a structured
directory" since P0. What was missing is that **HDL exposed none of it.** The DSL could say
`part ".shp"` and nothing else — no `pathPattern`, no `minParts`/`maxParts`, no
`nestedProfile` — so every directory-structured product was unauthorable no matter what the
vocabulary said.

`part pattern "<glob>" … min N max N nested <Bundle>` closes it, with the compiler rejecting a
part with no locator, bounds without a pattern, a max below its min, and a nested profile the
document does not declare.

**All four are now reached.** `GRASS` ×2 by the pattern-and-nesting surface itself; `MFF2` by
`nestedProfile`, which covered it in vocabulary but which nothing could author until HDL
exposed it; `MiraMonVector` by F3's `sectionHeaded`, its `.rel` being INI. The last two needed
no new vocabulary — only for the DSL to reach what already existed.

**Coverage: 135 → 139 of 196 reachable.**

> **Correction.** This section first claimed only two of the four, reasoning that counting
> `MFF2` and `MiraMonVector` would double-count F3 and `nestedProfile`. That was wrong: neither
> had been counted anywhere, so excluding them dropped two real drivers rather than avoiding a
> double count. Caught by reconciling the running total against the §1 partition — which left
> exactly four drivers unaccounted, these two plus `GXF` and `VDV`, and the latter two genuinely
> are not reached. A running total that is never reconciled against its partition drifts
> silently, in whichever direction the last judgment call leaned; this one leaned conservative,
> which is the more comfortable error and still an error.

The interesting part is why this went unnoticed for so long. `VocabCoverageTest` — added
precisely to stop the DSL falling behind the specification — checked bddo, dlv and core, and
not hx-bundle. Every other aspect is reached generically (`means araster:width`,
`carries ageom:`), so no per-term surface is needed; hx-bundle is the exception, because
`bundle`/`asset`/`part` are dedicated syntax and a term with no clause is a term no description
can state. The gate is now widened, and verified to catch exactly what it had missed.

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

Doing 1–3 takes full coverage from **97 to 141 of 196**. Steps 1–3 are done, plus F4's cheap half: **142**. Adding step 4 reaches **156**. The
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
