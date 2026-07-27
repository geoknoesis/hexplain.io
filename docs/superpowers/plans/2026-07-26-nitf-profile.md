# NGA NITF 2.1 Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a byte-level Hexplain (BDDO) description of the NGA NITF 2.1 container — file header, five segment subheaders, and a generic TRE framework — plus two worked TRE modules (BLOCKA, RPC00B) and validating examples, all conforming to the existing bddo + core SHACL shapes.

**Architecture:** New `specification/profiles/nitf/` directory holding pure Turtle. One core file (`nitf.ttl`) defines profile-local data types, shared enumerations, and one `bddo:Struct` per NITF header/subheader; two `nitf-tre-*.ttl` files each add one TRE `Struct`; two example files demonstrate a valid parse-output instance and a deliberately shape-violating fragment. No new SHACL shapes and no vocabulary changes — the profile's own `bddo:Field`/`bddo:Struct` nodes are validated against the shapes already in `bddo.ttl` and `core.ttl`.

**Tech Stack:** RDF 1.1 Turtle; BDDO (`https://hexplain.io/ns/bddo#`); Hexplain core (`https://hexplain.io/ns/core#`); SHACL (validated with pySHACL, advanced mode for `sh:sparql` constraints).

## Global Constraints

- **Source of truth (container):** MIL-STD-2500C, 01 May 2006, Appendix A — Tables A-1 (file header), A-3 (image subheader), A-5 (graphic), A-6 (text), A-7 (TRE format), A-8 (DES), A-9 (RES). Every field name, SIZE (bytes), and conditional rule is copied verbatim from these tables. Do not invent or "improve" field data.
- **Source of truth (TREs):** BLOCKA and RPC00B are registered TREs defined in **NGA STDI-0002**, not in MIL-STD-2500C. Their layouts in Task 9/10 are provided here from the standard registry; if STDI-0002 is available, cross-check before publishing. Any field the implementer cannot confirm against a citable source must carry an `rdfs:comment "UNVERIFIED — confirm against STDI-0002"` rather than be presented as authoritative.
- **Namespace:** `https://hexplain.io/ns/profile/nitf#`, preferred prefix `fmt` (matches the Shapefile profile's convention) — but this profile also needs its own terms, so use prefix `nitf:` bound to the same namespace throughout. `owl:versionIRI …/1.0`, `owl:versionInfo "1.0"`.
- **License / metadata:** mirror `specification/profiles/shapefile/shapefile.ttl` — `dcterms:created "2026-07-26"^^xsd:date`, `dcterms:creator <https://geoknoesis.com>`, `dcterms:license <https://creativecommons.org/licenses/by/4.0/>`, `vann:preferredNamespacePrefix "nitf"`, `vann:preferredNamespaceUri "https://hexplain.io/ns/profile/nitf#"`.
- **Endianness:** all NITF numeric data is big-endian (§5.1.9.1). Set `bddo:endianness bddo:BigEndian` once at each top-level `Struct`.
- **Field encoding:** NITF header/subheader fields are text (BCS/ECS). They are modeled as string-typed `bddo:Field`s with an explicit `bddo:size`, NOT as binary `bddo:uint*`. The single exception is `FBKGC` (3 raw RGB bytes).
- **Prerequisite tooling:** Python 3.9+ with `pyshacl` and `rdflib` installed (`pip install pyshacl rdflib`). pySHACL bundles rdflib; installing pyshacl is sufficient.
- **No new SHACL shapes, no edits to `bddo.ttl`/`core.ttl`/aspect vocabularies.** If a field seems to need a semantic target that does not exist, it goes in the `SEMANTIC GAP LOG` (Task 8), not into a vocabulary edit.
- **Commit style:** conventional commits, scope `nitf`; end every commit message body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## Reference: reusable rendering patterns

Every task below reuses these exact patterns. They are not placeholders — they are the canonical TTL forms.

**Ordered field list on a Struct** (`bddo:hasField` is an `rdf:List`):

```turtle
nitf:FileHeader a bddo:Struct ; rdfs:label "NITF File Header" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( nitf:FH_FHDR nitf:FH_FVER nitf:FH_CLEVEL ) .   # … full ordered list
```

**A fixed-width text field** (named IRI so it can be referenced from the list and from mappings):

```turtle
nitf:FH_FHDR a bddo:Field ; rdfs:label "FHDR — File Profile Name" ;
    bddo:dataType nitf:BCSA ; bddo:size 4 ; bddo:hasFixedValue "NITF" .
```

**A repeating array driven by a count field** (nested pair-Struct repeated N times):

```turtle
nitf:FH_ImgSegTable a bddo:Field ; rdfs:label "Image segment length pairs" ;
    bddo:dataType nitf:ImageSegLenPair ;
    bddo:repeatCountFromField nitf:FH_NUMI .

nitf:ImageSegLenPair a bddo:Struct ; rdfs:label "{ LISHn, LIn }" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( nitf:FH_LISHn nitf:FH_LIn ) .
```

**A conditional-presence field:**

```turtle
nitf:IS_IGEOLO a bddo:Field ; rdfs:label "IGEOLO — Image Geographic Location" ;
    bddo:dataType nitf:BCSA ; bddo:size 60 ;
    bddo:isPresentIf "ICORDS != ' '" .
```

**A sized TRE region containing a repeat-until sequence of TREs:**

```turtle
nitf:FH_UDHD a bddo:Field ; rdfs:label "UDHD — User-Defined Header Data (TRE sequence)" ;
    bddo:dataType nitf:TRE ;
    bddo:isPresentIf "UDHDL != '00000'" ;
    bddo:sizeFromExpression "UDHDL - 3" ;
    bddo:repeatUntil "end-of-region" .
```

**An enumeration attached to a field:**

```turtle
nitf:PVTYPEEnum a bddo:Enumeration ; rdfs:label "Pixel Value Type" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "INT" ]
      , [ a bddo:EnumValue ; bddo:enumRawValue "B" ]
      , [ a bddo:EnumValue ; bddo:enumRawValue "SI" ]
      , [ a bddo:EnumValue ; bddo:enumRawValue "R" ]
      , [ a bddo:EnumValue ; bddo:enumRawValue "C" ] .
# usage:  nitf:IS_PVTYPE … bddo:enumeration nitf:PVTYPEEnum .
```

**A semantic mapping on a field / class mapping on a Struct:**

```turtle
nitf:IS_NROWS  hexplain:mapsToProperty araster:height ;
    hexplain:valueExpression "xsd:integer(NROWS)" ; hexplain:valueDatatype xsd:integer .
nitf:ImageSubheader  hexplain:mapsToClass gv:RasterDataset .
```

---

## Task 1: SHACL validation harness

**Files:**
- Create: `tools/shacl_check.py`
- Create: `specification/profiles/nitf/` (empty dir; created implicitly by first write)

**Interfaces:**
- Produces: a CLI `python tools/shacl_check.py <target.ttl>` that loads bddo + dlv + core + the target into one data graph, validates against the bddo + core shapes graph in advanced mode, prints the report, and exits 0 (conforms) or 1 (violations). Later tasks call this verbatim.

- [ ] **Step 1: Write the harness script**

```python
# tools/shacl_check.py — validate a Hexplain TTL against bddo + core SHACL shapes.
import sys
from rdflib import Graph
from pyshacl import validate

ONT = [
    "specification/bddo/bddo.ttl",
    "specification/dlv/dlv.ttl",
    "specification/hexplain/core.ttl",
]
SHAPES = [
    "specification/bddo/bddo.ttl",
    "specification/hexplain/core.ttl",
]

def load(paths):
    g = Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g

def main(targets):
    data = load(ONT + list(targets))
    shapes = load(SHAPES)
    conforms, _, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    print(report)
    sys.exit(0 if conforms else 1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python tools/shacl_check.py <target.ttl> [more.ttl ...]")
        sys.exit(2)
    main(sys.argv[1:])
```

- [ ] **Step 2: Verify it runs against an existing profile (harness smoke test)**

Run (from repo root `d:\work\hexplain.io`): `python tools/shacl_check.py specification/profiles/shapefile/shapefile.ttl`
Expected: prints a validation report and exits 0 (`Conforms: True`). If it errors on import, confirm `pip install pyshacl rdflib` succeeded and that all five `ONT`/`SHAPES` files parse.

- [ ] **Step 3: Commit**

```bash
git add tools/shacl_check.py
git commit -m "build(nitf): add pySHACL validation harness for profiles"
```

---

## Task 2: `nitf.ttl` skeleton — ontology header, data types, core enumerations

**Files:**
- Create: `specification/profiles/nitf/nitf.ttl`

**Interfaces:**
- Produces: profile-local data types `nitf:BCSA`, `nitf:BCSN`, `nitf:BCSNpos`, `nitf:ECSA` (all `bddo:DataType`); enumerations `nitf:FSCLASEnum`, `nitf:PVTYPEEnum`, `nitf:IMODEEnum`, `nitf:ICORDSEnum`, `nitf:IREPEnum`, `nitf:ICEnum`. All later tasks reference these.

- [ ] **Step 1: Write the failing test**

The test IS the harness over the (not-yet-existing) file.
Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl`
Expected: FAIL — file not found / parse error (file does not exist yet).

- [ ] **Step 2: Author the ontology header + prefixes + data types + enumerations**

```turtle
# Hexplain Profile — NGA NITF 2.1 (MIL-STD-2500C). Byte-level container description.
@prefix nitf:    <https://hexplain.io/ns/profile/nitf#> .
@prefix bddo:    <https://hexplain.io/ns/bddo#> .
@prefix hexplain:<https://hexplain.io/ns/core#> .
@prefix gv:      <https://hexplain.io/ns/geo#> .
@prefix araster: <https://hexplain.io/ns/aspect/raster#> .
@prefix asec:    <https://hexplain.io/ns/aspect/security#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann:    <http://purl.org/vocab/vann/> .

<https://hexplain.io/ns/profile/nitf> a owl:Ontology ;
    owl:versionIRI <https://hexplain.io/ns/profile/nitf/1.0> ; owl:versionInfo "1.0" ;
    owl:imports <https://hexplain.io/ns/core> ;
    rdfs:label "Hexplain Profile — NGA NITF 2.1" ;
    rdfs:comment "Byte-level description of the National Imagery Transmission Format 2.1 container (MIL-STD-2500C): file header, image/graphic/text/DES/RES subheaders, and the generic Tagged Record Extension framework. NSIF/STANAG 4545 is field-compatible." ;
    rdfs:seeAlso <https://www.everyspec.com/MIL-STD/MIL-STD-2500-2599/MIL-STD-2500C_25693/> ;
    dcterms:created "2026-07-26"^^xsd:date ; dcterms:creator <https://geoknoesis.com> ;
    dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
    vann:preferredNamespacePrefix "nitf" ; vann:preferredNamespaceUri "https://hexplain.io/ns/profile/nitf#" .

# ---------- Profile-local data types (NITF fields are BCS/ECS text) ----------
nitf:BCSA a bddo:DataType ; rdfs:label "BCS-A (alphanumeric text)" ;
    bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .
nitf:BCSN a bddo:DataType ; rdfs:label "BCS-N (numeric text: digits + . / + -)" ;
    bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .
nitf:BCSNpos a bddo:DataType ; rdfs:label "BCS-N positive integer (digits only)" ;
    bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .
nitf:ECSA a bddo:DataType ; rdfs:label "ECS-A (restricted to BCS-A subset)" ;
    bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .

# ---------- Core enumerations (values verbatim from Table A-3) ----------
nitf:PVTYPEEnum a bddo:Enumeration ; rdfs:label "Pixel Value Type" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "INT" ] , [ a bddo:EnumValue ; bddo:enumRawValue "B" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "SI" ] , [ a bddo:EnumValue ; bddo:enumRawValue "R" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "C" ] .
nitf:IMODEEnum a bddo:Enumeration ; rdfs:label "Image Mode" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "B" ] , [ a bddo:EnumValue ; bddo:enumRawValue "P" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "R" ] , [ a bddo:EnumValue ; bddo:enumRawValue "S" ] .
nitf:ICORDSEnum a bddo:Enumeration ; rdfs:label "Image Coordinate Representation" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "U" ] , [ a bddo:EnumValue ; bddo:enumRawValue "G" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "N" ] , [ a bddo:EnumValue ; bddo:enumRawValue "S" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "D" ] , [ a bddo:EnumValue ; bddo:enumRawValue " " ] .
nitf:IREPEnum a bddo:Enumeration ; rdfs:label "Image Representation" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "MONO" ] , [ a bddo:EnumValue ; bddo:enumRawValue "RGB" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "RGB/LUT" ] , [ a bddo:EnumValue ; bddo:enumRawValue "MULTI" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "NODISPLY" ] , [ a bddo:EnumValue ; bddo:enumRawValue "NVECTOR" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "POLAR" ] , [ a bddo:EnumValue ; bddo:enumRawValue "VPH" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "YCbCr601" ] .
nitf:ICEnum a bddo:Enumeration ; rdfs:label "Image Compression" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "NC" ] , [ a bddo:EnumValue ; bddo:enumRawValue "NM" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "C1" ] , [ a bddo:EnumValue ; bddo:enumRawValue "C3" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "C4" ] , [ a bddo:EnumValue ; bddo:enumRawValue "C5" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "C6" ] , [ a bddo:EnumValue ; bddo:enumRawValue "C7" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "C8" ] , [ a bddo:EnumValue ; bddo:enumRawValue "I1" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "M1" ] , [ a bddo:EnumValue ; bddo:enumRawValue "M3" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "M4" ] , [ a bddo:EnumValue ; bddo:enumRawValue "M5" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "M6" ] , [ a bddo:EnumValue ; bddo:enumRawValue "M7" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "M8" ] .
nitf:FSCLASEnum a bddo:Enumeration ; rdfs:label "Security Classification level" ;
    bddo:hasEnumValue
      [ a bddo:EnumValue ; bddo:enumRawValue "T" ] , [ a bddo:EnumValue ; bddo:enumRawValue "S" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "C" ] , [ a bddo:EnumValue ; bddo:enumRawValue "R" ] ,
      [ a bddo:EnumValue ; bddo:enumRawValue "U" ] .
