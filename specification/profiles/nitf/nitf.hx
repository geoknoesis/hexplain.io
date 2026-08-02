// Hexplain Description Language (HDL) — NGA NITF 2.1 (MIL-STD-2500C)
// Authoring surface for the profile whose canonical compiled form is nitf.ttl.
// NOTE: compiles via the `hdl` module in hexplain-tools (io.hexplain.hdl.HdlCompiler;
// `.hx`/`.yaml` CLI). nitf.ttl is the hand-written equivalent. Every field below carries an
// `as FH_*`/`IS_*`/... alias so its minted IRI matches nitf.ttl's flat FH_/IS_ names exactly
// (HDL's default, unaliased form is a dotted `nitf:FileHeader.FHDR`) -- except SecurityMarking's
// 16 fields, which stay dotted: that struct is shared across six segments but the TTL inlines it
// with six different segment-specific prefixes (FH_FS*, IS_IS*, GS_SS*, TS_TS*, DES_DE(S)*,
// RES_RE*), so there is no single correct target name (a residual left for a future lift rule).
//
// STATUS — aligned with the P0 vocabulary extensions (2026-08-02).
// nitf.ttl remains authoritative; this file is the authoring surface and is kept in step
// with it. The three expression defects previously recorded here are resolved, because
// each was a workaround for something the vocabulary could not express before P0:
//   1. `@prop bddo:repeatUntil "end-of-region"` — that was never a HEL sentinel.
//      Now written with the native clause `repeat until eof()`.
//   2. `@prop bddo:sizeFromExpression "UDHDL - 3"` failed because `ascii[5]` parses to a
//      String and HEL rejects arithmetic on a non-numeric operand. The length fields are
//      now `anum[5]` (bddo:asciiInteger), whose HEL value is an Integer, so the
//      subtraction is valid without any coercion.
//   3. `@prop hexplain:valueExpression "xsd:integer(NROWS)"` invoked a function that does
//      not exist. NROWS/NCOLS are now `anum[8]` and yield Integers natively, so the
//      coercion is simply deleted rather than renamed.
// Where a number must still be read out of a genuinely textual field, HEL's function is
// `toNumber(...)` — not `number(...)`, and not `xsd:integer(...)`.
//
// Idiomatic choices (vs the hand-written TTL):
//   * BCS-A text fields are modeled as ascii[N]; BCS-N positive integers as anum[N]
//     (the digits-only restriction remains documentary — BDDO has no character-class
//     facet — but the numeric-vs-text distinction is now load-bearing, not cosmetic).
//   * The 16-field security block, repeated inline six times in the TTL, is factored into
//     one reusable `SecurityMarking` struct included as a nested field (its own field IRIs are
//     therefore left in HDL's dotted form, e.g. nitf:SecurityMarking.CLAS — see the file-header
//     note above). This attaches the asec:* markings to a per-segment marking resource (vs
//     flat-on-dataset in the TTL) — a deliberate HDL composition choice; a lift rule can flatten
//     it if required.
//   * TRE overflow areas (a sized region that then repeats TREs) use the @prop escape
//     hatch — the one NITF construct without dedicated HDL sugar.

format nitf
  @namespace "https://hexplain.io/ns/profile/nitf#"
  @endian big

use araster: <https://hexplain.io/ns/aspect/raster#>
use asec:    <https://hexplain.io/ns/aspect/security#>
use gv:      <https://hexplain.io/ns/geo#>
// nitf/vann below exist only so the format-scoped `raw-turtle` block in FileHeader (Task 6 Part B)
// can quote nitf.ttl's ontology header and custom bddo:DataType individuals verbatim — bddo/rdfs/
// xsd/owl/dcterms are already predeclared by io.hexplain.hdl.resolve.Resolver.PREDECLARED and need
// no `use` here, but "nitf" (the base namespace under an explicit prefix, vs the bare `:` HDL mints
// from @namespace) and "vann" are not, and TurtleEmitter.mergeRaw's prelude only includes prefixes
// from this `use` list -- an undeclared one would fail the embedded Turtle parse.
use nitf:    <https://hexplain.io/ns/profile/nitf#>
use vann:    <http://purl.org/vocab/vann/>

