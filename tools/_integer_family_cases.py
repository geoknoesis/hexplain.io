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


Row = dict[str, Any]


def cases() -> list[Row]:
    """Every integer-family case, in authored order: layout, bundle, network and video terms, then the advisory
    shapes."""
    return layout_cases() + bundle_cases() + network_cases() + video_cases() + advisory_cases()


def layout_cases() -> list[Row]:
    """The DLV extents, each with every integer datatype the retained layout cases do not already exercise."""
    rows: list[Row] = []
    for prop in ["cellBitWidth", "dimensionSize", "dimensionStride", "chunkSize"]:
        base = LAYOUT
        if prop == "dimensionSize":
            base = base.replace("; dlv:dimensionSize 8", "")
        if prop == "chunkSize":
            base += "ex:l dlv:chunkOffsetsFromField ex:f. "
        owner = "ex:l" if prop == "cellBitWidth" else "ex:d"
        rows += [
            row(prop + " " + datatype, "dlv/dlv.ttl", PREFIX + base + f'{owner} dlv:{prop} "1"^^xsd:{datatype}.')
            for datatype in NAMES
            if datatype not in ("integer", "unsignedByte")  # Already exercised by retained layout cases.
        ]
        if prop in ("dimensionSize", "chunkSize"):
            rows.append(
                row(
                    prop + " cardinality boundary",
                    "dlv/dlv.ttl",
                    PREFIX + base + f"{owner} dlv:{prop} 1,2.",
                    False,
                    term("dlv", prop),
                )
            )
    return rows


def bundle_cases() -> list[Row]:
    """abnd:minParts and abnd:maxParts with every integer datatype, and their cardinality."""
    rows: list[Row] = []
    for prop in ["minParts", "maxParts"]:
        rows += [
            row(
                prop + " " + datatype,
                "aspect/bundle/bundle.ttl",
                PREFIX + f'ex:spec a a:PartSpec; a:pathPattern "*.x"; a:{prop} "1"^^xsd:{datatype}.',
            )
            for datatype in NAMES
            if datatype != "integer"
        ]
        rows.append(
            row(
                prop + " cardinality boundary",
                "aspect/bundle/bundle.ttl",
                PREFIX + f'ex:spec a a:PartSpec; a:pathPattern "*.x"; a:{prop} 1,2.',
                False,
                term("bundle", prop),
            )
        )
    return rows


def network_cases() -> list[Row]:
    """The network-flow counters with every integer datatype but their own."""
    return [
        row(
            prop + " " + datatype,
            "npv/net.ttl",
            f'<urn:packet> <{term("networkflow", prop)}> "1"^^<{term("xsd", datatype)}>.',
        )
        for prop in ["sourcePort", "destinationPort", "sequenceNumber", "acknowledgmentNumber"]
        for datatype in NAMES
        if datatype not in ("integer", "unsignedShort")
    ]


def video_cases() -> list[Row]:
    """The video module's own integer shape: every datatype of the family, on a count and on a rate term."""
    rows = [
        row(
            "video " + prop + " " + datatype,
            "vdv/video.ttl",
            f'<urn:stream> <{term("video", prop)}> "1"^^<{term("xsd", datatype)}>.',
        )
        for prop in ["audioChannels", "frameCount"]
        for datatype in NAMES
    ]
    rows.append(
        row(
            "video audioChannels decimal is not an integer",
            "vdv/video.ttl",
            f"<urn:stream> <{term('video', 'audioChannels')}> 1.0 .",
            False,
            term("video", "audioChannels"),
        )
    )
    return rows


def advisory_cases() -> list[Row]:
    """Shapes that only advise: without allow_warnings their result fails the run, at sh:Warning."""
    bddo, warning = "bddo/bddo.ttl", term("sh", "Warning")
    head = f"@prefix b:<{term('bddo', '')}> . @prefix ex:<urn:ex:> . "
    return [
        row(
            "fixed-point scale beyond the portable range is advised against",
            bddo,
            head + "ex:f b:fixedPointScale 5000 .",
            False,
            term("bddo", "fixedPointScale"),
            severity=warning,
            allow_warnings=False,
        ),
        row(
            "fixed-point scale within the portable range draws no advice",
            bddo,
            head + "ex:f b:fixedPointScale -16 .",
        ),
        row(
            "custom encoding with a byte-order-ambiguous charset is advised against",
            bddo,
            head + 'ex:e a b:CustomEncoding ; b:ianaCharset "UTF-16" .',
            False,
            term("bddo", "ianaCharset"),
            severity=warning,
            allow_warnings=False,
        ),
        row(
            "custom encoding re-spelling a registered charset is advised against",
            bddo,
            head + 'ex:e a b:CustomEncoding ; b:ianaCharset "shift_jis" .',
            False,
            term("bddo", "ianaCharset"),
            severity=warning,
            allow_warnings=False,
        ),
        row(
            "custom encoding with an unregistered byte-ordered charset draws no advice",
            bddo,
            head + 'ex:e a b:CustomEncoding ; b:ianaCharset "IBM437" .',
        ),
    ]
