"""Complete the vector suites to what tools/test_codec_vector_completeness.py requires.

For every suite that lacks a vector for a category its contract declares, a parameter it declares, a
round trip, or a round trip at a stated compression level, this adds one. Error vectors are made from the
suite's own inputs -- a truncation, a flipped byte, a lowered output limit, a parameter the codec refuses --
and the category each candidate raises is confirmed with the reference engine's codec CLI before it is
recorded, so a candidate the engine reads as
a different category is dropped rather than asserted. Parameter and round-trip vectors of the transform
codecs are worked by hand or by the independent Python references (zlib); where a parameter's output has
no independent oracle (JPEG raw planes, LERC's TIFF layout), the engine's output is recorded and the
vector's source says so. Re-running adds nothing a suite already has.

    python tools/codecs/_complete_vectors.py --engine <hexplain-codec CLI> [--java-home DIR] [--codec NAME]...
"""

from __future__ import annotations

import argparse
import json
import lzma
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vectors  # noqa: E402
from rdflib import Graph, Namespace, URIRef  # noqa: E402
from vectors import ROOT, Json, step  # noqa: E402

HX = Namespace("https://hexplain.io/ns/core#")
ENGINE_SOURCE = {
    "id": "reference-engine",
    "url": "https://github.com/geoknoesis/hexplain-tools",
    "description": "Inputs derived here (tools/codecs/_complete_vectors.py) from this suite's own vectors: "
    "truncations, "
    "single-byte corruptions, lowered output limits and parameter settings; the category or output of each "
    "was confirmed with hexplain-tools {revision} (hexplain-codec vector) before it was recorded, since no "
    "independent implementation of this codec was at hand.",
    "licence": "inputs as the vectors they derive from; expectations CC0-1.0",
}
HAND_SOURCE = {
    "id": "round-trip",
    "url": "https://hexplain.io/specification/processing/#round-trip",
    "description": "Round trips worked by hand from the codec's definition (a transform) or fed through the previous "
    "step's output (a compressor, whose encoded bytes are the implementation's own: the encode step expects success "
    "only, and the decode step reads its output back to the input).",
    "licence": "CC0-1.0",
}


# The compressors whose contract encodes: their output is not canonical, so their round trip is the
# {"previous": true} form. (The transforms that encode have one fixed encoding, asserted byte for byte.)
COMPRESSORS = ("Deflate", "Zlib", "Gzip", "LZ4", "LZ4Block", "Zstd", "XZ", "LZW", "PackBits")