// =========================================================
// Reusable structs
// =========================================================

// Generic Tagged Record Extension (Table A-7), with tag dispatch to specific payloads.
struct TRE {
  CETAG  as TRE_CETAG  : ascii[6]
  CEL    as TRE_CEL    : ascii[5]
  CEDATA as TRE_CEDATA : bytes[CEL] switch CETAG {
             "BLOCKA" => BLOCKA
             "RPC00B" => RPC00B
           }
}

// Security marking block (16 fields; identical layout across all NITF subheaders),
// wired to the hx-security aspect. Concept-valued fields carry an enum raw->concept map;
// large registers (codewords, exemptions) are left physical with a pointer comment.
struct SecurityMarking {
  CLAS : ascii[1]  enum { "T"=>asec:TopSecret, "S"=>asec:Secret, "C"=>asec:Confidential,
                          "R"=>asec:Restricted, "U"=>asec:Unclassified } means asec:classification
  CLSY : ascii[2]  means asec:classificationSystem
  CODE : ascii[11] // codewords -> asec:compartment (asec:MarkingScheme; space-separated digraphs)
  CTLH : ascii[2]  // control/handling -> asec:controlAndHandling (asec:MarkingScheme)
  REL  : ascii[20] means asec:releasableTo
  DCTP : ascii[2]  enum { "DD"=>asec:DeclassifyOnDate, "DE"=>asec:DeclassifyOnEvent,
                          "GD"=>asec:DowngradeOnDate, "GE"=>asec:DowngradeOnEvent,
                          "O"=>asec:Oadr, "X"=>asec:ExemptFromAutomatic } means asec:declassificationType
  DCDT : ascii[8]  means asec:declassificationDate
  DCXM : ascii[4]  // -> asec:declassificationExemption (asec:ExemptionScheme)
  DG   : ascii[1]  enum { "S"=>asec:Secret, "C"=>asec:Confidential, "R"=>asec:Restricted } means asec:downgradeTo
  DGDT : ascii[8]  means asec:downgradeDate
  CLTX : ascii[43] means asec:classificationText
  CATP : ascii[1]  enum { "O"=>asec:OriginalAuthority, "D"=>asec:DerivativeSingle,
                          "M"=>asec:DerivativeMultiple } means asec:classificationAuthorityType
  CAUT : ascii[40] means asec:classificationAuthority
  CRSN : ascii[1]  enum { "A"=>asec:ReasonA, "B"=>asec:ReasonB, "C"=>asec:ReasonC, "D"=>asec:ReasonD,
                          "E"=>asec:ReasonE, "F"=>asec:ReasonF, "G"=>asec:ReasonG } means asec:classificationReason
  SRDT : ascii[8]  means asec:securitySourceDate
  CTLN : ascii[15] means asec:securityControlNumber
}

// File-header segment-length table pairs (Table A-1). These pairs live inside the FileHeader's
// segment tables (Table A-1), so nitf.ttl names their fields with the FH_ prefix, not one derived
// from these struct names -- FH_LISHn/FH_LIn etc. (RESegLen's ttl counterpart is even named
// "LRESHn", not "LRSHn": the ttl author expanded "LRSH" to "LRESH" for the pair's label, so the
// `as` target follows ttl's actual field name, not a mechanical prefix+DSL-name transform).
struct ImageSegLen   { LISH as FH_LISHn  : ascii[6]  LI  as FH_LIn  : ascii[10] }
struct GraphicSegLen { LSSH as FH_LSSHn  : ascii[4]  LS  as FH_LSn  : ascii[6]  }
struct TextSegLen    { LTSH as FH_LTSHn  : ascii[4]  LT  as FH_LTn  : ascii[5]  }
struct DESegLen      { LDSH as FH_LDSHn  : ascii[4]  LD  as FH_LDn  : ascii[9]  }
struct RESegLen      { LRSH as FH_LRESHn : ascii[4]  LRE as FH_LREn : ascii[7]  }

