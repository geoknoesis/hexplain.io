"""Round trips: the Processing Model's symmetry requirement (Serialisation, req-pm-serialisation-24), made runnable.

For every tree a Physical Parser produced, a Writer either writes a stream that parses to an isomorphic tree or raises
the error the serialisation rules require. The suite already holds such trees: the expected.json of every
Physical Parser case. `run_suite.py --round-trip` gives each to the writer under test (--w-cmd), parses what it wrote
with the parser under test (--pp-cmd) and compares the two trees by the Processing Model's definition of isomorphism
(processing/index.html#tree-isomorphism): equal node for node, except the recomputed derived values.

What each case must do is stated in specification/conformance/writer/round-trip-expectations.json, case id to one of

  "round-trip"    the writer writes a stream, and the stream parses to an isomorphic tree;
  "Unsupported"   the writer refuses with Unsupported feature (a text or tree container, a chunk table, a codec with
                  no encode direction);
  "Validation"    the tree came from a stream that was not canonical, and the rules refuse it where this writer's
                  bytes do not fit (an encoded field in a literal region, a text number spelt another way, a float
                  stored beyond the IEEE range): the writer refuses with a validation error, or -- its encoder
                  happening to fit -- round-trips.

The file is generated with the suite (generate_inputs.py) from `expectation` below: the Unsupported entries follow
from each case's description by rule 10 of the serialisation rules, and the Validation entries are the reviewed table
REFUSED, each with the rule that refuses it. A stream that parses to another tree, or does not parse, fails every
entry: that is the outcome symmetry forbids.

The same comparison serves a Writer case that states `"verify": "round-trip"` (a compressor, whose bytes are the
encoder's own): its expected.json is the tree the written stream must parse to.
"""

from __future__ import annotations

import functools
import json
import math
from collections.abc import Set
from pathlib import Path
from typing import Any

import rdflib
from rdflib import RDF, Literal, URIRef
from suite import ROOT, SUITE, dump

EXPECTATIONS = "writer/round-trip-expectations.json"
OUTCOMES = ("round-trip", "Unsupported", "Validation")
BDDO = "https://hexplain.io/ns/bddo#"
CORE = "https://hexplain.io/ns/core#"
DLV = "https://hexplain.io/ns/dlv#"
#: Rule 10: the containers a Writer refuses.
TEXT_CONTAINERS = ("DelimitedRecords", "KeyValueHeader", "DelimitedTable", "TreeDocument")
CHUNK_TABLE = ("chunkOffsetsFromField", "chunkLengthsFromField")
CODEC_PROPERTIES = ("isEncodedWith", "codec")
REGISTER = ROOT / "specification/register/media-encoding/media-encoding.ttl"

#: Trees a parser produced from a stream that was not canonical, which the rules refuse (or, for an encoder whose
#: output happens to fit, write): case id to the rule. Reviewed by hand against the case's description and input.
REFUSED = {
    "pp-codec-gzip-members": "rule 3: bddo:size 46 holds two gzip members; one re-encoded member has another length",
    "pp-codec-lz4-frame": "rule 3: bddo:size 89 holds the input's LZ4 frame; a re-encoded frame has its own length",
    "pp-codec-lz4-frame-block-checksums": "rule 3: bddo:size 101 holds a frame with block checksums, which an "
    "encoder need not write",
    "pp-codec-lz4-frame-concatenated": "rule 3: bddo:size 50 holds two LZ4 frames; one re-encoded frame is shorter",
    "pp-codec-lz4-frame-substream": "rule 3: bddo:size 24 holds the input's LZ4 frame of an encoded struct",
    "pp-codec-zstd-concatenated": "rule 3: bddo:size 74 holds two Zstandard frames; one re-encoded frame is shorter",
    "pp-textnum-decimals": "rule 5: the canonical spelling -20.0 does not fit bddo:size 4, which the input filled "
    "with -2e1",
}


