// Hexplain Description Language (HDL) — NGA NITF 2.1 (MIL-STD-2500C)
// Authoring surface for the profile whose canonical compiled form is nitf.ttl.
// NOTE: compiles via the `hdl` module in hexplain-tools (io.hexplain.hdl.HdlCompiler;
// `.hx`/`.yaml` CLI). nitf.ttl is the hand-written equivalent. Every field below carries an
// `as FH_*`/`IS_*`/... alias so its minted IRI matches nitf.ttl's flat FH_/IS_ names exactly
// (HDL's default, unaliased form is a dotted `nitf:FileHeader.FHDR`).
//
// (2026-08-08) The 16-field security-marking block used to be factored into one reusable
// `struct SecurityMarking` referenced as a nested field from all six subheaders -- HDL mints
// one shared field IRI per struct (nitf:SecurityMarking.CLAS) but nitf.ttl inlines the same 16
// fields six times under six different segment-specific prefixes (FH_FS*, IS_IS*, GS_SS*,
// TS_TS*, DES_DE(S)*, RES_RE*), so no aliasing scheme could reconcile one shared subject
// against six textually-identical but IRI-distinct copies. The struct is now flattened: each
// of the six subheaders carries its own inline copy of the 16 fields, named to match nitf.ttl
// exactly via `as`. Every copy keeps the richer modeling nitf.ttl does not have -- concept-
// valued `enum` maps (e.g. "T"=>usnato:TopSecret, drawn from the us-nato-security register)
// and `means asec:*` mappings -- so the compiled output is a strict superset of nitf.ttl's
// security-block triples, not a smaller copy of it.
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
//   * The 16-field security block is inlined six times, once per subheader, matching nitf.ttl's
//     own flat FH_FS*/IS_IS*/GS_SS*/TS_TS*/DES_DE(S)*/RES_RE* names exactly (see the file-header
//     note above). Concept-valued fields (CLAS/DCTP/DG/CATP/CRSN) point at one of five named,
//     concept-valued `.hx`-level enums (SecurityClassificationEnum..ClassificationReasonEnum,
//     declared with the other named enums below). nitf.ttl now carries the same five concept
//     enumerations, drawing their concepts from the us-nato-security register named by its
//     register bindings; they subsumed its former raw-only nitf:FSCLASEnum. Declaring
//     these once and referencing them from all six subheaders (rather than repeating an inline
//     `enum { ... }` map at each of the 30 use sites) keeps the compiled output's enum structure
//     shared six ways instead of independently duplicated.
//   * TRE overflow areas (a sized region that then repeats TREs) use the @prop escape
//     hatch — the one NITF construct without dedicated HDL sugar.

format nitf
  @namespace "https://hexplain.io/ns/profile/nitf#"
  @endian big

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asec:    <https://hexplain.io/ns/aspect/security#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>
// Controlled security-marking concepts (classification levels, declassification/authority/
// reason codes) were split out of the asec: aspect into this standalone, swappable register
// (Task 3) -- the aspect keeps the *properties* (asec:classification, asec:downgradeTo, ...);
// the register supplies the *concepts* those properties point at. See nitf.ttl's ontology
// header for the corresponding hexplain:usesRegister bindings.
use usnato:  <https://hexplain.io/ns/register/us-nato-security#>
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
// Named enumerations (nitf.ttl declares these as labelled bddo:Enumeration
// individuals and points fields at them, rather than repeating an anonymous copy
// at each use site).
//
// These are VALID-VALUE SETS, not concept schemes: each value carries only its raw
// code, exactly as nitf.ttl does. They deliberately mint no `=> Symbol` IRIs -- doing
// so would fabricate undefined format-local individuals (nitf:C1, nitf:M3, ...) that
// nothing defines and nothing else references. Where a value really does denote a
// shared concept, bind it to a defined one instead -- see the five CONCEPT-VALUED named
// enums directly below (SecurityClassificationEnum..ClassificationReasonEnum), each an
// `raw=>Symbol` mapping into usnato:, the us-nato-security register (specification/register/
// us-nato-security/us-nato-security.ttl), used from the CLAS/DCTP/DG/CATP/CRSN fields of
// every one of the six security blocks inlined into FileHeader/ImageSubheader/
// GraphicSubheader/TextSubheader/DESubheader/RESubheader below.
// =========================================================
enum PVTYPEEnum @label "Pixel Value Type" { "INT", "B", "SI", "R", "C" }
enum IREPEnum @label "Image Representation" { "MONO", "RGB", "RGB/LUT", "MULTI", "NODISPLY",
       "NVECTOR", "POLAR", "VPH", "YCbCr601" }
enum ICEnum @label "Image Compression" { "NC", "NM", "C1", "C3", "C4", "C5", "C6", "C7",
       "C8", "I1", "M1", "M3", "M4", "M5", "M6", "M7", "M8" }
enum IMODEEnum @label "Image Mode" { "B", "P", "R", "S" }
enum TXTFMTEnum @label "Text Format" { "STA", "MTF", "UT1", "U8S" }
enum ICORDSEnum @label "Image Coordinate Representation" { "U", "G", "N", "S", "D", " " }

// ---------------------------------------------------------------------------
// CONCEPT-VALUED named enumerations for the security-marking block (below). Unlike the
// five raw-value-only enums above, each of these carries `raw=>Symbol` arms into usnato:,
// the us-nato-security register -- controlled security-marking concepts were split out of
// the asec: aspect into this standalone, swappable register (Task 3), so the concept side
// of each arm below is usnato:*, not asec:*; the `means asec:*` clause on the field that
// uses the enum (declared with the fields themselves, further below) still names the
// asec: *property* the enum's resolved concept is the value of -- that part is unchanged.
// HDL's `enum` grammar allows concept-valued arms on
// a top-level named declaration exactly as on a field-inline one, and the compiler mints
// ONE shared bddo:Enumeration individual for each, referenced (not re-inlined) by every
// field below that writes `enum <Name>` -- so the same CLAS/DCTP/DG/CATP/CRSN semantics
// used identically across all six subheaders are declared once and shared six ways,
// rather than compiled as six independent anonymous copies. nitf.ttl declares the same five
// shared enumerations with the same raw codes and the same usnato: concepts, so the two
// descriptions agree; together they subsumed its former raw-only nitf:FSCLASEnum, which
// carried the five classification codes with no concept attached.
enum SecurityClassificationEnum @label "Security Classification level" {
  "T"=>usnato:TopSecret, "S"=>usnato:Secret, "C"=>usnato:Confidential, "R"=>usnato:Restricted, "U"=>usnato:Unclassified
}
enum DeclassificationTypeEnum @label "Declassification Type" {
  "DD"=>usnato:DeclassifyOnDate, "DE"=>usnato:DeclassifyOnEvent, "GD"=>usnato:DowngradeOnDate,
  "GE"=>usnato:DowngradeOnEvent, "O"=>usnato:Oadr, "X"=>usnato:ExemptFromAutomatic
}
enum DowngradeToEnum @label "Downgrade To" { "S"=>usnato:Secret, "C"=>usnato:Confidential, "R"=>usnato:Restricted }
enum ClassificationAuthorityTypeEnum @label "Classification Authority Type" {
  "O"=>usnato:OriginalAuthority, "D"=>usnato:DerivativeSingle, "M"=>usnato:DerivativeMultiple
}
enum ClassificationReasonEnum @label "Classification Reason" {
  "A"=>usnato:ReasonA, "B"=>usnato:ReasonB, "C"=>usnato:ReasonC, "D"=>usnato:ReasonD,
  "E"=>usnato:ReasonE, "F"=>usnato:ReasonF, "G"=>usnato:ReasonG
}


