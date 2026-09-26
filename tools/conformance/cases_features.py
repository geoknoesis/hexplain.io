"""Physical Parser and Semantic Emitter cases for the language features of the Unreleased section:
24-bit integers and half floats, the named CRC variants and bddo:CustomCrc, the LZ4 and Zstandard
codecs, parameterised structs and local bindings.

Every expected value is read off the specification text the case cites: the float16 values are
the binary16 values of their bit patterns, the CRCs are computed by the Rocksoft model in crc.py
(whose catalogue check values tools/test_crc_catalogue.py pins), LZ4 inputs are written by
lz4frames.py and Zstandard ones are pinned in zstdframes.py.
"""
import struct

import crc
import lz4frames
import zstdframes
from cases_physical import pp
from cases_semantic import ROOT as SE_ROOT
from cases_semantic import se

CODECS = {"features": {"requires": ["codecs-beyond-minimum"]}}
WIDTHS = ["req-bddo-core-datatypes-1", "req-pm-size-resolution-7"]

# ----------------------------------------------------------------- 24-bit integers and half floats

pp("uint24-both-byte-orders", "bddo:uint24 in both byte orders",
   "Three bytes each: the big-endian, little-endian and inherited forms, the largest value included.",
   WIDTHS + ["req-bddo-core-datatypes-3", "req-pm-byte-order-2"], ["byte-order", "bddo/index.html#odd-widths"],
   """
   ex:Root a bddo:Struct ; bddo:endianness bddo:LittleEndian ; bddo:hasField ( ex:be ex:le ex:inherited ex:max ex:after ) .
   ex:be a bddo:Field ; bddo:dataType bddo:uint24be .
   ex:le a bddo:Field ; bddo:dataType bddo:uint24le .
   ex:inherited a bddo:Field ; bddo:dataType bddo:uint24 .
   ex:max a bddo:Field ; bddo:dataType bddo:uint24be .
   ex:after a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   bytes.fromhex("010203") + bytes.fromhex("010203") + bytes.fromhex("0a0000") + bytes.fromhex("ffffff") + b"\x2a",
   {"be": 0x010203, "le": 0x030201, "inherited": 10, "max": 16777215, "after": 42})

pp("int24-negative", "bddo:int24 is a three-byte two's complement integer",
   "FF FF FE big-endian is -2, never 16777214; the extremes are -8388608 and 8388607.",
   WIDTHS + ["req-bddo-core-datatypes-3"], ["byte-order", "bddo/index.html#odd-widths"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:int24 .
   ex:b a bddo:Field ; bddo:dataType bddo:int24le .
   ex:c a bddo:Field ; bddo:dataType bddo:int24be .
   ex:d a bddo:Field ; bddo:dataType bddo:int24le .
   """,
   bytes.fromhex("fffffe") + bytes.fromhex("000080") + bytes.fromhex("7fffff") + bytes.fromhex("ffffff"),
   {"a": -2, "b": -8388608, "c": 8388607, "d": -1})

