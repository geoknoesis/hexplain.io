"""Codec vector suites: the manifest format, its loader and its checks.

A register concept that carries hexplain:codecContract has a normative vector suite at
specification/codecs/<LocalName>/vectors/manifest.json:

    {
      "codec": "<concept IRI>",
      "suiteVersion": <int: the contract's hexplain:vectorSuiteVersion>,
      "sources": [{"id": str, "description": str (provenance), "licence": str, "url": str (optional)}],
      "vectors": [{
          "id": str, "source": <source id>, "session": bool (optional; steps share one session),
          "steps": [{
              "direction": "decode" | "encode" | "describe",
              "params": {name: value},   # JSON by the contract's type: integer/float numbers,
                                         # booleans, strings, bytes {"hex": ..}, IRIs {"iri": ..}, lists
              "input": {"hex": ..} | {"base64": ..} | {"file": <path beside the manifest>}
                       | {"samples": {"width", "height", "bands", "sampleType", "hex" | "base64"}}
                       | {"previous": true},     # the previous step's output (a round trip through a compressor)
              "maxOutputBytes": int (optional, default 67108864),
              "expect": {"hex" | "base64": ..} | {"sha256": .., "size": int (optional)} | {"ok": true}
                        | {"error": "Validation" | "Checksum" | "Unsupported" | "ResourceLimit" | "Description"}
                        | {"samples": {"width", "height", "bands", "sampleType", "sha256", "order": "pixel" | "band"}},
                        any success form optionally with "validitySha256"
          }],
          "expectAll": {"sha256": .., "size": int (optional),
                        "unpack": {"bitsPerSample": int, "width": int} (optional),
                        "deinterleave": {"bands": int, "sampleBytes": int} (optional)}
      }]
    }

Sample types are uint8, int8, uint16, int16, uint32, int32, float32 and float64; samples are
little-endian and pixel-interleaved unless an implementation reports otherwise.

An implementation is run once per vector and prints one JSON object on stdout:

    {"steps": [{"ok": true, "size": int, "sha256": hex,
                "geometry": {"width", "height", "bands", "sampleType"}, "sha256Band": hex,
                "validitySha256": hex}
               | {"ok": false, "category": <category>, "message": str}],
     "all": {"sha256": hex, "size": int}}

"sha256" covers the step's output bytes as the implementation lays them out; "geometry" and
"sha256Band" (the samples rewritten band-sequentially) appear for samples only, and
"validitySha256" (the concatenated per-band validity masks, one byte per pixel) for samples that
carry masks; "all" appears when the vector has "expectAll" and covers the concatenation of every
step's output after expectAll's "unpack" (each row of `width` samples of `bitsPerSample` bits,
most significant bit first, widened to one byte per sample, the row's padding bits dropped) and
"deinterleave" (pixel-interleaved samples of `bands` bands of `sampleBytes` bytes each rewritten
band-sequentially). A step that fails ends the vector; the result lists the steps run.
"""

from __future__ import annotations

import base64
import hashlib
import json
import pathlib
from typing import Any, TypedDict

import rdflib
from rdflib import Literal, URIRef
from rdflib.term import Node

ROOT = pathlib.Path(__file__).resolve().parents[2]
HX = "https://hexplain.io/ns/core#"
CATEGORIES = {"Validation", "Checksum", "Unsupported", "ResourceLimit", "Description"}
SAMPLE_TYPES = {"uint8", "int8", "uint16", "int16", "uint32", "int32", "float32", "float64"}
TYPES = {
    HX + "IntegerParameterType": "integer",
    HX + "BooleanParameterType": "boolean",
    HX + "StringParameterType": "string",
    HX + "BytesParameterType": "bytes",
    HX + "IriParameterType": "iri",
    HX + "FloatParameterType": "float",
}
#: A manifest, a vector, a step, a step's input or expectation, or an implementation's result, as parsed JSON.
Json = dict[str, Any]


class ParameterSpec(TypedDict):
    """A parameter a contract declares."""

    type: str | None
    list: bool
    length: int | None
    required: bool
    minimum: float | None
    maximum: float | None
    allowed: list[Any]


class Contract(TypedDict):
    """A codec contract: its version, its vector suite's version, its kind, whether it keeps a session, and its
    parameters by key."""

    version: int
    suite: int
    kind: str
    session: bool
    parameters: dict[str, ParameterSpec]


def local_name(iri: str) -> str:
    return iri.rsplit("#", 1)[-1]


def suite_path(iri: str) -> pathlib.Path:
    return ROOT / "specification" / "codecs" / local_name(iri) / "vectors" / "manifest.json"


