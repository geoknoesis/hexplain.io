"""Physical Parser cases: resource limits. Each lowered limit is stated in the case manifest."""

from __future__ import annotations

from cases_physical import pp

NESTED = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ex:child ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:child a bddo:Field ; bddo:dataType ex:Root ; bddo:isPresentIf "v == 1" .
"""


def nested(depth: int) -> dict[str, object]:
    """The tree of a Root nested `depth` deep: the innermost has v 0 and no child."""
    node: dict[str, object] = {"v": 0, "child": None}
    for _ in range(depth - 1):
        node = {"v": 1, "child": node}
    return node


LIMITS = ["req-pm-resource-limits-1", "req-pm-errors-12"]

pp(
    "limit-depth-exceeded",
    "Entering a struct deeper than maxDepth is a ResourceLimit error",
    "The root is at depth 1; a fourth nested struct exceeds maxDepth 3.",
    LIMITS,
    ["resource-limits"],
    NESTED,
    b"\x01\x01\x01\x00",
    error="ResourceLimit",
    manifest={"limits": {"maxDepth": 3}},
)

pp(
    "limit-depth-at-limit",
    "A struct at exactly maxDepth is within the limit",
    "Four nested structs under maxDepth 4 parse.",
    ["req-pm-resource-limits-1"],
    ["resource-limits"],
    NESTED,
    b"\x01\x01\x01\x00",
    nested(4),
    manifest={"limits": {"maxDepth": 4}},
)

pp(
    "limit-depth-default",
    "The default configuration allows a nesting depth of 64",
    "64 nested structs parse with no limit configured.",
    ["req-pm-resource-limits-2"],
    ["resource-limits"],
    NESTED,
    b"\x01" * 63 + b"\x00",
    nested(64),
)

pp(
    "limit-visited-nodes",
    "Visited nodes beyond maxVisitedNodes is a ResourceLimit error",
    "A hundred array elements under maxVisitedNodes 50.",
    LIMITS + ["req-pm-security-resources-1"],
    ["resource-limits", "security-resources"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:vals ) .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 100 .
   """,
    bytes(100),
    error="ResourceLimit",
    manifest={"limits": {"maxVisitedNodes": 50}},
)

pp(
    "limit-materialized-bytes",
    "Bytes copied into values beyond maxMaterializedBytes is a ResourceLimit error",
    "A 100-byte field under maxMaterializedBytes 10.",
    LIMITS,
    ["resource-limits"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:data ) .
   ex:data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 100 .
   """,
    bytes(100),
    error="ResourceLimit",
    manifest={"limits": {"maxMaterializedBytes": 10}},
)

pp(
    "limit-input-bytes",
    "An input longer than maxInputBytes is a ResourceLimit error",
    "100 bytes of input under maxInputBytes 50.",
    LIMITS,
    ["resource-limits"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    bytes(100),
    error="ResourceLimit",
    manifest={"limits": {"maxInputBytes": 50}},
)

pp(
    "limit-hel-depth",
    "An expression deeper than the HEL nesting limit is a ResourceLimit error",
    "Five nested operators under a nesting limit of 3; not a syntax error.",
    LIMITS + ["req-hel-conformance-8"],
    ["resource-limits", "hel/index.html#conformance"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:d a bddo:Field ; bddo:valueFromExpression "-(-(-(-(-a))))" .
   """,
    b"\x01",
    error="ResourceLimit",
    manifest={"limits": {"maxHelDepth": 3}},
)

