# Design — Hexplain Profile: NGA NITF 2.1 (MIL-STD-2500C)

**Status:** approved design, pending spec review
**Date:** 2026-07-26
**Author:** Stephane Fellah / Geoknoesis LLC
**Source of truth:** MIL-STD-2500C, 01 May 2006 (NITF 2.1). NSIF/STANAG 4545 is field-compatible.

## 1. Goal & scope decisions (locked)

Produce a **byte-level Hexplain description of the NGA NITF 2.1 container** — the file
format itself — as a set of BDDO `Struct`/`Field` definitions, mirroring the
`specification/profiles/shapefile/` convention (TTL-only, no HTML page).

Locked scope decisions:

- **Coverage:** *Full container skeleton* — file header + all five segment subheaders
  (image, graphic, text, DES, RES) + a generic TRE framework. Subheaders described at
  field level; specific TREs limited to two worked modules.
- **Semantic depth:** *Lift what exists + log gaps* — `mapsToProperty`/`mapsToClass`
  for the handful of fields with a target in today's vocabularies (width, height,
  classification level, RasterDataset), everything else physical-only with a documented
  `SEMANTIC GAP LOG` backlog.
- **File structure:** *Modular (Structure A)* — container core in one file, one file per
  worked TRE. Embodies the "describe a custom TRE by adding one declarative file, no code"
  narrative.
- **Worked TREs:** **BLOCKA** (image block + corner lat/lon) and **RPC00B** (rational
  polynomial sensor model).

Explicit non-goals (YAGNI): no HTML spec page; no new SHACL shapes (reuse BDDO + core
shapes); no vocabulary extensions; exactly two TREs; one valid + one invalid example;
image *data* (pixel arrays), CLEVEL tables, blocked-image mask tables, and the
STREAMING_FILE_HEADER DES body are out of scope for cut #1 (described structurally only
where the container references them).

## 2. Framework primitives used

From `bddo` (physical) and `hexplain` core (mapping); no changes to either.

- `bddo:Struct` + `bddo:hasField` (ordered `rdf:List` of `bddo:Field`), `bddo:endianness`.
- Field sizing: `bddo:size`, `bddo:sizeFromField`, `bddo:trimNull`, `bddo:encoding`.
- Conditional presence: `bddo:isPresentIf` (string expr over prior fields).
- Repetition: `bddo:repeatCount`, `bddo:repeatCountFromField`, `bddo:repeatUntil`.
- Conditional data type: `bddo:hasConditionalDataType` → `bddo:DataTypeRule`.
- Enumerations: `bddo:enumeration` → `bddo:Enumeration`/`bddo:EnumValue`.
- Mapping: `hexplain:mapsToClass` (Struct→owl:Class), `hexplain:mapsToProperty`
  (Field→property), `hexplain:valueExpression` (HEL scaling).

## 3. File layout

```
specification/profiles/nitf/
  nitf.ttl              # ontology header + file header + 5 subheaders + generic TRE framework
  nitf-tre-blocka.ttl   # BLOCKA TRE Struct  (owl:imports nitf.ttl)
  nitf-tre-rpc00b.ttl   # RPC00B TRE Struct  (owl:imports nitf.ttl)
  example.ttl           # one valid worked instance graph
  example-invalid.ttl   # one deliberately SHACL-failing instance
```

- Namespace `https://hexplain.io/ns/profile/nitf#` (prefix `nitf:`), `owl:versionIRI …/1.0`.
- `owl:imports <https://hexplain.io/ns/core>` (transitively pulls bddo + dlv).
- Ontology metadata mirrors the Shapefile profile (dcterms, vann, CC-BY-4.0),
  `rdfs:seeAlso` MIL-STD-2500C, note of NSIF/STANAG 4545 equivalence.

## 4. Data types (profile-local `bddo:DataType`s)

NITF header/subheader fields are text (§5.1.7). Define profile-local types rather than
reuse the binary `bddo:uint*`:

- `nitf:BCSA`  → base string, encoding ascii, right-padded with BCS space `0x20`, `trimNull` off.
- `nitf:BCSN`  → base string, encoding ascii (numeric text: digits, `+ - . /`), used for BCS-N.
- `nitf:BCSNpos` → BCS-N positive integer (digits only), used for counts/lengths.
- `nitf:ECSA`  → ECS-A alphanumeric (restricted to BCS-A subset per §3.2.29 guidance).

