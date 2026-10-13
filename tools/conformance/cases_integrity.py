"""Physical Parser cases: checksums and codecs (the minimum codec set and Delta parameters).

Compressed inputs are written out as hex rather than produced by the local zlib, whose output can
differ between versions; each constant is checked against its plain text when the suite is
generated.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Any

from cases_physical import pp


def crc16_ccitt_false(data: Any) -> Any:
    """CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF, no reflection, no final XOR."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


assert crc16_ccitt_false(b"123456789") == 0x29B1  # the catalogue check value


def inflate(data: Any, wbits: Any) -> Any:
    out = zlib.decompressobj(wbits)
    return out.decompress(data) + out.flush()


RAW_DEFLATE = bytes.fromhex("63656067e0640000")  # raw DEFLATE of 05 00 07 00 09 00
ZLIB_123 = bytes.fromhex("78da6364620600000d0007")  # zlib of 01 02 03
GZIP_ABC = bytes.fromhex("1f8b080000000000020a4b4c4a0600c241243503000000")
GZIP_DEF = bytes.fromhex("1f8b080000000000020a4b494d030061e1c40c03000000")
ZLIB_DELTA = bytes.fromhex("78dae362646414616262020000c60028")  # zlib of 0A 01 01 01 14 02 02 02
assert inflate(RAW_DEFLATE, -15) == bytes.fromhex("050007000900")
assert zlib.decompress(ZLIB_123) == b"\x01\x02\x03"
assert inflate(GZIP_ABC, 31) == b"abc" and inflate(GZIP_DEF, 31) == b"def"
assert zlib.decompress(ZLIB_DELTA) == bytes([10, 1, 1, 1, 20, 2, 2, 2])

# ----------------------------------------------------------------- checksums

CRC_BODY = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:type ex:data ex:crc ) .
   ex:type a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromField ex:type ; bddo:coversToField ex:data ] .
"""

pp(
    "checksum-crc32",
    "CRC-32 over a field range, as zlib computes it",
    "coversFromField..coversToField covers the type and data fields inclusive.",
    ["req-pm-parsefield-16"],
    ["algorithm"],
    CRC_BODY,
    b"IENDabc" + struct.pack(">I", zlib.crc32(b"IENDabc")),
    {"type": "IEND", "data": b"abc", "crc": zlib.crc32(b"IENDabc")},
)

pp(
    "checksum-crc32-mismatch",
    "A checksum mismatch is a checksum error",
    "The stored CRC-32 is off by one.",
    ["req-pm-errors-1", "req-pm-errors-5"],
    ["algorithm", "errors"],
    CRC_BODY,
    b"IENDabc" + struct.pack(">I", zlib.crc32(b"IENDabc") ^ 1),
    error="Checksum",
)

pp(
    "checksum-adler32",
    "Adler-32 over a field range",
    "Adler-32 of 'Wikipedia' is 0x11E60398.",
    ["req-pm-parsefield-16"],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:adler32 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"Wikipedia" + struct.pack(">I", zlib.adler32(b"Wikipedia")),
    {"text": "Wikipedia", "sum": 0x11E60398},
)

pp(
    "checksum-crc16-ccitt-false",
    "bddo:crc16 is CRC-16/CCITT-FALSE",
    "Polynomial 0x1021, initial value 0xFFFF: the check value over '123456789' is 0x29B1.",
    ["req-pm-parsefield-16"],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint16 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc16 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"123456789" + struct.pack(">H", 0x29B1),
    {"text": "123456789", "sum": 0x29B1},
)

pp(
    "checksum-crc16-mismatch",
    "A CRC-16 computed with another variant does not match",
    "0x31C3 is CRC-16/XMODEM (initial value 0) of '123456789', not CCITT-FALSE.",
    ["req-pm-errors-5"],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint16 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc16 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"123456789" + struct.pack(">H", 0x31C3),
    error="Checksum",
)

DIGESTS = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256}
for algorithm, fn in DIGESTS.items():
    digest = fn(b"hexplain").digest()
    pp(
        f"checksum-{algorithm}",
        f"A {algorithm.upper()} digest is compared byte for byte",
        f"A {len(digest)}-byte bytes field holds the {algorithm} digest of the text before it.",
        ["req-pm-parsefield-16"],
        ["algorithm"],
        f"""
       ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:digest ) .
       ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 8 ; bddo:encoding bddo:ascii .
       ex:digest a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size {len(digest)} ;
           bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:{algorithm} ;
                           bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
       """,
        b"hexplain" + digest,
        {"text": "hexplain", "digest": digest},
    )

pp(
    "checksum-sha256-mismatch",
    "A digest mismatch is a checksum error",
    "The last byte of the SHA-256 digest is changed.",
    ["req-pm-errors-5"],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:digest ) .
   ex:text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 8 ; bddo:encoding bddo:ascii .
   ex:digest a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:sha256 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"hexplain" + hashlib.sha256(b"hexplain").digest()[:-1] + b"\x00",
    error="Checksum",
)

pp(
    "checksum-covers-expressions",
    "Coverage by expressions: start inclusive, end exclusive",
    "coversFromExpression 1 and coversToExpression 4 cover bytes 1, 2 and 3.",
    ["req-pm-parsefield-16"],
    ["algorithm", "hel/index.html#name-binding"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:crc ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 5 .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromExpression "1" ; bddo:coversToExpression "4" ] .
   """,
    b"abcde" + struct.pack(">I", zlib.crc32(b"bcd")),
    {"data": b"abcde", "crc": zlib.crc32(b"bcd")},
)

