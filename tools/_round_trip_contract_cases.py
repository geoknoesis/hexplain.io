"""Round-trip exemptions must follow dependency and field identity, while preserving shape."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import zlib
from pathlib import Path

import _round_trip_byte_cases
import _round_trip_scope_cases
import round_trip
import run_suite
from suite import SUITE

DESCRIPTION = """@prefix b:<https://hexplain.io/ns/bddo#>.
@prefix h:<https://hexplain.io/ns/core#>.
@prefix e:<https://example.test/#>.
@prefix other:<https://other.test/#>.
e:Root a b:Struct; b:hasField (e:n e:data e:plain e:crc e:exprCrc e:plainCrc e:dep e:dep2 e:fixed e:pos e:len e:nested).
e:n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n; h:isEncodedWith <urn:codec>.
e:plain a b:Field; b:dataType b:uint8.
e:crc a b:Field; b:checksum [b:coversFromField e:data; b:coversToField e:data].
e:exprCrc a b:Field; b:checksum [b:coversFromExpression "0"; b:coversToExpression "stream.length"].
e:plainCrc a b:Field; b:checksum [b:coversFromField e:plain; b:coversToField e:plain].
e:dep a b:Field; b:valueFromExpression "instance.n + 1".
e:dep2 a b:Field; b:valueFromExpression "instance.dep + 1".
e:fixed a b:Field; b:valueFromExpression "2 + 2".
e:pos a b:Field; b:valueFromExpression "stream.position".
e:len a b:Field; b:valueFromExpression "stream.length".
e:nested a b:Field; b:dataType e:Inner.
e:Inner a b:Struct; b:hasField (other:n).
other:n a b:Field; b:dataType b:uint8.
"""


def dependency_controls(root: Path) -> None:
    description = root / "description.ttl"
    description.write_text(DESCRIPTION, encoding="utf-8", newline="\n")
    exempt = round_trip.recomputed_paths(description, "https://example.test/#Root")
    assert exempt == {(name,) for name in ("n", "crc", "exprCrc", "dep", "dep2", "pos", "len")}, exempt
    expected = {"n": 1, "crc": 2, "dep": 2, "dep2": 3, "pos": 4, "len": 8, "nested": {"n": 42}, "fixed": 4}
    changed = dict(expected, n=2, crc=3, dep=3, dep2=4, pos=5, len=9)
    assert round_trip.isomorphism_problems(expected, changed, exempt) == []
    assert round_trip.isomorphism_problems(expected, dict(changed, nested={"n": 999}), exempt)
    assert round_trip.isomorphism_problems(expected, dict(changed, fixed=999), exempt)
    invalid_values: tuple[object, ...] = (None, True, "2", {}, [])
    for value in invalid_values:
        assert round_trip.isomorphism_problems(expected, dict(changed, n=value), exempt)
    # Reuse of the same struct in an array grants only the corresponding repeated-field path.
    repeated = DESCRIPTION.replace("e:Root a b:Struct;", "e:Item a b:Struct;", 1)
    repeated += "\ne:Root a b:Struct; b:hasField (e:items). e:items b:dataType e:Item; b:repeatCount 2.\n"
    description.write_text(repeated, encoding="utf-8", newline="\n")
    exempt = round_trip.recomputed_paths(description, "https://example.test/#Root")
    assert ("items", "*", "n") in exempt and ("n",) not in exempt
    assert round_trip.isomorphism_problems({"items": [expected]}, {"items": [changed]}, exempt) == []
    assert round_trip.isomorphism_problems({"items": [expected]}, {"items": [dict(changed, nested={"n": 9})]}, exempt)
    description.write_text(repeated + "\ne:items b:size 100.\n", encoding="utf-8", newline="\n")
    bounded = round_trip.recomputed_paths(description, "https://example.test/#Root")
    assert ("items", "*", "len") not in bounded
    description.write_text(
        repeated + "\ne:items b:size 100; h:isEncodedWith <urn:codec>.\n", encoding="utf-8", newline="\n"
    )
    decoded = round_trip.recomputed_paths(description, "https://example.test/#Root")
    assert ("items", "*", "len") in decoded
    # An unreachable encoded declaration must not exempt any field of the selected root.
    description.write_text(DESCRIPTION, encoding="utf-8", newline="\n")
    assert round_trip.recomputed_paths(description, "https://example.test/#Inner") == set()


def local_binding_controls(root: Path) -> None:
    description = root / "local-binding-description.ttl"
    source = """@prefix b:<https://hexplain.io/ns/bddo#>.
