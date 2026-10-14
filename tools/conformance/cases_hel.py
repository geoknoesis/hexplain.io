"""Physical Parser cases for HEL evaluated in a real parse context.

These are the cases the HEL vector format (validation/test/hel-vectors.tsv) cannot express, because
a vector carries only a flat data context: undefined names after the first path step, forward
references (which need a declaration order and a parse position), Bytes values and the
Bytes-vs-String rules, uint64 values above 2^63-1, sizeof of parsed nodes, stream metadata and eof(),
and the asset root outside a Bundle Processor. Values are bound to derived fields
(bddo:valueFromExpression), so the expected tree shows each expression's result.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from typing import Any

from cases_physical import pp

HEL = "hel/index.html#"


def hel(
    id: Any,
    title: str,
    intent: Any,
    reqs: Any,
    sections: Any,
    description: str,
    data: Any,
    expected: Any = None,
    error: Any = None,
    **kw: Any,
) -> None:
    pp(
        "hel-" + id,
        title,
        intent,
        reqs,
        [HEL + s if "#" not in s and s not in PM_SECTIONS else s for s in sections],
        description,
        data,
        expected,
        error,
        **kw,
    )


PM_SECTIONS = {"context", "stream-metadata", "errors", "algorithm", "multi-part-assets", "struct-size"}
TYPE_ERROR = "req-pm-errors-6"
SYNTAX = ["req-pm-errors-16", "req-hel-conformance-1", "req-hel-conformance-2"]


def derived(fields: list[str], exprs: dict[str, str], preamble: str = "") -> str:
    """A Root with the given physical fields (Turtle lines) then one derived field per expression."""
    names = [line.split()[0][3:] for line in fields] + list(exprs)
    lines = [f"ex:Root a bddo:Struct ; bddo:hasField ( {' '.join('ex:' + n for n in names)} ) ."]
    lines += fields
    lines += [f'ex:{name} a bddo:Field ; bddo:valueFromExpression "{expr}" .' for name, expr in exprs.items()]
    return "\n".join(lines) + ("\n" + preamble if preamble else "") + "\n"


def one(expr: str, fields: Sequence[str] = (), preamble: str = "") -> str:
    return derived(list(fields), {"d": expr}, preamble)


# ----------------------------------------------------------------- undefined names, forward references, Null

hel(
    "undefined-name",
    "An undefined name is an error, never Null",
    "A misspelt bare name in a derived value raises an undefined-name error.",
    ["req-hel-undefined-names-1", "req-hel-undefined-names-2", "req-hel-undefined-names-3", TYPE_ERROR],
    ["undefined-names"],
    one("lenght + 1", ["ex:length a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x01",
    error="Expression",
)

hel(
    "undefined-name-after-first-step",
    "A key after the first step must name a field of the addressed struct",
    "hdr.typo names no field of Hdr: an undefined-name error at the second step, not Null.",
    ["req-hel-key-resolution-2", "req-hel-undefined-names-2", TYPE_ERROR],
    ["key-resolution", "undefined-names"],
    derived(
        ["ex:hdr a bddo:Field ; bddo:dataType ex:Hdr ."],
        {"d": "hdr.typo"},
        "ex:Hdr a bddo:Struct ; bddo:hasField ( ex:n ) .\nex:n a bddo:Field ; bddo:dataType bddo:uint8 .",
    ),
    b"\x01",
    error="Expression",
)

hel(
    "undefined-name-in-presence",
    "An undefined name in a presence condition is an error, not a false condition",
    'isPresentIf "flgs == 1" does not silently skip the field.',
    ["req-hel-undefined-names-3", TYPE_ERROR],
    ["undefined-names"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:flags ex:opt ) .
    ex:flags a bddo:Field ; bddo:dataType bddo:uint8 .
    ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "flgs == 1" .
    """,
    b"\x01\x02",
    error="Expression",
)

hel(
    "self-where-undefined",
    "self outside a property that defines it is an undefined-name error",
    "A presence condition has no value under test.",
    ["req-hel-undefined-names-2", TYPE_ERROR],
    ["reserved-roots", "undefined-names"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:opt ) .
    ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "self == 1" .
    """,
    b"\x01",
    error="Expression",
)

hel(
    "forward-reference-size",
    "A size naming a later field is a forward-reference error",
    "data is sized by n, which is declared after it.",
    ["req-hel-undefined-names-4", "req-pm-context-1", TYPE_ERROR],
    ["undefined-names", "context"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:data ex:n ) .
    ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "n" .
    ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
    """,
    b"\x01\x02\x03",
    error="Expression",
)

hel(
    "forward-reference-derived",
    "A derived value naming a later field is a forward-reference error",
    "The derived field precedes the field it reads.",
    ["req-hel-undefined-names-4", "req-pm-context-1", TYPE_ERROR],
    ["undefined-names", "context"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:d ex:later ) .
    ex:d a bddo:Field ; bddo:valueFromExpression "later * 2" .
    ex:later a bddo:Field ; bddo:dataType bddo:uint8 .
    """,
    b"\x01",
    error="Expression",
)

hel(
    "forward-reference-parent",
    "A parent field not yet parsed is a forward reference",
    "A nested struct reads parent.after, which the parent declares after the nested field.",
    ["req-hel-undefined-names-4", "req-pm-context-1", TYPE_ERROR],
    ["undefined-names", "context"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:sub ex:after ) .
    ex:sub a bddo:Field ; bddo:dataType ex:Sub .
    ex:Sub a bddo:Struct ; bddo:hasField ( ex:d ) .
    ex:d a bddo:Field ; bddo:valueFromExpression "parent.after" .
    ex:after a bddo:Field ; bddo:dataType bddo:uint8 .
    """,
    b"\x01",
    error="Expression",
)

