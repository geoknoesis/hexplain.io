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
import argparse
import base64
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _tiff  # noqa: E402
from vectors import step, write_suite  # noqa: E402

GDAL = {"id": "gdal-3.13.3", "url": "https://github.com/OSGeo/gdal/tree/v3.13.3",
        "description": "Pixels decoded by GDAL 3.13.3 (container ghcr.io/osgeo/gdal@sha256:2dd0f81ef927ff4c3d4dbe4f73c029dc86d4073974c0564f8e196f6e1412e2e0) "
                       "from GDAL autotest files at commit c8b4c45fca87d3e6fbf80e7a7898b8a661ad0edc and from synthetic files written by "
                       "hexplain-tools tests/gdal/codec_vectors.py; imported by tools/codecs/_import_gdal_vectors.py from "
                       "core/src/test/resources/gdal-codec-vectors.tsv, gdal-codec-refusals.tsv and gdal-color-*.tsv.",
        "licence": "GDAL autotest data: MIT/X (GDAL LICENSE.TXT and per-file notices); synthetic files CC0-1.0"}
TIFF_CODECS = {2: "CCITTModifiedHuffman", 32771: "CCITTModifiedHuffman", 3: "CCITTGroup3", 4: "CCITTGroup4",
               32766: "NeXT", 32809: "ThunderScan"}
BITS = {2: 1, 32771: 1, 3: 1, 4: 1, 32766: 2, 32809: 4}


def rows(path):
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            yield line.split("\t")


def vector_id(name, suffix=""):
    return re.sub(r"[^A-Za-z0-9]+", "-", name.rsplit("/", 1)[-1]).strip("-") + suffix


def tiff_params(compression, tags, width, count):
    fill = _tiff.scalar(tags, 266, 1)
    if compression in (2, 32771):
        return {"columns": width, "rows": count, "fillOrder": fill, "rowAlignment": 8 if compression == 2 else 16}
    if compression == 3:
        return {"columns": width, "rows": count, "options": _tiff.scalar(tags, 292, 0), "fillOrder": fill}
    if compression == 4:
        return {"columns": width, "rows": count, "options": _tiff.scalar(tags, 293, 0), "fillOrder": fill}
    return {"columns": width, "rowBytes": (width * BITS[compression] + 7) // 8, "rows": count}


def tiff_family_file(name, data):
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


def strip_steps(data, tags, compression, fail_at=None):
    width, height = tags[256][0], tags[257][0]
    per = _tiff.scalar(tags, 278, height)
    steps = []
    for i, strip in enumerate(_tiff.strips(data, tags)):
        count = min(per, height - i * per)
        if count <= 0:
            break
        failing = fail_at is not None and i == fail_at
        steps.append(step(strip, {"error": "Validation"} if failing else {"ok": True},
                          tiff_params(compression, tags, width, count)))
        if failing:
            break
    return steps


def tiff_family(engine):
    resources = engine / "core/src/test/resources"
    suites = {name: [] for name in sorted(set(TIFF_CODECS.values()))}
    for row in rows(resources / "gdal-codec-vectors.tsv"):
        name, pixels, data = row[0], row[6], base64.b64decode(row[7])
        found = tiff_family_file(name, data)
        if not found:
            continue
        tags, compression = found
        suites[TIFF_CODECS[compression]].append({
            "id": vector_id(name), "session": True, "steps": strip_steps(data, tags, compression),
            "expectAll": {"sha256": pixels, "unpack": {"bitsPerSample": BITS[compression], "width": tags[256][0]}}})
    for row in rows(resources / "gdal-codec-refusals.tsv"):
        name, message, data = row[0], row[1], base64.b64decode(row[2])
        found = tiff_family_file(name, data)
        block = re.search(r"Y offset (\d+)", message)
        if not found or not block:
            continue
        tags, compression = found
        suites[TIFF_CODECS[compression]].append({
            "id": vector_id(name, "-refused"), "session": True,
            "steps": strip_steps(data, tags, compression, fail_at=int(block.group(1)))})
    for codec, vector_list in suites.items():
        if not vector_list:
            raise SystemExit(f"FAIL: no GDAL vector for {codec}")
        write_suite(codec, [GDAL], vector_list)
    print("PASS: " + ", ".join(f"{codec} {len(v)}" for codec, v in suites.items()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    parser.add_argument("family", choices=["tiff"])
    args = parser.parse_args()
    {"tiff": tiff_family}[args.family](pathlib.Path(args.engine))


if __name__ == "__main__":
    main()
