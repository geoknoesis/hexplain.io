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

from __future__ import annotations

import argparse
import json
import pathlib
import random
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "conformance"))
from lz4frames import xxh32
from vectors import Json, sha256, step, write_suite

TEXT = b"Hexplain reads LZ4 and Zstandard. "


def payload(n: int) -> bytes:
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
LIBRARIES = {
    "id": "reference-libraries",
    "url": "https://github.com/lz4/lz4",
    "description": "Written by python-lz4 1.9.4 (liblz4 1.9.4), python-zstandard 0.25 (zstd 1.5) and CPython's "
    "lzma module (liblzma 5) through hexplain-tools codecs/lz/src/test/resources/codec/generate_vectors.py "
    "and codecs/xz/src/test/resources/codec/generate_xz_vectors.py; single-byte corruptions, "
    "truncations and concatenations made here.",
    "licence": "BSD-2-Clause (liblz4), BSD-3-Clause (zstd, python-zstandard), 0BSD (liblzma); inputs CC0-1.0",
}
NUMCODECS = {
    "id": "numcodecs",
    "url": "https://github.com/zarr-developers/numcodecs",
    "description": "Chunks written by numcodecs 0.16.5 (numpy 2.3.2, Python 3.11.4) through hexplain-tools "
    "tests/gdal/zarr_codec_vectors.py (core/src/test/resources/zarr/numcodecs-vectors.json).",
    "licence": "MIT (numcodecs); data CC0-1.0",
}
HAND = {
    "id": "hand-built",
    "url": "https://github.com/lz4/lz4/blob/dev/doc/lz4_Frame_format.md",
    "description": (
        "Frames built byte by byte here from the LZ4 Frame Format Description 1.6.4 and RFC 8878 (Zstandard)."
    ),
    "licence": "CC0-1.0",
}


def le32(v: int) -> bytes:
    return struct.pack("<I", v & 0xFFFFFFFF)


def flip(data: bytes, at: int) -> bytes:
    b = bytearray(data)
    b[at] ^= 0x01
    return bytes(b)


def hand_lz4(body: bytes) -> bytes:
    header = bytearray(b"\x04\x22\x4d\x18\x60\x40\x00")
    header[6] = (xxh32(bytes(header[4:6])) >> 8) & 0xFF
    return bytes(header) + le32(len(body)) + body + le32(0)


def raw_zstd(fhd: int, header: bytes, raw: bytes) -> bytes:
    block = (len(raw) << 3) | 1
    return (
        le32(0xFD2FB528)
        + bytes([fhd])
        + header
        + bytes([block & 0xFF, (block >> 8) & 0xFF, (block >> 16) & 0xFF])
        + raw
    )


def ok(data: bytes) -> Json:
    return {"sha256": sha256(data), "size": len(data)}


def file_step(expect: Json, params: Json | None = None, file: str = "", max_output: int | None = None) -> Json:
    """A step over [file], a fixture written beside the manifest."""
    return step(b"", expect, params, file=file, max_output=max_output)


def lz4_files(lz: pathlib.Path) -> dict[str, bytes]:
    """The LZ4 frames of the suite: python-lz4's, and corruptions, truncations and concatenations of them."""
    framed, linked, stored = (
        (lz / "lz4-frame-independent-checksums.lz4").read_bytes(),
        (lz / "lz4-frame-linked.lz4").read_bytes(),
        (lz / "lz4-frame-stored.lz4").read_bytes(),
    )
    first = 4 + 2 + 8 + 1
    block_size = framed[first] | (framed[first + 1] << 8) | (framed[first + 2] << 16)
    skippable = le32(0x184D2A53) + le32(3) + b"\x09\x09\x09"
    return {
        "independent-checksums.lz4": framed,
        "linked.lz4": linked,
        "empty.lz4": (lz / "lz4-frame-empty.lz4").read_bytes(),
        "stored.lz4": stored,
        "content-checksum-flip.lz4": flip(framed, len(framed) - 1),
        "block-checksum-flip.lz4": flip(framed, first + 4 + block_size),
        "header-checksum-flip.lz4": flip(framed, first - 1),
        "stored-data-flip.lz4": flip(stored, 20),
        "truncated.lz4": linked[:-3],
        "trailing.lz4": linked + b"\x00",
        "concatenated.lz4": skippable + linked + skippable + linked,
    }