pp(
    "checksum-coverage-out-of-bounds",
    "A coverage bound outside the stream is a bounds error",
    "The covered range ends past the end of the stream.",
    ["req-pm-errors-3"],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:crc ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 5 .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromExpression "0" ; bddo:coversToExpression "stream.length + 5" ] .
   """,
    b"abcde" + struct.pack(">I", zlib.crc32(b"abcde")),
    error="Bounds",
)

pp(
    "checksum-empty-range",
    "A coverage range whose end precedes its start is not checked",
    "From offset 3 to offset 1 covers nothing, so the stored value (0) is not compared.",
    ["req-pm-parsefield-16"],
    ["algorithm"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:crc ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 5 .
   ex:crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
                       bddo:coversFromExpression "3" ; bddo:coversToExpression "1" ] .
   """,
    b"abcde\x00\x00\x00\x00",
    {"data": b"abcde", "crc": 0},
)

# ----------------------------------------------------------------- codecs


def codec_field(codec_turtle: Any, size: Any) -> str:
    return f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size {size} ; {codec_turtle} .
   """


def delta_params(params: Any) -> Any:
    return ", ".join(
        f'[ a hexplain:CodecParameter ; hexplain:parameterName "{k}" ; hexplain:parameterValue {v} ]'
        for k, v in params.items()
    )


def delta_field(params: Any, size: Any) -> Any:
    listed = delta_params(params)
    parameter = f" ; hexplain:codecParameter {listed}" if listed else ""
    return codec_field(
        f"hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Delta{parameter} ] )", size
    )


pp(
    "codec-store",
    "menc:Store is the identity",
    "The decoded bytes are the stored bytes.",
    ["req-pm-minimum-codecs-2", "req-pm-minimum-codecs-3"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Store", 3),
    b"xyz",
    {"data": b"xyz"},
)

pp(
    "codec-deflate-substream",
    "Raw DEFLATE decoded and re-parsed as a struct",
    "The inflated bytes 05 00 07 00 09 00 are re-parsed as a fresh sub-stream against the field's struct type.",
    ["req-pm-minimum-codecs-2", "req-pm-minimum-codecs-4", "req-pm-emission-1", "req-core-static-mapping-properties-3"],
    ["minimum-codecs", "emission"],
    f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:block ex:tail ) .
   ex:block a bddo:Field ; bddo:dataType ex:Payload ; bddo:size {len(RAW_DEFLATE)} ; hexplain:isEncodedWith \
menc:Deflate .
   ex:Payload a bddo:Struct ; bddo:endianness bddo:LittleEndian ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:c a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    RAW_DEFLATE + b"\x2a",
    {"block": {"a": 5, "b": 7, "c": 9}, "tail": 42},
)

pp(
    "codec-substream-origin",
    "A decoded sub-stream has its own offsets and length",
    "Inside a struct re-parsed from decoded bytes, alignment and stream.position count from the sub-stream's "
    "start and stream.length is its length.",
    ["req-pm-emission-1"],
    ["algorithm", "stream-metadata", "emission"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pad ex:block ) .
   ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   ex:block a bddo:Field ; bddo:dataType ex:Inner ; bddo:size 4 ; hexplain:isEncodedWith menc:Store .
   ex:Inner a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:pos ex:len ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:alignment 2 .
   ex:pos a bddo:Field ; bddo:valueFromExpression "stream.position" .
   ex:len a bddo:Field ; bddo:valueFromExpression "stream.length" .
   """,
    b"\x00\x00\x00" + b"\x01\xee\x00\x05",
    {"pad": b"\x00\x00\x00", "block": {"a": 1, "b": 5, "pos": 4, "len": 4}},
)