// Per-band record inside the image subheader (Table A-3 band loop).
struct ImageBand {
  IREPBAND as IB_IREPBAND : ascii[2]
  ISUBCAT  as IB_ISUBCAT  : ascii[6]
  IFC      as IB_IFC      : ascii[1]
  IMFLT    as IB_IMFLT    : ascii[3]
  NLUTS    as IB_NLUTS    : ascii[1]   // when != 0, NELUT(5)+LUTD data follow (deferred)
}

// =========================================================
// File header (Table A-1)
// =========================================================
struct FileHeader {
  FHDR     as FH_FHDR    : ascii[4]  @fixed "NITF"
  FVER     as FH_FVER    : ascii[5]  @fixed "02.10"
  CLEVEL   as FH_CLEVEL  : ascii[2]
  STYPE    as FH_STYPE   : ascii[4]  @fixed "BF01"
  OSTAID   as FH_OSTAID  : ascii[10]
  FDT      as FH_FDT     : ascii[14]
  FTITLE   as FH_FTITLE  : ascii[80]
  security : SecurityMarking
  FSCOP    as FH_FSCOP   : ascii[5]
  FSCPYS   as FH_FSCPYS  : ascii[5]
  ENCRYP   as FH_ENCRYP  : ascii[1]
  FBKGC    as FH_FBKGC   : bytes[3]
  ONAME    as FH_ONAME   : ascii[24]
  OPHONE   as FH_OPHONE  : ascii[18]
  FL       as FH_FL      : ascii[12]
  HL       as FH_HL      : ascii[6]
  NUMI     as FH_NUMI    : ascii[3]
  // `repeat [NUMI]` (bracketed) rather than bare `repeat NUMI`: HdlParser's exprFromAccessorRun()
  // detects "next field starts here" only via an unaliased `IDENT COLON` lookahead, so a bare run
  // would swallow the next field's own name once that field carries its own `as` alias (verified
  // against the compiler; the unbracketed form reproducibly mis-parses here). Same reason on every
  // other bracketed `if [...]`/`repeat [...]`/`repeat until [...]` guard added in this file --
  // each precedes a field that is itself aliased below. HelSynth's rewriter only recognizes
  // single-quoted strings (core's HEL lexer, same rule), so literal comparisons use `'x'` inside
  // the brackets even though the unbracketed originals were DSL double-quoted `"x"`.
  imageSegs   as FH_ImageSegTable   : ImageSegLen   repeat [NUMI]
  NUMS     as FH_NUMS    : ascii[3]
  graphicSegs as FH_GraphicSegTable : GraphicSegLen repeat [NUMS]
  NUMX     as FH_NUMX    : ascii[3]  @fixed "000"
  NUMT     as FH_NUMT    : ascii[3]
  textSegs    as FH_TextSegTable    : TextSegLen    repeat [NUMT]
  NUMDES   as FH_NUMDES  : ascii[3]
  deSegs      as FH_DESegTable      : DESegLen      repeat [NUMDES]
  NUMRES   as FH_NUMRES  : ascii[3]
  resSegs     as FH_RESegTable      : RESegLen      repeat [NUMRES]
  UDHDL    as FH_UDHDL   : anum[5]
  UDHOFL   as FH_UDHOFL  : ascii[3]  if [UDHDL != 0]
  UDHD     as FH_UDHD    : TRE if UDHDL != 0 @prop bddo:sizeFromExpression "UDHDL - 3" repeat until [eof()]
  XHDL     as FH_XHDL    : anum[5]
  XHDLOFL  as FH_XHDLOFL : ascii[3]  if [XHDL != 0]
  // Bracketed `repeat until [eof()]` here too, even though XHD looks like the struct's last field:
  // the `raw-turtle` keyword right after it is itself an IDENT token to the lexer (its `{...}` body
  // is lexed as a single opaque RAW_BLOCK, with no separate LBRACE the unbracketed accessor-run
  // loop could stop on), so an unbracketed trailing expression here would swallow both the
  // "raw-turtle" token and the entire RAW_BLOCK text into XHD's HEL expression -- verified against
  // the compiler; unbracketed reproducibly corrupts this field and silently drops the block below.
  XHD      as FH_XHD     : TRE if XHDL != 0 @prop bddo:sizeFromExpression "XHDL - 3" repeat until [eof()]

