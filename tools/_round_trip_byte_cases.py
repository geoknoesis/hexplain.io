"""Checksum exemptions follow changing physical bytes, never virtual values."""

import gzip
import zlib
from pathlib import Path

import round_trip
from pyshacl import validate
from rdflib import Graph
from suite import ROOT as SPEC_ROOT

PREFIX = """@prefix b:<https://hexplain.io/ns/bddo#>.
@prefix h:<https://hexplain.io/ns/core#>.
@prefix e:<https://example.test/#>.
"""
ROOT = "https://example.test/#Root"


def gzip_pair() -> tuple[bytes, bytes]:
    canonical = gzip.compress(b"\x00", mtime=0)
    header = bytearray(canonical[:10])
    header[3] |= 8  # The original member carries a filename; re-encoding may omit it.
    original = bytes(header) + b"abc\x00" + canonical[10:]
    assert len(original) == 25 and len(canonical) == 21
    assert gzip.decompress(original) == gzip.decompress(canonical) == b"\x00"
    return original, canonical


def virtual_range_controls(root: Path) -> None:
    description = root / "virtual-checksum-range.ttl"
    source = (
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:data e:a e:virtual e:z e:crc).
e:n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n;
    h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>.
e:a a b:Field; b:dataType b:uint8.
e:virtual a b:Field; b:valueFromExpression "instance.n + 1".
e:z a b:Field; b:dataType b:uint8.
e:crc a b:Field; b:dataType b:uint32; b:checksum [a b:Checksum;
    b:checksumAlgorithm b:crc32; b:coversFromField e:a; b:coversToField e:z].
"""
    )
    description.write_text(source, encoding="utf-8", newline="\n")
    original, canonical = gzip_pair()
    checksum = zlib.crc32(b"\x01\x02")
    before = {"n": len(original), "data": "00", "a": 1, "virtual": 26, "z": 2, "crc": checksum}
    after = dict(before, n=len(canonical), virtual=22)
    exempt = round_trip.recomputed_paths(description, ROOT, before)
    assert exempt == {("n",), ("virtual",)}, exempt
    assert not round_trip.isomorphism_problems(before, after, exempt)
    assert round_trip.isomorphism_problems(before, dict(after, crc=checksum ^ 1), exempt)
    # Each record retains its own strict checksum despite recomputed virtual members.
    repeated = source.replace("e:Root a b:Struct;", "e:Item a b:Struct;", 1)
    repeated += "\ne:Root a b:Struct; b:hasField (e:items). e:items a b:Field; b:dataType e:Item; b:repeatCount 2.\n"
    repeated_description = root / "repeated-virtual-checksum-range.ttl"
    repeated_description.write_text(repeated, encoding="utf-8", newline="\n")
    tree = {"items": [before, before]}
    exempt = round_trip.recomputed_paths(repeated_description, ROOT, tree)
    assert ("items", 0, "crc") not in exempt and ("items", 1, "crc") not in exempt
    assert not round_trip.isomorphism_problems(tree, {"items": [after, after]}, exempt)
    assert round_trip.isomorphism_problems(tree, {"items": [after, dict(after, crc=checksum ^ 1)]}, exempt)


def virtual_metadata_controls(root: Path) -> None:
    # Defensive analysis of an intentionally invalid profile; never positive conformance evidence.
    description = root / "virtual-byte-metadata.ttl"
    description.write_text(
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:virtual).
e:n a b:Field; b:dataType b:uint8.
e:virtual a b:Field; b:dataType b:uint32; b:valueFromExpression "4";
    b:sizeFromField e:n; h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>;
    b:checksum [a b:Checksum; b:checksumAlgorithm b:crc32; b:coversFromField e:n; b:coversToField e:n].
""",
        encoding="utf-8",
        newline="\n",
    )
    tree = {"n": 25, "virtual": 4}
    exempt = round_trip.recomputed_paths(description, ROOT, tree)
    assert not exempt, exempt
    assert round_trip.isomorphism_problems(tree, dict(tree, n=21), exempt)
    assert round_trip.isomorphism_problems(tree, dict(tree, virtual=99), exempt)


def virtual_length_controls(root: Path) -> None:
    description = root / "virtual-encoded-length.ttl"
    description.write_text(
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:data).
e:n a b:Field; b:valueFromExpression "25".
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n;
    h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>.
