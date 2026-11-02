"""Authored protection, acquisition and temporal boundary contracts.

These expectations follow the modules' declared meanings. No shape graph is inspected
to construct a passing fixture or choose the expected verdict.
"""

from __future__ import annotations

from typing import Any

from _cases import row

PREFIX = """@prefix p:<https://hexplain.io/ns/aspect/protection#>.
@prefix b:<https://hexplain.io/ns/bddo#>.
@prefix v:<https://hexplain.io/ns/aspect/provenance#>.
@prefix s:<https://hexplain.io/ns/aspect/signal#>.
@prefix t:<https://hexplain.io/ns/aspect/time#>.
@prefix xsd:<http://www.w3.org/2001/XMLSchema#>.
@prefix skos:<http://www.w3.org/2004/02/skos/core#>.
@prefix e:<urn:acceptance:>.
"""
PROTECTION = "https://hexplain.io/ns/aspect/protection#"


def cases() -> list[dict[str, Any]]:
    result = []
    context = """e:f a b:Field. e:g a b:Field. e:struct a b:Struct.
e:algorithm a skos:Concept. e:algorithm2 a skos:Concept.
e:range a p:ByteRange; p:fromField e:f; p:toField e:g.
e:range2 a p:ByteRange; p:fromField e:g; p:toField e:g.
"""
    # Every required member is independently removed, duplicated and mistyped.
    declarations = [
        ("EncryptedRegion", [("region", "e:f", "e:struct"), ("cipher", "e:algorithm", "e:algorithm2")]),
        (
            "Signature",
            [
                ("signatureAlgorithm", "e:algorithm", "e:algorithm2"),
                ("signatureValueField", "e:f", "e:g"),
                ("covers", "e:range", "e:range2"),
            ],
        ),
        (
            "ErrorCorrection",
            [
                ("errorCorrectingCode", "e:algorithm", "e:algorithm2"),
                ("dataRange", "e:range", "e:range2"),
                ("parityRange", "e:range", "e:range2"),
            ],
        ),
        ("ByteRange", [("fromField", "e:f", "e:g"), ("toField", "e:g", "e:f")]),
    ]
    for kind, members in declarations:
        for typed in (True, False):
            source = "e:declaration a p:" + kind + ". " if typed else ""
            source += "".join(f"e:declaration p:{prop} {value}. " for prop, value, _ in members)
            result.append(
                row(
                    f"acceptance {kind} {'typed' if typed else 'property activated'}",
                    "aspect/protection/protection.ttl",
                    PREFIX + context + source,
                )
            )
        for prop, _, alternate in members:
            for variant in ("missing", "duplicate", "wrong class"):
                source = f"e:declaration a p:{kind}. "
                for name, value, _ in members:
                    if name == prop:
                        if variant == "missing":
                            continue
                        value = value + ", " + alternate if variant == "duplicate" else "e:untyped"
                    source += f"e:declaration p:{name} {value}. "
                result.append(
                    row(
                        f"acceptance {kind} {prop} {variant}",
                        "aspect/protection/protection.ttl",
                        PREFIX + context + source,
                        False,
                        PROTECTION + prop,
                    )
                )
    for prop, cls in (("hasPlatform", "Platform"), ("hasSensorModel", "SensorModel")):
        for label, value, context, expected in (
            ("linked", "e:linked", f"e:linked a v:{cls}. ", True),
            ("blank linked", "_:linked", f"_:linked a v:{cls}. ", True),
            ("untyped", "e:linked", "", False),
            ("text is not a resource", '"name"', "", False),
        ):
            result.append(
                row(
                    f"acceptance acquisition {prop} {label}",
                    "aspect/provenance/provenance.ttl",
                    PREFIX + context + f"e:acquisition v:{prop} {value}. ",
                    expected,
                    "" if expected else "https://hexplain.io/ns/aspect/provenance#" + prop,
                )
            )
    for module, prefix, prop, variants in (
        (
            "signal",
            "s",
            "sampleRate",
            [
                ("fractional hertz", "0.5", True),
                ("zero", "0.0", False),
                ("negative", "-0.5", False),
                ("two rates", "0.5, 1.5", False),
            ],
        ),
        (
            "time",
            "t",
            "duration",
            [
                ("empty duration", "0", True),
                ("fractional seconds", "0.5", True),
                ("negative", "-0.5", False),
                ("two durations", "0, 1", False),
                ("text seconds", '"1"', False),
                ("binary float", "1e0", False),
            ],
        ),
    ):
        for label, value, expected in variants:
            result.append(
                row(
                    f"acceptance {module} {label}",
                    f"aspect/{module}/{module}.ttl",
                    PREFIX + f"e:content {prefix}:{prop} {value}. ",
                    expected,
                    "" if expected else f"https://hexplain.io/ns/aspect/{module}#{prop}",
                )
            )
    return result
