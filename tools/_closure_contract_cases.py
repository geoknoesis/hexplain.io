"""Final branch, nested-member and explicitly reused-shape witnesses."""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term
from _layout_property_cases import LAYOUT
from _layout_property_cases import PREFIX as LP
from _physical_property_cases import PREFIX as PHYSICAL


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, module: str, data: str, ok: bool = False, path: str = "", **extra: Any) -> None:
        rows.append(row("closure " + name, module, data, ok, path, **extra))

    def physical(name: str, body: str, path: str = "") -> None:
        add(name, "bddo/bddo.ttl", PHYSICAL + body, path=term("bddo", path) if path else "")

    physical("literal field type", 'ex:f a b:Field; b:dataType "uint8".', "dataType")
    physical(
        "literal dispatch default",
        'ex:f a b:DispatchTable; b:dispatchOnField ex:count; b:dispatchDefault "uint8".',
        "dispatchDefault",
    )
    physical("untyped struct member", "ex:f a b:Struct; b:hasField (ex:unknown).")
    physical("untyped conditional datatype member", "ex:f a b:Field; b:hasConditionalDataType (ex:unknown).")
    rule = 'ex:r a b:EndiannessRule; b:condition "true"; b:ruleEndianness b:BigEndian. '
    for label, value in [("literal", '"rules"'), ("duplicate", "(ex:r),(ex:r)")]:
        physical(
            "conditional endian " + label,
            rule + "ex:f b:hasConditionalEndianness " + value + ".",
            "hasConditionalEndianness",
        )
    for value in ["3", "8,16"]:
        physical(
            "numeric base " + value, "ex:f a b:Field; b:dataType b:uint8; b:numericBase " + value + ".", "numericBase"
        )
    group = (
        'ex:g a b:RecordGrouping; b:groupingStyle b:keyedGroup; b:groupOpenToken "BEGIN"; b:groupCloseToken "END". '
        'ex:g2 a b:RecordGrouping; b:groupingStyle b:keyedGroup; b:groupOpenToken "BEGIN"; b:groupCloseToken "END". '
    )
    for value in ["ex:unknown", "ex:g,ex:g2"]:
        physical(
            "group membership " + value,
            group + "ex:f a b:DelimitedRecords; b:hasField (ex:count); b:hasGrouping " + value + ".",
            "hasGrouping",
        )
    tree = (
        "ex:t a b:TreeDocument; b:treeSyntax b:xml; b:hasField (ex:f). ex:f a b:Field; b:dataType b:uint8; "
        'b:nodePath "/x". '
    )
    for prop, value in [("key", '"x"'), ("keyPath", '"x/y"'), ("atOffset", "1")]:
        physical("tree forbidden " + prop, tree + "ex:f b:" + prop + " " + value + ".")
    physical(
        "table key value separator",
        'ex:f a b:DelimitedTable; b:hasField (ex:count); b:fieldDelimiter "2C"^^xsd:hexBinary; '
        'b:keyValueSeparator "3D"^^xsd:hexBinary.',
        "keyValueSeparator",
    )
    for end in ["From", "To"]:
        physical(
            "checksum conflicting " + end,
            "ex:f a b:Checksum; b:checksumAlgorithm b:crc32; b:covers"
            + end
            + "Field ex:count; b:covers"
            + end
            + 'Expression "0".',
        )
    for prop, anchor, rule in [
        ("hasDimension", "; dlv:hasDimension (ex:d)", ""),
        (
            "hasConditionalCellDataType",
            "; dlv:cellDataType b:uint8",
            'ex:r a dlv:CellDataTypeRule; b:condition "true"; dlv:ruleCellDataType b:uint8.',
        ),
        (
            "hasConditionalDimensionOrder",
            "; dlv:hasDimension (ex:d)",
            'ex:r a dlv:DimensionOrderRule; b:condition "true"; dlv:ruleDimensionOrder (ex:d).',
        ),
    ]:
        base = LP + LAYOUT.replace(anchor, "") + rule + " "
        member = "ex:d" if prop == "hasDimension" else "ex:r"
        for label, value in [
            ("literal", '"list"'),
            ("duplicate", "(" + member + "),(" + member + ")"),
            ("untyped member", "(ex:unknown)"),
        ]:
            add(
                prop + " " + label,
                "dlv/dlv.ttl",
                base + "ex:l dlv:" + prop + " " + value + ".",
                path="" if label == "untyped member" else term("dlv", prop),
            )
    add(
        "dimension rule untyped member",
        "dlv/dlv.ttl",
        LP + 'ex:r a dlv:DimensionOrderRule; b:condition "true"; dlv:ruleDimensionOrder (ex:unknown).',
    )
    rp = prefix_block({"r": "raster", "ex": "urn:closure-raster:"}, " ")
    for name, body, path in [
        ("literal band", 'ex:f r:hasBand "band".', "hasBand"),
        ("literal dimension member", 'ex:f a r:SampleArray; r:dimensions ("dimension").', ""),
        ("literal dimensions", 'ex:f a r:SampleArray; r:dimensions "dimensions".', "dimensions"),
        (
            "duplicate dimensions",
            "ex:f a r:SampleArray; r:dimensions (), (ex:d). ex:d a r:ArrayDimension; r:dimensionExtent 1.",
            "dimensions",
        ),
    ]:
        add(name, "aspect/raster/raster.ttl", rp + body, path=term("raster", path) if path else "")
    add(
        "unknown bundle binding",
        "aspect/bundle/bundle.ttl",
        prefix_block({"a": "bundle"}, " ") + "<urn:f> a a:Asset; a:boundBy <urn:unknown>.",
        path=term("bundle", "boundBy"),
    )
    add(
        "video string duration",
        "vdv/video.ttl",
        '<urn:f> a <https://hexplain.io/ns/video#VideoStream>; <https://hexplain.io/ns/aspect/time#duration> "1".',
        path=term("time", "duration"),
    )
    add(
        "reused encoding shape without shorthand",
        "hexplain/core.ttl",
        prefix_block({"c": "hexplain", "ex": "urn:closure:", "skos": "skos"})
        + "ex:f c:hasEncodingStep (ex:step). ex:step a c:EncodingStep; c:codec ex:codec. ex:codec a skos:Concept.",
        True,
        target_shape=term("hexplain", "IsEncodedWithShape"),
        target_node="urn:closure:f",
    )
    physical(
        "checksum whole range conflicts with endpoint",
        'ex:f a b:Checksum; b:checksumAlgorithm b:crc32; b:coversExpression "range"; b:coversFromField ex:count.',
    )
    return rows