```

- [ ] **Step 3: Run the harness — expect conforms**

Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl`
Expected: PASS (`Conforms: True`). The only shape-bearing nodes so far are the `bddo:DataType` and `bddo:Enumeration`/`bddo:EnumValue` individuals; they must satisfy `DataTypeShape`, `EnumerationShape`, `EnumValueShape`. If it fails, read the report — most likely an `enumRawValue` missing or a `baseType` not in the allowed set.

- [ ] **Step 4: Commit**

```bash
git add specification/profiles/nitf/nitf.ttl
git commit -m "feat(nitf): profile header, BCS/ECS data types, core enumerations"
```

---

## Task 3: Generic TRE framework (`nitf:TRE`)

**Files:**
- Modify: `specification/profiles/nitf/nitf.ttl` (append)

**Interfaces:**
- Consumes: `nitf:BCSA`, `nitf:BCSNpos` (Task 2).
- Produces: `nitf:TRE` (a `bddo:Struct`) referenced by every TRE-area field and by the TRE modules (Tasks 9–10).

- [ ] **Step 1: Failing test** — append nothing yet; run harness to confirm current pass, then you will add `nitf:TRE` and a one-field smoke usage. Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl` → PASS (baseline).

- [ ] **Step 2: Append the TRE framework (Table A-7)**

```turtle
# ---------- Generic Tagged Record Extension (Table A-7) ----------
nitf:TRE a bddo:Struct ; rdfs:label "Tagged Record Extension" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( nitf:TRE_CETAG nitf:TRE_CEL nitf:TRE_CEDATA ) .

