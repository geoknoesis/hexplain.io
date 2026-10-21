"""Writer cases: the serialisation rules of the Processing Model (Serialisation, write direction), one rule per case.

A case gives a description, a root struct and a logical tree (tree.json, in the canonical JSON form of a parsed tree),
and states the exact bytes the rules require (expected.hex) or the error category they require instead. Every byte
string is read off the rule the case cites; the comments give the arithmetic where it is not obvious. The descriptions
use only constructs whose written form the rules fix: no case depends on what a compressing encoder chooses to emit.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any

from suite import Case

PM = "processing#"
CASES = []

ORDER = "req-pm-serialisation-1"
PRESENCE = "req-pm-serialisation-12"
STRUCT_SIZE = "req-pm-serialisation-14"
SELECTION = "req-pm-serialisation-17"
CODEC = "req-pm-serialisation-18"
BACK_PATCH = "req-pm-serialisation-19"
SCOPE = "req-pm-serialisation-20"
RECOMPUTED = "req-pm-serialisation-21"
CONSISTENT = "req-pm-serialisation-22"
TEXT = "req-pm-serialisation-23"
PADDING = "req-pm-serialisation-25"
SEPARATOR = "req-pm-serialisation-27"
LITERAL_REGION = "req-pm-serialisation-28"
TERMINATED = "req-pm-serialisation-31"


def w(
    id: Any,
    title: str,
    intent: Any,
    reqs: Any,
    sections: Any,
    description: str,
    tree: Any,
    expected: Any = None,
    error: Any = None,
    **kw: Any,
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
            manifest={"features": {"requires": ["writer"]}},
            **kw,
        )
    )


def crc32(data: bytes) -> bytes:
    """The CRC-32 of [data] as a big-endian uint32."""
    return struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF)


# ----------------------------------------------------------------- rule 1: field order and a consistent tree

PLAIN = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   """

w(
    "field-order",
    "Fields are written in list order, a sync struct beginning with its marker",
    "a, then the nested struct (its marker FF D8, then v), then b as a big-endian uint16: 01, FF D8 02, 00 03.",
    [ORDER],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:seg ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   ex:Seg a bddo:Struct ; bddo:syncOnMarker "FFD8"^^xsd:hexBinary ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   """,
    {"a": 1, "seg": {"v": 2}, "b": 3},
    bytes.fromhex("01 ffd8 02 0003"),
)

w(
    "tree-undeclared-key",
    "A tree that binds a field the description does not declare is refused",
    "zz is no field of Root: the tree is inconsistent with the description, a validation error.",
    [ORDER],
    [],
    PLAIN,
    {"a": 1, "b": 2, "zz": 3},
    error="Validation",
)

w(
    "tree-required-unbound",
    "A tree that leaves a required field unbound is refused",
    "b has no presence condition and no fixed value, so it is required; the tree leaves it unbound.",
    [ORDER],
    [],
    PLAIN,
    {"a": 1, "b": None},
    error="Validation",
)

w(
    "tree-struct-for-scalar",
    "A struct node for a scalar field is refused",
    "a is a uint8, a value; the tree holds a struct node there, a node of another kind.",
    [ORDER],
    [],
    PLAIN,
    {"a": {"v": 1}, "b": 2},
    error="Validation",
)

w(
    "tree-scalar-for-repeated",
    "A single value for a repeated field is refused",
    "v repeats twice, so its node is an array; a single value is a node of another kind.",
    [ORDER],
    [],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 .
   """,
    {"v": 1},
    error="Validation",
)

FIXED = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:magic ex:tag ex:tail ) .
   ex:magic a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:hasFixedValue 4660 .
   ex:tag a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ; bddo:hasFixedValue "CAFE"^^xsd:hexBinary .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """

w(
    "fixed-value-filled",
    "A fixed-value field the tree leaves unbound is written as its constant",
    "magic is 4660 = 0x1234 and tag is CA FE; the tree binds neither, and both are written.",
    [ORDER],
    ["algorithm"],
    FIXED,
    {"magic": None, "tag": None, "tail": 9},
    bytes.fromhex("1234 cafe 09"),
)

w(
    "fixed-value-mismatch",
    "A tree that binds another value than the constant is refused",
    "magic is bound to 4661 where the description fixes 4660: writing it would give a stream the description "
    "refuses to read.",
    [ORDER],
    ["algorithm"],
    FIXED,
    {"magic": 4661, "tag": bytes.fromhex("cafe"), "tail": 9},
    error="Validation",
)

# ----------------------------------------------------------------- rule 1: presence

OPTIONAL = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:flags ex:opt ex:tail ) .
   ex:flags a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:opt a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:isPresentIf "flags == 1" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """

