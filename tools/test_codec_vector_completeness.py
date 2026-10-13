"""Every codec vector suite reaches every part of its contract.

tools/test_codec_contracts.py checks that a suite is well formed; this gate checks that it is complete
(specification/codecs/index.html#completeness). For each register concept with a hexplain:codecContract:
  * every category the contract declares with hexplain:raisesCategory is expected by at least one step
    (a limit, a truncation or corruption, a flipped check, a refused coding feature);
  * every parameter the contract declares is passed by at least one step;
  * a codec whose contract encodes (hexplain:encodes true on the contract) has at least one round trip: an
    encode step followed, in the same vector, by a decode step whose input is the encode step's expected
    output and whose expected output is the encode step's input (Processing Model, Serialisation, symmetry);
  * a codec whose contract does not state hexplain:encodes true has no encode step at all: the register, not
    the suite, says which direction a contract covers.
A declared category that no input of any known implementation raises is a defect of the contract, not of
the suite: the manifest records it under "unreached" with the reason, this gate reports it as a WARN line
rather than a failure, and the register is to withdraw the category (none is recorded today). Nothing else
is exempt.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

from rdflib import Graph, Namespace, URIRef

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "codecs"))

import vectors  # noqa: E402

REGISTER = ROOT / "specification/register/media-encoding/media-encoding.ttl"
SCHEMA = ROOT / "specification/codecs/vector-manifest.schema.json"
HX = Namespace("https://hexplain.io/ns/core#")


def _bytes(spec):
    """The bytes of an inline hex or base64 spec, or None for a file or samples input."""
    if not isinstance(spec, dict) or "file" in spec or "samples" in spec:
        return None
    try:
        return vectors.input_bytes(spec, ROOT)
    except (ValueError, KeyError, OSError):
        return None


def round_trips(manifest: Any) -> Any:
    """The ids of the vectors that hold a round trip."""
    found = []
    for vector in manifest.get("vectors", []):
        steps = vector.get("steps") or []
        for first, second in zip(steps, steps[1:], strict=False):
            if first.get("direction") != "encode" or second.get("direction") != "decode":
                continue
            if "error" in first.get("expect", {}) or "error" in second.get("expect", {}):
                continue
            original = _bytes(first.get("input", {}))
            if original is None or _bytes(second.get("expect", {})) != original:
                continue
            encoded = _bytes(first.get("expect", {}))
            # A transform's encoding is fixed, so the decode step carries it; a compressor's is the
            # implementation's own, so the decode step reads the previous step's output.
            if (encoded is not None and _bytes(second.get("input", {})) == encoded) or second.get("input", {}).get(
                "previous"
            ) is True:
                found.append(vector["id"])
                break
    return found


def schema_validator() -> Any:
    """A validator of the published manifest schema, or None where the jsonschema package is not installed (it is
    not one of the pinned requirements, so the schema check runs where it is available and is reported either way)."""
    import json

    try:
        import jsonschema
    except ImportError:
        return None
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def problems(manifest: Any, contract: Any, declared_categories: Any, encodes: Any, warnings: Any = None) -> Any:
    out = []
    expected, params, directions = set(), set(), set()
    for vector in manifest.get("vectors", []):
        for step in vector.get("steps") or []:
            directions.add(step.get("direction"))
            if "error" in step.get("expect", {}):
                expected.add(step["expect"]["error"])
            params |= set(step.get("params", {}))
    unreached = manifest.get("unreached") or {}
    for category, reason in sorted(unreached.items()):
        if (
            category not in declared_categories
            or category in expected
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            out.append(
                f"unreached names {category}, which the contract does not declare, a step expects, or has no reason"
            )
        elif warnings is not None:
            warnings.append(
                f"the contract declares hexplain:raisesCategory {category}, which no input reaches: {reason}"
            )
    for category in sorted(declared_categories - expected - set(unreached)):
        out.append(f"the contract declares hexplain:raisesCategory {category}, and no step expects it")
    for name in sorted(set(contract["parameters"]) - params):
        out.append(f"the contract declares the parameter {name}, and no step passes it")
    if "encode" in directions and not encodes:
        out.append(
            "a step encodes, and the contract does not state hexplain:encodes true (the register says which "
            "directions a contract covers)"
        )
    if encodes and not round_trips(manifest):
        out.append(
            "the codec encodes, and no vector holds a round trip (an encode step whose expected output the next "
            "decode step reads back to the encode step's input)"
        )
    return out


def main() -> int:
    register = Graph().parse(REGISTER, format="turtle")
    contracts = vectors.contracts(register)
    failures, warnings, trips = [], [], 0
    validator = schema_validator()
    for iri, contract in sorted(contracts.items()):
        node = URIRef(iri + ".contract")
        declared = {str(o) for o in register.objects(node, HX.raisesCategory)}
        encodes = any(o.toPython() is True for o in register.objects(node, HX.encodes))
        path = vectors.suite_path(iri)
        if not path.is_file():
            continue  # test_codec_contracts reports the missing suite
        manifest = vectors.load(path)
        found = problems(manifest, contract, declared, encodes, warnings)
        if validator is not None:
            found += [
                f"not valid against vector-manifest.schema.json at /{'/'.join(map(str, e.absolute_path))}: "
                f"{e.message[:160]}"
                for e in list(validator.iter_errors(manifest))[:3]
            ]
        failures += [f"{path.relative_to(ROOT).as_posix()}: {p}" for p in found]
        trips += len(round_trips(manifest))
    for w in warnings:
        print("WARN: " + w)
    # The gate notices what it is for.
    probe = {
        "vectors": [
            {
                "id": "x",
                "steps": [{"direction": "decode", "params": {}, "input": {"hex": "00"}, "expect": {"hex": "00"}}],
            }
        ]
    }
    assert problems(probe, {"parameters": {"level": {}}}, {"Validation"}, True) == [
        "the contract declares hexplain:raisesCategory Validation, and no step expects it",
        "the contract declares the parameter level, and no step passes it",
        "the codec encodes, and no vector holds a round trip (an encode step whose expected output the next decode "
        "step reads back to the encode step's input)",
    ], "the completeness check no longer notices a gap"
    trip = {
        "vectors": [
            {
                "id": "rt",
                "steps": [
                    {"direction": "encode", "params": {}, "input": {"hex": "0102"}, "expect": {"hex": "0201"}},
                    {"direction": "decode", "params": {}, "input": {"hex": "0201"}, "expect": {"hex": "0102"}},
                ],
            }
        ]
    }
    assert round_trips(trip) == ["rt"], "the round-trip check no longer recognises one"
    assert problems(trip, {"parameters": {}}, set(), True) == [], "a round trip of an encoding contract was refused"
    assert len(problems(trip, {"parameters": {}}, set(), False)) == 1, (
        "an encode step under a contract that does not state hexplain:encodes went unnoticed"
    )
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        return 1
    print(
        f"PASS: {len(contracts)} codec vector suites expect every declared category, pass every declared parameter "
        f"and hold {trips} round trips; "
        + (
            "every manifest is valid against the published schema"
            if validator is not None
            else "schema validation not run (jsonschema is not installed)"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
