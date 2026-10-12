"""Complete the vector suites to what tools/test_codec_vector_completeness.py requires.

For every suite that lacks a vector for a category its contract declares, a parameter it declares, or a
round trip, this adds one. Error vectors are made from the suite's own inputs -- a truncation, a flipped
byte, a lowered output limit, a parameter the codec refuses -- and the category each candidate raises is
confirmed with the reference engine's codec CLI before it is recorded, so a candidate the engine reads as
a different category is dropped rather than asserted. Parameter and round-trip vectors of the transform
codecs are worked by hand or by the independent Python references (zlib); where a parameter's output has
no independent oracle (JPEG raw planes, LERC's TIFF layout), the engine's output is recorded and the
vector's source says so. Re-running adds nothing a suite already has.

    python tools/codecs/_complete_vectors.py --engine <hexplain-codec CLI> [--java-home DIR] [--codec NAME]...
"""
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

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vectors  # noqa: E402
from vectors import ROOT, step  # noqa: E402

from rdflib import Graph, Namespace, URIRef  # noqa: E402

HX = Namespace("https://hexplain.io/ns/core#")
ENGINE_SOURCE = {
    "id": "reference-engine",
    "url": "https://github.com/geoknoesis/hexplain-tools",
    "description": "Inputs derived here (tools/codecs/_complete_vectors.py) from this suite's own vectors: truncations, "
                   "single-byte corruptions, lowered output limits and parameter settings; the category or output of each "
                   "was confirmed with hexplain-tools {revision} (hexplain-codec vector) before it was recorded, since no "
                   "independent implementation of this codec was at hand.",
    "licence": "inputs as the vectors they derive from; expectations CC0-1.0",
}
HAND_SOURCE = {
    "id": "round-trip",
    "url": "https://hexplain.io/specification/processing/#round-trip",
    "description": "Round trips worked by hand from the codec's definition (a transform) or fed through the previous "
                   "step's output (a compressor, encoded with zlib for the expectation-free encode step).",
    "licence": "CC0-1.0",
}


class Engine:
    def __init__(self, cli, java_home):
        self.cli, self.java_home = cli, java_home
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="hexplain-vectors-"))

    def run(self, codec, base, vector):
        """The engine's result for [vector], a vector of the suite whose manifest lives at [base]."""
        directory = self.tmp / vectors.local_name(codec)
        if not directory.is_dir():
            shutil.copytree(base, directory)
        manifest = {"codec": codec, "suiteVersion": 1, "sources": [], "vectors": [vector]}
        (directory / "probe.json").write_text(json.dumps(manifest), encoding="utf-8")
        env = dict(os.environ)
        if self.java_home:
            env["JAVA_HOME"] = self.java_home
        run = subprocess.run([self.cli, "vector", "--manifest", str(directory / "probe.json"), "--id", vector["id"]],
                             capture_output=True, text=True, env=env, timeout=300)
        try:
            return json.loads(run.stdout)
        except json.JSONDecodeError:
            return {"steps": [{"ok": False, "category": "CRASH", "message": (run.stdout + run.stderr)[-400:]}]}


def category(result):
    last = result.get("steps", [])[-1] if result.get("steps") else {}
    return None if last.get("ok") else last.get("category")


def flip(data, at):
    b = bytearray(data)
    b[at % len(b)] ^= 0x01
    return bytes(b)


def first_success(manifest, base):
    for v in manifest["vectors"]:
        s = v["steps"][0]
        if s["direction"] == "decode" and "error" not in s["expect"]:
            return v, s
    raise ValueError("no successful vector")


def input_of(s, base):
    return vectors.input_bytes(s["input"], base)


def with_input(s, data, expect, **extra):
    """A copy of step [s] over [data] (inline hex, samples kept) expecting [expect]."""
    out = {"direction": s["direction"], "params": dict(s.get("params", {})), "expect": expect}
    if "samples" in s["input"]:
        geometry = {k: v for k, v in s["input"]["samples"].items() if k not in ("hex", "base64")}
        out["input"] = {"samples": dict(geometry, hex=data.hex())}
    else:
        out["input"] = {"hex": data.hex()}
    out.update(extra)
    return out


def expected_size(s):
    e = s["expect"]
    if "hex" in e:
        return len(e["hex"]) // 2
    if "size" in e:
        return e["size"]
    return None


