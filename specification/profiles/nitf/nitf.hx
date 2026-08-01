// Hexplain Description Language (HDL) — NGA NITF 2.1 (MIL-STD-2500C)
// Authoring surface for the profile whose canonical compiled form is nitf.ttl.
// NOTE: compiles via the `hdl` module in hexplain-tools (io.hexplain.hdl.HdlCompiler;
// `.hx`/`.yaml` CLI). nitf.ttl is the hand-written equivalent. A compile of THIS file
// emits HDL's dotted-IRI structs (e.g. nitf:FileHeader.FHDR) rather than the TTL's
// FH_/IS_ names, so the two are structurally equivalent, not byte-isomorphic.
//
// Idiomatic choices (vs the hand-written TTL):
//   * BCS-A / BCS-N text fields are modeled as ascii[N] (the BCS-N vs BCS-A distinction
//     in the TTL is documentary only — BDDO has no character-class facet).
//   * Field IRIs are HDL's dotted form, e.g. nitf:ImageSubheader.NROWS.
//   * The 16-field security block, repeated inline six times in the TTL, is factored into
//     one reusable `SecurityMarking` struct included as a nested field. This attaches the
//     asec:* markings to a per-segment marking resource (vs flat-on-dataset in the TTL) —
//     a deliberate HDL composition choice; a lift rule can flatten it if required.
//   * TRE overflow areas (a sized region that then repeats TREs) use the @prop escape
//     hatch — the one NITF construct without dedicated HDL sugar.

format nitf
  @namespace "https://hexplain.io/ns/profile/nitf#"
  @endian big

use araster: <https://hexplain.io/ns/aspect/raster#>
use asec:    <https://hexplain.io/ns/aspect/security#>
use gv:      <https://hexplain.io/ns/geo#>

// =========================================================
// Reusable structs
// =========================================================