`FBKGC` (file background colour, 3 bytes RGB) is the one genuinely binary field →
`bddo:bytes`, `bddo:size 3`. (Value range 0x00–0xFF per component, Table A‑1.)

Note: BCS-N fields carry numeric text (e.g. `NROWS` = the 8 characters `"00001024"`), not
a binary integer. Where a mapped semantic value must be numeric, use
`hexplain:valueExpression` to coerce the parsed string to xsd:integer.

## 5. Container model — `nitf.ttl`

Six top-level big-endian `bddo:Struct`s. Field order, sizes, and conditional rules are
transcribed **verbatim from the MIL-STD-2500C Appendix A tables** cited below. Every
field carries `bddo:size` (fixed) from the table's SIZE column.

### 5.1 `nitf:FileHeader` — Table A‑1

Fixed prefix: `FHDR`(4,="NITF") `FVER`(5,="02.10") `CLEVEL`(2) `STYPE`(4,="BF01")
`OSTAID`(10) `FDT`(14) `FTITLE`(80).

**File security block** (16 fields): `FSCLAS`(1) `FSCLSY`(2) `FSCODE`(11) `FSCTLH`(2)
`FSREL`(20) `FSDCTP`(2) `FSDCDT`(8) `FSDCXM`(4) `FSDG`(1) `FSDGDT`(8) `FSCLTX`(43)
`FSCATP`(1) `FSCAUT`(40) `FSCRSN`(1) `FSSRDT`(8) `FSCTLN`(15).

Then `FSCOP`(5) `FSCPYS`(5) `ENCRYP`(1) `FBKGC`(3, binary) `ONAME`(24) `OPHONE`(18)
`FL`(12) `HL`(6).

**Segment-length tables** — the repeating arrays:

| Count field | repeats a nested `Struct` of |
|---|---|
| `NUMI`(3)   | `{ LISHn(6), LIn(10) }` |
| `NUMS`(3)   | `{ LSSHn(4), LSn(6) }` |
| `NUMX`(3)   | *(reserved, always "000"; no repeat)* |
| `NUMT`(3)   | `{ LTSHn(4), LTn(5) }` |
| `NUMDES`(3) | `{ LDSHn(4), LDn(9) }` |
| `NUMRES`(3) | `{ LRESHn(4), LREn(7) }` |

Each modeled as a `Field` whose `dataType` is the pair-`Struct`, with
`bddo:repeatCountFromField` pointing at the preceding count field.

**Extension areas:** `UDHDL`(5); if `UDHDL != "00000"` → `UDHOFL`(3) + `UDHD` (TRE
sequence, byte length = `UDHDL − 3`). Then `XHDL`(5); if non-zero → `XHDLOFL`(3) + `XHD`
(TRE sequence, length = `XHDL − 3`). Modeled with `bddo:isPresentIf` on the length field
and `bddo:sizeFromExpression` for the region byte length; the TRE sequence uses a `Field`
of `dataType nitf:TRE` with `bddo:repeatUntil` (consume the sized region).

### 5.2 `nitf:ImageSubheader` — Table A‑3

`IM`(2,="IM") `IID1`(10) `IDATIM`(14) `TGTID`(17) `IID2`(80), the **image security block**
(`ISCLAS`…`ISCTLN`, same 16-field pattern as file security, sizes per Table A‑3),
`ENCRYP`(1) `ISORCE`(42) `NROWS`(8) `NCOLS`(8) `PVTYPE`(3) `IREP`(8) `ICAT`(8) `ABPP`(2)
`PJUST`(1) `ICORDS`(1).

Then three NITF-specific mechanisms:

- **`IGEOLO`(60)** — `bddo:isPresentIf "ICORDS != ' '"` (§6.13; omitted when ICORDS is BCS
  space). Four corner locations in image-coordinate order.
