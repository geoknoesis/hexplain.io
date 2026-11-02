"""Physical Parser and Semantic Emitter cases for the representation terms of BDDO 1.3 and DLV 1.3 and for the
addressing and emission rules settled with them: padding and struct alignment, float formats, binary-coded decimal,
fixed-point scale, custom encodings, computed layout extents, the Adler-32 checksum field, negative offsets, an
enumerated field mapped both ways, and the HEL points on reserved roots, HEL-RE and the math group.

Every expected value is worked out from the Processing Model's text in the case's intent, never recorded from an
implementation.
"""

from __future__ import annotations

from cases_hel import SYNTAX, TYPE_ERROR, derived, hel, one
from cases_physical import pp
from cases_semantic import MINT, se
from cases_semantic import ROOT as SE_ROOT

PAD = ["req-pm-alignment-padding-1"]

# ----------------------------------------------------------------- padding

pp(
    "pad-field",
    "bddo:padTo on a field skips to the next boundary after its value",
    "A uint8 padded to 4 at offset 0 is followed by three bytes of padding, whose content is not checked when no "
    "bddo:padByte is stated; the next field starts at offset 4.",
    PAD + ["req-pm-parsefield-31", "req-pm-alignment-padding-4"],
    ["alignment-padding", "algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:padTo 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x01\xee\x00\xff\x02",
    {"a": 1, "b": 2},
)

pp(
    "pad-field-on-boundary",
    "A cursor already on the padding boundary does not move",
    "A uint16 padded to 2 ends at offset 2, a multiple of 2: nothing is skipped.",
    PAD + ["req-pm-parsefield-31"],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:padTo 2 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x00\x01\x02",
    {"a": 1, "b": 2},
)

pp(
    "pad-repeated-field",
    "Padding follows the whole sequence of a repeated field",
    "Three uint8 elements end at offset 3; the field's bddo:padTo 4 skips one byte once, after the sequence, not "
    "after each element.",
    PAD + ["req-pm-parsefield-31"],
    ["alignment-padding", "algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:xs ex:tail ) .
   ex:xs a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 3 ; bddo:padTo 4 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x01\x02\x03\xee\x09",
    {"xs": [1, 2, 3], "tail": 9},
)

pp(
    "pad-struct-extent",
    "bddo:padTo on a struct pads after its last member, inside its extent",
    "Rec reads one byte and pads to 4, so it ends at offset 4 and sizeof(rec) is 4, the padding included.",
    PAD + ["req-pm-parsestruct-12"],
    ["alignment-padding", "algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:rec ex:n ex:tail ) .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:padTo 4 ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:n a bddo:Field ; bddo:valueFromExpression "sizeof(rec)" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x07\x00\x00\x00\x09",
    {"rec": {"a": 7}, "n": 4, "tail": 9},
)

pp(
    "pad-origin-is-the-stream",
    "A struct's position does not move the padding origin",
    "Rec starts at offset 6, reads one byte and pads to 4: it ends at offset 8, the next multiple of 4 from the start "
    "of the stream, not at offset 10.",
    PAD + ["req-pm-parsestruct-12"],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:lead ex:rec ex:tail ) .
   ex:lead a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 6 .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:padTo 4 ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x00" * 6 + b"\x07\xee\x09",
    {"lead": b"\x00" * 6, "rec": {"a": 7}, "tail": 9},
)

pp(
    "pad-past-region",
    "Padding that would pass the end of the bounded region is a bounds error",
    "Box is bounded to 2 bytes; its field pads to 4, and offset 4 lies outside the region.",
    ["req-pm-alignment-padding-2", "req-pm-errors-3"],
    ["alignment-padding", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:size 2 .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:padTo 4 .
   """,
    b"\x01\x00\x00\x00",
    error="Bounds",
)

PAD_AT_OFFSET = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:p ex:q ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:p a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 4 ; bddo:padTo 4 {more}.
   ex:q a bddo:Field ; bddo:dataType bddo:uint8 .
"""

pp(
    "pad-field-at-offset",
    "bddo:padTo on an offset-addressed field pads at the target and leaves the saved cursor alone",
    "p is read at offset 4 and padded there, to offset 8; the cursor is then restored to offset 1, where q is read. "
    "Padding applied at the saved cursor instead would move q to offset 4.",
    PAD + ["req-pm-parsefield-34", "req-pm-parsefield-7"],
    ["algorithm", "alignment-padding"],
    PAD_AT_OFFSET.format(more=""),
    b"\x01\x02\xee\xee\x05\xee\xee\xee",
    {"n": 1, "p": 5, "q": 2},
)

pp(
    "pad-field-at-offset-checks-first",
    "An offset-addressed field's checks are made before its padding is applied",
    "p is read at offset 4 of a six-byte stream: its fixed value does not match, and its padding to offset 8 would "
    "pass the end of the stream. The checks come first, so the error is the validation error, not the bounds error "
    "of the padding.",
    ["req-pm-parsefield-34", "req-pm-parsefield-31"],
    ["algorithm", "alignment-padding", "errors"],
    PAD_AT_OFFSET.format(more="; bddo:hasFixedValue 9 "),
    b"\x01\x02\xee\xee\x05\xee",
    error="Validation",
)

pp(
    "pad-byte-without-pad-to",
    "bddo:padByte without bddo:padTo is a description error",
    "A fill byte describes padding; the field declares none.",
    ["req-pm-alignment-padding-5", "req-pm-errors-8"],
    ["alignment-padding", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:padByte "00"^^xsd:hexBinary .
   """,
    b"\x01",
    error="Description",
)

# ----------------------------------------------------------------- struct alignment

pp(
    "align-struct",
    "bddo:alignment on a struct aligns the start of every instance",
    "Rec is aligned to 4: after one byte it starts at offset 4. The skipped bytes precede the struct, so sizeof(rec) "
    "is 2.",
    PAD + ["req-pm-parsestruct-11"],
    ["alignment-padding", "algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:rec ex:n ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:alignment 4 ; bddo:hasField ( ex:b ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:n a bddo:Field ; bddo:valueFromExpression "sizeof(rec)" .
   """,
    b"\x01\xee\xee\xee\x12\x34",
    {"a": 1, "rec": {"b": 0x1234}, "n": 2},
)

pp(
    "align-struct-each-instance",
    "A struct's alignment applies to each element of a repeated field",
    "Rec is aligned to 2 and holds one byte: the first element starts at offset 2, the second at offset 4.",
    PAD + ["req-pm-parsestruct-11"],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:recs ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:recs a bddo:Field ; bddo:dataType ex:Rec ; bddo:repeatCount 2 .
   ex:Rec a bddo:Struct ; bddo:alignment 2 ; bddo:hasField ( ex:b ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x01\xee\x0a\xee\x0b",
    {"a": 1, "recs": [{"b": 10}, {"b": 11}]},
)

# ----------------------------------------------------------------- float formats

FLOATS = ["req-pm-numeric-representation-1"]

pp(
    "float-ibm-hexadecimal",
    "bddo:ibmHexadecimal reads IBM hexadecimal floating point",
    "C2 76 A0 00: sign 1, exponent 0x42, fraction 0x76A000, so -0x76A000 x 16^(66-64-6) = -118.625. 42 01 00 00 is "
    "not normalised and is read by the same formula: 0x010000 x 16^-4 = 1.0. The 64-bit 41 10 00 00 00 00 00 00 is "
    "2^52 x 16^-13 = 1.0.",
    FLOATS + ["req-pm-numeric-representation-3", "req-pm-numeric-representation-6"],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:ibmHexadecimal .
   ex:b a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:ibmHexadecimal .
   ex:c a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:ibmHexadecimal .
   """,
    bytes.fromhex("c276a000420100004110000000000000"),
    {"a": -118.625, "b": 1.0, "c": 1.0},
)

pp(
    "float-vax",
    "bddo:vaxF reads VAX F_floating and bddo:vaxD D_floating, each in its own word order",
    "48 42 00 00 is the words 0x4248, 0x0000: sign 0, exponent 132, fraction 0x480000, so (0.5 + 0x480000 / 2^24) x "
    "2^4 = 12.5. The D_floating 80 40 then six zero bytes is the word 0x4080 first: exponent 129, fraction 0, so "
    "0.5 x 2 = 1.0. The struct's little-endian declaration is not consulted.",
    FLOATS + ["req-pm-numeric-representation-4", "req-pm-numeric-representation-10", "req-pm-numeric-representation-6"],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:endianness bddo:BigEndian ; bddo:hasField ( ex:f ex:d ) .
   ex:f a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:vaxF .
   ex:d a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxD .
   """,
    bytes.fromhex("484200008040000000000000"),
    {"f": 12.5, "d": 1.0},
)

pp(
    "float-vax-reserved-operand",
    "A VAX reserved operand is a validation error",
    "00 80 00 00 is the word 0x8000: sign 1 with exponent 0, which is no number.",
    FLOATS + ["req-pm-numeric-representation-4", "req-pm-errors-4"],
    ["numeric-representation", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:f ) .
   ex:f a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:vaxF .
   """,
    bytes.fromhex("00800000"),
    error="Validation",
)

pp(
    "float-bfloat16",
    "bddo:bfloat16 is the upper half of a binary32 value",
    "3F C0 is the top sixteen bits of 3F C0 00 00, which is 1.5; C0 00 is -2.0. As binary16 the same bytes would be "
    "1.9375 and -2.0, so the first value shows the format is honoured. A field with no bddo:floatFormat stays "
    "IEEE 754: 3C 00 is 1.0.",
    FLOATS + ["req-pm-numeric-representation-5", "req-pm-numeric-representation-2"],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:plain ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float16 ; bddo:floatFormat bddo:bfloat16 .
   ex:b a bddo:Field ; bddo:dataType bddo:float16 ; bddo:floatFormat bddo:bfloat16 .
   ex:plain a bddo:Field ; bddo:dataType bddo:float16 ; bddo:floatFormat bddo:ieee754 .
   """,
    bytes.fromhex("3fc0c0003c00"),
    {"a": 1.5, "b": -2.0, "plain": 1.0},
)

pp(
    "float-format-on-data-type",
    "A data type's bddo:floatFormat applies to every field of that type",
    "ex:Ibm32 is a profile's 32-bit float type that states the format once; the field states none.",
    FLOATS + ["req-pm-numeric-representation-3"],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType ex:Ibm32 .
   ex:Ibm32 a bddo:DataType ; bddo:baseType bddo:baseFloat ; bddo:bitWidth 32 ; bddo:xsdType xsd:float ;
       bddo:floatFormat bddo:ibmHexadecimal .
   """,
    bytes.fromhex("c276a000"),
    {"a": -118.625},
)

pp(
    "float-format-width",
    "A float format on a width it is not defined for is a description error",
    "bddo:bfloat16 is a 16-bit format; the field is a bddo:float32.",
    ["req-pm-numeric-representation-7", "req-pm-errors-8"],
    ["numeric-representation", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:bfloat16 .
   """,
    bytes(4),
    error="Description",
)

# ----------------------------------------------------------------- binary-coded decimal

pp(
    "bcd",
    "bddo:bcd reads packed decimal digits in the byte order in force",
    "12 34 big-endian spells 1234; the same bytes little-endian spell 3412; the single byte 99 is 99.",
    ["req-pm-numeric-representation-8"],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:be ex:le ex:one ) .
   ex:be a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:bcd true .
   ex:le a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:endianness bddo:LittleEndian ; bddo:bcd true .
   ex:one a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bcd true .
   """,
    bytes.fromhex("1234123499"),
    {"be": 1234, "le": 3412, "one": 99},
)

pp(
    "bcd-invalid-nibble",
    "A nibble above 9 in a packed decimal field is a validation error",
    "1A: the low nibble is 10, which is no decimal digit.",
    ["req-pm-numeric-representation-9", "req-pm-errors-4"],
    ["numeric-representation", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bcd true .
   """,
    b"\x1a",
    error="Validation",
)

pp(
    "bcd-signed",
    "Packed decimal on a signed data type is a description error",
    "Packed decimal has no sign nibble, so a signed type has no packed-decimal reading: bddo:BcdShape refuses "
    "bddo:bcd true on a bddo:int16, whatever the bytes.",
    ["req-pm-errors-8"],
    ["numeric-representation", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:int16 ; bddo:bcd true .
   """,
    b"\x00\x45",
    error="Description",
)

# ----------------------------------------------------------------- custom encodings

pp(
    "encoding-custom-unsupported",
    "A custom encoding whose character set the processor does not decode is Unsupported",
    "No processor has a decoder for the character set this description names, so every processor refuses it rather "
    "than read the bytes as some other text.",
    ["req-pm-text-decoding-5", "req-pm-text-decoding-6", "req-pm-errors-10"],
    ["text-decoding", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:name ) .
   ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding ex:NoSuch .
   ex:NoSuch a bddo:Encoding , bddo:CustomEncoding ; bddo:ianaCharset "X-Hexplain-No-Such-Charset" .
   """,
    b"AB",
    error="Unsupported",
)

pp(
    "encoding-custom-known-charset",
    "A custom encoding of a character set the processor decodes reads as the registered encoding does",
    "ISO-8859-1 is a character set every Physical Parser decodes; a custom encoding that names it, in any letter "
    "case, reads E9 41 as the two characters U+00E9 and A, exactly as bddo:latin1 does.",
    ["req-pm-text-decoding-7"],
    ["text-decoding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:custom ex:registered ) .
   ex:custom a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding ex:Latin .
   ex:registered a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:latin1 .
   ex:Latin a bddo:Encoding , bddo:CustomEncoding ; bddo:ianaCharset "iso-8859-1" .
   """,
    b"\xe9A\xe9A",
    {"custom": "éA", "registered": "éA"},
)

# ----------------------------------------------------------------- computed layout extents

COMPUTED_LAYOUT = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:depth ex:pixels ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:depth a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
"""

pp(
    "layout-size-from-expression",
    "A computed dimension size, chunk extent and packed width resolve when the layout is resolved",
    "The row holds w * 2 cells, tiles are w cells wide and a cell is depth / 2 bits; each expression is evaluated "
    "with the containing struct as instance, and the field's value is its bytes.",
    ["req-pm-data-layouts-1", "req-pm-data-layouts-2"],
    ["data-layouts"],
    COMPUTED_LAYOUT
    + """
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:cellBitWidthFromExpression "depth / 2" ;
       dlv:hasDimension ( ex:DimX ) .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromExpression "w * 2" ;
       dlv:chunkSizeFromExpression "instance.w" .
   """,
    b"\x02\x08" + b"\x12\x34",
    {"w": 2, "depth": 8, "pixels": b"\x12\x34"},
)

pp(
    "layout-size-expression-not-integer",
    "A computed dimension size that is not an integer is a Type / HEL error",
    "w / 2.0 is a Float; an extent is an Integer, and an integral Float is not one.",
    ["req-pm-data-layouts-1", "req-pm-data-layouts-2", "req-pm-errors-6"],
    ["data-layouts", "errors"],
    COMPUTED_LAYOUT
    + """
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:hasDimension ( ex:DimX ) .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromExpression "w / 2.0" .
   """,
    b"\x02\x08" + b"\x12\x34",
    error="Expression",
)

# ----------------------------------------------------------------- the Adler-32 checksum field

pp(
    "checksum-adler32-field-width",
    "An Adler-32 whose checksum field is not a 32-bit integer is a description error",
    "bddo:adler32 is a 32-bit integer check; a bddo:uint16 checksum field cannot hold it.",
    ["req-pm-parsefield-30", "req-pm-errors-8"],
    ["algorithm", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 9 .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint16 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:adler32 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"Wikipedia" + b"\x03\x98",
    error="Description",
)

# ----------------------------------------------------------------- negative offsets

NEGATIVE = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:p ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:p a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffsetFromExpression "{value}" {base}.
"""

pp(
    "offset-negative-stream-start",
    "A negative offset from streamStart is a bounds error",
    "The expression yields -1; a distance from the start of the stream is never negative.",
    ["req-pm-parsefield-32", "req-pm-errors-3"],
    ["negative-offsets", "errors"],
    NEGATIVE.format(value="0 - 1", base=""),
    b"\x0a\x0b",
    error="Bounds",
)

pp(
    "offset-negative-stream-end",
    "A negative offset from streamEnd is a bounds error",
    "streamEnd counts backward from the end of the stream; -1 is not reinterpreted as one byte past it, or as one "
    "byte before it.",
    ["req-pm-parsefield-32", "req-pm-errors-3"],
    ["negative-offsets", "errors"],
    NEGATIVE.format(value="0 - 1", base="; bddo:offsetBase bddo:streamEnd "),
    b"\x0a\x0b",
    error="Bounds",
)

pp(
    "offset-current-negative",
    "A negative offset from currentPosition moves backward from the cursor",
    "After a and b the cursor is at offset 2; -2 from it is offset 0, inside the stream, so p reads a's byte again. "
    "currentPosition does not restore the cursor, so q, which follows, reads offset 1.",
    ["req-pm-parsefield-33", "req-pm-parsefield-7"],
    ["negative-offsets", "algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:p ex:q ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:p a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffsetFromExpression "0 - 2" ;
       bddo:offsetBase bddo:currentPosition .
   ex:q a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x0a\x0b",
    {"a": 10, "b": 11, "p": 10, "q": 11},
)

pp(
    "offset-current-negative-outside",
    "A negative offset from currentPosition whose target is before the stream is a bounds error",
    "The cursor is at offset 2 and the offset is -5: it is the target, not the sign, that is out of bounds.",
    ["req-pm-parsefield-33", "req-pm-errors-3"],
    ["negative-offsets", "errors"],
    NEGATIVE.format(value="0 - 5", base="; bddo:offsetBase bddo:currentPosition "),
    b"\x0a\x0b",
    error="Bounds",
)

# ----------------------------------------------------------------- fixed-point scale and enumerations (emission)

se(
    "fixed-point-scale",
    "A fixed-point field is emitted as the scaled value in an xsd:decimal literal",
    "00 01 80 00 with scale -16 is 98304 / 65536 = 1.5; the integer 3 with scale 2 is 12. The parsed value, which "
    "the bddo:validIf reads, stays the integer.",
    MINT + ["req-pm-value-mapping-1", "req-pm-emission-5"],
    ["value-mapping", "numeric-representation"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:q ex:coarse ) .
   ex:q a bddo:Field ; bddo:dataType bddo:uint32 ; bddo:fixedPointScale -16 ; bddo:validIf "self == 98304" ;
       hexplain:mapsToProperty ex:gain .
   ex:coarse a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:fixedPointScale 2 ; hexplain:mapsToProperty ex:step .
   """,
    bytes.fromhex("0001800003"),
    f'{SE_ROOT} a ex:Rec ; ex:gain "1.5"^^xsd:decimal ; ex:step "12"^^xsd:decimal .',
)

se(
    "fixed-point-scale-range",
    "The scales -4096 and 4096 are supported and emitted exactly",
    "The integer 1 with scale -4096 is 2^-4096, a decimal of 4096 fraction digits, and with scale 4096 it is 2^4096, "
    "an integer of 1234 digits: every Semantic Emitter supports the whole range, and an xsd:decimal holds both "
    "exactly.",
    MINT + ["req-pm-value-mapping-2", "req-pm-value-mapping-1"],
    ["value-mapping", "numeric-representation"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:tiny ex:huge ) .
   ex:tiny a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:fixedPointScale -4096 ; hexplain:mapsToProperty ex:tiny .
   ex:huge a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:fixedPointScale 4096 ; hexplain:mapsToProperty ex:huge .
   """,
    b"\x01\x01",
    f'{SE_ROOT} a ex:Rec ; ex:tiny "0.{str(5**4096).zfill(4096)}"^^xsd:decimal ; ex:huge "{2**4096}"^^xsd:decimal .',
)

ENUM_BOTH = """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:colour ) .
   ex:colour a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:colourType ;
       hexplain:mapsToObjectProperty ex:colourKind ;
       bddo:enumeration [ a bddo:Enumeration ;
           bddo:hasEnumValue [ a bddo:EnumValue ; bddo:enumRawValue 2 ; bddo:enumSymbol ex:Colour ] ,
                             [ a bddo:EnumValue ; bddo:enumRawValue 4 ; rdfs:label "alpha" ] ] .
   """

se(
    "enum-both-properties",
    "An enumerated field mapped both ways emits the literal and the symbol on each property's own rule",
    "Colour type 2 has the symbol ex:Colour: the literal and the symbol on the mapsToProperty property, and the "
    "symbol on the mapsToObjectProperty property.",
    MINT + ["req-pm-emission-13", "req-pm-emission-2", "req-pm-emission-6"],
    ["emission"],
    ENUM_BOTH,
    b"\x02",
    f'{SE_ROOT} a ex:Image ; ex:colourType "2"^^xsd:unsignedByte , ex:Colour ; ex:colourKind ex:Colour .',
)

se(
    "enum-both-properties-no-symbol",
    "An enumerated field mapped both ways emits the literal alone for a value without a symbol",
    "Colour type 4 matches a value with no bddo:enumSymbol: there is no symbol for either property, so only the "
    "literal is emitted.",
    MINT + ["req-pm-emission-13", "req-pm-emission-2", "req-pm-emission-6"],
    ["emission"],
    ENUM_BOTH,
    b"\x04",
    f'{SE_ROOT} a ex:Image ; ex:colourType "4"^^xsd:unsignedByte .',
)

# ----------------------------------------------------------------- HEL: reserved roots

hel(
    "root-as-function-name",
    "A reserved root written as a function name is a syntax error",
    "asset(1) is not a call: asset is a root, and no function is named for one.",
    ["req-hel-formal-grammar-4", "req-hel-formal-grammar-3"] + SYNTAX,
    ["syntax"],
    one("asset(1)"),
    b"",
    error="Expression",
)

hel(
    "root-as-key",
    "A reserved root written as a key after a dot is a syntax error",
    "a.param: a step is parent or a name, and a name is never a reserved word.",
    ["req-hel-formal-grammar-4"] + SYNTAX,
    ["syntax"],
    one("a.param", ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x01",
    error="Expression",
)

hel(
    "stream-key-parent-is-null",
    "A .parent after a key of stream is Null",
    "The stream is not a struct instance, so stream.length records no holder: its parent is Null, which equals no "
    "Integer, and is not the current struct, whose field a would otherwise be read.",
    ["req-hel-reserved-roots-5"],
    ["reserved-roots"],
    derived(
        ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."],
        {"viaStream": "stream.length.parent.a == 1", "direct": "a == 1"},
    ),
    b"\x01",
    {"a": 1, "viaStream": False, "direct": True},
)

# ----------------------------------------------------------------- HEL: the math group and unsigned 64-bit values

hel(
    "math-unsigned-64",
    "The math functions accept an unsigned 64-bit Integer above 2^63-1",
    "They are functions of a value, not Integer arithmetic: the rounding functions and abs return the largest uint64 "
    "unchanged, min and max compare it by value, and toString renders its digits.",
    ["req-hel-math-5", "req-hel-numeric-semantics-5"],
    ["math", "numeric-semantics"],
    derived(
        ["ex:big a bddo:Field ; bddo:dataType bddo:uint64 ."],
        {
            "fl": "floor(big)",
            "ce": "ceil(big)",
            "tr": "trunc(big)",
            "ro": "round(big)",
            "ab": "abs(big)",
            "mx": "max(1, big)",
            "mn": "min(big, 1)",
            "text": "toString(big)",
        },
    ),
    b"\xff" * 8,
    {
        "big": 2**64 - 1,
        "fl": 2**64 - 1,
        "ce": 2**64 - 1,
        "tr": 2**64 - 1,
        "ro": 2**64 - 1,
        "ab": 2**64 - 1,
        "mx": 2**64 - 1,
        "mn": 1,
        "text": "18446744073709551615",
    },
)

hel(
    "math-tostring-shortest-digits",
    "toString of a Float writes the shortest digits that round-trip",
    "The smallest subnormal is written 4.9E-324, the two digits that read back to it, not the seventeen of its exact "
    "decimal expansion's rounding; 1.0E23 is written with one digit, though its binary64 value is "
    "9.999999999999999161E22.",
    ["req-hel-math-6", "req-hel-math-4"],
    ["math"],
    derived([], {"tiny": "toString(5e-324)", "big": "toString(1e23)"}),
    b"",
    {"tiny": "4.9E-324", "big": "1.0E23"},
)

# ----------------------------------------------------------------- HEL-RE

TEXT = {"features": {"requires": ["hel-ext-text"]}}

hel(
    "regex-hyphen-in-class",
    "An unescaped hyphen in a character class is a literal first or last, and a range between two characters",
    "[-a] and [a-] each contain the hyphen; [a-c] is the range.",
    ["req-hel-ext-text-6", "req-hel-ext-text-4"],
    ["ext-text"],
    derived(
        [],
        {
            "first": "matches('-', '[-a]')",
            "last": "matches('-', '[a-]')",
            "range": "matches('b', '[a-c]')",
            "notInRange": "matches('-', '[a-c]')",
        },
    ),
    b"",
    {"first": True, "last": True, "range": True, "notInRange": False},
    manifest=TEXT,
)

hel(
    "regex-hyphen-misplaced",
    "A hyphen that is neither first, last nor a range is an argument error",
    "[a-c-e]: the second hyphen follows a range, so it cannot begin one, and it is not the class's last member.",
    ["req-hel-ext-text-6", TYPE_ERROR],
    ["ext-text"],
    one("matches('b', '[a-c-e]')"),
    b"",
    error="Expression",
    manifest=TEXT,
)

hel(
    "regex-unknown-block",
    "An unknown block name in a block escape is an argument error",
    "\\\\p{IsNoSuchBlock} names no Unicode block; it is not read as matching nothing.",
    ["req-hel-ext-text-5", TYPE_ERROR],
    ["ext-text"],
    one(r"matches('a', '\\\\p{IsNoSuchBlock}')"),
    b"",
    error="Expression",
    manifest=TEXT,
)

hel(
    "regex-quantifier-bound",
    "A quantifier bound above 2^31-1 is an argument error",
    "a{2147483648}: the bound is one more than the largest a pattern may state.",
    ["req-hel-ext-text-4", TYPE_ERROR],
    ["ext-text"],
    one("matches('a', 'a{2147483648}')"),
    b"",
    error="Expression",
    manifest=TEXT,
)