def load(path: pathlib.Path | str) -> Json:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _literal(node: Node | None) -> Literal:
    """[node], which the contract shapes require to be a literal."""
    if not isinstance(node, Literal):
        raise ValueError(f"a codec contract states a literal here, not {node!r}")
    return node


def _number(literal: Node | None) -> float | None:
    return float(_literal(literal).toPython()) if literal is not None else None


def _flag(graph: rdflib.Graph, subject: Node, name: str) -> bool:
    """Whether [subject] states the boolean [name] true."""
    node = graph.value(subject, URIRef(HX + name))
    return bool(node and _literal(node).toPython())


def _parameter(graph: rdflib.Graph, spec: Node) -> ParameterSpec:
    """The declaration [spec] of a contract's parameter."""
    hx = lambda name: URIRef(HX + name)  # noqa: E731
    length = graph.value(spec, hx("listLength"))
    return {
        "type": TYPES.get(str(graph.value(spec, hx("parameterType")))),
        "list": _flag(graph, spec, "listValued"),
        "length": _literal(length).toPython() if length else None,
        "required": _flag(graph, spec, "requiredParameter"),
        "minimum": _number(graph.value(spec, hx("minimumValue"))),
        "maximum": _number(graph.value(spec, hx("maximumValue"))),
        "allowed": [_literal(v).toPython() for v in graph.objects(spec, hx("allowedValue"))],
    }


def contracts(graph: rdflib.Graph) -> dict[str, Contract]:
    """Every contract of [graph] as {concept IRI: {"version", "suite", "kind", "session", "parameters"}}."""
    out: dict[str, Contract] = {}
    hx = lambda name: URIRef(HX + name)  # noqa: E731
    for concept, contract in graph.subject_objects(hx("codecContract")):
        parameters = {}
        for spec in graph.objects(contract, hx("declaresParameter")):
            parameters[str(graph.value(spec, hx("parameterKey")))] = _parameter(graph, spec)
        out[str(concept)] = {
            "version": _literal(graph.value(contract, hx("contractVersion"))).toPython(),
            "suite": _literal(graph.value(contract, hx("vectorSuiteVersion"))).toPython(),
            "kind": local_name(str(graph.value(contract, hx("codecKind")))),
            "session": bool(_literal(graph.value(contract, hx("keepsSession"))).toPython()),
            "parameters": parameters,
        }
    return out


def _decode_bytes(spec: Json) -> bytes:
    if "hex" in spec:
        return bytes.fromhex(spec["hex"])
    if "base64" in spec:
        return base64.b64decode(spec["base64"])
    raise ValueError(f"no hex or base64 in {spec}")


def input_bytes(spec: Json, base: pathlib.Path | str, previous: bytes | None = None) -> bytes:
    """The bytes of a step's input (for samples, their data; for {"previous": true}, [previous], the output of the
    step before it, which a static reader passes as None)."""
    if "file" in spec:
        return (pathlib.Path(base) / spec["file"]).read_bytes()
    if "samples" in spec:
        return _decode_bytes(spec["samples"])
    if spec.get("previous") is True:
        if previous is None:
            raise ValueError("no previous step output")
        return previous
    return _decode_bytes(spec)


def _item_problem(name: str, value: Any, spec: ParameterSpec) -> str | None:
    kind = spec["type"]
    if kind == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return f"parameter {name} is not an integer: {value!r}"
    if kind == "float" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return f"parameter {name} is not a number: {value!r}"
    if kind == "boolean" and not isinstance(value, bool):
        return f"parameter {name} is not a boolean: {value!r}"
    if kind == "string" and not isinstance(value, str):
        return f"parameter {name} is not a string: {value!r}"
    if kind == "bytes" and not (isinstance(value, dict) and ("hex" in value or "base64" in value)):
        return f'parameter {name} is not bytes ({{"hex": ..}}): {value!r}'
    if kind == "iri" and not (isinstance(value, dict) and "iri" in value):
        return f'parameter {name} is not an IRI ({{"iri": ..}}): {value!r}'
    if kind in ("integer", "float"):
        if spec["minimum"] is not None and value < spec["minimum"]:
            return f"parameter {name} = {value} is below {spec['minimum']}"
        if spec["maximum"] is not None and value > spec["maximum"]:
            return f"parameter {name} = {value} is above {spec['maximum']}"
    if spec["allowed"] and value not in spec["allowed"]:
        return f"parameter {name} = {value!r} is not one of {spec['allowed']}"
    return None


