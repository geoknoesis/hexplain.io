"""Physical Parser cases: alignment origins, offsets from a sibling, the three VAX formats, what makes a description
valid, strides a stream supplies, and separated tokens that abut at the start of a region."""

from __future__ import annotations

from cases_physical import pp

FLOATS = ["req-pm-numeric-representation-1"]
VALID = "req-pm-inputs-outputs-2"
ORIGIN = "req-pm-alignment-padding-6"

# ----------------------------------------------------------------- the alignment origin

pp(
    "align-struct-origin-padding",
    "bddo:structOrigin pads a struct relative to its own start",
    "Rec starts at offset 6 and pads to 4 from its own first byte: one byte read, three of padding, so it ends at "
    "offset 10 and after is read there. Measured from the stream's start, as without bddo:alignmentOrigin, it would "
    "end at 8.",
    [ORIGIN, "req-pm-alignment-padding-1"],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pad ex:rec ex:after ) .
   ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 6 .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:padTo 4 ; bddo:alignmentOrigin bddo:structOrigin ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:after a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x00" * 6 + b"\x07" + b"\xee\xee\xee" + b"\x42",
    {"pad": b"\x00" * 6, "rec": {"a": 7}, "after": 0x42},
)

pp(
    "align-struct-origin-field",
    "A field aligned under bddo:structOrigin counts from its struct's start; the origin is not inherited",
    "Rec starts at offset 3. b is aligned to 2 from Rec's first byte, so after a it starts at offset 5 (Rec offset 2), "
    "not 4. c states no origin and aligns to 4 from the stream's start, offset 8, although its struct's b chose "
    "bddo:structOrigin.",
    [ORIGIN, "req-pm-alignment-padding-1"],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pad ex:rec ) .
   ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:alignment 2 ; bddo:alignmentOrigin bddo:structOrigin .
   ex:c a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:alignment 4 .
   """,
    b"\x00\x00\x00" + b"\x07" + b"\xee" + b"\x12" + b"\xee\xee" + b"\x34",
    {"pad": b"\x00\x00\x00", "rec": {"a": 7, "b": 0x12, "c": 0x34}},
)

pp(
    "align-derived-field",
    "Alignment on a derived field is a description error",
    "A derived field occupies no bytes, so there is nothing to align; bddo:DerivedFieldShape refuses it.",
    ["req-pm-alignment-padding-7"],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:twice ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:twice a bddo:Field ; bddo:valueFromExpression "a * 2" ; bddo:alignment 4 .
   """,
    b"\x03",
    error="Description",
)

# ----------------------------------------------------------------- offsets from a sibling

