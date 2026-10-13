"""Writer cases, second module: the forms of a value (Processing Model, Serialisation, rules 3, 5, 6, 7 and 9).

cases_writer.py holds one case per rule; these cases follow a value through the representations the rules name:
variable-length integers, bit orders, the non-IEEE float formats and packed decimal, a scalar under a bound length,
type selection by parameter and by condition, and an encoded field in its region. As there, every byte string is read
off the rule the case cites. One case, w-codec-compressor-round-trip, runs a compressing encoder, whose bytes are its
own: it states the tree the written stream must parse back to ("verify": "round-trip") instead of bytes.
"""

from __future__ import annotations

from typing import Any

from suite import Case

PM = "processing#"
CASES = []

SELECTION = "req-pm-serialisation-17"
CODEC = "req-pm-serialisation-18"
RECOMPUTED = "req-pm-serialisation-21"
CONSISTENT = "req-pm-serialisation-22"
TEXT = "req-pm-serialisation-23"
PADDING = "req-pm-serialisation-25"
EXTENT = "req-pm-serialisation-26"
LITERAL_REGION = "req-pm-serialisation-28"
ENCODED_REGION = "req-pm-serialisation-29"
BOUND_LENGTH = "req-pm-serialisation-30"
TERMINATED = "req-pm-serialisation-31"
NOT_PADDED = "req-pm-serialisation-32"
IBM = "req-pm-serialisation-33"
VAX = "req-pm-serialisation-34"
BFLOAT = "req-pm-serialisation-35"
NO_INVERSE = "req-pm-serialisation-36"
BCD = "req-pm-serialisation-37"
FIXED_POINT = "req-pm-serialisation-38"


def w(
    id: str,
    title: str,
    intent: str,
    reqs: list[str],
    sections: list[str],
    description: str,
    tree: Any,
    expected: bytes | None = None,
    error: str | None = None,
    reparsed: Any = None,
    manifest: dict[str, Any] | None = None,
) -> None:
    CASES.append(
        Case(
            id=f"w-{id}",
            cls="writer",
            title=title,
            intent=intent,
            requirements=reqs,
            sections=[PM + s for s in ["serialisation", *sections]],
            description=description,
            tree=tree,
            expected_bytes=expected,
            error=error,
            reparsed=reparsed,
            manifest=dict({"features": {"requires": ["writer"]}}, **(manifest or {})),
        )
    )


# ----------------------------------------------------------------- rule 3: extents