// =========================================================
// Reusable structs
// =========================================================

// Generic Tagged Record Extension (Table A-7), with tag dispatch to specific payloads.
struct TRE @label "Tagged Record Extension" {
  CETAG  as TRE_CETAG  : nitf:BCSA[6] @label "CETAG/RETAG — 6-char tag"
  CEL    as TRE_CEL    : nitf:BCSNpos[5] @label "CEL/REL — length of CEDATA"
  CEDATA as TRE_CEDATA : bytes[CEL] switch CETAG {
             "BLOCKA" => BLOCKA
             "RPC00B" => RPC00B
           } @label "CEDATA/REDATA — user-defined data"
}

// File-header segment-length table pairs (Table A-1). These pairs live inside the FileHeader's
// segment tables (Table A-1), so nitf.ttl names their fields with the FH_ prefix, not one derived
// from these struct names -- FH_LISHn/FH_LIn etc. (RESegLen's ttl counterpart is even named
// "LRESHn", not "LRSHn": the ttl author expanded "LRSH" to "LRESH" for the pair's label, so the
// `as` target follows ttl's actual field name, not a mechanical prefix+DSL-name transform).
struct ImageSegLen as ImageSegLenPair   @label "{ LISHn, LIn }" { LISH as FH_LISHn  : ascii[6] @label "LISHn — length of nth image subheader"  LI  as FH_LIn  : ascii[10] @label "LIn — length of nth image segment" }
struct GraphicSegLen as GraphicSegLenPair @label "{ LSSHn, LSn }" { LSSH as FH_LSSHn  : ascii[4] @label "LSSHn — length of nth graphic subheader"  LS  as FH_LSn  : ascii[6] @label "LSn — length of nth graphic segment"  }
struct TextSegLen as TextSegLenPair    @label "{ LTSHn, LTn }" { LTSH as FH_LTSHn  : ascii[4] @label "LTSHn — length of nth text subheader"  LT  as FH_LTn  : ascii[5] @label "LTn — length of nth text segment"  }
struct DESegLen as DESegLenPair      @label "{ LDSHn, LDn }" { LDSH as FH_LDSHn  : ascii[4] @label "LDSHn — length of nth data extension segment subheader"  LD  as FH_LDn  : ascii[9] @label "LDn — length of nth data extension segment"  }
struct RESegLen as RESegLenPair      @label "{ LRESHn, LREn }" { LRSH as FH_LRESHn : ascii[4] @label "LRESHn — length of nth reserved extension segment subheader"  LRE as FH_LREn : ascii[7] @label "LREn — length of nth reserved extension segment"  }

// Per-band record inside the image subheader (Table A-3 band loop).
struct ImageBand @label "Image band record (Table A-3 band loop)" {
  IREPBAND as IB_IREPBAND : nitf:BCSA[2] @label "IREPBANDn"
  ISUBCAT  as IB_ISUBCAT  : nitf:BCSA[6] @label "ISUBCATn"
  IFC      as IB_IFC      : nitf:BCSA[1] @label "IFCn"
  IMFLT    as IB_IMFLT    : nitf:BCSA[3] @label "IMFLTn"
  NLUTS    as IB_NLUTS    : nitf:BCSNpos[1] @label "NLUTSn (LUT sub-loop omitted in cut #1)" @comment "When NLUTSn != 0, NELUTn(5) + LUTDnm data follow; LUT body deferred (see design non-goals)." // when != 0, NELUT(5)+LUTD data follow (deferred)
}

