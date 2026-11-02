"""Execute the specification's actual SPARQL function bodies against independent fixtures."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef, Variable

ROOT = Path(__file__).resolve().parents[1]
FN = Namespace("https://hexplain.io/ns/fn#")
SH = Namespace("http://www.w3.org/ns/shacl#")
SR = Namespace("https://hexplain.io/ns/aspect/spatialref#")
RASTER = Namespace("https://hexplain.io/ns/aspect/raster#")
SAMPLING = Namespace("https://hexplain.io/ns/aspect/sampling#")
NODE = URIRef("urn:function-contract:node")


def check() -> int:
    functions = Graph().parse(ROOT / "specification/fn/fn.ttl")
    checked: set[str] = set()
    calls = 0

    def evaluate(name: str, data: Graph, *args: Any) -> list[Any]:
        nonlocal calls
        checked.add(name)
        calls += 1
        query = str(functions.value(FN[name], SH.select))
        bindings = {
            f"arg{i + 1}": value if isinstance(value, (URIRef, Literal)) else Literal(value)
            for i, value in enumerate(args)
        }
        values = []
        for binding in data.query(query, initBindings=bindings, initNs={"xsd": XSD}).bindings:
            value = binding.get(Variable("result"))
            if value is not None:
                assert isinstance(value, Literal), (name, "nonliteral function result")
                expected_type = functions.value(FN[name], SH.returnType)
                # RDFLib's mixed double/decimal arithmetic returns decimal in calibrate's
                # default-coefficient branch. Keep this host limitation explicit and narrow.
                promotion_limit = name == "calibrate" and expected_type == XSD.double and value.datatype == XSD.decimal
                assert value.datatype == expected_type or promotion_limit, (name, value.datatype)
                values.append(value.toPython())
        return values

    def affine(registration: str = "PixelCorner") -> Graph:
        data = Graph()
        for prop, value in (
            ("originX", 100),
            ("originY", 200),
            ("scaleX", 2),
            ("scaleY", -3),
            ("skewX", 0.5),
            ("skewY", -0.25),
        ):
            data.add((NODE, SR[prop], Literal(value)))
        data.add((NODE, SR.pixelRegistration, SR[registration]))
        return data

    for registration in ("PixelCorner", "PixelCenter"):
        data = affine(registration)
        for column, row in ((0, 0), (0.5, 0.5), (-0.25, -0.5), (2.75, 1.25)):
            x, y = 100 + 2 * column + 0.5 * row, 200 - 0.25 * column - 3 * row
            assert evaluate("worldX", data, NODE, column, row) == [x]
            assert evaluate("worldY", data, NODE, column, row) == [y]
            assert evaluate("column", data, NODE, x, y) == [math.floor(column)]
            assert evaluate("row", data, NODE, x, y) == [math.floor(row)]
    for name, required in (("worldX", "originX"), ("worldY", "originY"), ("column", "originX"), ("row", "originY")):
        data = affine()
        data.remove((NODE, SR[required], None))
        assert not evaluate(name, data, NODE, 0, 0), (name, "missing coefficient")
        data = affine()
        data.add((NODE, SR.scaleX, Literal(3)))
        assert not evaluate(name, data, NODE, 0, 0), (name, "ambiguous coefficient")
    singular = affine()
    for prop in ("scaleX", "scaleY", "skewX", "skewY"):
        singular.set((NODE, SR[prop], Literal(1)))
    for name in ("column", "row"):
        assert not evaluate(name, singular, NODE, 100, 200), (name, "singular inverse")
    north_up = affine()
    north_up.remove((NODE, SR.skewX, None))
    north_up.remove((NODE, SR.skewY, None))
    assert evaluate("worldX", north_up, NODE, 0.5, 0.5) == [101.0]
    assert evaluate("worldY", north_up, NODE, 0.5, 0.5) == [198.5]

    data = Graph()
    assert evaluate("calibrate", data, NODE, 100) == [100.0]
    data.add((NODE, RASTER.sampleScale, Literal(0.5)))
    data.add((NODE, RASTER.sampleOffset, Literal(-2)))
    assert evaluate("calibrate", data, NODE, 100) == [48.0]
    data.add((NODE, RASTER.sampleScale, Literal(2)))
    assert not evaluate("calibrate", data, NODE, 100)
    data.set((NODE, RASTER.sampleScale, Literal("invalid")))
    assert not evaluate("calibrate", data, NODE, 100)

    data = Graph()
    assert evaluate("isNoData", data, NODE, 7) == [False]
    data.add((NODE, RASTER.noDataValue, Literal(7)))
    assert evaluate("isNoData", data, NODE, 7) == [True]
    assert evaluate("isNoData", data, NODE, 8) == [False]
    data.add((NODE, RASTER.noDataValue, Literal(8)))
    assert not evaluate("isNoData", data, NODE, 7)
    data.remove((NODE, RASTER.noDataValue, None))
    parent = URIRef("urn:function-contract:parent")
    data.add((parent, RASTER.hasBand, NODE))
    data.add((parent, RASTER.noDataValue, Literal(9)))
    assert evaluate("isNoData", data, NODE, 9) == [True]
    data.add((NODE, RASTER.noDataValue, Literal(7)))
    assert evaluate("isNoData", data, NODE, 9) == [False]
    data.set((NODE, RASTER.noDataValue, Literal(float("nan"))))
    assert evaluate("isNoData", data, NODE, float("nan")) == [True]
    # An integer format compares exactly: 2^63 - 1 and 2^63 - 2 are one double but two integers.
    data = Graph()
    data.add((NODE, SAMPLING.sampleFormat, SAMPLING.SignedInteger))
    data.add((NODE, SAMPLING.bitDepth, Literal(64)))
    data.add((NODE, RASTER.noDataValue, Literal("9223372036854775807", datatype=XSD.long)))
    assert evaluate("isNoData", data, NODE, Literal("9223372036854775807", datatype=XSD.long)) == [True]
    assert evaluate("isNoData", data, NODE, Literal("9223372036854775806", datatype=XSD.long)) == [False]
    data.set((NODE, RASTER.noDataValue, Literal(-9999.0)))
    assert evaluate("isNoData", data, NODE, -9999) == [True]
    assert evaluate("isNoData", data, NODE, -9998.5) == [False]
    pure = {str(function).removeprefix(str(FN)) for function in functions.subjects(RDF.type, SH.SPARQLFunction)}
    assert checked == pure, ("A pure specification function has no executable contract", pure - checked)
    return calls
