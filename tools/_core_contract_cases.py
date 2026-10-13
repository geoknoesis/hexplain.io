"""Encoding, mapping and layout-link contracts with independent fixtures."""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term

PREFIX = (
    prefix_block(
        {
            "c": "hexplain",
            "b": "bddo",
            "d": "dlv",
            "ex": "urn:core-contract:",
            "skos": "skos",
            "owl": "owl",
            "rdf": "rdf",
            "xsd": "xsd",
        }
    )
    + """ex:codec a skos:Concept . ex:codec2 a skos:Concept . ex:layout a d:DataLayout . ex:layout2 a d:DataLayout .
ex:step a c:EncodingStep; c:codec ex:codec . ex:step2 a c:EncodingStep; c:codec ex:codec2 .
ex:param a c:CodecParameter; c:parameterName "level"; c:parameterValue 1 .
"""
)
MODULE = "hexplain/core.ttl"


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, body: str, ok: bool, path: str = "") -> None:
        rows.append(row("core " + name, MODULE, PREFIX + body, ok, term("hexplain", path) if path else ""))

    for prop, base, good, second, bad, required in [
        ("isEncodedWith", "", "ex:codec", "ex:codec2", "ex:untyped", False),
        ("codec", "ex:f a c:EncodingStep.", "ex:codec", "ex:codec2", "ex:untyped", True),
        ("hasDataLayout", "ex:f a b:Field.", "ex:layout", "ex:layout2", "ex:untyped", False),
        ("hasEncodingStep", "", "(ex:step)", "(ex:step2)", '"steps"', False),
        ("parameterName", "ex:f a c:CodecParameter; c:parameterValue 1.", '"level"', '"other"', "1", True),
        ("parameterValue", 'ex:f a c:CodecParameter; c:parameterName "level".', "1", "2", None, True),
        (
            "valueDatatype",
            'ex:f a b:Field; c:valueExpression "value".',
            "xsd:integer",
            "xsd:string",
            '"integer"',
            False,
        ),
    ]:
        variants: list[tuple[str, str | None, bool]] = [
            ("valid", good, True),
            ("duplicate", good + "," + second, False),
        ]
        if bad:
            variants.append(("bad", bad, False))
        if required:
            variants.append(("missing", None, False))
        if prop in ["codec", "isEncodedWith"]:
            variants.append(("literal", '"codec"', False))
        # hexplain:codec and hexplain:parameterValue each moved into an sh:xone alternative
        # (run-time codec selection; a parameter's expression form) alongside a sibling
        # property, each branch checking presence (sh:minCount) only. Absence of both
        # alternatives reports the xone violation itself, which carries no sh:resultPath;
        # a duplicate value still trips the sibling maxCount clause outside the xone, which does.
        NO_PATH = {("codec", "missing"), ("parameterValue", "missing")}
        for label, value, ok in variants:
            path = "" if ok or (prop, label) in NO_PATH else prop
            add(
                prop + " " + label,
                base + (" ex:f c:" + prop + " " + value + "." if value is not None else ""),
                ok,
                path,
            )
    add("untyped layout owner", "ex:f c:hasDataLayout ex:layout.", False)
    add("invalid pipeline member", "ex:f c:hasEncodingStep (ex:untyped).", False)
    add(
        "invalid codec parameter",
        "ex:f a c:EncodingStep; c:codec ex:codec; c:codecParameter ex:untyped.",
        False,
        "codecParameter",
    )
    # Register lifecycle: a status from the closed set, at most one; a retired entry is
    # owl:deprecated, and a superseded one names its successor.
    add("status valid", "ex:f c:status c:statusValid.", True)
    add("status deprecated", "ex:f c:status c:statusDeprecated; owl:deprecated true.", True)
    add(
        "status superseded",
        "ex:f c:status c:statusSuperseded; owl:deprecated true; <http://purl.org/dc/terms/isReplacedBy> ex:g.",
        True,
    )
    add("status unknown value", "ex:f c:status ex:retired.", False, "status")
    add("status twice", "ex:f c:status c:statusValid, c:statusDeprecated; owl:deprecated true.", False, "status")
    add("deprecated status without owl:deprecated", "ex:f c:status c:statusDeprecated.", False)
    add("superseded status without successor", "ex:f c:status c:statusSuperseded; owl:deprecated true.", False)
    add("typed codec parameter", "ex:f a c:EncodingStep; c:codec ex:codec; c:codecParameter ex:param.", True)
    for cls in ["rdf:Property", "owl:DatatypeProperty", "owl:ObjectProperty", "owl:AnnotationProperty"]:
        add("mapping " + cls, "ex:f a b:Field; c:mapsToProperty ex:p. ex:p a " + cls + ".", True)
    add("mapping untyped property", "ex:f a b:Field; c:mapsToProperty ex:unknown.", False, "mapsToProperty")
    add("mapping literal property", 'ex:f a b:Field; c:mapsToProperty "p".', False, "mapsToProperty")
    add("mapping untyped owner", "ex:f c:mapsToProperty ex:p. ex:p a rdf:Property.", False)
    return rows