// =========================================================
// File header (Table A-1)
// =========================================================
struct FileHeader @label "NITF File Header (Table A-1)" {
  FHDR     as FH_FHDR    : nitf:BCSA[4]  @fixed "NITF" @label "FHDR — File Profile Name"
  FVER     as FH_FVER    : nitf:BCSA[5]  @fixed "02.10" @label "FVER — File Version"
  CLEVEL   as FH_CLEVEL  : nitf:BCSNpos[2] @label "CLEVEL — Complexity Level"
  STYPE    as FH_STYPE   : nitf:BCSA[4]  @fixed "BF01" @label "STYPE — Standard Type"
  OSTAID   as FH_OSTAID  : nitf:BCSA[10] @label "OSTAID — Originating Station ID"
  FDT      as FH_FDT     : nitf:BCSN[14] @label "FDT — File Date and Time (CCYYMMDDhhmmss)"
  FTITLE   as FH_FTITLE  : nitf:ECSA[80] @label "FTITLE — File Title"
  // ---- Security block (FSCLAS..FSCTLN), wired to the hx-security aspect (asec:*) ----
  // Concept-valued fields point at one of the five named CONCEPT-VALUED enums declared
  // near the top of this file (SecurityClassificationEnum..ClassificationReasonEnum).
  // nitf.ttl declares the same five, drawing their concepts from the us-nato-security
  // register named by its register bindings.
  // CODE/CTLH/DCXM are large open-ended registers (codewords, control/handling markings,
  // exemption codes) with no closed concept set today, so they stay physical-only with a
  // pointer comment to where they would attach once the aspect vocab grows a MarkingScheme.
  // FSCODE is nitf:BCSA here (unlike every other segment's CODE field, which is nitf:ECSA) --
  // that is nitf.ttl's own irregularity, reproduced verbatim, not introduced by this file.
  FSCLAS as FH_FSCLAS : nitf:ECSA[1]  enum SecurityClassificationEnum means asec:classification
                           @label "FSCLAS — File Security Classification"
  FSCLSY as FH_FSCLSY : nitf:ECSA[2]  means asec:classificationSystem @label "FSCLSY — File Security Classification System"
  FSCODE as FH_FSCODE : nitf:BCSA[11] @label "FSCODE — File Codewords" // -> asec:compartment (usnato:MarkingScheme; space-separated digraphs)
  FSCTLH as FH_FSCTLH : nitf:ECSA[2]  @label "FSCTLH — File Control and Handling" // -> asec:controlAndHandling (usnato:MarkingScheme)
  FSREL  as FH_FSREL  : nitf:ECSA[20] means asec:releasableTo @label "FSREL — File Releasing Instructions"
  FSDCTP as FH_FSDCTP : nitf:ECSA[2]  enum DeclassificationTypeEnum means asec:declassificationType
                           @label "FSDCTP — File Declassification Type"
  FSDCDT as FH_FSDCDT : nitf:ECSA[8]  means asec:declassificationDate @label "FSDCDT — File Declassification Date"
  FSDCXM as FH_FSDCXM : nitf:ECSA[4]  @label "FSDCXM — File Declassification Exemption" // -> asec:declassificationExemption (usnato:ExemptionScheme)
  FSDG   as FH_FSDG   : nitf:ECSA[1]  enum DowngradeToEnum means asec:downgradeTo @label "FSDG — File Downgrade"
  FSDGDT as FH_FSDGDT : nitf:ECSA[8]  means asec:downgradeDate @label "FSDGDT — File Downgrade Date"
  FSCLTX as FH_FSCLTX : nitf:ECSA[43] means asec:classificationText @label "FSCLTX — File Classification Text"
  FSCATP as FH_FSCATP : nitf:ECSA[1]  enum ClassificationAuthorityTypeEnum means asec:classificationAuthorityType
                           @label "FSCATP — File Classification Authority Type"
  FSCAUT as FH_FSCAUT : nitf:ECSA[40] means asec:classificationAuthority @label "FSCAUT — File Classification Authority"
  FSCRSN as FH_FSCRSN : nitf:ECSA[1]  enum ClassificationReasonEnum means asec:classificationReason
                           @label "FSCRSN — File Classification Reason"
  FSSRDT as FH_FSSRDT : nitf:ECSA[8]  means asec:securitySourceDate @label "FSSRDT — File Security Source Date"
  FSCTLN as FH_FSCTLN : nitf:ECSA[15] means asec:securityControlNumber @label "FSCTLN — File Security Control Number"
  FSCOP    as FH_FSCOP   : nitf:BCSNpos[5] @label "FSCOP — File Copy Number"
  FSCPYS   as FH_FSCPYS  : nitf:BCSNpos[5] @label "FSCPYS — File Number of Copies"
  ENCRYP   as FH_ENCRYP  : nitf:BCSNpos[1] @label "ENCRYP — Encryption"
  FBKGC    as FH_FBKGC   : bytes[3] @label "FBKGC — File Background Color (RGB)"
  ONAME    as FH_ONAME   : nitf:ECSA[24] @label "ONAME — Originator's Name"
  OPHONE   as FH_OPHONE  : nitf:ECSA[18] @label "OPHONE — Originator's Phone Number"
  FL       as FH_FL      : nitf:BCSNpos[12] @label "FL — File Length"
  HL       as FH_HL      : nitf:BCSNpos[6] @label "HL — NITF File Header Length"
  NUMI     as FH_NUMI    : nitf:BCSNpos[3] @label "NUMI — Number of Image Segments"
  // `repeat [NUMI]` (bracketed) rather than bare `repeat NUMI`: HdlParser's exprFromAccessorRun()
  // detects "next field starts here" only via an unaliased `IDENT COLON` lookahead, so a bare run
  // would swallow the next field's own name once that field carries its own `as` alias (verified
  // against the compiler; the unbracketed form reproducibly mis-parses here). Same reason on every
  // other bracketed `if [...]`/`repeat [...]`/`repeat until [...]` guard added in this file --
  // each precedes a field that is itself aliased below. HelSynth's rewriter only recognizes
  // single-quoted strings (core's HEL lexer, same rule), so literal comparisons use `'x'` inside
  // the brackets even though the unbracketed originals were DSL double-quoted `"x"`.
  imageSegs   as FH_ImageSegTable   : ImageSegLen   repeat [NUMI] @label "Image segment length pairs (× NUMI)"
  NUMS     as FH_NUMS    : nitf:BCSNpos[3] @label "NUMS — Number of Graphic Segments"
  graphicSegs as FH_GraphicSegTable : GraphicSegLen repeat [NUMS] @label "Graphic segment length pairs (× NUMS)"
  NUMX     as FH_NUMX    : nitf:BCSNpos[3]  @label "NUMX — Reserved for Future Use"
  NUMT     as FH_NUMT    : nitf:BCSNpos[3] @label "NUMT — Number of Text Segments"
  textSegs    as FH_TextSegTable    : TextSegLen    repeat [NUMT] @label "Text segment length pairs (× NUMT)"
  NUMDES   as FH_NUMDES  : nitf:BCSNpos[3] @label "NUMDES — Number of Data Extension Segments"
  deSegs      as FH_DESegTable      : DESegLen      repeat [NUMDES] @label "DES length pairs (× NUMDES)"
  NUMRES   as FH_NUMRES  : nitf:BCSNpos[3] @label "NUMRES — Number of Reserved Extension Segments"
  resSegs     as FH_RESegTable      : RESegLen      repeat [NUMRES] @label "RES length pairs (× NUMRES)"
  UDHDL    as FH_UDHDL   : nitf:BCSNpos[5] @label "UDHDL — User-Defined Header Data Length"
  UDHOFL   as FH_UDHOFL  : nitf:BCSNpos[3]  if [UDHDL != 0] @label "UDHOFL — user-defined header overflow"
  UDHD     as FH_UDHD    : TRE if UDHDL != 0 @prop bddo:sizeFromExpression "FH_UDHDL - 3" repeat until [eof()] @label "UDHD — user-defined header data (TREs)"
  XHDL     as FH_XHDL    : nitf:BCSNpos[5] @label "XHDL — Extended Header Data Length"
  XHDLOFL  as FH_XHDLOFL : nitf:BCSNpos[3]  if [XHDL != 0] @label "XHDLOFL — extended header overflow"
  // Bracketed `repeat until [eof()]` here too, even though XHD looks like the struct's last field:
  // the `raw-turtle` keyword right after it is itself an IDENT token to the lexer (its `{...}` body
  // is lexed as a single opaque RAW_BLOCK, with no separate LBRACE the unbracketed accessor-run
  // loop could stop on), so an unbracketed trailing expression here would swallow both the
  // "raw-turtle" token and the entire RAW_BLOCK text into XHD's HEL expression -- verified against
  // the compiler; unbracketed reproducibly corrupts this field and silently drops the block below.
  XHD      as FH_XHD     : TRE if XHDL != 0 @prop bddo:sizeFromExpression "FH_XHDL - 3" repeat until [eof()] @label "XHD — extended header data (TREs)"

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