hel(
    "absent-optional-null",
    "An absent optional field reads as Null, and every comparison but == with Null is false",
    "opt == 1 and opt != 1 are both false; opt == opt is true (Null == Null); parent fields already parsed "
    "are visible.",
    ["req-hel-undefined-names-5", "req-hel-conformance-4", "req-pm-parsefield-4"],
    ["undefined-names", "coercion"],
    derived(
        ['ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf \\"false\\" .'],
        {"eq": "opt == 1", "ne": "opt != 1", "same": "opt == opt"},
    ).replace('\\"', '"'),
    b"",
    {"opt": None, "eq": False, "ne": False, "same": True},
)

hel(
    "null-arithmetic",
    "Arithmetic on Null is an error",
    "An absent optional field plus one.",
    ["req-hel-coercion-1", TYPE_ERROR],
    ["coercion"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:opt ex:d ) .
    ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "false" .
    ex:d a bddo:Field ; bddo:valueFromExpression "opt + 1" .
    """,
    b"",
    error="Expression",
)

# ----------------------------------------------------------------- Bytes values

BYTES_FIELDS = [
    "ex:tag a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .",
    "ex:tag2 a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .",
    "ex:acc a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 .",
    "ex:lat a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 ; bddo:encoding bddo:latin1 .",
    "ex:bad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 .",
    "ex:pad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .",
]

hel(
    "bytes-vs-string",
    "Bytes compared with a String decode in the field's encoding",
    "IHDR bytes equal 'IHDR'; C3 A9 decodes as UTF-8 by default and E9 as the field's ISO-8859-1; a "
    "malformed byte equals no "
    "String, not even U+FFFD; "
    "two Bytes values compare byte for byte; len() of Bytes counts bytes; trim() and concat() accept Bytes "
    "as a String.",
    ["req-hel-core-functions-2", "req-hel-conformance-4", "req-pm-text-decoding-1"],
    ["coercion", "core-functions"],
    derived(
        BYTES_FIELDS,
        {
            "eq": "tag == 'IHDR'",
            "ne": "tag != 'IEND'",
            "utf8": "acc == '\\\\u00e9'",
            "latin": "lat == '\\\\u00e9'",
            "malformed": "bad == '\\\\uFFFD'",
            "malformedNe": "bad != '\\\\uFFFD'",
            "same": "tag == tag2",
            "n": "len(acc)",
            "trimmed": "trim(pad)",
            "joined": "concat(tag, '!')",
        },
    ),
    b"IHDR" + b"IHDR" + "é".encode() + b"\xe9" + b"\xff" + b" ab ",
    {
        "tag": b"IHDR",
        "tag2": b"IHDR",
        "acc": "é".encode(),
        "lat": b"\xe9",
        "bad": b"\xff",
        "pad": b" ab ",
        "eq": True,
        "ne": True,
        "utf8": True,
        "latin": True,
        "malformed": False,
        "malformedNe": True,
        "same": True,
        "n": 2,
        "trimmed": "ab",
        "joined": "IHDR!",
    },
)

hel(
    "bytes-malformed-argument",
    "Bytes that are not well-formed are an error where a String is required",
    "trim() of the single byte FF, which is not UTF-8.",
    ["req-pm-text-decoding-1", "req-hel-conformance-4", TYPE_ERROR],
    ["core-functions", "coercion"],
    one("trim(bad)", ["ex:bad a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 1 ."]),
    b"\xff",
    error="Expression",
)

hel(
    "bytes-ordering",
    "Ordering Bytes against a String is an error",
    "Only == and != compare Bytes with a String.",
    ["req-hel-conformance-4", TYPE_ERROR],
    ["coercion"],
    one("tag < 'z'", ["ex:tag a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ."]),
    b"IHDR",
    error="Expression",
)

# ----------------------------------------------------------------- uint64 and numeric semantics

hel(
    "uint64-exact",
    "A uint64 above 2^63-1 keeps its exact value for comparisons and Float arithmetic",
    "The largest uint64 is greater than the largest Integer literal and than 1.0e19, and times 1.0 is the Float 2^64.",
    ["req-hel-numeric-semantics-5", "req-hel-coercion-2"],
    ["numeric-semantics", "coercion"],
    derived(
        ["ex:big a bddo:Field ; bddo:dataType bddo:uint64 ."],
        {"gt": "big > 9223372036854775807", "gtf": "big > 1.0e19", "f": "big * 1.0"},
    ),
    b"\xff" * 8,
    {"big": 2**64 - 1, "gt": True, "gtf": True, "f": 1.8446744073709552e19},
)

hel(
    "uint64-integer-arithmetic",
    "A uint64 above 2^63-1 in Integer arithmetic is an out-of-range error",
    "big + 1 cannot be an Integer.",
    ["req-hel-numeric-semantics-5", "req-hel-conformance-7", TYPE_ERROR],
    ["numeric-semantics"],
    one("big + 1", ["ex:big a bddo:Field ; bddo:dataType bddo:uint64 ."]),
    b"\xff" * 8,
    error="Expression",
)

hel(
    "exact-mixed-comparison",
    "Integer vs Float compares exact values without rounding the Integer",
    "2^53 + 1 as a uint64 is not equal to the Float 2^53, which it would be if the Integer were rounded first.",
    ["req-hel-coercion-2"],
    ["coercion"],
    derived(
        ["ex:v a bddo:Field ; bddo:dataType bddo:uint64 ."],
        {"eq": "v == 9007199254740992.0", "gt": "v > 9007199254740992.0"},
    ),
    struct.pack(">Q", 2**53 + 1),
    {"v": 2**53 + 1, "eq": False, "gt": True},
)

hel(
    "integer-overflow",
    "Integer overflow is an error, never a wrap-around",
    "2 times the largest Integer.",
    ["req-hel-numeric-semantics-1", "req-hel-conformance-7", TYPE_ERROR],
    ["numeric-semantics"],
    one("a * 9223372036854775807", ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x02",
    error="Expression",
)

hel(
    "division-by-zero",
    "Division by zero is an error",
    "An Integer divided by a zero read from the data.",
    ["req-hel-numeric-semantics-2", "req-hel-conformance-7", TYPE_ERROR],
    ["numeric-semantics"],
    one("a / z", ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 .", "ex:z a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x05\x00",
    error="Expression",
)

hel(
    "float-division-by-zero",
    "Float division by zero is an error, not Infinity",
    "1.0 divided by a zero Float.",
    ["req-hel-numeric-semantics-2", TYPE_ERROR],
    ["numeric-semantics"],
    one("1.0 / (z * 1.0)", ["ex:z a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x00",
    error="Expression",
)

hel(
    "integer-division",
    "Integer division truncates toward zero and % takes the dividend's sign",
    "-3 / 2 is -1, -3 % 2 is -1, 5 / 2.0 is 2.5 and -4 >> 1 is -2 (arithmetic shift).",
    ["req-hel-conformance-4"],
    ["numeric-semantics"],
    derived(
        ["ex:n a bddo:Field ; bddo:dataType bddo:int8 .", "ex:m a bddo:Field ; bddo:dataType bddo:int8 ."],
        {"q": "n / 2", "r": "n % 2", "f": "5 / 2.0", "s": "m >> 1"},
    ),
    b"\xfd\xfc",
    {"n": -3, "m": -4, "q": -1, "r": -1, "f": 2.5, "s": -2},
)

hel(
    "shift-count-range",
    "A shift count outside 0..63 is an error",
    "1 << 64 is not reduced modulo 64.",
    ["req-hel-numeric-semantics-3", TYPE_ERROR],
    ["numeric-semantics"],
    one("a << 64", ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x01",
    error="Expression",
)

hel(
    "shift-overflow",
    "A left shift beyond the signed 64-bit range is an error",
    "1 << 63 overflows.",
    ["req-hel-numeric-semantics-4", TYPE_ERROR],
    ["numeric-semantics"],
    one("a << 63", ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x01",
    error="Expression",
)

hel(
    "literal-range",
    "An Integer literal above 2^63-1 is a syntax error",
    "9223372036854775808 does not wrap around.",
    ["req-hel-formal-grammar-2", TYPE_ERROR] + SYNTAX,
    ["syntax"],
    one("9223372036854775808"),
    b"",
    error="Expression",
)

hel(
    "literal-extremes",
    "The largest literal, and the minimum Integer written as an expression",
    "9223372036854775807 and -9223372036854775807 - 1 are exact.",
    ["req-hel-formal-grammar-2"],
    ["syntax", "numeric-semantics"],
    derived([], {"max": "9223372036854775807", "min": "-9223372036854775807 - 1"}),
    b"",
    {"max": 2**63 - 1, "min": -(2**63)},
)

# ----------------------------------------------------------------- arrays and indexes

ITEMS = ["ex:items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatCount 2 ."]
ITEM = "ex:Item a bddo:Struct ; bddo:hasField ( ex:v ) .\nex:v a bddo:Field ; bddo:dataType bddo:uint8 ."

hel(
    "index-out-of-range",
    "A subscript past the end of an array is an error",
    "items[2] of a two-element array.",
    ["req-hel-key-resolution-4", "req-hel-numeric-semantics-6", TYPE_ERROR],
    ["key-resolution", "numeric-semantics"],
    derived(ITEMS, {"d": "items[2].v"}, ITEM),
    b"\x01\x02",
    error="Expression",
)

hel(
    "index-float",
    "A Float subscript is an error",
    "items[1.0] is not an Integer index.",
    ["req-hel-numeric-semantics-6", TYPE_ERROR],
    ["numeric-semantics"],
    derived(ITEMS, {"d": "items[1.0].v"}, ITEM),
    b"\x01\x02",
    error="Expression",
)

hel(
    "index-negative",
    "A negative subscript is an error",
    "items[-1] does not count from the end.",
    ["req-hel-numeric-semantics-6", TYPE_ERROR],
    ["numeric-semantics"],
    derived(ITEMS, {"d": "items[-1].v"}, ITEM),
    b"\x01\x02",
    error="Expression",
)

hel(
    "quantifiers",
    "all and any evaluate their predicate per element",
    "Over struct elements bare names read the element; over scalars self is the element; an empty array "
    "makes all true and any false.",
    ["req-hel-conformance-4"],
    ["ext-quantifiers"],
    derived(
        ITEMS
        + [
            "ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 .",
            "ex:none a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 0 .",
        ],
        {
            "allPos": "all(items, v > 0)",
            "anyBig": "any(items, v > 5)",
            "scalars": "all(vals, self < 10)",
            "emptyAll": "all(none, false)",
            "emptyAny": "any(none, true)",
        },
        ITEM,
    ),
    b"\x01\x02\x03\x04",
    {
        "items": [{"v": 1}, {"v": 2}],
        "vals": [3, 4],
        "none": [],
        "allPos": True,
        "anyBig": False,
        "scalars": True,
        "emptyAll": True,
        "emptyAny": False,
    },
    manifest={"features": {"requires": ["hel-ext-quantifier"]}},
)

hel(
    "quantifier-not-array",
    "A quantifier's first argument must be an array",
    "all(5, true).",
    ["req-hel-ext-quantifiers-1", TYPE_ERROR],
    ["ext-quantifiers"],
    one("all(5, true)"),
    b"",
    error="Expression",
    manifest={"features": {"requires": ["hel-ext-quantifier"]}},
)

hel(
    "quantifier-non-boolean",
    "A quantifier predicate must yield a Boolean",
    "all(items, v) yields Integers.",
    ["req-hel-ext-quantifiers-2", TYPE_ERROR],
    ["ext-quantifiers"],
    derived(ITEMS, {"d": "all(items, v)"}, ITEM),
    b"\x01\x02",
    error="Expression",
    manifest={"features": {"requires": ["hel-ext-quantifier"]}},
)

# ----------------------------------------------------------------- operators

hel(
    "and-evaluates-both-operands",
    "and does not short-circuit",
    "false and (1 / z == 0) raises the division by zero even though false decides the result.",
    ["req-hel-operator-precedence-4", "req-hel-numeric-semantics-2", TYPE_ERROR],
    ["evaluation"],
    one("false and (1 / z == 0)", ["ex:z a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x00",
    error="Expression",
)

hel(
    "ternary-guard",
    "The ternary evaluates only the selected branch",
    "A guard written with the ternary does not evaluate the out-of-range subscript; the ternary is right-associative.",
    ["req-hel-operator-precedence-1", "req-hel-operator-precedence-2"],
    ["evaluation"],
    derived(
        ITEMS,
        {
            "guard": "len(items) > 5 ? items[5].v == 1 : false",
            "nested": "len(items) == 1 ? 10 : len(items) == 2 ? 20 : 30",
        },
        ITEM,
    ),
    b"\x01\x02",
    {"items": [{"v": 1}, {"v": 2}], "guard": False, "nested": 20},
)

hel(
    "logical-operand-types",
    "The operands of and are type-checked even when the left decides",
    "false and 1 is an error.",
    ["req-hel-operator-precedence-3", TYPE_ERROR],
    ["evaluation"],
    one("false and 1"),
    b"",
    error="Expression",
)

hel(
    "precedence-and-comparisons",
    "Bitwise operators bind tighter than comparisons; strings order by code point; NaN compares false",
    "flags & 1 == 1 tests the masked bit; 'B' < 'a'; NaN == NaN is false and NaN != NaN true.",
    ["req-hel-conformance-4"],
    ["evaluation", "coercion"],
    derived(
        ["ex:flags a bddo:Field ; bddo:dataType bddo:uint8 ."],
        {
            "bit": "flags & 1 == 1",
            "order": "'B' < 'a'",
            "nan": "(1e308 * 10.0) - (1e308 * 10.0)",
            "nanEq": "nan == nan",
            "nanNe": "nan != nan",
            "nanLt": "nan < 1",
        },
    ),
    b"\x03",
    {"flags": 3, "bit": True, "order": True, "nan": float("nan"), "nanEq": False, "nanNe": True, "nanLt": False},
)

hel(
    "incompatible-comparison",
    "Comparing an Integer with a String is an error",
    "a == 'x'.",
    ["req-hel-conformance-4", TYPE_ERROR],
    ["coercion"],
    one("a == 'x'", ["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."]),
    b"\x01",
    error="Expression",
)

hel(
    "comparison-chain",
    "Comparisons do not chain",
    "1 < 2 < 3 is a syntax error.",
    [TYPE_ERROR] + SYNTAX,
    ["syntax"],
    one("1 < 2 < 3"),
    b"",
    error="Expression",
)

hel(
    "non-ascii-identifier",
    "A non-ASCII letter outside a string literal is a syntax error",
    "café is neither a name nor a number.",
    [TYPE_ERROR] + SYNTAX,
    ["syntax"],
    one("café == 1"),
    b"",
    error="Expression",
)

hel(
    "string-escapes",
    "String escapes: \\xHH, \\uHHHH and \\n",
    "'\\x41\\u00e9\\n' is A, e-acute and a line feed.",
    ["req-hel-formal-grammar-1"],
    ["syntax"],
    one("'\\\\x41\\\\u00e9\\\\n'"),
    b"",
    {"d": "Aé\n"},
)

hel(
    "unknown-escape",
    "An unknown escape is a syntax error",
    "'\\q' is not an escape.",
    ["req-hel-formal-grammar-1", TYPE_ERROR] + SYNTAX,
    ["syntax"],
    one("'\\\\q'"),
    b"",
    error="Expression",
)

# ----------------------------------------------------------------- core functions

hel(
    "core-functions",
    "The core function library",
    "sizeof of a terminated string includes its terminator; len and count; trim, substringBefore/After, "
    "substring, concat and toNumber.",
    ["req-hel-core-functions-1", "req-hel-versioning-2", "req-hel-conformance-4"],
    ["core-functions", "tonumber"],
    derived(
        [
            "ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf8 ; bddo:terminator "
            '\\"00\\"^^xsd:hexBinary .',
            "ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 3 .",
        ],
        {
            "sz": "sizeof(name)",
            "ln": "len(vals)",
            "cn": "count(name)",
            "tr": "trim('  x ')",
            "sb": "substringBefore('a,b', ',')",
            "sa": "substringAfter('a,b', ',')",
            "none": "substringBefore('ab', ',')",
            "ss": "substring('hello', 1, 3)",
            "cc": "concat('<', name, '>')",
            "ti": "toNumber('10')",
            "tf": "toNumber('-1.5e1')",
        },
    ).replace('\\"', '"'),
    b"abc\x00\x01\x02\x03",
    {
        "name": "abc",
        "vals": [1, 2, 3],
        "sz": 4,
        "ln": 3,
        "cn": 3,
        "tr": "x",
        "sb": "a",
        "sa": "b",
        "none": "",
        "ss": "ell",
        "cc": "<abc>",
        "ti": 10,
        "tf": -15.0,
    },
)

hel(
    "tonumber-float-lexeme",
    "toNumber of a lexeme with a fraction is a Float",
    "'10.0' is a Float, '10' an Integer.",
    ["req-hel-core-functions-3", "req-hel-tonumber-1"],
    ["tonumber"],
    derived([], {"i": "toNumber('10')", "f": "toNumber('10.0')"}),
    b"",
    {"i": 10, "f": 10.0},
)

hel(
    "tonumber-whitespace",
    "toNumber does not trim",
    "' 1' does not match NumericText.",
    ["req-hel-core-functions-3", "req-hel-tonumber-1", TYPE_ERROR],
    ["tonumber"],
    one("toNumber(' 1')"),
    b"",
    error="Expression",
)

hel(
    "tonumber-hex",
    "toNumber rejects hexadecimal forms",
    "'0x10' does not match NumericText.",
    ["req-hel-tonumber-1", TYPE_ERROR],
    ["tonumber"],
    one("toNumber('0x10')"),
    b"",
    error="Expression",
)

hel(
    "substring-range",
    "substring past the end of its string is a range error",
    "substring('abc', 2, 5).",
    ["req-hel-conformance-7", TYPE_ERROR],
    ["core-functions"],
    one("substring('abc', 2, 5)"),
    b"",
    error="Expression",
)

hel(
    "concat-number",
    "concat does not convert numbers",
    "concat('a', 1) is an argument type error.",
    ["req-hel-core-functions-2", TYPE_ERROR],
    ["core-functions"],
    one("concat('a', 1)"),
    b"",
    error="Expression",
)

hel(
    "function-arity",
    "A core function called with the wrong number of arguments is an error",
    "len() takes exactly one argument.",
    ["req-hel-conformance-4", TYPE_ERROR],
    ["core-functions"],
    one("len(vals, vals)", ["ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 1 ."]),
    b"\x01",
    error="Expression",
)

hel(
    "sizeof-nodes",
    "sizeof measures any parsed node: a struct, an array element, a field",
    "A 3-byte header, the second 2-byte entry, and a 2-byte field reached through root.",
    ["req-hel-core-functions-1", "req-pm-parsestruct-4"],
    ["core-functions", "struct-size"],
    derived(
        [
            "ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .",
            "ex:entries a bddo:Field ; bddo:dataType ex:Entry ; bddo:repeatCount 2 .",
        ],
        {"hdrSize": "sizeof(hdr)", "entrySize": "sizeof(entries[1])", "viaRoot": "sizeof(root.hdr.b)"},
        "ex:Hdr a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .\n"
        "ex:a a bddo:Field ; bddo:dataType bddo:uint8 .\nex:b a bddo:Field ; bddo:dataType bddo:uint16 .\n"
        "ex:Entry a bddo:Struct ; bddo:hasField ( ex:t ex:u ) .\n"
        "ex:t a bddo:Field ; bddo:dataType bddo:uint8 .\nex:u a bddo:Field ; bddo:dataType bddo:uint8 .",
    ),
    b"\x01\x00\x02" + b"\x01\x02\x03\x04",
    {
        "hdr": {"a": 1, "b": 2},
        "entries": [{"t": 1, "u": 2}, {"t": 3, "u": 4}],
        "hdrSize": 3,
        "entrySize": 2,
        "viaRoot": 2,
    },
)

hel(
    "sizeof-derived",
    "sizeof of a derived field is an error",
    "A derived field has no byte extent.",
    ["req-hel-conformance-7", TYPE_ERROR],
    ["core-functions", "struct-size"],
    derived(["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ."], {"twice": "a * 2", "d": "sizeof(twice)"}),
    b"\x01",
    error="Expression",
)

# ----------------------------------------------------------------- stream metadata

hel(
    "stream-metadata",
    "stream.position, stream.remaining, stream.length and eof() inside a region",
    "In a 4-byte struct region starting at offset 1, after one byte: position 2 (from the stream start), remaining 3 "
    "(to the region end), length 6 (the whole stream, not narrowed) and eof() false.",
    ["req-hel-conformance-4"],
    ["stream-metadata", "reserved-roots"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:box ex:tail ) .
    ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
    ex:box a bddo:Field ; bddo:dataType ex:Box .
    ex:Box a bddo:Struct ; bddo:size 4 ; bddo:hasField ( ex:b ex:pos ex:rem ex:len ex:end ) .
    ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
    ex:pos a bddo:Field ; bddo:valueFromExpression "stream.position" .
    ex:rem a bddo:Field ; bddo:valueFromExpression "stream.remaining" .
    ex:len a bddo:Field ; bddo:valueFromExpression "stream.length" .
    ex:end a bddo:Field ; bddo:valueFromExpression "eof()" .
    ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
    """,
    b"\x01\x02\x00\x00\x00\x09",
    {"a": 1, "box": {"b": 2, "pos": 2, "rem": 3, "len": 6, "end": False}, "tail": 9},
)

