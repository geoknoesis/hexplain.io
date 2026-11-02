"""Authored module contracts; expectations do not come from reading the shapes."""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term

#: The local prefix each family and aspect namespace is bound to in the authored bodies.
BINDINGS = {
    "ex": "urn:family-contract:",
    "a": "audio",
    "d": "docfont",
    "i": "image",
    "ar": "archive",
    "g": "geo",
    "r": "raster",
    "v": "video",
    "net": "networkflow",
    "s": "sampling",
    "sig": "signal",
    "t": "time",
    "enc": "encoding",
    "fs": "fsmeta",
    "integ": "integrity",
    "pack": "packaging",
    "sr": "spatialref",
    "pc": "pointcloud",
    "prov": "provenance",
    "geom": "geometry",
    "col": "color",
    "asec": "security",
    "b": "bddo",
    "skos": "skos",
    "xsd": "xsd",
    "dc": "dct",
}
PREFIX = (
    prefix_block(BINDINGS)
    + """ex:c a skos:Concept . ex:c2 a skos:Concept . ex:box a d:BoundingBox . ex:struct a b:Struct .
ex:entry a ar:ArchiveEntry .
"""
)
# Two distinct conforming values and an independently chosen invalid value.
KINDS = {
    "string": ('"text"', '"other"', "1"),
    "date": ('"2026-09-08T00:00:00Z"^^xsd:dateTime', '"2026-09-09T00:00:00Z"^^xsd:dateTime', '"2026-09-08"'),
    # A calendar date, not an instant: a marking decision is dated to a day, and an xsd:dateTime is
    # the wrong datatype for it rather than merely a more precise one.
    "calendarDate": ('"2026-09-08"^^xsd:date', '"2026-09-09"^^xsd:date', '"2026-09-08T00:00:00Z"^^xsd:dateTime'),
    "boolean": ("true", "false", '"true"'),
    "hex": ('"00"^^xsd:hexBinary', '"FF"^^xsd:hexBinary', '"00"'),
    "positive": ("1", "2", "0"),
    "nonnegative": ("0", "1", "-1"),
    "literal": ("1", "2", "ex:untyped"),
    "concept": ("ex:c", "ex:c2", "ex:untyped"),
    "box": ("ex:box", "ex:box", "ex:untyped"),
    "struct": ("ex:struct", "ex:struct", "ex:untyped"),
    "entry": ("ex:entry", "ex:entry", "ex:untyped"),
    "registration": ("sr:PixelCorner", "sr:PixelCenter", "ex:untyped"),
}
# Module, stable target context, property, value contract, maximum one value.
Contract = tuple[str, str, str, str, bool]
CONTRACTS: list[Contract] = []
SECURITY = "aspect/security/security.ttl"


def group(module: str, context: str, items: list[tuple[str, str, bool]]) -> None:
    for prop, kind, unique in items:
        CONTRACTS.append((module, context, prop, kind, unique))


def unique(*pairs: tuple[str, str]) -> list[tuple[str, str, bool]]:
    return [(p, k, True) for p, k in pairs]