pp(
    "offset-field-start",
    "bddo:fieldStart counts an offset from the start of an earlier sibling",
    "dir starts at offset 1; tbl is 3 bytes after it, at offset 4, read there, and the cursor comes back for tail.",
    ["req-pm-parsefield-35", "req-pm-parsefield-7"],
    ["field-start", "algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ex:dir ex:tbl ex:tail ) .
   ex:hdr a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:dir a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:tbl a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 3 ;
       bddo:offsetBase bddo:fieldStart ; bddo:offsetBaseField ex:dir .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x01\xaa\xbb\xcc\x77",
    {"hdr": 1, "dir": 0xAABB, "tbl": 0x77, "tail": 0xCC},
)

pp(
    "offset-field-start-outside",
    "An offset from a sibling whose target lies outside the stream is a bounds error",
    "dir starts at offset 1 and the offset is 9: offset 10 of a 4-byte stream.",
    ["req-pm-parsefield-35"],
    ["field-start"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ex:dir ex:tbl ) .
   ex:hdr a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:dir a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:tbl a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 9 ;
       bddo:offsetBase bddo:fieldStart ; bddo:offsetBaseField ex:dir .
   """,
    b"\x01\xaa\xbb\xcc",
    error="Bounds",
)

pp(
    "offset-field-start-absent-base",
    "An offset from a sibling that was not read is a description error",
    "flag is 0, so dir is absent: its start, the origin of tbl's offset, does not exist.",
    ["req-pm-parsefield-36"],
    ["field-start"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:flag ex:dir ex:tbl ) .
   ex:flag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:dir a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:isPresentIf "flag == 1" .
   ex:tbl a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 1 ;
       bddo:offsetBase bddo:fieldStart ; bddo:offsetBaseField ex:dir .
   """,
    b"\x00\xaa\xbb\xcc",
    error="Description",
)

# ----------------------------------------------------------------- VAX formats and validity

pp(
    "float-vax-d-g",
    "bddo:vaxD and bddo:vaxG read the same eight bytes as different numbers",
    "80 40 then six zero bytes is the word 0x4080 first. As D_floating: exponent 129 (eight bits), fraction 0, so "
    "0.5 x 2 = 1.0. As G_floating: exponent 0x408 = 1032 (eleven bits), fraction 0, so 0.5 x 2^8 = 128.0. "
    "20 C1 ... is D_floating -2.5 (exponent 130, fraction 2^53 of 2^56) and 24 C0 ... G_floating -2.5 (exponent "
    "1026, fraction 2^50 of 2^53).",
    FLOATS
    + ["req-pm-numeric-representation-10", "req-pm-numeric-representation-11", "req-pm-numeric-representation-6"],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:d ex:g ex:dn ex:gn ) .
   ex:d a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxD .
   ex:g a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxG .
   ex:dn a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxD .
   ex:gn a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxG .
   """,
    bytes.fromhex("8040000000000000804000000000000020c100000000000024c0000000000000"),
    {"d": 1.0, "g": 128.0, "dn": -2.5, "gn": -2.5},
)

pp(
    "float-vax-f-64-deprecated",
    "A 64-bit bddo:vaxF is the deprecated spelling of bddo:vaxD, valid and read as D_floating",
    "bddo:FloatFormatWidthShape reports the 64-bit bddo:vaxF at sh:Warning; the description is valid and the field "
    "reads exactly as its bddo:vaxD twin: 80 40 then six zero bytes is 1.0.",
    FLOATS + ["req-pm-numeric-representation-4", "req-pm-numeric-representation-10", VALID],
    ["numeric-representation", "valid-description"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:old ex:new ) .
   ex:old a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxF .
   ex:new a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxD .
   """,
    bytes.fromhex("80400000000000008040000000000000"),
    {"old": 1.0, "new": 1.0},
)

pp(
    "valid-despite-warning",
    "A description whose only results are warnings is valid and is parsed",
    "The custom encoding re-spells ISO-8859-1, a registered encoding's charset, which bddo:CustomEncodingCharsetShape "
    "reports at sh:Warning. That is no reason to refuse the description: E9 41 reads as U+00E9 and A.",
    [VALID, "req-pm-text-decoding-7"],
    ["valid-description", "text-decoding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:name ) .
   ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding ex:Latin .
   ex:Latin a bddo:Encoding , bddo:CustomEncoding ; bddo:ianaCharset "ISO-8859-1" .
   """,
    b"\xe9A",
    {"name": "éA"},
)

# ----------------------------------------------------------------- strides a stream supplies

pp(
    "layout-stride-from-field-zero",
    "A stride of zero read from a field is a description error when the layout is resolved",
    "The row pitch field holds 0: no cell after the first has an address, and the description pairs the layout with "
    "a stride it cannot have.",
    ["req-pm-data-layouts-5", "req-pm-data-layouts-1"],
    ["data-layouts"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pitch ex:pixels ) .
   ex:pitch a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; hexplain:hasDataLayout ex:Layout .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:hasDimension ( ex:DimY ex:DimX ) .
   ex:DimY a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSize 2 ; dlv:dimensionStrideFromField ex:pitch .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSize 2 .
   """,
    b"\x00\x01\x02\x03\x04",
    error="Description",
)

# ----------------------------------------------------------------- separated tokens at the start of a region

pp(
    "separated-abutting-regions",
    "A separated token at the start of a region is preceded by nothing, so tokens of adjacent regions abut",
    "Each one-byte box holds one separated token. The region bounds the token, so '12' is the two tokens 1 and 2, "
    "not the token 12: nothing separates them, and nothing needs to.",
    ["req-pm-size-resolution-6", "req-pm-text-numbers-2"],
    ["size-resolution", "text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:first ex:second ) .
   ex:first a bddo:Field ; bddo:dataType ex:Box .
   ex:second a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 1 ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" .
   """,
    b"12",
    {"first": {"v": 1}, "second": {"v": 2}},
)