def parameter_problems(params: Json, contract: Contract) -> list[str]:
    problems = []
    declared = contract["parameters"]
    for name in params:
        if name not in declared:
            problems.append(f"parameter {name} is not declared by the contract")
    for name, spec in declared.items():
        if spec["required"] and name not in params:
            problems.append(f"required parameter {name} is missing")
        if name not in params:
            continue
        value = params[name]
        if spec["list"]:
            if not isinstance(value, list):
                problems.append(f"parameter {name} is not a list")
                continue
            if spec["length"] is not None and len(value) != spec["length"]:
                problems.append(f"parameter {name} has {len(value)} items, not {spec['length']}")
            problems += [p for p in (_item_problem(name, v, spec) for v in value) if p]
        else:
            problem = _item_problem(name, value, spec)
            if problem:
                problems.append(problem)
    return problems


def problems(manifest: Json, contract: Contract, base: pathlib.Path | str) -> list[str]:
    """Everything wrong with [manifest] against [contract]; empty when it is well formed."""
    out = []
    if manifest.get("suiteVersion") != contract["suite"]:
        out.append(
            f"suiteVersion {manifest.get('suiteVersion')} differs from the contract's vectorSuiteVersion "
            f"{contract['suite']}"
        )
    sources = {s.get("id"): s for s in manifest.get("sources", [])}
    if not sources:
        out.append("no sources")
    for sid, source in sources.items():
        if not source.get("description") or not source.get("licence"):
            out.append(f"source {sid} lacks a description (provenance) or a licence")
    ids: set[Any] = set()
    for vector in manifest.get("vectors", []):
        out += _vector_problems(vector, sources, ids, contract, base)
    if not any(_decodes(vector) for vector in manifest.get("vectors", [])):
        out.append("no decoding vector that succeeds")
    return out


def _decodes(vector: Json) -> bool:
    """Whether [vector] has a decoding step that is expected to succeed."""
    steps = vector.get("steps") or []
    return any(step.get("direction") == "decode" and "error" not in (step.get("expect") or {}) for step in steps)


def _vector_problems(
    vector: Json, sources: dict[Any, Json], ids: set[Any], contract: Contract, base: pathlib.Path | str
) -> list[str]:
    """What is wrong with one vector: its id (recorded in [ids]), its source and its steps."""
    out = []
    vid = vector.get("id")
    if not vid or vid in ids:
        out.append(f"vector id {vid!r} is missing or repeated")
    ids.add(vid)
    if vector.get("source") not in sources:
        out.append(f"vector {vid} names an unknown source {vector.get('source')!r}")
    steps = vector.get("steps") or []
    if not steps:
        out.append(f"vector {vid} has no steps")
    for i, step in enumerate(steps):
        out += _step_problems(f"vector {vid} step {i}", step, steps[i - 1] if i else None, contract, base)
    return out


def _step_problems(
    where: str, step: Json, before: Json | None, contract: Contract, base: pathlib.Path | str
) -> list[str]:
    """What is wrong with one step, [before] being the step before it (None for the first)."""
    out = []
    if step.get("direction") not in ("decode", "encode", "describe"):
        out.append(f"{where}: direction {step.get('direction')!r}")
    expect = step.get("expect") or {}
    if not expect:
        out.append(f"{where}: no expect")
    if "error" in expect and expect["error"] not in CATEGORIES:
        out.append(f"{where}: unknown error category {expect['error']!r}")
    if expect.get("error") != "Description":
        out += [f"{where}: {p}" for p in parameter_problems(step.get("params", {}), contract)]
    spec = step.get("input", {})
    if spec.get("previous") is True:
        if before is None or "error" in (before.get("expect") or {}):
            out.append(f"{where}: reads the previous step's output, and no previous step succeeds")
    else:
        try:
            input_bytes(spec, base)
        except (OSError, ValueError, KeyError) as e:
            out.append(f"{where}: unreadable input: {e}")
    samples = expect.get("samples")
    if samples and samples.get("sampleType") not in SAMPLE_TYPES:
        out.append(f"{where}: unknown sampleType {samples.get('sampleType')!r}")
    return out


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compare(vector: Json, result: Json) -> list[str]:
    """Differences between what [vector] expects and what an implementation reported."""
    out: list[str] = []
    reported = result.get("steps", [])
    for i, step in enumerate(vector["steps"]):
        if i >= len(reported):
            out.append(f"step {i}: not run")
            break
        out += _step_differences(i, step["expect"], reported[i])
    if "expectAll" in vector and not out:
        want, got = vector["expectAll"], result.get("all") or {}
        if got.get("sha256") != want["sha256"] or ("size" in want and got.get("size") != want["size"]):
            out.append(f"all steps: {got}, expected {want}")
    return out


