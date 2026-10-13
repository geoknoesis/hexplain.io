"""Vectors of the TIFF-family codecs defined by worked examples rather than decoders.

LZW and PackBits: the worked examples of TIFF Revision 6.0 (sections 13 and 9). LZW's example codes
256 7 258 8 8 258 6 6 257 are packed here as 9-bit codes, most significant bit first.
FloatingPointPredictor: rows encoded here from the definition in Adobe TIFF Technical Note 3
(bytes regrouped by significance, then byte differences). BitReverse: by definition.
"""

from __future__ import annotations

import pathlib
import struct
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from vectors import step, write_suite  # noqa: E402

TIFF6 = {
    "id": "tiff-6.0",
    "url": "https://www.itu.int/itudoc/itu-t/com16/tiff-fx/docs/tiff6.pdf",
    "description": "Worked examples of TIFF Revision 6.0 (Adobe, 1992): PackBits (section 9) and LZW (section 13), "
    "encoded as bytes by tools/codecs/_generate_tiff_vectors.py.",
    "licence": "CC0-1.0 (the byte strings)",
}
TN3 = {
    "id": "tiff-tn3",
    "url": "https://chriscox.org/TIFFTN3d1.pdf",
    "description": "Rows encoded by tools/codecs/_generate_tiff_vectors.py from the floating-point predictor of Adobe "
    "Photoshop TIFF Technical Note 3 (April 2005).",
    "licence": "CC0-1.0",
}
DEFINITION = {"id": "definition", "description": "Computed by hand from the codec's definition.", "licence": "CC0-1.0"}


def pack_codes(codes: Any, width: int = 9) -> Any:
    bits, used, out = 0, 0, bytearray()
    for code in codes:
        bits = (bits << width) | code
        used += width
        while used >= 8:
            out.append((bits >> (used - 8)) & 0xFF)
            used -= 8
    if used:
        out.append((bits << (8 - used)) & 0xFF)
    return bytes(out)


def fp_encode(row: Any, element: Any, stride: Any) -> Any:
    """TN3 on one row of little-endian samples: planes, most significant byte first, then byte differences."""
    count = len(row) // element
    planes = bytearray(len(row))
    for sample in range(count):
        for byte in range(element):
            planes[(element - byte - 1) * count + sample] = row[sample * element + byte]
    out = bytearray(planes)
    for i in range(len(out) - 1, stride - 1, -1):
        out[i] = (planes[i] - planes[i - stride]) & 0xFF
    return bytes(out)


def main() -> None:
    lzw = pack_codes([256, 7, 258, 8, 8, 258, 6, 6, 257])
    write_suite(
        "LZW",
        [TIFF6],
        [
            {"id": "tiff6-example", "steps": [step(lzw, {"hex": "070707080807070606"}, {"variant": "tiff"})]},
            {"id": "default-variant", "steps": [step(lzw, {"hex": "070707080807070606"})]},
            {"id": "truncated", "steps": [step(lzw[:-1], {"error": "Validation"})]},
            {"id": "no-clear-code", "steps": [step(pack_codes([7, 257]), {"error": "Validation"})]},
            {"id": "over-bound", "steps": [step(lzw, {"error": "ResourceLimit"}, max_output=4)]},
            {"id": "unknown-variant", "steps": [step(lzw, {"error": "Description"}, {"variant": "gif"})]},
        ],
    )
    packed = bytes.fromhex("feaa0280002afdaa0380002a22f7aa")
    unpacked = bytes.fromhex("aaaaaa80002aaaaaaaaa80002a22aaaaaaaaaaaaaaaaaaaa")
    write_suite(
        "PackBits",
        [TIFF6],
        [
            {"id": "tiff6-example", "steps": [step(packed, {"hex": unpacked.hex()})]},
            {"id": "no-op-control", "steps": [step(bytes([0x80, 0x00, 0x41, 0x80]), {"hex": "41"})]},
            {"id": "truncated-literal", "steps": [step(bytes([0x05, 0x41, 0x42]), {"error": "Validation"})]},
            {"id": "truncated-repeat", "steps": [step(bytes([0xFE]), {"error": "Validation"})]},
            {"id": "over-bound", "steps": [step(packed, {"error": "ResourceLimit"}, max_output=10)]},
        ],
    )
    row32 = b"".join(struct.pack("<f", v) for v in (1.0, 2.5, -3.25, 100.0))
    row32be = b"".join(struct.pack(">f", v) for v in (1.0, 2.5, -3.25, 100.0))
    rows64 = b"".join(struct.pack("<d", v) for v in (0.5, -1.0, 3.0, 7.25))
    write_suite(
        "FloatingPointPredictor",
        [TN3],
        [
            {
                "id": "float32-one-row",
                "steps": [step(fp_encode(row32, 4, 1), {"hex": row32.hex()}, {"elementSize": 4})],
            },
            {
                "id": "float32-big-endian",
                "steps": [step(fp_encode(row32, 4, 1), {"hex": row32be.hex()}, {"elementSize": 4, "littleEndian": 0})],
            },
            {
                "id": "float64-two-rows-two-samples",
                "steps": [
                    step(
                        fp_encode(rows64[:16], 8, 2) + fp_encode(rows64[16:], 8, 2),
                        {"hex": rows64.hex()},
                        {"elementSize": 8, "samplesPerPixel": 2, "rowBytes": 16},
                    )
                ],
            },
            {
                "id": "encode-float32",
                "steps": [step(row32, {"hex": fp_encode(row32, 4, 1).hex()}, {"elementSize": 4}, direction="encode")],
            },
            {
                "id": "partial-row",
                "steps": [step(bytes(12), {"error": "Validation"}, {"elementSize": 4, "rowBytes": 8})],
            },
            {
                "id": "row-not-whole-pixels",
                "steps": [step(bytes(8), {"error": "Description"}, {"elementSize": 4, "rowBytes": 6})],
            },
            {"id": "missing-element-size", "steps": [step(bytes(8), {"error": "Description"})]},
        ],
    )
    write_suite(
        "BitReverse",
        [DEFINITION],
        [
            {"id": "bytes", "steps": [step(bytes([0x01, 0x80, 0xF0, 0x00, 0xFF]), {"hex": "80010f00ff"})]},
            {"id": "empty", "steps": [step(b"", {"hex": ""})]},
            {"id": "encode-is-decode", "steps": [step(bytes([0x03]), {"hex": "c0"}, direction="encode")]},
            {"id": "over-bound", "steps": [step(bytes(8), {"error": "ResourceLimit"}, max_output=4)]},
        ],
    )
    print("PASS: wrote LZW, PackBits, FloatingPointPredictor and BitReverse suites")


if __name__ == "__main__":
    main()