nitf:TRE_CETAG a bddo:Field ; rdfs:label "CETAG/RETAG — 6-char tag" ;
    bddo:dataType nitf:BCSA ; bddo:size 6 .
nitf:TRE_CEL a bddo:Field ; rdfs:label "CEL/REL — length of CEDATA" ;
    bddo:dataType nitf:BCSNpos ; bddo:size 5 .
nitf:TRE_CEDATA a bddo:Field ; rdfs:label "CEDATA/REDATA — user-defined data" ;
    bddo:dataType bddo:bytes ; bddo:sizeFromField nitf:TRE_CEL .
```

- [ ] **Step 3: Run harness — expect conforms**

Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl`
Expected: PASS. `nitf:TRE_CEDATA` uses `bddo:bytes` with exactly one sizing mechanism (`sizeFromField`), satisfying `VariableLengthFieldShape` + `FieldSizingShape`.

- [ ] **Step 4: Commit**

```bash
git add specification/profiles/nitf/nitf.ttl
git commit -m "feat(nitf): generic Tagged Record Extension framework"
```

---

## Task 4: File header (`nitf:FileHeader`)

**Files:**
- Modify: `specification/profiles/nitf/nitf.ttl` (append)

**Interfaces:**
- Consumes: `nitf:BCSA`, `nitf:BCSN`, `nitf:BCSNpos`, `nitf:FSCLASEnum`, `nitf:TRE`.
- Produces: `nitf:FileHeader` (Struct); the six pair-Structs `nitf:ImageSegLenPair`, `nitf:GraphicSegLenPair`, `nitf:TextSegLenPair`, `nitf:DESegLenPair`, `nitf:RESegLenPair`; the field IRIs `nitf:FH_FSCLAS`, `nitf:FH_NUMI` (used by mappings/examples later).

**Field spec — Table A-1** (author each as a named `bddo:Field` with `bddo:dataType` + `bddo:size`; datatype column: A=`nitf:BCSA`, E=`nitf:ECSA`, N=`nitf:BCSN`, Np=`nitf:BCSNpos`, bin=`bddo:bytes`):

| Field IRI suffix | NITF | size | type | notes |
|---|---|---|---|---|
| FHDR | FHDR | 4 | A | `hasFixedValue "NITF"` |
| FVER | FVER | 5 | A | `hasFixedValue "02.10"` |
| CLEVEL | CLEVEL | 2 | Np | |
| STYPE | STYPE | 4 | A | `hasFixedValue "BF01"` |
| OSTAID | OSTAID | 10 | A | |
| FDT | FDT | 14 | N | CCYYMMDDhhmmss |
| FTITLE | FTITLE | 80 | E | |
| FSCLAS | FSCLAS | 1 | E | `bddo:enumeration nitf:FSCLASEnum` |
| FSCLSY | FSCLSY | 2 | E | |
| FSCODE | FSCODE | 11 | A | |
| FSCTLH | FSCTLH | 2 | E | |
| FSREL | FSREL | 20 | E | |
| FSDCTP | FSDCTP | 2 | E | |
| FSDCDT | FSDCDT | 8 | E | |
| FSDCXM | FSDCXM | 4 | E | |
| FSDG | FSDG | 1 | E | |
| FSDGDT | FSDGDT | 8 | E | |
| FSCLTX | FSCLTX | 43 | E | |
| FSCATP | FSCATP | 1 | E | |
| FSCAUT | FSCAUT | 40 | E | |
| FSCRSN | FSCRSN | 1 | E | |
| FSSRDT | FSSRDT | 8 | E | |
| FSCTLN | FSCTLN | 15 | E | |
| FSCOP | FSCOP | 5 | Np | |
| FSCPYS | FSCPYS | 5 | Np | |
| ENCRYP | ENCRYP | 1 | Np | |
| FBKGC | FBKGC | 3 | bin | `bddo:bytes` (RGB) |
| ONAME | ONAME | 24 | E | |
| OPHONE | OPHONE | 18 | E | |
| FL | FL | 12 | Np | |
| HL | HL | 6 | Np | |
| NUMI | NUMI | 3 | Np | drives ImageSegLenPair repeat |
| NUMS | NUMS | 3 | Np | drives GraphicSegLenPair repeat |
| NUMX | NUMX | 3 | Np | reserved "000" |
| NUMT | NUMT | 3 | Np | drives TextSegLenPair repeat |
| NUMDES | NUMDES | 3 | Np | drives DESegLenPair repeat |
| NUMRES | NUMRES | 3 | Np | drives RESegLenPair repeat |
| UDHDL | UDHDL | 5 | Np | |
| XHDL | XHDL | 5 | Np | |

