"""The first image directory of a classic TIFF, as far as the codec vector builders need it."""

from __future__ import annotations

import struct
from typing import Any

SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8}
FORMATS = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 16: "Q"}
#: An image directory: {tag: a list of numbers, or raw bytes for ASCII and UNDEFINED}.
Tags = dict[int, Any]


def first_ifd(data: bytes) -> tuple[Tags, str]:
    """({tag: list of numbers, or raw bytes for ASCII/UNDEFINED}, byte order) of IFD 0; RATIONAL as floats."""
    order = {b"II": "<", b"MM": ">"}[data[:2]]
    if struct.unpack(order + "H", data[2:4])[0] != 42:
        raise ValueError("not a classic TIFF")
    at = struct.unpack(order + "I", data[4:8])[0]
    count = struct.unpack(order + "H", data[at : at + 2])[0]
    tags: Tags = {}
    for i in range(count):
        entry = at + 2 + 12 * i
        tag, kind, n = struct.unpack(order + "HHI", data[entry : entry + 8])
        size = SIZES.get(kind, 1) * n
        start = entry + 8 if size <= 4 else struct.unpack(order + "I", data[entry + 8 : entry + 12])[0]
        raw = data[start : start + size]
        if kind in FORMATS:
            tags[tag] = list(struct.unpack(order + FORMATS[kind] * n, raw))
        elif kind == 5:
            pairs = struct.unpack(order + "II" * n, raw)
            tags[tag] = [pairs[2 * k] / pairs[2 * k + 1] for k in range(n)]
        else:
            tags[tag] = raw
    return tags, order


def scalar(tags: Tags, tag: int, default: int) -> int:
    """The first value of the integer tag [tag], or [default] when the directory lacks it."""
    value = tags.get(tag)
    return default if value is None else int(value[0])


def strips(data: bytes, tags: Tags) -> list[bytes]:
    """The stored bytes of every strip (or tile), in order."""
    offsets, counts = tags.get(324) or tags[273], tags.get(325) or tags[279]
    return [data[o : o + c] for o, c in zip(offsets, counts, strict=True)]