w(
    "presence-absent",
    "A field whose presence condition is false is not written",
    "flags is 0, so opt is absent and unbound: flags and tail are the whole stream.",
    [PRESENCE],
    ["algorithm"],
    OPTIONAL,
    {"flags": 0, "opt": None, "tail": 9},
    bytes.fromhex("00 09"),
)

w(
    "presence-present",
    "A field whose presence condition is true is written in its place",
    "flags is 1, so opt is present, between flags and tail.",
    [PRESENCE],
    ["algorithm"],
    OPTIONAL,
    {"flags": 1, "opt": 5, "tail": 9},
    bytes.fromhex("01 0005 09"),
)

w(
    "presence-absent-bound",
    "A field bound where its presence condition is false is refused",
    "flags is 0, so opt must be unbound; the tree binds it.",
    [PRESENCE],
    ["algorithm"],
    OPTIONAL,
    {"flags": 0, "opt": 5, "tail": 9},
    error="Validation",
)

w(
    "presence-present-unbound",
    "A field unbound where its presence condition is true is refused",
    "flags is 1, so opt must be bound; the tree leaves it unbound.",
    [PRESENCE],
    ["algorithm"],
    OPTIONAL,
    {"flags": 1, "opt": None, "tail": 9},
    error="Validation",
)

# ----------------------------------------------------------------- rule 2: dependent lengths and counts

LENGTH = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n .
   """

w(
    "length-filled",
    "An unbound length field is filled with the dependent field's byte length",
    "data is three bytes, so n, which the tree leaves unbound, is written as 3.",
    [RECOMPUTED],
    ["size-resolution"],
    LENGTH,
    {"n": None, "data": bytes.fromhex("010203")},
    bytes.fromhex("03 010203"),
)

w(
    "length-terminator-included",
    "A recomputed length counts the terminator",
    "box holds the string 'hi' and its terminator 00: three serialised bytes, so n, the length of box, is 3.",
    [RECOMPUTED, TERMINATED],
    ["size-resolution", "terminators"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:box ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:sizeFromField ex:n .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:terminator "00"^^xsd:hexBinary .
   """,
    {"n": None, "box": {"s": "hi"}},
    bytes.fromhex("03 6869 00"),
)

w(
    "length-inconsistent",
    "A bound length that differs from its recomputation is refused",
    "n is bound to 2 and data is three bytes the tree itself determines: the tree is never silently corrected.",
    [CONSISTENT],
    ["size-resolution"],
    LENGTH,
    {"n": 2, "data": bytes.fromhex("010203")},
    error="Validation",
)

COUNT = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:v ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:v a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:repeatCountFromField ex:n .
   """

w(
    "count-filled",
    "An unbound count field is filled with the number of elements",
    "v has two elements, so n is written as 2, then 00 01 and 00 02.",
    [RECOMPUTED],
    ["algorithm"],
    COUNT,
    {"n": None, "v": [1, 2]},
    bytes.fromhex("02 0001 0002"),
)

w(
    "count-inconsistent",
    "A bound count that differs from the number of elements is refused",
    "n is bound to 7 and v has two elements.",
    [CONSISTENT],
    ["algorithm"],
    COUNT,
    {"n": 7, "v": [1, 2]},
    error="Validation",
)

w(
    "size-expression-mismatch",
    "A size given by an expression is not inverted",
    "n * 2 is 4 over the fields written so far, and data serialises to three bytes: the expression is evaluated as "
    "at parse, and a value that does not match it is a validation error.",
    [ORDER],
    ["size-resolution"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "n * 2" .
   """,
    {"n": 2, "data": bytes.fromhex("010203")},
    error="Validation",
)
# ----------------------------------------------------------------- rules 2 and 8: checksums