@prefix h:<https://hexplain.io/ns/core#>.
@prefix e:<https://example.test/#>.
e:Root a b:Struct; b:hasField
    (e:n e:data e:a e:local e:next e:z e:derived e:stable e:stableDerived e:plainCrc e:lengthCrc).
e:n a b:Field; b:dataType b:uint8.
e:data a b:Field; b:dataType b:bytes; b:sizeFromField e:n; h:isEncodedWith <urn:codec>.
e:a a b:Field; b:dataType b:uint8.
e:local a b:LocalBinding; b:localExpression "instance.n + 1".
e:next a b:LocalBinding; b:localExpression "local + 1".
e:z a b:Field; b:dataType b:uint8.
e:derived a b:Field; b:valueFromExpression "instance.next + 1".
e:stable a b:LocalBinding; b:localExpression "2".
e:stableDerived a b:Field; b:valueFromExpression "stable + 1".
e:plainCrc a b:Field; b:dataType b:uint32; b:checksum [a b:Checksum;
    b:checksumAlgorithm b:crc32; b:coversFromField e:a; b:coversToField e:z].
e:lengthCrc a b:Field; b:dataType b:uint32; b:checksum [a b:Checksum;
    b:checksumAlgorithm b:crc32; b:coversFromField e:n; b:coversToField e:n].
