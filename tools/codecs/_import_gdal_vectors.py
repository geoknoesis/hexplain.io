"""Import codec vectors from the GDAL 3.13.3 decodes the reference engine's TIFF parity tests use.

Each row of hexplain-tools core/src/test/resources/gdal-codec-vectors.tsv is a TIFF (or BMP) with
the SHA-256 of the pixels GDAL 3.13.3 decodes from it. A row becomes a codec vector when the
codec's output IS those pixels: a stripped image whose strips, decoded in order sharing one
session, give every image row; expectAll unpacks sub-byte samples and compares with GDAL's hash.
gdal-codec-refusals.tsv rows are files GDAL refuses: the strips before the block GDAL names must
decode and that block must be a Validation error.

T.6 files named "corrupt" are skipped: libtiff's recovery from an early EOFB leaves the rest of
the strip buffer as the previous strip left it, which is the TIFF reader's buffer, not the
codec's output. NeXT and ThunderScan files with FillOrder 2 are skipped: the TIFF reader, not the
codec, reverses their bits.

Usage: python tools/codecs/_import_gdal_vectors.py --engine d:/work/hexplain-tools tiff
"""

from __future__ import annotations

import argparse
import base64
import pathlib
import re
import struct
import sys
from collections.abc import Iterator
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _tiff  # noqa: E402
from vectors import sha256, step, write_suite  # noqa: E402

GDAL = {
    "id": "gdal-3.13.3",
    "url": "https://github.com/OSGeo/gdal/tree/v3.13.3",
    "description": "Pixels decoded by GDAL 3.13.3 (container "
    "ghcr.io/osgeo/gdal@sha256:2dd0f81ef927ff4c3d4dbe4f73c029dc86d4073974c0564f8e196f6e1412e2e0) "
    "from GDAL autotest files at commit c8b4c45fca87d3e6fbf80e7a7898b8a661ad0edc and from synthetic files written by "
    "hexplain-tools tests/gdal/codec_vectors.py; imported by tools/codecs/_import_gdal_vectors.py from "
    "core/src/test/resources/gdal-codec-vectors.tsv, gdal-codec-refusals.tsv and gdal-color-*.tsv.",
    "licence": "GDAL autotest data: MIT/X (GDAL LICENSE.TXT and per-file notices); synthetic files CC0-1.0",
}
TIFF_CODECS = {
    2: "CCITTModifiedHuffman",
    32771: "CCITTModifiedHuffman",
    3: "CCITTGroup3",
    4: "CCITTGroup4",
    32766: "NeXT",
    32809: "ThunderScan",
}
BITS = {2: 1, 32771: 1, 3: 1, 4: 1, 32766: 2, 32809: 4}


def rows(path: Any) -> Iterator[Any]:
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            yield line.split("\t")


def vector_id(name: str, suffix: str = "") -> Any:
    return re.sub(r"[^A-Za-z0-9]+", "-", name.rsplit("/", 1)[-1]).strip("-") + suffix