def lz4_file_vectors() -> list[Json]:
    """The LZ4 vectors over the frame files."""
    checksum, validation = {"error": "Checksum"}, {"error": "Validation"}
    return [
        {"id": "independent-checksums", "steps": [file_step(ok(DATA), file="independent-checksums.lz4")]},
        {"id": "linked", "steps": [file_step(ok(DATA), file="linked.lz4")]},
        {"id": "empty", "steps": [file_step({"hex": ""}, file="empty.lz4")]},
        {"id": "stored-blocks", "steps": [file_step(ok(RANDOM), file="stored.lz4")]},
        {"id": "content-checksum-mismatch", "steps": [file_step(checksum, file="content-checksum-flip.lz4")]},
        {"id": "block-checksum-mismatch", "steps": [file_step(checksum, file="block-checksum-flip.lz4")]},
        {"id": "header-checksum-mismatch", "steps": [file_step(checksum, file="header-checksum-flip.lz4")]},
        {"id": "stored-data-mismatch", "steps": [file_step(checksum, file="stored-data-flip.lz4")]},
        {"id": "truncated", "steps": [file_step(validation, file="truncated.lz4")]},
        {"id": "trailing-byte", "steps": [file_step(validation, file="trailing.lz4")]},
        {"id": "skippable-and-concatenated", "steps": [file_step(ok(DATA + DATA), file="concatenated.lz4")]},
        {"id": "over-bound", "steps": [file_step({"error": "ResourceLimit"}, file="linked.lz4", max_output=100000)]},
        {"id": "unknown-parameter", "steps": [file_step({"error": "Description"}, {"level": 1}, file="linked.lz4")]},
    ]


def lz4_hand_vectors() -> list[Json]:
    """The LZ4 frames built here: a dictionary frame, and blocks whose matches reach outside or overlap."""
    dict_header = b"\x04\x22\x4d\x18\x61\x40" + le32(7)
    dictionary = dict_header + bytes([(xxh32(dict_header[4:]) >> 8) & 0xFF]) + le32(0)
    vectors = [
        ("dictionary", dictionary, {"error": "Unsupported"}),
        ("match-before-start", hand_lz4(bytes([0x10, 0x61, 2, 0, 0])), {"error": "Validation"}),
        ("match-offset-zero", hand_lz4(bytes([0x10, 0x61, 0, 0, 0])), {"error": "Validation"}),
        ("overlapping-match", hand_lz4(bytes([0x10, 0x61, 1, 0, 0x10, 0x62])), {"hex": b"aaaaab".hex()}),
    ]
    return [{"id": vid, "source": "hand-built", "steps": [step(data, expect)]} for vid, data, expect in vectors]


def lz4_suite(lz: pathlib.Path) -> None:
    write_suite("LZ4", [LIBRARIES, HAND], lz4_file_vectors() + lz4_hand_vectors(), files=lz4_files(lz))


def lz4_block_suite(lz: pathlib.Path, numcodecs: list[Json]) -> None:
    """LZ4 Block: python-lz4's block under right and wrong declared sizes, and numcodecs' lz4 chunks."""
    size = {"decodedSize": 150000}
    vector_list: list[Json] = [
        {"id": "block", "steps": [file_step(ok(DATA), size, file="block.lz4")]},
        {
            "id": "declared-too-small",
            "steps": [file_step({"error": "Validation"}, {"decodedSize": 149999}, file="block.lz4")],
        },
        {
            "id": "declared-too-large",
            "steps": [file_step({"error": "Validation"}, {"decodedSize": 150001}, file="block.lz4")],
        },
        {"id": "missing-size", "steps": [file_step({"error": "Description"}, file="block.lz4")]},
        {"id": "zero-size", "steps": [file_step({"error": "Description"}, {"decodedSize": 0}, file="block.lz4")]},
        {
            "id": "over-bound",
            "steps": [file_step({"error": "ResourceLimit"}, size, file="block.lz4", max_output=1000)],
        },
    ]
    for v in (v for v in numcodecs if v["group"] == "lz4"):
        encoded = bytes.fromhex(v["encoded"])
        params = {"decodedSize": struct.unpack("<I", encoded[:4])[0]}
        vector_list.append(
            {
                "id": "numcodecs-" + v["name"].replace("=", "-"),
                "source": "numcodecs",
                "steps": [step(encoded[4:], {"hex": v["decoded"]}, params)],
            }
        )
    write_suite(
        "LZ4Block", [LIBRARIES, NUMCODECS], vector_list, files={"block.lz4": (lz / "lz4-block.lz4").read_bytes()}
    )


