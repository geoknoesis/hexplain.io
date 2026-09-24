"""Physical Parser cases: integers, byte order, floats, bit fields and alignment."""
import struct

from cases_physical import GENERIC, pp

pp("int-explicit-order-types", "An explicitly ordered data type wins over every declaration",
   "bddo:uint16le and bddo:int32le read little-endian inside a struct declared big-endian, and bddo:uint16be big-endian inside one declared little-endian.",
   [GENERIC], ["byte-order"],
   """
   ex:Root a bddo:Struct ; bddo:endianness bddo:BigEndian ; bddo:hasField ( ex:a ex:b ex:inner ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16le .
   ex:b a bddo:Field ; bddo:dataType bddo:int32le .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:Inner a bddo:Struct ; bddo:endianness bddo:LittleEndian ; bddo:hasField ( ex:c ) .
   ex:c a bddo:Field ; bddo:dataType bddo:uint16be .
   """,
   b"\x01\x02" + b"\xfe\xff\xff\xff" + b"\x01\x02",
   {"a": 0x0201, "b": -2, "inner": {"c": 0x0102}})

pp("int-field-endianness", "A field's own byte order overrides its struct's",
   "bddo:endianness on the field outranks the containing struct's declaration.",
   [GENERIC], ["byte-order"],
   """
   ex:Root a bddo:Struct ; bddo:endianness bddo:BigEndian ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:endianness bddo:LittleEndian .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   """,
   b"\x01\x02\x01\x02", {"a": 0x0201, "b": 0x0102})

pp("int-endianness-inherited", "A nested struct inherits the byte order in force",
   "A struct that declares no byte order reads in the order of the struct it is parsed from; a nested declaration wins again below it.",
   [GENERIC], ["byte-order"],
   """
   ex:Root a bddo:Struct ; bddo:endianness bddo:LittleEndian ; bddo:hasField ( ex:mid ) .
   ex:mid a bddo:Field ; bddo:dataType ex:Mid .
   ex:Mid a bddo:Struct ; bddo:hasField ( ex:a ex:deep ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:deep a bddo:Field ; bddo:dataType ex:Deep .
   ex:Deep a bddo:Struct ; bddo:endianness bddo:BigEndian ; bddo:hasField ( ex:b ex:leaf ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:leaf a bddo:Field ; bddo:dataType ex:Leaf .
   ex:Leaf a bddo:Struct ; bddo:hasField ( ex:c ) .
   ex:c a bddo:Field ; bddo:dataType bddo:uint16 .
   """,
   b"\x01\x02" * 3, {"mid": {"a": 0x0201, "deep": {"b": 0x0102, "leaf": {"c": 0x0102}}}})

pp("int-conditional-endianness", "Conditional byte order is resolved from a discriminator field",
   "A TIFF-style II/MM marker selects the struct's byte order once it is bound; later fields and nested structs read in the selected order.",
   [GENERIC], ["byte-order"],
   """
   ex:Root a bddo:Struct ;
       bddo:hasConditionalEndianness (
           [ a bddo:EndiannessRule ; bddo:condition "order == 'II'" ; bddo:ruleEndianness bddo:LittleEndian ]
           [ a bddo:EndiannessRule ; bddo:condition "order == 'MM'" ; bddo:ruleEndianness bddo:BigEndian ] ) ;
       bddo:hasField ( ex:order ex:magic ex:ifd ) .
   ex:order a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   ex:magic a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:ifd a bddo:Field ; bddo:dataType ex:Ifd .
   ex:Ifd a bddo:Struct ; bddo:hasField ( ex:offset ) .
   ex:offset a bddo:Field ; bddo:dataType bddo:uint32 .
   """,
   b"II" + b"\x2a\x00" + b"\x08\x00\x00\x00",
   {"order": "II", "magic": 42, "ifd": {"offset": 8}})

pp("int-conditional-endianness-provisional", "Fields before a conditional byte order resolves use the provisional order",
   "Until a rule matches, fields read in the inherited order (big-endian at the root); a rule naming a field not yet bound counts as not holding.",
   [GENERIC], ["byte-order"],
   """
   ex:Root a bddo:Struct ;
       bddo:hasConditionalEndianness (
           [ a bddo:EndiannessRule ; bddo:condition "flag == 1" ; bddo:ruleEndianness bddo:LittleEndian ] ) ;
       bddo:hasField ( ex:early ex:flag ex:late ) .
   ex:early a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:flag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:late a bddo:Field ; bddo:dataType bddo:uint16 .
   """,
   b"\x01\x02" + b"\x01" + b"\x01\x02",
   {"early": 0x0102, "flag": 1, "late": 0x0201})