def _step_differences(i: int, expect: Json, got: Json) -> list[str]:
    """Differences between what step [i] expects and what the implementation reported for it."""
    if "error" in expect:
        if got.get("ok") or got.get("category") != expect["error"]:
            return [f"step {i}: expected a {expect['error']} error, got {got}"]
        return []
    if not got.get("ok"):
        return [f"step {i}: expected success, got {got.get('category')}: {got.get('message')}"]
    out = _output_differences(i, expect, got)
    if "validitySha256" in expect and got.get("validitySha256") != expect["validitySha256"]:
        out.append(f"step {i}: validity masks {got.get('validitySha256')}, expected {expect['validitySha256']}")
    return out


def _output_differences(i: int, expect: Json, got: Json) -> list[str]:
    """Differences between the output step [i] expects (bytes, a digest or samples) and the one reported."""
    out = []
    if "hex" in expect or "base64" in expect:
        want = _decode_bytes(expect)
        if got.get("sha256") != sha256(want) or got.get("size") != len(want):
            out.append(
                f"step {i}: output {got.get('size')} bytes {got.get('sha256')}, expected {len(want)} "
                f"bytes {sha256(want)}"
            )
    elif "sha256" in expect:
        if got.get("sha256") != expect["sha256"] or ("size" in expect and got.get("size") != expect["size"]):
            out.append(f"step {i}: output {got.get('size')} bytes {got.get('sha256')}, expected {expect}")
    elif "samples" in expect:
        samples = expect["samples"]
        geometry = got.get("geometry") or {}
        for key in ("width", "height", "bands", "sampleType"):
            if key in samples and geometry.get(key) != samples[key]:
                out.append(f"step {i}: {key} {geometry.get(key)}, expected {samples[key]}")
        digest = got.get("sha256Band") if samples.get("order", "pixel") == "band" else got.get("sha256")
        if "sha256" in samples and digest != samples["sha256"]:
            out.append(
                f"step {i}: samples {digest}, expected {samples['sha256']} ({samples.get('order', 'pixel')} order)"
            )
    return out


def unpack(data: bytes, bits: int, width: int) -> bytes:
    """Rows of [width] samples of [bits] bits (MSB first, rows padded to a byte) as one byte per sample."""
    row_bytes = (width * bits + 7) // 8
    out = bytearray()
    for start in range(0, len(data) - len(data) % row_bytes if row_bytes else 0, row_bytes):
        row = data[start : start + row_bytes]
        for x in range(width):
            bit = x * bits
            value = 0
            for k in range(bits):
                b = bit + k
                value = (value << 1) | ((row[b // 8] >> (7 - b % 8)) & 1)
            out.append(value)
    return bytes(out)


def deinterleave(data: bytes, bands: int, item: int = 1) -> bytes:
    """Pixel-interleaved samples of [bands] bands (each [item] bytes) rewritten band-sequentially."""
    pixels = len(data) // (bands * item)
    out = bytearray(len(data))
    for p in range(pixels):
        for b in range(bands):
            src = (p * bands + b) * item
            dst = (b * pixels + p) * item
            out[dst : dst + item] = data[src : src + item]
    return bytes(out)


MENC = "https://hexplain.io/ns/register/media-encoding#"


def step(
    data: bytes,
    expect: Json,
    params: Json | None = None,
    direction: str = "decode",
    max_output: int | None = None,
    file: str | None = None,
) -> Json:
    """One vector step over [data] (inline hex), or over [file] beside the manifest when given."""
    s: Json = {
        "direction": direction,
        "params": params or {},
        "input": {"file": file} if file else {"hex": data.hex()},
        "expect": expect,
    }
    if max_output is not None:
        s["maxOutputBytes"] = max_output
    return s


def write_suite(name: str, sources: list[Json], vector_list: list[Json], files: dict[str, bytes] | None = None) -> None:
    """Write specification/codecs/<name>/vectors/manifest.json and the binary [files] beside it."""
    directory = ROOT / "specification" / "codecs" / name / "vectors"
    directory.mkdir(parents=True, exist_ok=True)
    for rel, data in (files or {}).items():
        (directory / rel).write_bytes(data)
    manifest = {
        "codec": MENC + name,
        "suiteVersion": 1,
        "sources": sources,
        "vectors": [dict(v, source=v.get("source", sources[0]["id"])) for v in vector_list],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