group(
    "adv/audio.ttl",
    "ex:f sig:sampleRate 1.",
    unique(
        ("sig:sampleRate", "positive"),
        ("s:componentCount", "positive"),
        ("s:bitDepth", "positive"),
        ("t:duration", "literal"),
        ("enc:bitrate", "positive"),
        ("enc:codec", "concept"),
    ),
)
group(
    "adv/audio.ttl",
    'ex:f a:artist "artist".',
    unique(("a:artist", "string"), ("a:album", "string"), ("a:trackTitle", "string"), ("a:trackNumber", "positive")),
)
group(
    "dfv/docfont.ttl",
    "ex:f a d:Document.",
    [("dc:creator", "string", False)]
    + unique(("dc:title", "string"), ("dc:created", "date"), ("dc:modified", "date"), ("d:pageCount", "positive")),
)
group("dfv/docfont.ttl", "", [("d:hasBoundingBox", "box", False)])
group(
    "dfv/docfont.ttl",
    'ex:f d:fontFamily "font".',
    unique(("d:fontFamily", "string"), ("d:fontStyle", "string"), ("d:glyphCount", "positive")),
)
group(
    "idv/image.ttl",
    "ex:f a i:ImageHeader.",
    unique(
        ("r:width", "positive"), ("r:height", "positive"), ("s:bitDepth", "positive"), ("col:colorSpace", "concept")
    ),
)
group(
    "idv/image.ttl",
    "ex:f i:colorType 1.",
    [
        (p, "literal", p == "i:colorType")
        for p in ["i:colorType", "i:compressionMethod", "i:filterMethod", "i:interlaceMethod"]
    ],
)
group("axv/archive.ttl", "ex:f a ar:Archive.", [("pack:hasEntry", "entry", False)])
group(
    "axv/archive.ttl",
    "ex:f a ar:ArchiveEntry.",
    unique(
        ("fs:fileName", "string"),
        ("fs:fileSize", "nonnegative"),
        ("ar:compressedSize", "nonnegative"),
        ("integ:checksum", "hex"),
        ("fs:modificationTime", "date"),
        ("fs:isDirectory", "boolean"),
        ("enc:compression", "concept"),
    ),
)
group("gv/geo.ttl", 'ex:f sr:wktString "WKT".', [("sr:wktString", "string", True), ("sr:epsgCode", "positive", True)])
group(
    "gv/geo.ttl",
    "ex:f sr:originLatitude 1.",
    [("sr:originLatitude", "literal", True), ("sr:originLongitude", "literal", True)],
)
group("gv/geo.ttl", "", [("sr:pixelRegistration", "registration", True)])
group("gv/geo.ttl", "ex:f a g:VectorDataset.", [("geom:geometryType", "concept", True)])
group(
    "gv/geo.ttl",
    "ex:f pc:pointCount 0.",
    [("pc:pointCount", "nonnegative", True), ("pc:pointDataLayout", "struct", True)],
)
group(
    "gv/geo.ttl",
    'ex:f prov:acquisitionTime "2026-09-08T00:00:00Z"^^xsd:dateTime.',
    [
        ("prov:acquisitionTime", "date", True),
        ("prov:platformName", "string", False),
        ("prov:sensorType", "string", False),
    ],
)
group(
    "npv/net.ttl",
    "",
    [("net:sourceAddress", "string", True), ("net:destinationAddress", "string", True), ("net:tcpFlags", "hex", True)],
)
# The marking spine is flat -- no class of its own -- so every case below is activated by the
# presence of the property itself. A conforming sibling stays in the context so an invalid variant
# fails on exactly the path under test.
# Every property is repeatable on purpose -- a resource marked under two systems carries two of
# most of them -- so none of these cases asserts uniqueness.
group(
    SECURITY,
    'ex:f asec:markingSystem "US".',
    [
        (p, k, False)
        for p, k in [
            ("asec:markingSystem", "string"),
            ("asec:sensitivityLevel", "concept"),
            ("asec:sensitivityLevelText", "string"),
            ("asec:markingText", "string"),
            ("asec:markingIdentifier", "string"),
            ("asec:markingAuthority", "string"),
            ("asec:markingDate", "calendarDate"),
            ("asec:expiresOn", "calendarDate"),
            ("asec:marking", "concept"),
            ("asec:releasableTo", "string"),
        ]
    ],
)
# A declared level change must say when it takes effect, so the context carries the date; the
# missing-date counterexample is authored below, where the absence is the point.
group(
    SECURITY,
    'ex:f asec:levelChangeDate "2026-09-08"^^xsd:date.',
    [("asec:levelChangesTo", "concept", False), ("asec:levelChangeDate", "calendarDate", False)],
)
group(
    "vdv/video.ttl",
    "ex:f a v:VideoStream.",
    unique(
        ("r:width", "positive"),
        ("r:height", "positive"),
        ("enc:bitrate", "positive"),
        ("enc:codec", "concept"),
        ("col:colorSpace", "concept"),
        ("t:duration", "nonnegative"),
        ("v:audioChannels", "positive"),
    ),
)


def contract_cases() -> list[dict[str, Any]]:
    """valid / invalid / duplicate variants of every CONTRACTS entry."""
    from rdflib import Graph, URIRef

    result = []
    subject = URIRef("urn:family-contract:f")
    for module, context, prop, kind, one in CONTRACTS:
        first, second, bad = KINDS[kind]
        probe = Graph().parse(data=PREFIX + f"ex:f {prop} {first}.", format="turtle")
        predicate = next(probe.predicates(subject, None))
        base = Graph().parse(data=PREFIX + context, format="turtle")
        base.remove((subject, predicate, None))
        variants = [("valid", first, True), ("invalid", bad, False)]
        if one and first != second:
            variants.append(("duplicate", first + ", " + second, False))
        for name, value, expected in variants:
            data = base + Graph().parse(data=PREFIX + f"ex:f {prop} {value}.", format="turtle")
            result.append(
                row(
                    module + ":" + prop + ":" + name,
                    module,
                    data.serialize(format="turtle"),
                    expected,
                    str(predicate) if not expected else "",
                )
            )
    return result