CHECKSUM = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:crc ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromField ex:data ; bddo:coversToField ex:data ] .
   """

w(
    "checksum-filled",
    "An unbound checksum field is computed over the covered bytes and back-patched",
    "The CRC-32 of 01 02 03 is 55BC801D, written as a big-endian uint32 after the data.",
    [BACK_PATCH, RECOMPUTED],
    ["algorithm"],
    CHECKSUM,
    {"data": bytes.fromhex("010203"), "crc": None},
    bytes.fromhex("010203") + crc32(bytes.fromhex("010203")),
)

w(
    "checksum-inconsistent",
    "A bound checksum over bytes the tree determines must equal its recomputation",
    "The tree binds crc to 55BC801E, one more than the CRC-32 of the data it also binds.",
    [CONSISTENT],
    ["algorithm"],
    CHECKSUM,
    {"data": bytes.fromhex("010203"), "crc": 0x55BC801E},
    error="Validation",
)

w(
    "checksum-covers-later-bytes",
    "A checksum is patched after its struct is written, in the field's byte order",
    "crc comes first and covers offsets 4 to the end of the stream, bytes written after it: its four bytes are "
    "fill until data is written, then the CRC-32 of 01 02 03 as a little-endian uint32, 1D 80 BC 55.",
    [BACK_PATCH],
    ["algorithm", "byte-order"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:crc ex:data ) .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32le ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromExpression "4" ; bddo:coversToExpression "stream.length" ] .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   """,
    {"crc": None, "data": bytes.fromhex("010203")},
    crc32(bytes.fromhex("010203"))[::-1] + bytes.fromhex("010203"),
)

INNER = bytes.fromhex("0a0b") + crc32(bytes.fromhex("0a0b"))

w(
    "checksum-innermost-first",
    "An outer checksum covers the patched bytes of an inner one",
    "The inner struct is 0A 0B and the CRC-32 of those two bytes; the outer checksum is the CRC-32 of all six "
    "bytes of the inner struct, its patched checksum included.",
    [BACK_PATCH],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:inner ex:outer ) .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:outer a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromField ex:inner ; bddo:coversToField ex:inner ] .
   ex:Inner a bddo:Struct ; bddo:hasField ( ex:d ex:c ) .
   ex:d a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 .
   ex:c a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromField ex:d ; bddo:coversToField ex:d ] .
   """,
    {"inner": {"d": bytes.fromhex("0a0b"), "c": None}, "outer": None},
    INNER + crc32(INNER),
)

# ----------------------------------------------------------------- rule 3: extents

w(
    "region-filled",
    "A region of literal size is filled to its end after a shorter value",
    "box is a region of four bytes and its struct takes two: 00 07, then two fill bytes 00, then tail. The stream "
    "reads back as the same tree, whatever the stream it was parsed from held in those two bytes.",
    [LITERAL_REGION],
    ["size-resolution"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:tail ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:size 4 .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"box": {"a": 7}, "tail": 9},
    bytes.fromhex("0007 0000 09"),
)

w(
    "region-overflow",
    "A value longer than its region of literal size is refused",
    "data is five bytes and its region is four.",
    [LITERAL_REGION],
    ["size-resolution"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:tail ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"data": bytes.fromhex("0102030405"), "tail": 9},
    error="Validation",
)

BOX = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:tail ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size {size} ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """

w(
    "struct-size-filled",
    "A struct's declared size is a region, filled to its end",
    "Box is four bytes and its fields take two: 01 02, two fill bytes, then tail.",
    [STRUCT_SIZE],
    ["struct-size"],
    BOX.format(size=4),
    {"box": {"a": 1, "b": 2}, "tail": 9},
    bytes.fromhex("0102 0000 09"),
)

w(
    "struct-size-overflow",
    "Fields that do not fit their struct's declared size are refused",
    "Box is one byte and its fields take two.",
    [STRUCT_SIZE],
    ["struct-size"],
    BOX.format(size=1),
    {"box": {"a": 1, "b": 2}, "tail": 9},
    error="Validation",
)