pp(
    "codec-zlib-adler-mismatch",
    "A zlib Adler-32 mismatch is a checksum error",
    "The last byte of the zlib trailer is changed.",
    ["req-pm-minimum-codecs-5", "req-pm-errors-5"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Zlib", len(ZLIB_123)),
    ZLIB_123[:-1] + bytes([ZLIB_123[-1] ^ 0xFF]),
    error="Checksum",
)

pp(
    "codec-zlib-trailing-bytes",
    "Bytes after the end of a zlib stream inside its block are a validation error",
    "One stray byte follows the zlib trailer within the field's region.",
    ["req-pm-minimum-codecs-10", "req-pm-minimum-codecs-5"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Zlib", len(ZLIB_123) + 1),
    ZLIB_123 + b"\x00",
    error="Validation",
)

pp(
    "codec-deflate-truncated",
    "Compressed data that cannot be decoded is a validation error",
    "A raw DEFLATE block cut short by two bytes.",
    ["req-pm-minimum-codecs-10", "req-pm-minimum-codecs-4"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Deflate", len(RAW_DEFLATE) - 3),
    RAW_DEFLATE[:-3],
    error="Validation",
)

pp(
    "codec-gzip-members",
    "Several gzip members decode in order and concatenate",
    "Two members holding 'abc' and 'def' decode to 'abcdef'.",
    ["req-pm-minimum-codecs-6"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Gzip", len(GZIP_ABC) + len(GZIP_DEF)),
    GZIP_ABC + GZIP_DEF,
    {"data": b"abcdef"},
)

pp(
    "codec-gzip-crc-mismatch",
    "A gzip member's CRC-32 mismatch is a checksum error",
    "The member's CRC-32 trailer is changed.",
    ["req-pm-minimum-codecs-6", "req-pm-errors-5"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Gzip", len(GZIP_ABC)),
    GZIP_ABC[:-8] + bytes([GZIP_ABC[-8] ^ 1]) + GZIP_ABC[-7:],
    error="Checksum",
)

pp(
    "codec-gzip-isize-mismatch",
    "A gzip member's length (ISIZE) mismatch is a checksum error",
    "ISIZE says 4 where 3 bytes decode.",
    ["req-pm-minimum-codecs-6", "req-pm-errors-5"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Gzip", len(GZIP_ABC)),
    GZIP_ABC[:-4] + struct.pack("<I", 4),
    error="Checksum",
)

pp(
    "codec-gzip-trailing-garbage",
    "Bytes after the last gzip member that begin no member are a validation error",
    "Two bytes of garbage follow the only member.",
    ["req-pm-minimum-codecs-6"],
    ["minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Gzip", len(GZIP_ABC) + 2),
    GZIP_ABC + b"xx",
    error="Validation",
)

pp(
    "codec-delta-bytes",
    "menc:Delta with one-byte samples, arithmetic modulo 256",
    "Each byte adds the restored byte before it, modulo 256: 12 + 250 restores to 6.",
    ["req-pm-minimum-codecs-7", "req-pm-minimum-codecs-8"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 1}, 5),
    bytes([10, 1, 1, 250, 10]),
    {"data": bytes([10, 11, 12, 6, 16])},
)

pp(
    "codec-delta-16-bit",
    "menc:Delta with two-byte samples in both byte orders",
    "Big-endian by default, little-endian with littleEndian 1: 0x00FF then +2 restores 0x0101.",
    ["req-pm-minimum-codecs-7"],
    ["minimum-codecs", "delta-parameters"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:be ex:le ) .
   ex:be a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ;
       hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Delta ;
           hexplain:codecParameter [ a hexplain:CodecParameter ; hexplain:parameterName "elementSize" ; \
hexplain:parameterValue 2 ] ] ) .
   ex:le a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ;
       hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Delta ;
           hexplain:codecParameter [ a hexplain:CodecParameter ; hexplain:parameterName "elementSize" ; \
hexplain:parameterValue 2 ] ,
                                   [ a hexplain:CodecParameter ; hexplain:parameterName "littleEndian" ; \
hexplain:parameterValue 1 ] ] ) .
   """,
    bytes.fromhex("00ff0002") + bytes.fromhex("ff000200"),
    {"be": bytes.fromhex("00ff0101"), "le": bytes.fromhex("ff000101")},
)

pp(
    "codec-delta-samples-per-pixel",
    "samplesPerPixel predicts each channel from the previous pixel",
    "RGB pixels: each sample adds the same channel of the pixel before it.",
    ["req-pm-minimum-codecs-7"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 1, "samplesPerPixel": 3}, 9),
    bytes([10, 20, 30, 1, 2, 3, 1, 1, 1]),
    {"data": bytes([10, 20, 30, 11, 22, 33, 12, 23, 34])},
)

pp(
    "codec-delta-row-bytes",
    "rowBytes restarts the predictor at every row",
    "Two-byte rows: the first sample of each row is stored as is; a short last row decodes as far as it goes.",
    ["req-pm-minimum-codecs-7"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 1, "rowBytes": 2}, 5),
    bytes([5, 1, 7, 1, 9]),
    {"data": bytes([5, 6, 7, 8, 9])},
)

pp(
    "codec-delta-predictor-1",
    "predictor 1 is the identity",
    "No prediction: the stage passes the bytes through.",
    ["req-pm-minimum-codecs-7"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 1, "predictor": 1}, 3),
    bytes([5, 1, 1]),
    {"data": bytes([5, 1, 1])},
)

pp(
    "codec-delta-predictor-3",
    "An undefined predictor is refused with Unsupported feature",
    "TIFF's floating-point predictor 3 is not defined by this version.",
    ["req-pm-minimum-codecs-9", "req-pm-errors-10"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 1, "predictor": 3}, 3),
    bytes([5, 1, 1]),
    error="Unsupported",
)

pp(
    "codec-delta-missing-element-size",
    "menc:Delta without its required elementSize is a description error",
    "elementSize is REQUIRED.",
    ["req-pm-minimum-codecs-8", "req-pm-errors-8"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({}, 3),
    bytes([5, 1, 1]),
    error="Description",
)

pp(
    "codec-delta-unknown-parameter",
    "An unknown Delta parameter is a description error",
    "menc:Delta takes exactly its five parameters.",
    ["req-pm-errors-8"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 1, "stride": 2}, 3),
    bytes([5, 1, 1]),
    error="Description",
)

pp(
    "codec-delta-element-size-out-of-range",
    "An elementSize other than 1, 2, 4 or 8 is a description error",
    "elementSize 3.",
    ["req-pm-minimum-codecs-8", "req-pm-errors-8"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 3}, 3),
    bytes([5, 1, 1]),
    error="Description",
)

pp(
    "codec-delta-partial-sample",
    "A block that is not a whole number of samples is a validation error",
    "Three bytes of two-byte samples.",
    ["req-pm-minimum-codecs-7"],
    ["minimum-codecs", "delta-parameters"],
    delta_field({"elementSize": 2}, 3),
    bytes([5, 1, 1]),
    error="Validation",
)

pp(
    "codec-pipeline-reverse-order",
    "Encoding steps are decoded in reverse list order",
    "The list says Delta then Zlib, the order the writer applied them; a reader inflates first and then "
    "undoes the predictor.",
    ["req-pm-minimum-codecs-5", "req-pm-minimum-codecs-7"],
    ["minimum-codecs"],
    codec_field(
        "hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:Delta ; "
        'hexplain:codecParameter [ a hexplain:CodecParameter ; hexplain:parameterName "elementSize" ; '
        "hexplain:parameterValue 1 ] ] [ a hexplain:EncodingStep ; hexplain:codec menc:Zlib ] )",
        len(ZLIB_DELTA),
    ),
    ZLIB_DELTA,
    {"data": bytes([10, 11, 12, 13, 33, 35, 37, 39])},
)

pp(
    "codec-beyond-minimum-set",
    "A codec beyond the minimum set that the processor does not claim is Unsupported",
    "menc:Zstd is not in the minimum codec set; a processor that does not decode it must refuse, not return "
    "the encoded bytes.",
    [
        "req-pm-minimum-codecs-1",
        "req-pm-optional-codecs-3",
        "req-pm-conformance-classes-3",
        "req-pm-conformance-classes-4",
        "req-pm-errors-10",
        "req-pm-errors-11",
    ],
    ["minimum-codecs", "optional-codecs", "refusal"],
    codec_field("hexplain:isEncodedWith menc:Zstd", 3),
    b"\x28\xb5\x2f",
    error="Unsupported",
    manifest={"codecs": {"unclaimed": ["https://hexplain.io/ns/register/media-encoding#Zstd"]}},
)

pp(
    "codec-decoded-byte-limit",
    "Decoded output counts toward the decoded-byte limit",
    "Inflating to 17 bytes under a 10-byte maxDecodedBytes is a ResourceLimit error.",
    ["req-pm-resource-limits-1", "req-pm-resource-limits-3", "req-pm-errors-12"],
    ["resource-limits", "minimum-codecs"],
    codec_field("hexplain:isEncodedWith menc:Zlib", 16),
    bytes.fromhex("78dacb48cdc9c957c84090003a2e067d"),
    error="ResourceLimit",
    manifest={"limits": {"maxDecodedBytes": 10}},
)

pp(
    "checksum-digest-field-width",
    "A digest whose checksum field is not bytes of the digest's length is a description error",
    "A SHA-256 is 32 bytes, compared byte for byte; a bddo:uint32 checksum field cannot hold it.",
    ["req-pm-parsefield-16", "req-pm-errors-8"],
    ["algorithm", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 8 .
   ex:sum a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:sha256 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"hexplain" + hashlib.sha256(b"hexplain").digest()[:4],
    error="Description",
)

pp(
    "checksum-digest-field-short",
    "A digest whose bytes field is shorter than the digest is a description error",
    "An MD5 is 16 bytes; a 15-byte bddo:bytes checksum field is not exactly the digest's length.",
    ["req-pm-parsefield-16", "req-pm-errors-8"],
    ["algorithm", "errors"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:text ex:sum ) .
   ex:text a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 8 .
   ex:sum a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 15 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:md5 ;
                       bddo:coversFromField ex:text ; bddo:coversToField ex:text ] .
   """,
    b"hexplain" + hashlib.md5(b"hexplain").digest()[:15],
    error="Description",
)


# ----------------------------------------------------------------- the trailing parameter of Zlib and Gzip


def trailing(codec: Any, value: str = "ignore") -> str:
    return (
        f"hexplain:hasEncodingStep ( [ a hexplain:EncodingStep ; hexplain:codec menc:{codec} ; "
        f'hexplain:codecParameter [ a hexplain:CodecParameter ; hexplain:parameterName "trailing" ; '
        f'hexplain:parameterValue "{value}" ] ] )'
    )


pp(
    "codec-zlib-trailing-ignore",
    "trailing=ignore leaves the bytes after a zlib stream undecoded and unreported",
    "Two stray bytes follow the zlib trailer within the block; the output is the stream's three bytes alone.",
    ["req-pm-minimum-codecs-11", "req-pm-minimum-codecs-10"],
    ["minimum-codecs", "framing-parameters"],
    codec_field(trailing("Zlib"), len(ZLIB_123) + 2),
    ZLIB_123 + b"\xde\xad",
    {"data": b"\x01\x02\x03"},
)

pp(
    "codec-zlib-trailing-refuse",
    "trailing=refuse, the default written out, keeps the validation error",
    "The same block with the parameter at its default value.",
    ["req-pm-minimum-codecs-10", "req-pm-minimum-codecs-5"],
    ["minimum-codecs", "framing-parameters"],
    codec_field(trailing("Zlib", "refuse"), len(ZLIB_123) + 2),
    ZLIB_123 + b"\xde\xad",
    error="Validation",
)

pp(
    "codec-zlib-trailing-ignore-adler-mismatch",
    "trailing=ignore still verifies the stream's Adler-32",
    "The last byte of the zlib trailer is changed and two stray bytes follow: the check fails before the "
    "rest is ignored.",
    ["req-pm-minimum-codecs-11", "req-pm-errors-5"],
    ["minimum-codecs", "framing-parameters"],
    codec_field(trailing("Zlib"), len(ZLIB_123) + 2),
    ZLIB_123[:-1] + bytes([ZLIB_123[-1] ^ 0xFF]) + b"\xde\xad",
    error="Checksum",
)

pp(
    "codec-gzip-trailing-ignore",
    "trailing=ignore leaves the bytes after the last gzip member undecoded and unreported",
    "Two bytes that begin no member follow the only member; the output is the member's content.",
    ["req-pm-minimum-codecs-11", "req-pm-minimum-codecs-6"],
    ["minimum-codecs", "framing-parameters"],
    codec_field(trailing("Gzip"), len(GZIP_ABC) + 2),
    GZIP_ABC + b"xx",
    {"data": b"abc"},
)

pp(
    "codec-gzip-trailing-ignore-truncated-member",
    "Under trailing=ignore a member that begins and does not end is truncated data",
    "A second member is cut at the end of its ten-byte header: it began, so it is not ignorable trailing data.",
    ["req-pm-minimum-codecs-11", "req-pm-minimum-codecs-6"],
    ["minimum-codecs", "framing-parameters"],
    codec_field(trailing("Gzip"), len(GZIP_ABC) + 10),
    GZIP_ABC + GZIP_ABC[:10],
    error="Validation",
)