- **Comment loop:** `NICOM`(1) → `ICOMn`(80) with `bddo:repeatCountFromField nitf:NICOM`.
- **Compression:** `IC`(2); `COMRAT`(4) with `bddo:isPresentIf "IC not in (NC, NM)"`.
- **Band loop:** `NBANDS`(1); `XBANDS`(5) with `isPresentIf "NBANDS == 0"`; then a per-band
  `Struct` repeated by `NBANDS`/`XBANDS`:
  `IREPBANDn`(2) `ISUBCATn`(6) `IFCn`(1) `IMFLTn`(3) `NLUTSn`(1); nested LUT sub-loop
  `NELUTn`(5)+`LUTDnm` present iff `NLUTSn != 0` (LUT *data* body described structurally
  only — see non-goals).

Tail: `ISYNC`(1) `IMODE`(1) `NBPR`(4) `NBPC`(4) `NPPBH`(4) `NPPBV`(4) `NBPP`(2) `IDLVL`(3)
`IALVL`(3) `ILOC`(10) `IMAG`(4) `UDIDL`(5) [→ `UDOFL`(3)+`UDID` TRE area] `IXSHDL`(5)
[→ `IXSOFL`(3)+`IXSHD` TRE area].

Enumerations worth minting (small, high value): `IREP`, `ICAT`, `PVTYPE`, `IMODE`, `ICORDS`,
`IC` — from the value ranges in Table A‑3 (and A‑2/A‑2(B) for IREP/ICAT).

### 5.3 `nitf:GraphicSubheader` — Table A‑5

`SY`(2) `SID`(10) `SNAME`(20), graphic security block (`SSCLAS`…`SSCTLN`), `ENCRYP`(1)
`SFMT`(1,=C) `SSTRUCT`(13) `SDLVL`(3) `SALVL`(3) `SLOC`(10) `SBND1`(10) `SCOLOR`(1)
`SBND2`(10) `SRES2`(2) `SXSHDL`(5) [→ `SXSOFL`(3)+`SXSHD` TRE area].

### 5.4 `nitf:TextSubheader` — Table A‑6

`TE`(2) `TEXTID`(7) `TXTALVL`(3) `TXTDT`(14) `TXTITL`(80), text security block
(`TSCLAS`…`TSCTLN`), `ENCRYP`(1) `TXTFMT`(3, enum STA/MTF/UT1/U8S) `TXSHDL`(5)
[→ `TXSOFL`(3)+`TXSHD` TRE area].

### 5.5 `nitf:DESubheader` — Table A‑8

`DE`(2) `DESID`(25) `DESVER`(2), DES security block (`DECLAS`,`DESCLSY`…`DESCTLN`),
then the overflow-conditional fields: `DESOFLW`(6) + `DESITEM`(3) present iff
`DESID == "TRE_OVERFLOW"` (§5.8.3.1) — the path by which TREs relocate out of a full
header/subheader. `DESSHL`(4); `DESSHF`(len=`DESSHL`) present iff `DESSHL != 0`; then
`DESDATA` (for `TRE_OVERFLOW`, a TRE sequence — `repeatUntil`).

### 5.6 `nitf:RESubheader` — Table A‑9

`RE`(2) `RESID`(25) `RESVER`(2), RES security block (`RECLAS`,`RECLSY`…`RECTLN`),
`RESSHL`(4); `RESSHF`(len) present iff non-zero; `RESDATA`.

## 6. Generic TRE framework — Table A‑7

One reusable `nitf:TRE` `Struct`:

- `CETAG`(6, `nitf:BCSA`) — the 6-char tag (`RETAG`/`CETAG` share layout).
- `CEL`(5, `nitf:BCSNpos`, range 00001–99985) — length of `CEDATA`.
- `CEDATA` — `bddo:sizeFromField nitf:CEL`.

TRE areas (`UDHD`, `XHD`, `UDID`, `IXSHD`, `SXSHD`, `TXSHD`, and `TRE_OVERFLOW` DES data)
reference `nitf:TRE` via a `repeatUntil` field over the sized region (§5.8.1.3). The
`TRE_OVERFLOW` relocation is modeled structurally; per-TRE remapping into overflow is not
resolved (documented, not implemented).

## 7. Worked TRE modules

Each is an independent file importing `nitf.ttl`, defining one `Struct` whose fields are
the TRE's declared layout, plus (where a target exists) semantic mappings.