w(
    "separated-tokens",
    "A separated token is preceded by one space when a token precedes it",
    "Two separated scalars and a separated array: the first token is preceded by nothing, every later one by one "
    "0x20, so the tokens do not run together: '1 2 33 4'.",
    [SEPARATOR],
    ["size-resolution", "text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:vals ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" .
   ex:b a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" .
   ex:vals a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" ; bddo:repeatCount 2 .
   """,
    {"a": 1, "b": 2, "vals": [33, 4]},
    b"1 2 33 4",
)

w(
    "separated-region-start",
    "The first token of a region is preceded by nothing, so tokens of adjacent regions abut",
    "Each one-byte box holds one separated token. The second token starts its own region, so no separator precedes "
    "it although a token was written just before: '12', which the parse rules read back as 1 and 2.",
    [SEPARATOR],
    ["size-resolution", "text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:first ex:second ) .
   ex:first a bddo:Field ; bddo:dataType ex:Box .
   ex:second a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 1 ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" .
   """,
    {"first": {"v": 1}, "second": {"v": 2}},
    b"12",
)

# ----------------------------------------------------------------- rule 4: padding, alignment and offsets

w(
    "bit-field-realigned",
    "The unused bits of a partial byte are written 0",
    "f is 5 in three bits, most significant bit first: 101, then five unused bits 0, A0; b starts at the next byte.",
    [PADDING],
    ["bit-cursor"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:f ex:b ) .
   ex:f a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 3 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"f": 5, "b": 255},
    bytes.fromhex("a0 ff"),
)

w(
    "alignment",
    "bddo:alignment writes fill bytes to the next multiple of the alignment",
    "a ends at offset 1 and b is aligned to 4: three fill bytes 00, then b at offset 4.",
    [PADDING],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:alignment 4 .
   """,
    {"a": 1, "b": 2},
    bytes.fromhex("01 000000 02"),
)

w(
    "repeat-index",
    "A Writer binds repeat.index to each element's position",
    "The tree holds three Item elements; each is written with repeat.index as its argument, so v == param.i holds "
    "for 0, 1 and 2 and the output is 000102.",
    ["req-pm-serialisation-39"],
    ["repeat-index"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.items ) .
   ex:Root.items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatCount 3 ; bddo:hasArgument ( "repeat.index" ) .
   ex:Item a bddo:Struct ; bddo:hasParameter ( ex:Item.i ) ; bddo:hasField ( ex:Item.v ) .
   ex:Item.i a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Item.v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:validIf "self == param.i" .
   """,
    {"items": [{"v": 0}, {"v": 1}, {"v": 2}]},
    bytes.fromhex("00 01 02"),
)

w(
    "pad-to-pad-byte",
    "The padding of a bddo:padTo is its declared bddo:padByte, and 00 when none is declared",
    "a is padded to 4 with its pad byte 2A: 01 2A 2A 2A. The struct Rec is padded to 4 with no pad byte declared: "
    "its member 02 at offset 4, then 00 00 00 to offset 8. Then tail.",
    [PADDING],
    ["alignment-padding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:rec ex:tail ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:padTo 4 ; bddo:padByte "2A"^^xsd:hexBinary .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:padTo 4 ; bddo:hasField ( ex:b ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"a": 1, "rec": {"b": 2}, "tail": 9},
    bytes.fromhex("01 2a2a2a 02 000000 09"),
)

w(
    "pad-to-struct-origin",
    "bddo:padTo under bddo:structOrigin is written relative to the struct's own start",
    "Rec starts at offset 6 and pads to 4 from its first byte: its member 07, then three fill bytes 00 to offset 10, "
    "where after is written. The stream origin would have stopped the padding at offset 8.",
    [PADDING],
    ["alignment-padding", "alignment-origin"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pad ex:rec ex:after ) .
   ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 6 .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:padTo 4 ; bddo:alignmentOrigin bddo:structOrigin ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:after a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"pad": b"\x00" * 6, "rec": {"a": 7}, "after": 0x42},
    bytes.fromhex("000000000000 07 000000 42"),
)

