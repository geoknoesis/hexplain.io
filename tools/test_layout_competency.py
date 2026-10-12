"""Executable layout and compound-dataset contracts, without inference or rules.

The retained corpus (specification/validation/test/layout-competency.tsv) is compared with the
cases this gate generates; after changing a case, regenerate it with ``--write``.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

from _layout_property_cases import LAYOUT, PREFIX
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "specification/validation/test/layout-competency.tsv"
SHAPES = ["specification/dlv/dlv.ttl", "specification/aspect/bundle/bundle.ttl"]
SH = Namespace("http://www.w3.org/ns/shacl#")
DLV = "https://hexplain.io/ns/dlv#"
BUNDLE = "https://hexplain.io/ns/aspect/bundle#"

Case = tuple[str, str, bool, str]


def cases() -> list[Case]:
    """(name, Turtle body, expected conformance, expected result path) in authored order."""
    rows: list[Case] = []

    def case(name: str, data: str, ok: bool, path: str = "") -> None:
        rows.append((name, data, ok, path))

    for prop in ["cellBitWidth", "dimensionSize", "dimensionStride", "chunkSize"]:
        owner = "ex:l" if prop == "cellBitWidth" else "ex:d"
        base = LAYOUT
        if prop == "dimensionSize":
            base = base.replace("; dlv:dimensionSize 8", "")
        if prop == "chunkSize":
            base += "ex:l dlv:chunkOffsetsFromField ex:f. "
        for label, value, ok in [
            ("integer", "3", True),
            ("typed integer", '"3"^^xsd:unsignedByte', True),
            ("zero", "0", False),
            ("negative", "-1", False),
            ("fraction", "1.5", False),
            ("string", '"3"', False),
        ]:
            case(prop + " " + label, base + f"{owner} dlv:{prop} {value}.", ok, "" if ok else DLV + prop)
    case("MSB packed", LAYOUT + "ex:l dlv:cellBitWidth 1; dlv:cellPackingOrder b:MSBFirst.", True)
    case("LSB packed", LAYOUT + "ex:l dlv:cellBitWidth 4; dlv:cellPackingOrder b:LSBFirst.", True)
    case("dynamic packed width", LAYOUT + "ex:l dlv:cellBitWidthFromField ex:f.", True)
    case("conflicting packed widths", LAYOUT + "ex:l dlv:cellBitWidth 4; dlv:cellBitWidthFromField ex:f.", False)
    # An XSD rdfs:range holds wherever the property is used, so a non-integer width is rejected even
    # outside a layout (it used to validate because no layout shape was activated).
    case("unrelated metadata", 'ex:x dlv:cellBitWidth "verbatim".', False, DLV + "cellBitWidth")
    for prop in ["minParts", "maxParts"]:
        for label, value, ok in [
            ("zero", "0", True),
            ("integer", "2", True),
            ("fraction", "0.5", False),
            ("negative", "-1", False),
            ("string", '"2"', False),
        ]:
            case(
                prop + " " + label,
                f'ex:s a a:PartSpec; a:pathPattern "*.x"; a:{prop} {value}.',
                ok,
                "" if ok else BUNDLE + prop,
            )
    profile = (
        'ex:profile a a:BundleProfile; a:partSpec ex:spec. ex:spec a a:PartSpec; a:extension ".x"; a:required true; '
        "a:partRole ex:role. "
    )
    asset = "ex:asset a a:Asset; dct:conformsTo ex:profile. "
    part = "ex:asset a:hasPart ex:p. ex:p a a:Part; a:partRole ex:role. "
    case("required compound part", profile + asset + part, True)
    case("missing required compound part", profile + asset, False)
    case(
        "nested compound scoped independently",
        profile + asset + part + "ex:p a a:Asset; dct:conformsTo ex:profile.",
        False,
    )
    case(
        "nested compound satisfied",
        profile
        + asset
        + part
        + "ex:p a a:Asset; dct:conformsTo ex:profile; a:hasPart ex:leaf. ex:leaf a a:Part; a:partRole ex:role.",
        True,
    )
    case("primary typed part", asset + part + "ex:asset a:primaryPart ex:p.", True)
    case("literal primary", asset + 'ex:asset a:primaryPart "part".', False, BUNDLE + "primaryPart")
    case("inverted count range", 'ex:s a a:PartSpec; a:pathPattern "*.x"; a:minParts 3; a:maxParts 2.', False)
    case("required zero contradiction", 'ex:s a a:PartSpec; a:pathPattern "*.x"; a:required true; a:minParts 0.', False)
    case(
        "primary alone satisfies required role",
        profile + asset + "ex:asset a:primaryPart ex:p. ex:p a a:Part; a:partRole ex:role.",
        True,
    )
    case("primary wrong role still rejects", profile + asset + "ex:asset a:primaryPart ex:p. ex:p a a:Part.", False)
    case("literal compound member", asset + 'ex:asset a:hasPart "file".', False, BUNDLE + "hasPart")
    case("untyped compound member", asset + "ex:asset a:hasPart ex:p.", False, BUNDLE + "hasPart")
    case("unrelated hasPart remains out of scope", 'ex:x a:hasPart "verbatim".', True)
    # Cross-property, cardinality and explicit-target controls (not physical decoding).
    for name, tail, ok, path in [
        ("packing order without width", "ex:l dlv:cellPackingOrder b:MSBFirst.", False, ""),
        (
            "unknown packing order",
            "ex:l dlv:cellBitWidth 3; dlv:cellPackingOrder ex:Unknown.",
            False,
            "cellPackingOrder",
        ),
        (
            "literal packing order",
            'ex:l dlv:cellBitWidth 3; dlv:cellPackingOrder "MSBFirst".',
            False,
            "cellPackingOrder",
        ),
        (
            "two packing orders",
            "ex:l dlv:cellBitWidth 3; dlv:cellPackingOrder b:MSBFirst,b:LSBFirst.",
            False,
            "cellPackingOrder",
        ),
        ("two packed widths", "ex:l dlv:cellBitWidth 3,4.", False, "cellBitWidth"),
        ("untyped width field", "ex:l dlv:cellBitWidthFromField ex:unknown.", False, "cellBitWidthFromField"),
        ("literal width field", 'ex:l dlv:cellBitWidthFromField "width".', False, "cellBitWidthFromField"),
        ("dynamic packing order", "ex:l dlv:cellBitWidthFromField ex:f; dlv:cellPackingOrder b:LSBFirst.", True, ""),
        ("three bit cross byte packing", "ex:l dlv:cellBitWidth 3; dlv:cellPackingOrder b:MSBFirst.", True, ""),
        ("wide integer width", "ex:l dlv:cellBitWidth 18446744073709551616.", True, ""),
        ("two strides", "ex:d dlv:dimensionStride 1,2.", False, "dimensionStride"),
        ("untyped stride field", "ex:d dlv:dimensionStrideFromField ex:unknown.", False, "dimensionStrideFromField"),
        (
            "literal stride expression",
            "ex:d dlv:dimensionStrideFromExpression 8.",
            False,
            "dimensionStrideFromExpression",
        ),
        ("literal axis", 'ex:d dlv:hasAxis "x".', False, "hasAxis"),
    ]:
        case(name, LAYOUT + tail, ok, DLV + path if path else "")
    case("unmarked unrelated packing metadata", 'ex:x dlv:cellPackingOrder "raw".', True)
    case(
        "child does not satisfy parent role",
        profile
        + asset
        + "ex:asset a:hasPart ex:p. ex:p a a:Part; a:hasPart ex:leaf. ex:leaf a a:Part; a:partRole ex:role.",
        False,
    )
    case(
        "parent does not satisfy child role",
        profile + asset + part + "ex:p a a:Asset; dct:conformsTo ex:profile; a:hasPart ex:leaf. ex:leaf a a:Part.",
        False,
    )
    return rows


def render(rows: list[Case]) -> str:
    """Validate every case and render the corpus rows (name, verdict, path, base64 Turtle)."""
    shapes = Graph()
    for f in SHAPES:
        shapes.parse(ROOT / f)
    lines = ["# name\tconforms\texpected-path\tbase64 Turtle"]
    for name, data, expected, path in rows:
        source = PREFIX + data
        ok, report, detail = validate(
            Graph().parse(data=source, format="turtle"), shacl_graph=shapes, inference="none", advanced=False
        )
        assert bool(ok) == expected, (name, detail)
        if path:
            assert URIRef(path) in report.objects(None, SH.resultPath), (name, detail)
        lines.append("\t".join([name, str(expected).lower(), path, base64.b64encode(source.encode()).decode()]))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--write", action="store_true", help=f"Regenerate {CORPUS.relative_to(ROOT).as_posix()} from the authored cases"
    )
    args = parser.parse_args()
    rows = cases()
    rendered = render(rows)
    if args.write:
        CORPUS.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {len(rows)} layout/compound cases to {CORPUS.relative_to(ROOT).as_posix()}")
        return 0
    assert CORPUS.read_text(encoding="utf-8") == rendered, (
        f"{CORPUS.relative_to(ROOT).as_posix()} differs from the authored cases; "
        "run `python tools/test_layout_competency.py --write` after reviewing the change"
    )
    print(f"PASS: {len(rows)} layout/compound cases with inference and rule execution disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
