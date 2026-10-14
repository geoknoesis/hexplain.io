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
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _tiff  # noqa: E402
from _tiff import Tags  # noqa: E402
from vectors import Json, sha256, step, write_suite  # noqa: E402

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


def rows(path: pathlib.Path) -> Iterator[list[str]]:
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            yield line.split("\t")


def vector_id(name: str, suffix: str = "") -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name.rsplit("/", 1)[-1]).strip("-") + suffix


def tiff_params(compression: int, tags: Tags, width: int, count: int) -> Json:
    fill = _tiff.scalar(tags, 266, 1)
    if compression in (2, 32771):
        return {"columns": width, "rows": count, "fillOrder": fill, "rowAlignment": 8 if compression == 2 else 16}
    if compression == 3:
        return {"columns": width, "rows": count, "options": _tiff.scalar(tags, 292, 0), "fillOrder": fill}
    if compression == 4:
        return {"columns": width, "rows": count, "options": _tiff.scalar(tags, 293, 0), "fillOrder": fill}
    return {"columns": width, "rowBytes": (width * BITS[compression] + 7) // 8, "rows": count}


def tiff_family_file(name: str, data: bytes) -> tuple[Tags, int] | None:
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


def strip_steps(data: bytes, tags: Tags, compression: int, fail_at: int | None = None) -> list[Json]:
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


def tiff_family(engine: pathlib.Path) -> None:
    resources = engine / "core/src/test/resources"
    suites: dict[str, list[Json]] = {name: [] for name in sorted(set(TIFF_CODECS.values()))}
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


def tiff_lzw(data: bytes) -> bytes | None:
    """TIFF 6.0 LZW, to recover the sampling units a YCbCr strip stores; None when the strip ends early."""
    table, out, bit, width = [bytes([i]) for i in range(256)] + [b"", b""], bytearray(), 0, 9
    prev: bytes | None = None
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


def jpeg_frame(data: bytes) -> tuple[int, int] | None:
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


def stripped(tags: Tags) -> bool:
    return 324 not in tags and _tiff.scalar(tags, 284, 1) == 1


def strip_rows(tags: Tags) -> list[int]:
    height = tags[257][0]
    per = _tiff.scalar(tags, 278, height)
    return [min(per, height - i * per) for i in range((height + per - 1) // per)]


def samples_input(data: bytes, width: int, rows: int, bands: int) -> Json:
    return {"samples": {"width": width, "height": rows, "bands": bands, "sampleType": "uint8", "hex": data.hex()}}


def unique_id(suite_list: list[Json], base: str) -> str:
    """[base], or [base]-2, -3, ... when [suite_list] already has a vector with that id (two source
    TSVs can each hold a file with the same basename but different bytes)."""
    ids = {v["id"] for v in suite_list}
    if base not in ids:
        return base
    n = 2
    while f"{base}-{n}" in ids:
        n += 1
    return f"{base}-{n}"


IMAGE_CODECS = ("JPEG", "WebP", "JPEGXL", "YCbCrToRGB", "CIELabToRGB", "CMYKToRGB", "SGILogRLE", "MicrosoftRLE")


@dataclass
class ColorTiff:
    """A stripped TIFF of a colour codec: its tags and strips, and the expectation over all of them."""

    tags: Tags
    compression: int
    photometric: int
    width: int
    spp: int
    bps: int
    strips: list[bytes]
    counts: list[int]
    whole: Json


def color_tiff(pixels: str, data: bytes) -> ColorTiff | None:
    """The stripped TIFF [data] whose decoded pixels hash to [pixels], or None when it is tiled."""
    tags, _ = _tiff.first_ifd(data)
    if not stripped(tags):
        return None
    compression, photometric = _tiff.scalar(tags, 259, 1), _tiff.scalar(tags, 262, 1)
    width, spp, bps = tags[256][0], _tiff.scalar(tags, 277, 1), _tiff.scalar(tags, 258, 8)
    item = 2 if bps == 16 or bps == 12 else 1
    whole = {
        "sha256": pixels,
        "deinterleave": {"bands": spp if photometric not in (5, 8) else 4, "sampleBytes": item},
    }
    strips, counts = _tiff.strips(data, tags), strip_rows(tags)
    return ColorTiff(tags, compression, photometric, width, spp, bps, strips, counts, whole)


def jpeg_tiff_vector(image: ColorTiff) -> Json | None:
    """A JPEG-in-TIFF's strips, one session, or None when a strip's frame does not cover its rows."""
    params: Json = {
        "precision": image.bps,
        "colorTransform": "ycbcr-to-rgb" if image.photometric == 6 else "none",
    }
    if 347 in image.tags:
        params["tables"] = {"hex": bytes(image.tags[347]).hex()}
    for s, n in zip(image.strips, image.counts, strict=True):
        frame = jpeg_frame(s)
        if frame is None or frame[0] != image.width or frame[1] < n:
            return None
    steps = [step(s, {"ok": True}, dict(params, rows=n)) for s, n in zip(image.strips, image.counts, strict=True)]
    return {"session": True, "expectAll": image.whole, "steps": steps}


def ycbcr_tiff_vector(image: ColorTiff) -> Json | None:
    """An uncompressed or LZW YCbCr TIFF's sampling units, or None when a strip ends early."""
    units = [s if image.compression == 1 else tiff_lzw(s) for s in image.strips]
    if any(u is None for u in units):
        return None
    tags = image.tags
    hs, vs = (tags.get(530) or [2, 2])[:2]
    params: Json = {"layout": "units", "subsampling": [hs, vs]}
    if 529 in tags and len(tags[529]) == 3:
        params["coefficients"] = tags[529]
    if 532 in tags and len(tags[532]) == 6:
        params["referenceBlackWhite"] = tags[532]
    steps = [
        dict(step(b"", {"ok": True}, params), input=samples_input(u, image.width, n, 3))
        for u, n in zip(units, image.counts, strict=True)
        if u is not None
    ]
    return {"expectAll": image.whole, "steps": steps}


def separated_tiff_vector(image: ColorTiff) -> tuple[str, Json]:
    """An uncompressed CMYK or CIE L*a*b* TIFF's samples, with the codec that converts them."""
    codec, params = ("CMYKToRGB", {"alpha": True}) if image.photometric == 5 else ("CIELabToRGB", {"alpha": True})
    if image.photometric == 8 and 318 in image.tags:
        params["whitePoint"] = image.tags[318]
    steps = [
        dict(step(b"", {"ok": True}, params), input=samples_input(s, image.width, n, image.spp))
        for s, n in zip(image.strips, image.counts, strict=True)
    ]
    return codec, {"expectAll": image.whole, "steps": steps}


def color_tiff_vector(image: ColorTiff) -> tuple[str, Json | None] | None:
    """The codec a colour TIFF exercises and its vector (no id yet; None when the file does not make one), or None
    when no codec of this family reads it."""
    compression, photometric, bps = image.compression, image.photometric, image.bps
    if compression == 7 and not (bps == 12 and (image.width * image.spp) % 2):
        return "JPEG", jpeg_tiff_vector(image)
    if compression == 50001:
        return "WebP", {
            "expectAll": image.whole,
            "steps": [step(s, {"ok": True}, {"bands": image.spp}) for s in image.strips],
        }
    if compression in (50002, 52546):
        return "JPEGXL", {"expectAll": image.whole, "steps": [step(s, {"ok": True}) for s in image.strips]}
    if compression == 34676:
        steps = [
            step(s, {"ok": True}, {"columns": image.width, "rows": n})
            for s, n in zip(image.strips, image.counts, strict=True)
        ]
        return "SGILogRLE", {"expectAll": {"sha256": image.whole["sha256"]}, "steps": steps}
    if compression in (1, 5) and photometric == 6 and bps == 8:
        return "YCbCrToRGB", ycbcr_tiff_vector(image)
    if compression == 1 and photometric in (5, 8) and bps == 8:
        return separated_tiff_vector(image)
    return None


def color_rows(resources: pathlib.Path, suites: dict[str, list[Json]]) -> list[tuple[str, str, bytes]]:
    """The JPEG files and JPEG XL refusals of the colour TSV, added to [suites]; its other files and the lossy TSV's,
    as (name, pixels, data), for the TIFF pass."""
    tiffs = []
    for row in rows(resources / "gdal-color-codec-vectors.tsv"):
        kind, name, bands, pixels, data = row[0], row[1], int(row[4]), row[6], base64.b64decode(row[7])
        if kind == "jpeg":
            samples = {
                "width": int(row[2]),
                "height": int(row[3]),
                "bands": bands,
                "sampleType": "uint8",
                "sha256": pixels,
                "order": "band",
            }
            params = {"colorTransform": "ycbcr-to-rgb"} if bands == 3 else {}
            suites["JPEG"].append({"id": vector_id(name), "steps": [step(data, {"samples": samples}, params)]})
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
    return tiffs


def neutral_chroma_vector() -> Json:
    """YCbCr with neutral chroma is grey: a vector worked from the definition."""
    gray = bytes(v for y in (0, 64, 128, 255) for v in (y, 128, 128))
    samples = {
        "width": 4,
        "height": 1,
        "bands": 3,
        "sampleType": "uint8",
        "sha256": sha256(bytes(v for y in (0, 64, 128, 255) for v in (y, y, y))),
        "order": "pixel",
    }
    return {
        "id": "neutral-chroma-is-grey",
        "source": "definition",
        "steps": [dict(step(b"", {"samples": samples}), input=samples_input(gray, 4, 1, 3))],
    }


def bmp_geometry(data: bytes) -> tuple[int, int, int, int]:
    """(pixel data offset, width, height, bits per pixel) of a BMP file."""
    offset, width, height = (
        struct.unpack("<I", data[10:14])[0],
        struct.unpack("<i", data[18:22])[0],
        abs(struct.unpack("<i", data[22:26])[0]),
    )
    return offset, width, height, struct.unpack("<H", data[28:30])[0]


def bmp_vectors(resources: pathlib.Path) -> list[Json]:
    """The run-length-encoded BMP files of the codec TSV, then the BMP files GDAL refuses."""
    out = []
    for row in rows(resources / "gdal-codec-vectors.tsv"):
        name, pixels, data = row[0], row[6], base64.b64decode(row[7])
        if data[:2] != b"BM":
            continue
        offset, width, height, bits = bmp_geometry(data)
        compression = struct.unpack("<I", data[30:34])[0]
        if (compression, bits) in ((1, 8), (2, 4)):
            params = {"bitsPerPixel": bits, "width": width, "height": height}
            expect = {"sha256": pixels, "size": width * height}
            out.append({"id": vector_id(name), "steps": [step(data[offset:], expect, params)]})
    for row in rows(resources / "gdal-codec-refusals.tsv"):
        name, data = row[0], base64.b64decode(row[2])
        if data[:2] == b"BM":
            offset, width, height, bits = bmp_geometry(data)
            params = {"bitsPerPixel": bits, "width": width, "height": height}
            out.append(
                {"id": vector_id(name, "-refused"), "steps": [step(data[offset:], {"error": "Validation"}, params)]}
            )
    return out


def image_family(engine: pathlib.Path) -> None:
    resources = engine / "core/src/test/resources"
    suites: dict[str, list[Json]] = {name: [] for name in IMAGE_CODECS}
    for name, pixels, data in color_rows(resources, suites):
        image = color_tiff(pixels, data)
        found = color_tiff_vector(image) if image is not None else None
        if found is None:
            continue
        codec, vector = found
        if vector is None:
            continue
        suites[codec].append({"id": unique_id(suites[codec], vector_id(name)), **vector})
    suites["YCbCrToRGB"].append(neutral_chroma_vector())
    suites["MicrosoftRLE"] += bmp_vectors(resources)
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