// Generic Tagged Record Extension (Table A-7), with tag dispatch to specific payloads.
struct TRE {
  CETAG  : ascii[6]
  CEL    : ascii[5]
  CEDATA : bytes[CEL] switch CETAG {
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

// File-header segment-length table pairs (Table A-1).
struct ImageSegLen   { LISH : ascii[6]  LI  : ascii[10] }
struct GraphicSegLen { LSSH : ascii[4]  LS  : ascii[6]  }
struct TextSegLen    { LTSH : ascii[4]  LT  : ascii[5]  }
struct DESegLen      { LDSH : ascii[4]  LD  : ascii[9]  }
struct RESegLen      { LRSH : ascii[4]  LRE : ascii[7]  }

// Per-band record inside the image subheader (Table A-3 band loop).
struct ImageBand {
  IREPBAND : ascii[2]
  ISUBCAT  : ascii[6]
  IFC      : ascii[1]
  IMFLT    : ascii[3]
  NLUTS    : ascii[1]   // when != 0, NELUT(5)+LUTD data follow (deferred)
}

// =========================================================
// File header (Table A-1)
// =========================================================
struct FileHeader {
  FHDR     : ascii[4]  @fixed "NITF"
  FVER     : ascii[5]  @fixed "02.10"
  CLEVEL   : ascii[2]
  STYPE    : ascii[4]  @fixed "BF01"
  OSTAID   : ascii[10]
  FDT      : ascii[14]
  FTITLE   : ascii[80]
  security : SecurityMarking
  FSCOP    : ascii[5]
  FSCPYS   : ascii[5]
  ENCRYP   : ascii[1]
  FBKGC    : bytes[3]
  ONAME    : ascii[24]
  OPHONE   : ascii[18]
  FL       : ascii[12]
  HL       : ascii[6]
  NUMI     : ascii[3]
  imageSegs   : ImageSegLen   repeat NUMI
  NUMS     : ascii[3]
  graphicSegs : GraphicSegLen repeat NUMS
  NUMX     : ascii[3]  @fixed "000"
  NUMT     : ascii[3]
  textSegs    : TextSegLen    repeat NUMT
  NUMDES   : ascii[3]
  deSegs      : DESegLen      repeat NUMDES
  NUMRES   : ascii[3]
  resSegs     : RESegLen      repeat NUMRES
  UDHDL    : ascii[5]
  UDHOFL   : ascii[3]  if UDHDL != "00000"
  UDHD     : TRE if UDHDL != "00000" @prop bddo:sizeFromExpression "UDHDL - 3" @prop bddo:repeatUntil "end-of-region"
  XHDL     : ascii[5]
  XHDLOFL  : ascii[3]  if XHDL != "00000"
  XHD      : TRE if XHDL != "00000" @prop bddo:sizeFromExpression "XHDL - 3" @prop bddo:repeatUntil "end-of-region"
}

// =========================================================
// Image subheader (Table A-3)
// =========================================================
struct ImageSubheader means gv:RasterDataset {
  IM       : ascii[2]  @fixed "IM"
  IID1     : ascii[10]
  IDATIM   : ascii[14]
  TGTID    : ascii[17]
  IID2     : ascii[80]
  security : SecurityMarking
  ENCRYP   : ascii[1]
  ISORCE   : ascii[42]
  NROWS    : ascii[8]  means araster:height @prop hexplain:valueExpression "xsd:integer(NROWS)" @prop hexplain:valueDatatype xsd:integer
  NCOLS    : ascii[8]  means araster:width  @prop hexplain:valueExpression "xsd:integer(NCOLS)" @prop hexplain:valueDatatype xsd:integer
  PVTYPE   : ascii[3]  enum { "INT"=>Int, "B"=>BiLevel, "SI"=>Signed, "R"=>Real, "C"=>Complex }
  IREP     : ascii[8]  // enum over MONO/RGB/RGB-LUT/MULTI/NODISPLY/NVECTOR/POLAR/VPH/YCbCr601
  ICAT     : ascii[8]
  ABPP     : ascii[2]
  PJUST    : ascii[1]
  ICORDS   : ascii[1]
  IGEOLO   : ascii[60] if ICORDS != " "
  NICOM    : ascii[1]
  ICOM     : ascii[80] repeat NICOM
  IC       : ascii[2]  // enum over NC/NM/C1/C3-C8/I1/M1/M3-M8
  COMRAT   : ascii[4]  if IC != "NC" and IC != "NM"
  NBANDS   : ascii[1]
  XBANDS   : ascii[5]  if NBANDS == "0"
  bands    : ImageBand repeat NBANDS
  ISYNC    : ascii[1]
  IMODE    : ascii[1]  enum { "B"=>BlockInterleaved, "P"=>PixelInterleaved, "R"=>RowInterleaved, "S"=>BandSequential }
  NBPR     : ascii[4]
  NBPC     : ascii[4]
  NPPBH    : ascii[4]
  NPPBV    : ascii[4]
  NBPP     : ascii[2]
  IDLVL    : ascii[3]
  IALVL    : ascii[3]
  ILOC     : ascii[10]
  IMAG     : ascii[4]
  UDIDL    : ascii[5]
  UDOFL    : ascii[3]  if UDIDL != "00000"
  UDID     : TRE if UDIDL != "00000" @prop bddo:sizeFromExpression "UDIDL - 3" @prop bddo:repeatUntil "end-of-region"
  IXSHDL   : ascii[5]
  IXSOFL   : ascii[3]  if IXSHDL != "00000"
  IXSHD    : TRE if IXSHDL != "00000" @prop bddo:sizeFromExpression "IXSHDL - 3" @prop bddo:repeatUntil "end-of-region"
}

// =========================================================
// Graphic subheader (Table A-5)
// =========================================================
struct GraphicSubheader {
  SY       : ascii[2]  @fixed "SY"
  SID      : ascii[10]
  SNAME    : ascii[20]
  security : SecurityMarking
  ENCRYP   : ascii[1]
  SFMT     : ascii[1]  @fixed "C"
  SSTRUCT  : ascii[13]
  SDLVL    : ascii[3]
  SALVL    : ascii[3]
  SLOC     : ascii[10]
  SBND1    : ascii[10]
  SCOLOR   : ascii[1]
  SBND2    : ascii[10]
  SRES2    : ascii[2]
  SXSHDL   : ascii[5]
  SXSOFL   : ascii[3]  if SXSHDL != "00000"
  SXSHD    : TRE if SXSHDL != "00000" @prop bddo:sizeFromExpression "SXSHDL - 3" @prop bddo:repeatUntil "end-of-region"
}

// =========================================================
// Text subheader (Table A-6)
// =========================================================
struct TextSubheader {
  TE       : ascii[2]  @fixed "TE"
  TEXTID   : ascii[7]
  TXTALVL  : ascii[3]
  TXTDT    : ascii[14]
  TXTITL   : ascii[80]
  security : SecurityMarking
  ENCRYP   : ascii[1]
  TXTFMT   : ascii[3]  enum { "STA"=>Standard, "MTF"=>MessageTextFormat, "UT1"=>EcsText, "U8S"=>U8sText }
  TXSHDL   : ascii[5]
  TXSOFL   : ascii[3]  if TXSHDL != "00000"
  TXSHD    : TRE if TXSHDL != "00000" @prop bddo:sizeFromExpression "TXSHDL - 3" @prop bddo:repeatUntil "end-of-region"
}

// =========================================================
// Data Extension Segment subheader (Table A-8)
// =========================================================
struct DESubheader {
  DE       : ascii[2]  @fixed "DE"
  DESID    : ascii[25]
  DESVER   : ascii[2]
  security : SecurityMarking
  DESOFLW  : ascii[6]  if DESID == "TRE_OVERFLOW"
  DESITEM  : ascii[3]  if DESID == "TRE_OVERFLOW"
  DESSHL   : ascii[4]
  DESSHF   : ascii[DESSHL] if DESSHL != "0000"
  DESDATA  : bytes[..]   // for DESID = TRE_OVERFLOW this is a TRE sequence
}

// =========================================================
// Reserved Extension Segment subheader (Table A-9)
// =========================================================
struct RESubheader {
  RE       : ascii[2]  @fixed "RE"
  RESID    : ascii[25]
  RESVER   : ascii[2]
  security : SecurityMarking
  RESSHL   : ascii[4]
  RESSHF   : ascii[RESSHL] if RESSHL != "0000"
  RESDATA  : bytes[..]
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