hel(
    "stream-position-bits",
    "During bit fields a partly consumed byte counts as consumed",
    "After a 3-bit field, stream.position is 1.",
    ["req-hel-conformance-4"],
    ["stream-metadata"],
    derived(["ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:bitLength 3 ."], {"pos": "stream.position"}),
    b"\xe0",
    {"a": 7, "pos": 1},
)

hel(
    "stream-unknown-key",
    "A stream key other than length, position and remaining is an undefined-name error",
    "stream.size.",
    ["req-hel-undefined-names-2", TYPE_ERROR],
    ["reserved-roots"],
    one("stream.size"),
    b"",
    error="Expression",
)

# ----------------------------------------------------------------- extension groups used in parsing

hel(
    "text-group",
    "The text group: matches is anchored at both ends",
    "matches('IHDR', 'IH') is false; matches('IHDR', 'I.*') true; startsWith and the clamping substr.",
    ["req-hel-conformance-4"],
    ["ext-text"],
    derived(
        [],
        {
            "partial": "matches('IHDR', 'IH')",
            "whole": "matches('IHDR', 'I.*')",
            "starts": "startsWith('IHDR', 'IH')",
            "clamped": "substr('abc', 1, 10)",
        },
    ),
    b"",
    {"partial": False, "whole": True, "starts": True, "clamped": "bc"},
    manifest={"features": {"requires": ["hel-ext-text"]}},
)

