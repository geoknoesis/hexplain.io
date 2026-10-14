"""A deliberately small, independent implementation of Store, Deflate, Zlib and Gzip.

It exists to prove tools/codecs/run_vectors.py end to end with an implementation that shares no
code with the reference engine. Usage (the runner's command template):

    python tools/codecs/_python_reference.py vector --manifest M --id ID
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import zlib
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vectors  # noqa: E402

MENC = "https://hexplain.io/ns/register/media-encoding#"


class CodecError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


def _level(params: dict[str, Any], allowed: set[str]) -> str:
    for name in params:
        if name not in allowed:
            raise CodecError("Description", f"unknown parameter {name}")
    level = params.get("level", -1)
    if not isinstance(level, int) or isinstance(level, bool) or not -1 <= level <= 9:
        raise CodecError("Description", f"level {level!r}")
    trailing = params.get("trailing", "refuse")
    if trailing not in ("refuse", "ignore"):
        raise CodecError("Description", f"trailing {trailing!r}")
    return trailing


def _inflate(data: bytes, wbits: int, limit: int, trailing: str) -> tuple[bytes, bytes]:
    d = zlib.decompressobj(wbits)
    try:
        out = d.decompress(data, limit + 1)
    except zlib.error as e:
        raise CodecError("Checksum" if "incorrect" in str(e) and "check" in str(e) else "Validation", str(e)) from e
    if len(out) > limit:
        raise CodecError("ResourceLimit", f"more than {limit} bytes")
    if not d.eof:
        raise CodecError("Validation", "truncated stream")
    return out, d.unused_data


def _encode(name: str, params: dict[str, Any], data: bytes, limit: int) -> bytes:
    """The encode direction of the four codecs, through zlib: raw DEFLATE, a zlib stream or one gzip member."""
    level = params.get("level", -1)
    if name == "Deflate":
        _level(params, {"level"})
        c = zlib.compressobj(level, zlib.DEFLATED, -15)
    elif name == "Zlib":
        _level(params, {"level", "trailing"})
        c = zlib.compressobj(level, zlib.DEFLATED, 15)
    elif name == "Gzip":
        for p in params:
            if p != "trailing":
                raise CodecError("Description", f"unknown parameter {p}")
        c = zlib.compressobj(-1, zlib.DEFLATED, 31)
    else:
        raise CodecError("Unsupported", f"{name} does not encode here")
    out = c.compress(data) + c.flush()
    if len(out) > limit:
        raise CodecError("ResourceLimit", f"more than {limit} bytes")
    return out


def apply(codec: str, direction: str, params: dict[str, Any], data: bytes, limit: int) -> bytes:
    name = codec[len(MENC) :]
    if name == "Store":
        if params:
            raise CodecError("Description", "Store takes no parameters")
        if len(data) > limit:
            raise CodecError("ResourceLimit", f"more than {limit} bytes")
        return data
    if direction == "encode":
        return _encode(name, params, data, limit)
    if direction != "decode":
        raise CodecError("Unsupported", f"{direction} is not implemented here")
    if name == "Deflate":
        _level(params, {"level"})
        out, rest = _inflate(data, -15, limit, "refuse")
        if rest:
            raise CodecError("Validation", "trailing bytes")
        return out
    if name == "Zlib":
        trailing = _level(params, {"level", "trailing"})
        out, rest = _inflate(data, 15, limit, trailing)
        if rest and trailing == "refuse":
            raise CodecError("Validation", "trailing bytes")
        return out
    if name == "Gzip":
        return _gunzip(params, data, limit)
    raise CodecError("Unsupported", f"{codec} is not implemented here")


def _gunzip(params: dict[str, Any], data: bytes, limit: int) -> bytes:
    """The decode direction of Gzip: every member, and what follows the last one as the trailing parameter says."""
    for p in params:
        if p != "trailing":
            raise CodecError("Description", f"unknown parameter {p}")
    trailing = params.get("trailing", "refuse")
    if trailing not in ("refuse", "ignore"):
        raise CodecError("Description", f"trailing {trailing!r}")
    out, rest, members = b"", data, 0
    while rest:
        if len(rest) < 10 or rest[:2] != b"\x1f\x8b":
            if members and trailing == "ignore":
                break
            raise CodecError("Validation", "not a gzip member")
        part, rest = _inflate(rest, 31, limit - len(out), "refuse")
        out += part
        members += 1
    if not members:
        raise CodecError("Validation", "empty gzip stream")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["vector"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    path = pathlib.Path(args.manifest)
    manifest = vectors.load(path)
    vector = next(v for v in manifest["vectors"] if v["id"] == args.id)
    steps: list[dict[str, Any]] = []
    outputs: list[bytes] = []
    for step in vector["steps"]:
        try:
            data = apply(
                manifest["codec"],
                step["direction"],
                step.get("params", {}),
                vectors.input_bytes(step["input"], path.parent, outputs[-1] if outputs else None),
                step.get("maxOutputBytes", 67108864),
            )
        except CodecError as e:
            steps.append({"ok": False, "category": e.category, "message": str(e)})
            break
        outputs.append(data)
        steps.append({"ok": True, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    result: dict[str, Any] = {"steps": steps}
    if "expectAll" in vector:
        joined = b"".join(outputs)
        result["all"] = {"sha256": hashlib.sha256(joined).hexdigest(), "size": len(joined)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