  // ---- Non-HDL-expressible triples, carried verbatim from nitf.ttl (Task 6 Part B) ----
  // Format-level `raw-turtle` does not exist: HdlParser.parseStruct() is the only place that
  // accepts the `raw-turtle` keyword (io.hexplain.hdl.parse.Parser.kt, both the top-level `parse()`
  // dispatch loop and `parseFormat()` have no such branch), so this is anchored on FileHeader --
  // the format's root segment -- purely as a syntactic home. The emitted triples are ordinary
  // top-level RDF regardless of which struct's raw-turtle block declares them.
  raw-turtle {
    <https://hexplain.io/ns/profile/nitf> a owl:Ontology ;
        owl:imports <https://hexplain.io/ns/core> ;
        dcterms:created "2026-07-26"^^xsd:date ; dcterms:creator <https://geoknoesis.com> ;
        dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
        vann:preferredNamespacePrefix "nitf" ; vann:preferredNamespaceUri "https://hexplain.io/ns/profile/nitf#" .

    nitf:BCSA a bddo:DataType ; rdfs:label "BCS-A (alphanumeric text)" ;
        bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .
    nitf:BCSN a bddo:DataType ; rdfs:label "BCS-N (numeric text: digits + . / + -)" ;
        bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .
    nitf:BCSNpos a bddo:DataType ; rdfs:label "BCS-N positive integer (digits only)" ;
        rdfs:comment "NITF BCS-N restricted to digits: counts, lengths and dimensions. Carries bddo:asciiInteger semantics -- the field width comes from bddo:size and the parsed HEL value is an Integer, so it drives sizeFromExpression / atOffsetFromExpression / repeatCountFromExpression directly, with no toNumber() coercion. Contrast nitf:BCSN, which stays textual because it also carries CCYYMMDDhhmmss date-times." ;
        bddo:baseType bddo:baseInteger ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:integer .
    nitf:ECSA a bddo:DataType ; rdfs:label "ECS-A (restricted to BCS-A subset)" ;
        bddo:baseType bddo:baseString ; bddo:encoding bddo:ascii ; bddo:xsdType xsd:string .
  }
}