Pair-Struct member sizes (Table A-1): `LISHn`6/`LIn`10; `LSSHn`4/`LSn`6; `LTSHn`4/`LTn`5; `LDSHn`4/`LDn`9; `LRESHn`4/`LREn`7. All `nitf:BCSNpos`. Extension overflow fields: `UDHOFL`3, `XHDLOFL`3 (both Np, conditional on their length field ≠ "00000").

- [ ] **Step 1: Failing test** — run harness (baseline PASS), then add the header referencing new IRIs. Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl` → PASS baseline.

- [ ] **Step 2: Author the file header Struct + fields**

Author every field in the table above using the fixed-width-field pattern. The `hasField` list must be in table order, with the repeat/extension fields interleaved exactly here:

```turtle
nitf:FileHeader a bddo:Struct ; rdfs:label "NITF File Header (Table A-1)" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField (
      nitf:FH_FHDR nitf:FH_FVER nitf:FH_CLEVEL nitf:FH_STYPE nitf:FH_OSTAID nitf:FH_FDT nitf:FH_FTITLE
      nitf:FH_FSCLAS nitf:FH_FSCLSY nitf:FH_FSCODE nitf:FH_FSCTLH nitf:FH_FSREL nitf:FH_FSDCTP nitf:FH_FSDCDT
      nitf:FH_FSDCXM nitf:FH_FSDG nitf:FH_FSDGDT nitf:FH_FSCLTX nitf:FH_FSCATP nitf:FH_FSCAUT nitf:FH_FSCRSN
      nitf:FH_FSSRDT nitf:FH_FSCTLN nitf:FH_FSCOP nitf:FH_FSCPYS nitf:FH_ENCRYP nitf:FH_FBKGC nitf:FH_ONAME
      nitf:FH_OPHONE nitf:FH_FL nitf:FH_HL
      nitf:FH_NUMI nitf:FH_ImageSegTable
      nitf:FH_NUMS nitf:FH_GraphicSegTable
      nitf:FH_NUMX
      nitf:FH_NUMT nitf:FH_TextSegTable
      nitf:FH_NUMDES nitf:FH_DESegTable
      nitf:FH_NUMRES nitf:FH_RESegTable
      nitf:FH_UDHDL nitf:FH_UDHOFL nitf:FH_UDHD
      nitf:FH_XHDL nitf:FH_XHDLOFL nitf:FH_XHD
    ) .

# Example fixed field (repeat for every row of the table):
nitf:FH_FHDR a bddo:Field ; rdfs:label "FHDR — File Profile Name" ;
    bddo:dataType nitf:BCSA ; bddo:size 4 ; bddo:hasFixedValue "NITF" .
nitf:FH_FSCLAS a bddo:Field ; rdfs:label "FSCLAS — File Security Classification" ;
    bddo:dataType nitf:ECSA ; bddo:size 1 ; bddo:enumeration nitf:FSCLASEnum .
nitf:FH_FBKGC a bddo:Field ; rdfs:label "FBKGC — File Background Color (RGB)" ;
    bddo:dataType bddo:bytes ; bddo:size 3 .
# … author FVER, CLEVEL, STYPE, OSTAID, FDT, FTITLE, the 16 FS* security fields,
#     FSCOP, FSCPYS, ENCRYP, ONAME, OPHONE, FL, HL, the six NUM* count fields,
#     UDHDL, XHDL — all from the table.

# Segment-length tables (repeat pattern; one per segment type):
nitf:FH_ImageSegTable a bddo:Field ; rdfs:label "Image segment length pairs (× NUMI)" ;
    bddo:dataType nitf:ImageSegLenPair ; bddo:repeatCountFromField nitf:FH_NUMI .
nitf:ImageSegLenPair a bddo:Struct ; rdfs:label "{ LISHn, LIn }" ;
    bddo:endianness bddo:BigEndian ; bddo:hasField ( nitf:FH_LISHn nitf:FH_LIn ) .
nitf:FH_LISHn a bddo:Field ; rdfs:label "LISHn — length of nth image subheader" ;
    bddo:dataType nitf:BCSNpos ; bddo:size 6 .
nitf:FH_LIn a bddo:Field ; rdfs:label "LIn — length of nth image segment" ;
    bddo:dataType nitf:BCSNpos ; bddo:size 10 .
# … GraphicSegLenPair {LSSHn 4, LSn 6}, TextSegLenPair {LTSHn 4, LTn 5},
#     DESegLenPair {LDSHn 4, LDn 9}, RESegLenPair {LRESHn 4, LREn 7} — same pattern.

# Extension areas:
nitf:FH_UDHOFL a bddo:Field ; rdfs:label "UDHOFL — user-defined header overflow" ;
    bddo:dataType nitf:BCSNpos ; bddo:size 3 ; bddo:isPresentIf "UDHDL != '00000'" .
nitf:FH_UDHD a bddo:Field ; rdfs:label "UDHD — user-defined header data (TREs)" ;
    bddo:dataType nitf:TRE ; bddo:isPresentIf "UDHDL != '00000'" ;
    bddo:sizeFromExpression "UDHDL - 3" ; bddo:repeatUntil "end-of-region" .
nitf:FH_XHDLOFL a bddo:Field ; rdfs:label "XHDLOFL — extended header overflow" ;
    bddo:dataType nitf:BCSNpos ; bddo:size 3 ; bddo:isPresentIf "XHDL != '00000'" .
nitf:FH_XHD a bddo:Field ; rdfs:label "XHD — extended header data (TREs)" ;
    bddo:dataType nitf:TRE ; bddo:isPresentIf "XHDL != '00000'" ;
    bddo:sizeFromExpression "XHDL - 3" ; bddo:repeatUntil "end-of-region" .
```

- [ ] **Step 3: Run harness — expect conforms**

Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl`
Expected: PASS. Watch for `FieldSizingShape` (a field must have exactly one sizing mechanism — `FH_UDHD` uses only `sizeFromExpression`), `FieldOffsetShape`, and `StructShape` (every `hasField` member is a `bddo:Field`; the pair-Struct list members are Fields).

- [ ] **Step 4: Commit**

```bash
git add specification/profiles/nitf/nitf.ttl
git commit -m "feat(nitf): file header struct with segment tables and TRE areas"
```

---

## Task 5: Image subheader (`nitf:ImageSubheader`)

**Files:**
- Modify: `specification/profiles/nitf/nitf.ttl` (append)