w(
    "varint-shortest",
    "A varint is written in the shortest encoding of its value",
    "300 as a bddo:varuint is LEB128 AC 02; -3 as a bddo:varint is zigzag 5, one byte 05; 300 as a "
    "bddo:sqliteVarint is 82 2C. Each is the shortest encoding: no padding continuation byte is written, whatever "
    "length a stream the tree was parsed from gave it.",
    [EXTENT],
    ["size-resolution", "text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:u ex:s ex:q ) .
   ex:u a bddo:Field ; bddo:dataType bddo:varuint .
   ex:s a bddo:Field ; bddo:dataType bddo:varint .
   ex:q a bddo:Field ; bddo:dataType bddo:sqliteVarint .
   """,
    {"u": 300, "s": -3, "q": 300},
    bytes.fromhex("ac02 05 822c"),
)

w(
    "repeat-until-to-end-not-padded",
    "A to-end sequence that its condition ends is written as its elements, with no padding",
    "items runs to the end of the stream unless an element is 0. The tree's sequence ends with 0, so the condition "
    "ends it: its three elements are written and nothing is added to reach the end of the region; tail follows.",
    [NOT_PADDED],
    ["size-resolution"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:items ex:tail ) .
   ex:items a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:sizeToEndOfStream true ; bddo:repeatUntil "self == 0" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"items": [1, 2, 0], "tail": 9},
    bytes.fromhex("010200 09"),
)

w(
    "terminator-in-value",
    "A value in which its terminator occurs is refused",
    "line ends at the first 0D 0A. The tree's value holds 0D 0A inside it, so the stream would read back as the "
    "two bytes before it: a validation error.",
    [TERMINATED],
    ["terminators"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:line ex:tail ) .
   ex:line a bddo:Field ; bddo:dataType bddo:bytes ; bddo:terminator "0D0A"^^xsd:hexBinary .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"line": bytes.fromhex("41420d0a43"), "tail": 1},
    error="Validation",
)

BOUND_STRING = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:s ex:tail ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:trimNull true ;
       bddo:sizeFromField ex:n .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """

w(
    "trim-null-bound-length-padded",
    "A trimNull string under a bound length is NUL-padded to that length",
    "n is bound to 6, so the region of s is six bytes: 'AB' is followed by four NUL code units, which the parse "
    "removes again, and n is written as 6. (Parsing 06 41 42 00 00 00 00 gives this tree.)",
    [BOUND_LENGTH, TEXT],
    ["size-resolution", "text-decoding"],
    BOUND_STRING,
    {"n": 6, "s": "AB", "tail": 7},
    bytes.fromhex("06 4142 00000000 07"),
)

w(
    "trim-null-unbound-length-filled",
    "A trimNull string under an unbound length is written at its own length",
    "The tree leaves n unbound: the region is the value's own length, two bytes, and n is filled with 2.",
    [RECOMPUTED],
    ["size-resolution", "text-decoding"],
    BOUND_STRING,
    {"n": None, "s": "AB", "tail": 7},
    bytes.fromhex("02 4142 07"),
)

w(
    "trim-null-bound-length-too-long",
    "A value longer than its bound length is refused",
    "n is bound to 1 and 'AB' is two bytes: no padding makes it fit, a validation error.",
    [BOUND_LENGTH],
    ["size-resolution"],
    BOUND_STRING,
    {"n": 1, "s": "AB", "tail": 7},
    error="Validation",
)

w(
    "bound-length-not-padded-without-trim-null",
    "A string without trimNull must be exactly its bound length",
    "s does not trim NULs, so padding would read back as part of the value: n is bound to 4, 'AB' is two bytes, "
    "and the tree is refused.",
    [BOUND_LENGTH, CONSISTENT],
    ["size-resolution"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:s ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:sizeFromField ex:n .
   """,
    {"n": 4, "s": "AB"},
    error="Validation",
)

# ----------------------------------------------------------------- rule 3 and rule 6: bit orders

w(
    "bits-lsb-first",
    "Bit fields are packed least-significant bit first under bddo:LSBFirst",
    "a (3 bits, 4) takes the low three bits of the first byte and b (5 bits, 22) the five above them: "
    "10110 100 = B4. c (12 bits, 0xABC) continues in the same order, its low eight bits BC in the next byte and "
    "its high four, A, in the low nibble of the third; d (4 bits, 5) takes the nibble above: 5A.",
    [EXTENT, SELECTION],
    ["bit-cursor", "byte-order"],
    """
   ex:Root a bddo:Struct ; bddo:bitOrder bddo:LSBFirst ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 3 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 5 .
   ex:c a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:bitLength 12 .
   ex:d a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   """,
    {"a": 4, "b": 22, "c": 0xABC, "d": 5},
    bytes.fromhex("b4 bc 5a"),
)

w(
    "bits-field-order-overrides-struct",
    "A field's own bit order is the effective one, and a change of order starts a new byte",
    "The struct is LSBFirst; a declares MSBFirst and is written in the top three bits of the first byte "
    "(101 00000 = A0, the unused bits 0). b, back under LSBFirst, differs in order from a, so it begins on the "
    "next byte, in its low five bits: 16. (The parse case pp-bits-field-order-overrides-struct reads B4 16 as this "
    "tree; the bits it skips are written as 0.)",
    [EXTENT, PADDING],
    ["bit-cursor", "byte-order"],
    """
   ex:Root a bddo:Struct ; bddo:bitOrder bddo:LSBFirst ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 3 ; bddo:bitOrder bddo:MSBFirst .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 5 .
   """,
    {"a": 5, "b": 22},
    bytes.fromhex("a0 16"),
)

# ----------------------------------------------------------------- rule 6: type selection

w(
    "parameterised-struct",
    "A node under a parameterised struct is serialised with the arguments its field names",
    "row is a Row with n = 2, so its local binding bytes is 4 and data is four bytes; the binding writes nothing "
    "and is no member of the node.",
    [SELECTION],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.row ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.row a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.n" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ) ; bddo:hasField ( ex:Row.bytes ex:Row.data ) .
   ex:Row.n a bddo:Parameter .
   ex:Row.bytes a bddo:LocalBinding ; bddo:localExpression "param.n * 2" .
   ex:Row.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "bytes" .
   """,
    {"n": 2, "row": {"data": b"abcd"}},
    bytes.fromhex("02 61626364"),
)

w(
    "parameterised-struct-argument-mismatch",
    "A size the arguments give that the node does not serialise to is refused",
    "With n = 3 the Row's data must be six bytes; the tree holds four. The expression cannot be inverted, so the "
    "tree is refused rather than n rewritten.",
    [SELECTION],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.row ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.row a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.n" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ) ; bddo:hasField ( ex:Row.bytes ex:Row.data ) .
   ex:Row.n a bddo:Parameter .
   ex:Row.bytes a bddo:LocalBinding ; bddo:localExpression "param.n * 2" .
   ex:Row.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "bytes" .
   """,
    {"n": 3, "row": {"data": b"abcd"}},
    error="Validation",
)

CONDITIONAL = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:body ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ;
       bddo:hasConditionalDataType (
           [ a bddo:DataTypeRule ; bddo:condition "kind == 1" ; bddo:ruleDataType ex:A ]
           [ a bddo:DataTypeRule ; bddo:condition "kind == 2" ; bddo:ruleDataType ex:B ] ) .
   ex:A a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:B a bddo:Struct ; bddo:hasField ( ex:b ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   """

w(
    "conditional-data-type-selected",
    "A conditional data type is evaluated over the fields written so far",
    "kind is 1, so body is an A: its one byte 05 is written into the region of two bytes, which is filled to its "
    "end with a fill byte.",
    [SELECTION, LITERAL_REGION],
    ["algorithm", "size-resolution"],
    CONDITIONAL,
    {"kind": 1, "body": {"a": 5}},
    bytes.fromhex("01 05 00"),
)

w(
    "conditional-data-type-default",
    "A field whose rules all fail is written in its declared data type",
    "kind is 9: neither rule applies, so body is its declared bddo:bytes, two bytes.",
    [SELECTION],
    ["algorithm"],
    CONDITIONAL,
    {"kind": 9, "body": bytes.fromhex("aabb")},
    bytes.fromhex("09 aabb"),
)

w(
    "conditional-data-type-wrong-members",
    "A node that is not of the selected type is refused",
    "kind is 2, which selects B; the node's member is a, a field of A.",
    [SELECTION],
    ["algorithm"],
    CONDITIONAL,
    {"kind": 2, "body": {"a": 5}},
    error="Validation",
)

# ----------------------------------------------------------------- rule 4: an offset before the stream

w(
    "offset-before-stream-start",
    "An offset target before the start of the stream is refused",
    "ptr is 4, so the target of val is 4 - 8 = -4, before the first byte of the output: a validation error.",
    [PADDING],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:ptr ex:val ) .
   ex:ptr a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:val a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffsetFromExpression "ptr - 8" .
   """,
    {"ptr": 4, "val": 1},
    error="Validation",
)

# ----------------------------------------------------------------- rule 9: numeric representations

IBM_FIELDS = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:z ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:ibmHexadecimal .
   ex:b a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:ibmHexadecimal .
   ex:z a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:ibmHexadecimal .
   ex:c a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:ibmHexadecimal .
   """

w(
    "float-ibm-hexadecimal",
    "An IBM hexadecimal float is written as the normalised number of the format",
    "-118.625 is -0.76A × 16^2: sign 1, exponent 64 + 2 = 0x42, fraction 76A000, bytes C2 76 A0 00. 1.0 is "
    "0.1 × 16^1: 41 10 00 00, the normalised form, not the 42 01 00 00 a stream may also spell it. -0.0 is a zero "
    "fraction and a zero exponent under the sign: 80 00 00 00. In 64 bits 1.0 is 41 10 then six zero bytes.",
    [IBM],
    ["numeric-representation"],
    IBM_FIELDS,
    {"a": -118.625, "b": 1.0, "z": -0.0, "c": 1.0},
    bytes.fromhex("c276a000 41100000 80000000 4110000000000000"),
)

w(
    "float-ibm-nan",
    "A NaN has no IBM hexadecimal form",
    "The format has no NaN: a validation error, never bits that read back as a number.",
    [NO_INVERSE],
    ["numeric-representation"],
    IBM_FIELDS,
    {"a": float("nan"), "b": 1.0, "z": 0.0, "c": 1.0},
    error="Validation",
)

w(
    "float-ibm-significand-not-exact",
    "A value whose significand the IBM format cannot carry is refused",
    "The binary32 nearest 0.1 is 0xCCCCCD × 2^-27, twenty-four significant bits. Its IBM fraction would stand at "
    "exponent 0x40, where one unit is 2^-24: the three low bits fall off, the nearest IBM number is another "
    "value, and it would read back as that value. A validation error.",
    [NO_INVERSE],
    ["numeric-representation"],
    IBM_FIELDS,
    {"a": 0.10000000149011612, "b": 1.0, "z": 0.0, "c": 1.0},
    error="Validation",
)

VAX_FIELDS = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:f ex:d ex:z ) .
   ex:f a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:vaxF .
   ex:d a bddo:Field ; bddo:dataType bddo:float64 ; bddo:floatFormat bddo:vaxF .
   ex:z a bddo:Field ; bddo:dataType bddo:float32 ; bddo:floatFormat bddo:vaxF .
   """

w(
    "float-vax",
    "A VAX float is written in the format's own word order",
    "12.5 is 0.78125 × 2^4: exponent 128 + 4 = 132, fraction (0.78125 - 0.5) × 2^24 = 0x480000, the 32 bits "
    "42 48 00 00, stored as two 16-bit words each least significant byte first: 48 42 00 00. 1.0 as D_floating "
    "is exponent 129 and a zero fraction, 40 80 then zeros, stored 80 40 00 00 00 00 00 00. A positive zero is "
    "all-zero bytes. The struct's byte order is not consulted.",
    [VAX],
    ["numeric-representation"],
    VAX_FIELDS,
    {"f": 12.5, "d": 1.0, "z": 0.0},
    bytes.fromhex("48420000 8040000000000000 00000000"),
)

w(
    "float-vax-infinity",
    "An infinity has no VAX form",
    "VAX floats have neither infinities nor NaN: a validation error.",
    [NO_INVERSE],
    ["numeric-representation"],
    VAX_FIELDS,
    {"f": float("inf"), "d": 1.0, "z": 0.0},
    error="Validation",
)

w(
    "float-vax-negative-zero",
    "A negative zero has no VAX form",
    "A set sign bit with a zero exponent is VAX's reserved operand, which the parse refuses: -0.0 cannot be written.",
    [NO_INVERSE],
    ["numeric-representation"],
    VAX_FIELDS,
    {"f": 12.5, "d": 1.0, "z": -0.0},
    error="Validation",
)

BFLOAT_FIELDS = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float16 ; bddo:floatFormat bddo:bfloat16 .
   ex:b a bddo:Field ; bddo:dataType bddo:float16 ; bddo:floatFormat bddo:bfloat16 ;
       bddo:endianness bddo:LittleEndian .
   """

w(
    "float-bfloat16",
    "A bfloat16 is the sixteen high bits of the binary32 value, the infinities included",
    "1.0 is the binary32 3F800000, so a is 3F 80. Negative infinity is FF800000, so b is FF 80, written "
    "little-endian: 80 FF.",
    [BFLOAT],
    ["numeric-representation"],
    BFLOAT_FIELDS,
    {"a": 1.0, "b": float("-inf")},
    bytes.fromhex("3f80 80ff"),
)

w(
    "float-bfloat16-low-bits",
    "A binary32 value with low bits set has no bfloat16 form",
    "1.0000001192092896 is the binary32 3F800001: its sixteen low bits are not zero, so no bfloat16 reads back as it.",
    [NO_INVERSE],
    ["numeric-representation"],
    BFLOAT_FIELDS,
    {"a": 1.0000001192092896, "b": 1.0},
    error="Validation",
)

BCD_FIELDS = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:be ex:le ex:one ex:s ) .
   ex:be a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:bcd true .
   ex:le a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:endianness bddo:LittleEndian ; bddo:bcd true .
   ex:one a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bcd true .
   ex:s a bddo:Field ; bddo:dataType bddo:int16 ; bddo:bcd true .
   """

w(
    "bcd",
    "Packed decimal is written two digits to a byte, zero-padded, in the byte order in force",
    "1234 big-endian is 12 34; 3412 little-endian is its pairs 34 12 with the least significant first, 12 34; 7 "
    "in one byte is 07, padded with a leading zero digit; 45 in two bytes is 00 45.",
    [BCD],
    ["numeric-representation"],
    BCD_FIELDS,
    {"be": 1234, "le": 3412, "one": 7, "s": 45},
    bytes.fromhex("1234 1234 07 0045"),
)

w(
    "bcd-too-many-digits",
    "A number of more digits than the field holds is refused",
    "one is one byte, two digits; 123 has three.",
    [BCD],
    ["numeric-representation"],
    BCD_FIELDS,
    {"be": 1234, "le": 3412, "one": 123, "s": 45},
    error="Validation",
)

w(
    "bcd-negative",
    "A negative number has no packed-decimal form",
    "s is a signed type, so -5 is inside its range; packed decimal spells non-negative numbers only.",
    [BCD],
    ["numeric-representation"],
    BCD_FIELDS,
    {"be": 1234, "le": 3412, "one": 7, "s": -5},
    error="Validation",
)

w(
    "fixed-point-raw-integer",
    "A fixed-point scale changes nothing a Writer does",
    "q is a Q16.16 number: the tree holds the integer as read, 98304 (which stands for 1.5), and it is written "
    "unchanged, 00 01 80 00, never scaled.",
    [FIXED_POINT],
    ["numeric-representation"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:q ) .
   ex:q a bddo:Field ; bddo:dataType bddo:uint32 ; bddo:fixedPointScale -16 .
   """,
    {"q": 98304},
    bytes.fromhex("00018000"),
)

w(
    "text-number-infinity",
    "An infinite Float has no text-number spelling",
    "The parse rules read no spelling as an infinity, so none can be written: a validation error.",
    [TEXT],
    ["text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:x ) .
   ex:x a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:terminator "0A"^^xsd:hexBinary .
   """,
    {"x": float("inf")},
    error="Validation",
)

# ----------------------------------------------------------------- rule 7: an encoded field and its region

STORED = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:tail ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 ; hexplain:isEncodedWith menc:Store .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """

w(
    "codec-literal-region-fits",
    "An encoding that fills its literal region is written",
    "menc:Store leaves the three bytes as they are; they are the field's value and fill bddo:size 3 exactly.",
    [CODEC, ENCODED_REGION],
    ["minimum-codecs", "size-resolution"],
    STORED,
    {"data": b"xyz", "tail": 9},
    b"xyz\x09",
)

w(
    "codec-literal-region-overflow",
    "An encoding longer than its literal region is refused",
    "The four stored bytes do not fit bddo:size 3.",
    [ENCODED_REGION],
    ["minimum-codecs", "size-resolution"],
    STORED,
    {"data": b"wxyz", "tail": 9},
    error="Validation",
)

w(
    "codec-literal-region-short",
    "An encoding shorter than its literal region is refused when its codec would read the fill",
    "Two stored bytes would be followed by one fill byte, and menc:Store reads every byte of its region: the "
    "stream would parse to three bytes, another tree. A validation error.",
    [ENCODED_REGION],
    ["minimum-codecs", "size-resolution", "round-trip"],
    STORED,
    {"data": b"xy", "tail": 9},
    error="Validation",
)

w(
    "codec-pipeline-kinds-disconnected",
    "A pipeline whose kinds do not connect is a description error, whatever the tree",
    "menc:Zlib yields bytes and menc:CMYKToRGB takes samples, so the steps do not connect. That is an error of "
    "the description, raised when it is loaded (the parse case pp-codec-pipeline-kinds-disconnected refuses the "
    "same description), before any question about the tree or about which of its codecs encode.",
    [CODEC],
    ["codec-contracts", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ;
       hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Zlib ]
                                  [ a hexplain:EncodingStep ; hexplain:codec menc:CMYKToRGB ] ) .
   """,
    {"data": bytes.fromhex("00000000")},
    error="Description",
    manifest={"codecs": {"requires": ["https://hexplain.io/ns/register/media-encoding#CMYKToRGB"]}},
)

w(
    "codec-encode-exceeds-limit",
    "An encode output beyond the decoded-byte limit is a resource-limit error",
    "The case lowers maxDecodedBytes to 4. menc:Store's output for the eight bytes of data is eight bytes, which "
    "counts toward the limit and exceeds it.",
    [CODEC],
    ["minimum-codecs", "resource-limits"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n ; hexplain:isEncodedWith menc:Store .
   """,
    {"n": None, "data": bytes(range(8))},
    error="ResourceLimit",
    manifest={"limits": {"maxDecodedBytes": 4}},
)

COMPRESSED = {"magic": 0x7E, "payload": b"compressible " * 12}

w(
    "codec-compressor-round-trip",
    "A compressed field parses back to the tree it was written from",
    "payload is encoded with menc:Deflate, whose bytes are the encoder's own (its level, its block structure), so "
    "the case fixes no bytes: the written stream is parsed with the same description and must give this tree "
    "again.",
    [CODEC],
    ["minimum-codecs", "round-trip"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:magic ex:payload ) .
   ex:magic a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:payload a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ;
       hexplain:isEncodedWith menc:Deflate .
   """,
    COMPRESSED,
    reparsed=COMPRESSED,
)