// =========================================================
// Image subheader (Table A-3)
// =========================================================
struct ImageSubheader means gv:RasterDataset {
  IM       as IS_IM      : ascii[2]  @fixed "IM"
  IID1     as IS_IID1    : ascii[10]
  IDATIM   as IS_IDATIM  : ascii[14]
  TGTID    as IS_TGTID   : ascii[17]
  IID2     as IS_IID2    : ascii[80]
  security : SecurityMarking
  ENCRYP   as IS_ENCRYP  : ascii[1]
  ISORCE   as IS_ISORCE  : ascii[42]
  NROWS    as IS_NROWS   : anum[8]  means araster:height
  NCOLS    as IS_NCOLS   : anum[8]  means araster:width
  PVTYPE   as IS_PVTYPE  : ascii[3]  enum { "INT"=>Int, "B"=>BiLevel, "SI"=>Signed, "R"=>Real, "C"=>Complex }
  IREP     as IS_IREP    : ascii[8]  // enum over MONO/RGB/RGB-LUT/MULTI/NODISPLY/NVECTOR/POLAR/VPH/YCbCr601
  ICAT     as IS_ICAT    : ascii[8]
  ABPP     as IS_ABPP    : ascii[2]
  PJUST    as IS_PJUST   : ascii[1]
  ICORDS   as IS_ICORDS  : ascii[1]
  // Bracketed guards below: HdlParser's exprFromAccessorRun() only recognizes an unaliased
  // `IDENT COLON` as "next field starts here", so once the following field carries its own `as`
  // alias a bare trailing expression here would swallow that field's name (verified against the
  // compiler). HelSynth's rewriter (like core's HEL lexer) only recognizes single-quoted strings,
  // so literal comparisons use `'x'` inside the brackets even though the DSL source is `"x"`.
  IGEOLO   as IS_IGEOLO  : ascii[60] if [ICORDS != ' ']
  NICOM    as IS_NICOM   : ascii[1]
  ICOM     as IS_ICOM    : ascii[80] repeat [NICOM]
  IC       as IS_IC      : ascii[2]  // enum over NC/NM/C1/C3-C8/I1/M1/M3-M8
  COMRAT   as IS_COMRAT  : ascii[4]  if [IC != 'NC' and IC != 'NM']
  NBANDS   as IS_NBANDS  : ascii[1]
  XBANDS   as IS_XBANDS  : ascii[5]  if [NBANDS == '0']
  bands    as IS_BandTable : ImageBand repeat [NBANDS]
  ISYNC    as IS_ISYNC   : ascii[1]
  IMODE    as IS_IMODE   : ascii[1]  enum { "B"=>BlockInterleaved, "P"=>PixelInterleaved, "R"=>RowInterleaved, "S"=>BandSequential }
  NBPR     as IS_NBPR    : ascii[4]
  NBPC     as IS_NBPC    : ascii[4]
  NPPBH    as IS_NPPBH   : ascii[4]
  NPPBV    as IS_NPPBV   : ascii[4]
  NBPP     as IS_NBPP    : ascii[2]
  IDLVL    as IS_IDLVL   : ascii[3]
  IALVL    as IS_IALVL   : ascii[3]
  ILOC     as IS_ILOC    : ascii[10]
  IMAG     as IS_IMAG    : ascii[4]
  UDIDL    as IS_UDIDL   : anum[5]
  UDOFL    as IS_UDOFL   : ascii[3]  if [UDIDL != 0]
  UDID     as IS_UDID    : TRE if UDIDL != 0 @prop bddo:sizeFromExpression "UDIDL - 3" repeat until [eof()]
  IXSHDL   as IS_IXSHDL  : anum[5]
  IXSOFL   as IS_IXSOFL  : ascii[3]  if [IXSHDL != 0]
  IXSHD    as IS_IXSHD   : TRE if IXSHDL != 0 @prop bddo:sizeFromExpression "IXSHDL - 3" repeat until eof()
}

// =========================================================
// Graphic subheader (Table A-5)
// =========================================================
struct GraphicSubheader {
  SY       as GS_SY      : ascii[2]  @fixed "SY"
  SID      as GS_SID     : ascii[10]
  SNAME    as GS_SNAME   : ascii[20]
  security : SecurityMarking
  ENCRYP   as GS_ENCRYP  : ascii[1]
  SFMT     as GS_SFMT    : ascii[1]  @fixed "C"
  SSTRUCT  as GS_SSTRUCT : ascii[13]
  SDLVL    as GS_SDLVL   : ascii[3]
  SALVL    as GS_SALVL   : ascii[3]
  SLOC     as GS_SLOC    : ascii[10]
  SBND1    as GS_SBND1   : ascii[10]
  SCOLOR   as GS_SCOLOR  : ascii[1]
  SBND2    as GS_SBND2   : ascii[10]
  SRES2    as GS_SRES2   : ascii[2]
  SXSHDL   as GS_SXSHDL  : anum[5]
  // Bracketed guard: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field (SXSHD) carries its own `as` alias.
  SXSOFL   as GS_SXSOFL  : ascii[3]  if [SXSHDL != 0]
  SXSHD    as GS_SXSHD   : TRE if SXSHDL != 0 @prop bddo:sizeFromExpression "SXSHDL - 3" repeat until eof()
}