**Interfaces:**
- Consumes: all data types, `nitf:PVTYPEEnum`, `nitf:IREPEnum`, `nitf:ICEnum`, `nitf:IMODEEnum`, `nitf:ICORDSEnum`, `nitf:FSCLASEnum`, `nitf:TRE`.
- Produces: `nitf:ImageSubheader` (Struct); field IRIs `nitf:IS_NROWS`, `nitf:IS_NCOLS`, `nitf:IS_ISCLAS` (used by mappings/examples); per-band Struct `nitf:ImageBand`.

**Field spec — Table A-3, in order.** Security block `IS*` (16 fields) has identical sizes to the file-header `FS*` block. Core geometry/representation fields:

| suffix | NITF | size | type | notes |
|---|---|---|---|---|
| IM | IM | 2 | A | fixed "IM" |
| IID1 | IID1 | 10 | A | |
| IDATIM | IDATIM | 14 | N | |
| TGTID | TGTID | 17 | A | |
| IID2 | IID2 | 80 | E | |
| ISCLAS…ISCTLN | (16 security fields) | — | E/A | sizes as FS* block (Task 4) |
| ENCRYP | ENCRYP | 1 | Np | |
| ISORCE | ISORCE | 42 | E | |
| NROWS | NROWS | 8 | Np | |
| NCOLS | NCOLS | 8 | Np | |
| PVTYPE | PVTYPE | 3 | A | enum PVTYPEEnum |
| IREP | IREP | 8 | A | enum IREPEnum |
| ICAT | ICAT | 8 | A | |
| ABPP | ABPP | 2 | Np | |
| PJUST | PJUST | 1 | A | |
| ICORDS | ICORDS | 1 | A | enum ICORDSEnum |
| IGEOLO | IGEOLO | 60 | A | `isPresentIf "ICORDS != ' '"` |
| NICOM | NICOM | 1 | Np | drives ICOM repeat |
| IC | IC | 2 | A | enum ICEnum |
| COMRAT | COMRAT | 4 | A | `isPresentIf "IC not in (NC, NM)"` |
| NBANDS | NBANDS | 1 | Np | |
| XBANDS | XBANDS | 5 | Np | `isPresentIf "NBANDS == 0"` |
| (band loop) | IREPBANDn… | — | — | see ImageBand Struct |
| ISYNC | ISYNC | 1 | Np | |
| IMODE | IMODE | 1 | A | enum IMODEEnum |
| NBPR | NBPR | 4 | Np | |
| NBPC | NBPC | 4 | Np | |
| NPPBH | NPPBH | 4 | Np | |
| NPPBV | NPPBV | 4 | Np | |
| NBPP | NBPP | 2 | Np | |
| IDLVL | IDLVL | 3 | Np | |
| IALVL | IALVL | 3 | Np | |
| ILOC | ILOC | 10 | N | |
| IMAG | IMAG | 4 | A | |
| UDIDL | UDIDL | 5 | Np | |
| IXSHDL | IXSHDL | 5 | Np | |

Repeat/conditional sub-structures:

