"""Exercise each promised integer datatype alternative with the same exact value."""

from __future__ import annotations

from typing import Any

from _cases import row, term
from _layout_property_cases import LAYOUT, PREFIX

NAMES = [
    "integer",
    "positiveInteger",
    "nonNegativeInteger",
    "int",
    "long",
    "short",
    "byte",
    "unsignedInt",
    "unsignedLong",
    "unsignedShort",
    "unsignedByte",
]


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, module: str, data: str, expected: bool = True, path: str = "") -> None:
        rows.append(row(name, module, data, expected, path))

    for prop in ["cellBitWidth", "dimensionSize", "dimensionStride", "chunkSize"]:
        base = LAYOUT
        if prop == "dimensionSize":
            base = base.replace("; dlv:dimensionSize 8", "")
        if prop == "chunkSize":
            base += "ex:l dlv:chunkOffsetsFromField ex:f. "
        owner = "ex:l" if prop == "cellBitWidth" else "ex:d"
        for datatype in NAMES:
            if datatype in ("integer", "unsignedByte"):
                continue  # Already exercised by retained layout cases.
            add(prop + " " + datatype, "dlv/dlv.ttl", PREFIX + base + f'{owner} dlv:{prop} "1"^^xsd:{datatype}.')
        if prop in ("dimensionSize", "chunkSize"):
            add(
                prop + " cardinality boundary",
                "dlv/dlv.ttl",
                PREFIX + base + f"{owner} dlv:{prop} 1,2.",
                False,
                term("dlv", prop),
            )
    for prop in ["minParts", "maxParts"]:
        for datatype in NAMES:
            if datatype == "integer":
                continue
            add(
                prop + " " + datatype,
                "aspect/bundle/bundle.ttl",
                PREFIX + f'ex:spec a a:PartSpec; a:pathPattern "*.x"; a:{prop} "1"^^xsd:{datatype}.',
            )
        add(
            prop + " cardinality boundary",
            "aspect/bundle/bundle.ttl",
            PREFIX + f'ex:spec a a:PartSpec; a:pathPattern "*.x"; a:{prop} 1,2.',
            False,
            term("bundle", prop),
        )
    for prop in ["sourcePort", "destinationPort", "sequenceNumber", "acknowledgmentNumber"]:
        for datatype in NAMES:
            if datatype in ("integer", "unsignedShort"):
                continue
            add(
                prop + " " + datatype,
                "npv/net.ttl",
                f'<urn:packet> <{term("networkflow", prop)}> "1"^^<{term("xsd", datatype)}>.',
            )
    return rows
