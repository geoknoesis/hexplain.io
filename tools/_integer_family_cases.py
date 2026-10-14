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
    # The video module's own integer shape: every datatype of the family, on a count and on a rate term.
    for prop in ["audioChannels", "frameCount"]:
        for datatype in NAMES:
            add(
                "video " + prop + " " + datatype,
                "vdv/video.ttl",
                f'<urn:stream> <{term("video", prop)}> "1"^^<{term("xsd", datatype)}>.',
            )
    add(
        "video audioChannels decimal is not an integer",
        "vdv/video.ttl",
        f"<urn:stream> <{term('video', 'audioChannels')}> 1.0 .",
        False,
        term("video", "audioChannels"),
    )
    rows.extend(advisory_cases())
    return rows


def advisory_cases() -> list[dict[str, Any]]:
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