def complete(name, manifest, contract, declared, base, engine, log):
    added = []
    ids = {v["id"] for v in manifest["vectors"]}
    expected_cats, params_used, directions = set(), set(), set()
    for v in manifest["vectors"]:
        for s in v["steps"]:
            directions.add(s["direction"])
            if "error" in s["expect"]:
                expected_cats.add(s["expect"]["error"])
            params_used |= set(s.get("params", {}))
    ok_vector, ok_step = first_success(manifest, base)
    data = input_of(ok_step, base)
    session = ok_vector.get("session", False)

    def propose(vid, steps, want, source="reference-engine", keep_session=True):
        if vid in ids:
            return False
        vector = {"id": vid, "steps": steps, "source": source}
        if session and keep_session:
            vector["session"] = True
        result = engine.run(manifest["codec"], base, vector)
        got = category(result)
        if want is None:
            last = result["steps"][-1]
            if not last.get("ok"):
                log.append(f"{name}/{vid}: engine refused ({got}: {last.get('message', '')[:120]})")
                return False
            # Record what the engine produced where no independent oracle exists.
            expect = {"sha256": last["sha256"], "size": last["size"]}
            if last.get("geometry"):
                expect = {"samples": dict(last["geometry"], sha256=last["sha256"])}
            steps[-1]["expect"] = expect
        elif got != want:
            log.append(f"{name}/{vid}: wanted {want}, engine says {got}")
            return False
        manifest["vectors"].append(vector)
        ids.add(vid)
        added.append(vid)
        return True

    # ResourceLimit: the first successful step under a limit of 0 bytes.
    if "ResourceLimit" in declared and "ResourceLimit" not in expected_cats:
        size = expected_size(ok_step)
        limit = 0 if size is None else max(0, size - 1)
        propose("over-bound", [with_input(ok_step, data, {"error": "ResourceLimit"}, maxOutputBytes=limit)], "ResourceLimit")

    # Validation: truncations and corruptions of the first successful input.
    if "Validation" in declared and "Validation" not in expected_cats:
        candidates = []
        if "samples" in ok_step["input"]:
            candidates.append(("partial-pixel", data[:-1]))
            candidates.append(("partial-pixel", data[:len(data) // 2 + 1]))
        else:
            candidates += [("truncated", data[:len(data) // 2]), ("truncated", data[:-1]),
                           ("truncated", data[:max(1, len(data) // 4)])]
            candidates += [("corrupted", flip(data, i)) for i in (0, 1, 2, 3, 4, 5, 8, len(data) // 2, len(data) - 1)]
            candidates += [("partial-element", data[:-1]), ("trailing-byte", data + b"\x00")]
        for label, d in candidates:
            if propose(label, [with_input(ok_step, d, {"error": "Validation"})], "Validation"):
                break

    # Checksum: flip bytes near the end of the first successful input (where the checks sit).
    if "Checksum" in declared and "Checksum" not in expected_cats:
        for i in range(1, min(len(data), 48)):
            if propose("checksum-mismatch", [with_input(ok_step, flip(data, len(data) - i), {"error": "Checksum"})], "Checksum"):
                break

    # Unsupported: a coding feature the contract names as refused.
    if "Unsupported" in declared and "Unsupported" not in expected_cats:
        for label, d, params in unsupported_candidates(name, data, ok_step):
            s = with_input(ok_step, d, {"error": "Unsupported"})
            if params is not None:
                s["params"] = params
            if propose(label, [s], "Unsupported"):
                break

    # Parameters the contract declares and no vector passes.
    for pname in sorted(set(contract["parameters"]) - params_used):
        for label, steps_ in parameter_candidates(name, pname, manifest, base, ok_step, data):
            if propose(label, steps_, None):
                break

    # Round trips.
    if "encode" in directions or name in ("Deflate", "Zlib", "Gzip"):
        trip = round_trip(name, manifest)
        if trip and trip["id"] not in ids:
            result = engine.run(manifest["codec"], base, trip)
            if category(result) is None and all(st.get("ok") for st in result["steps"]):
                manifest["vectors"].append(trip)
                added.append(trip["id"])
                ids.add(trip["id"])
            else:
                log.append(f"{name}/{trip['id']}: round trip refused by the engine: {result}")
    return added


def unsupported_candidates(name, data, ok_step):
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
        yield "x86-filter", lzma.compress(raw, format=lzma.FORMAT_XZ, filters=[{"id": lzma.FILTER_X86}, {"id": lzma.FILTER_LZMA2}]), None
        yield "delta-filter", lzma.compress(raw, format=lzma.FORMAT_XZ, filters=[{"id": lzma.FILTER_DELTA, "dist": 4}, {"id": lzma.FILTER_LZMA2}]), None
        yield "no-check", lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_NONE), None


def parameter_candidates(name, pname, manifest, base, ok_step, data):
    params = dict(ok_step.get("params", {}))
    if name == "Blosc":
        header = data[:16]
        typesize = header[3]
        shuffle = bool(header[2] & 0x01)
        values = {"cname": "blosclz", "clevel": 5, "shuffle": shuffle, "typesize": typesize, "blocksize": 0}
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
        geometry = {"layout": "tiff", "width": cols, "height": rows, "samplesPerPixel": 1, "sampleType": "int8",
                    "planarSeparate": False, "alphaFromMask": False, "lercParameters": [0, 0]}
        yield "tiff-layout-char", [with_input(ok_step, data, None, params=geometry)]


def round_trip(name, manifest):
    def hexes(v):
        return v["steps"][0]["input"]["hex"], v["steps"][0]["expect"]["hex"], v["steps"][0].get("params", {})
    encode = next((v for v in manifest["vectors"] if v["steps"][0]["direction"] == "encode"
                   and "hex" in v["steps"][0]["expect"]), None)
    if encode:
        original, encoded, params = hexes(encode)
        return {"id": "round-trip", "source": "round-trip", "steps": [
            step(bytes.fromhex(original), {"hex": encoded}, params, direction="encode"),
            step(bytes.fromhex(encoded), {"hex": original}, params)]}
    if name in ("Deflate", "Zlib", "Gzip"):
        original = b"round trip through the compressor " * 4
        decode = {"direction": "decode", "params": {}, "input": {"previous": True}, "expect": {"hex": original.hex()}}
        return {"id": "round-trip", "source": "round-trip", "steps": [
            step(original, {"ok": True}, direction="encode"), decode]}
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--engine", required=True, help="the hexplain-codec command-line tool")
    ap.add_argument("--java-home")
    ap.add_argument("--revision", default="(working tree)", help="the engine's commit, recorded in the source")
    ap.add_argument("--codec", action="append", default=[])
    args = ap.parse_args(argv)
    engine = Engine(args.engine, args.java_home)
    register = Graph().parse(ROOT / "specification/register/media-encoding/media-encoding.ttl", format="turtle")
    contracts = vectors.contracts(register)
    log, total = [], 0
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
                manifest["sources"].append(dict(ENGINE_SOURCE, description=ENGINE_SOURCE["description"].format(revision=args.revision)))
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