def authored_cases() -> list[dict[str, Any]]:
    """Cases written one by one: severity, native functions, level changes, video literals."""
    result = []
    # Severity, both ways. Recording a resolved level without the verbatim text it came from is
    # valid and readable, so the case conforms once advisory results are allowed; the same case
    # without that allowance is the proof that the advisory result is actually produced. The
    # aspect treats a marking as a legal artefact whose written form matters independently of
    # what it resolves to, which is why this is worth saying at all.
    resolved_only = PREFIX + "ex:f asec:sensitivityLevel ex:c."
    result.append(
        row("security level without verbatim text is advisory only", SECURITY, resolved_only, allow_warnings=True)
    )
    result.append(
        row(
            "security level without verbatim text is reported",
            SECURITY,
            resolved_only,
            False,
            term("security", "sensitivityLevelText"),
            severity=term("sh", "Warning"),
            allow_warnings=False,
        )
    )
    result.append(
        row(
            "security level with verbatim text is complete",
            SECURITY,
            PREFIX + 'ex:f asec:sensitivityLevel ex:c ; asec:sensitivityLevelText "SECRET".',
            allow_warnings=False,
        )
    )
    # The native-function contract, both ways. A caller reading an unbound result needs to know
    # whether that outcome is described or a defect, so a native function must say which.
    fnp = prefix_block({"hxf": "hxf", "ex": BINDINGS["ex"]}, " ")
    for name, body, ok in [
        (
            "fn native function states when it is unbound",
            'ex:f a hxf:Function ; hxf:kind hxf:Native ; hxf:unboundWhen "out of range".',
            True,
        ),
        (
            "fn native function may declare itself total",
            "ex:f a hxf:Function ; hxf:kind hxf:Native ; hxf:total true.",
            True,
        ),
        ("fn native function without a contract is rejected", "ex:f a hxf:Function ; hxf:kind hxf:Native.", False),
        ("fn pure function needs no unbound contract", "ex:f a hxf:Function ; hxf:kind hxf:Pure.", True),
    ]:
        result.append(row(name, "fn/fn.ttl", fnp + body, ok))
    # A level change with no effective date: the minimum-count obligation's failing witness, which
    # no valid/invalid/duplicate variant of a present property can provide.
    result.append(
        row(
            "security level change without a date",
            SECURITY,
            PREFIX + "ex:f asec:levelChangesTo ex:c.",
            False,
            term("security", "levelChangeDate"),
        )
    )
    result.append(
        row(
            "security level change with a date",
            SECURITY,
            PREFIX + 'ex:f asec:levelChangesTo ex:c; asec:levelChangeDate "2026-09-08"^^xsd:date.',
        )
    )
    for name, body in [
        ("fractional duration", "t:duration 0.5"),
        ("integer frame rate", "v:frameRate 30"),
        ("positiveInteger audio channels", 'v:audioChannels "2"^^xsd:positiveInteger'),
        ("uint64 frame count", 'v:frameCount "18446744073709551615"^^xsd:unsignedLong'),
    ]:
        result.append(row("video " + name, "vdv/video.ttl", PREFIX + "ex:f a v:VideoStream; " + body + "."))
    return result


def cases() -> list[dict[str, Any]]:
    """Every authored family contract, from this module and every sibling case library."""
    from _acceptance_contract_cases import cases as acceptance
    from _closure_contract_cases import cases as closure
    from _core_contract_cases import cases as core
    from _integer_family_cases import cases as integers
    from _layout_property_cases import cases as layout_properties
    from _mapping_contract_cases import cases as mappings
    from _physical_property_cases import cases as physical
    from _range_contract_cases import cases as ranges
    from _raster_contract_cases import cases as raster
    from _record_contract_cases import cases as records
    from _remaining_contract_cases import cases as remaining
    from _requirement_contract_cases import cases as requirements
    from _review_2026_11_cases import cases as review_2026_11
    from _review_contract_cases import cases as review
    from _semantic_boundary_cases import cases as semantic
    from _spatial_contract_cases import cases as spatial
    from _structural_contract_cases import cases as structural
    from _structure_contract_cases import cases as structure
    from _tree_contract_cases import cases as tree

    everything = (
        contract_cases()
        + authored_cases()
        + mappings()
        + integers()
        + physical()
        + spatial()
        + requirements()
        + raster()
        + core()
        + layout_properties()
        + structural()
        + tree()
        + semantic()
        + remaining()
        + closure()
        + ranges()
        + review()
        + records()
        + acceptance()
        + structure()
        + review_2026_11()
    )
    # A case is about one obligation. An advisory result from some other shape -- a level with no
    # rank, say -- must not decide it, or every advisory constraint added later would silently
    # rewrite the expected outcome of cases that have nothing to do with it. Cases that are
    # themselves about an advisory result say so by setting allowWarnings explicitly.
    for entry in everything:
        entry.setdefault("allowWarnings", True)
    return everything