"""
    description.write_text(source, encoding="utf-8", newline="\n")
    # Bindings are evaluation context, not necessarily exposed in the observed tree.
    expected = {
        "n": 25,
        "data": "00",
        "derived": 28,
        "stableDerived": 3,
        "plainCrc": 7,
        "lengthCrc": zlib.crc32(bytes([25])),
    }
    changed = dict(expected, n=21, derived=24, lengthCrc=zlib.crc32(bytes([21])))
    exempt = round_trip.recomputed_paths(description, "https://example.test/#Root", expected)
    assert exempt == {(name,) for name in ("n", "local", "next", "derived", "lengthCrc")}, exempt
    assert not round_trip.isomorphism_problems(expected, changed, exempt)
    assert round_trip.isomorphism_problems(expected, dict(changed, stableDerived=99), exempt)
    # Bindings inside a checksum range occupy no bytes and must not exempt its checksum.
    assert round_trip.isomorphism_problems(expected, dict(changed, plainCrc=99), exempt)
    assert round_trip.isomorphism_problems(expected, dict(changed, derived="24"), exempt)
    # Exposed bindings follow the same rule, but unrelated bindings remain strict.
    exposed = dict(expected, local=26, next=27, stable=2)
    exposed_changed = dict(changed, local=22, next=23, stable=2)
    assert not round_trip.isomorphism_problems(exposed, exposed_changed, exempt)
    assert round_trip.isomorphism_problems(exposed, dict(exposed_changed, stable=99), exempt)
    repeated = source.replace("e:Root a b:Struct;", "e:Item a b:Struct;", 1)
    repeated += "\ne:Root a b:Struct; b:hasField (e:items). e:items b:dataType e:Item; b:repeatCount 2.\n"
    description.write_text(repeated, encoding="utf-8", newline="\n")
    tree = {"items": [expected, expected]}
    scoped = round_trip.recomputed_paths(description, "https://example.test/#Root", tree)
    assert scoped == {("items", i) + path for i in range(2) for path in exempt}, scoped
    assert not round_trip.isomorphism_problems(tree, {"items": [expected, changed]}, scoped)
    assert round_trip.isomorphism_problems(tree, {"items": [expected, dict(changed, stableDerived=99)]}, scoped)


def repetition_controls(root: Path) -> None:
    description = root / "repeated-description.ttl"
    source = DESCRIPTION.replace(
        "e:Root a b:Struct; b:hasField (e:n e:data e:plain e:crc e:exprCrc e:plainCrc "
        "e:dep e:dep2 e:fixed e:pos e:len e:nested).",
        "e:Item a b:Struct; b:hasField (e:pos e:n e:data).",
    )
    source += "\ne:Root a b:Struct; b:hasField (e:items). e:items b:dataType e:Item; b:repeatCount 2.\n"
    description.write_text(source, encoding="utf-8", newline="\n")
    expected = {"items": [{"pos": 0, "n": 2, "data": "01"}, {"pos": 3, "n": 2, "data": "02"}]}
    actual = {"items": [{"pos": 0, "n": 3, "data": "01"}, {"pos": 4, "n": 2, "data": "02"}]}
    exempt = round_trip.recomputed_paths(description, "https://example.test/#Root", expected)
    assert ("items", 0, "pos") not in exempt
    assert ("items", 1, "pos") in exempt
    assert not round_trip.isomorphism_problems(expected, actual, exempt)
    actual["items"][0]["pos"] = 999
    assert round_trip.isomorphism_problems(expected, actual, exempt)
    description.write_text(
        source.replace("b:repeatCount 2", 'b:repeatUntil "stream.position == stream.length"'),
        encoding="utf-8",
        newline="\n",
    )
    until = round_trip.recomputed_paths(description, "https://example.test/#Root", expected)
    assert ("items", 1, "pos") in until and ("items", 0, "pos") not in until
    # A sequence of root structs also has positions affected by previous root instances.
    sequence = expected["items"]
    root_sequence = round_trip.recomputed_paths(description, "https://example.test/#Item", sequence)
    assert (1, "pos") in root_sequence and (0, "pos") not in root_sequence
    assert round_trip.isomorphism_problems({"*": 1, "unrelated": 2}, {"*": 9, "unrelated": 3}, {("*",)})
    # A fixed-size record contains recompression within its own physical extent.
    description.write_text(source + "\ne:items b:size 20.\n", encoding="utf-8", newline="\n")
    bounded = round_trip.recomputed_paths(description, "https://example.test/#Root", expected)
    assert ("items", 1, "pos") not in bounded


def cell_observation_controls(root: Path) -> None:
    case = root / "cell-observation"
    case.mkdir()
    (case / "manifest.json").write_text(
        json.dumps({"class": "physical-parser", "cells": ["pixels"], "root": "urn:cells:Root"}),
        encoding="utf-8",
        newline="\n",
    )
    (case / "description.ttl").write_text(
        """@prefix b:<https://hexplain.io/ns/bddo#>.
        <urn:cells:Root> a b:Struct; b:hasField (<urn:cells:pixels>).
        <urn:cells:pixels> b:dataType b:bytes; b:size 2.
        """,
        encoding="utf-8",
        newline="\n",
    )
    (case / "expected.json").write_text('{"pixels":[1,2]}', encoding="utf-8", newline="\n")
    (case / "round-trip-tree.json").write_text('{"pixels":"0102"}', encoding="utf-8", newline="\n")
    writer = root / "cell-writer.py"
    writer.write_text(
        "import sys,json,pathlib\n"
        "assert json.loads(pathlib.Path(sys.argv[1]).read_text()) == {'pixels':'0102'}\n"
        "pathlib.Path(sys.argv[2]).write_bytes(bytes([1,2]))\n",
        encoding="utf-8",
        newline="\n",
    )
    parser = root / "cell-parser.py"
    parser.write_text(
        "import sys,pathlib\npathlib.Path(sys.argv[1]).write_text('{\"pixels\":[1,2]}')\n",
        encoding="utf-8",
        newline="\n",
    )
    python = Path(sys.executable).as_posix()
    writer_cmd = f'"{python}" "{writer.as_posix()}" {{input}} {{out}}'
    parser_cmd = f'"{python}" "{parser.as_posix()}" {{out}} {{cells}}'
    claims = {"classes": ["Physical Parser"], "optionalFeatures": ["writer"]}
    status, detail = run_suite.run_round_trip(case, writer_cmd, parser_cmd, claims, "round-trip", 5)
    assert status == "PASS", detail


def corpus_control(root: Path) -> None:
    case = SUITE / "physical-parser/pp-codec-substream-origin"
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    altered = copy.deepcopy(expected)
    altered["block"]["pos"] = 999
    exempt = round_trip.recomputed_paths(
        case / "description.ttl", json.loads((case / "manifest.json").read_text(encoding="utf-8"))["root"]
    )
    assert ("block", "pos") not in exempt and ("block", "len") not in exempt
    assert round_trip.isomorphism_problems(expected, altered, exempt)
    parser = root / "parser.py"
    parser.write_text(
        "import pathlib,sys\npathlib.Path(sys.argv[1]).write_text(" + repr(json.dumps(altered)) + ")\n",
        encoding="utf-8",
        newline="\n",
    )
    python = Path(sys.executable).as_posix()
    stub = Path(run_suite.HERE / "stub_processor.py").as_posix()
    writer = f'"{python}" "{stub}" write {{case}} {{out}} {{err}}'
    claims = {"classes": ["Physical Parser"], "optionalFeatures": ["writer"]}
    assert (
        run_suite.run_round_trip(case, writer, f'"{python}" "{parser.as_posix()}" {{out}}', claims, "round-trip", 5)[0]
        == "FAIL"
    )


def check() -> list[str]:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        cell_observation_controls(root)
        repetition_controls(root)
        dependency_controls(root)
        local_binding_controls(root)
        _round_trip_scope_cases.check(root)
        _round_trip_byte_cases.check(root)
        corpus_control(root)
    return []