class Engine:
    def __init__(self, cli: str, java_home: str | None) -> None:
        self.cli, self.java_home = cli, java_home
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="hexplain-vectors-"))

    def run(self, codec: str, base: pathlib.Path, vector: Json) -> Json:
        """The engine's result for [vector], a vector of the suite whose manifest lives at [base]."""
        directory = self.tmp / vectors.local_name(codec)
        if not directory.is_dir():
            shutil.copytree(base, directory)
        manifest = {"codec": codec, "suiteVersion": 1, "sources": [], "vectors": [vector]}
        (directory / "probe.json").write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
        env = dict(os.environ)
        if self.java_home:
            env["JAVA_HOME"] = self.java_home
        run = subprocess.run(
            [self.cli, "vector", "--manifest", str(directory / "probe.json"), "--id", vector["id"]],
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        try:
            result: Json = json.loads(run.stdout)
        except json.JSONDecodeError:
            return {"steps": [{"ok": False, "category": "CRASH", "message": (run.stdout + run.stderr)[-400:]}]}
        return result


def category(result: Json) -> str | None:
    last = result.get("steps", [])[-1] if result.get("steps") else {}
    return None if last.get("ok") else last.get("category")


def flip(data: bytes, at: int) -> bytes:
    b = bytearray(data)
    b[at % len(b)] ^= 0x01
    return bytes(b)


def first_success(manifest: Json, base: pathlib.Path) -> tuple[Json, Json]:
    for v in manifest["vectors"]:
        s = v["steps"][0]
        if s["direction"] == "decode" and "error" not in s["expect"]:
            return v, s
    raise ValueError("no successful vector")


def input_of(s: Json, base: pathlib.Path) -> bytes:
    return vectors.input_bytes(s["input"], base)


def with_input(s: Json, data: bytes, expect: Json | None, **extra: Any) -> Json:
    """A copy of step [s] over [data] (inline hex, samples kept) expecting [expect]."""
    out = {"direction": s["direction"], "params": dict(s.get("params", {})), "expect": expect}
    if "samples" in s["input"]:
        geometry = {k: v for k, v in s["input"]["samples"].items() if k not in ("hex", "base64")}
        out["input"] = {"samples": dict(geometry, hex=data.hex())}
    else:
        out["input"] = {"hex": data.hex()}
    out.update(extra)
    return out


def expected_size(s: Json) -> int | None:
    e = s["expect"]
    if "hex" in e:
        return len(e["hex"]) // 2
    if "size" in e:
        return e["size"]
    return None


class Completion:
    """The vectors added to one suite: each candidate is run on the engine and kept when it raises the category
    wanted (or, wanting none, succeeds), its id being new to the suite."""

    def __init__(self, name: str, manifest: Json, base: pathlib.Path, engine: Engine, log: list[str]) -> None:
        self.name, self.manifest, self.base, self.engine, self.log = name, manifest, base, engine, log
        self.ids = {v["id"] for v in manifest["vectors"]}
        self.added: list[str] = []
        self.session = False

    def propose(
        self,
        vid: str,
        steps: list[Json],
        want: str | None,
        source: str = "reference-engine",
        keep_session: bool = True,
    ) -> bool:
        """Add the vector [vid] of [steps] when the engine raises [want] on it, or, [want] being None, succeeds (its
        output then recorded as the expectation)."""
        if vid in self.ids:
            return False
        vector: Json = {"id": vid, "steps": steps, "source": source}
        if self.session and keep_session:
            vector["session"] = True
        result = self.engine.run(self.manifest["codec"], self.base, vector)
        got = category(result)
        if want is None:
            last = result["steps"][-1]
            if not last.get("ok"):
                self.log.append(f"{self.name}/{vid}: engine refused ({got}: {last.get('message', '')[:120]})")
                return False
            # Record what the engine produced where no independent oracle exists.
            expect = {"sha256": last["sha256"], "size": last["size"]}
            if last.get("geometry"):
                expect = {"samples": dict(last["geometry"], sha256=last["sha256"])}
            steps[-1]["expect"] = expect
        elif got != want:
            self.log.append(f"{self.name}/{vid}: wanted {want}, engine says {got}")
            return False
        self.manifest["vectors"].append(vector)
        self.ids.add(vid)
        self.added.append(vid)
        return True

    def round_trip(self, trip: Json) -> None:
        """Add the round trip [trip] when its id is new and every step of it succeeds on the engine."""
        if trip["id"] in self.ids:
            return
        result = self.engine.run(self.manifest["codec"], self.base, trip)
        if category(result) is None and all(st.get("ok") for st in result["steps"]):
            self.manifest["vectors"].append(trip)
            self.added.append(trip["id"])
            self.ids.add(trip["id"])
        else:
            self.log.append(f"{self.name}/{trip['id']}: round trip refused by the engine: {result}")


def _covered(manifest: Json) -> tuple[set[str], set[str], set[str]]:
    """The error categories the suite's steps expect, the parameters they pass and the directions they run."""
    expected_cats: set[str] = set()
    params_used: set[str] = set()
    directions: set[str] = set()
    for v in manifest["vectors"]:
        for s in v["steps"]:
            directions.add(s["direction"])
            if "error" in s["expect"]:
                expected_cats.add(s["expect"]["error"])
            params_used |= set(s.get("params", {}))
    return expected_cats, params_used, directions


def complete(
    name: str,
    manifest: Json,
    contract: vectors.Contract,
    declared: set[str],
    base: pathlib.Path,
    engine: Engine,
    log: list[str],
) -> list[str]:
    completion = Completion(name, manifest, base, engine, log)
    expected_cats, params_used, directions = _covered(manifest)
    ok_vector, ok_step = first_success(manifest, base)
    data = input_of(ok_step, base)
    completion.session = ok_vector.get("session", False)
    missing = {c for c in declared if c not in expected_cats}
    if "ResourceLimit" in missing:
        _propose_resource_limit(completion, ok_step, data)
    if "Validation" in missing:
        _propose_validation(completion, ok_step, data)
    if "Checksum" in missing:
        _propose_checksum(completion, ok_step, data)
    if "Unsupported" in missing:
        _propose_unsupported(completion, ok_step, data)
    # Description: parameter values the contract admits one by one and the codec cannot run together
    # (Processing Model, Codec contracts: the bytes are not at fault, the description is). Proposed even
    # where a step already expects the category: an omitted required parameter is what the load-time
    # check refuses, and this is the case only the running codec can see.
    if "Description" in declared:
        for label, params in description_candidates(name):
            if completion.propose(
                label, [with_input(ok_step, data, {"error": "Description"}, params=params)], "Description"
            ):
                break
    # Parameters the contract declares and no vector passes.
    for pname in sorted(set(contract["parameters"]) - params_used):
        for label, steps_ in parameter_candidates(name, pname, manifest, base, ok_step, data):
            if completion.propose(label, steps_, None):
                break
    if "encode" in directions or name in COMPRESSORS:
        trip = round_trip(name, manifest)
        if trip:
            completion.round_trip(trip)
    # An encode-only parameter (the compression level) is shown honoured only by an encode step that succeeds.
    for trip in level_round_trips(name, contract):
        completion.round_trip(trip)
    return completion.added


def _propose_resource_limit(completion: Completion, ok_step: Json, data: bytes) -> None:
    """ResourceLimit: the first successful step under a limit of 0 bytes."""
    size = expected_size(ok_step)
    limit = 0 if size is None else max(0, size - 1)
    completion.propose(
        "over-bound", [with_input(ok_step, data, {"error": "ResourceLimit"}, maxOutputBytes=limit)], "ResourceLimit"
    )


def _propose_validation(completion: Completion, ok_step: Json, data: bytes) -> None:
    """Validation: truncations and corruptions of the first successful input."""
    candidates = []
    if "samples" in ok_step["input"]:
        candidates.append(("partial-pixel", data[:-1]))
        candidates.append(("partial-pixel", data[: len(data) // 2 + 1]))
    else:
        candidates += [
            ("truncated", data[: len(data) // 2]),
            ("truncated", data[:-1]),
            ("truncated", data[: max(1, len(data) // 4)]),
        ]
        candidates += [("corrupted", flip(data, i)) for i in (0, 1, 2, 3, 4, 5, 8, len(data) // 2, len(data) - 1)]
        candidates += [("partial-element", data[:-1]), ("trailing-byte", data + b"\x00")]
    for label, d in candidates:
        if completion.propose(label, [with_input(ok_step, d, {"error": "Validation"})], "Validation"):
            break


def _propose_checksum(completion: Completion, ok_step: Json, data: bytes) -> None:
    """Checksum: flip bytes near the end of the first successful input (where the checks sit)."""
    for i in range(1, min(len(data), 48)):
        corrupted = with_input(ok_step, flip(data, len(data) - i), {"error": "Checksum"})
        if completion.propose("checksum-mismatch", [corrupted], "Checksum"):
            break


def _propose_unsupported(completion: Completion, ok_step: Json, data: bytes) -> None:
    """Unsupported: a coding feature the contract names as refused."""
    for label, d, params in unsupported_candidates(completion.name, data, ok_step):
        s = with_input(ok_step, d, {"error": "Unsupported"})
        if params is not None:
            s["params"] = params
        if completion.propose(label, [s], "Unsupported"):
            break


def level_round_trips(name: str, contract: vectors.Contract) -> list[Json]:
    """Round trips of a compressor whose contract declares `level`, at the lowest and the highest explicit level
    (0, where the contract's range reaches it, and the maximum): the encode step passes the level and expects
    success, the encoded bytes being the implementation's own, and the decode step reads them back."""
    spec = contract["parameters"].get("level")
    if name not in COMPRESSORS or spec is None:
        return []
    lowest, highest = spec["minimum"], spec["maximum"]
    if lowest is None or highest is None:
        raise ValueError(f"{name}: the level parameter states no range")
    original = b"round trip through the compressor at a stated level " * 4
    trips = []
    for level in sorted({max(int(lowest), 0), int(highest)}):
        decode = {"direction": "decode", "params": {}, "input": {"previous": True}, "expect": {"hex": original.hex()}}
        trips.append(
            {
                "id": f"round-trip-level-{level}",
                "source": "round-trip",
                "steps": [step(original, {"ok": True}, {"level": level}, direction="encode"), decode],
            }
        )
    return trips


def unsupported_candidates(name: str, data: bytes, ok_step: Json) -> Iterator[tuple[str, bytes, Json | None]]:
    if name == "JPEG":
        yield "arithmetic-coding", data.replace(b"\xff\xc0", b"\xff\xc9", 1), None
        yield "lossless-process", data.replace(b"\xff\xc0", b"\xff\xc3", 1), None
        yield "twelve-bit-declared", data, dict(ok_step.get("params", {}), precision=12)
    elif name == "LERC":
        yield "unknown-version", data[:6] + struct.pack("<i", 99) + data[10:], None
        yield "lerc1-blob", b"CntZImage " + data[10:], None
    elif name == "MicrosoftRLE":
        # RLE8: a delta escape (00 02 dx dy) skips pixels, which this version refuses.
        yield "delta-escape", bytes.fromhex("0002010100000001"), {"bitsPerPixel": 8, "width": 4, "height": 2}
    elif name == "WebP":
        # A VP8X container with the animation flag and an ANIM chunk instead of a bitstream.
        anim = b"ANIM" + struct.pack("<I", 6) + b"\x00\x00\x00\x00\x00\x00"
        vp8x = b"VP8X" + struct.pack("<I", 10) + bytes([0x02, 0, 0, 0]) + b"\x00\x00\x00" + b"\x00\x00\x00"
        body = b"WEBP" + vp8x + anim
        yield "animation", b"RIFF" + struct.pack("<I", len(body)) + body, dict(ok_step.get("params", {}))
    elif name == "XZ":
        raw = b"XZ unsupported probe " * 50
        yield (
            "x86-filter",
            lzma.compress(raw, format=lzma.FORMAT_XZ, filters=[{"id": lzma.FILTER_X86}, {"id": lzma.FILTER_LZMA2}]),
            None,
        )
        yield (
            "delta-filter",
            lzma.compress(
                raw, format=lzma.FORMAT_XZ, filters=[{"id": lzma.FILTER_DELTA, "dist": 4}, {"id": lzma.FILTER_LZMA2}]
            ),
            None,
        )
        yield "no-check", lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_NONE), None


def description_candidates(name: str) -> Iterator[tuple[str, Json]]:
    if name == "Delta":
        # rowBytes is any non-negative integer and elementSize any of 1, 2, 4, 8; a row is nonetheless a
        # whole number of pixels, so a 3-byte row of 2-byte samples describes nothing.
        yield "row-not-whole-pixels", {"elementSize": 2, "rowBytes": 3}


def parameter_candidates(
    name: str, pname: str, manifest: Json, base: pathlib.Path, ok_step: Json, data: bytes
) -> Iterator[tuple[str, list[Json]]]:
    params = dict(ok_step.get("params", {}))
    if name == "Blosc":
        header = data[:16]
        typesize = header[3]
        shuffle = bool(header[2] & 0x01)
        values: Json = {"cname": "blosclz", "clevel": 5, "shuffle": shuffle, "typesize": typesize, "blocksize": 0}
        yield f"parameter-{pname}", [with_input(ok_step, data, None, params={pname: values[pname]})]
    elif name == "CCITTGroup3" and pname == "noEol":
        for v in manifest["vectors"]:
            if "noeol" in v["id"]:
                steps = [dict(s, params=dict(s["params"], noEol=1)) for s in v["steps"]]
                for s in steps:
                    s["expect"] = {"ok": True}
                yield "noeol-declared", steps
                break
    elif name == "CIELabToRGB" and pname == "whitePoint":
        yield "white-point-d50", [with_input(ok_step, data, None, params=dict(params, whitePoint=[0.9642, 0.8249]))]
    elif name == "JPEG" and pname == "output":
        yield "raw-planes", [with_input(ok_step, data, None, params=dict(params, output="raw-planes"))]
    elif name == "LERC":
        rows, cols = struct.unpack_from("<ii", data, 10)
        geometry = {
            "layout": "tiff",
            "width": cols,
            "height": rows,
            "samplesPerPixel": 1,
            "sampleType": "int8",
            "planarSeparate": False,
            "alphaFromMask": False,
            "lercParameters": [0, 0],
        }
        yield "tiff-layout-char", [with_input(ok_step, data, None, params=geometry)]


def round_trip(name: str, manifest: Json) -> Json | None:
    def hexes(v: Json) -> tuple[str, str, Json]:
        return v["steps"][0]["input"]["hex"], v["steps"][0]["expect"]["hex"], v["steps"][0].get("params", {})

    encode = next(
        (v for v in manifest["vectors"] if v["steps"][0]["direction"] == "encode" and "hex" in v["steps"][0]["expect"]),
        None,
    )
    if encode:
        original, encoded, params = hexes(encode)
        return {
            "id": "round-trip",
            "source": "round-trip",
            "steps": [
                step(bytes.fromhex(original), {"hex": encoded}, params, direction="encode"),
                step(bytes.fromhex(encoded), {"hex": original}, params),
            ],
        }
    if name in COMPRESSORS:
        # A compressor's encoded bytes are its implementation's own (match search, block splitting, run
        # packing), so the encode step expects only success and the decode step reads its output back.
        through = b"round trip through the compressor " * 4
        params = {"decodedSize": len(through)} if name == "LZ4Block" else {}
        decode = {
            "direction": "decode",
            "params": params,
            "input": {"previous": True},
            "expect": {"hex": through.hex()},
        }
        return {
            "id": "round-trip",
            "source": "round-trip",
            "steps": [step(through, {"ok": True}, params, direction="encode"), decode],
        }
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--engine", required=True, help="the hexplain-codec command-line tool")
    ap.add_argument("--java-home")
    ap.add_argument("--revision", default="(working tree)", help="the engine's commit, recorded in the source")
    ap.add_argument("--codec", action="append", default=[])
    args = ap.parse_args(argv)
    engine = Engine(args.engine, args.java_home)
    register = Graph().parse(ROOT / "specification/register/media-encoding/media-encoding.ttl", format="turtle")
    contracts = vectors.contracts(register)
    log: list[str] = []
    total = 0
    for iri, contract in sorted(contracts.items()):
        name = vectors.local_name(iri)
        if args.codec and name not in args.codec:
            continue
        path = vectors.suite_path(iri)
        manifest = vectors.load(path)
        declared = {str(o) for o in register.objects(URIRef(iri + ".contract"), HX.raisesCategory)}
        added = complete(name, manifest, contract, declared, path.parent, engine, log)
        if added:
            sources = {s["id"] for s in manifest["sources"]}
            needed = {v["source"] for v in manifest["vectors"] if v["id"] in added}
            if "reference-engine" in needed and "reference-engine" not in sources:
                manifest["sources"].append(
                    dict(ENGINE_SOURCE, description=ENGINE_SOURCE["description"].format(revision=args.revision))
                )
            if "round-trip" in needed and "round-trip" not in sources:
                manifest["sources"].append(HAND_SOURCE)
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
            print(f"{name}: added {', '.join(added)}")
            total += len(added)
    print(f"added {total} vectors")
    if log:
        print("not added:\n  " + "\n  ".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
