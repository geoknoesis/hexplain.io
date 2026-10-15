"""Table, record, geometry-record, raster grid metadata and sample-format witnesses: activation, membership,
cardinality and ordering, both ways."""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term

TABULAR = "aspect/tabular/tabular.ttl"
GEOMETRY = "aspect/geometry/geometry.ttl"
RASTER = "aspect/raster/raster.ttl"
SAMPLING = "aspect/sampling/sampling.ttl"


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(aspect: str, module: str, name: str, body: str, ok: bool, path: str = "") -> None:
        prefix = prefix_block({"p": aspect, "ex": "urn:record-contract:", "xsd": "xsd"}, " ")
        rows.append(row(aspect + " " + name, module, prefix + body, ok, term(aspect, path) if path else ""))

    for name, body, ok, path in [
        ("table with fewer records than its count", "ex:t a p:Table; p:rowCount 2; p:hasRecord ex:r.", True, ""),
        ("table with as many records as its count", "ex:t p:rowCount 1; p:hasRecord ex:r.", True, ""),
        ("table with more records than its count", "ex:t p:rowCount 1; p:hasRecord ex:r, ex:s.", False, ""),
        ("empty table", "ex:t a p:Table; p:rowCount 0.", True, ""),
        ("table with two row counts", "ex:t a p:Table; p:rowCount 1, 2.", False, "rowCount"),
        ("untyped table with two row counts", "ex:t p:hasField ex:c; p:rowCount 1, 2.", False, "rowCount"),
        ("literal column", "ex:t p:hasField 1.", False, "hasField"),
        ("literal record", "ex:t p:hasRecord 1.", False, "hasRecord"),
        ("record of two tables", "ex:t p:hasRecord ex:r. ex:u p:hasRecord ex:r.", False, ""),
    ]:
        add("tabular", TABULAR, name, body, ok, path)
    for name, body, ok, path in [
        ("record with one geometry", "ex:r a p:GeometryRecord; p:hasGeometry ex:g.", True, ""),
        ("record without geometry", "ex:r a p:GeometryRecord.", False, "hasGeometry"),
        ("record with two geometries", "ex:r p:hasGeometry ex:g, ex:h.", False, "hasGeometry"),
        ("literal geometry", 'ex:r p:hasGeometry "POINT (1 2)".', False, "hasGeometry"),
        ("geometry of two records", "ex:r p:hasGeometry ex:g. ex:s p:hasGeometry ex:g.", False, ""),
        ("collection with members", "ex:c a p:Geometry; p:hasMember ex:a, ex:b.", True, ""),
        ("member of two collections", "ex:c p:hasMember ex:a. ex:d p:hasMember ex:a.", False, ""),
        ("member of itself", "ex:c p:hasMember ex:c.", False, ""),
        ("membership cycle", "ex:c p:hasMember ex:d. ex:d p:hasMember ex:c.", False, ""),
        ("literal member", 'ex:c p:hasMember "POINT (1 2)".', False, "hasMember"),
    ]:
        add("geometry", GEOMETRY, name, body, ok, path)
    for name, body, ok, path in [
        ("format no-data value", 'ex:g a p:RasterGrid; p:formatNoDataValue "-32767"^^xsd:short.', True, ""),
        ("text format no-data value", 'ex:g p:formatNoDataValue "none".', False, "formatNoDataValue"),
        ("two format no-data values", "ex:g p:formatNoDataValue -32767, -32768.", False, "formatNoDataValue"),
        ("ordered bounds", 'ex:g p:boundsMinX "0.0"^^xsd:double; p:boundsMaxX "0.0"^^xsd:double.', True, ""),
        ("inverted bounds", 'ex:g p:boundsMinY "2.0"^^xsd:double; p:boundsMaxY "1.0"^^xsd:double.', False, ""),
        ("node registration", "ex:g p:boundsRegistration p:nodeRegistration.", True, ""),
        ("unknown registration", "ex:g p:boundsRegistration ex:corner.", False, "boundsRegistration"),
        ("ordered value range", 'ex:g p:minimumValue "-1.0"^^xsd:double; p:maximumValue "9.0"^^xsd:double.', True, ""),
        (
            "inverted value range",
            'ex:g p:minimumValue "9.0"^^xsd:double; p:maximumValue "-1.0"^^xsd:double.',
            False,
            "",
        ),
        ("grid-level calibration", 'ex:g a p:RasterGrid; p:sampleScale "0.5"^^xsd:double.', True, ""),
    ]:
        add("raster", RASTER, name, body, ok, path)
    for literal in ('"1.5"^^xsd:double', '"1.5"^^xsd:float', "1.5", "-32767"):
        add("raster", RASTER, "format no-data value " + literal, f"ex:g p:formatNoDataValue {literal}.", True)
    for prop in ("boundsMinX", "boundsMaxX", "boundsMinY", "boundsMaxY", "minimumValue", "maximumValue"):
        add("raster", RASTER, prop + " decimal", f"ex:g p:{prop} 1.5.", False, prop)
        add("raster", RASTER, prop + " twice", f'ex:g p:{prop} "1.0"^^xsd:double, "2.0"^^xsd:double.', False, prop)
    add(
        "raster",
        RASTER,
        "two registrations",
        "ex:g p:boundsRegistration p:nodeRegistration, p:cellRegistration.",
        False,
    )
    for name, body, ok, path in [
        ("format name not a string", "ex:b p:sampleFormatName 1.", False, "sampleFormatName"),
        ("two format names", 'ex:b p:sampleFormatName "float", "signedInteger".', False, "sampleFormatName"),
    ]:
        add("sampling", SAMPLING, name, body, ok, path)
    for name, body, ok, path in [
        ("format name", 'ex:b p:sampleFormatName "float".', True, ""),
        ("unknown format name", 'ex:b p:sampleFormatName "int16".', False, "sampleFormatName"),
        (
            "agreeing format and name",
            'ex:b p:sampleFormatName "signedInteger"; p:sampleFormat p:SignedInteger.',
            True,
            "",
        ),
        (
            "contradicting format and name",
            'ex:b p:sampleFormatName "float"; p:sampleFormat p:SignedInteger.',
            False,
            "",
        ),
    ]:
        add("sampling", SAMPLING, name, body, ok, path)
    return rows
