"""Physical Parser cases for the rules settled in round 4 of the language text, and the regressions of round 3.

Fixed values by literal kind (Processing Model, Fixed value), conflicting forms (Conflicting forms), bddo:streamEnd
inside a decoded sub-stream and inside a bounded region, HEL result types, string literals holding control characters,
expression depth, the geometry extension group, tree documents with a document type declaration, the capability
statement a processor must make, and a resource limit that must not be dodged.
"""
import struct

from cases_hel import derived, hel, one
from cases_physical import CASES, pp
from suite import Case

FIXED = "processing#fixed-values"
CONFLICT = "processing#conflicting-forms"
DESCRIPTION = "req-pm-errors-8"

# ----------------------------------------------------------------- fixed values

pp("fixed-string-on-bytes", "A string fixed value on a bytes field is compared as UTF-8, never read as hex digits or a number",
   "\"CAFE\" is the four bytes 43 41 46 45 and \"1234\" the four bytes 31 32 33 34; neither is the hex CA FE nor the "
   "integer 1234.",
   ["req-pm-parsefield-12"], [FIXED, "algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "CAFE" .
   ex:b a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "1234" .
   """,
   b"CAFE1234", {"a": b"CAFE", "b": b"1234"})

pp("fixed-string-on-bytes-not-hex", "The bytes CA FE 00 00 do not match the string fixed value \"CAFE\"",
   "The string denotes its UTF-8 encoding, 43 41 46 45; the field's four bytes CA FE 00 00 differ: a validation error.",
   ["req-pm-parsefield-12", "req-pm-errors-4"], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "CAFE" .
   """,
   b"\xca\xfe\x00\x00", error="Validation")

pp("fixed-string-trim-null", "A string fixed value is compared with the value after bddo:trimNull",
   "A six-byte NUL-padded ASCII field holding 41 42 00 00 00 00 has the value AB, which matches \"AB\".",
   ["req-pm-parsefield-12", "req-pm-parsefield-11"], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:size 6 ; bddo:trimNull true ;
       bddo:hasFixedValue "AB" .
   """,
   b"AB\x00\x00\x00\x00", {"s": "AB"})

pp("fixed-string-on-utf16", "A string fixed value on a UTF-16 field is compared by code points",
   "The field's bytes 41 00 42 00 decode as UTF-16LE to \"AB\", which the fixed value is; its UTF-8 encoding is irrelevant.",
   ["req-pm-parsefield-12"], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:c ) .
   ex:c a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf16le ; bddo:size 4 ; bddo:hasFixedValue "AB" .
   """,
   b"A\x00B\x00", {"c": "AB"})

F32_TENTH = struct.unpack(">f", struct.pack(">f", 0.1))[0]

pp("fixed-float32-rounded", "A float fixed value on a float32 field is compared after rounding to float32",
   "\"0.1\"^^xsd:double differs from the float32 nearest 0.1 as a binary64 value, but rounded to the field's format it is "
   "that float32, so the field matches.",
   ["req-pm-parsefield-13"], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:float32 ; bddo:hasFixedValue "0.1"^^xsd:double .
   """,
   struct.pack(">f", 0.1), {"v": F32_TENTH})

pp("fixed-float32-mismatch", "A float32 field whose value differs from the rounded fixed value is a validation error",
   "0.25 is read where 0.5 is fixed.",
   ["req-pm-parsefield-13", "req-pm-errors-4"], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:float32 ; bddo:hasFixedValue "0.5"^^xsd:double .
   """,
   struct.pack(">f", 0.25), error="Validation")

pp("fixed-string-on-numeric", "A string fixed value on a numeric field is a description error",
   "\"12\" is characters; an integer field is compared with numbers or with its hexBinary encoding only.",
   ["req-pm-parsefield-14", DESCRIPTION], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:hasFixedValue "12" .
   """,
   b"\x0c", error="Description")

pp("fixed-number-on-bytes", "A numeric fixed value on a bytes field is a description error",
   "An integer does not say which bytes it would be.",
   ["req-pm-parsefield-14", DESCRIPTION], [FIXED],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 ; bddo:hasFixedValue 7 .
   """,
   b"\x07", error="Description")

# ----------------------------------------------------------------- conflicting forms

for cid, title, intent, rid, body in [
    ("count-and-until", "A repeat count together with a repeat-until condition is a description error",
     "bddo:repeatCount 2 and bddo:repeatUntil on one field: no order between them is defined.", "req-pm-parsefield-21",
     'ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 ; bddo:repeatUntil "self == 0" .'),
    ("two-count-forms", "Two repeat-count forms on one field are a description error",
     "bddo:repeatCount and bddo:repeatCountFromField.", "req-pm-parsefield-21",
     'ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 ; bddo:repeatCountFromField ex:n .'),
    ("two-offset-forms", "Two offset forms on one field are a description error",
     "bddo:atOffset and bddo:atOffsetFromExpression.", "req-pm-parsefield-22",
     'ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 1 ; bddo:atOffsetFromExpression "0" .'),
    ("two-data-types", "Two bddo:dataType values on one field are a description error",
     "bddo:dataType is functional; uint8 and uint16 cannot both be the field's type.", "req-pm-parsefield-24",
     'ex:a a bddo:Field ; bddo:dataType bddo:uint8 , bddo:uint16 .'),
    ("two-literal-sizes", "Two bddo:size values on one field are a description error",
     "The precedence of the four size forms does not order two values of one form.", "req-pm-parsefield-24",
     'ex:a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 , 2 .'),
]:
    pp("conflict-" + cid, title, intent, [rid, "req-pm-parsefield-20", DESCRIPTION], [CONFLICT],
       "ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:a ) .\nex:n a bddo:Field ; bddo:dataType bddo:uint8 .\n" + body + "\n",
       b"\x02\x00\x00\x00\x00", error="Description")

# ----------------------------------------------------------------- streamEnd: the current stream, not a region

pp("offset-stream-end-substream", "Inside a decoded sub-stream, streamEnd counts back from the sub-stream's length",
   "Inner is re-parsed from a four-byte block decoded by menc:Store; offset 1 from its stream end is the block's last byte "
   "(04), not the input's (09).",
   ["req-pm-parsefield-7", "req-pm-emission-1"], ["algorithm", "stream-metadata"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:pad ex:block ex:tail ) .
   ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   ex:block a bddo:Field ; bddo:dataType ex:Inner ; bddo:size 4 ; hexplain:isEncodedWith menc:Store .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Inner a bddo:Struct ; bddo:hasField ( ex:a ex:last ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:last a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 1 ; bddo:offsetBase bddo:streamEnd .
   """,
   b"\x00\x00\x00" + b"\x01\x02\x03\x04" + b"\x09",
   {"pad": b"\x00\x00\x00", "block": {"a": 1, "last": 4}, "tail": 9})

pp("offset-stream-end-in-region", "Inside a bounded region, streamEnd still counts back from the stream's length",
   "Hdr is a two-byte region of a four-byte input. A bounded region is not a stream, so offset 1 from the stream end is "
   "the input's last byte (0D); the stream-scoped read may leave the region, and restores the cursor, so a reads 0A.",
   ["req-pm-parsefield-7", "req-pm-parsestruct-5"], ["algorithm", "stream-metadata"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ex:rest ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .
   ex:rest a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 .
   ex:Hdr a bddo:Struct ; bddo:size 2 ; bddo:hasField ( ex:last ex:a ) .
   ex:last a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 1 ; bddo:offsetBase bddo:streamEnd ;
       bddo:seekScope bddo:streamScope .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"\x0a\x0b\x0c\x0d", {"hdr": {"last": 13, "a": 10}, "rest": b"\x0c\x0d"})

pp("offset-stream-end-nested-region", "streamEnd inside a region nested in the stream counts back from the stream's end",
   "Inner is a four-byte region after h; offset 2 from the end of the eight-byte input is byte 6 (0x15), read with stream "
   "scope because it lies past Inner's region.",
   ["req-pm-parsefield-7"], ["algorithm", "stream-metadata"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:h ex:inner ) .
   ex:h a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:Inner a bddo:Struct ; bddo:size 4 ; bddo:hasField ( ex:p ) .
   ex:p a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 2 ; bddo:offsetBase bddo:streamEnd ;
       bddo:seekScope bddo:streamScope .
   """,
   b"\x00\x0a\x0b\x0c\x0d\x14\x15\x16", {"h": 0, "inner": {"p": 21}})

# ----------------------------------------------------------------- HEL in a parse context

INTEGER_RESULT = ["req-hel-conformance-6", "req-hel-name-binding-1", "req-pm-errors-6"]

hel("float-result-count", "A repeat count expression that yields a Float is an error, even an integral one",
    "repeatCountFromExpression \"2.0\" yields a Float where the name-binding table requires an Integer.",
    INTEGER_RESULT, ["conformance", "name-binding"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
    ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromExpression "2.0" .
    """,
    b"\x01\x02", error="Expression")

hel("float-result-size", "A size expression that yields a Float is an error, even an integral one",
    "sizeFromExpression \"4 / 2.0\" is 2.0, a Float, not the size 2.",
    INTEGER_RESULT, ["conformance", "name-binding"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
    ex:a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "4 / 2.0" .
    """,
    b"\x01\x02", error="Expression")

hel("string-control-characters", "A string literal may hold a control character literally",
    "The literal holds U+0001 and U+001F written as themselves (the Turtle escapes \\u0001 and \\u001F put the characters "
    "into the expression); SChar admits every character but ' and \\.",
    ["req-hel-conformance-2", "req-hel-formal-grammar-1"], ["syntax"],
    one("'a\\u0001b\\u001Fc'"), b"", {"d": "a\u0001b\u001fc"})

hel("flat-chain-depth", "A left-associative chain of one operator counts as one n-ary node for the depth limit",
    "Eight 1s joined by + under maxHelDepth 3: the chain is one node of depth 2, not a tree seven deep.",
    ["req-hel-conformance-10", "req-hel-conformance-8"], ["expression-depth", "conformance"],
    one(" + ".join(["1"] * 8)), b"", {"d": 8}, manifest={"limits": {"maxHelDepth": 3}})

hel("flat-conjunction-depth", "A chain of and counts as one n-ary node for the depth limit",
    "Six comparisons joined by and under maxHelDepth 3: each comparison is depth 2, the chain one more.",
    ["req-hel-conformance-10", "req-hel-conformance-8"], ["expression-depth", "conformance"],
    one(" and ".join(["1 == 1"] * 6)), b"", {"d": True}, manifest={"limits": {"maxHelDepth": 3}})

hel("reserved-word-key", "A field whose local name is a reserved word cannot be read by name",
    "root.self is not an accessor: after a dot a key is a Name, and self is a reserved word, so the expression is a syntax "
    "error.",
    ["req-hel-key-resolution-3", "req-hel-conformance-2", "req-pm-errors-16"], ["key-resolution", "syntax"],
    derived(["ex:self a bddo:Field ; bddo:dataType bddo:uint8 ."], {"d": "root.self"}), b"\x01", error="Expression")

hel("duplicate-local-name", "Two fields of one struct sharing a local name are a description error",
    "ex:a and <https://example.org/other#a> both have the local name a, so the name a could read either.",
    ["req-hel-key-resolution-1", "req-hel-key-resolution-5", DESCRIPTION], ["key-resolution"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:a <https://example.org/other#a> ) .
    ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
    <https://example.org/other#a> a bddo:Field ; bddo:dataType bddo:uint8 .
    """,
    b"\x01\x02", error="Description")

hel("unknown-function", "A call to a function in neither the core set nor any group is an error when the description is loaded",
    "frobnicate() names no HEL 1.0 function. An expression carries no version marker, and a later 1.x version may only add "
    "functions without changing what a 1.0 expression yields, so the name is an error now, not a deferred Null.",
    ["req-hel-versioning-1", "req-hel-versioning-2", "req-hel-extension-groups-1", "req-pm-errors-6"],
    ["versioning", "extension-groups"],
    one("frobnicate(1)"), b"", error="Expression")

VECTOR_CONTEXT = ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 .", "ex:b a bddo:Field ; bddo:dataType bddo:uint8 .",
                  "ex:big a bddo:Field ; bddo:dataType bddo:uint32 .", "ex:f a bddo:Field ; bddo:dataType bddo:float64 .",
                  "ex:neg a bddo:Field ; bddo:dataType bddo:int8 ."]

hel("vector-rows", "Rows of hel-vectors.tsv evaluate to the values the rows give",
    "The rows named integer addition, integer division truncates toward zero, negative integer division truncates toward "
    "zero, float division does not truncate, bitwise not, right shift is arithmetic, integer and float compare exactly and "
    "ternary is right-associative, over their context {a: 7, b: 2, big: 4294967295, f: 2.5, neg: -3} parsed from bytes.",
    ["req-hel-conformance-9", "req-hel-conformance-4"], ["conformance", "numeric-semantics"],
    derived(VECTOR_CONTEXT, {"r1": "a + b", "r2": "a / b", "r3": "neg / b", "r4": "f / b", "r5": "~a", "r6": "neg >> 1",
                             "r7": "9007199254740993 > 9007199254740992.0", "r8": "false ? 1 : true ? 2 : 3"}),
    b"\x07\x02" + struct.pack(">I", 4294967295) + struct.pack(">d", 2.5) + b"\xfd",
    {"a": 7, "b": 2, "big": 4294967295, "f": 2.5, "neg": -3,
     "r1": 9, "r2": 3, "r3": -1, "r4": 1.25, "r5": -8, "r6": -2, "r7": True, "r8": 2})

GEOMETRY = {"features": {"requires": ["hel-ext-geometry"]}}


def coords(*names, n=4):
    return [f"ex:{name} a bddo:Field ; bddo:dataType bddo:int8 ; bddo:repeatCount {n} ." for name in names]


hel("geometry-orientation", "ringOrientation: counter-clockwise 1, clockwise -1, degenerate 0",
    "The unit square traversed (0,0) (4,0) (4,4) (0,4) is counter-clockwise; the same square the other way round is "
    "clockwise; four collinear points have zero signed area.",
    ["req-hel-conformance-4"], ["ext-geometry"],
    derived(coords("ax", "ay", "bx", "by", "cx", "cy"),
            {"ccw": "ringOrientation(ax, ay)", "cw": "ringOrientation(bx, by)", "flat": "ringOrientation(cx, cy)"}),
    bytes([0, 4, 4, 0, 0, 0, 4, 4, 0, 0, 4, 4, 0, 4, 4, 0, 0, 1, 2, 3, 0, 1, 2, 3]),
    {"ax": [0, 4, 4, 0], "ay": [0, 0, 4, 4], "bx": [0, 0, 4, 4], "by": [0, 4, 4, 0], "cx": [0, 1, 2, 3], "cy": [0, 1, 2, 3],
     "ccw": 1, "cw": -1, "flat": 0}, manifest=GEOMETRY)

hel("geometry-self-intersecting", "isSelfIntersecting: a bow-tie crosses itself, a square does not",
    "(0,0) (4,4) (4,0) (0,4) has two non-adjacent edges crossing properly at (2,2); the square has none.",
    ["req-hel-conformance-4"], ["ext-geometry"],
    derived(coords("ax", "ay", "bx", "by"),
            {"bowtie": "isSelfIntersecting(ax, ay)", "square": "isSelfIntersecting(bx, by)"}),
    bytes([0, 4, 4, 0, 0, 4, 0, 4, 0, 4, 4, 0, 0, 0, 4, 4]),
    {"ax": [0, 4, 4, 0], "ay": [0, 4, 0, 4], "bx": [0, 4, 4, 0], "by": [0, 0, 4, 4], "bowtie": True, "square": False},
    manifest=GEOMETRY)

hel("geometry-length-mismatch", "Coordinate arrays of different lengths are an error",
    "Three x coordinates and two y coordinates.",
    ["req-hel-conformance-4", "req-pm-errors-6"], ["ext-geometry"],
    derived(coords("xs", n=3) + coords("ys", n=2), {"d": "ringOrientation(xs, ys)"}),
    bytes([0, 4, 4, 0, 0]), error="Expression", manifest=GEOMETRY)

# ----------------------------------------------------------------- tree documents with a document type declaration

TREES = {"features": {"requires": ["tree-documents"]}}
XML_A = """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:xml ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/r/a" .
"""

pp("tree-xml-external-entity", "A reference to an external XML entity is a validation error; its text is never fetched",
   "The internal subset declares ext as a SYSTEM entity naming a local file; whether or not the processor reads the "
   "declaration, &ext; is refused, not replaced with the file's content.",
   ["req-pm-tree-documents-1", "req-pm-tree-documents-2", "req-pm-errors-4"], ["tree-documents"], XML_A,
   b'<?xml version="1.0"?>\n<!DOCTYPE r [ <!ENTITY ext SYSTEM "file:///etc/hostname"> ]>\n<r><a>&ext;</a></r>',
   error="Validation", manifest=TREES)

pp("tree-xml-external-dtd-not-fetched", "An external DTD is never fetched, and a document that needs nothing from it parses",
   "The declaration names a DTD at an address nothing listens on; a processor that fetched it would fail, one that "
   "declines the declaration reads a as 1.",
   ["req-pm-tree-documents-1"], ["tree-documents"], XML_A,
   b'<?xml version="1.0"?>\n<!DOCTYPE r SYSTEM "http://127.0.0.1:9/never.dtd">\n<r><a>1</a></r>',
   {"a": "1"}, manifest=TREES)

# ----------------------------------------------------------------- resource limits and claims

pp("limit-no-cheaper-interpretation", "A limit reached while reading a sequence is a ResourceLimit error, not a skipped sequence",
   "200 one-byte elements under maxVisitedNodes 50: the processor may not finish by treating the sequence as an opaque "
   "byte run.",
   ["req-pm-resource-limits-4", "req-pm-resource-limits-1", "req-pm-errors-12"], ["resource-limits"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:items ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:items a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromField ex:n .
   """,
   bytes([200]) + bytes(200), error="ResourceLimit", manifest={"limits": {"maxVisitedNodes": 50}})

CASES.append(Case(
    id="pp-claims-statement", cls="physical-parser",
    title="A processor states the classes and the optional features it claims",
    intent="The runner asks the implementation for its claims statement (a JSON object listing its conformance classes and "
           "its optional features by feature token). Every conforming processor makes one; its classes and features come "
           "from the closed lists of the Processing Model.",
    requirements=["req-pm-conformance-classes-5"],
    sections=["processing#conformance-classes", "processing#optional-features"],
    root=None, manifest={"check": "claims"},
    claims={"required": ["classes", "optionalFeatures"],
            "classes": ["Physical Parser", "Semantic Emitter", "Bundle Processor", "HDL Compiler", "Conformance Evaluator"],
            "optionalFeatures": ["tree-documents", "grouped-headers", "nested-profiles", "chunked-cell-access",
                                 "chunk-order-other", "hel-ext-text", "hel-ext-temporal", "hel-ext-quantifier",
                                 "hel-ext-geometry", "hel-ext-register", "codecs-beyond-minimum"],
            "mustInclude": {"classes": ["Physical Parser"]}}))