def zstd_files(lz: pathlib.Path) -> dict[str, bytes]:
    """The Zstandard frames of the suite: python-zstandard's, and corruptions and truncations of them."""
    checksummed, streamed, streamed_checksum = (
        (lz / "zstd-checksum-size.zst").read_bytes(),
        (lz / "zstd-streamed.zst").read_bytes(),
        (lz / "zstd-streamed-checksum.zst").read_bytes(),
    )
    return {
        "checksum-size.zst": checksummed,
        "streamed.zst": streamed,
        "streamed-checksum.zst": streamed_checksum,
        "concatenated.zst": (lz / "zstd-concatenated.zst").read_bytes(),
        "empty.zst": (lz / "zstd-empty.zst").read_bytes(),
        "checksum-flip.zst": flip(checksummed, len(checksummed) - 2),
        "streamed-checksum-flip.zst": flip(streamed_checksum, len(streamed_checksum) - 2),
        "truncated.zst": streamed[:-1],
        "trailing-magic.zst": streamed + b"\x28\xb5",
    }


def zstd_file_vectors() -> list[Json]:
    """The Zstandard vectors over the frame files."""
    return [
        {"id": "checksum-and-size", "steps": [file_step(ok(DATA), file="checksum-size.zst")]},
        {"id": "streamed", "steps": [file_step(ok(DATA), file="streamed.zst")]},
        {"id": "streamed-checksum", "steps": [file_step(ok(DATA), file="streamed-checksum.zst")]},
        {"id": "skippable-and-concatenated", "steps": [file_step(ok(DATA), file="concatenated.zst")]},
        {"id": "empty", "steps": [file_step({"hex": ""}, file="empty.zst")]},
        {"id": "checksum-mismatch", "steps": [file_step({"error": "Checksum"}, file="checksum-flip.zst")]},
        {
            "id": "streamed-checksum-mismatch",
            "steps": [file_step({"error": "Checksum"}, file="streamed-checksum-flip.zst")],
        },
        {"id": "truncated", "steps": [file_step({"error": "Validation"}, file="truncated.zst")]},
        {"id": "trailing-partial-magic", "steps": [file_step({"error": "Validation"}, file="trailing-magic.zst")]},
        {
            "id": "over-bound",
            "steps": [file_step({"error": "ResourceLimit"}, file="checksum-size.zst", max_output=149999)],
        },
    ]


def zstd_hand_vectors() -> list[Json]:
    """The Zstandard frames built here, field by field from RFC 8878."""
    abc = {"hex": b"abc".hex()}
    vectors: list[tuple[str, bytes, Json, int | None]] = [
        ("not-a-frame", bytes([1, 2, 3, 4, 5]), {"error": "Validation"}, None),
        ("skippable-past-end", le32(0x184D2A50) + le32(100) + bytes(3), {"error": "Validation"}, None),
        ("raw-block", raw_zstd(0x20, b"\x03", b"abc"), abc, None),
        ("reserved-bit", raw_zstd(0x28, b"\x03", b"abc"), {"error": "Validation"}, None),
        ("content-size-mismatch", raw_zstd(0x20, b"\x04", b"abc"), {"error": "Checksum"}, None),
        ("content-size-beyond-blocks", raw_zstd(0xA0, le32(1_000_000), b"abc"), {"error": "ResourceLimit"}, 100),
        ("dictionary", raw_zstd(0x21, b"\x05\x03", b"abc"), {"error": "Unsupported"}, None),
        ("dictionary-zero", raw_zstd(0x21, b"\x00\x03", b"abc"), abc, None),
        ("window-too-large", raw_zstd(0x00, b"\x88", b"abc"), {"error": "Unsupported"}, None),
    ]
    return [
        {"id": vid, "source": "hand-built", "steps": [step(data, expect, max_output=limit)]}
        for vid, data, expect, limit in vectors
    ]


