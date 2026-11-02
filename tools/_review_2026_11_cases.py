"""Two-sided witnesses for the constraints the 2026-11 review added or corrected.

Each finding is witnessed both ways: a graph the corrected shape accepts and one it rejects, with
the source shape (and, for a property constraint, the result path) the rejection must carry. The
graphs carry no ontology, as every family contract does, so a fact a shape reads from the module
(a data type's base type, a struct's parameters) is stated in the case itself.
"""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term

BDDO = "bddo/bddo.ttl"
DLV = "dlv/dlv.ttl"

PREFIX = prefix_block({"ex": "urn:review-2026-11:", "b": "bddo", "dlv": "dlv", "xsd": "xsd", "rdfs": "rdfs"}, " ")

# Facts the module states and a case's shapes read: the types the cases name, and a struct with
# one parameter that a field may instantiate.
TYPES = (
    "b:uint8 a b:DataType; b:baseType b:baseInteger; b:bitWidth 8; b:isSigned false. "
    "b:uint16 a b:DataType; b:baseType b:baseInteger; b:bitWidth 16; b:isSigned false. "
    "b:float32 a b:DataType; b:baseType b:baseFloat; b:bitWidth 32. "
    "b:asciiInteger a b:DataType. "
)
ROW = (
    "ex:Row a b:Struct; b:hasParameter (ex:Row.n); b:hasField (ex:Row.v). "
    "ex:Row.n a b:Parameter. ex:Row.v a b:Field; b:dataType b:uint8. "
)


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, module: str, body: str, ok: bool, path: str = "", shape: str = "", ns: str = "bddo") -> None:
        rows.append(
            row(
                "review 2026-11 " + name,
                module,
                PREFIX + TYPES + body,
                ok,
                term(ns, path) if path else "",
                # A property constraint is matched by its path: its source shape is a blank node.
                expected_shape=term(ns, shape) if shape and not path and not ok else "",
            )
        )

    # Arity applies to every kind of struct, the container subclasses included. The subclass axioms
    # are stated as the module states them, for the shapes that read them (sh:class); the arity
    # rule itself names the container classes and needs none.
    axioms = (
        "b:DelimitedRecords rdfs:subClassOf b:Struct. b:DelimitedTable rdfs:subClassOf b:DelimitedRecords. "
        "b:TreeDocument rdfs:subClassOf b:Struct. "
    )
    table = axioms + (
        'ex:T a b:DelimitedTable; b:fieldDelimiter "2c"^^xsd:hexBinary; b:hasField (ex:T.c); b:hasParameter (ex:T.n). '
        "ex:T.c a b:Field; b:dataType b:asciiInteger. ex:T.n a b:Parameter. "
    )
    add(
        "arity of a parameterised delimited table",
        BDDO,
        table + 'ex:f a b:Field; b:dataType ex:T; b:hasArgument ("1").',
        True,
    )
    add(
        "arity of a delimited table named without arguments",
        BDDO,
        table.replace(axioms, "") + "ex:f a b:Field; b:dataType ex:T.",
        False,
        shape="ArgumentArityShape",
    )
    tree = axioms + (
        "ex:D a b:TreeDocument; b:treeSyntax b:json; b:hasField (ex:D.a); b:hasParameter (ex:D.n). "
        'ex:D.a a b:Field; b:dataType b:asciiInteger; b:nodePath "/a". ex:D.n a b:Parameter. '
    )
    add(
        "arity of a tree document given two arguments for one parameter",
        BDDO,
        tree + 'ex:f a b:Field; b:dataType ex:D; b:hasArgument ("1" "2").',
        False,
        shape="ArgumentArityShape",
    )

    # bddo:bcd false is the default and constrains nothing; bddo:bcd true needs an integer.
    add("bcd false on a float field", BDDO, "ex:f a b:Field; b:dataType b:float32; b:bcd false.", True)
    add(
        "bcd true on a float field",
        BDDO,
        "ex:f a b:Field; b:dataType b:float32; b:bcd true.",
        False,
        shape="NumericRepresentationShape",
    )
    add("bcd true on an unsigned integer field", BDDO, "ex:f a b:Field; b:dataType b:uint16; b:bcd true.", True)
    add(
        "bcd true beside a fixed-point scale",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:bcd true; b:fixedPointScale -2.",
        False,
        shape="NumericRepresentationShape",
    )
    add(
        "bcd false beside a fixed-point scale",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:bcd false; b:fixedPointScale -2.",
        True,
    )
    add(
        "bcd true beside a bit length",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:bcd true; b:bitLength 12.",
        False,
        shape="BcdShape",
    )

    # Arguments are supplied only where a parameterised struct is named.
    add(
        "arguments for a parameterised struct",
        BDDO,
        ROW + 'ex:f a b:Field; b:dataType ex:Row; b:hasArgument ("1").',
        True,
    )
    add(
        "arguments for a primitive type",
        BDDO,
        'ex:f a b:Field; b:dataType b:uint8; b:hasArgument ("1" "2").',
        False,
        shape="ArgumentListShape",
    )
    add(
        "arguments on a field typed only by its rules",
        BDDO,
        ROW + 'ex:f a b:Field; b:hasConditionalDataType (ex:r); b:hasArgument ("1"). '
        'ex:r a b:DataTypeRule; b:condition "true"; b:ruleDataType ex:Row; b:hasArgument ("1").',
        False,
        shape="ArgumentListShape",
    )
    add(
        "arguments on the rule that names the parameterised struct",
        BDDO,
        ROW + "ex:f a b:Field; b:hasConditionalDataType (ex:r). "
        'ex:r a b:DataTypeRule; b:condition "true"; b:ruleDataType ex:Row; b:hasArgument ("1").',
        True,
    )

    # A dispatch default has nowhere to state arguments.
    dispatch = 'ex:t a b:DispatchTable; b:dispatchOnExpression "1"; '
    add("dispatch default without parameters", BDDO, dispatch + "b:dispatchDefault b:uint8.", True)
    add(
        "dispatch default naming a parameterised struct",
        BDDO,
        ROW + dispatch + "b:dispatchDefault ex:Row.",
        False,
        shape="DispatchDefaultShape",
    )

    # A derived field selects no type, by dispatch or with arguments.
    add("derived field", BDDO, 'ex:f a b:Field; b:valueFromExpression "1".', True)
    add(
        "derived field with a dispatch table",
        BDDO,
        'ex:f a b:Field; b:valueFromExpression "1"; b:hasDispatchTable ex:t. '
        + dispatch
        + "b:dispatchDefault b:uint8.",
        False,
        shape="DerivedFieldShape",
    )
    add(
        "derived field with arguments",
        BDDO,
        ROW + 'ex:f a b:Field; b:valueFromExpression "1"; b:hasArgument ("1").',
        False,
        shape="DerivedFieldShape",
    )

    # The deprecated base type names are read, and reported at sh:Warning.
    old = "ex:d a b:DataType; b:baseType b:integer; b:bitWidth 8."
    rows.append(row("review 2026-11 deprecated base type is advisory only", BDDO, PREFIX + old, allow_warnings=True))
    rows.append(
        row(
            "review 2026-11 deprecated base type is reported",
            BDDO,
            PREFIX + old,
            False,
            expected_shape=term("bddo", "DeprecatedBaseTypeShape"),
            severity=term("sh", "Warning"),
            allow_warnings=False,
        )
    )
    rows.append(
        row(
            "review 2026-11 current base type is not reported",
            BDDO,
            PREFIX + "ex:d a b:DataType; b:baseType b:baseInteger; b:bitWidth 8.",
            allow_warnings=False,
        )
    )
    add(
        "unknown base type",
        BDDO,
        "ex:d a b:DataType; b:baseType ex:integer; b:bitWidth 8.",
        False,
        "baseType",
        "DataTypeShape",
    )

    # The deprecated endianness spelling is constrained as bddo:endianness is.
    add("deprecated endianness alone", BDDO, "ex:f a b:Field; b:dataType b:uint16; b:hasEndianness b:BigEndian.", True)
    add(
        "two deprecated endiannesses",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:hasEndianness b:BigEndian, b:LittleEndian.",
        False,
        "hasEndianness",
        "DeprecatedEndiannessShape",
    )
    add(
        "deprecated endianness not a byte order",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:hasEndianness ex:middle.",
        False,
        "hasEndianness",
        "DeprecatedEndiannessShape",
    )
    add(
        "deprecated endianness contradicting endianness",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:hasEndianness b:BigEndian; b:endianness b:LittleEndian.",
        False,
        shape="DeprecatedEndiannessShape",
    )
    add(
        "deprecated endianness beside conditional endianness",
        BDDO,
        "ex:f a b:Field; b:dataType b:uint16; b:hasEndianness b:BigEndian; b:hasConditionalEndianness (ex:r). "
        'ex:r a b:EndiannessRule; b:condition "true"; b:ruleEndianness b:BigEndian.',
        False,
        "hasEndianness",
        "ConditionalEndiannessShape",
    )
    rows.append(
        row(
            "review 2026-11 deprecated endianness is reported",
            BDDO,
            PREFIX + TYPES + "ex:f a b:Field; b:dataType b:uint16; b:hasEndianness b:BigEndian.",
            False,
            expected_shape=term("bddo", "DeprecatedEndiannessUseShape"),
            severity=term("sh", "Warning"),
            allow_warnings=False,
        )
    )

    # A tree document's fields are located by path, never by any byte offset. The result is the
    # list member's nested node shape, reported on the document without a path of its own.
    add(
        "tree document field located by its path",
        BDDO,
        tree + 'ex:f a b:Field; b:dataType ex:D; b:hasArgument ("1").',
        True,
    )
    for prop, value in [("atOffsetFromField", "ex:D.a"), ("atOffsetFromExpression", '"4"')]:
        add(
            "tree document field located by " + prop,
            BDDO,
            tree.replace('b:nodePath "/a". ', 'b:nodePath "/a"; b:' + prop + " " + value + ". "),
            False,
        )

    # DLV: a conditional dimension order is a permutation of one set of dimensions, and a layout
    # chunked through it still needs its chunk offsets.
    dims = (
        "ex:y a dlv:Dimension; dlv:hasAxis dlv:axisY; dlv:dimensionSize 4. "
        "ex:x a dlv:Dimension; dlv:hasAxis dlv:axisX; dlv:dimensionSize 4. "
        "ex:b a dlv:Dimension; dlv:hasAxis dlv:axisBand; dlv:dimensionSize 3. "
        "dlv:axisX a dlv:Axis. dlv:axisY a dlv:Axis. dlv:axisBand a dlv:Axis. "
    )

    def layout(first: str, second: str, extra: str = "") -> str:
        return (
            "ex:l a dlv:DataLayout; dlv:cellDataType b:uint8; dlv:hasConditionalDimensionOrder (ex:r1 ex:r2)"
            + extra
            + '. ex:r1 a dlv:DimensionOrderRule; b:condition "true"; dlv:ruleDimensionOrder ('
            + first
            + ') . ex:r2 a dlv:DimensionOrderRule; b:condition "false"; dlv:ruleDimensionOrder ('
            + second
            + "). "
            + dims
        )

    add("dimension orders that permute one set", DLV, layout("ex:b ex:y ex:x", "ex:y ex:x ex:b"), True, ns="dlv")
    add(
        "dimension orders naming different sets",
        DLV,
        layout("ex:y ex:x", "ex:y ex:x ex:b"),
        False,
        shape="DataLayoutShape",
        ns="dlv",
    )
    add(
        "dimension order naming a dimension twice",
        DLV,
        layout("ex:y ex:x", "ex:x ex:x ex:y"),
        False,
        shape="DataLayoutShape",
        ns="dlv",
    )
    chunked = dims.replace("ex:y a dlv:Dimension; dlv:hasAxis dlv:axisY; dlv:dimensionSize 4.", "")
    chunked_y = "ex:y a dlv:Dimension; dlv:hasAxis dlv:axisY; dlv:dimensionSize 4; dlv:chunkSize 2. "
    add(
        "chunked conditional order with chunk offsets",
        DLV,
        layout("ex:y ex:x", "ex:x ex:y", "; dlv:chunkOffsetsFromField ex:offsets").replace(dims, chunked + chunked_y)
        + "ex:offsets a b:Field.",
        True,
        ns="dlv",
    )
    add(
        "chunked conditional order without chunk offsets",
        DLV,
        layout("ex:y ex:x", "ex:x ex:y").replace(dims, chunked + chunked_y),
        False,
        shape="ChunkedLayoutShape",
        ns="dlv",
    )
    return rows
