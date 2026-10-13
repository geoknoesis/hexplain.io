"""Layout fixtures and the layout selector, dynamic dimension and rule property contracts.

PREFIX and LAYOUT are the shared layout/compound-dataset fixture: the competency gate
(tools/test_layout_competency.py) and the closure and integer-family libraries build on them.
"""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row

PREFIX = (
    prefix_block(
        {
            "ex": "urn:hexplain:competency:",
            "dlv": "dlv",
            "b": "bddo",
            "a": "bundle",
            "xsd": "xsd",
            "skos": "skos",
            "dct": "dct",
        }
    )
    + """b:uint8 a b:DataType . ex:axis a dlv:Axis . ex:f a b:Field .
ex:role a skos:Concept .
"""
)
#: One layout with one dimension; the base most layout cases mutate.
LAYOUT = (
    "ex:l a dlv:DataLayout; dlv:cellDataType b:uint8; dlv:hasDimension (ex:d). ex:d a dlv:Dimension; dlv:hasAxis "
    "ex:axis; dlv:dimensionSize 8. "
)
DLV = "https://hexplain.io/ns/dlv#"
MODULE = "dlv/dlv.ttl"


def cases() -> list[dict[str, Any]]:
    rows = []
    value: str | None
    prefix = PREFIX + "ex:f2 a b:Field. ex:order a dlv:ChunkOrder. ex:order2 a dlv:ChunkOrder. b:uint16 a b:DataType. "

    def add(name: str, base: str, owner: str, prop: str, value: str | None, ok: bool) -> None:
        statement = f" {owner} " + (prop if ":" in prop else "dlv:" + prop) + f" {value}." if value is not None else ""
        path = "" if ok else "https://hexplain.io/ns/" + ("bddo#condition" if prop == "b:condition" else "dlv#" + prop)
        rows.append(row("layout property " + name, MODULE, prefix + base + statement, ok, path))

    for prop, owner, good, second, bad in [
        ("cellDataType", "ex:l", "b:uint8", "b:uint16", "ex:unknown"),
        ("cellBitWidthFromField", "ex:l", "ex:f", "ex:f2", "ex:unknown"),
        ("dimensionStrideFromField", "ex:d", "ex:f", "ex:f2", "ex:unknown"),
        ("dimensionStrideFromExpression", "ex:d", '"1"', '"2"', "1"),
        ("dimensionSizeFromField", "ex:d", "ex:f", "ex:f2", "ex:unknown"),
        ("chunkSizeFromField", "ex:d", "ex:f", "ex:f2", "ex:unknown"),
        ("chunkOffsetsFromField", "ex:l", "ex:f", "ex:f2", "ex:unknown"),
        ("chunkLengthsFromField", "ex:l", "ex:f", "ex:f2", "ex:unknown"),
        ("chunkOrder", "ex:l", "ex:order", "ex:order2", "ex:unknown"),
        ("chunkOffsetBase", "ex:l", "b:streamStart", "b:parentStart", "ex:unknown"),
    ]:
        base = LAYOUT
        if prop == "cellDataType":
            base = base.replace("; dlv:cellDataType b:uint8", "")
        if prop == "dimensionSizeFromField":
            base = base.replace("; dlv:dimensionSize 8", "")
        if prop.startswith("chunk") and prop != "chunkOffsetsFromField":
            base += "ex:l dlv:chunkOffsetsFromField ex:f. "
        for label, value, ok in [("valid", good, True), ("duplicate", good + "," + second, False), ("bad", bad, False)]:
            add(prop + " " + label, base, owner, prop, value, ok)
    for cls, prop, good, second, bad in [
        ("CellDataTypeRule", "ruleCellDataType", "b:uint8", "b:uint16", "ex:unknown"),
        ("DimensionOrderRule", "ruleDimensionOrder", "(ex:d)", "(ex:d)", '"dimension"'),
    ]:
        base = LAYOUT + "ex:r a dlv:" + cls + ". "
        for label, value, ok in [
            ("valid", good, True),
            ("duplicate", good + "," + second, False),
            ("bad", bad, False),
            ("missing", None, False),
        ]:
            add(cls + " " + prop + " " + label, base + 'ex:r b:condition "true". ', "ex:r", prop, value, ok)
        for label, value, ok in [("bad", "1", False), ("duplicate", '"true","false"', False), ("missing", None, False)]:
            add(
                cls + " condition " + label,
                base + "ex:r dlv:" + prop + " " + good + ". ",
                "ex:r",
                "b:condition",
                value,
                ok,
            )
    add("missing axis", LAYOUT.replace("; dlv:hasAxis ex:axis", ""), "ex:d", "hasAxis", None, False)
    return rows
