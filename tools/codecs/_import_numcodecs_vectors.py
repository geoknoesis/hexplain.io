"""Import the Blosc and numcodecs filter vectors written with numcodecs 0.16.5 (c-blosc 1.21).

hexplain-tools codecs-array/src/test/resources/zarr/numcodecs-vectors.json (tests/gdal/zarr_codec_vectors.py)
holds every Blosc inner compressor and shuffle mode and the Delta, Shuffle, BitRound, Quantize and
FixedScaleOffset filters, each with the bytes numcodecs decodes. BloscLZ vectors are the first
block of the unshuffled one-byte-element BloscLZ frames: one split, whose decoded bytes are the
frame's first block.
Usage: python tools/codecs/_import_numcodecs_vectors.py --engine d:/work/hexplain-tools
"""
import argparse
import ast
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from vectors import sha256, step, write_suite  # noqa: E402

NUMCODECS = {"id": "numcodecs", "url": "https://github.com/zarr-developers/numcodecs",
             "description": "Chunks written by numcodecs 0.16.5 with c-blosc 1.21.7.dev (numpy 2.3.2, Python 3.11.4) through "
                            "hexplain-tools tests/gdal/zarr_codec_vectors.py (codecs-array/src/test/resources/zarr/numcodecs-vectors.json).",
             "licence": "MIT (numcodecs), BSD-3-Clause (c-blosc); data CC0-1.0"}
FILTERS = {"delta": "TypedDelta", "shuffle": "Shuffle", "bitround": "BitRound", "quantize": "Quantize",
           "fixedscaleoffset": "FixedScaleOffset"}


def filter_params(config):
    kind = config["id"]
    if kind == "delta":
        return {"dtype": config["dtype"], "astype": config["astype"]}
    if kind == "shuffle":
        return {"elementSize": int(config["elementsize"])}
    if kind == "bitround":
        return {"keepbits": int(config["keepbits"])}
    if kind == "quantize":
        return {"digits": int(config["digits"]), "dtype": config["dtype"], "astype": config["astype"]}
    return {"offset": float(config["offset"]), "scale": float(config["scale"]), "dtype": config["dtype"], "astype": config["astype"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    engine = pathlib.Path(parser.parse_args().engine)
    source = json.loads((engine / "core/src/test/resources/zarr/numcodecs-vectors.json").read_text(encoding="utf-8"))["vectors"]
    suites = {name: [] for name in ("Blosc", "BloscLZ", *FILTERS.values())}
    for v in source:
        encoded, decoded = bytes.fromhex(v["encoded"]), bytes.fromhex(v["decoded"])
        vid = v["name"].replace(" ", "-").replace("=", "-").replace("<", "le").replace(">", "be").replace("|", "")
        if v["group"] == "blosc":
            expect = {"sha256": sha256(decoded), "size": len(decoded)}
            suites["Blosc"].append({"id": vid, "steps": [step(encoded, expect)]})
            if decoded:
                suites["Blosc"].append({"id": vid + "-over-bound",
                                        "steps": [step(encoded, {"error": "ResourceLimit"}, max_output=len(decoded) - 1)]})
            flags, typesize = encoded[2], encoded[3]
            if v["name"].startswith("blosclz shuffle=0 u1") and flags & 0x02 == 0 and typesize == 1:
                blocksize = struct.unpack("<i", encoded[8:12])[0]
                start = struct.unpack("<i", encoded[16:20])[0]
                cbytes = struct.unpack("<i", encoded[start:start + 4])[0]
                size = min(blocksize, len(decoded))
                if cbytes != size:
                    suites["BloscLZ"].append({"id": vid, "steps": [step(encoded[start + 4:start + 4 + cbytes],
                                                                         {"hex": decoded[:size].hex()}, {"decodedSize": size})]})
        elif v["group"] == "filter":
            config = ast.literal_eval(v["config"]) if isinstance(v["config"], str) else v["config"]
            suites[FILTERS[config["id"]]].append({"id": vid, "steps": [step(encoded, {"hex": decoded.hex()}, filter_params(config))]})
    suites["Blosc"].append({"id": "snappy-inner-unsupported", "steps": [step(
        bytes([2, 1, 0x41, 1]) + struct.pack("<iii", 16, 16, 28) + struct.pack("<i", 20) + struct.pack("<i", 4) + b"abcd",
        {"error": "Unsupported"})]})
    suites["FixedScaleOffset"].append({"id": "zero-scale", "steps": [step(bytes([1]), {"error": "Validation"},
        {"offset": 0.0, "scale": 0.0, "dtype": "<f4", "astype": "|u1"})]})
    suites["TypedDelta"].append({"id": "unknown-dtype", "steps": [step(bytes(4), {"error": "Unsupported"}, {"dtype": "<c8"})]})
    for codec, vector_list in suites.items():
        if not vector_list:
            raise SystemExit(f"FAIL: no numcodecs vector for {codec}")
        write_suite(codec, [NUMCODECS], vector_list)
    print("PASS: " + ", ".join(f"{codec} {len(v)}" for codec, v in suites.items()))


if __name__ == "__main__":
    main()