""",
        encoding="utf-8",
        newline="\n",
    )
    original, _ = gzip_pair()
    assert len(original) == 25  # A valid input fits the constant, byte-free bound.
    tree = {"n": 25, "data": "00"}
    exempt = round_trip.recomputed_paths(description, ROOT, tree)
    assert not exempt, exempt
    assert round_trip.isomorphism_problems(tree, dict(tree, n=21), exempt)


def encoded_presence_controls(root: Path) -> None:
    template = (
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:a e:optional e:z e:crc).
e:n a b:Field; b:dataType b:uint8.
e:a a b:Field; b:dataType b:uint8.
e:optional a b:Field; b:dataType b:bytes; b:sizeFromField e:n;
    h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>; MODE.
e:z a b:Field; b:dataType b:uint8.
e:crc a b:Field; b:dataType b:uint32; b:checksum [a b:Checksum;
    b:checksumAlgorithm b:crc32; b:coversFromField e:a; b:coversToField e:z].
"""
    )
    checksum = zlib.crc32(b"\x01\x02")
    absent = {"n": 0, "a": 1, "z": 2, "crc": checksum}
    for name, mode, tree in (
        ("absent-encoding.ttl", 'b:isPresentIf "false"', absent),
        ("empty-encoding.ttl", "b:repeatCount 0", dict(absent, optional=[])),
    ):
        description = root / name
        description.write_text(template.replace("MODE", mode), encoding="utf-8", newline="\n")
        exempt = round_trip.recomputed_paths(description, ROOT, tree)
        assert ("crc",) not in exempt, (name, exempt)
        assert round_trip.isomorphism_problems(tree, dict(tree, crc=checksum ^ 1), exempt)
    # Absence also prevents descending into a struct's otherwise repeated encoded children.
    nested = template.replace(
        "b:dataType b:bytes; b:sizeFromField e:n;\n"
        "    h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>; MODE",
        'b:dataType e:Inner; b:isPresentIf "false"',
    )
    nested += """
e:Inner a b:Struct; b:hasField (e:count e:bytes).
e:count a b:Field; b:dataType b:uint8.
e:bytes a b:Field; b:dataType b:bytes; b:repeatCount 1; b:sizeFromField e:count;
    h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>.
"""
    description = root / "absent-encoded-struct.ttl"
    description.write_text(nested, encoding="utf-8", newline="\n")
    exempt = round_trip.recomputed_paths(description, ROOT, absent)
    assert ("crc",) not in exempt and round_trip.isomorphism_problems(absent, dict(absent, crc=checksum ^ 1), exempt)
    # A present encoded repetition still contributes actual changing bytes to the range.
    description = root / "present-encoding.ttl"
    description.write_text(template.replace("MODE", "b:repeatCount 1"), encoding="utf-8", newline="\n")
    original, canonical = gzip_pair()
    before = {"n": 25, "a": 1, "optional": ["00"], "z": 2, "crc": zlib.crc32(b"\x01" + original + b"\x02")}
    after = {"n": 21, "a": 1, "optional": ["00"], "z": 2, "crc": zlib.crc32(b"\x01" + canonical + b"\x02")}
    exempt = round_trip.recomputed_paths(description, ROOT, before)
    assert ("crc",) in exempt and not round_trip.isomorphism_problems(before, after, exempt)


def physical_checksum_controls(root: Path) -> None:
    description = root / "physical-checksum-dependencies.ttl"
    description.write_text(
        PREFIX
        + """
e:Root a b:Struct; b:hasField (e:n e:data e:headerCrc e:dataCrc).
e:n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n;
    h:isEncodedWith <https://hexplain.io/ns/register/media-encoding#Gzip>.
e:headerCrc a b:Field; b:dataType b:uint32; b:checksum [a b:Checksum;
    b:checksumAlgorithm b:crc32; b:coversFromField e:n; b:coversToField e:n].
e:dataCrc a b:Field; b:dataType b:uint32; b:checksum [a b:Checksum;
    b:checksumAlgorithm b:crc32; b:coversFromField e:data; b:coversToField e:data].
""",
        encoding="utf-8",
        newline="\n",
    )
    original, canonical = gzip_pair()
    before = {"n": len(original), "data": "00", "headerCrc": zlib.crc32(bytes([25])), "dataCrc": zlib.crc32(original)}
    after = {"n": len(canonical), "data": "00", "headerCrc": zlib.crc32(bytes([21])), "dataCrc": zlib.crc32(canonical)}
    exempt = round_trip.recomputed_paths(description, ROOT, before)
    assert exempt == {("n",), ("headerCrc",), ("dataCrc",)}, exempt
    assert not round_trip.isomorphism_problems(before, after, exempt)


def check(root: Path) -> None:
    virtual_range_controls(root)
    virtual_metadata_controls(root)
    virtual_length_controls(root)
    encoded_presence_controls(root)
    physical_checksum_controls(root)
    shapes = Graph().parse(SPEC_ROOT / "specification/bddo/bddo.ttl")
    for name in (
        "virtual-checksum-range.ttl",
        "repeated-virtual-checksum-range.ttl",
        "physical-checksum-dependencies.ttl",
        "virtual-encoded-length.ttl",
        "absent-encoding.ttl",
        "empty-encoding.ttl",
        "absent-encoded-struct.ttl",
        "present-encoding.ttl",
    ):
        ok, _, detail = validate(Graph().parse(root / name), shacl_graph=shapes, ont_graph=shapes, inference="none")
        assert ok, (name, detail)