hel(
    "text-pattern-not-string",
    "A matches pattern must be a String",
    "matches('a', 1).",
    ["req-hel-ext-text-1", TYPE_ERROR],
    ["ext-text"],
    one("matches('a', 1)"),
    b"",
    error="Expression",
    manifest={"features": {"requires": ["hel-ext-text"]}},
)

hel(
    "temporal-group",
    "datetime is strict: an impossible date is Null, never rolled over",
    "2024-02-29 12:00:00 is 1709208000 seconds after the epoch; 2024-02-30 is not a date.",
    ["req-hel-ext-temporal-2"],
    ["ext-temporal"],
    derived(
        [],
        {
            "leap": "datetime('2024-02-29 12:00:00', 'yyyy-MM-dd HH:mm:ss')",
            "bad": "datetime('2024-02-30 12:00:00', 'yyyy-MM-dd HH:mm:ss')",
        },
    ),
    b"",
    {"leap": 1709208000, "bad": None},
    manifest={"features": {"requires": ["hel-ext-temporal"]}},
)

hel(
    "temporal-date-only",
    "datetime of a date with no time of day is Null",
    "The pattern yyyy-MM-dd reads the text in full but supplies no time, so the text is not a full date and "
    "time and the "
    "result is Null, not midnight.",
    ["req-hel-ext-temporal-1"],
    ["ext-temporal"],
    derived([], {"d": "datetime('2024-02-29', 'yyyy-MM-dd')"}),
    b"",
    {"d": None},
    manifest={"features": {"requires": ["hel-ext-temporal"]}},
)