pp("float-ieee754", "Floats decode as IEEE 754 in the resolved byte order",
   "float32 and float64, big- and little-endian.",
   [GENERIC], ["byte-order", "value-mapping"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float32 .
   ex:b a bddo:Field ; bddo:dataType bddo:float64 .
   ex:c a bddo:Field ; bddo:dataType bddo:float32le .
   ex:d a bddo:Field ; bddo:dataType bddo:float64le .
   """,
   struct.pack(">f", 1.5) + struct.pack(">d", -0.25) + struct.pack("<f", 3.0) + struct.pack("<d", 1e100),
   {"a": 1.5, "b": -0.25, "c": 3.0, "d": 1e100})

pp("float-nan-infinity", "NaN and infinities survive decoding",
   "A float field holding NaN or an infinity yields that value; the canonical form spells them as strings.",
   [GENERIC], ["value-mapping"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:float32 .
   ex:b a bddo:Field ; bddo:dataType bddo:float64 .
   ex:c a bddo:Field ; bddo:dataType bddo:float64 .
   """,
   bytes.fromhex("7fc00000") + bytes.fromhex("7ff0000000000000") + bytes.fromhex("fff0000000000000"),
   {"a": float("nan"), "b": float("inf"), "c": float("-inf")})

pp("members-in-list-order", "Members are processed in bddo:hasField list order",
   "The fields are read in the order of the rdf:List, not in the order of their IRIs.",
   ["req-pm-parsestruct-1"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:zeta ex:alpha ex:mid ) .
   ex:alpha a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:mid a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:zeta a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x02\x03\x04", {"zeta": 1, "alpha": 0x0203, "mid": 4})

# ----------------------------------------------------------------- bit fields

pp("bits-msb-first", "Bit fields pack most-significant bit first by default",
   "Two 4-bit fields over 0x45 read 4 and 5 (the IPv4 version/IHL byte); a following byte field starts on the next byte.",
   [GENERIC], ["bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:version ex:ihl ex:tos ) .
   ex:version a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   ex:ihl a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   ex:tos a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x45\x10", {"version": 4, "ihl": 5, "tos": 0x10})

pp("bits-span-byte-boundary", "A bit field continues into the next byte",
   "A 4-bit field then a 12-bit field over AB CD read 0xA and 0xBCD, the second spanning the byte boundary.",
   [GENERIC], ["bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:bitLength 12 .
   """,
   b"\xab\xcd", {"a": 0xA, "b": 0xBCD})

pp("bits-lsb-first", "bddo:LSBFirst takes bits from the least-significant end",
   "Under LSBFirst a 3-bit then a 5-bit field over 0xB4 (1011 0100) take the low three bits (100 = 4) and then the high five (10110 = 22); each value keeps its bits' significance.",
   [GENERIC], ["bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:bitOrder bddo:LSBFirst ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 3 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 5 .
   """,
   b"\xb4", {"a": 4, "b": 22})

pp("bits-lsb-span", "Under LSBFirst a field spanning bytes takes its later bits as more significant",
   "A 4-bit then a 12-bit field over CD AB: the first takes CD's low nibble (0xD), the second CD's high nibble as its low four bits and all of AB above them (0xABC).",
   [GENERIC], ["bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:bitOrder bddo:LSBFirst ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:bitLength 12 .
   """,
   b"\xcd\xab", {"a": 0xD, "b": 0xABC})

pp("bits-realign-before-byte-field", "The bit cursor realigns before a byte-oriented read",
   "After a 3-bit field the remaining five bits of the byte are skipped; the uint8 reads the next byte.",
   [GENERIC], ["bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 3 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\xe0\x07", {"a": 7, "b": 7})

pp("bits-realign-at-struct-end", "The bit cursor realigns at the end of a struct",
   "A nested struct holding one 4-bit field consumes its whole byte; the sibling bit field after it reads the next byte.",
   [GENERIC], ["bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:head ex:b ) .
   ex:head a bddo:Field ; bddo:dataType ex:Head .
   ex:Head a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   """,
   b"\x12\x34", {"head": {"a": 1}, "b": 3})

pp("bits-past-end", "A bit read past the end of the stream is a bounds error",
   "Twelve bits cannot be read from one byte.",
   ["req-pm-errors-3"], ["bit-cursor", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:bitLength 12 .
   """,
   b"\xff", error="Bounds")

pp("bits-offset-read-restores-bit-cursor", "An offset-addressed read does not disturb a run of bit fields",
   "Between two 4-bit fields, an offset-addressed byte is read; the second nibble still comes from the first byte.",
   [GENERIC], ["algorithm", "bit-cursor"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hi ex:far ex:lo ) .
   ex:hi a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   ex:far a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 2 .
   ex:lo a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 4 .
   """,
   b"\x9c\x00\x77", {"hi": 9, "far": 0x77, "lo": 0xC})

# ----------------------------------------------------------------- alignment

pp("align-from-stream-start", "Alignment is measured from the start of the stream",
   "A uint32 aligned to 4 after one byte starts at offset 4; the skipped bytes are not read.",
   [GENERIC], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint32 ; bddo:alignment 4 .
   """,
   b"\x01\xee\xee\xee\x00\x00\x00\x02", {"a": 1, "b": 2})

pp("align-region-does-not-move-origin", "A bounded region does not move the alignment origin",
   "Inside a 10-byte region starting at offset 6, a field aligned to 4 after one byte starts at offset 8, not 10.",
   [GENERIC], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pad ex:box ) .
   ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 6 .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:size 10 .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:alignment 4 .
   """,
   b"\x00" * 6 + b"\x07" + b"\xee" + b"\x12\x34" + b"\x00" * 6,
   {"pad": b"\x00" * 6, "box": {"a": 7, "b": 0x1234}})