    # Register bindings (Task 5) -- quoted verbatim from nitf.ttl's ontology header so the
    # compiled graph stays isomorphic to it for this subject; see nitf.ttl for the rationale
    # (one binding per asec: property that is actually concept-valued in this profile).
    <https://hexplain.io/ns/profile/nitf> hexplain:usesRegister
        [ a hexplain:RegisterBinding ; hexplain:forProperty asec:classification ;
          hexplain:register usnato:ClassificationLevelScheme ] ,
        [ a hexplain:RegisterBinding ; hexplain:forProperty asec:downgradeTo ;
          hexplain:register usnato:ClassificationLevelScheme ] ,
        [ a hexplain:RegisterBinding ; hexplain:forProperty asec:declassificationType ;
          hexplain:register usnato:DeclassTypeScheme ] ,
        [ a hexplain:RegisterBinding ; hexplain:forProperty asec:classificationAuthorityType ;
          hexplain:register usnato:AuthorityTypeScheme ] ,
        [ a hexplain:RegisterBinding ; hexplain:forProperty asec:classificationReason ;
          hexplain:register usnato:ClassificationReasonScheme ] .

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
struct ImageSubheader means gv:RasterDataset @label "NITF Image Subheader (Table A-3)" {
  IM       as IS_IM      : nitf:BCSA[2]  @fixed "IM" @label "IM — File Part Type"
  IID1     as IS_IID1    : nitf:BCSA[10] @label "IID1 — Image Identifier 1"
  IDATIM   as IS_IDATIM  : nitf:BCSN[14] @label "IDATIM — Image Date and Time (CCYYMMDDhhmmss)"
  TGTID    as IS_TGTID   : nitf:BCSA[17] @label "TGTID — Target Identifier"
  IID2     as IS_IID2    : nitf:ECSA[80] @label "IID2 — Image Identifier 2"
  // ---- Security block (ISCLAS..ISCTLN) -- same modeling as FileHeader's FSCLAS..FSCTLN
  // block above (concept enums inline, CODE/CTLH/DCXM physical-only): MIL-STD-2500C repeats
  // the identical 16-field block verbatim in every subheader, just under a different prefix.
  ISCLAS as IS_ISCLAS : nitf:ECSA[1]  enum SecurityClassificationEnum means asec:classification
                           @label "ISCLAS — Image Security Classification"
  ISCLSY as IS_ISCLSY : nitf:ECSA[2]  means asec:classificationSystem @label "ISCLSY — Image Security Classification System"
  ISCODE as IS_ISCODE : nitf:ECSA[11] @label "ISCODE — Image Codewords" // -> asec:compartment (usnato:MarkingScheme; space-separated digraphs)
  ISCTLH as IS_ISCTLH : nitf:ECSA[2]  @label "ISCTLH — Image Control and Handling" // -> asec:controlAndHandling (usnato:MarkingScheme)
  ISREL  as IS_ISREL  : nitf:ECSA[20] means asec:releasableTo @label "ISREL — Image Releasing Instructions"
  ISDCTP as IS_ISDCTP : nitf:ECSA[2]  enum DeclassificationTypeEnum means asec:declassificationType
                           @label "ISDCTP — Image Declassification Type"
  ISDCDT as IS_ISDCDT : nitf:ECSA[8]  means asec:declassificationDate @label "ISDCDT — Image Declassification Date"
  ISDCXM as IS_ISDCXM : nitf:ECSA[4]  @label "ISDCXM — Image Declassification Exemption" // -> asec:declassificationExemption (usnato:ExemptionScheme)
  ISDG   as IS_ISDG   : nitf:ECSA[1]  enum DowngradeToEnum means asec:downgradeTo @label "ISDG — Image Downgrade"
  ISDGDT as IS_ISDGDT : nitf:ECSA[8]  means asec:downgradeDate @label "ISDGDT — Image Downgrade Date"
  ISCLTX as IS_ISCLTX : nitf:ECSA[43] means asec:classificationText @label "ISCLTX — Image Classification Text"
  ISCATP as IS_ISCATP : nitf:ECSA[1]  enum ClassificationAuthorityTypeEnum means asec:classificationAuthorityType
                           @label "ISCATP — Image Classification Authority Type"
  ISCAUT as IS_ISCAUT : nitf:ECSA[40] means asec:classificationAuthority @label "ISCAUT — Image Classification Authority"
  ISCRSN as IS_ISCRSN : nitf:ECSA[1]  enum ClassificationReasonEnum means asec:classificationReason
                           @label "ISCRSN — Image Classification Reason"
  ISSRDT as IS_ISSRDT : nitf:ECSA[8]  means asec:securitySourceDate @label "ISSRDT — Image Security Source Date"
  ISCTLN as IS_ISCTLN : nitf:ECSA[15] means asec:securityControlNumber @label "ISCTLN — Image Security Control Number"
  ENCRYP   as IS_ENCRYP  : nitf:BCSNpos[1] @label "ENCRYP — Encryption"
  ISORCE   as IS_ISORCE  : nitf:ECSA[42] @label "ISORCE — Image Source"
  NROWS    as IS_NROWS   : nitf:BCSNpos[8]  means araster:height @label "NROWS — Number of Significant Rows in image"
  NCOLS    as IS_NCOLS   : nitf:BCSNpos[8]  means araster:width @label "NCOLS — Number of Significant Columns in image"
  PVTYPE   as IS_PVTYPE  : nitf:BCSA[3] enum PVTYPEEnum @label "PVTYPE — Pixel Value Type"
  // Raw values taken from nitf:IREPEnum in nitf.ttl (MIL-STD-2500C Table A-3), which is the
  // authoritative spelling -- note "RGB/LUT" with a solidus, not the "RGB-LUT" this line used
  // to carry as prose. Symbols are the codes themselves, so nothing about the standard's
  // meaning is invented here; the solidus is not a legal identifier, hence RGB_LUT.
  IREP     as IS_IREP    : nitf:BCSA[8] enum IREPEnum @label "IREP — Image Representation"
  ICAT     as IS_ICAT    : nitf:BCSA[8] @label "ICAT — Image Category"
  ABPP     as IS_ABPP    : nitf:BCSNpos[2] @label "ABPP — Actual Bits-Per-Pixel Per Band"
  PJUST    as IS_PJUST   : nitf:BCSA[1] @label "PJUST — Pixel Justification"
  ICORDS   as IS_ICORDS  : nitf:BCSA[1] enum ICORDSEnum @label "ICORDS — Image Coordinate Representation"
  // Bracketed guards below: HdlParser's exprFromAccessorRun() only recognizes an unaliased
  // `IDENT COLON` as "next field starts here", so once the following field carries its own `as`
  // alias a bare trailing expression here would swallow that field's name (verified against the
  // compiler). HelSynth's rewriter (like core's HEL lexer) only recognizes single-quoted strings,
  // so literal comparisons use `'x'` inside the brackets even though the DSL source is `"x"`.
  IGEOLO   as IS_IGEOLO  : nitf:BCSA[60] if [ICORDS != ' '] @label "IGEOLO — Image Geographic Location"
    // ICORDS decides what these 60 characters MEAN, so the footprint is a conditional
    // mapping rather than a plain one. Only 'D' (decimal degrees) is expressible: see the
    // LIMITS note in nitf.ttl for why 'G', 'N'/'S' and 'U' are not.
    value `concat('POLYGON((', substring(instance.IS_IGEOLO, 7, 8), ' ', substring(instance.IS_IGEOLO, 0, 7), ', ', substring(instance.IS_IGEOLO, 22, 8), ' ', substring(instance.IS_IGEOLO, 15, 7), ', ', substring(instance.IS_IGEOLO, 37, 8), ' ', substring(instance.IS_IGEOLO, 30, 7), ', ', substring(instance.IS_IGEOLO, 52, 8), ' ', substring(instance.IS_IGEOLO, 45, 7), ', ', substring(instance.IS_IGEOLO, 7, 8), ' ', substring(instance.IS_IGEOLO, 0, 7), '))')` @datatype xsd:string
    map { when [ICORDS == 'D'] => asref:footprintWKT }
  NICOM    as IS_NICOM   : nitf:BCSNpos[1] @label "NICOM — Number of Image Comments"
  ICOM     as IS_ICOM    : nitf:ECSA[80] repeat [NICOM] @label "ICOMn — Image Comment n (× NICOM)"
  // Raw values taken from nitf:ICEnum in nitf.ttl (MIL-STD-2500C Table A-3). Symbols are the
  // codes themselves rather than invented scheme names, so this encodes the valid-value set
  // without asserting a meaning for any code.
  IC       as IS_IC      : nitf:BCSA[2] enum ICEnum @label "IC — Image Compression"
  // Raw HEL (backtick) here, not `[IC != 'NC' and IC != 'NM']`: HelUnparser.grouped()
  // unconditionally parenthesizes BOTH operands of any binary op it round-trips, so the
  // bracket form would compile to "(instance.IS_IC != 'NC') and (instance.IS_IC != 'NM')" --
  // semantically identical to nitf.ttl's `bddo:isPresentIf "IS_IC != 'NC' and IS_IC != 'NM'"`
  // but spelled differently, and HDL has no surface syntax to suppress those parens. Raw HEL
  // is returned verbatim (HelSynth.toInstanceHel: `if (expr.rawHel) return src`), bypassing
  // the parse/unparse round trip, so it reproduces nitf.ttl's exact string. Written with the
  // post-alias name `IS_IC` (not the pre-alias DSL name `IC`) because raw HEL skips the
  // sibling renamer too -- a bare accessor still resolves against the current instance (HEL
  // has no separate "parent" root at struct scope), matching nitf.ttl's own spelling.
  COMRAT   as IS_COMRAT  : nitf:BCSA[4]  if `IS_IC != 'NC' and IS_IC != 'NM'` @label "COMRAT — Compression Rate Code"
  NBANDS   as IS_NBANDS  : nitf:BCSNpos[1] @label "NBANDS — Number of Bands"
                           means asamp:componentCount
  // Numeric `0`, not the string `'0'`: NBANDS is nitf:BCSNpos, whose bddo:baseType is
  // bddo:baseInteger, so HEL sees an Integer here and a string comparison would never match.
  // (nitf.ttl has always had the numeric form; this file's `'0'` was correct only while the
  // field was a plain `ascii[1]`.)
  XBANDS   as IS_XBANDS  : nitf:BCSNpos[5]  if [NBANDS == 0] @label "XBANDS — Number of Multispectral Bands"
  bands    as IS_BandTable : ImageBand repeat [NBANDS] @label "Band records (× NBANDS)"
  ISYNC    as IS_ISYNC   : nitf:BCSNpos[1] @label "ISYNC — Image Sync Code"
  IMODE    as IS_IMODE   : nitf:BCSA[1] enum IMODEEnum @label "IMODE — Image Mode"
  NBPR     as IS_NBPR    : nitf:BCSNpos[4] @label "NBPR — Number of Blocks Per Row"
  NBPC     as IS_NBPC    : nitf:BCSNpos[4] @label "NBPC — Number of Blocks Per Column"
  NPPBH    as IS_NPPBH   : nitf:BCSNpos[4] @label "NPPBH — Number of Pixels Per Block Horizontal"
  NPPBV    as IS_NPPBV   : nitf:BCSNpos[4] @label "NPPBV — Number of Pixels Per Block Vertical"
  NBPP     as IS_NBPP    : nitf:BCSNpos[2] @label "NBPP — Number of Bits Per Pixel Per Band"
                           means asamp:bitDepth
  IDLVL    as IS_IDLVL   : nitf:BCSNpos[3] @label "IDLVL — Image Display Level"
  IALVL    as IS_IALVL   : nitf:BCSNpos[3] @label "IALVL — Image Attachment Level"
  ILOC     as IS_ILOC    : nitf:BCSN[10] @label "ILOC — Image Location"
  IMAG     as IS_IMAG    : nitf:BCSA[4] @label "IMAG — Image Magnification"
  UDIDL    as IS_UDIDL   : nitf:BCSNpos[5] @label "UDIDL — User-Defined Image Data Length"
  UDOFL    as IS_UDOFL   : nitf:BCSNpos[3]  if [UDIDL != 0] @label "UDOFL — user-defined image data overflow"
  UDID     as IS_UDID    : TRE if UDIDL != 0 @prop bddo:sizeFromExpression "IS_UDIDL - 3" repeat until [eof()] @label "UDID — user-defined image data (TREs)"
  IXSHDL   as IS_IXSHDL  : nitf:BCSNpos[5] @label "IXSHDL — Image Extended Subheader Data Length"
  IXSOFL   as IS_IXSOFL  : nitf:BCSNpos[3]  if [IXSHDL != 0] @label "IXSOFL — image extended subheader overflow"
  IXSHD    as IS_IXSHD   : TRE if IXSHDL != 0 @prop bddo:sizeFromExpression "IS_IXSHDL - 3" repeat until eof() @label "IXSHD — image extended subheader data (TREs)"
}

// =========================================================
// Graphic subheader (Table A-5)
// =========================================================
struct GraphicSubheader @label "NITF Graphic Subheader (Table A-5)" {
  SY       as GS_SY      : nitf:BCSA[2]  @fixed "SY" @label "SY — File Part Type"
  SID      as GS_SID     : nitf:BCSA[10] @label "SID — Graphic Identifier"
  SNAME    as GS_SNAME   : nitf:ECSA[20] @label "SNAME — Graphic Name"
  // ---- Security block (SSCLAS..SSCTLN) -- same modeling as FileHeader's FSCLAS..FSCTLN above ----
  SSCLAS as GS_SSCLAS : nitf:ECSA[1]  enum SecurityClassificationEnum means asec:classification
                           @label "SSCLAS — Graphic Security Classification"
  SSCLSY as GS_SSCLSY : nitf:ECSA[2]  means asec:classificationSystem @label "SSCLSY — Graphic Security Classification System"
  SSCODE as GS_SSCODE : nitf:ECSA[11] @label "SSCODE — Graphic Codewords" // -> asec:compartment (usnato:MarkingScheme; space-separated digraphs)
  SSCTLH as GS_SSCTLH : nitf:ECSA[2]  @label "SSCTLH — Graphic Control and Handling" // -> asec:controlAndHandling (usnato:MarkingScheme)
  SSREL  as GS_SSREL  : nitf:ECSA[20] means asec:releasableTo @label "SSREL — Graphic Releasing Instructions"
  SSDCTP as GS_SSDCTP : nitf:ECSA[2]  enum DeclassificationTypeEnum means asec:declassificationType
                           @label "SSDCTP — Graphic Declassification Type"
  SSDCDT as GS_SSDCDT : nitf:ECSA[8]  means asec:declassificationDate @label "SSDCDT — Graphic Declassification Date"
  SSDCXM as GS_SSDCXM : nitf:ECSA[4]  @label "SSDCXM — Graphic Declassification Exemption" // -> asec:declassificationExemption (usnato:ExemptionScheme)
  SSDG   as GS_SSDG   : nitf:ECSA[1]  enum DowngradeToEnum means asec:downgradeTo @label "SSDG — Graphic Downgrade"
  SSDGDT as GS_SSDGDT : nitf:ECSA[8]  means asec:downgradeDate @label "SSDGDT — Graphic Downgrade Date"
  SSCLTX as GS_SSCLTX : nitf:ECSA[43] means asec:classificationText @label "SSCLTX — Graphic Classification Text"
  SSCATP as GS_SSCATP : nitf:ECSA[1]  enum ClassificationAuthorityTypeEnum means asec:classificationAuthorityType
                           @label "SSCATP — Graphic Classification Authority Type"
  SSCAUT as GS_SSCAUT : nitf:ECSA[40] means asec:classificationAuthority @label "SSCAUT — Graphic Classification Authority"
  SSCRSN as GS_SSCRSN : nitf:ECSA[1]  enum ClassificationReasonEnum means asec:classificationReason
                           @label "SSCRSN — Graphic Classification Reason"
  SSSRDT as GS_SSSRDT : nitf:ECSA[8]  means asec:securitySourceDate @label "SSSRDT — Graphic Security Source Date"
  SSCTLN as GS_SSCTLN : nitf:ECSA[15] means asec:securityControlNumber @label "SSCTLN — Graphic Security Control Number"
  ENCRYP   as GS_ENCRYP  : nitf:BCSNpos[1] @label "ENCRYP — Encryption"
  SFMT     as GS_SFMT    : nitf:BCSA[1]  @fixed "C" @label "SFMT — Graphic Type"
  SSTRUCT  as GS_SSTRUCT : nitf:BCSNpos[13] @label "SSTRUCT — Reserved for Future Use"
  SDLVL    as GS_SDLVL   : nitf:BCSNpos[3] @label "SDLVL — Graphic Display Level"
  SALVL    as GS_SALVL   : nitf:BCSNpos[3] @label "SALVL — Graphic Attachment Level"
  SLOC     as GS_SLOC    : nitf:BCSN[10] @label "SLOC — Graphic Location"
  SBND1    as GS_SBND1   : nitf:BCSN[10] @label "SBND1 — First Graphic Bound Location"
  SCOLOR   as GS_SCOLOR  : nitf:BCSA[1] @label "SCOLOR — Graphic Color"
  SBND2    as GS_SBND2   : nitf:BCSN[10] @label "SBND2 — Second Graphic Bound Location"
  SRES2    as GS_SRES2   : nitf:BCSNpos[2] @label "SRES2 — Reserved for Future Use"
  SXSHDL   as GS_SXSHDL  : nitf:BCSNpos[5] @label "SXSHDL — Graphic Extended Subheader Data Length"
  // Bracketed guard: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field (SXSHD) carries its own `as` alias.
  SXSOFL   as GS_SXSOFL  : nitf:BCSNpos[3]  if [SXSHDL != 0] @label "SXSOFL — graphic extended subheader overflow"
  SXSHD    as GS_SXSHD   : TRE if SXSHDL != 0 @prop bddo:sizeFromExpression "GS_SXSHDL - 3" repeat until eof() @label "SXSHD — graphic extended subheader data (TREs)"
}

// =========================================================
// Text subheader (Table A-6)
// =========================================================
struct TextSubheader @label "NITF Text Subheader (Table A-6)" {
  TE       as TS_TE      : nitf:BCSA[2]  @fixed "TE" @label "TE — File Part Type"
  TEXTID   as TS_TEXTID  : nitf:BCSA[7] @label "TEXTID — Text Identifier"
  TXTALVL  as TS_TXTALVL : nitf:BCSNpos[3] @label "TXTALVL — Text Attachment Level"
  TXTDT    as TS_TXTDT   : nitf:BCSN[14] @label "TXTDT — Text Date and Time (CCYYMMDDhhmmss)"
  TXTITL   as TS_TXTITL  : nitf:ECSA[80] @label "TXTITL — Text Title"
  // ---- Security block (TSCLAS..TSCTLN) -- same modeling as FileHeader's FSCLAS..FSCTLN above ----
  TSCLAS as TS_TSCLAS : nitf:ECSA[1]  enum SecurityClassificationEnum means asec:classification
                           @label "TSCLAS — Text Security Classification"
  TSCLSY as TS_TSCLSY : nitf:ECSA[2]  means asec:classificationSystem @label "TSCLSY — Text Security Classification System"
  TSCODE as TS_TSCODE : nitf:ECSA[11] @label "TSCODE — Text Codewords" // -> asec:compartment (usnato:MarkingScheme; space-separated digraphs)
  TSCTLH as TS_TSCTLH : nitf:ECSA[2]  @label "TSCTLH — Text Control and Handling" // -> asec:controlAndHandling (usnato:MarkingScheme)
  TSREL  as TS_TSREL  : nitf:ECSA[20] means asec:releasableTo @label "TSREL — Text Releasing Instructions"
  TSDCTP as TS_TSDCTP : nitf:ECSA[2]  enum DeclassificationTypeEnum means asec:declassificationType
                           @label "TSDCTP — Text Declassification Type"
  TSDCDT as TS_TSDCDT : nitf:ECSA[8]  means asec:declassificationDate @label "TSDCDT — Text Declassification Date"
  TSDCXM as TS_TSDCXM : nitf:ECSA[4]  @label "TSDCXM — Text Declassification Exemption" // -> asec:declassificationExemption (usnato:ExemptionScheme)
  TSDG   as TS_TSDG   : nitf:ECSA[1]  enum DowngradeToEnum means asec:downgradeTo @label "TSDG — Text Downgrade"
  TSDGDT as TS_TSDGDT : nitf:ECSA[8]  means asec:downgradeDate @label "TSDGDT — Text Downgrade Date"
  TSCLTX as TS_TSCLTX : nitf:ECSA[43] means asec:classificationText @label "TSCLTX — Text Classification Text"
  TSCATP as TS_TSCATP : nitf:ECSA[1]  enum ClassificationAuthorityTypeEnum means asec:classificationAuthorityType
                           @label "TSCATP — Text Classification Authority Type"
  TSCAUT as TS_TSCAUT : nitf:ECSA[40] means asec:classificationAuthority @label "TSCAUT — Text Classification Authority"
  TSCRSN as TS_TSCRSN : nitf:ECSA[1]  enum ClassificationReasonEnum means asec:classificationReason
                           @label "TSCRSN — Text Classification Reason"
  TSSRDT as TS_TSSRDT : nitf:ECSA[8]  means asec:securitySourceDate @label "TSSRDT — Text Security Source Date"
  TSCTLN as TS_TSCTLN : nitf:ECSA[15] means asec:securityControlNumber @label "TSCTLN — Text Security Control Number"
  ENCRYP   as TS_ENCRYP  : nitf:BCSNpos[1] @label "ENCRYP — Encryption"
  TXTFMT   as TS_TXTFMT  : nitf:BCSA[3] enum TXTFMTEnum @label "TXTFMT — Text Format"
  TXSHDL   as TS_TXSHDL  : nitf:BCSNpos[5] @label "TXSHDL — Text Extended Subheader Data Length"
  // Bracketed guard: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field (TXSHD) carries its own `as` alias.
  TXSOFL   as TS_TXSOFL  : nitf:BCSNpos[3]  if [TXSHDL != 0] @label "TXSOFL — text extended subheader overflow"
  TXSHD    as TS_TXSHD   : TRE if TXSHDL != 0 @prop bddo:sizeFromExpression "TS_TXSHDL - 3" repeat until eof() @label "TXSHD — text extended subheader data (TREs)"
}

// =========================================================
// Data Extension Segment subheader (Table A-8)
// =========================================================
struct DESubheader @label "NITF Data Extension Segment Subheader (Table A-8)" {
  DE       as DES_DE     : nitf:BCSA[2]  @fixed "DE" @label "DE — File Part Type"
  DESID    as DES_DESID  : nitf:BCSA[25] @label "DESID — Unique DES Type Identifier"
  DESVER   as DES_DESVER : nitf:BCSNpos[2] @label "DESVER — Version of the Data Definition"
  // ---- Security block (DECLAS..DESCTLN) -- same modeling as FileHeader's FSCLAS..FSCTLN
  // above. Irregular name: MIL-STD-2500C's own field mnemonic for the first field is DECLAS
  // (2-letter "DE" root), not DESCLAS -- every other field in this block happens to have a
  // mnemonic that already starts with "DES" (DESCLSY, DESCODE, ...), so DES_DECLAS is the
  // literal mnemonic prefixed with "DES_", reproduced verbatim from nitf.ttl, not an alias
  // exception invented here.
  DECLAS  as DES_DECLAS  : nitf:ECSA[1]  enum SecurityClassificationEnum means asec:classification
                           @label "DECLAS — Data Extension Segment Security Classification"
  DESCLSY as DES_DESCLSY : nitf:ECSA[2]  means asec:classificationSystem @label "DESCLSY — DES Security Classification System"
  DESCODE as DES_DESCODE : nitf:ECSA[11] @label "DESCODE — DES Codewords" // -> asec:compartment (usnato:MarkingScheme; space-separated digraphs)
  DESCTLH as DES_DESCTLH : nitf:ECSA[2]  @label "DESCTLH — DES Control and Handling" // -> asec:controlAndHandling (usnato:MarkingScheme)
  DESREL  as DES_DESREL  : nitf:ECSA[20] means asec:releasableTo @label "DESREL — DES Releasing Instructions"
  DESDCTP as DES_DESDCTP : nitf:ECSA[2]  enum DeclassificationTypeEnum means asec:declassificationType
                           @label "DESDCTP — DES Declassification Type"
  DESDCDT as DES_DESDCDT : nitf:ECSA[8]  means asec:declassificationDate @label "DESDCDT — DES Declassification Date"
  DESDCXM as DES_DESDCXM : nitf:ECSA[4]  @label "DESDCXM — DES Declassification Exemption" // -> asec:declassificationExemption (usnato:ExemptionScheme)
  DESDG   as DES_DESDG   : nitf:ECSA[1]  enum DowngradeToEnum means asec:downgradeTo @label "DESDG — DES Downgrade"
  DESDGDT as DES_DESDGDT : nitf:ECSA[8]  means asec:downgradeDate @label "DESDGDT — DES Downgrade Date"
  DESCLTX as DES_DESCLTX : nitf:ECSA[43] means asec:classificationText @label "DESCLTX — DES Classification Text"
  DESCATP as DES_DESCATP : nitf:ECSA[1]  enum ClassificationAuthorityTypeEnum means asec:classificationAuthorityType
                           @label "DESCATP — DES Classification Authority Type"
  DESCAUT as DES_DESCAUT : nitf:ECSA[40] means asec:classificationAuthority @label "DESCAUT — DES Classification Authority"
  DESCRSN as DES_DESCRSN : nitf:ECSA[1]  enum ClassificationReasonEnum means asec:classificationReason
                           @label "DESCRSN — DES Classification Reason"
  DESSRDT as DES_DESSRDT : nitf:ECSA[8]  means asec:securitySourceDate @label "DESSRDT — DES Security Source Date"
  DESCTLN as DES_DESCTLN : nitf:ECSA[15] means asec:securityControlNumber @label "DESCTLN — DES Security Control Number"
  // Bracketed guards: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field carries its own `as` alias, and why literal
  // comparisons use `'x'` (HelSynth/HEL only recognize single-quoted strings) instead of the DSL's
  // own `"x"`.
  // `trim(...)` is required, not cosmetic: DESID is ascii[25] and MIL-STD-2500C space-pads it,
  // so the stored value is "TRE_OVERFLOW" followed by 13 spaces and a bare `==` comparison can
  // never be true -- the two fields below would be silently omitted from every DES that has
  // them. nitf.ttl's hand-written form has always had the trim; this file had lost it.
  DESOFLW  as DES_DESOFLW : nitf:BCSA[6]  if [trim(DESID) == 'TRE_OVERFLOW'] @label "DESOFLW — DES Overflowed Header Type"
  DESITEM  as DES_DESITEM : nitf:BCSNpos[3]  if [trim(DESID) == 'TRE_OVERFLOW'] @label "DESITEM — DES Data Item Overflowed"
  DESSHL   as DES_DESSHL  : nitf:BCSNpos[4] @label "DESSHL — DES User-Defined Subheader Length"
  DESSHF   as DES_DESSHF  : nitf:BCSA[DESSHL] if [DESSHL != 0] @label "DESSHF — DES User-Defined Subheader Fields"
  DESDATA  as DES_DESDATA : bytes[..] @label "DESDATA — DES Data Field" @comment "Bounded by the enclosing segment's LDn length from the file header's DES length table. When DESID = TRE_OVERFLOW, this field carries a nitf:TRE sequence rather than opaque bytes." // for DESID = TRE_OVERFLOW this is a TRE sequence
}

// =========================================================
// Reserved Extension Segment subheader (Table A-9)
// =========================================================
struct RESubheader @label "NITF Reserved Extension Segment Subheader (Table A-9)" {
  RE       as RES_RE     : nitf:BCSA[2]  @fixed "RE" @label "RE — File Part Type"
  RESID    as RES_RESID  : nitf:BCSA[25] @label "RESID — Unique RES Type Identifier"
  RESVER   as RES_RESVER : nitf:BCSNpos[2] @label "RESVER — Version of the Data Definition"
  // ---- Security block (RECLAS..RECTLN) -- same modeling as FileHeader's FSCLAS..FSCTLN above ----
  RECLAS as RES_RECLAS : nitf:ECSA[1]  enum SecurityClassificationEnum means asec:classification
                           @label "RECLAS — Reserved Extension Segment Security Classification"
  RECLSY as RES_RECLSY : nitf:ECSA[2]  means asec:classificationSystem @label "RECLSY — RES Security Classification System"
  RECODE as RES_RECODE : nitf:ECSA[11] @label "RECODE — RES Codewords" // -> asec:compartment (usnato:MarkingScheme; space-separated digraphs)
  RECTLH as RES_RECTLH : nitf:ECSA[2]  @label "RECTLH — RES Control and Handling" // -> asec:controlAndHandling (usnato:MarkingScheme)
  REREL  as RES_REREL  : nitf:ECSA[20] means asec:releasableTo @label "REREL — RES Releasing Instructions"
  REDCTP as RES_REDCTP : nitf:ECSA[2]  enum DeclassificationTypeEnum means asec:declassificationType
                           @label "REDCTP — RES Declassification Type"
  REDCDT as RES_REDCDT : nitf:ECSA[8]  means asec:declassificationDate @label "REDCDT — RES Declassification Date"
  REDCXM as RES_REDCXM : nitf:ECSA[4]  @label "REDCXM — RES Declassification Exemption" // -> asec:declassificationExemption (usnato:ExemptionScheme)
  REDG   as RES_REDG   : nitf:ECSA[1]  enum DowngradeToEnum means asec:downgradeTo @label "REDG — RES Downgrade"
  REDGDT as RES_REDGDT : nitf:ECSA[8]  means asec:downgradeDate @label "REDGDT — RES Downgrade Date"
  RECLTX as RES_RECLTX : nitf:ECSA[43] means asec:classificationText @label "RECLTX — RES Classification Text"
  RECATP as RES_RECATP : nitf:ECSA[1]  enum ClassificationAuthorityTypeEnum means asec:classificationAuthorityType
                           @label "RECATP — RES Classification Authority Type"
  RECAUT as RES_RECAUT : nitf:ECSA[40] means asec:classificationAuthority @label "RECAUT — RES Classification Authority"
  RECRSN as RES_RECRSN : nitf:ECSA[1]  enum ClassificationReasonEnum means asec:classificationReason
                           @label "RECRSN — RES Classification Reason"
  RESRDT as RES_RESRDT : nitf:ECSA[8]  means asec:securitySourceDate @label "RESRDT — RES Security Source Date"
  RECTLN as RES_RECTLN : nitf:ECSA[15] means asec:securityControlNumber @label "RECTLN — RES Security Control Number"
  RESSHL   as RES_RESSHL  : nitf:BCSNpos[4] @label "RESSHL — RES User-Defined Subheader Length"
  // Bracketed guard: see the note on ImageSubheader.IGEOLO for why an unaliased-next-field
  // heuristic forces this once the following field (RESDATA) carries its own `as` alias.
  RESSHF   as RES_RESSHF  : nitf:BCSA[RESSHL] if [RESSHL != 0] @label "RESSHF — RES User-Defined Subheader Fields"
  RESDATA  as RES_RESDATA : bytes[..] @label "RESDATA — RES Data Field" @comment "Bounded by the enclosing segment's LREn length from the file header's RES length table."
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