def tree_cases(suite: Path = SUITE) -> list[Path]:
    """The Physical Parser cases that state a parsed tree, in order."""
    out = []
    for path in sorted((Path(suite) / "physical-parser").glob("*/manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("check") is None and (path.parent / "expected.json").is_file():
            out.append(path.parent)
    return out


_ENCODING: set[str] | None = None


def encoding_codecs() -> set[str]:
    """The register concepts whose contract states hexplain:encodes true."""
    global _ENCODING  # noqa: PLW0603 -- the register is parsed once per process
    if _ENCODING is None:
        graph = rdflib.Graph().parse(REGISTER, format="turtle")
        encodes = URIRef(CORE + "encodes")
        contract = URIRef(CORE + "codecContract")
        _ENCODING = {
            str(concept)
            for concept, node in graph.subject_objects(contract)
            if any(isinstance(o, Literal) and o.toPython() is True for o in graph.objects(node, encodes))
        }
    return _ENCODING


def codecs_named(graph: rdflib.Graph) -> set[str]:
    """Every register concept a description names as the codec of a field or of a step. (The candidates of a
    run-time selection are not counted: which of them a tree selects is the tree's to say.)"""
    named = set()
    for local in CODEC_PROPERTIES:
        named |= {str(o) for o in graph.objects(None, URIRef(CORE + local)) if isinstance(o, URIRef)}
    return {iri for iri in named if iri.startswith("https://hexplain.io/ns/register/media-encoding#")}


@functools.cache
def unsupported_reason(description: bytes) -> str | None:
    """Why rule 10 (or rule 7) has a Writer refuse the description (its Turtle) with Unsupported feature, or None."""
    graph = rdflib.Graph().parse(data=description, format="turtle")
    for local in TEXT_CONTAINERS:
        if (None, RDF.type, URIRef(BDDO + local)) in graph:
            return f"rule 10: a bddo:{local}"
    for local in CHUNK_TABLE:
        if (None, URIRef(DLV + local), None) in graph:
            return f"rule 10: a chunk table (dlv:{local})"
    decode_only = sorted(codecs_named(graph) - encoding_codecs())
    if decode_only:
        return f"rule 7: {decode_only[0].rpartition('#')[2]} has no encode direction"
    return None


def expectation(case_id: str, description: bytes) -> tuple[str, str]:
    """(outcome, reason) the serialisation rules give the tree of the Physical Parser case [case_id], whose
    description.ttl holds [description]."""
    refused = unsupported_reason(description)
    if refused:
        return "Unsupported", refused
    if case_id in REFUSED:
        return "Validation", REFUSED[case_id]
    return "round-trip", ""


def expectations_file(cases: dict[str, Any]) -> bytes:
    """The bytes of round-trip-expectations.json for the Physical Parser cases given as {case id: Case}: every
    case that states a tree, with its outcome."""
    out = {}
    for case_id, case in sorted(cases.items()):
        files = case.artifacts()
        if "expected.json" in files and not case.manifest.get("check"):
            out[case_id] = expectation(case_id, files["description.ttl"])[0]
    stale = sorted(set(REFUSED) - set(out))
    if stale:
        raise ValueError(f"round_trip.REFUSED names cases that state no tree: {stale}")
    return dump(out)


def load_expectations(suite: Path = SUITE) -> dict[str, str]:
    return json.loads((Path(suite) / EXPECTATIONS).read_text(encoding="utf-8"))


def recomputed_keys(description: Path) -> set[str]:
    """The local names of the fields whose value isomorphism exempts: the length field of an encoded field, and,
    in a description with an encoded field, every checksum field and every derived field (a checksum whose covered
    range includes encoded bytes is recomputed, and a derived value may rest on either). Field keys are local names,
    so the exemption is by name."""
    graph = rdflib.Graph().parse(description, format="turtle")
    encoded = set()
    for local in ("isEncodedWith", "hasEncodingStep", "codecFromExpression"):
        encoded |= set(graph.subjects(URIRef(CORE + local), None))
    if not encoded:
        return set()
    exempt = set()
    for field in encoded:
        exempt |= set(graph.objects(field, URIRef(BDDO + "sizeFromField")))
    exempt |= set(graph.subjects(URIRef(BDDO + "checksum"), None))
    exempt |= set(graph.subjects(URIRef(BDDO + "valueFromExpression"), None))
    return {str(term).rpartition("#")[2].rpartition("/")[2] for term in exempt}


def same_value(expected: Any, actual: Any) -> bool:
    """Equal values of the same type: a NaN equals a NaN, and -0.0 is not 0.0."""
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, float):
        if math.isnan(expected) or math.isnan(actual):
            return math.isnan(expected) and math.isnan(actual)
        return expected == actual and math.copysign(1.0, expected) == math.copysign(1.0, actual)
    return expected == actual


def isomorphism_problems(expected: Any, actual: Any, exempt: Set[str] = frozenset(), path: str = "$") -> list[str]:
    """Why two canonical trees are not isomorphic (processing/index.html#tree-isomorphism); [] when they are.
    A member whose key is in [exempt] is a recomputed derived value: bound in one tree it is bound in the other,
    and its value is not compared."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: a struct node became {actual!r}"]
        if set(expected) != set(actual):
            return [f"{path}: members {sorted(expected)} became {sorted(actual)}"]
        out = []
        for key, value in expected.items():
            if key in exempt:
                if (value is None) != (actual[key] is None):
                    out.append(f"{path}.{key}: a recomputed value is bound in one tree and not in the other")
            else:
                out += isomorphism_problems(value, actual[key], exempt, f"{path}.{key}")
        return out
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: an array node became {actual!r}"]
        if len(expected) != len(actual):
            return [f"{path}: {len(expected)} elements became {len(actual)}"]
        out = []
        for index, (e, a) in enumerate(zip(expected, actual, strict=True)):
            out += isomorphism_problems(e, a, exempt, f"{path}[{index}]")
        return out
    return [] if same_value(expected, actual) else [f"{path}: {expected!r} became {actual!r}"]


def judge(expected: str, refusal: str | None, problems: list[str] | None) -> tuple[str, str]:
    """(PASS or FAIL, detail) of one round trip: [refusal] is the category the writer raised, or None when it
    wrote a stream, whose re-parse differs from the tree by [problems]."""
    if refusal is not None:
        if expected == "round-trip":
            return "FAIL", f"the writer refused a tree a parser produced ({refusal}); the rules require a stream"
        if refusal != expected:
            return "FAIL", f"the writer refused with {refusal}; the rules require {expected}"
        return "PASS", ""
    if problems:
        return "FAIL", "the written stream parses to another tree: " + "; ".join(problems[:5])
    if expected == "Unsupported":
        return "FAIL", "the writer wrote a stream; the rules require Unsupported feature"
    return "PASS", ""