w(
    "offset-addressed",
    "An offset-addressed field is written at its target and the cursor restored",
    "ptr is 4, so val is written at offset 4; next follows ptr at offset 1; the two bytes between the cursor and "
    "the target that nothing writes are fill bytes.",
    [PADDING],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:ptr ex:val ex:next ) .
   ex:ptr a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:val a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:atOffsetFromField ex:ptr .
   ex:next a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"ptr": 4, "val": 0x1234, "next": 7},
    bytes.fromhex("04 07 0000 1234"),
)

w(
    "offset-conflict",
    "A target already written with different bytes is refused",
    "x is addressed at offset 0, where a was written as 01; x is 02.",
    [PADDING],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:x ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:x a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 0 .
   """,
    {"a": 1, "x": 2},
    error="Validation",
)
# ----------------------------------------------------------------- rule 5: text and text numbers

w(
    "text-encodings",
    "A string is encoded in its bddo:encoding",
    "e-acute is E9 in Latin-1 and C3 A9 in UTF-8; 'hi' is 68 00 69 00 in UTF-16LE. The UTF-8 string is terminated "
    "by 00.",
    [TEXT],
    ["text-decoding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:l ex:u ex:t ) .
   ex:l a bddo:Field ; bddo:dataType bddo:string ; bddo:size 1 ; bddo:encoding bddo:latin1 .
   ex:u a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:utf16le .
   ex:t a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf8 ; bddo:terminator "00"^^xsd:hexBinary .
   """,
    {"l": "\u00e9", "u": "hi", "t": "\u00e9"},
    bytes.fromhex("e9 68006900 c3a9 00"),
)

ASCII4 = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii ; bddo:trimNull true .
   """

w(
    "text-unrepresentable",
    "A character the encoding cannot represent is refused",
    "e-acute has no ASCII encoding.",
    [TEXT],
    ["text-decoding"],
    ASCII4,
    {"s": "\u00e9"},
    error="Validation",
)

w(
    "text-trim-null-padded",
    "A fixed-size trimNull string is followed by NUL code units to its width",
    "'ab' in a width of four: 61 62 00 00.",
    [TEXT],
    ["text-decoding"],
    ASCII4,
    {"s": "ab"},
    bytes.fromhex("6162 0000"),
)

w(
    "text-too-long",
    "A string longer than its fixed width is refused",
    "'abcde' is five bytes in a width of four.",
    [TEXT],
    ["text-decoding"],
    ASCII4,
    {"s": "abcde"},
    error="Validation",
)

w(
    "text-number-integers",
    "An Integer written as text is rendered canonically and zero-padded to a literal width",
    "42 in five bytes is 00042; -42 is -0042, the zeros after the sign; 255 in radix 16 is 00FF, its digits "
    "upper-case; the terminated 42 is not padded.",
    [TEXT],
    ["text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 5 .
   ex:b a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 5 .
   ex:c a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 4 ; bddo:numericBase 16 .
   ex:d a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:terminator "0A"^^xsd:hexBinary .
   """,
    {"a": 42, "b": -42, "c": 255, "d": 42},
    b"00042" + b"-0042" + b"00FF" + b"42\n",
)