- **`nitf:BLOCKA`** (`CETAG`="BLOCKA", `CEL`=123): `BLOCK_INSTANCE`(2) `N_GRAY`(5)
  `L_LINES`(5) `LAYOVER_ANGLE`(3) `SHADOW_ANGLE`(3) reserved(16) `FRLC_LOC`(21)
  `LRLC_LOC`(21) `LRFC_LOC`(21) `FRFC_LOC`(21) reserved(5). Corner `*_LOC` = lat/lon.
- **`nitf:RPC00B`** (`CETAG`="RPC00B", `CEL`=1041): `SUCCESS`(1) `ERR_BIAS`(7) `ERR_RAND`(7)
  offset/scale fields (`LINE_OFF`(6) `SAMP_OFF`(5) `LAT_OFF`(8) `LONG_OFF`(9)
  `HEIGHT_OFF`(5) `LINE_SCALE`(6) `SAMP_SCALE`(5) `LAT_SCALE`(8) `LONG_SCALE`(9)
  `HEIGHT_SCALE`(5)), then four 20-coefficient arrays (`LINE_NUM_COEFF`, `LINE_DEN_COEFF`,
  `SAMP_NUM_COEFF`, `SAMP_DEN_COEFF`), each a 12-char field with `bddo:repeatCount 20`.

## 8. Semantic lift (today) + gap log

Mappings with a real target now:

| NITF | maps to |
|---|---|
| `nitf:ImageSubheader` | `hexplain:mapsToClass gv:RasterDataset` |
| `NROWS` | `araster:height` (via valueExpression → xsd:integer) |
| `NCOLS` | `araster:width` |
| `FSCLAS` / `ISCLAS` | `asec:classificationLevel` |

`# SEMANTIC GAP LOG` block in `nitf.ttl` (echoed here) lists the backlog for a future
"extend vocabs" sub-project: `NBANDS`→band count, `NBPP`/`ABPP`→bit depth, `IGEOLO` +
BLOCKA corners→geospatial footprint, RPC00B→sensor model, and the ~18 remaining ISM
security fields (codewords, control/handling, releasability, declass) → an ISM-aligned
security register. (Table A‑4 gives the codeword digraphs for that future register.)

## 9. Validation & worked examples

- Description validates against the **existing** BDDO + core SHACL shapes (Struct/Field
  sizing single-mechanism rules, offset/repetition single-mechanism, `mapsToProperty`
  domain, enum shapes). No new shapes.
- `example.ttl` — a worked instance graph for a small single-image, single-band,
  uncompressed, unclassified NITF (`NUMI`=1, no graphics/text/DES/RES, one BLOCKA TRE),
  modeled on the standard's Table I/II example values and the `roads.*` example style.
- `example-invalid.ttl` — same, with one deliberate SHACL violation (e.g. a `Field`
  carrying both `bddo:size` and `bddo:sizeFromField`).

## 10. Sources of truth & verification

- **Container + subheaders + generic TRE:** exact from MIL-STD-2500C Appendix A
  (Tables A‑1, A‑3, A‑5, A‑6, A‑7, A‑8, A‑9). No memory-sourced field data.
- **BLOCKA / RPC00B field layouts** are *registered TREs*, defined in **NGA STDI-0002
  (Compendium of Controlled Extensions)**, not in MIL-STD-2500C. Their field tables in §7
  are from domain knowledge and **must be verified against STDI-0002** before publication;
  any field not confirmed against a citable source will be flagged in the TTL rather than
  trusted.

## 11. Build sequence (for the implementation plan)

1. Ontology header + data types + shared enumerations in `nitf.ttl`.
2. `nitf:TRE` generic framework.
3. `nitf:FileHeader` (incl. the six segment-length repeat structs + extension areas).
4. `nitf:ImageSubheader` (incl. band loop, IGEOLO conditional, comment loop).
5. Graphic / Text / DES / RES subheaders.
6. Semantic mappings + gap-log block.
7. `nitf-tre-blocka.ttl`, `nitf-tre-rpc00b.ttl`.
8. `example.ttl` + `example-invalid.ttl`.
9. SHACL-validate all TTL against bddo + core shapes; fix until clean.
