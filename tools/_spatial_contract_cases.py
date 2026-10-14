"""Independent coordinate-model property and required-value counterexamples."""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term

PREFIX = prefix_block({"ex": "urn:spatial-contract:", "s": "spatialref", "xsd": "xsd"})
MODULE = "aspect/spatialref/spatialref.ttl"
OFFSETS = "lineOffset sampleOffset latitudeOffset longitudeOffset heightOffset"
SCALES = "lineScale sampleScale latitudeScale longitudeScale heightScale"
VECTORS = "lineNumerator lineDenominator sampleNumerator sampleDenominator"


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, body: str, ok: bool, path: str = "") -> None:
        rows.append(row("spatial " + name, MODULE, PREFIX + body, ok, term("spatialref", path) if path else ""))

    models = [
        ("GeoTransform", "originX originY scaleX scaleY", "skewX skewY"),
        ("GroundControlPoint", "gcpPixelX gcpPixelY gcpX gcpY", "gcpZ"),
        ("CubicRationalTransform", OFFSETS + " " + SCALES, ""),
    ]
    for cls, required, optional in models:
        props = (required + " " + optional).split()
        base = {p: '"1"^^xsd:double' for p in props}
        if cls == "CubicRationalTransform":
            base.update({p: "(" + " ".join(['"1"^^xsd:double'] * 20) + ")" for p in VECTORS.split()})
            base["polynomialBasis"] = "ex:basis"

        def body(values: dict[str, str], cls: str = cls) -> str:
            return "ex:f a s:" + cls + ". " + "".join("ex:f s:" + p + " " + v + ". " for p, v in values.items())

        add(cls + " valid", body(base), True)
        for prop in props:
            for label, value in [
                ("wrong type", '"1"'),
                ("duplicate", '"1"^^xsd:double,"2"^^xsd:double'),
                ("nonfinite", '"INF"^^xsd:double'),
            ]:
                changed = dict(base)
                changed[prop] = value
                add(cls + " " + prop + " " + label, body(changed), False, prop)
            if prop in required.split():
                changed = dict(base)
                del changed[prop]
                add(cls + " " + prop + " missing", body(changed), False, prop)
            if prop in SCALES.split():
                changed = dict(base)
                changed[prop] = '"0"^^xsd:double'
                add(cls + " " + prop + " zero", body(changed), False, prop)
        if cls == "CubicRationalTransform":
            for prop in VECTORS.split() + ["polynomialBasis"]:
                duplicate = "ex:other" if prop == "polynomialBasis" else "(" + " ".join(['"2"^^xsd:double'] * 20) + ")"
                for label, given in [
                    ("missing", None),
                    ("literal", '"bad"'),
                    ("duplicate", base[prop] + "," + duplicate),
                ]:
                    changed = dict(base)
                    if given is None:
                        del changed[prop]
                    else:
                        changed[prop] = given
                    add(cls + " " + prop + " " + label, body(changed), False, prop)
    for prop, valid, bad in [
        ("wktString", '"GEOGCRS[...]"', "1"),
        ("crsIdentifier", "ex:crs", '"EPSG:4326"'),
        ("coordinateEpoch", "2026.5", '"2026.5"'),
    ]:
        add(prop + " valid", "ex:f a s:CoordinateReferenceSystem; s:" + prop + " " + valid + ".", True)
        add(prop + " invalid", "ex:f a s:CoordinateReferenceSystem; s:" + prop + " " + bad + ".", False, prop)
    return rows
