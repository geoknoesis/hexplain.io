"""A deliberately small, independent implementation of Store, Deflate, Zlib and Gzip.

It exists to prove tools/codecs/run_vectors.py end to end with an implementation that shares no
code with the reference engine. Usage (the runner's command template):

    python tools/codecs/_python_reference.py vector --manifest M --id ID
"""
import argparse
import hashlib
import json
import pathlib
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import vectors  # noqa: E402

MENC = "https://hexplain.io/ns/register/media-encoding#"


class CodecError(Exception):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def _level(params, allowed):
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


def _inflate(data, wbits, limit, trailing):
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


def apply(codec, direction, params, data, limit):
    name = codec[len(MENC):]
    if name == "Store":
        if params:
            raise CodecError("Description", "Store takes no parameters")
        if len(data) > limit:
            raise CodecError("ResourceLimit", f"more than {limit} bytes")
        return data
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
    raise CodecError("Unsupported", f"{codec} is not implemented here")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["vector"])
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    path = pathlib.Path(args.manifest)
    manifest = vectors.load(path)
    vector = next(v for v in manifest["vectors"] if v["id"] == args.id)
    steps, outputs = [], []
    for step in vector["steps"]:
        try:
            data = apply(manifest["codec"], step["direction"], step.get("params", {}),
                         vectors.input_bytes(step["input"], path.parent), step.get("maxOutputBytes", 67108864))
        except CodecError as e:
            steps.append({"ok": False, "category": e.category, "message": str(e)})
            break
        outputs.append(data)
        steps.append({"ok": True, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    result = {"steps": steps}
    if "expectAll" in vector:
        joined = b"".join(outputs)
        result["all"] = {"sha256": hashlib.sha256(joined).hexdigest(), "size": len(joined)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
