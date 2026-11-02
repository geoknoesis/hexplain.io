"""Integer-family alternatives and semantic cardinality/value boundaries."""

from __future__ import annotations

from typing import Any

from _cases import PREFIXES, prefix_block, row

TYPES = [
    "integer",
    "positiveInteger",
    "nonNegativeInteger",
    "int",
    "long",
    "unsignedInt",
    "unsignedLong",
    "short",
    "unsignedShort",
    "byte",
    "unsignedByte",
]
SPATIALREF = "aspect/spatialref/spatialref.ttl"


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, module: str, ns: str, body: str, ok: bool, path: str = "") -> None:
        namespace = PREFIXES[ns.rsplit("/", 1)[-1]]
        prefix = prefix_block({"p": namespace, "ex": "urn:semantic-boundary:", "xsd": "xsd"}, " ")
        rows.append(
            row(
                "semantic " + name,
                module,
                prefix + body,
                ok,
                "https://hexplain.io/ns/" + ns + "#" + path if path else "",
            )
        )

    for aspect, prop, base in [
        ("sampling", "componentCount", ""),
        ("raster", "width", ""),
        ("raster", "dimensionExtent", "ex:f a p:ArrayDimension."),
        ("geometry", "dimensionality", ""),
    ]:
        for datatype in TYPES:
            if prop == "dimensionExtent" and datatype in ["short", "unsignedShort", "byte", "unsignedByte"]:
                continue
            add(
                aspect + " " + prop + " " + datatype,
                "aspect/" + aspect + "/" + aspect + ".ttl",
                "aspect/" + aspect,
                base + " ex:f p:" + prop + ' "2"^^xsd:' + datatype + ".",
                True,
            )
    for prop in ["frameRateNumerator", "frameRateDenominator"]:
        other = "frameRateDenominator" if prop == "frameRateNumerator" else "frameRateNumerator"
        for label, value, ok in [
            ("positiveInteger", '"1"^^xsd:positiveInteger', True),
            ("missing", None, False),
            ("duplicate", "1,2", False),
            ("wrong type", '"1"', False),
            ("zero", "0", False),
        ]:
            body = "ex:f p:" + other + " 1. " + ("ex:f p:" + prop + " " + value + "." if value else "")
            add(prop + " " + label, "vdv/video.ttl", "video", body, ok, "" if ok else prop)
    for prop, value in [
        ("aspectRatio", "1"),
        ("aspectRatio", '"wide"'),
        ("aspectRatio", '"1:1","2:1"'),
        ("frameRate", "1,2"),
        ("frameCount", "1,2"),
        ("frameCount", "18446744073709551616"),
        ("audioChannels", '"2"'),
        ("scanType", "p:Progressive,p:Interlaced"),
    ]:
        add("video " + prop + " " + value, "vdv/video.ttl", "video", "ex:f p:" + prop + " " + value + ".", False, prop)
    add("progressive scan", "vdv/video.ttl", "video", "ex:f p:scanType p:Progressive.", True)
    for prop in ["hasZ", "hasM"]:
        for value in ["true,false", '"true"']:
            add(
                prop + " " + value,
                "aspect/geometry/geometry.ttl",
                "aspect/geometry",
                "ex:f p:" + prop + " " + value + ".",
                False,
                prop,
            )
    add(
        "dimension duplicate",
        "aspect/geometry/geometry.ttl",
        "aspect/geometry",
        "ex:f p:dimensionality 2,3.",
        False,
        "dimensionality",
    )
    for aspect, prop, values in [("time", "duration", "1,2"), ("signal", "sampleRate", "1,2")]:
        add(
            aspect + " duplicate",
            "aspect/" + aspect + "/" + aspect + ".ttl",
            "aspect/" + aspect,
            "ex:f p:" + prop + " " + values + ".",
            False,
            prop,
        )
    for prop, values in [("height", "0"), ("bandCount", "0"), ("hasGroup", '"group"')]:
        add(
            "raster " + prop + " invalid",
            "aspect/raster/raster.ttl",
            "aspect/raster",
            "ex:f p:" + prop + " " + values + ".",
            False,
            prop,
        )
    for prop, values in [
        ("wktString", '""'),
        ("wktString", '"one","two"'),
        ("coordinateEpoch", "2026.5,2027.5"),
        ("crsIdentifier", "ex:a,ex:b"),
    ]:
        add(
            "crs " + prop + " " + values,
            SPATIALREF,
            "aspect/spatialref",
            "ex:f a p:CoordinateReferenceSystem; p:" + prop + " " + values + ".",
            False,
            prop,
        )
    for prop in ["hasCRS", "hasGeoTransform", "hasRationalTransform"]:
        add("literal " + prop, SPATIALREF, "aspect/spatialref", "ex:f p:" + prop + ' "value".', False)
    return rows