w(
    "text-number-floats",
    "A Float written as text takes the canonical Float spelling; nan is followed by spaces",
    "1.5 in six bytes is 0001.5 and -2.5 in five is -02.5, zero-padded after the sign; NaN is nan, which has no "
    "digits to pad and is followed by three spaces to its width of six.",
    [TEXT],
    ["text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 6 .
   ex:b a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 5 .
   ex:c a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 6 .
   """,
    {"a": 1.5, "b": -2.5, "c": float("nan")},
    b"0001.5" + b"-02.5" + b"nan   ",
)

w(
    "text-number-overflow",
    "A text number whose rendering does not fit its width is refused",
    "1234567 is seven digits in a width of five. A refusal is a conforming outcome here even for a parsed tree; "
    "a stream that reads back as another number is not.",
    [TEXT],
    ["text-numbers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ) .
   ex:n a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 5 .
   """,
    {"n": 1234567},
    error="Validation",
)

w(
    "text-number-bound-width",
    "A width a bound field gives is the width to write",
    "w is bound to 5 and names the width of n: 42 is padded to 00042, and w is written as bound, not recomputed "
    "from the rendering.",
    [TEXT],
    ["text-numbers", "size-resolution"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:n ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:n a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:sizeFromField ex:w .
   """,
    {"w": 5, "n": 42},
    b"\x05" + b"00042",
)

# ----------------------------------------------------------------- rule 6: type selection and byte order

w(
    "byte-order",
    "Integers are written in the effective byte order",
    "Big-endian by default (01 02); bddo:uint16le and a field's own bddo:endianness are little-endian (02 01, "
    "04 03); a nested struct declared little-endian writes its uint32 1 as 01 00 00 00.",
    [SELECTION],
    ["byte-order"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:inner ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16le .
   ex:c a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:endianness bddo:LittleEndian .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:Inner a bddo:Struct ; bddo:endianness bddo:LittleEndian ; bddo:hasField ( ex:d ) .
   ex:d a bddo:Field ; bddo:dataType bddo:uint32 .
   """,
    {"a": 0x0102, "b": 0x0102, "c": 0x0304, "inner": {"d": 1}},
    bytes.fromhex("0102 0201 0403 01000000"),
)

CONDITIONAL_ORDER = """
   ex:Root a bddo:Struct ;
       bddo:hasConditionalEndianness (
           [ a bddo:EndiannessRule ; bddo:condition "order == 'II'" ; bddo:ruleEndianness bddo:LittleEndian ]
           [ a bddo:EndiannessRule ; bddo:condition "order == 'MM'" ; bddo:ruleEndianness bddo:BigEndian ] ) ;
       bddo:hasField ( ex:order ex:magic ) .
   ex:order a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   ex:magic a bddo:Field ; bddo:dataType bddo:uint16 .
   """

w(
    "byte-order-conditional-little",
    "A conditional byte order is evaluated over the fields written so far",
    "order is 'II', written first, so magic 42 is little-endian: 49 49, 2A 00.",
    [SELECTION],
    ["byte-order"],
    CONDITIONAL_ORDER,
    {"order": "II", "magic": 42},
    b"II" + bytes.fromhex("2a00"),
)

w(
    "byte-order-conditional-big",
    "The same description writes the other byte order for the other value",
    "order is 'MM', so magic 42 is big-endian: 4D 4D, 00 2A.",
    [SELECTION],
    ["byte-order"],
    CONDITIONAL_ORDER,
    {"order": "MM", "magic": 42},
    b"MM" + bytes.fromhex("002a"),
)

DISPATCH = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnField ex:tag .
   ex:arm1 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey 1 ; bddo:armDataType ex:A .
   ex:arm2 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey 2 ; bddo:armDataType ex:B .
   ex:A a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:B a bddo:Struct ; bddo:hasField ( ex:b ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   """

w(
    "dispatch-selected",
    "A dispatched node is serialised as the struct its key selects",
    "tag is 2, which selects B: body is written as B's uint16 b, 00 05.",
    [SELECTION],
    ["algorithm"],
    DISPATCH,
    {"tag": 2, "body": {"b": 5}},
    bytes.fromhex("02 0005"),
)

w(
    "dispatch-wrong-members",
    "A node whose members are not the selected struct's fields is refused",
    "tag is 2, which selects B, and the node holds A's field a.",
    [SELECTION],
    ["algorithm"],
    DISPATCH,
    {"tag": 2, "body": {"a": 5}},
    error="Validation",
)

# ----------------------------------------------------------------- rule 7: codecs

w(
    "codec-length-recomputed",
    "A length and a checksum that rest on encoded bytes are recomputed whatever the tree binds",
    "data is encoded with menc:Store, the identity, so its encoded bytes are 78 79 7A. n is bound to 99 and crc to "
    "DEADBEEF, values that say nothing about the bytes being written: n is written as 3 and crc as the CRC-32 of "
    "the three encoded bytes, and neither is a validation error.",
    [CODEC, RECOMPUTED],
    ["minimum-codecs"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ex:crc ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n ; hexplain:isEncodedWith menc:Store .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromField ex:data ; bddo:coversToField ex:data ] .
   """,
    {"n": 99, "data": b"xyz", "crc": 0xDEADBEEF},
    b"\x03" + b"xyz" + crc32(b"xyz"),
)

w(
    "codec-substream-struct",
    "An encoded struct is serialised to a fresh sub-stream, then encoded",
    "Payload is written to its own stream, little-endian: 01 00 02 00. menc:Store leaves the four bytes as they "
    "are, and they are the field's value: n is filled with 4.",
    [CODEC, RECOMPUTED],
    ["minimum-codecs"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:block ex:tail ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:block a bddo:Field ; bddo:dataType ex:Payload ; bddo:sizeFromField ex:n ; hexplain:isEncodedWith menc:Store .
   ex:Payload a bddo:Struct ; bddo:endianness bddo:LittleEndian ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    {"n": None, "block": {"a": 1, "b": 2}, "tail": 9},
    bytes.fromhex("04 0100 0200 09"),
)

w(
    "codec-delta-step",
    "An encoding step is encoded by its codec's contract with the step's parameters",
    "menc:Delta with one-byte samples writes each byte as its difference from the byte before it, modulo 256: "
    "10 11 12 6 16 becomes 10 1 1 250 10. The five encoded bytes are the field's value, so n is 5.",
    [CODEC],
    ["minimum-codecs", "codec-contracts"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n ;
       hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Delta ;
           hexplain:codecParameter [ a hexplain:CodecParameter ; hexplain:parameterName "elementSize" ; \
hexplain:parameterValue 1 ] ] ) .
   """,
    {"n": None, "data": bytes([10, 11, 12, 6, 16])},
    bytes([5, 10, 1, 1, 250, 10]),
)

w(
    "codec-no-encode-direction",
    "A codec whose contract defines no encode direction is refused with Unsupported feature",
    "The contract of menc:JPEG has no hexplain:encodes: whether or not the processor decodes it, the field cannot "
    "be written.",
    [CODEC],
    ["codec-contracts", "optional-codecs"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:isEncodedWith menc:JPEG .
   """,
    {"data": bytes.fromhex("0102")},
    error="Unsupported",
)

# ----------------------------------------------------------------- rule 10: scope

w(
    "container-key-value",
    "A key/value header is outside what this version writes",
    "The root is a bddo:KeyValueHeader, a text container: Unsupported feature.",
    [SCOPE],
    ["text-containers", "key-value"],
    """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:hasField ( ex:Root.samples ) .
   ex:Root.samples a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "samples" .
   """,
    {"samples": 3},
    error="Unsupported",
)

w(
    "container-nested-delimited-table",
    "A text container reached through a field of a byte-level struct is refused",
    "Root is a byte-level struct, and its field rows is a bddo:DelimitedTable: the description reaches a text "
    "container, and the refusal is Unsupported feature, not a partial stream.",
    [SCOPE],
    ["text-containers", "delimited-tables"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:rows ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:rows a bddo:Field ; bddo:dataType ex:Table ; bddo:sizeFromField ex:n .
   ex:Table a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:hasField ( ex:Table.name \
ex:Table.qty ) .
   ex:Table.name a bddo:Field ; bddo:dataType bddo:string .
   ex:Table.qty a bddo:Field ; bddo:dataType bddo:asciiInteger .
   """,
    {"n": None, "rows": [{"name": "a", "qty": 1}]},
    error="Unsupported",
)

w(
    "container-tree-document",
    "A tree document is outside what this version writes",
    "The root is a bddo:TreeDocument: Unsupported feature, whether or not the processor claims tree documents.",
    [SCOPE],
    ["text-containers", "tree-documents"],
    """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ex:Root.dtype ) .
   ex:Root.dtype a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/dtype" .
   """,
    {"dtype": "u1"},
    error="Unsupported",
)

w(
    "chunk-table",
    "A layout with a chunk table is outside what this version writes",
    "The layout of pixels names a chunk table (dlv:chunkOffsetsFromField): Unsupported feature.",
    [SCOPE],
    ["data-layouts"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:offsets ex:pixels ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:offsets a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:chunkOffsetsFromField ex:offsets ;
       dlv:chunkOffsetBase bddo:streamStart ; dlv:chunkOrder dlv:rowMajor ; dlv:hasDimension ( ex:DimX ) .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:w ; dlv:chunkSize 2 .
   """,
    {"w": 4, "offsets": [3, 5], "pixels": bytes.fromhex("01020304")},
    error="Unsupported",
)
