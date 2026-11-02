"""Every codec vector suite reaches every part of its contract.

tools/test_codec_contracts.py checks that a suite is well formed; this gate checks that it is complete
(specification/codecs/index.html#completeness). For each register concept with a hexplain:codecContract:
  * every category the contract declares with hexplain:raisesCategory is expected by at least one step
    (a limit, a truncation or corruption, a flipped check, a refused coding feature);
  * every parameter the contract declares is passed, with a value the contract admits, by at least one step that
    succeeds, and in the direction the parameter applies: a parameter that only steers encoding (ENCODE_ONLY, the
    compression `level`) by an encode step, every other one by a step of either direction the contract covers. A
    step that expects the parameter's refusal shows that a bad value is refused, not that a good one is honoured;
  * a codec whose contract encodes (hexplain:encodes true on the contract) has at least one round trip: an
    encode step followed, in the same vector, by a decode step whose input is the encode step's expected
    output and whose expected output is the encode step's input (Processing Model, Serialisation, symmetry);
  * a codec whose contract does not state hexplain:encodes true has no encode step at all: the register, not
    the suite, says which direction a contract covers.
A declared category that no input of any known implementation raises is a defect of the contract, not of
the suite: the manifest records it under "unreached" with the reason, this gate reports it as a WARN line
rather than a failure, and the register is to withdraw the category (none is recorded today). Nothing else
is exempt. Every manifest is also validated against the published schema (vector-manifest.schema.json); the
jsonschema package is one of the pinned requirements, so the check always runs.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import TYPE_CHECKING, Any

from rdflib import Graph, Literal, Namespace, URIRef

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "codecs"))

import vectors  # noqa: E402
from vectors import Contract, Json, ParameterSpec  # noqa: E402

if TYPE_CHECKING:
    import jsonschema

REGISTER = ROOT / "specification/register/media-encoding/media-encoding.ttl"
SCHEMA = ROOT / "specification/codecs/vector-manifest.schema.json"
HX = Namespace("https://hexplain.io/ns/core#")
#: Parameters that steer only the encoder: a decoder reads the same bytes whatever value it is given, so only an
#: encode step shows the parameter honoured.
ENCODE_ONLY = frozenset({"level"})


def _bytes(spec: object) -> bytes | None:
    """The bytes of an inline hex or base64 spec, or None for a file or samples input."""
    if not isinstance(spec, dict) or "file" in spec or "samples" in spec:
        return None
    try:
        return vectors.input_bytes(spec, ROOT)
    except (ValueError, KeyError, OSError):
        return None


def round_trips(manifest: Json) -> list[str]:
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


def schema_validator() -> jsonschema.Draft202012Validator:
    """A validator of the published manifest schema."""
    import jsonschema

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def admitted(value: Any, spec: ParameterSpec) -> bool:
    """Whether a step's parameter value lies inside what the contract's parameter specification admits (its
    allowed values and its bounds; the loader checks the type)."""
    lowest, highest = spec.get("minimum"), spec.get("maximum")
    for v in value if isinstance(value, list) else [value]:
        if spec.get("allowed") and v not in spec["allowed"]:
            return False
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if lowest is not None and v < lowest:
                return False
            if highest is not None and v > highest:
                return False
    return True


def parameter_problems(manifest: Json, contract: Contract) -> list[str]:
    """The declared parameters no succeeding step passes with an admitted value in the direction it applies."""
    shown = set()
    for vector in manifest.get("vectors", []):
        for step in vector.get("steps") or []:
            if "error" in step.get("expect", {}):
                continue
            for name, value in step.get("params", {}).items():
                spec = contract["parameters"].get(name)
                applies = step.get("direction") == "encode" if name in ENCODE_ONLY else True
                if spec is not None and applies and admitted(value, spec):
                    shown.add(name)
    out = []
    for name in sorted(set(contract["parameters"]) - shown):
        where = "encode step" if name in ENCODE_ONLY else "step"
        out.append(
            f"the contract declares the parameter {name}, and no succeeding {where} passes an admitted value of it"
        )
    return out


def problems(
    manifest: Json,
    contract: Contract,
    declared_categories: set[str],
    encodes: bool,
    warnings: list[str] | None = None,
) -> list[str]:
    out = []
    expected: set[str] = set()
    directions: set[str] = set()
    for vector in manifest.get("vectors", []):
        for step in vector.get("steps") or []:
            directions.add(step.get("direction"))
            if "error" in step.get("expect", {}):
                expected.add(step["expect"]["error"])
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
    out += parameter_problems(manifest, contract)
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


LEVEL: ParameterSpec = {
    "type": "integer",
    "list": False,
    "length": None,
    "required": False,
    "minimum": -1,
    "maximum": 9,
    "allowed": [],
}


def probe_contract(parameters: dict[str, ParameterSpec]) -> Contract:
    """A contract declaring [parameters], for the self-test."""
    return {"version": 1, "suite": 1, "kind": "compression", "session": False, "parameters": parameters}


def self_test(validator: jsonschema.Draft202012Validator) -> None:
    """The gate notices what it is for."""
    decode = {"direction": "decode", "params": {}, "input": {"hex": "00"}, "expect": {"hex": "00"}}
    probe = {"vectors": [{"id": "x", "steps": [decode]}]}
    gap = "the contract declares the parameter level, and no succeeding encode step passes an admitted value of it"
    assert problems(probe, probe_contract({"level": LEVEL}), {"Validation"}, True) == [
        "the contract declares hexplain:raisesCategory Validation, and no step expects it",
        gap,
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
    assert problems(trip, probe_contract({}), set(), True) == [], "a round trip of an encoding contract was refused"
    assert len(problems(trip, probe_contract({}), set(), False)) == 1, (
        "an encode step under a contract that does not state hexplain:encodes went unnoticed"
    )

    def passing(direction: str, value: int, expect: dict[str, Any]) -> list[str]:
        step = dict(decode, direction=direction, params={"level": value}, expect=expect)
        return parameter_problems({"vectors": [{"id": "p", "steps": [step]}]}, probe_contract({"level": LEVEL}))

    assert passing("decode", 10, {"error": "Description"}) == [gap], "a refused value counted as passing a parameter"
    assert passing("decode", 6, {"hex": "00"}) == [gap], "an encode-only parameter counted on a decode step"
    assert passing("encode", 10, {"ok": True}) == [gap], "a value outside the contract counted as passing a parameter"
    assert passing("encode", 6, {"ok": True}) == [], "an admitted value on a succeeding encode step was not counted"
    assert list(validator.iter_errors(probe)), "the schema check accepts a manifest without a codec or sources"


def main() -> int:
    register = Graph().parse(REGISTER, format="turtle")
    contracts = vectors.contracts(register)
    failures: list[str] = []
    warnings: list[str] = []
    trips = 0
    validator = schema_validator()
    for iri, contract in sorted(contracts.items()):
        node = URIRef(iri + ".contract")
        declared = {str(o) for o in register.objects(node, HX.raisesCategory)}
        encodes = any(isinstance(o, Literal) and o.toPython() is True for o in register.objects(node, HX.encodes))
        path = vectors.suite_path(iri)
        if not path.is_file():
            continue  # test_codec_contracts reports the missing suite
        manifest = vectors.load(path)
        found = problems(manifest, contract, declared, encodes, warnings)
        found += [
            f"not valid against vector-manifest.schema.json at /{'/'.join(map(str, e.absolute_path))}: "
            f"{e.message[:160]}"
            for e in list(validator.iter_errors(manifest))[:3]
        ]
        failures += [f"{path.relative_to(ROOT).as_posix()}: {p}" for p in found]
        trips += len(round_trips(manifest))
    for w in warnings:
        print("WARN: " + w)
    self_test(validator)
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        return 1
    print(
        f"PASS: {len(contracts)} codec vector suites expect every declared category, pass every declared parameter "
        f"in a succeeding step of its direction and hold {trips} round trips; every manifest is valid against the "
        "published schema"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
