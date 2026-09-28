"""Import the LZ4, LZ4 Block, Zstandard and XZ vectors the reference engine's codec tests use.

Sources recorded in the manifests:
  * reference libraries: python-lz4 1.9.4 (liblz4 1.9.4), python-zstandard 0.25 and CPython's lzma
    module (liblzma), through hexplain-tools codecs/lz/src/test/resources/codec/generate_vectors.py and
    codecs/xz/src/test/resources/codec/generate_xz_vectors.py, over the deterministic 150000-byte payload
    rebuilt below;
  * numcodecs 0.16.5 chunks (lz4, zstd, lzma, lzma-alone groups of
    core/src/test/resources/zarr/numcodecs-vectors.json, written by tests/gdal/zarr_codec_vectors.py);
  * frames hand-built here from the LZ4 Frame Format Description and RFC 8878 for error cases.

Usage: python tools/codecs/_import_engine_vectors.py --engine d:/work/hexplain-tools
"""
import argparse
import json
import pathlib
import random
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from conformance.lz4frames import xxh32  # noqa: E402
from vectors import sha256, step, write_suite  # noqa: E402

TEXT = b"Hexplain reads LZ4 and Zstandard. "


def payload(n):
    b = bytearray(n)
    for i in range(n):
        b[i] = TEXT[i % len(TEXT)] if (i // 1000) % 2 == 0 else ((i * 2654435761) >> 13) & 0xFF
    return bytes(b)


DATA = payload(150000)
# generate_vectors.py creates ONE Random(5) and draws 3000 bytes from it. Calling random.Random(5)
# inside the generator expression instead re-seeds on every draw, so every byte comes out the same
# (0x9f) -- which is where the wrong stored-blocks digest 55b17ac2... came from.
_stored_rng = random.Random(5)
RANDOM = bytes(_stored_rng.getrandbits(8) for _ in range(3000))
LIBRARIES = {"id": "reference-libraries", "url": "https://github.com/lz4/lz4",
             "description": "Written by python-lz4 1.9.4 (liblz4 1.9.4), python-zstandard 0.25 (zstd 1.5) and CPython's "
                            "lzma module (liblzma 5) through hexplain-tools codecs/lz/src/test/resources/codec/generate_vectors.py "
                            "and codecs/xz/src/test/resources/codec/generate_xz_vectors.py; single-byte corruptions, "
                            "truncations and concatenations made here.",
             "licence": "BSD-2-Clause (liblz4), BSD-3-Clause (zstd, python-zstandard), 0BSD (liblzma); inputs CC0-1.0"}
NUMCODECS = {"id": "numcodecs", "url": "https://github.com/zarr-developers/numcodecs",
             "description": "Chunks written by numcodecs 0.16.5 (numpy 2.3.2, Python 3.11.4) through hexplain-tools "
                            "tests/gdal/zarr_codec_vectors.py (core/src/test/resources/zarr/numcodecs-vectors.json).",
             "licence": "MIT (numcodecs); data CC0-1.0"}
HAND = {"id": "hand-built", "url": "https://github.com/lz4/lz4/blob/dev/doc/lz4_Frame_format.md",
        "description": "Frames built byte by byte here from the LZ4 Frame Format Description 1.6.4 and RFC 8878 (Zstandard).",
        "licence": "CC0-1.0"}


def le32(v):
    return struct.pack("<I", v & 0xFFFFFFFF)


def flip(data, at):
    b = bytearray(data)
    b[at] ^= 0x01
    return bytes(b)


def hand_lz4(body):
    header = bytearray(b"\x04\x22\x4d\x18\x60\x40\x00")
    header[6] = (xxh32(bytes(header[4:6])) >> 8) & 0xFF
    return bytes(header) + le32(len(body)) + body + le32(0)


def raw_zstd(fhd, header, raw):
    block = (len(raw) << 3) | 1
    return le32(0xFD2FB528) + bytes([fhd]) + header + bytes([block & 0xFF, (block >> 8) & 0xFF, (block >> 16) & 0xFF]) + raw


def ok(data):
    return {"sha256": sha256(data), "size": len(data)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    engine = pathlib.Path(parser.parse_args().engine)
    # LZ4 and Zstandard fixtures live in the codecs/lz plugin module (task 13); XZ's live in the
    # codecs/xz plugin module (task 14).
    lz_codec = engine / "codecs/lz/src/test/resources/codec"
    xz_codec = engine / "codecs/xz/src/test/resources/codec"
    numcodecs = json.loads((engine / "adapters/src/test/resources/zarr/numcodecs-vectors.json").read_text(encoding="utf-8"))["vectors"]
    read = lambda name: (lz_codec / name).read_bytes()  # noqa: E731
    read_xz = lambda name: (xz_codec / name).read_bytes()  # noqa: E731
    if read("lz4-block.lz4") and len(DATA) != 150000:
        raise SystemExit("payload rebuilt wrongly")

    framed, linked, stored = read("lz4-frame-independent-checksums.lz4"), read("lz4-frame-linked.lz4"), read("lz4-frame-stored.lz4")
    first = 4 + 2 + 8 + 1
    block_size = framed[first] | (framed[first + 1] << 8) | (framed[first + 2] << 16)
    skippable = le32(0x184D2A53) + le32(3) + b"\x09\x09\x09"
    dict_header = b"\x04\x22\x4d\x18\x61\x40" + le32(7)
    dictionary = dict_header + bytes([(xxh32(dict_header[4:]) >> 8) & 0xFF]) + le32(0)
    lz4_files = {
        "independent-checksums.lz4": framed, "linked.lz4": linked, "empty.lz4": read("lz4-frame-empty.lz4"),
        "stored.lz4": stored, "content-checksum-flip.lz4": flip(framed, len(framed) - 1),
        "block-checksum-flip.lz4": flip(framed, first + 4 + block_size), "header-checksum-flip.lz4": flip(framed, first - 1),
        "stored-data-flip.lz4": flip(stored, 20), "truncated.lz4": linked[:-3], "trailing.lz4": linked + b"\x00",
        "concatenated.lz4": skippable + linked + skippable + linked,
    }
    write_suite("LZ4", [LIBRARIES, HAND], [
        {"id": "independent-checksums", "steps": [step(b"", ok(DATA), file="independent-checksums.lz4")]},
        {"id": "linked", "steps": [step(b"", ok(DATA), file="linked.lz4")]},
        {"id": "empty", "steps": [step(b"", {"hex": ""}, file="empty.lz4")]},
        {"id": "stored-blocks", "steps": [step(b"", ok(RANDOM), file="stored.lz4")]},
        {"id": "content-checksum-mismatch", "steps": [step(b"", {"error": "Checksum"}, file="content-checksum-flip.lz4")]},
        {"id": "block-checksum-mismatch", "steps": [step(b"", {"error": "Checksum"}, file="block-checksum-flip.lz4")]},
        {"id": "header-checksum-mismatch", "steps": [step(b"", {"error": "Checksum"}, file="header-checksum-flip.lz4")]},
        {"id": "stored-data-mismatch", "steps": [step(b"", {"error": "Checksum"}, file="stored-data-flip.lz4")]},
        {"id": "truncated", "steps": [step(b"", {"error": "Validation"}, file="truncated.lz4")]},
        {"id": "trailing-byte", "steps": [step(b"", {"error": "Validation"}, file="trailing.lz4")]},
        {"id": "skippable-and-concatenated", "steps": [step(b"", ok(DATA + DATA), file="concatenated.lz4")]},
        {"id": "over-bound", "steps": [step(b"", {"error": "ResourceLimit"}, file="linked.lz4", max_output=100000)]},
        {"id": "unknown-parameter", "steps": [step(b"", {"error": "Description"}, {"level": 1}, file="linked.lz4")]},
        {"id": "dictionary", "source": "hand-built", "steps": [step(dictionary, {"error": "Unsupported"})]},
        {"id": "match-before-start", "source": "hand-built",
         "steps": [step(hand_lz4(bytes([0x10, 0x61, 2, 0, 0])), {"error": "Validation"})]},
        {"id": "match-offset-zero", "source": "hand-built",
         "steps": [step(hand_lz4(bytes([0x10, 0x61, 0, 0, 0])), {"error": "Validation"})]},
        {"id": "overlapping-match", "source": "hand-built",
         "steps": [step(hand_lz4(bytes([0x10, 0x61, 1, 0, 0x10, 0x62])), {"hex": b"aaaaab".hex()})]},
    ], files=lz4_files)

    block = read("lz4-block.lz4")
    lz4_chunks = [v for v in numcodecs if v["group"] == "lz4"]
    write_suite("LZ4Block", [LIBRARIES, NUMCODECS], [
        {"id": "block", "steps": [step(b"", ok(DATA), {"decodedSize": 150000}, file="block.lz4")]},
        {"id": "declared-too-small", "steps": [step(b"", {"error": "Validation"}, {"decodedSize": 149999}, file="block.lz4")]},
        {"id": "declared-too-large", "steps": [step(b"", {"error": "Validation"}, {"decodedSize": 150001}, file="block.lz4")]},
        {"id": "missing-size", "steps": [step(b"", {"error": "Description"}, file="block.lz4")]},
        {"id": "zero-size", "steps": [step(b"", {"error": "Description"}, {"decodedSize": 0}, file="block.lz4")]},
        {"id": "over-bound", "steps": [step(b"", {"error": "ResourceLimit"}, {"decodedSize": 150000}, file="block.lz4", max_output=1000)]},
    ] + [
        {"id": "numcodecs-" + v["name"].replace("=", "-"), "source": "numcodecs",
         "steps": [step(bytes.fromhex(v["encoded"])[4:], {"hex": v["decoded"]},
                        {"decodedSize": struct.unpack("<I", bytes.fromhex(v["encoded"])[:4])[0]})]}
        for v in lz4_chunks
    ], files={"block.lz4": block})

    checksummed, streamed, streamed_checksum = read("zstd-checksum-size.zst"), read("zstd-streamed.zst"), read("zstd-streamed-checksum.zst")
    zstd_files = {"checksum-size.zst": checksummed, "streamed.zst": streamed, "streamed-checksum.zst": streamed_checksum,
                  "concatenated.zst": read("zstd-concatenated.zst"), "empty.zst": read("zstd-empty.zst"),
                  "checksum-flip.zst": flip(checksummed, len(checksummed) - 2),
                  "streamed-checksum-flip.zst": flip(streamed_checksum, len(streamed_checksum) - 2),
                  "truncated.zst": streamed[:-1], "trailing-magic.zst": streamed + b"\x28\xb5"}
    write_suite("Zstd", [LIBRARIES, NUMCODECS, HAND], [
        {"id": "checksum-and-size", "steps": [step(b"", ok(DATA), file="checksum-size.zst")]},
        {"id": "streamed", "steps": [step(b"", ok(DATA), file="streamed.zst")]},
        {"id": "streamed-checksum", "steps": [step(b"", ok(DATA), file="streamed-checksum.zst")]},
        {"id": "skippable-and-concatenated", "steps": [step(b"", ok(DATA), file="concatenated.zst")]},
        {"id": "empty", "steps": [step(b"", {"hex": ""}, file="empty.zst")]},
        {"id": "checksum-mismatch", "steps": [step(b"", {"error": "Checksum"}, file="checksum-flip.zst")]},
        {"id": "streamed-checksum-mismatch", "steps": [step(b"", {"error": "Checksum"}, file="streamed-checksum-flip.zst")]},
        {"id": "truncated", "steps": [step(b"", {"error": "Validation"}, file="truncated.zst")]},
        {"id": "trailing-partial-magic", "steps": [step(b"", {"error": "Validation"}, file="trailing-magic.zst")]},
        {"id": "over-bound", "steps": [step(b"", {"error": "ResourceLimit"}, file="checksum-size.zst", max_output=149999)]},
        {"id": "not-a-frame", "source": "hand-built", "steps": [step(bytes([1, 2, 3, 4, 5]), {"error": "Validation"})]},
        {"id": "skippable-past-end", "source": "hand-built",
         "steps": [step(le32(0x184D2A50) + le32(100) + bytes(3), {"error": "Validation"})]},
        {"id": "raw-block", "source": "hand-built", "steps": [step(raw_zstd(0x20, b"\x03", b"abc"), {"hex": b"abc".hex()})]},
        {"id": "reserved-bit", "source": "hand-built", "steps": [step(raw_zstd(0x28, b"\x03", b"abc"), {"error": "Validation"})]},
        {"id": "content-size-mismatch", "source": "hand-built", "steps": [step(raw_zstd(0x20, b"\x04", b"abc"), {"error": "Checksum"})]},
        {"id": "content-size-beyond-blocks", "source": "hand-built",
         "steps": [step(raw_zstd(0xA0, le32(1_000_000), b"abc"), {"error": "ResourceLimit"}, max_output=100)]},
        {"id": "dictionary", "source": "hand-built", "steps": [step(raw_zstd(0x21, b"\x05\x03", b"abc"), {"error": "Unsupported"})]},
        {"id": "dictionary-zero", "source": "hand-built", "steps": [step(raw_zstd(0x21, b"\x00\x03", b"abc"), {"hex": b"abc".hex()})]},
        {"id": "window-too-large", "source": "hand-built", "steps": [step(raw_zstd(0x00, b"\x88", b"abc"), {"error": "Unsupported"})]},
    ] + [
        {"id": "numcodecs-" + v["name"].replace("=", "-"), "source": "numcodecs",
         "steps": [step(bytes.fromhex(v["encoded"]), {"hex": v["decoded"]})]}
        for v in numcodecs if v["group"] == "zstd"
    ], files=zstd_files)

    crc64, concatenated = read_xz("xz-crc64.xz"), read_xz("xz-concatenated.xz")
    single = {"concatenated": 0, "memoryLimitKiB": 102400}
    write_suite("XZ", [LIBRARIES, NUMCODECS], [
        {"id": "crc64", "steps": [step(b"", ok(DATA), file="crc64.xz")]},
        {"id": "sha256", "steps": [step(b"", ok(DATA), file="sha256.xz")]},
        {"id": "concatenated-with-padding", "steps": [step(b"", ok(DATA), file="concatenated.xz")]},
        {"id": "first-stream-only", "steps": [step(b"", ok(DATA[:70000]), {"concatenated": 0}, file="concatenated.xz")]},
        {"id": "truncated", "steps": [step(b"", {"error": "Validation"}, file="truncated.xz")]},
        {"id": "memory-limit", "steps": [step(b"", {"error": "ResourceLimit"}, {"memoryLimitKiB": 1}, file="crc64.xz")]},
        {"id": "over-bound", "steps": [step(b"", {"error": "ResourceLimit"}, file="crc64.xz", max_output=1000)]},
        {"id": "bad-level", "steps": [step(b"", {"error": "Description"}, {"level": 10}, file="crc64.xz")]},
    ] + [
        {"id": "numcodecs-" + v["name"].replace(" ", "-").replace("+", "-"), "source": "numcodecs",
         "steps": [step(bytes.fromhex(v["encoded"]), {"hex": v["decoded"]} if v["group"] == "lzma" else {"error": "Validation"}, single)]}
        for v in numcodecs if v["group"] in ("lzma", "lzma-alone")
    ], files={"crc64.xz": crc64, "sha256.xz": read_xz("xz-sha256.xz"), "concatenated.xz": concatenated,
              "truncated.xz": crc64[:-20]})
    print("PASS: wrote LZ4, LZ4Block, Zstd and XZ suites")


if __name__ == "__main__":
    main()