def tiff_params(compression: Any, tags: Any, width: Any, count: Any) -> dict[str, Any]:
    fill = _tiff.scalar(tags, 266, 1)
    if compression in (2, 32771):
        return {"columns": width, "rows": count, "fillOrder": fill, "rowAlignment": 8 if compression == 2 else 16}
    if compression == 3:
        return {"columns": width, "rows": count, "options": _tiff.scalar(tags, 292, 0), "fillOrder": fill}
    if compression == 4:
        return {"columns": width, "rows": count, "options": _tiff.scalar(tags, 293, 0), "fillOrder": fill}
    return {"columns": width, "rowBytes": (width * BITS[compression] + 7) // 8, "rows": count}


def tiff_family_file(name: str, data: Any) -> Any:
    """(tags, compression) for a stripped single-sample TIFF of a TIFF-family codec, else None."""
    if data[:2] not in (b"II", b"MM"):
        return None
    try:
        tags, _ = _tiff.first_ifd(data)
    except (ValueError, KeyError, struct.error):
        return None
    compression = _tiff.scalar(tags, 259, 1)
    if compression not in TIFF_CODECS or 324 in tags or _tiff.scalar(tags, 277, 1) != 1:
        return None
    if compression == 4 and "corrupt" in name:
        return None
    if compression in (32766, 32809) and _tiff.scalar(tags, 266, 1) != 1:
        return None
    return tags, compression


def strip_steps(data: Any, tags: Any, compression: Any, fail_at: Any = None) -> Any:
    width, height = tags[256][0], tags[257][0]
    per = _tiff.scalar(tags, 278, height)
    steps = []
    for i, strip in enumerate(_tiff.strips(data, tags)):
        count = min(per, height - i * per)
        if count <= 0:
            break
        failing = fail_at is not None and i == fail_at
        steps.append(
            step(
                strip,
                {"error": "Validation"} if failing else {"ok": True},
                tiff_params(compression, tags, width, count),
            )
        )
        if failing:
            break
    return steps


def tiff_family(engine: Any) -> None:
    resources = engine / "core/src/test/resources"
    suites = {name: [] for name in sorted(set(TIFF_CODECS.values()))}
    for row in rows(resources / "gdal-codec-vectors.tsv"):
        name, pixels, data = row[0], row[6], base64.b64decode(row[7])
        found = tiff_family_file(name, data)
        if not found:
            continue
        tags, compression = found
        suites[TIFF_CODECS[compression]].append(
            {
                "id": vector_id(name),
                "session": True,
                "steps": strip_steps(data, tags, compression),
                "expectAll": {"sha256": pixels, "unpack": {"bitsPerSample": BITS[compression], "width": tags[256][0]}},
            }
        )
    for row in rows(resources / "gdal-codec-refusals.tsv"):
        name, message, data = row[0], row[1], base64.b64decode(row[2])
        found = tiff_family_file(name, data)
        block = re.search(r"Y offset (\d+)", message)
        if not found or not block:
            continue
        tags, compression = found
        suites[TIFF_CODECS[compression]].append(
            {
                "id": vector_id(name, "-refused"),
                "session": True,
                "steps": strip_steps(data, tags, compression, fail_at=int(block.group(1))),
            }
        )
    for codec, vector_list in suites.items():
        if not vector_list:
            raise SystemExit(f"FAIL: no GDAL vector for {codec}")
        write_suite(codec, [GDAL], vector_list)
    print("PASS: " + ", ".join(f"{codec} {len(v)}" for codec, v in suites.items()))


DEFINITION = {"id": "definition", "description": "Computed by hand from the codec's definition.", "licence": "CC0-1.0"}
SAMPLE_TYPES = {8: "uint8", 16: "uint16"}


def tiff_lzw(data: Any) -> Any:
    """TIFF 6.0 LZW, to recover the sampling units a YCbCr strip stores; None when the strip ends early."""
    table, out, bit, width, prev = [bytes([i]) for i in range(256)] + [b"", b""], bytearray(), 0, 9, None
    while True:
        if bit + width > len(data) * 8:
            return None
        code = 0
        for k in range(width):
            b = bit + k
            code = (code << 1) | ((data[b >> 3] >> (7 - (b & 7))) & 1)
        bit += width
        if code == 257:
            return bytes(out)
        if code == 256:
            table, width, prev = table[:258], 9, None
            continue
        if code < len(table):
            entry = table[code]
        elif code == len(table) and prev is not None:
            entry = prev + prev[:1]
        else:
            return None
        out += entry
        if prev is not None and len(table) < 4096:
            table.append(prev + entry[:1])
            if width < 12 and len(table) == (1 << width) - 1:
                width += 1
        prev = entry


def jpeg_frame(data: Any) -> Any:
    """(width, height) of the first SOF0/1/2 frame header in a JPEG stream, or None."""
    at = 2
    while at + 4 <= len(data):
        if data[at] != 0xFF:
            return None
        marker, length = data[at + 1], (data[at + 2] << 8) | data[at + 3]
        if marker in (0xC0, 0xC1, 0xC2):
            return (data[at + 7] << 8) | data[at + 8], (data[at + 5] << 8) | data[at + 6]
        at += 2 + length
    return None


def stripped(tags: Any) -> Any:
    return 324 not in tags and _tiff.scalar(tags, 284, 1) == 1


def strip_rows(tags: Any) -> list[Any]:
    height = tags[257][0]
    per = _tiff.scalar(tags, 278, height)
    return [min(per, height - i * per) for i in range((height + per - 1) // per)]


def samples_input(data: Any, width: Any, rows: Any, bands: Any) -> dict[str, Any]:
    return {"samples": {"width": width, "height": rows, "bands": bands, "sampleType": "uint8", "hex": data.hex()}}


def unique_id(suite_list: Any, base: Any) -> Any:
    """[base], or [base]-2, -3, ... when [suite_list] already has a vector with that id (two source
    TSVs can each hold a file with the same basename but different bytes)."""
    ids = {v["id"] for v in suite_list}
    if base not in ids:
        return base
    n = 2
    while f"{base}-{n}" in ids:
        n += 1
    return f"{base}-{n}"


def image_family(engine: Any) -> None:
    resources = engine / "core/src/test/resources"
    suites = {
        name: []
        for name in ("JPEG", "WebP", "JPEGXL", "YCbCrToRGB", "CIELabToRGB", "CMYKToRGB", "SGILogRLE", "MicrosoftRLE")
    }
    tiffs = []  # (name, pixels, data)
    for row in rows(resources / "gdal-color-codec-vectors.tsv"):
        kind, name, bands, pixels, data = row[0], row[1], int(row[4]), row[6], base64.b64decode(row[7])
        if kind == "jpeg":
            suites["JPEG"].append(
                {
                    "id": vector_id(name),
                    "steps": [
                        step(
                            data,
                            {
                                "samples": {
                                    "width": int(row[2]),
                                    "height": int(row[3]),
                                    "bands": bands,
                                    "sampleType": "uint8",
                                    "sha256": pixels,
                                    "order": "band",
                                }
                            },
                            {"colorTransform": "ycbcr-to-rgb"} if bands == 3 else {},
                        )
                    ],
                }
            )
        elif kind == "refused" and name.startswith("jxl"):
            tags, _ = _tiff.first_ifd(data)
            suites["JPEGXL"].append(
                {
                    "id": vector_id(name, "-refused"),
                    "steps": [step(_tiff.strips(data, tags)[0], {"error": "Unsupported"})],
                }
            )
        else:
            tiffs.append((name, pixels, data))
    for row in rows(resources / "gdal-color-lossy-vectors.tsv"):
        tiffs.append((row[0], row[6], base64.b64decode(row[7])))
    for name, pixels, data in tiffs:
        tags, _ = _tiff.first_ifd(data)
        if not stripped(tags):
            continue
        compression, photometric = _tiff.scalar(tags, 259, 1), _tiff.scalar(tags, 262, 1)
        width, spp, bps = tags[256][0], _tiff.scalar(tags, 277, 1), _tiff.scalar(tags, 258, 8)
        strips, counts = _tiff.strips(data, tags), strip_rows(tags)
        item = 2 if bps == 16 or bps == 12 else 1
        whole = {
            "sha256": pixels,
            "deinterleave": {"bands": spp if photometric not in (5, 8) else 4, "sampleBytes": item},
        }
        if compression == 7 and not (bps == 12 and (width * spp) % 2):
            params = {"precision": bps, "colorTransform": "ycbcr-to-rgb" if photometric == 6 else "none"}
            if 347 in tags:
                params["tables"] = {"hex": bytes(tags[347]).hex()}
            if any(
                jpeg_frame(s) is None or jpeg_frame(s)[0] != width or jpeg_frame(s)[1] < n
                for s, n in zip(strips, counts, strict=True)
            ):
                continue
            suites["JPEG"].append(
                {
                    "id": unique_id(suites["JPEG"], vector_id(name)),
                    "session": True,
                    "expectAll": whole,
                    "steps": [step(s, {"ok": True}, dict(params, rows=n)) for s, n in zip(strips, counts, strict=True)],
                }
            )
        elif compression == 50001:
            suites["WebP"].append(
                {
                    "id": unique_id(suites["WebP"], vector_id(name)),
                    "expectAll": whole,
                    "steps": [step(s, {"ok": True}, {"bands": spp}) for s in strips],
                }
            )
        elif compression in (50002, 52546):
            suites["JPEGXL"].append(
                {
                    "id": unique_id(suites["JPEGXL"], vector_id(name)),
                    "expectAll": whole,
                    "steps": [step(s, {"ok": True}) for s in strips],
                }
            )
        elif compression == 34676:
            suites["SGILogRLE"].append(
                {
                    "id": unique_id(suites["SGILogRLE"], vector_id(name)),
                    "expectAll": {"sha256": pixels},
                    "steps": [
                        step(s, {"ok": True}, {"columns": width, "rows": n})
                        for s, n in zip(strips, counts, strict=True)
                    ],
                }
            )
        elif compression in (1, 5) and photometric == 6 and bps == 8:
            units = [s if compression == 1 else tiff_lzw(s) for s in strips]
            if any(u is None for u in units):
                continue
            hs, vs = (tags.get(530) or [2, 2])[:2]
            params = {"layout": "units", "subsampling": [hs, vs]}
            if 529 in tags and len(tags[529]) == 3:
                params["coefficients"] = tags[529]
            if 532 in tags and len(tags[532]) == 6:
                params["referenceBlackWhite"] = tags[532]
            suites["YCbCrToRGB"].append(
                {
                    "id": unique_id(suites["YCbCrToRGB"], vector_id(name)),
                    "expectAll": whole,
                    "steps": [
                        dict(step(b"", {"ok": True}, params), input=samples_input(u, width, n, 3))
                        for u, n in zip(units, counts, strict=True)
                    ],
                }
            )
        elif compression == 1 and photometric in (5, 8) and bps == 8:
            codec, params = ("CMYKToRGB", {"alpha": True}) if photometric == 5 else ("CIELabToRGB", {"alpha": True})
            if photometric == 8 and 318 in tags:
                params["whitePoint"] = tags[318]
            suites[codec].append(
                {
                    "id": unique_id(suites[codec], vector_id(name)),
                    "expectAll": whole,
                    "steps": [
                        dict(step(b"", {"ok": True}, params), input=samples_input(s, width, n, spp))
                        for s, n in zip(strips, counts, strict=True)
                    ],
                }
            )
    gray = bytes(v for y in (0, 64, 128, 255) for v in (y, 128, 128))
    suites["YCbCrToRGB"].append(
        {
            "id": "neutral-chroma-is-grey",
            "source": "definition",
            "steps": [
                dict(
                    step(
                        b"",
                        {
                            "samples": {
                                "width": 4,
                                "height": 1,
                                "bands": 3,
                                "sampleType": "uint8",
                                "sha256": sha256(bytes(v for y in (0, 64, 128, 255) for v in (y, y, y))),
                                "order": "pixel",
                            }
                        },
                    ),
                    input=samples_input(gray, 4, 1, 3),
                )
            ],
        }
    )
    for row in rows(resources / "gdal-codec-vectors.tsv"):
        name, pixels, data = row[0], row[6], base64.b64decode(row[7])
        if data[:2] != b"BM":
            continue
        offset, width, height = (
            struct.unpack("<I", data[10:14])[0],
            struct.unpack("<i", data[18:22])[0],
            abs(struct.unpack("<i", data[22:26])[0]),
        )
        bits, compression = struct.unpack("<H", data[28:30])[0], struct.unpack("<I", data[30:34])[0]
        if (compression, bits) in ((1, 8), (2, 4)):
            suites["MicrosoftRLE"].append(
                {
                    "id": vector_id(name),
                    "steps": [
                        step(
                            data[offset:],
                            {"sha256": pixels, "size": width * height},
                            {"bitsPerPixel": bits, "width": width, "height": height},
                        )
                    ],
                }
            )
    for row in rows(resources / "gdal-codec-refusals.tsv"):
        name, data = row[0], base64.b64decode(row[2])
        if data[:2] == b"BM":
            offset, width, height = (
                struct.unpack("<I", data[10:14])[0],
                struct.unpack("<i", data[18:22])[0],
                abs(struct.unpack("<i", data[22:26])[0]),
            )
            bits = struct.unpack("<H", data[28:30])[0]
            suites["MicrosoftRLE"].append(
                {
                    "id": vector_id(name, "-refused"),
                    "steps": [
                        step(
                            data[offset:],
                            {"error": "Validation"},
                            {"bitsPerPixel": bits, "width": width, "height": height},
                        )
                    ],
                }
            )
    for codec, vector_list in suites.items():
        if not vector_list:
            raise SystemExit(f"FAIL: no GDAL vector for {codec}")
        sources = [GDAL, DEFINITION] if any(v.get("source") == "definition" for v in vector_list) else [GDAL]
        write_suite(codec, sources, vector_list)
    print("PASS: " + ", ".join(f"{codec} {len(v)}" for codec, v in suites.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("family", choices=["tiff", "image"])
    args = parser.parse_args()
    {"tiff": tiff_family, "image": image_family}[args.family](pathlib.Path(args.engine))


if __name__ == "__main__":
    main()