pp("int24-repeated", "Repeated 24-bit samples are packed three bytes apart",
   "Four signed 24-bit little-endian PCM samples occupy twelve bytes, and the field after them starts at offset 12.",
   WIDTHS + ["req-bddo-core-datatypes-3", "req-pm-parsefield-8"], ["bddo/index.html#odd-widths", "size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:samples ex:end ) .
   ex:samples a bddo:Field ; bddo:dataType bddo:int24le ; bddo:repeatCount 4 .
   ex:end a bddo:Field ; bddo:valueFromExpression "stream.position" .
   """,
   b"".join((v & 0xFFFFFF).to_bytes(3, "little") for v in (0, 1, -1, 4660)),
   {"samples": [0, 1, -1, 4660], "end": 12})


def half(bits):
    return struct.unpack(">e", bits.to_bytes(2, "big"))[0]


pp("float16-normal-values", "bddo:float16 decodes binary16 values exactly, in both byte orders",
   "3C00 is 1.0, C000 is -2.0, 7BFF is the largest finite value 65504, and 3555 is 0.333251953125 exactly.",
   WIDTHS + ["req-bddo-core-datatypes-4", "req-pm-byte-order-2"], ["bddo/index.html#odd-widths", "byte-order"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:one ex:minusTwo ex:max ex:third ex:thirdLe ) .
   ex:one a bddo:Field ; bddo:dataType bddo:float16 .
   ex:minusTwo a bddo:Field ; bddo:dataType bddo:float16be .
   ex:max a bddo:Field ; bddo:dataType bddo:float16 .
   ex:third a bddo:Field ; bddo:dataType bddo:float16be .
   ex:thirdLe a bddo:Field ; bddo:dataType bddo:float16le .
   """,
   bytes.fromhex("3c00" "c000" "7bff" "3555" "5535"),
   {"one": 1.0, "minusTwo": -2.0, "max": 65504.0, "third": 0.333251953125, "thirdLe": 0.333251953125})
assert half(0x3555) == 0.333251953125

pp("float16-subnormals-and-zeros", "bddo:float16 subnormals and signed zeros",
   "0001 is 2^-24, 03FF the largest subnormal (1023 x 2^-24), 0400 the smallest normal 2^-14, 8000 negative zero; "
   "little-endian 0100 is 2^-24 too.",
   WIDTHS + ["req-bddo-core-datatypes-4"], ["bddo/index.html#odd-widths"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tiny ex:largestSub ex:smallestNormal ex:negZero ex:tinyLe ) .
   ex:tiny a bddo:Field ; bddo:dataType bddo:float16be .
   ex:largestSub a bddo:Field ; bddo:dataType bddo:float16be .
   ex:smallestNormal a bddo:Field ; bddo:dataType bddo:float16be .
   ex:negZero a bddo:Field ; bddo:dataType bddo:float16be .
   ex:tinyLe a bddo:Field ; bddo:dataType bddo:float16le .
   """,
   bytes.fromhex("0001" "03ff" "0400" "8000" "0100"),
   {"tiny": 2.0 ** -24, "largestSub": 1023 * 2.0 ** -24, "smallestNormal": 2.0 ** -14, "negZero": -0.0,
    "tinyLe": 2.0 ** -24})
assert half(0x0001) == 2.0 ** -24 and half(0x03FF) == 1023 * 2.0 ** -24

pp("float16-infinities-and-nan", "bddo:float16 infinities and NaN",
   "7C00 is +Infinity, FC00 is -Infinity, and 7E00 and 7C01 (quiet and signalling patterns) are NaN.",
   WIDTHS + ["req-bddo-core-datatypes-4"], ["bddo/index.html#odd-widths"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:posInf ex:negInf ex:quiet ex:signalling ) .
   ex:posInf a bddo:Field ; bddo:dataType bddo:float16be .
   ex:negInf a bddo:Field ; bddo:dataType bddo:float16be .
   ex:quiet a bddo:Field ; bddo:dataType bddo:float16be .
   ex:signalling a bddo:Field ; bddo:dataType bddo:float16le .
   """,
   bytes.fromhex("7c00" "fc00" "7e00" "017c"),
   {"posInf": float("inf"), "negInf": float("-inf"), "quiet": float("nan"), "signalling": float("nan")})

pp("float16-fixed-value", "A fixed value on a float16 field is compared at binary16 width",
   "0.1 rounds to the binary16 2E66 (0.0999755859375); 65504 is 7BFF exactly.",
   ["req-pm-parsefield-26", "req-pm-parsefield-13"], ["fixed-values", "bddo/index.html#odd-widths"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tenth ex:max ) .
   ex:tenth a bddo:Field ; bddo:dataType bddo:float16be ; bddo:hasFixedValue "0.1"^^xsd:double .
   ex:max a bddo:Field ; bddo:dataType bddo:float16le ; bddo:hasFixedValue "65504"^^xsd:float .
   """,
   bytes.fromhex("2e66" "ff7b"), {"tenth": 0.0999755859375, "max": 65504.0})
assert half(0x2E66) == 0.0999755859375

pp("float16-fixed-value-mismatch", "A float16 one unit in the last place away from the fixed value is a validation error",
   "2E67 is the binary16 after 2E66, the nearest binary16 to 0.1, so it does not match.",
   ["req-pm-parsefield-26", "req-pm-errors-4"], ["fixed-values"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tenth ) .
   ex:tenth a bddo:Field ; bddo:dataType bddo:float16be ; bddo:hasFixedValue "0.1"^^xsd:double .
   """,
   bytes.fromhex("2e67"), error="Validation")

pp("float16-fixed-value-overflow", "A fixed value that overflows binary16 is a description error",
   "70000 rounds beyond 65504, the largest finite binary16.",
   ["req-pm-parsefield-26", "req-pm-parsefield-14", "req-pm-errors-8"], ["fixed-values"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:float16be ; bddo:hasFixedValue "70000"^^xsd:double .
   """,
   bytes.fromhex("7bff"), error="Description")

pp("uint24-fixed-hex-width", "A hex fixed value on a 24-bit field must be three bytes",
   "Two bytes of hexBinary on a bddo:uint24 field is a description error.",
   ["req-pm-parsefield-2", "req-pm-parsefield-14"], ["fixed-values"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint24be ; bddo:hasFixedValue "0102"^^xsd:hexBinary .
   """,
   bytes.fromhex("000102"), error="Description")

pp("uint24-fixed-value", "A three-byte hex fixed value is the field's encoding in its byte order",
   "010203 on a little-endian uint24 is the value 0x030201; an integer fixed value compares by value.",
   ["req-pm-parsefield-2", "req-pm-parsefield-13"], ["fixed-values"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint24le ; bddo:hasFixedValue "010203"^^xsd:hexBinary .
   ex:b a bddo:Field ; bddo:dataType bddo:int24be ; bddo:hasFixedValue "-2"^^xsd:int .
   """,
   bytes.fromhex("010203" "fffffe"), {"a": 0x030201, "b": -2})

# ----------------------------------------------------------------- CRCs

CHECK = "req-pm-parsefield-16"
FIELD_TYPE = {8: "uint8", 16: "uint16", 32: "uint32", 64: "uint64"}
PACK = {8: ">B", 16: ">H", 32: ">I", 64: ">Q"}
for name, (hdl, label, width, *_rest, check) in crc.NAMED.items():
    if name in ("crc16", "crc32"):
        continue   # checksum-crc16-ccitt-false and checksum-crc32 already hold them
    pp(f"crc-{hdl}", f"bddo:{name} is {label}",
       f"The checksum of the ASCII bytes '123456789' is the catalogue check value {check:#x}, stored big-endian in a "
       f"{width}-bit field.",
       [CHECK, "req-bddo-checksum-algorithms-1"], ["algorithm", "bddo/index.html#checksum-algorithms"],
       f"""
       ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
       ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
       ex:sum a bddo:Field ; bddo:dataType bddo:{FIELD_TYPE[width]} ;
           bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:{name} ;
                           bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
       """,
       b"123456789" + struct.pack(PACK[width], check), {"text": "123456789", "sum": check})

pp("crc-stored-little-endian", "A CRC is compared with the field's value in the field's own byte order",
   "CRC-32C of '123456789' (0xE3069283) stored little-endian as 83 92 06 E3 in a bddo:uint32le field.",
   [CHECK], ["algorithm", "bddo/index.html#checksum-algorithms"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint32le ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32c ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + struct.pack("<I", 0xE3069283), {"text": "123456789", "sum": 0xE3069283})


def custom(width, poly, init, refin, refout, xorout):
    return (f"[ a bddo:CustomCrc ; bddo:crcWidth {width} ; bddo:crcPolynomial {poly} ; bddo:crcInit {init} ; "
            f"bddo:crcReflectIn {str(refin).lower()} ; bddo:crcReflectOut {str(refout).lower()} ; bddo:crcXorOut {xorout} ]")


ARC = custom(16, 0x8005, 0, True, True, 0)
assert crc.crc(b"123456789", 16, 0x8005, 0, True, True, 0) == 0xBB3D
pp("crc-custom", "A bddo:CustomCrc is computed from its six parameters",
   "The parameters of CRC-16/ARC (0x8005, reflected, init 0) give 0xBB3D over '123456789', stored little-endian.",
   [CHECK, "req-bddo-checksum-algorithms-1"], ["algorithm", "bddo/index.html#checksum-algorithms"],
   f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint16le ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm {ARC} ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + struct.pack("<H", 0xBB3D), {"text": "123456789", "sum": 0xBB3D})

OPENPGP = crc.crc(b"123456789", 24, 0x864CFB, 0xB704CE, False, False, 0)
assert OPENPGP == 0x21CF02   # the catalogue's CRC-24/OPENPGP check value
pp("crc-custom-24-bit", "A 24-bit custom CRC stored in a bddo:uint24 field",
   "CRC-24/OPENPGP (polynomial 0x864CFB, init 0xB704CE) gives 0x21CF02 over '123456789'; no named algorithm is 24 bits wide.",
   [CHECK, "req-bddo-checksum-algorithms-1", "req-bddo-core-datatypes-3"],
   ["algorithm", "bddo/index.html#checksum-algorithms"],
   f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint24be ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm {custom(24, 0x864CFB, 0xB704CE, False, False, 0)} ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + OPENPGP.to_bytes(3, "big"), {"text": "123456789", "sum": OPENPGP})

pp("crc-named-mismatch", "A named CRC that does not match is a checksum error",
   "0xCBF43926 is CRC-32/ISO-HDLC of '123456789', not the CRC-32C the field declares (0xE3069283).",
   [CHECK, "req-pm-errors-5"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32c ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + struct.pack(">I", 0xCBF43926), error="Checksum")

pp("crc-custom-mismatch", "A custom CRC that does not match is a checksum error",
   "0x4B37 is CRC-16/MODBUS of '123456789' (init 0xFFFF); the custom parameters say init 0, which gives 0xBB3D.",
   [CHECK, "req-pm-errors-5"], ["algorithm", "errors"],
   f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint16 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm {ARC} ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + struct.pack(">H", 0x4B37), error="Checksum")

pp("crc-field-too-narrow", "A CRC stored in a field narrower than the CRC is a description error",
   "A 32-bit CRC-32C declared on a bddo:uint16 field.",
   [CHECK, "req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint16 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32c ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + struct.pack(">H", 0x9283), error="Description")

pp("crc-field-too-wide", "A CRC stored in a field wider than the CRC is a description error",
   "A 16-bit CRC-16/ARC declared on a bddo:uint32 field: the checksum field is exactly as wide as the CRC.",
   [CHECK, "req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc16Arc ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789" + struct.pack(">I", 0xBB3D), error="Description")

pp("crc-custom-invalid-width", "A custom CRC width outside 8..64 is a description error",
   "bddo:CustomCrcShape rejects a width of 7; an invalid description is a Description error when it is loaded.",
   ["req-bddo-checksum-algorithms-1", "req-pm-errors-8"], ["algorithm", "errors", "bddo/index.html#checksum-algorithms"],
   f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint8 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm {custom(7, 3, 0, False, False, 0)} ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
   b"123456789\x00", error="Description")

# ----------------------------------------------------------------- LZ4 and Zstandard

OPTIONAL = "req-pm-optional-codecs-3"
TEXT = b"Hexplain LZ4 frame: " + b"abcabcabcabcabcabc" * 10 + bytes(range(40))
FRAME = lz4frames.frame(TEXT)
FRAME_CHECKED = lz4frames.frame(TEXT, block_checksum=True, content_size=True)
BLOCK = lz4frames.compress_block(TEXT)
assert len(BLOCK) < len(TEXT) and lz4frames.decompress_block(BLOCK, len(TEXT)) == TEXT


def encoded(codec_turtle, size):
    return f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size {size} ; {codec_turtle} .
   """


def lz4_block(size_param, length):
    parameter = ("" if size_param is None else
                 f' ; hexplain:codecParameter [ a hexplain:CodecParameter ; hexplain:parameterName "decodedSize" ; '
                 f'hexplain:parameterValue {size_param} ]')
    return encoded(f"hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:LZ4Block{parameter} ] )",
                   length)


pp("codec-lz4-frame", "menc:LZ4 decodes the LZ4 frame format",
   "A frame with one compressed block and a content checksum, written by tools/conformance/lz4frames.py.",
   [OPTIONAL, "req-pm-optional-codecs-4", "req-pm-minimum-codecs-1"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:LZ4", len(FRAME)), FRAME, {"data": TEXT}, manifest=CODECS)

pp("codec-lz4-frame-block-checksums", "LZ4 block checksums and content size are verified and decode",
   "The frame declares its content size and a checksum after every block, all correct.",
   [OPTIONAL, "req-pm-optional-codecs-4"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:LZ4", len(FRAME_CHECKED)), FRAME_CHECKED, {"data": TEXT}, manifest=CODECS)

pp("codec-lz4-frame-concatenated", "Concatenated LZ4 frames decode in order",
   "Two frames, 'first ' and 'second', decode to 'first second'.",
   [OPTIONAL, "req-pm-optional-codecs-4"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:LZ4", len(lz4frames.frame(b"first ")) + len(lz4frames.frame(b"second"))),
   lz4frames.frame(b"first ") + lz4frames.frame(b"second"), {"data": b"first second"}, manifest=CODECS)

pp("codec-lz4-frame-substream", "An LZ4 frame decoded and re-parsed as a struct",
   "The decoded bytes 00 03 'abc' are re-parsed as a fresh sub-stream against the field's struct type.",
   [OPTIONAL, "req-pm-emission-1"], ["optional-codecs", "emission"],
   f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:block ) .
   ex:block a bddo:Field ; bddo:dataType ex:Payload ; bddo:size {len(lz4frames.frame(bytes.fromhex('0003') + b'abc'))} ;
       hexplain:isEncodedWith menc:LZ4 .
   ex:Payload a bddo:Struct ; bddo:hasField ( ex:n ex:s ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:sizeFromField ex:n ; bddo:encoding bddo:ascii .
   """,
   lz4frames.frame(bytes.fromhex("0003") + b"abc"), {"block": {"n": 3, "s": "abc"}}, manifest=CODECS)

pp("codec-lz4-content-checksum-mismatch", "An LZ4 content checksum mismatch is a checksum error",
   "The last byte of the content checksum is changed.",
   [OPTIONAL, "req-pm-optional-codecs-4", "req-pm-optional-codecs-1", "req-pm-errors-5"], ["optional-codecs", "errors"],
   encoded("hexplain:isEncodedWith menc:LZ4", len(FRAME)), FRAME[:-1] + bytes([FRAME[-1] ^ 0xFF]),
   error="Checksum", manifest=CODECS)

pp("codec-lz4-header-checksum-mismatch", "An LZ4 frame header checksum mismatch is a checksum error",
   "The header checksum byte after the frame descriptor is changed.",
   [OPTIONAL, "req-pm-optional-codecs-4", "req-pm-optional-codecs-1"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:LZ4", len(FRAME)), FRAME[:6] + bytes([FRAME[6] ^ 0xFF]) + FRAME[7:],
   error="Checksum", manifest=CODECS)

pp("codec-lz4-frame-truncated", "A truncated LZ4 frame is a validation error",
   "The frame is cut ten bytes short, inside its last block.",
   [OPTIONAL, "req-pm-optional-codecs-1", "req-pm-minimum-codecs-10"], ["optional-codecs", "minimum-codecs"],
   encoded("hexplain:isEncodedWith menc:LZ4", len(FRAME) - 10), FRAME[:-10], error="Validation", manifest=CODECS)

pp("codec-lz4-block", "menc:LZ4Block decodes one raw block to its decodedSize",
   f"A {len(BLOCK)}-byte block with match copies decodes to the {len(TEXT)} bytes decodedSize names.",
   [OPTIONAL, "req-pm-optional-codecs-5", "req-pm-optional-codecs-7"], ["optional-codecs", "lz4-parameters"],
   lz4_block(len(TEXT), len(BLOCK)), BLOCK, {"data": TEXT}, manifest=CODECS)

pp("codec-lz4-block-missing-size", "menc:LZ4Block without decodedSize is a description error",
   "decodedSize is REQUIRED: the block format records no length.",
   [OPTIONAL, "req-pm-optional-codecs-7", "req-pm-optional-codecs-1", "req-pm-errors-8"], ["optional-codecs", "lz4-parameters"],
   lz4_block(None, len(BLOCK)), BLOCK, error="Description", manifest=CODECS)

pp("codec-lz4-block-shorthand", "hexplain:isEncodedWith menc:LZ4Block is a description error",
   "The shorthand cannot carry the required decodedSize parameter.",
   [OPTIONAL, "req-pm-optional-codecs-7", "req-pm-errors-8"], ["optional-codecs", "lz4-parameters"],
   encoded("hexplain:isEncodedWith menc:LZ4Block", len(BLOCK)), BLOCK, error="Description", manifest=CODECS)

pp("codec-lz4-block-size-mismatch", "An LZ4 block that decodes to another length than decodedSize is a validation error",
   "decodedSize is one byte short of what the block decodes to.",
   [OPTIONAL, "req-pm-optional-codecs-5", "req-pm-optional-codecs-1"], ["optional-codecs"],
   lz4_block(len(TEXT) - 1, len(BLOCK)), BLOCK, error="Validation", manifest=CODECS)

BAD_OFFSET = bytes([0x20]) + b"ab" + struct.pack("<H", 5) + bytes([0x10]) + b"c"
pp("codec-lz4-block-bad-offset", "An LZ4 match reaching before the start of the output is a validation error",
   "After two literals a match with offset 5 would copy from before the first byte.",
   [OPTIONAL, "req-pm-optional-codecs-1"], ["optional-codecs"],
   lz4_block(7, len(BAD_OFFSET)), BAD_OFFSET, error="Validation", manifest=CODECS)

Z1, Z2 = zstdframes.frame(zstdframes.CONTENT_1), zstdframes.frame(zstdframes.CONTENT_2)
pp("codec-zstd-frame", "menc:Zstd decodes a Zstandard frame",
   "A frame with a compressed block, a declared content size and a content checksum.",
   [OPTIONAL, "req-pm-optional-codecs-6"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:Zstd", len(Z1)), Z1, {"data": zstdframes.CONTENT_1}, manifest=CODECS)

pp("codec-zstd-concatenated", "Concatenated Zstandard frames decode in order",
   "Two frames decode to the concatenation of their contents.",
   [OPTIONAL, "req-pm-optional-codecs-6"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:Zstd", len(Z1) + len(Z2)), Z1 + Z2,
   {"data": zstdframes.CONTENT_1 + zstdframes.CONTENT_2}, manifest=CODECS)

pp("codec-zstd-checksum-mismatch", "A Zstandard content checksum mismatch is a checksum error",
   "The last byte of the content checksum is changed.",
   [OPTIONAL, "req-pm-optional-codecs-6", "req-pm-optional-codecs-1", "req-pm-errors-5"], ["optional-codecs", "errors"],
   encoded("hexplain:isEncodedWith menc:Zstd", len(Z1)), Z1[:-1] + bytes([Z1[-1] ^ 0xFF]),
   error="Checksum", manifest=CODECS)

pp("codec-zstd-truncated", "A truncated Zstandard frame is a validation error",
   "The frame is cut six bytes short, inside its compressed block.",
   [OPTIONAL, "req-pm-optional-codecs-1", "req-pm-minimum-codecs-10"], ["optional-codecs", "minimum-codecs"],
   encoded("hexplain:isEncodedWith menc:Zstd", len(Z1) - 6), Z1[:-6], error="Validation", manifest=CODECS)

DICT = zstdframes.dictionary_frame(b"abc", 7)
pp("codec-zstd-dictionary", "A Zstandard frame that names a dictionary is Unsupported",
   "The frame header carries Dictionary_ID 7; this version defines no way to supply a dictionary.",
   [OPTIONAL, "req-pm-optional-codecs-6", "req-pm-optional-codecs-1", "req-pm-errors-10"], ["optional-codecs"],
   encoded("hexplain:isEncodedWith menc:Zstd", len(DICT)), DICT, error="Unsupported", manifest=CODECS)

pp("codec-zstd-parameter-unknown", "A parameter on menc:Zstd is a description error",
   "menc:LZ4 and menc:Zstd take no parameters.",
   [OPTIONAL, "req-pm-errors-8"], ["lz4-parameters"],
   encoded("hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Zstd ; hexplain:codecParameter "
           "[ a hexplain:CodecParameter ; hexplain:parameterName \"level\" ; hexplain:parameterValue 3 ] ] )", len(Z1)),
   Z1, error="Description", manifest=CODECS)

# ----------------------------------------------------------------- parameterised structs

PARAM = ["req-pm-parsestruct-9", "req-pm-parsefield-11"]
ROW = """
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ex:Row.w ) ; bddo:hasField ( ex:Row.cells ) .
   ex:Row.n a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Row.w a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Row.cells a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.w" ;
       bddo:repeatCountFromExpression "param.n" .
"""

pp("param-basic", "A parameterised struct reads its parameters with param",
   "The caller passes its count and width; the row repeats count cells of width bytes. Parameters are not in the tree.",
   PARAM + ["req-hel-reserved-roots-2", "req-bddo-parameterised-structs-1"],
   ["algorithm", "bddo/index.html#parameterised-structs", "hel/index.html#reserved-roots"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.count ex:Root.width ex:Root.rows ex:Root.tail ) .
   ex:Root.count a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.width a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.rows a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.count" "instance.width" ) .
   ex:Root.tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """ + ROW,
   b"\x02\x03" + b"abc" + b"def" + b"\x2a",
   {"count": 2, "width": 3, "rows": {"cells": [b"abc", b"def"]}, "tail": 42})

pp("param-nested-arguments", "Arguments are expressions in the caller's context and pass parameters on",
   "Root passes w and w * 2 to Row; Row passes param.w + 1 to Cell, whose data is that many bytes.",
   PARAM + ["req-hel-name-binding-1"], ["algorithm", "parameter-scope", "hel/index.html#name-binding"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.w ex:Root.a ex:Root.b ) .
   ex:Root.w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.a a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.w" ) .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.w * 2" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.w ) ; bddo:hasField ( ex:Row.cell ) .
   ex:Row.w a bddo:Parameter .
   ex:Row.cell a bddo:Field ; bddo:dataType ex:Cell ; bddo:hasArgument ( "param.w + 1" ) .
   ex:Cell a bddo:Struct ; bddo:hasParameter ( ex:Cell.size ) ; bddo:hasField ( ex:Cell.data ) .
   ex:Cell.size a bddo:Parameter .
   ex:Cell.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.size" .
   """,
   b"\x02" + b"abc" + b"defgh",
   {"w": 2, "a": {"cell": {"data": b"abc"}}, "b": {"cell": {"data": b"defgh"}}})

pp("param-repeated-field", "A repeated field of a parameterised struct evaluates its arguments for each element",
   "Each element receives the current stream.position, so the three elements see 1, 3 and 5.",
   PARAM, ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.items ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatCountFromField ex:Root.n ;
       bddo:hasArgument ( "stream.position" ) .
   ex:Item a bddo:Struct ; bddo:hasParameter ( ex:Item.at ) ; bddo:hasField ( ex:Item.v ex:Item.start ) .
   ex:Item.at a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Item.v a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:Item.start a bddo:Field ; bddo:valueFromExpression "param.at" .
   """,
   b"\x03" + struct.pack(">HHH", 7, 8, 9),
   {"n": 3, "items": [{"v": 7, "start": 1}, {"v": 8, "start": 3}, {"v": 9, "start": 5}]})

pp("param-rule-and-arm-arguments", "Conditional type rules and dispatch arms supply arguments of their own",
   "kind 2 selects the rule that passes 4 and the dispatch arm that passes 1.",
   PARAM + ["req-pm-parsefield-9", "req-pm-parsefield-10"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.kind ex:Root.body ex:Root.tail ) .
   ex:Root.kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.body a bddo:Field ; bddo:hasConditionalDataType (
       [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 1" ; bddo:ruleDataType ex:Blob ; bddo:hasArgument ( "2" ) ]
       [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 2" ; bddo:ruleDataType ex:Blob ; bddo:hasArgument ( "4" ) ] ) .
   ex:Root.tail a bddo:Field ; bddo:hasDispatchTable ex:Tails .
   ex:Tails a bddo:DispatchTable ; bddo:dispatchOnField ex:Root.kind .
   ex:tailTwo a bddo:DispatchArm ; bddo:armTable ex:Tails ; bddo:armKey 2 ; bddo:armDataType ex:Blob ;
       bddo:hasArgument ( "1" ) .
   ex:Blob a bddo:Struct ; bddo:hasParameter ( ex:Blob.size ) ; bddo:hasField ( ex:Blob.data ) .
   ex:Blob.size a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Blob.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.size" .
   """,
   b"\x02wxyz!", {"kind": 2, "body": {"data": b"wxyz"}, "tail": {"data": b"!"}})

NODE = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.levels ex:Root.tree ) .
   ex:Root.levels a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.tree a bddo:Field ; bddo:dataType ex:Node ; bddo:hasArgument ( "instance.levels" ) .
   ex:Node a bddo:Struct ; bddo:hasParameter ( ex:Node.depth ) ; bddo:hasField ( ex:Node.v ex:Node.child ) .
   ex:Node.depth a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Node.v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Node.child a bddo:Field ; bddo:dataType ex:Node ; bddo:hasArgument ( "param.depth - 1" ) ;
       bddo:isPresentIf "param.depth > 1" .
"""
pp("param-recursion", "A struct may pass arguments to itself",
   "Three levels: each node passes depth - 1 to its child, and the child of depth 1 is absent.",
   PARAM + ["req-bddo-parameterised-structs-1"], ["algorithm", "bddo/index.html#parameterised-structs"],
   NODE, b"\x03\x0a\x0b\x0c",
   {"levels": 3, "tree": {"v": 10, "child": {"v": 11, "child": {"v": 12, "child": None}}}})

pp("param-recursion-depth-limit", "A recursion the data does not end is bounded by the nesting depth limit",
   "Ten levels under maxDepth 4: the root is at depth 1 and the fourth node at depth 5 exceeds the limit.",
   ["req-pm-resource-limits-1", "req-pm-errors-12", "req-pm-parsestruct-9"], ["resource-limits"],
   NODE, b"\x0a" + bytes(range(10)), error="ResourceLimit", manifest={"limits": {"maxDepth": 4}})

pp("param-arity-mismatch", "Too few arguments for a parameterised struct is a description error",
   "Row declares two parameters and the field supplies one.",
   ["req-bddo-parameterised-structs-1", "req-pm-errors-8"], ["errors", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.rows ) .
   ex:Root.rows a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "1" ) .
   """ + ROW, b"abc", error="Description")

pp("param-arguments-without-parameters", "Arguments for a struct without parameters are a description error",
   "Plain declares no parameter, and the field passes one argument.",
   ["req-bddo-parameterised-structs-1", "req-pm-errors-8"], ["errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.p ) .
   ex:Root.p a bddo:Field ; bddo:dataType ex:Plain ; bddo:hasArgument ( "1" ) .
   ex:Plain a bddo:Struct ; bddo:hasField ( ex:Plain.v ) .
   ex:Plain.v a bddo:Field ; bddo:dataType bddo:uint8 .
   """, b"\x01", error="Description")

pp("param-field-name-clash", "A parameter sharing its name with a field of its struct is a description error",
   "Row's parameter n and its field n have the same simple key.",
   ["req-bddo-parameterised-structs-2", "req-pm-errors-8"], ["errors", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.r ) .
   ex:Root.r a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "1" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ) ; bddo:hasField ( ex:n ) .
   ex:Row.n a bddo:Parameter .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   """, b"\x01", error="Description")

pp("param-type-mismatch", "An argument that is not of its parameter's type is a description error",
   "The parameter is a bddo:IntegerParameter and the argument is the String 'abc'.",
   ["req-pm-errors-8", "req-pm-parsefield-11", "req-pm-context-3"], ["errors", "algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.b ) .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Blob ; bddo:hasArgument ( "'abc'" ) .
   ex:Blob a bddo:Struct ; bddo:hasParameter ( ex:Blob.size ) ; bddo:hasField ( ex:Blob.data ) .
   ex:Blob.size a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Blob.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 .
   """, b"\x01", error="Description")

pp("param-type-mismatch-evaluated", "An evaluated argument that is not of its parameter's type is an expression error",
   "The argument reads the string field tag, whose value is known only when it is evaluated: a Type / HEL error, not a "
   "description error.",
   ["req-pm-errors-6", "req-pm-parsefield-11", "req-pm-context-4"], ["errors", "algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.tag ex:Root.b ) .
   ex:Root.tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 1 ; bddo:encoding bddo:ascii .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Blob ; bddo:hasArgument ( "instance.tag" ) .
   ex:Blob a bddo:Struct ; bddo:hasParameter ( ex:Blob.size ) ; bddo:hasField ( ex:Blob.data ) .
   ex:Blob.size a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Blob.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 .
   """, b"a\x01", error="Expression")

pp("param-float-accepts-integer", "An Integer argument for a bddo:FloatParameter is converted to Float",
   "The derived field reads the parameter back: 3 becomes 3.0.",
   ["req-pm-parsefield-11"], ["algorithm", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.s ) .
   ex:Root.s a bddo:Field ; bddo:dataType ex:Scaled ; bddo:hasArgument ( "3" ) .
   ex:Scaled a bddo:Struct ; bddo:hasParameter ( ex:Scaled.k ) ; bddo:hasField ( ex:Scaled.v ex:Scaled.k2 ) .
   ex:Scaled.k a bddo:Parameter ; bddo:parameterType bddo:FloatParameter .
   ex:Scaled.v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Scaled.k2 a bddo:Field ; bddo:valueFromExpression "param.k" .
   """, b"\x07", {"s": {"v": 7, "k2": 3.0}})

pp("param-undeclared", "param.x in a struct with no parameter x is a description error",
   "Blob declares the parameter size and reads param.length.",
   ["req-hel-reserved-roots-2", "req-pm-errors-8"], ["errors", "hel/index.html#reserved-roots"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.b ) .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Blob ; bddo:hasArgument ( "1" ) .
   ex:Blob a bddo:Struct ; bddo:hasParameter ( ex:Blob.size ) ; bddo:hasField ( ex:Blob.data ) .
   ex:Blob.size a bddo:Parameter .
   ex:Blob.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.length" .
   """, b"\x01", error="Description")

QUANTIFIER = {"features": {"requires": ["hel-ext-quantifier"]}}
pp("param-quantifier-element", "Inside a quantifier over struct elements, param and bare names are the element's",
   "The predicates read the element's parameter stop and its binding low; the root declares neither, and the description "
   "loads. Items 1 and 12 against stop 9: not all below, not all low, some not low.",
   ["req-hel-ext-quantifiers-3", "req-hel-reserved-roots-3", "req-pm-parsestruct-9", "req-pm-parsestruct-10"],
   ["parameter-scope", "hel/index.html#ext-quantifiers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.items ex:Root.below ex:Root.low ex:Root.high ) .
   ex:Root.items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatCount 2 ; bddo:hasArgument ( "9" ) .
   ex:Root.below a bddo:Field ; bddo:valueFromExpression "all(instance.items, instance.v < param.stop)" .
   ex:Root.low a bddo:Field ; bddo:valueFromExpression "all(items, low)" .
   ex:Root.high a bddo:Field ; bddo:valueFromExpression "any(root.items, not low)" .
   ex:Item a bddo:Struct ; bddo:hasParameter ( ex:Item.stop ) ; bddo:hasField ( ex:Item.v ex:Item.low ) .
   ex:Item.stop a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Item.v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Item.low a bddo:LocalBinding ; bddo:localExpression "instance.v < param.stop" .
   """,
   b"\x01\x0c", {"items": [{"v": 1}, {"v": 12}], "below": False, "low": False, "high": True}, manifest=QUANTIFIER)

pp("param-quantifier-holding-struct", "Inside a quantifier over struct elements, the holding struct's parameters are not reachable",
   "Outer declares limit, but the predicate runs with each Plain element as instance, and Plain declares no parameter: "
   "a description error when the description is loaded.",
   ["req-hel-reserved-roots-3", "req-hel-ext-quantifiers-3", "req-pm-errors-8"], ["errors", "hel/index.html#reserved-roots"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.o ) .
   ex:Root.o a bddo:Field ; bddo:dataType ex:Outer ; bddo:hasArgument ( "5" ) .
   ex:Outer a bddo:Struct ; bddo:hasParameter ( ex:Outer.limit ) ; bddo:hasField ( ex:Outer.items ex:Outer.ok ) .
   ex:Outer.limit a bddo:Parameter .
   ex:Outer.items a bddo:Field ; bddo:dataType ex:Plain ; bddo:repeatCount 2 .
   ex:Outer.ok a bddo:Field ; bddo:valueFromExpression "all(instance.items, instance.v < param.limit)" .
   ex:Plain a bddo:Struct ; bddo:hasField ( ex:Plain.v ) .
   ex:Plain.v a bddo:Field ; bddo:dataType bddo:uint8 .
   """, b"\x01\x02", error="Description", manifest=QUANTIFIER)

pp("param-on-text-container", "A text container with parameters is a description error",
   "The key/value header declares bddo:hasParameter; its members are located by key, so it has no scope for arguments.",
   ["req-bddo-parameterised-structs-4", "req-pm-errors-8"], ["errors", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.h ) .
   ex:Root.h a bddo:Field ; bddo:dataType ex:Hdr ; bddo:size 10 ; bddo:hasArgument ( "1" ) .
   ex:Hdr a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:recordDelimiter "0A"^^xsd:hexBinary ;
       bddo:hasParameter ( ex:Hdr.n ) ; bddo:hasField ( ex:Hdr.samples ) .
   ex:Hdr.n a bddo:Parameter .
   ex:Hdr.samples a bddo:Field ; bddo:dataType bddo:asciiInteger .
   """, b"samples=4\n", error="Description")

pp("param-root-struct", "A root struct with parameters is a description error",
   "The root has no caller to supply its argument.",
   ["req-pm-parsestruct-9", "req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasParameter ( ex:Root.n ) ; bddo:hasField ( ex:Root.v ) .
   ex:Root.n a bddo:Parameter .
   ex:Root.v a bddo:Field ; bddo:dataType bddo:uint8 .
   """, b"\x01", error="Description")

pp("param-argument-forward-reference", "An argument naming a later field is a forward reference",
   "The argument reads instance.n, which is declared after the field that passes it.",
   ["req-hel-undefined-names-4", "req-pm-context-1"], ["context", "hel/index.html#undefined-names"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.b ex:Root.n ) .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Blob ; bddo:hasArgument ( "instance.n" ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Blob a bddo:Struct ; bddo:hasParameter ( ex:Blob.size ) ; bddo:hasField ( ex:Blob.data ) .
   ex:Blob.size a bddo:Parameter .
   ex:Blob.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.size" .
   """, b"\x01\x01", error="Expression")

# ----------------------------------------------------------------- local bindings

LET = ["req-pm-parsestruct-10"]
pp("let-size-and-count", "A local binding supplies a size and a count, and is not in the tree",
   "area = w * h sizes the pixels; spare = area - 4, read by bare name, counts the marks. Neither binding appears in the tree.",
   LET + ["req-bddo-structural-properties-1"], ["algorithm", "parameter-scope", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.w ex:Root.h ex:Root.area ex:Root.pixels ex:Root.spare ex:Root.marks ) .
   ex:Root.w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.h a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.area a bddo:LocalBinding ; bddo:localExpression "instance.w * instance.h" .
   ex:Root.pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.area" .
   ex:Root.spare a bddo:LocalBinding ; bddo:localExpression "area - 4" .
   ex:Root.marks a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromExpression "spare" .
   """,
   b"\x02\x03" + b"pixels" + b"\x01\x02",
   {"w": 2, "h": 3, "pixels": b"pixels", "marks": [1, 2]})

pp("let-struct-size", "A struct's size expression may read a local binding of the struct",
   "total = n + 1 bounds the box; the byte after its region is the next field.",
   LET + ["req-pm-struct-size-3"], ["struct-size", "parameter-scope"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.box ex:Root.after ) .
   ex:Root.box a bddo:Field ; bddo:dataType ex:Box .
   ex:Root.after a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Box a bddo:Struct ; bddo:sizeFromExpression "instance.total" ;
       bddo:hasField ( ex:Box.n ex:Box.total ex:Box.first ) .
   ex:Box.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Box.total a bddo:LocalBinding ; bddo:localExpression "instance.n + 1" .
   ex:Box.first a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   bytes.fromhex("04aabbccddee"), {"box": {"n": 4, "first": 0xAA}, "after": 0xEE})

pp("let-with-parameter", "A local binding may compute from a parameter",
   "Row binds bytes = param.n * 2 and sizes its data with it.",
   LET + ["req-pm-parsestruct-9"], ["algorithm", "parameter-scope"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.row ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.row a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.n" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ) ; bddo:hasField ( ex:Row.bytes ex:Row.data ) .
   ex:Row.n a bddo:Parameter .
   ex:Row.bytes a bddo:LocalBinding ; bddo:localExpression "param.n * 2" .
   ex:Row.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "bytes" .
   """,
   b"\x02abcd", {"n": 2, "row": {"data": b"abcd"}})

pp("let-forward-reference", "Reading a local binding before its position is a forward reference",
   "pixels reads area, which is bound only after it.",
   LET + ["req-hel-undefined-names-4", "req-pm-context-1"], ["parameter-scope", "hel/index.html#undefined-names"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.w ex:Root.pixels ex:Root.area ) .
   ex:Root.w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.area" .
   ex:Root.area a bddo:LocalBinding ; bddo:localExpression "instance.w * 2" .
   """, b"\x02abcd", error="Expression")

pp("let-not-reachable-through-parent", "A local binding is not a node: parent.<name> does not reach it",
   "The child struct reads parent.area, which names no field of the parent: an undefined name.",
   ["req-hel-undefined-names-2", "req-hel-key-resolution-2"], ["parameter-scope", "hel/index.html#local-bindings"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.w ex:Root.area ex:Root.child ) .
   ex:Root.w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.area a bddo:LocalBinding ; bddo:localExpression "instance.w * 2" .
   ex:Root.child a bddo:Field ; bddo:dataType ex:Child .
   ex:Child a bddo:Struct ; bddo:hasField ( ex:Child.data ) .
   ex:Child.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "parent.area" .
   """, b"\x02abcd", error="Expression")

pp("let-not-reachable-through-self", "A local binding is not a node: self.<name> does not reach it",
   "The repeat-until condition over struct elements reads self.last; self is the element, as instance is, but a binding "
   "is reached only through instance: an undefined name.",
   ["req-hel-undefined-names-2", "req-hel-key-resolution-2"], ["parameter-scope", "hel/index.html#local-bindings"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.items ) .
   ex:Root.items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatUntil "self.last" .
   ex:Item a bddo:Struct ; bddo:hasField ( ex:Item.v ex:Item.last ) .
   ex:Item.v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Item.last a bddo:LocalBinding ; bddo:localExpression "instance.v == 9" .
   """, b"\x09", error="Expression")

pp("let-name-clash", "A local binding sharing its name with a field is a description error",
   "The binding ex:Root.w and the field ex:w have the same simple key.",
   ["req-bddo-parameterised-structs-3", "req-pm-errors-8"], ["errors", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:Root.w ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.w a bddo:LocalBinding ; bddo:localExpression "1" .
   """, b"\x02", error="Description")

pp("let-in-header", "A local binding in a key/value header is a description error",
   "bddo:LocalBindingShape rejects a binding in a text container, which has no member order.",
   ["req-bddo-parameterised-structs-3", "req-pm-errors-8"], ["errors", "bddo/index.html#parameterised-structs"],
   """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ;
       bddo:hasField ( ex:Root.samples ex:Root.twice ) .
   ex:Root.samples a bddo:Field ; bddo:dataType bddo:asciiInteger .
   ex:Root.twice a bddo:LocalBinding ; bddo:localExpression "instance.samples * 2" .
   """, b"samples=4\n", error="Description")

# ----------------------------------------------------------------- semantic emitter

se("parameters-and-bindings-not-emitted", "Parameters and local bindings are never emitted",
   "Only the mapped fields are lifted: the parameter scale and the binding doubled produce no triples, though the "
   "value expression of a mapped field reads both after the parse (2 x 6 + 3 = 15).",
   ["req-pm-emission-10", "req-pm-emission-5"], ["emission", "parameter-scope"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:Root.v ex:Root.item ) .
   ex:Root.v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   ex:Root.item a bddo:Field ; bddo:dataType ex:Item ; bddo:hasArgument ( "instance.v" ) ;
       hexplain:mapsToObjectProperty ex:item .
   ex:Item a bddo:Struct ; hexplain:mapsToClass ex:ItemClass ; bddo:hasParameter ( ex:Item.scale ) ;
       bddo:hasField ( ex:Item.doubled ex:Item.w ex:Item.s ) .
   ex:Item.scale a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Item.doubled a bddo:LocalBinding ; bddo:localExpression "param.scale * 2" .
   ex:Item.w a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:width .
   ex:Item.s a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:scaled ;
       hexplain:valueExpression "instance.s * doubled + param.scale" ; hexplain:valueDatatype xsd:integer .
   """,
   bytes([3, 5, 2]),
   f"""
   {SE_ROOT} a ex:File ; ex:value "3"^^xsd:unsignedByte ; ex:item <urn:example:input#root/item> .
   <urn:example:input#root/item> a ex:ItemClass ; ex:width "5"^^xsd:unsignedByte ; ex:scaled "15"^^xsd:integer .
   """)