pp(
    "limit-hel-length",
    "An expression longer than the HEL length limit is a ResourceLimit error",
    "A 21-character expression under a length limit of 10.",
    LIMITS + ["req-hel-conformance-8"],
    ["resource-limits", "hel/index.html#conformance"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:d a bddo:Field ; bddo:valueFromExpression "a + a + a + a + a + a" .
   """,
    b"\x01",
    error="ResourceLimit",
    manifest={"limits": {"maxHelLength": 10}},
)

pp(
    "limit-hel-default-depth",
    "The default configuration accepts an expression 512 levels deep",
    "511 unary minus operators over a literal make a tree 512 deep; (-1) to the 511th power times 1 is -1.",
    ["req-pm-resource-limits-2", "req-hel-conformance-8"],
    ["resource-limits", "hel/index.html#conformance"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:d ) .
   ex:d a bddo:Field ; bddo:valueFromExpression "%s" .
   """
    % ("- " * 511 + "1"),
    b"",
    {"d": -1},
)

pp(
    "limit-tree-depth",
    "A tree document nested beyond maxTreeDepth is a ResourceLimit error",
    "JSON objects nested four deep (the top-level object at depth 1) under maxTreeDepth 3.",
    LIMITS,
    ["resource-limits", "tree-documents"],
    """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/a" .
   """,
    b'{"a": "x", "b": {"c": {"d": {"e": 1}}}}',
    error="ResourceLimit",
    manifest={"limits": {"maxTreeDepth": 3}, "features": {"requires": ["tree-documents"]}},
)

pp(
    "limit-quantifier-evaluations",
    "Quantifier predicate evaluations beyond maxQuantifierEvaluations is a ResourceLimit error",
    "all() over ten elements whose predicate holds for each needs ten evaluations; the limit is 5.",
    LIMITS + ["req-hel-ext-quantifiers-4", "req-hel-conformance-8"],
    ["resource-limits", "hel/index.html#ext-quantifiers"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:items ex:d ) .
   ex:items a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 10 .
   ex:d a bddo:Field ; bddo:valueFromExpression "all(items, self >= 0)" .
   """,
    bytes(10),
    error="ResourceLimit",
    manifest={"limits": {"maxQuantifierEvaluations": 5}, "features": {"requires": ["hel-ext-quantifier"]}},
)

# The quantifier group's collection, byte and text functions charge every input or output element
# against the same budget, before the allocation or conversion it pays for.
for _case, _title, _detail, _expression, _requirements in [
    (
        "limit-collection-output",
        "A collection whose expanded output exceeds maxQuantifierEvaluations is a ResourceLimit error",
        "repeatValue(1, 10) expands to ten elements before sumOf reads one; the limit is 5.",
        "sumOf(repeatValue(1, 10), self)",
        ["req-hel-ext-quantifiers-5", "req-hel-ext-quantifiers-6"],
    ),
    (
        "limit-collection-traversal",
        "A traversal beyond maxQuantifierEvaluations is a ResourceLimit error",
        "sumOf over ten elements processes ten inputs; the limit is 5.",
        "sumOf(items, self)",
        ["req-hel-ext-quantifiers-5"],
    ),
    (
        "limit-text-conversion",
        "A text conversion beyond maxQuantifierEvaluations is a ResourceLimit error",
        "unicodeText over ten scalar codes charges ten inputs and ten outputs; the limit is 5.",
        "unicodeText(items)",
        ["req-hel-ext-quantifiers-5", "req-hel-ext-quantifiers-6"],
    ),
]:
    pp(
        _case,
        _title,
        _detail,
        LIMITS + _requirements + ["req-hel-conformance-8"],
        ["resource-limits", "hel/index.html#ext-quantifiers"],
        f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:items ex:d ) .
   ex:items a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 10 .
   ex:d a bddo:Field ; bddo:valueFromExpression "{_expression}" .
   """,
        b"A" * 10,
        error="ResourceLimit",
        manifest={"limits": {"maxQuantifierEvaluations": 5}, "features": {"requires": ["hel-ext-quantifier"]}},
    )

pp(
    "limit-regex-steps",
    "A regular-expression match beyond maxRegexSteps is a ResourceLimit error, not false",
    "Matching 100 a's against a* in full examines at least 100 characters of the subject; the limit is 10.",
    LIMITS + ["req-hel-ext-text-3", "req-hel-conformance-8"],
    ["resource-limits", "hel/index.html#ext-text"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:d ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:size 100 ; bddo:encoding bddo:ascii .
   ex:d a bddo:Field ; bddo:valueFromExpression "matches(s, 'a*')" .
   """,
    b"a" * 100,
    error="ResourceLimit",
    manifest={"limits": {"maxRegexSteps": 10}, "features": {"requires": ["hel-ext-text"]}},
)

# ----------------------------------------------------------------- the cost of a pattern's counted quantifiers

#: A match is bounded including its idle iterations; a pattern too large to compile is a ResourceLimit error; a
#: pattern within the two figures is not refused for its counted quantifiers.
IDLE_BOUNDED, TOO_LARGE, WITHIN_CAPS = "req-hel-ext-text-9", "req-hel-ext-text-8", "req-hel-ext-text-10"
TEXT_GROUP = {"features": {"requires": ["hel-ext-text"]}}
EMPTY_SUBJECT = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:n ex:d ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:d a bddo:Field ; bddo:valueFromExpression "matches('', '{pattern}')" .
   """

pp(
    "limit-regex-idle-iterations",
    "Iterations that consume no input are bounded: a huge empty repetition is true or a ResourceLimit error",
    "((){20000}){200000} asks for four thousand million iterations of a group that matches the empty string. "
    "The empty subject matches it, so a processor that does not perform the idle iterations answers true; one "
    "that performs them meets its match-cost limit, and one that refuses the pattern for its bounds (200,000 is "
    "above 65,535, and the product above 1,000,000) says so. Each is a ResourceLimit error or the value true; "
    "what no processor may do is run unbounded, or answer false.",
    [IDLE_BOUNDED, TOO_LARGE, "req-hel-ext-text-3"],
    ["resource-limits", "hel/index.html#ext-text"],
    EMPTY_SUBJECT.replace("{pattern}", "((){20000}){200000}"),
    b"\x00",
    {"n": 0, "d": True},
    manifest=dict(TEXT_GROUP, orError="ResourceLimit"),
)

pp(
    "limit-regex-counted-bound-above-cap",
    "A counted quantifier above 65,535 may be refused, and is otherwise matched correctly",
    "a{65536} is a HEL-RE expression (the bound is below 2^31), so it is no argument error. A processor MAY "
    "refuse it with a ResourceLimit error; one that compiles it finds that the one-character subject does not "
    "match.",
    [TOO_LARGE],
    ["hel/index.html#ext-text"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:d ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:size 1 ; bddo:encoding bddo:ascii .
   ex:d a bddo:Field ; bddo:valueFromExpression "matches(s, 'a{65536}')" .
   """,
    b"a",
    {"s": "a", "d": False},
    manifest=dict(TEXT_GROUP, orError="ResourceLimit"),
)

pp(
    "limit-regex-counted-within-caps",
    "A pattern within both figures is not refused for its counted quantifiers",
    "(a{10}){10} has bounds of 10 and a nested product of 100, and ((){100}){100} a product of 10,000: both "
    "are within 65,535 and 1,000,000, so neither is refused. A hundred a's match the first, and the empty "
    "subject matches the second, whose ten thousand idle iterations are far below the least match-cost limit a "
    "processor has by default.",
    [WITHIN_CAPS, IDLE_BOUNDED],
    ["resource-limits", "hel/index.html#ext-text"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:s ex:d ex:e ) .
   ex:s a bddo:Field ; bddo:dataType bddo:string ; bddo:size 100 ; bddo:encoding bddo:ascii .
   ex:d a bddo:Field ; bddo:valueFromExpression "matches(s, '(a{10}){10}')" .
   ex:e a bddo:Field ; bddo:valueFromExpression "matches('', '((){100}){100}')" .
   """,
    b"a" * 100,
    {"s": "a" * 100, "d": True, "e": True},
    manifest=TEXT_GROUP,
)