// =========================================================
// Text subheader (Table A-6)
// =========================================================
struct TextSubheader {
  TE       as TS_TE      : ascii[2]  @fixed "TE"
  TEXTID   as TS_TEXTID  : ascii[7]
  TXTALVL  as TS_TXTALVL : ascii[3]
  TXTDT    as TS_TXTDT   : ascii[14]
  TXTITL   as TS_TXTITL  : ascii[80]
  security : SecurityMarking
  ENCRYP   as TS_ENCRYP  : ascii[1]
  TXTFMT   as TS_TXTFMT  : ascii[3]  enum { "STA"=>Standard, "MTF"=>MessageTextFormat, "UT1"=>EcsText, "U8S"=>U8sText }
  TXSHDL   as TS_TXSHDL  : anum[5]
  // Bracketed guard: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field (TXSHD) carries its own `as` alias.
  TXSOFL   as TS_TXSOFL  : ascii[3]  if [TXSHDL != 0]
  TXSHD    as TS_TXSHD   : TRE if TXSHDL != 0 @prop bddo:sizeFromExpression "TXSHDL - 3" repeat until eof()
}

// =========================================================
// Data Extension Segment subheader (Table A-8)
// =========================================================
struct DESubheader {
  DE       as DES_DE     : ascii[2]  @fixed "DE"
  DESID    as DES_DESID  : ascii[25]
  DESVER   as DES_DESVER : ascii[2]
  security : SecurityMarking
  // Bracketed guards: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field carries its own `as` alias, and why literal
  // comparisons use `'x'` (HelSynth/HEL only recognize single-quoted strings) instead of the DSL's
  // own `"x"`.
  DESOFLW  as DES_DESOFLW : ascii[6]  if [DESID == 'TRE_OVERFLOW']
  DESITEM  as DES_DESITEM : ascii[3]  if [DESID == 'TRE_OVERFLOW']
  DESSHL   as DES_DESSHL  : anum[4]
  DESSHF   as DES_DESSHF  : ascii[DESSHL] if [DESSHL != 0]
  DESDATA  as DES_DESDATA : bytes[..]   // for DESID = TRE_OVERFLOW this is a TRE sequence
}

// =========================================================
// Reserved Extension Segment subheader (Table A-9)
// =========================================================
struct RESubheader {
  RE       as RES_RE     : ascii[2]  @fixed "RE"
  RESID    as RES_RESID  : ascii[25]
  RESVER   as RES_RESVER : ascii[2]
  security : SecurityMarking
  RESSHL   as RES_RESSHL  : anum[4]
  // Bracketed guard: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field (RESDATA) carries its own `as` alias.
  RESSHF   as RES_RESSHF  : ascii[RESSHL] if [RESSHL != 0]
  RESDATA  as RES_RESDATA : bytes[..]
}

// =========================================================
// Worked TRE payloads (STDI-0002)
// =========================================================
struct BLOCKA {                                  // CEL 123
  BLOCK_INSTANCE : ascii[2]
  N_GRAY         : ascii[5]
  L_LINES        : ascii[5]
  LAYOVER_ANGLE  : ascii[3]
  SHADOW_ANGLE   : ascii[3]
  reserved1      : bytes[16]
  FRLC_LOC       : ascii[21]
  LRLC_LOC       : ascii[21]
  LRFC_LOC       : ascii[21]
  FRFC_LOC       : ascii[21]
  reserved2      : bytes[5]
}

struct RPC00B {                                  // CEL 1041 = 81 + 4x(20x12)
  SUCCESS      : ascii[1]
  ERR_BIAS     : ascii[7]
  ERR_RAND     : ascii[7]
  LINE_OFF     : ascii[6]
  SAMP_OFF     : ascii[5]
  LAT_OFF      : ascii[8]
  LONG_OFF     : ascii[9]
  HEIGHT_OFF   : ascii[5]
  LINE_SCALE   : ascii[6]
  SAMP_SCALE   : ascii[5]
  LAT_SCALE    : ascii[8]
  LONG_SCALE   : ascii[9]
  HEIGHT_SCALE : ascii[5]
  LINE_NUM_COEFF : ascii[12] repeat 20
  LINE_DEN_COEFF : ascii[12] repeat 20
  SAMP_NUM_COEFF : ascii[12] repeat 20
  SAMP_DEN_COEFF : ascii[12] repeat 20
}