def zstd_suite(lz: pathlib.Path, numcodecs: list[Json]) -> None:
    chunks = [
        {
            "id": "numcodecs-" + v["name"].replace("=", "-"),
            "source": "numcodecs",
            "steps": [step(bytes.fromhex(v["encoded"]), {"hex": v["decoded"]})],
        }
        for v in numcodecs
        if v["group"] == "zstd"
    ]
    vector_list = zstd_file_vectors() + zstd_hand_vectors() + chunks
    write_suite("Zstd", [LIBRARIES, NUMCODECS, HAND], vector_list, files=zstd_files(lz))


def xz_suite(xz: pathlib.Path, numcodecs: list[Json]) -> None:
    """XZ: CPython lzma's streams, and numcodecs' lzma chunks (an LZMA-alone chunk is not an XZ stream)."""
    crc64, concatenated = (xz / "xz-crc64.xz").read_bytes(), (xz / "xz-concatenated.xz").read_bytes()
    single = {"concatenated": 0, "memoryLimitKiB": 102400}
    vector_list: list[Json] = [
        {"id": "crc64", "steps": [file_step(ok(DATA), file="crc64.xz")]},
        {"id": "sha256", "steps": [file_step(ok(DATA), file="sha256.xz")]},
        {"id": "concatenated-with-padding", "steps": [file_step(ok(DATA), file="concatenated.xz")]},
        {
            "id": "first-stream-only",
            "steps": [file_step(ok(DATA[:70000]), {"concatenated": 0}, file="concatenated.xz")],
        },
        {"id": "truncated", "steps": [file_step({"error": "Validation"}, file="truncated.xz")]},
        {
            "id": "memory-limit",
            "steps": [file_step({"error": "ResourceLimit"}, {"memoryLimitKiB": 1}, file="crc64.xz")],
        },
        {"id": "over-bound", "steps": [file_step({"error": "ResourceLimit"}, file="crc64.xz", max_output=1000)]},
        {"id": "bad-level", "steps": [file_step({"error": "Description"}, {"level": 10}, file="crc64.xz")]},
    ]
    for v in (v for v in numcodecs if v["group"] in ("lzma", "lzma-alone")):
        expect = {"hex": v["decoded"]} if v["group"] == "lzma" else {"error": "Validation"}
        vector_list.append(
            {
                "id": "numcodecs-" + v["name"].replace(" ", "-").replace("+", "-"),
                "source": "numcodecs",
                "steps": [step(bytes.fromhex(v["encoded"]), expect, single)],
            }
        )
    files = {
        "crc64.xz": crc64,
        "sha256.xz": (xz / "xz-sha256.xz").read_bytes(),
        "concatenated.xz": concatenated,
        "truncated.xz": crc64[:-20],
    }
    write_suite("XZ", [LIBRARIES, NUMCODECS], vector_list, files=files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    engine = pathlib.Path(parser.parse_args().engine)
    # LZ4 and Zstandard fixtures live in the codecs/lz plugin module (task 13); XZ's live in the
    # codecs/xz plugin module (task 14).
    lz_codec = engine / "codecs/lz/src/test/resources/codec"
    xz_codec = engine / "codecs/xz/src/test/resources/codec"
    numcodecs = json.loads(
        (engine / "adapters/src/test/resources/zarr/numcodecs-vectors.json").read_text(encoding="utf-8")
    )["vectors"]
    if (lz_codec / "lz4-block.lz4").read_bytes() and len(DATA) != 150000:
        raise SystemExit("payload rebuilt wrongly")
    lz4_suite(lz_codec)
    lz4_block_suite(lz_codec, numcodecs)
    zstd_suite(lz_codec, numcodecs)
    xz_suite(xz_codec, numcodecs)
    print("PASS: wrote LZ4, LZ4Block, Zstd and XZ suites")


if __name__ == "__main__":
    main()
