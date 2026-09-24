"""Physical Parser cases: the parse algorithm of the Processing Model, one construct per case.

Each expected tree is read off the specification text cited by the case's requirements and
sections; the comments give the arithmetic where the value is not obvious from the input.
"""
import struct
import zlib

from suite import Case

PM = "processing#"
CASES = []


def pp(id, title, intent, reqs, sections, description, data, expected=None, error=None, **kw):
    CASES.append(Case(id=f"pp-{id}", cls="physical-parser", title=title, intent=intent,
                      requirements=reqs, sections=[PM + s if "#" not in s else s for s in sections],
                      description=description, input=data, expected=expected, error=error, **kw))


GENERIC = "req-pm-conformance-1"

# ----------------------------------------------------------------- integers and byte order

pp("int-default-big-endian", "Integers default to big-endian",
   "A multi-byte integer with no byte order declared anywhere is read big-endian (the last case of the byte-order list).",
   [GENERIC, "req-pm-introduction-1"], ["byte-order"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint32 .
   """,
   b"\x01\x02" + b"\x00\x00\x01\x00",
   {"a": 0x0102, "b": 0x100})

pp("int-signed-widths", "Signed integers are two's complement at every width",
   "int8, int16, int32 and int64 decode their two's-complement bit patterns, the int64 minimum included.",
   [GENERIC], ["byte-order", "value-mapping"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:int8 .
   ex:b a bddo:Field ; bddo:dataType bddo:int16 .
   ex:c a bddo:Field ; bddo:dataType bddo:int32 .
   ex:d a bddo:Field ; bddo:dataType bddo:int64 .
   """,
   b"\xff" + b"\xff\xfe" + b"\xff\xff\xff\xfd" + b"\x80" + b"\x00" * 7,
   {"a": -1, "b": -2, "c": -3, "d": -(2 ** 63)})

pp("int-uint64-above-int64", "A uint64 above 2^63-1 keeps its exact value",
   "The largest uint64 is decoded exactly; above 2^53 the canonical form writes it as a decimal string.",
   ["req-hel-numeric-semantics-5"], ["byte-order", "value-mapping"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:big ex:edge ) .
   ex:big a bddo:Field ; bddo:dataType bddo:uint64 .
   ex:edge a bddo:Field ; bddo:dataType bddo:uint64 .
   """,
   b"\xff" * 8 + struct.pack(">Q", 2 ** 53 + 1),
   {"big": 2 ** 64 - 1, "edge": 2 ** 53 + 1})

pp("read-past-end", "A read past the end of the stream is a bounds error",
   "A uint32 field over a two-byte stream would pass the end of the stream.",
   ["req-pm-errors-1", "req-pm-errors-3"], ["errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint32 .
   """,
   b"\x00\x01", error="Bounds")

pp("codec-zlib", "menc:Zlib decodes zlib-framed data",
   "A bytes field encoded with menc:Zlib yields the inflated bytes.",
   ["req-pm-minimum-codecs-2", "req-pm-minimum-codecs-5", "req-pm-emission-1"], ["minimum-codecs", "emission"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n ; hexplain:isEncodedWith menc:Zlib .
   """,
   bytes([len(zlib.compress(b"hello hello hello"))]) + zlib.compress(b"hello hello hello"),
   {"n": len(zlib.compress(b"hello hello hello")), "data": b"hello hello hello"})