# ----------------------------------------------------------------- the asset root outside a bundle

hel(
    "asset-outside-bundle",
    "asset in a description parsed on its own is an error, never Null",
    "A single part parsed outside an asset cannot read asset.Header.n.",
    ["req-hel-conformance-3", "req-pm-multi-part-assets-3", "req-hel-core-functions-4", "req-hdl-layout-1", TYPE_ERROR],
    ["reserved-roots", "multi-part-assets"],
    one("asset.Header.n"),
    b"",
    error="Expression",
)

hel(
    "part-extension-outside-bundle",
    "partExtension() outside an asset is an error",
    "partExtension(asset.Grid) with no asset.",
    ["req-hel-conformance-3", "req-pm-multi-part-assets-3", "req-hel-core-functions-4", TYPE_ERROR],
    ["core-functions", "multi-part-assets"],
    one("partExtension(asset.Grid)"),
    b"",
    error="Expression",
)

hel(
    "presence-result-type",
    "A presence condition must yield a Boolean",
    'bddo:isPresentIf "1" yields an Integer where the name-binding table requires a Boolean.',
    ["req-hel-conformance-6", "req-hel-name-binding-1", TYPE_ERROR],
    ["name-binding", "conformance"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
    ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "1" .
    """,
    b"\x01",
    error="Expression",
)

hel(
    "size-result-type",
    "A size expression must yield an Integer",
    "bddo:sizeFromExpression yielding a String is a Type / HEL error.",
    ["req-hel-conformance-6", "req-pm-size-resolution-2", TYPE_ERROR],
    ["name-binding", "conformance"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
    ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "'two'" .
    """,
    b"\x01\x02",
    error="Expression",
)

hel(
    "extension-group-unclaimed",
    "A function of an extension group the processor does not implement is refused at load",
    "matches() belongs to the text group; a processor without it rejects the description when it is loaded, "
    "not at the first evaluation.",
    ["req-hel-extension-groups-1", "req-hel-conformance-5", "req-pm-errors-10"],
    ["extension-groups", "conformance"],
    one("matches('a', 'a')"),
    b"",
    error="Unsupported",
    manifest={"claims": {"withdraw": ["hel-ext-text"]}},
)


# ----------------------------------------------------------------- the math group, Float remainder

N5 = ["ex:n a bddo:Field ; bddo:dataType bddo:int8 ."]

hel(
    "math-rounding",
    "floor, ceil, trunc and round yield Integers; round ties away from zero",
    "floor(-2.5) is -3 and ceil(-2.5) is -2; trunc(-2.7) is -2; round(2.5) is 3, round(-2.5) is -3 and "
    "round(-0.4) is 0; "
    "an Integer argument is returned unchanged, and ceil(n / 2.0) is the Integer 3 for n = 5.",
    ["req-hel-math-1", "req-hel-core-functions-1"],
    ["math"],
    derived(
        N5,
        {
            "fl": "floor(2.7)",
            "fn": "floor(-2.5)",
            "ce": "ceil(2.1)",
            "cn": "ceil(-2.5)",
            "tn": "trunc(-2.7)",
            "ru": "round(2.5)",
            "rn": "round(-2.5)",
            "rz": "round(-0.4)",
            "same": "floor(n)",
            "half": "ceil(n / 2.0)",
        },
    ),
    b"\x05",
    {"n": 5, "fl": 2, "fn": -3, "ce": 3, "cn": -2, "tn": -2, "ru": 3, "rn": -3, "rz": 0, "same": 5, "half": 3},
)

hel(
    "math-rounding-nan",
    "Rounding NaN is an argument error",
    "Infinity - Infinity is NaN, which has no integer value.",
    ["req-hel-math-1", TYPE_ERROR],
    ["math"],
    one("floor((1e308 * 10.0) - (1e308 * 10.0))"),
    b"",
    error="Expression",
)

hel(
    "math-rounding-infinity",
    "Rounding an infinite Float is an argument error",
    "1e308 * 10.0 overflows to Infinity.",
    ["req-hel-math-1", TYPE_ERROR],
    ["math"],
    one("ceil(1e308 * 10.0)"),
    b"",
    error="Expression",
)

hel(
    "math-rounding-overflow",
    "A rounded value outside the signed 64-bit range is an overflow error",
    "1e19 is above 2^63-1.",
    ["req-hel-math-1", TYPE_ERROR],
    ["math"],
    one("round(1e19)"),
    b"",
    error="Expression",
)

hel(
    "math-abs-min-max",
    "abs keeps its argument's type; min and max select an argument with its own type",
    "abs(-3) is the Integer 3 and abs(-2.5) the Float 2.5; min(2, 2.5) is the Integer 2 and max(2, 2.5) the Float 2.5; "
    "of two equal arguments the first is selected, so min(1, 1.0) is the Integer 1 and min(1.0, 1) the Float 1.0.",
    ["req-hel-math-2", "req-hel-core-functions-1"],
    ["math"],
    derived(
        N5,
        {
            "ai": "abs(n)",
            "af": "abs(-2.5)",
            "lo": "min(2, 2.5)",
            "hi": "max(2, 2.5)",
            "first": "min(1, 1.0)",
            "firstf": "min(1.0, 1)",
            "three": "max(n, 0, 7)",
            "single": "min(n)",
        },
    ),
    b"\xfd",
    {"n": -3, "ai": 3, "af": 2.5, "lo": 2, "hi": 2.5, "first": 1, "firstf": 1.0, "three": 7, "single": -3},
)

hel(
    "math-min-string",
    "min and max take numbers only",
    "max(1, 'a') is a type error.",
    ["req-hel-core-functions-1", TYPE_ERROR],
    ["math"],
    one("max(1, 'a')"),
    b"",
    error="Expression",
)

hel(
    "math-min-no-arguments",
    "min and max take at least one argument",
    "min() is an error that names the function.",
    ["req-hel-core-functions-1", TYPE_ERROR],
    ["math", "core-functions"],
    one("min()"),
    b"",
    error="Expression",
)

hel(
    "math-tostring",
    "toString renders a number canonically",
    "An Integer is its decimal digits; a Float is its shortest round-trip digits, positional from 10^-3 up to but not "
    "including 10^7 and scientific outside that range, always with a digit on each side of the point.",
    ["req-hel-math-3", "req-hel-math-4"],
    ["math", "float-rendering"],
    derived(
        N5,
        {
            "neg": "toString(-42)",
            "two": "toString(2.0)",
            "sum": "toString(0.1 + 0.2)",
            "big": "toString(1e7)",
            "below": "toString(1234567.0)",
            "milli": "toString(0.001)",
            "small": "toString(1e-4)",
            "tiny": "toString(4.9e-324)",
            "huge": "toString(1.7976931348623157e308)",
            "minus": "toString(-1.5e-5)",
            "cat": "concat('n=', toString(n))",
        },
    ),
    b"\x05",
    {
        "n": 5,
        "neg": "-42",
        "two": "2.0",
        "sum": "0.30000000000000004",
        "big": "1.0E7",
        "below": "1234567.0",
        "milli": "0.001",
        "small": "1.0E-4",
        "tiny": "4.9E-324",
        "huge": "1.7976931348623157E308",
        "minus": "-1.5E-5",
        "cat": "n=5",
    },
)

hel(
    "math-tostring-string",
    "toString converts numbers, nothing else",
    "toString('a') is a type error.",
    ["req-hel-math-3", TYPE_ERROR],
    ["math"],
    one("toString('a')"),
    b"",
    error="Expression",
)

hel(
    "float-remainder",
    "Float % is the truncated remainder, with the dividend's sign",
    "5.5 % 2.0 is 1.5, -5.5 % 2.0 is -1.5, 5.5 % -2.0 is 1.5 and -5.5 % -2.0 is -1.5; a mixed Integer and Float % is a "
    "Float remainder (7.5 % 5 is 2.5), and a finite dividend with an infinite divisor is returned unchanged.",
    ["req-hel-numeric-semantics-7"],
    ["numeric-semantics", "float-remainder"],
    derived(
        N5,
        {
            "pp": "5.5 % 2.0",
            "np": "-5.5 % 2.0",
            "pn": "5.5 % -2.0",
            "nn": "-5.5 % -2.0",
            "mixed": "7.5 % n",
            "inf": "3.5 % (1e308 * 10.0)",
        },
    ),
    b"\x05",
    {"n": 5, "pp": 1.5, "np": -1.5, "pn": 1.5, "nn": -1.5, "mixed": 2.5, "inf": 3.5},
)

hel(
    "float-remainder-by-zero",
    "Float % by zero is an error",
    "5.5 % 0.0 is a division-by-zero error, not NaN.",
    ["req-hel-numeric-semantics-7", "req-hel-numeric-semantics-2", TYPE_ERROR],
    ["numeric-semantics"],
    one("5.5 % 0.0"),
    b"",
    error="Expression",
)

# ----------------------------------------------------------------- HEL-RE, reserved words, non-leading parent

TEXT = {"features": {"requires": ["hel-ext-text"]}}

hel(
    "regex-xsd-constructs",
    "matches patterns are XSD regular expressions",
    "The digit and category escapes, class subtraction, a counted quantifier, a branch and a literal dollar written "
    "as a class each have the meaning XSD gives them. A backslash of the pattern is written twice in the HEL literal.",
    ["req-hel-ext-text-4"],
    ["ext-text"],
    derived(
        [],
        {
            "digits": r"matches('123', '\\\\d+')",
            "consonant": "matches('c', '[a-z-[aeiou]]')",
            "vowel": "matches('e', '[a-z-[aeiou]]')",
            "category": r"matches('A1', '\\\\p{Lu}\\\\d')",
            "dollar": "matches('a$', 'a[$]')",
            "branch": "matches('z', '[a-c][0-9]+|z')",
            "counted": "matches('aaa', 'a{2,3}')",
            "over": "matches('aaaa', 'a{2,3}')",
        },
    ),
    b"",
    {
        "digits": True,
        "consonant": True,
        "vowel": False,
        "category": True,
        "dollar": True,
        "branch": True,
        "counted": True,
        "over": False,
    },
    manifest=TEXT,
)

for _id, _what, _pattern in (
    ("backreference", "A back-reference", r"(a)\\\\1"),
    ("lookahead", "Look-ahead", "(?=a)ab"),
    ("non-capturing-group", "A non-capturing group", "(?:a)b"),
    ("anchors", "An unescaped ^ or $", "^ab$"),
    ("lazy-quantifier", "A lazy quantifier", "a.*?b"),
    ("hex-escape", "A hexadecimal escape", r"\\\\x61b"),
    ("word-boundary", "The word-boundary escape", r"a\\\\bb"),
):
    hel(
        f"regex-{_id}",
        f"{_what} is not HEL-RE: an argument error",
        "XSD's regular-expression language does not define the construct, so the pattern is refused rather than given "
        "one dialect's meaning.",
        ["req-hel-ext-text-4", TYPE_ERROR],
        ["ext-text"],
        one(f"matches('ab', '{_pattern}')"),
        b"",
        error="Expression",
        manifest=TEXT,
    )

hel(
    "regex-pattern-from-data",
    "A pattern read from the data is held to HEL-RE too",
    "The pattern bytes are (?i)a, which opens with an inline flag; the error is raised when the pattern is evaluated.",
    ["req-hel-ext-text-4", TYPE_ERROR],
    ["ext-text"],
    one(
        "matches('a', p)", ["ex:p a bddo:Field ; bddo:dataType bddo:string ; bddo:size 5 ; bddo:encoding bddo:ascii ."]
    ),
    b"(?i)a",
    error="Expression",
    manifest=TEXT,
)

hel(
    "not-is-an-operator",
    "not followed by a parenthesis is the operator, never a call",
    "not(n == 5) and n == 0 is (not (n == 5)) and (n == 0), false for n = 5; were not(...) to take the whole "
    "conjunction it would be true. not (n == 0) and n == 5 is true.",
    ["req-hel-formal-grammar-3"],
    ["syntax"],
    derived(N5, {"tight": "not(n == 5) and n == 0", "spaced": "not (n == 0) and n == 5"}),
    b"\x05",
    {"n": 5, "tight": False, "spaced": True},
)

hel(
    "reserved-word-call",
    "A reserved word followed by a parenthesis is not a function call",
    "true() is a syntax error: no function is named by a reserved word.",
    ["req-hel-formal-grammar-3", TYPE_ERROR] + SYNTAX,
    ["syntax"],
    one("true()"),
    b"",
    error="Expression",
)

hel(
    "parent-non-leading",
    "A .parent step after a key or a subscript is the struct holding that field",
    "hdr.parent is the root (count 9); hdr.n.parent is hdr, though n is a scalar; hdr.items[0].parent is hdr, the "
    "struct holding the array field; in an element, v.parent.parent climbs one above the element, to hdr; and above "
    "the root the step is Null, as root.parent is.",
    ["req-hel-reserved-roots-4", "req-hel-key-resolution-2"],
    ["reserved-roots", "non-leading-parent"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:count ex:hdr ex:holder ex:value ex:element ex:above ) .
    ex:count a bddo:Field ; bddo:dataType bddo:uint8 .
    ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .
    ex:holder a bddo:Field ; bddo:valueFromExpression "hdr.parent.count" .
    ex:value a bddo:Field ; bddo:valueFromExpression "hdr.n.parent.n" .
    ex:element a bddo:Field ; bddo:valueFromExpression "hdr.items[0].parent.n" .
    ex:above a bddo:Field ; bddo:valueFromExpression "hdr.parent.parent == root.parent" .
    ex:Hdr a bddo:Struct ; bddo:hasField ( ex:n ex:items ) .
    ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
    ex:items a bddo:Field ; bddo:dataType ex:Item ; bddo:repeatCountFromField ex:n .
    ex:Item a bddo:Struct ; bddo:hasField ( ex:v ex:climb ) .
    ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
    ex:climb a bddo:Field ; bddo:valueFromExpression "v.parent.parent.n" .
    """,
    b"\x09\x02\x0a\x14",
    {
        "count": 9,
        "hdr": {"n": 2, "items": [{"v": 10, "climb": 2}, {"v": 20, "climb": 2}]},
        "holder": 9,
        "value": 2,
        "element": 2,
        "above": True,
    },
)

hel(
    "stream-length-before-first-field",
    "The length of the input is known before the first field is read",
    "The first field's size is stream.length - 1: the processor knows |S| before it reads anything.",
    ["req-pm-inputs-outputs-1"],
    ["processing#inputs-outputs", "reserved-roots"],
    """
    ex:Root a bddo:Struct ; bddo:hasField ( ex:body ex:last ) .
    ex:body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "stream.length - 1" .
    ex:last a bddo:Field ; bddo:dataType bddo:uint8 .
    """,
    b"abc\x07",
    {"body": b"abc", "last": 7},
)
