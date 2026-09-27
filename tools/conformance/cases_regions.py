"""Physical Parser cases: strings, terminators, sizes and regions, repetition, offsets, sync,
presence, derived values, constraints and root keys."""
from cases_physical import pp

# ----------------------------------------------------------------- strings

pp("str-encodings", "Strings decode in their declared encoding",
   "ASCII, UTF-8 (a two-byte character), ISO-8859-1 and UTF-16BE strings of fixed size.",
   ["req-pm-parsefield-11"], ["algorithm", "value-mapping"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:b a bddo:Field ; bddo:dataType bddo:string ; bddo:size 3 ; bddo:encoding bddo:utf8 .
   ex:c a bddo:Field ; bddo:dataType bddo:string ; bddo:size 1 ; bddo:encoding bddo:latin1 .
   ex:d a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:utf16be .
   """,
   b"IHDR" + "é!".encode("utf-8") + b"\xe9" + "AB".encode("utf-16-be"),
   {"a": "IHDR", "b": "é!", "c": "é", "d": "AB"})

pp("str-trim-null", "bddo:trimNull ends a fixed-size string at its first NUL",
   "With trimNull the value is the characters before the first NUL; without it, the NUL padding is part of the value.",
   ["req-pm-parsefield-11"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:string ; bddo:size 8 ; bddo:encoding bddo:utf8 ; bddo:trimNull true .
   ex:b a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:utf8 .
   """,
   b"ab\x00cd\x00\x00\x00" + b"x\x00\x00\x00",
   {"a": "ab", "b": "x\x00\x00\x00"})

pp("str-trim-null-utf16", "A UTF-16 string is trimmed at a NUL code unit, not a zero byte",
   "In UTF-16LE the bytes 41 00 00 42 00 00 hold 'A', U+4200 and a NUL: the zero bytes inside the first two code units do not end the string.",
   ["req-pm-parsefield-11"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:string ; bddo:size 8 ; bddo:encoding bddo:utf16le ; bddo:trimNull true .
   """,
   bytes.fromhex("4100004200000000"), {"a": "A䈀"})

pp("bytes-value", "A bytes field yields its raw bytes",
   "bddo:bytes is not decoded; the canonical form writes it as lower-case hex.",
   ["req-pm-parsefield-11", "req-pm-size-resolution-9"], ["algorithm", "value-mapping"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   """,
   b"\x89PNG" + b"0a", {"a": b"\x89PNG", "b": "0a"})

# ----------------------------------------------------------------- terminators

pp("term-nul", "A terminator is consumed but is not part of the value",
   "A NUL-terminated string is followed directly by the next field.",
   ["req-pm-terminators-1", "req-pm-terminators-4"], ["terminators"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:n ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf8 ; bddo:terminator "00"^^xsd:hexBinary .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"abc\x00\x05", {"s": "abc", "n": 5})

pp("term-multibyte", "A multi-byte terminator is matched as a sequence",
   "A CR LF terminator ends the value at the first CR LF; a lone CR earlier does not.",
   ["req-pm-terminators-3"], ["terminators"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:n ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:terminator "0D0A"^^xsd:hexBinary .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"a\rb\r\nX", {"s": "a\rb", "n": 0x58})

pp("term-in-declared-region", "With a declared region the cursor moves to the region end",
   "An 8-byte string terminated by NUL: the value ends at the NUL and the bytes after it are padding.",
   ["req-pm-terminators-5"], ["terminators", "size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:n ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:size 8 ; bddo:terminator "00"^^xsd:hexBinary .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"hi\x00\xff\xff\xff\xff\xff\x07", {"s": "hi", "n": 7})

pp("term-bytes", "A bytes field may be terminated",
   "The terminator search is byte-aligned for bytes.",
   ["req-pm-terminators-1", "req-pm-terminators-4"], ["terminators"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:b ex:n ) .
   ex:b a bddo:Field ; bddo:dataType bddo:bytes ; bddo:terminator "FFFF"^^xsd:hexBinary .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\xff\x02\xff\xff\x03", {"b": b"\x01\xff\x02", "n": 3})

pp("term-utf16-code-unit-aligned", "A UTF-16 terminator only matches on a code-unit boundary",
   "In 41 00 00 42 00 00 the pair 00 00 at offset 1 straddles two code units and does not count; the terminator is the pair at offset 4.",
   ["req-pm-terminators-3"], ["terminators"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:n ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf16le ; bddo:terminator "0000"^^xsd:hexBinary .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   bytes.fromhex("410000420000") + b"\x01", {"s": "A䈀", "n": 1})

pp("term-not-found", "A missing terminator is a bounds error",
   "No NUL occurs before the end of the stream.",
   ["req-pm-terminators-6", "req-pm-errors-3"], ["terminators", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:terminator "00"^^xsd:hexBinary .
   """,
   b"abc", error="Bounds")

pp("term-bounded-by-enclosing-region", "The terminator search is bounded by the enclosing region",
   "A NUL right after a 3-byte struct region lies outside the search bound.",
   ["req-pm-errors-3"], ["terminators", "algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 3 ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:terminator "00"^^xsd:hexBinary .
   """,
   b"abc\x00", error="Bounds")

pp("term-empty", "An empty terminator is a description error",
   "bddo:terminator with no bytes cannot end anything.",
   ["req-pm-terminators-2", "req-pm-errors-8", "req-pm-errors-9"], ["terminators", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:terminator ""^^xsd:hexBinary .
   """,
   b"abc\x00", error="Description")

# ----------------------------------------------------------------- sizes and regions

pp("size-from-field", "bddo:sizeFromField sizes a field from a bound sibling",
   "The length prefix gives the byte count of the data that follows.",
   ["req-pm-size-resolution-9"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ex:tail ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x03abc\x09", {"n": 3, "data": b"abc", "tail": 9})

pp("size-from-parent-field", "bddo:sizeFromField falls back to the parent struct",
   "A field of a nested struct is sized by a field of the struct that contains it.",
   ["req-pm-size-resolution-9"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:sub ex:tail ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:sub a bddo:Field ; bddo:dataType ex:Sub .
   ex:Sub a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x02\xaa\xbb\xcc", {"n": 2, "sub": {"data": b"\xaa\xbb"}, "tail": 0xCC})

pp("size-from-expression", "bddo:sizeFromExpression sizes a field by a HEL expression",
   "The size is twice the count field.",
   ["req-pm-size-resolution-9"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "n * 2" .
   """,
   b"\x02abcd", {"n": 2, "data": b"abcd"})

pp("size-from-text-number", "A size read from a number written as text is accepted by its value",
   "An asciiInteger length \"03\" sizes the following field to three bytes.",
   ["req-pm-size-resolution-2"], ["size-resolution", "text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 2 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:n .
   """,
   b"03xyz", {"n": 3, "data": b"xyz"})

pp("size-to-end-of-stream", "bddo:sizeToEndOfStream takes the rest of the stream",
   "Without an enclosing region the field runs to the end of the input.",
   ["req-pm-size-resolution-9"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:rest ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:rest a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
   """,
   b"\x01xyz", {"a": 1, "rest": b"xyz"})

pp("size-to-end-of-region", "bddo:sizeToEndOfStream inside a region stops at the region end",
   "In a 4-byte struct region the field takes the three bytes left in the region, not the rest of the stream.",
   ["req-pm-size-resolution-9", "req-pm-parsestruct-5"], ["size-resolution", "algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:tail ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 4 ; bddo:hasField ( ex:a ex:rest ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:rest a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01xyz\x09", {"box": {"a": 1, "rest": b"xyz"}, "tail": 9})

pp("size-precedence", "Of several region forms the first in the normative order decides",
   "A field declaring both bddo:size 2 and bddo:sizeFromField (3) takes two bytes: bddo:size precedes bddo:sizeFromField.",
   ["req-pm-size-resolution-9", "req-pm-size-resolution-4"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ex:tail ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ; bddo:sizeFromField ex:n .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x03ab\x07", {"n": 3, "data": b"ab", "tail": 7})

pp("size-ignored-on-fixed-width", "A size on a fixed-width type does not change its width",
   "A uint16 declaring bddo:size 4 still occupies two bytes.",
   ["req-pm-size-resolution-7"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:size 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x00\x05\x06\x07", {"a": 5, "b": 6})

pp("size-region-skips-remainder", "After a sized struct field the cursor moves to the region end",
   "A 3-byte region holding a one-byte struct: the two bytes after it are skipped.",
   ["req-pm-parsestruct-8", "req-pm-size-resolution-9"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:small ex:tail ) .
   ex:small a bddo:Field ; bddo:dataType ex:Small ; bddo:size 3 .
   ex:Small a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\xee\xee\x02", {"small": {"a": 1}, "tail": 2})

pp("size-region-past-enclosing", "A region extending past the enclosing region is a bounds error",
   "A 5-byte field inside a 3-byte struct region.",
   ["req-pm-errors-3"], ["size-resolution", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 3 ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 5 .
   """,
   b"abcdefgh", error="Bounds")

pp("size-negative", "A negative size is a bounds error",
   "n - 5 with n = 2.",
   ["req-pm-errors-3"], ["size-resolution", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:data ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "n - 5" .
   """,
   b"\x02abcdef", error="Bounds")

pp("size-past-end-of-stream", "A declared region past the end of the stream is a bounds error",
   "Ten bytes are declared and four remain.",
   ["req-pm-errors-3"], ["size-resolution", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 10 .
   """,
   b"abcd", error="Bounds")

pp("size-no-extent", "A variable-length field with no extent is a description error",
   "A bytes field with neither a region nor a terminator.",
   ["req-pm-errors-8"], ["size-resolution", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes .
   """,
   b"abcd", error="Description")

pp("struct-size-literal", "A literal struct size skips the struct's trailing padding",
   "A 4-byte struct holding one byte: the next field reads after the padding.",
   ["req-pm-parsestruct-8", "req-pm-struct-size-3", "req-pm-parsestruct-5"], ["struct-size"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:rec ex:b ) .
   ex:rec a bddo:Field ; bddo:dataType ex:Rec .
   ex:Rec a bddo:Struct ; bddo:size 4 ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\xee\xee\xee\x02", {"rec": {"a": 1}, "b": 2})

pp("struct-size-from-own-field", "A struct sized by its own first field bounds the rest of it",
   "A box whose length (counted from the box's first byte) is its first field: the payload runs to the box end, not the stream end.",
   ["req-pm-struct-size-3", "req-pm-parsestruct-5"], ["struct-size", "size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:tail ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:sizeFromField ex:len ; bddo:hasField ( ex:len ex:payload ) .
   ex:len a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:payload a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x04\xaa\xbb\xcc\x09", {"box": {"len": 4, "payload": b"\xaa\xbb\xcc"}, "tail": 9})

pp("struct-size-never-bound", "A struct size naming a field that is never bound is a forward reference",
   "The size names a field skipped by bddo:isPresentIf; the struct must not be left unbounded.",
   ["req-pm-struct-size-1", "req-pm-struct-size-2", "req-pm-errors-6"], ["struct-size"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:sizeFromExpression "late + 2" ; bddo:hasField ( ex:a ex:late ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:late a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "a == 0" .
   """,
   b"\x01\x02\x03\x04", error="Expression")

pp("struct-size-cursor-beyond", "A struct size smaller than what was already read is a bounds error",
   "The size (1) is known only after three bytes have been read.",
   ["req-pm-errors-3"], ["struct-size"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:sizeFromField ex:len ; bddo:hasField ( ex:a ex:len ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:len a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x00\x00\x01\x00", error="Bounds")

pp("bounds-nested-region", "A nested read crossing its struct's region is a bounds error",
   "A uint32 inside a 2-byte struct region, though the stream has more bytes.",
   ["req-pm-errors-3"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:size 2 .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint32 .
   """,
   b"\x00\x00\x00\x01\x00\x00", error="Bounds")

# ----------------------------------------------------------------- repetition

pp("rep-count", "Repeat counts: literal, from a field and from an expression",
   "bddo:repeatCount, bddo:repeatCountFromField and bddo:repeatCountFromExpression each give the element count; a zero count is an empty array.",
   ["req-pm-parsefield-8", "req-pm-size-resolution-10"], ["algorithm", "size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:lit ex:byField ex:byExpr ex:none ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:lit a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 3 .
   ex:byField a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:repeatCountFromField ex:n .
   ex:byExpr a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromExpression "n - 1" .
   ex:none a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromExpression "n - 2" .
   """,
   b"\x02" + b"\x01\x02\x03" + b"\x00\x0a\x00\x0b" + b"\x07",
   {"n": 2, "lit": [1, 2, 3], "byField": [10, 11], "byExpr": [7], "none": []})

pp("rep-struct-elements", "A repeated struct field is an array of structs",
   "Two entries of a two-field struct.",
   ["req-pm-parsefield-8"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:entries ) .
   ex:entries a bddo:Field ; bddo:dataType ex:Entry ; bddo:repeatCount 2 .
   ex:Entry a bddo:Struct ; bddo:hasField ( ex:tag ex:val ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:val a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x0a\x02\x0b", {"entries": [{"tag": 1, "val": 10}, {"tag": 2, "val": 11}]})

pp("rep-until-scalar", "repeatUntil over scalars binds self to the value just read",
   "Elements are read until the condition holds; the element that satisfies it is included.",
   ["req-hel-name-binding-1"], ["algorithm", "repeat-until-bindings", "hel/index.html#name-binding"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:vals ex:tail ) .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatUntil "self == 0" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x05\x06\x00\x09", {"vals": [5, 6, 0], "tail": 9})

pp("rep-until-struct", "repeatUntil over structs reads the element just parsed by bare name",
   "PNG-style chunks until type == 'IEND': instance and self are the chunk just read.",
   ["req-hel-name-binding-1"], ["repeat-until-bindings", "hel/index.html#name-binding"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:chunks ex:tail ) .
   ex:chunks a bddo:Field ; bddo:dataType ex:Chunk ; bddo:repeatUntil "type == 'IEND'" .
   ex:Chunk a bddo:Struct ; bddo:hasField ( ex:type ex:len ) .
   ex:type a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:len a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"IHDR\x0dIDAT\x02IEND\x00\x09",
   {"chunks": [{"type": "IHDR", "len": 13}, {"type": "IDAT", "len": 2}, {"type": "IEND", "len": 0}], "tail": 9})

pp("rep-until-struct-parent", "Over struct elements, parent is the struct holding the sequence",
   "parent.stop reads the containing struct's field, not the element's.",
   ["req-hel-name-binding-1"], ["repeat-until-bindings"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:stop ex:items ) .
   ex:stop a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatUntil "v == parent.stop" .
   ex:Item a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x03\x01\x02\x03\x04", {"stop": 3, "items": [{"v": 1}, {"v": 2}, {"v": 3}]})

pp("rep-until-scalar-parent", "Over scalar elements, parent is the containing struct's parent",
   "For scalar elements instance stays the containing struct, so parent.stop reads the grandparent's field.",
   ["req-hel-name-binding-1"], ["repeat-until-bindings"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:stop ex:sub ) .
   ex:stop a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:sub a bddo:Field ; bddo:dataType ex:Sub .
   ex:Sub a bddo:Struct ; bddo:hasField ( ex:stop2 ex:vals ) .
   ex:stop2 a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatUntil "self == parent.stop" .
   """,
   b"\x04\x02\x01\x02\x03\x04\x05", {"stop": 4, "sub": {"stop2": 2, "vals": [1, 2, 3, 4]}})

pp("rep-until-eof-region", "repeatUntil eof() stops at the end of the innermost region",
   "Inside a 4-byte struct region eof() is true at the region end, not at the end of the stream.",
   ["req-pm-size-resolution-10"], ["stream-metadata", "repeat-until-bindings"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:tail ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 4 ; bddo:hasField ( ex:items ) .
   ex:items a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatUntil "eof()" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x02\x03\x04\x05", {"box": {"items": [1, 2, 3, 4]}, "tail": 5})

pp("rep-until-region-exhausted", "A repeatUntil sequence stops when its declared region is exhausted",
   "A 3-byte region whose condition never holds yields three elements and no error.",
   ["req-pm-size-resolution-10"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:vals ex:tail ) .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:size 3 ; bddo:repeatUntil "self == 255" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x02\x03\x04", {"vals": [1, 2, 3], "tail": 4})

pp("rep-until-negative-size", "A negative declared size makes a repeatUntil sequence empty",
   "For a repeatUntil sequence only, a negative size (n - 4 with n = 2) is an empty sequence, not an error.",
   ["req-pm-size-resolution-10"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:vals ex:tail ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:sizeFromExpression "n - 4" ; bddo:repeatUntil "self == 0" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x02\x07", {"n": 2, "vals": [], "tail": 7})

pp("rep-zero-byte-element", "An element that consumes no bytes and does not end the sequence is a bounds error",
   "A struct of one derived field repeated until false would loop forever.",
   ["req-pm-errors-3"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:items ) .
   ex:items a bddo:Field ; bddo:dataType ex:Empty ; bddo:repeatUntil "false" .
   ex:Empty a bddo:Struct ; bddo:hasField ( ex:d ) .
   ex:d a bddo:Field ; bddo:valueFromExpression "1" .
   """,
   b"\x01\x02", error="Bounds")

pp("rep-until-on-text-container", "repeatUntil on a text container is a description error",
   "A text container consumes its whole region, so no element could follow the first.",
   ["req-pm-errors-8"], ["algorithm", "text-containers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr ; bddo:repeatUntil "true" .
   ex:Hdr a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:hasField ( ex:Hdr.a ) .
   ex:Hdr.a a bddo:Field ; bddo:dataType bddo:string ; bddo:key "a" .
   """,
   b"a=1\n", error="Description")

# ----------------------------------------------------------------- offsets

pp("offset-literal-restores-cursor", "An offset-addressed field does not advance sibling parsing",
   "The field at offset 3 is read, then the cursor returns to where it was.",
   ["req-pm-parsefield-7"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:far ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:far a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 3 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x02\xee\x09", {"a": 1, "far": 9, "b": 2})

pp("offset-from-field-and-expression", "Offsets from a field and from an expression",
   "bddo:atOffsetFromField and bddo:atOffsetFromExpression address from the stream start by default.",
   ["req-pm-parsefield-7"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:ptr ex:val ex:next ) .
   ex:ptr a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:val a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:atOffsetFromField ex:ptr .
   ex:next a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffsetFromExpression "ptr + 2" .
   """,
   b"\x02\xee\x12\x34\x56", {"ptr": 2, "val": 0x1234, "next": 0x56})

pp("offset-stream-end", "bddo:streamEnd counts backward from the end of the stream",
   "Offset 1 from the stream end is the last byte.",
   ["req-pm-parsefield-7"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:last ex:first ) .
   ex:last a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 1 ; bddo:offsetBase bddo:streamEnd .
   ex:first a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x02\x03", {"last": 3, "first": 1})

pp("offset-current-position", "bddo:currentPosition moves the cursor and does not restore it",
   "Offset 1 from the current position skips one byte, and the next field continues after the read.",
   ["req-pm-parsefield-7"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 1 ; bddo:offsetBase bddo:currentPosition .
   ex:c a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\xee\x02\x03", {"a": 1, "b": 2, "c": 3})

pp("offset-outside-region", "An offset outside the innermost region is a bounds error",
   "Offset 3 addressed from inside a 2-byte struct region.",
   ["req-pm-errors-3"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 2 ; bddo:hasField ( ex:a ex:far ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:far a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 3 .
   """,
   b"\x01\x02\x03\x04", error="Bounds")

pp("offset-stream-scope", "bddo:streamScope lets one offset read leave the region",
   "The same read with seekScope streamScope resolves against the whole stream, and the region bound is back in force afterwards.",
   ["req-pm-parsefield-7"], ["algorithm", "stream-metadata"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:tail ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:size 2 ; bddo:hasField ( ex:a ex:far ex:rest ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:far a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 3 ; bddo:seekScope bddo:streamScope .
   ex:rest a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x01\x02\x03\x04", {"box": {"a": 1, "far": 4, "rest": b"\x02"}, "tail": 3})

pp("offset-past-end", "An offset past the end of the stream is a bounds error",
   "Offset 10 in a 4-byte stream.",
   ["req-pm-errors-3"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:far ) .
   ex:far a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 10 .
   """,
   b"\x01\x02\x03\x04", error="Bounds")

# ----------------------------------------------------------------- sync

pp("sync-marker", "bddo:syncOnMarker advances the cursor past the marker",
   "The bytes before the next FF D8 are skipped and the marker is consumed: the struct's first field follows it.",
   ["req-pm-parsestruct-2", "req-pm-parsestruct-3"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:seg ex:tail ) .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   ex:Seg a bddo:Struct ; bddo:syncOnMarker "FFD8"^^xsd:hexBinary ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x00\x11\xff\xd8\x07\x09", {"seg": {"v": 7}, "tail": 9})

pp("sync-missing", "A missing sync marker is a sync error",
   "No FF D8 occurs in the stream.",
   ["req-pm-errors-1", "req-pm-errors-2"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:seg ) .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   ex:Seg a bddo:Struct ; bddo:syncOnMarker "FFD8"^^xsd:hexBinary ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x00\x11\xff\x07", error="Sync")

SEG = """
   ex:Seg a bddo:Struct ; bddo:syncOnMarker "FFD8"^^xsd:hexBinary ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   """

pp("sync-marker-at-cursor", "A sync marker that starts at the cursor is found there",
   "The stream starts with FF D8: the search starts at the cursor, so the marker is consumed at offset 0 and v is 7.",
   ["req-pm-parsestruct-3"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:seg ex:tail ) .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """ + SEG,
   b"\xff\xd8\x07\x09", {"seg": {"v": 7}, "tail": 9})

pp("sync-bounded-by-region", "The sync search stops at the end of the enclosing region",
   "Seg is parsed inside a three-byte region that holds no FF D8; the marker after the region is not found, a sync error.",
   ["req-pm-parsestruct-3", "req-pm-errors-2"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:after ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:size 3 .
   ex:after a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:seg ) .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   """ + SEG,
   b"\x00\x11\x22\xff\xd8\x07", error="Sync")

pp("sync-marker-straddles-bound", "A sync marker that runs past the enclosing region's end is not found",
   "The four-byte region ends between FF and D8: the occurrence does not lie entirely in the region, a sync error.",
   ["req-pm-parsestruct-3", "req-pm-errors-2"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:box ex:after ) .
   ex:box a bddo:Field ; bddo:dataType ex:Box ; bddo:size 4 .
   ex:after a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:seg ) .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   """ + SEG,
   b"\x00\x11\x22\xff\xd8\x07", error="Sync")

pp("sync-struct-size-after-marker", "A synced struct's own size is measured from after the marker",
   "Seg declares size 2 and syncs on FF D8 at offset 1: its region is [3, 5), so v is AA, BB is padding, and tail is CC.",
   ["req-pm-parsestruct-3", "req-pm-struct-size-3", "req-pm-parsestruct-8"], ["algorithm", "struct-size"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:seg ex:tail ) .
   ex:seg a bddo:Field ; bddo:dataType ex:Seg .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Seg a bddo:Struct ; bddo:syncOnMarker "FFD8"^^xsd:hexBinary ; bddo:size 2 ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x00\xff\xd8\xaa\xbb\xcc", {"seg": {"v": 0xAA}, "tail": 0xCC})

# ----------------------------------------------------------------- presence, derived values, constraints

pp("present-if", "bddo:isPresentIf false skips the field and binds it to Null",
   "The optional field consumes nothing when its flag is clear; the canonical form writes it as null.",
   ["req-hel-undefined-names-5"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:flags ex:opt ex:opt2 ex:tail ) .
   ex:flags a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:opt a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:isPresentIf "flags & 1 == 1" .
   ex:opt2 a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "flags & 2 == 2" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x02\x05\x07", {"flags": 2, "opt": None, "opt2": 5, "tail": 7})

pp("derived-value", "A derived field consumes no bytes",
   "bddo:valueFromExpression binds w * h and the next field reads the next byte.",
   ["req-pm-parsefield-5"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:h ex:area ex:tail ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:h a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:area a bddo:Field ; bddo:valueFromExpression "w * h" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x02\x03\x09", {"w": 2, "h": 3, "area": 6, "tail": 9})

pp("derived-null", "A derived field whose value is Null is unbound",
   "The expression reads an absent optional field.",
   ["req-hel-undefined-names-5"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:opt ex:copy ) .
   ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "false" .
   ex:copy a bddo:Field ; bddo:valueFromExpression "opt" .
   """,
   b"", {"opt": None, "copy": None})

pp("valid-if", "bddo:validIf false is a validation error",
   "self <= 10 fails for 11.",
   ["req-pm-parsefield-17", "req-pm-errors-4"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:validIf "self <= 10" .
   """,
   b"\x0b", error="Validation")

pp("valid-if-holds", "bddo:validIf true accepts the value",
   "self <= 10 holds for 10.",
   ["req-pm-parsefield-17"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:validIf "self <= 10" .
   """,
   b"\x0a", {"v": 10})

pp("valid-if-evaluation-failure", "A validIf that fails to evaluate is a Type / HEL error",
   "Adding a string to an integer is a type error, which reports a defect of the description, not of the data.",
   ["req-pm-errors-6", "req-hel-coercion-1"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:validIf "self + 'a' == 1" .
   """,
   b"\x01", error="Expression")

pp("root-key", "bddo:rootKeyFromField binds a record's value in the root context",
   "Records name their values; a later field reads root.WDTH, and an unbound data-named key reads Null (first occurrence wins).",
   ["req-pm-parsefield-18"], ["algorithm", "hel/index.html#key-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:records ex:width ) .
   ex:records a bddo:Field ; bddo:dataType ex:Record ; bddo:repeatCount 3 .
   ex:Record a bddo:Struct ; bddo:hasField ( ex:name ex:value ) .
   ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:value a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:rootKeyFromField ex:name .
   ex:width a bddo:Field ; bddo:valueFromExpression "root.WDTH" .
   """,
   b"HGHT\x02WDTH\x05WDTH\x09",
   {"records": [{"name": "HGHT", "value": 2}, {"name": "WDTH", "value": 5}, {"name": "WDTH", "value": 9}],
    "width": 5})

pp("root-key-unbound", "A root key the data never binds reads Null",
   "The records name only HGHT, so root.WDTH, a key only data could bind, is Null rather than an undefined name.",
   ["req-pm-parsefield-18", "req-hel-undefined-names-5"], ["algorithm", "hel/index.html#key-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:records ex:width ) .
   ex:records a bddo:Field ; bddo:dataType ex:Record ; bddo:repeatCount 1 .
   ex:Record a bddo:Struct ; bddo:hasField ( ex:name ex:value ) .
   ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:value a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:rootKeyFromField ex:name .
   ex:width a bddo:Field ; bddo:valueFromExpression "root.WDTH" .
   """,
   b"HGHT\x02", {"records": [{"name": "HGHT", "value": 2}], "width": None})

pp("rep-count-negative", "A negative repeat count is a bounds error",
   "n - 3 with n = 1: a repeat count must be a non-negative integer, and a negative one is a bounds error, as a negative size is.",
   ["req-pm-size-resolution-3", "req-pm-errors-3"], ["size-resolution"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:vals ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromExpression "n - 3" .
   """,
   b"\x01\x05", error="Bounds")


# ----------------------------------------------------------------- decoding text: well-formed or a validation error

DECODE = ["req-pm-text-decoding-1", "req-pm-text-decoding-2", "req-pm-errors-4"]


def one_string(encoding, size):
    return f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:size {size} ; bddo:encoding bddo:{encoding} .
   """


pp("str-utf8-malformed", "A string field that is not well-formed UTF-8 is a validation error",
   "C3 28 is a lead byte followed by a byte that cannot continue it; the value is never U+FFFD followed by '('.",
   DECODE, ["text-decoding"], one_string("utf8", 2), b"\xc3\x28", error="Validation")

pp("str-utf8-overlong", "An overlong UTF-8 sequence is not well-formed",
   "C0 AF would spell '/' in two bytes; RFC 3629 forbids overlong forms.",
   DECODE, ["text-decoding"], one_string("utf8", 2), b"\xc0\xaf", error="Validation")

pp("str-utf8-encoded-surrogate", "A UTF-8-encoded surrogate is not well-formed",
   "ED A0 80 encodes U+D800, which is not a Unicode scalar value.",
   DECODE, ["text-decoding"], one_string("utf8", 3), b"\xed\xa0\x80", error="Validation")

pp("str-utf16-lone-surrogate", "A lone UTF-16 surrogate is a validation error",
   "41 00 00 D8: 'A' and then a high surrogate with no low surrogate after it.",
   DECODE, ["text-decoding"], one_string("utf16le", 4), b"A\x00\x00\xd8",
   error="Validation")

pp("str-utf16-odd-length", "A UTF-16 string of an odd number of bytes is a validation error",
   "Three bytes hold one code unit and half of another.",
   DECODE, ["text-decoding"], one_string("utf16be", 3), b"\x00A\x00",
   error="Validation")

pp("str-ascii-high-byte", "A byte above 7F in a US-ASCII string is a validation error",
   "41 80: the second byte is not ASCII, so the value is neither 'A' followed by U+FFFD nor 'A' followed by U+0080.",
   DECODE, ["text-decoding"], one_string("ascii", 2), b"A\x80", error="Validation")

pp("str-latin1-every-byte", "Every byte is well-formed ISO-8859-1",
   "80 and FF decode to U+0080 and U+00FF.",
   ["req-pm-text-decoding-1"], ["text-decoding"], one_string("latin1", 2), b"\x80\xff", {"s": "\u0080\u00ff"})

pp("textnum-non-ascii-digit", "A number written as text uses ASCII digits only",
   "The UTF-8 field holds ARABIC-INDIC DIGIT ONE and TWO, well-formed text that is not a number: a validation error, "
   "not 12.",
   ["req-pm-text-decoding-3", "req-pm-text-numbers-3", "req-pm-errors-4"], ["text-decoding", "text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ) .
   ex:n a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 4 ; bddo:encoding bddo:utf8 .
   """,
   "\u0661\u0662".encode("utf-8"), error="Validation")