- **Comment loop:** `nitf:IS_ICOM a bddo:Field ; bddo:dataType nitf:ECSA ; bddo:size 80 ; bddo:repeatCountFromField nitf:IS_NICOM .`
- **Band loop:** field `nitf:IS_BandTable` with `bddo:dataType nitf:ImageBand ; bddo:repeatCountFromField nitf:IS_NBANDS`. (Cut #1: repeat by NBANDS; the XBANDS>9 large-band case is noted `rdfs:comment` but not separately modeled.) The per-band Struct:

```turtle
nitf:ImageBand a bddo:Struct ; rdfs:label "Image band record (Table A-3 band loop)" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( nitf:IB_IREPBAND nitf:IB_ISUBCAT nitf:IB_IFC nitf:IB_IMFLT nitf:IB_NLUTS ) .
nitf:IB_IREPBAND a bddo:Field ; rdfs:label "IREPBANDn" ; bddo:dataType nitf:BCSA ; bddo:size 2 .
nitf:IB_ISUBCAT a bddo:Field ; rdfs:label "ISUBCATn" ; bddo:dataType nitf:BCSA ; bddo:size 6 .
nitf:IB_IFC a bddo:Field ; rdfs:label "IFCn" ; bddo:dataType nitf:BCSA ; bddo:size 1 .
nitf:IB_IMFLT a bddo:Field ; rdfs:label "IMFLTn" ; bddo:dataType nitf:BCSA ; bddo:size 3 .
nitf:IB_NLUTS a bddo:Field ; rdfs:label "NLUTSn (LUT sub-loop omitted in cut #1)" ;
    bddo:dataType nitf:BCSNpos ; bddo:size 1 ;
    rdfs:comment "When NLUTSn != 0, NELUTn(5) + LUTDnm data follow; LUT body deferred (see design non-goals)." .
```

- **UDID / IXSHD TRE areas** — same pattern as `FH_UDHD`/`FH_XHD` but conditioned on `UDIDL`/`IXSHDL`, with `UDOFL`(3)/`IXSOFL`(3) present fields.

- [ ] **Step 1: Failing test** — baseline PASS, then append. Run harness → PASS baseline.
- [ ] **Step 2: Author `nitf:ImageSubheader`, its ordered `hasField` list (table order, with IGEOLO/COMRAT/XBANDS conditional fields, the comment loop, the band table, and the two TRE areas interleaved exactly per Table A-3), the 16 IS* security fields, `nitf:ImageBand`, and the ICOM field.** Use the field-rendering, conditional, repeat, and enum patterns from the reference section.
- [ ] **Step 3: Run harness** — `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl` → PASS. Common trip: a field with both `bddo:size` and a conditional/enum is fine; a field with two *sizing* mechanisms is not.
- [ ] **Step 4: Commit** — `git commit -am "feat(nitf): image subheader with band loop, IGEOLO/COMRAT conditionals"`

---

## Task 6: Graphic and Text subheaders

**Files:** Modify `specification/profiles/nitf/nitf.ttl` (append).
**Interfaces:** Produces `nitf:GraphicSubheader`, `nitf:TextSubheader`; field IRIs `nitf:GS_SSCLAS`, `nitf:TS_TSCLAS`.

**Graphic — Table A-5, in order:** `SY`2(A,fixed "SY") `SID`10(A) `SNAME`20(E) + graphic security block `SSCLAS…SSCTLN` (sizes as FS* block, prefix SS) `ENCRYP`1(Np) `SFMT`1(A,fixed "C") `SSTRUCT`13(Np) `SDLVL`3(Np) `SALVL`3(Np) `SLOC`10(N) `SBND1`10(N) `SCOLOR`1(A) `SBND2`10(N) `SRES2`2(Np) `SXSHDL`5(Np) then `SXSOFL`3(Np, `isPresentIf "SXSHDL != '00000'"`) + `SXSHD` (TRE area, `sizeFromExpression "SXSHDL - 3"`, `repeatUntil`).

**Text — Table A-6, in order:** `TE`2(A,fixed "TE") `TEXTID`7(A) `TXTALVL`3(Np) `TXTDT`14(N) `TXTITL`80(E) + text security block `TSCLAS…TSCTLN` (prefix TS) `ENCRYP`1(Np) `TXTFMT`3(A; enum values STA/MTF/UT1/U8S — define `nitf:TXTFMTEnum` here) `TXSHDL`5(Np) then `TXSOFL`3(Np, `isPresentIf "TXSHDL != '00000'"`) + `TXSHD` (TRE area).

- [ ] **Step 1: Failing test** — baseline PASS.
- [ ] **Step 2: Author both Structs, their fields, the SS*/TS* security blocks, and `nitf:TXTFMTEnum`.**
- [ ] **Step 3: Run harness** → PASS.
- [ ] **Step 4: Commit** — `git commit -am "feat(nitf): graphic and text subheaders"`

---

## Task 7: DES and RES subheaders

**Files:** Modify `specification/profiles/nitf/nitf.ttl` (append).
**Interfaces:** Produces `nitf:DESubheader`, `nitf:RESubheader`.

**DES — Table A-8, in order:** `DE`2(A,fixed "DE") `DESID`25(A) `DESVER`2(Np) + DES security block `DECLAS`1(E,enum FSCLASEnum) `DESCLSY`2…`DESCTLN`15 (prefix DES, sizes as FS* block) then overflow-conditional: `DESOFLW`6(A, `isPresentIf "DESID == 'TRE_OVERFLOW'"`) `DESITEM`3(Np, `isPresentIf "DESID == 'TRE_OVERFLOW'"`) `DESSHL`4(Np) `DESSHF`(A, `sizeFromField nitf:DES_DESSHL`, `isPresentIf "DESSHL != '0000'"`) `DESDATA`(`bddo:bytes`, `sizeToEndOfStream true`; `rdfs:comment` that for `DESID = TRE_OVERFLOW` this is a `nitf:TRE` sequence).

**RES — Table A-9, in order:** `RE`2(A,fixed "RE") `RESID`25(A) `RESVER`2(Np) + RES security block `RECLAS`1(E,enum FSCLASEnum) `RECLSY`2…`RECTLN`15 (prefix RE) `RESSHL`4(Np) `RESSHF`(A, `sizeFromField nitf:RES_RESSHL`, `isPresentIf "RESSHL != '0000'"`) `RESDATA`(`bddo:bytes`, `sizeToEndOfStream true`).

Note: `DESDATA`/`RESDATA` use `bddo:sizeToEndOfStream true` as their single sizing mechanism (the surrounding segment length bounds them). Do not also add `size`/`sizeFromField` (would violate `FieldSizingShape`).

- [ ] **Step 1: Failing test** — baseline PASS.
- [ ] **Step 2: Author both Structs + DES*/RE* security blocks.**
- [ ] **Step 3: Run harness** → PASS.
- [ ] **Step 4: Commit** — `git commit -am "feat(nitf): DES and RES subheaders"`

---

## Task 8: Semantic lift + gap log

**Files:** Modify `specification/profiles/nitf/nitf.ttl` (append).
**Interfaces:** Consumes field IRIs `nitf:IS_NROWS`, `nitf:IS_NCOLS`, `nitf:FH_FSCLAS`, `nitf:IS_ISCLAS`, Struct `nitf:ImageSubheader`. Adds `hexplain:*` triples to existing nodes.

- [ ] **Step 1: Failing test** — baseline PASS.
- [ ] **Step 2: Append mappings + gap log**

```turtle
# ---------- Semantic lift (targets that exist today) ----------
nitf:ImageSubheader hexplain:mapsToClass gv:RasterDataset .
nitf:IS_NROWS hexplain:mapsToProperty araster:height ;
    hexplain:valueExpression "xsd:integer(NROWS)" ; hexplain:valueDatatype xsd:integer .
nitf:IS_NCOLS hexplain:mapsToProperty araster:width ;
    hexplain:valueExpression "xsd:integer(NCOLS)" ; hexplain:valueDatatype xsd:integer .
nitf:FH_FSCLAS hexplain:mapsToProperty asec:classificationLevel .
nitf:IS_ISCLAS hexplain:mapsToProperty asec:classificationLevel .

# ---------- SEMANTIC GAP LOG (backlog for a future "extend vocabs" sub-project) ----------
# The following NITF fields have no semantic target in current vocabularies and remain
# physical-only until the aspect vocabularies are extended:
#   NBANDS            -> raster band count            (needs araster:bandCount)
#   NBPP / ABPP       -> bit depth                    (needs araster:bitDepth)
#   IGEOLO + BLOCKA corners -> geospatial footprint   (needs spatialref corner/bbox term)
#   RPC00B            -> rational-polynomial sensor model (needs a sensor-model vocab)
#   ISCODE/ISCTLH/ISREL/ISDCTP…ISCTLN (15 ISM fields) -> ISM-aligned security register
#     (Table A-4 gives the codeword digraphs for that future register)
```

- [ ] **Step 3: Run harness** — `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl` → PASS. `MapsToPropertyShape` requires the subject be a `bddo:Field` and the object an IRI property; `MapsToClassShape` requires the subject be a `bddo:Struct`. (`araster:height` etc. are `owl:DatatypeProperty` in their vocabularies, satisfying the `sh:or` in `core.ttl`.)
- [ ] **Step 4: Commit** — `git commit -am "feat(nitf): semantic lift for width/height/classification + gap log"`

---

## Task 9: BLOCKA TRE module

**Files:** Create `specification/profiles/nitf/nitf-tre-blocka.ttl`.
**Interfaces:** Consumes `nitf:TRE`, `nitf:BCSA`, `nitf:BCSN` (imported via `nitf.ttl`). Produces `nitf:BLOCKA`.

BLOCKA layout (STDI-0002; CEDATA length 123 = 2+5+5+3+3+16+21+21+21+21+5):

- [ ] **Step 1: Failing test** — run `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl specification/profiles/nitf/nitf-tre-blocka.ttl` → FAIL (file missing).
- [ ] **Step 2: Author the module**

```turtle
@prefix nitf: <https://hexplain.io/ns/profile/nitf#> .
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .

<https://hexplain.io/ns/profile/nitf/tre/blocka> a owl:Ontology ;
    owl:imports <https://hexplain.io/ns/profile/nitf> ;
    rdfs:label "NITF TRE — BLOCKA (image block metadata, STDI-0002)" ;
    rdfs:comment "CEDATA layout for the BLOCKA controlled extension (CETAG=BLOCKA, CEL=123). Corner *_LOC fields are lat/lon strings." .

nitf:BLOCKA a bddo:Struct ; rdfs:label "BLOCKA TRE payload" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( nitf:BLOCKA_BLOCK_INSTANCE nitf:BLOCKA_N_GRAY nitf:BLOCKA_L_LINES
      nitf:BLOCKA_LAYOVER_ANGLE nitf:BLOCKA_SHADOW_ANGLE nitf:BLOCKA_RES1
      nitf:BLOCKA_FRLC_LOC nitf:BLOCKA_LRLC_LOC nitf:BLOCKA_LRFC_LOC nitf:BLOCKA_FRFC_LOC
      nitf:BLOCKA_RES2 ) .

nitf:BLOCKA_BLOCK_INSTANCE a bddo:Field ; rdfs:label "BLOCK_INSTANCE" ; bddo:dataType nitf:BCSNpos ; bddo:size 2 .
nitf:BLOCKA_N_GRAY a bddo:Field ; rdfs:label "N_GRAY" ; bddo:dataType nitf:BCSNpos ; bddo:size 5 .
nitf:BLOCKA_L_LINES a bddo:Field ; rdfs:label "L_LINES" ; bddo:dataType nitf:BCSNpos ; bddo:size 5 .
nitf:BLOCKA_LAYOVER_ANGLE a bddo:Field ; rdfs:label "LAYOVER_ANGLE" ; bddo:dataType nitf:BCSA ; bddo:size 3 .
nitf:BLOCKA_SHADOW_ANGLE a bddo:Field ; rdfs:label "SHADOW_ANGLE" ; bddo:dataType nitf:BCSA ; bddo:size 3 .
nitf:BLOCKA_RES1 a bddo:Field ; rdfs:label "reserved-001" ; bddo:dataType nitf:BCSA ; bddo:size 16 .
nitf:BLOCKA_FRLC_LOC a bddo:Field ; rdfs:label "FRLC_LOC (first row/last col lat/lon)" ; bddo:dataType nitf:BCSA ; bddo:size 21 .
nitf:BLOCKA_LRLC_LOC a bddo:Field ; rdfs:label "LRLC_LOC" ; bddo:dataType nitf:BCSA ; bddo:size 21 .
nitf:BLOCKA_LRFC_LOC a bddo:Field ; rdfs:label "LRFC_LOC" ; bddo:dataType nitf:BCSA ; bddo:size 21 .
nitf:BLOCKA_FRFC_LOC a bddo:Field ; rdfs:label "FRFC_LOC" ; bddo:dataType nitf:BCSA ; bddo:size 21 .
nitf:BLOCKA_RES2 a bddo:Field ; rdfs:label "reserved-002" ; bddo:dataType nitf:BCSA ; bddo:size 5 .
```

- [ ] **Step 3: Run harness** — `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl specification/profiles/nitf/nitf-tre-blocka.ttl` → PASS.
- [ ] **Step 4: Commit** — `git add specification/profiles/nitf/nitf-tre-blocka.ttl && git commit -m "feat(nitf): BLOCKA TRE module"`

---

## Task 10: RPC00B TRE module

**Files:** Create `specification/profiles/nitf/nitf-tre-rpc00b.ttl`.
**Interfaces:** Consumes `nitf:TRE`, `nitf:BCSA`, `nitf:BCSN`. Produces `nitf:RPC00B`.

RPC00B layout (STDI-0002; CEDATA length 1041 = 81 fixed + 4×20×12 coefficients):

- [ ] **Step 1: Failing test** — run harness over nitf.ttl + this file → FAIL (missing).
- [ ] **Step 2: Author the module**

```turtle
@prefix nitf: <https://hexplain.io/ns/profile/nitf#> .
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .

<https://hexplain.io/ns/profile/nitf/tre/rpc00b> a owl:Ontology ;
    owl:imports <https://hexplain.io/ns/profile/nitf> ;
    rdfs:label "NITF TRE — RPC00B (rational polynomial camera, STDI-0002)" ;
    rdfs:comment "CEDATA layout for the RPC00B controlled extension (CETAG=RPC00B, CEL=1041)." .

nitf:RPC00B a bddo:Struct ; rdfs:label "RPC00B TRE payload" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( nitf:RPC_SUCCESS nitf:RPC_ERR_BIAS nitf:RPC_ERR_RAND
      nitf:RPC_LINE_OFF nitf:RPC_SAMP_OFF nitf:RPC_LAT_OFF nitf:RPC_LONG_OFF nitf:RPC_HEIGHT_OFF
      nitf:RPC_LINE_SCALE nitf:RPC_SAMP_SCALE nitf:RPC_LAT_SCALE nitf:RPC_LONG_SCALE nitf:RPC_HEIGHT_SCALE
      nitf:RPC_LINE_NUM_COEFF nitf:RPC_LINE_DEN_COEFF nitf:RPC_SAMP_NUM_COEFF nitf:RPC_SAMP_DEN_COEFF ) .

nitf:RPC_SUCCESS a bddo:Field ; rdfs:label "SUCCESS" ; bddo:dataType nitf:BCSNpos ; bddo:size 1 .
nitf:RPC_ERR_BIAS a bddo:Field ; rdfs:label "ERR_BIAS" ; bddo:dataType nitf:BCSN ; bddo:size 7 .
nitf:RPC_ERR_RAND a bddo:Field ; rdfs:label "ERR_RAND" ; bddo:dataType nitf:BCSN ; bddo:size 7 .
nitf:RPC_LINE_OFF a bddo:Field ; rdfs:label "LINE_OFF" ; bddo:dataType nitf:BCSNpos ; bddo:size 6 .
nitf:RPC_SAMP_OFF a bddo:Field ; rdfs:label "SAMP_OFF" ; bddo:dataType nitf:BCSNpos ; bddo:size 5 .
nitf:RPC_LAT_OFF a bddo:Field ; rdfs:label "LAT_OFF" ; bddo:dataType nitf:BCSN ; bddo:size 8 .
nitf:RPC_LONG_OFF a bddo:Field ; rdfs:label "LONG_OFF" ; bddo:dataType nitf:BCSN ; bddo:size 9 .
nitf:RPC_HEIGHT_OFF a bddo:Field ; rdfs:label "HEIGHT_OFF" ; bddo:dataType nitf:BCSN ; bddo:size 5 .
nitf:RPC_LINE_SCALE a bddo:Field ; rdfs:label "LINE_SCALE" ; bddo:dataType nitf:BCSNpos ; bddo:size 6 .
nitf:RPC_SAMP_SCALE a bddo:Field ; rdfs:label "SAMP_SCALE" ; bddo:dataType nitf:BCSNpos ; bddo:size 5 .
nitf:RPC_LAT_SCALE a bddo:Field ; rdfs:label "LAT_SCALE" ; bddo:dataType nitf:BCSN ; bddo:size 8 .
nitf:RPC_LONG_SCALE a bddo:Field ; rdfs:label "LONG_SCALE" ; bddo:dataType nitf:BCSN ; bddo:size 9 .
nitf:RPC_HEIGHT_SCALE a bddo:Field ; rdfs:label "HEIGHT_SCALE" ; bddo:dataType nitf:BCSN ; bddo:size 5 .
# Four coefficient arrays: 20 coefficients each, 12 chars per coefficient.
nitf:RPC_LINE_NUM_COEFF a bddo:Field ; rdfs:label "LINE_NUM_COEFF (20 × 12)" ;
    bddo:dataType nitf:BCSN ; bddo:size 12 ; bddo:repeatCount 20 .
nitf:RPC_LINE_DEN_COEFF a bddo:Field ; rdfs:label "LINE_DEN_COEFF (20 × 12)" ;
    bddo:dataType nitf:BCSN ; bddo:size 12 ; bddo:repeatCount 20 .
nitf:RPC_SAMP_NUM_COEFF a bddo:Field ; rdfs:label "SAMP_NUM_COEFF (20 × 12)" ;
    bddo:dataType nitf:BCSN ; bddo:size 12 ; bddo:repeatCount 20 .
nitf:RPC_SAMP_DEN_COEFF a bddo:Field ; rdfs:label "SAMP_DEN_COEFF (20 × 12)" ;
    bddo:dataType nitf:BCSN ; bddo:size 12 ; bddo:repeatCount 20 .
```

- [ ] **Step 3: Run harness** → PASS. (Each coefficient field has exactly one sizing mechanism `size` plus one repetition mechanism `repeatCount` — allowed; `FieldSizingShape` and `FieldRepetitionShape` each permit one.)
- [ ] **Step 4: Commit** — `git add specification/profiles/nitf/nitf-tre-rpc00b.ttl && git commit -m "feat(nitf): RPC00B TRE module"`

---

## Task 11: Valid worked example (`example.ttl`)

**Files:** Create `specification/profiles/nitf/example.ttl`.
**Interfaces:** A semantic instance graph illustrating the parse output — must parse cleanly and conform.

- [ ] **Step 1: Failing test** — `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl specification/profiles/nitf/example.ttl` → FAIL (missing).
- [ ] **Step 2: Author the instance** (values from Table II — a 1332×2050, 8-bit, uncompressed, unclassified single-band VIS image):

```turtle
# Worked instance: the semantic graph a conforming processor emits for a small NITF file.
@prefix ex:      <https://example.org/data/> .
@prefix nitf:    <https://hexplain.io/ns/profile/nitf#> .
@prefix gv:      <https://hexplain.io/ns/geo#> .
@prefix araster: <https://hexplain.io/ns/aspect/raster#> .
@prefix asec:    <https://hexplain.io/ns/aspect/security#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

ex:sample-nitf a gv:RasterDataset ;
    dcterms:conformsTo <https://hexplain.io/ns/profile/nitf/1.0> ;
    asec:classificationLevel "U" ;
    araster:width 2050 ;
    araster:height 1332 .
```

- [ ] **Step 3: Run harness** → PASS (`Conforms: True`; no bddo/core shape targets these instance triples, so it conforms as long as it parses and violates nothing).
- [ ] **Step 4: Commit** — `git add specification/profiles/nitf/example.ttl && git commit -m "docs(nitf): worked valid instance example"`

---

## Task 12: Invalid example (`example-invalid.ttl`) — proves the shapes bite

**Files:** Create `specification/profiles/nitf/example-invalid.ttl`.
**Interfaces:** A deliberately malformed `bddo:Field` that MUST trigger a bddo shape violation, proving the harness and shapes catch errors.

- [ ] **Step 1: Author the malformed fragment**

```turtle
# Deliberately invalid: a Field declaring TWO sizing mechanisms — must fail FieldSizingShape.
@prefix nitf: <https://hexplain.io/ns/profile/nitf#> .
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

nitf:BadField a bddo:Field ; rdfs:label "invalid — two sizing mechanisms" ;
    bddo:dataType nitf:BCSA ; bddo:size 4 ; bddo:sizeFromField nitf:TRE_CEL .
```

- [ ] **Step 2: Run the harness and confirm it FAILS**

Run: `python tools/shacl_check.py specification/profiles/nitf/nitf.ttl specification/profiles/nitf/example-invalid.ttl`
Expected: FAIL (exit 1). The report must name `FieldSizingShape` (SPARQL constraint: "a bddo:Field must use at most one sizing/termination mechanism"). This is the intended, documented failure.

- [ ] **Step 3: Record the expected failure and commit**

Add a header comment to the file noting the expected violation, then:
```bash
git add specification/profiles/nitf/example-invalid.ttl
git commit -m "docs(nitf): SHACL-failing example proving shape enforcement"
```

---

## Self-review

**Spec coverage** (design §§1–11):
- §3 file layout → Tasks 2–12 create exactly the five files + harness. ✓
- §4 data types → Task 2. ✓
- §5.1 file header + segment tables + extension areas → Task 4. ✓
- §5.2 image subheader + band loop + IGEOLO/COMRAT conditionals → Task 5. ✓
- §5.3–5.6 graphic/text/DES/RES → Tasks 6–7. ✓
- §6 generic TRE → Task 3. ✓
- §7 BLOCKA/RPC00B → Tasks 9–10. ✓
- §8 semantic lift + gap log → Task 8. ✓
- §9 validation + valid/invalid examples → Tasks 1, 11, 12. ✓
- §10 sources of truth / STDI-0002 caveat → Global Constraints + Tasks 9/10 comments. ✓
- §11 build sequence → task order matches. ✓

**Placeholder scan:** long mechanical field lists are given as complete exact tables (name/size/type) plus the full TTL rendering pattern — every field is fully specified, no "TBD"/"handle the rest". The LUT sub-loop and DESDATA/RESDATA TRE-sequence bodies are explicitly scoped out with `rdfs:comment`, matching design non-goals (not placeholders).

**Type consistency:** field IRIs referenced across tasks are consistent — `nitf:IS_NROWS`/`nitf:IS_NCOLS`/`nitf:IS_ISCLAS`/`nitf:FH_FSCLAS` defined in Tasks 4–5 and consumed in Task 8; `nitf:TRE`/`nitf:TRE_CEL` defined in Task 3, consumed in Tasks 4/5/6/7/12; data types `nitf:BCSA`/`nitf:BCSN`/`nitf:BCSNpos`/`nitf:ECSA` defined in Task 2, used throughout. Harness command form is identical in every task.
