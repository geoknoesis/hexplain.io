"""Write the vector suites of the minimum codec set: Store, Deflate, Zlib, Gzip and Delta.

Compressed inputs are produced by CPython's zlib binding (the zlib reference library); the
Delta vectors are the worked examples of the Processing Model's Delta definition, computed by
hand. Re-running rewrites the manifests; commit them together with any change to this script.
"""
import gzip
import hashlib
import pathlib
import platform
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from vectors import step, write_suite as write  # noqa: E402

PAYLOAD = b"Hexplain decodes the minimum codec set. " * 64
ZLIB_SOURCE = {
    "id": "zlib", "url": "https://zlib.net/",
    "description": f"Compressed with zlib {zlib.ZLIB_RUNTIME_VERSION} through CPython {platform.python_version()} "
                   "(tools/codecs/_generate_minimum_vectors.py); corruptions are single-byte edits of those streams.",
    "licence": "zlib licence (library); inputs CC0-1.0",
}
PM_SOURCE = {
    "id": "processing-model", "url": "https://hexplain.io/specification/processing/#delta-parameters",
    "description": "Worked from the Processing Model's Delta definition by hand.",
    "licence": "CC0-1.0",
}


def flip(data, at):
    b = bytearray(data)
    b[at] ^= 0x01
    return bytes(b)


def ok_payload():
    return {"sha256": hashlib.sha256(PAYLOAD).hexdigest(), "size": len(PAYLOAD)}


def main():
    store = [
        {"id": "identity", "steps": [step(bytes([0, 1, 255]), {"hex": "0001ff"})]},
        {"id": "empty", "steps": [step(b"", {"hex": ""})]},
        {"id": "encode-identity", "steps": [step(bytes([7, 8]), {"hex": "0708"}, direction="encode")]},
        {"id": "over-bound", "steps": [step(bytes(10), {"error": "ResourceLimit"}, max_output=4)]},
    ]
    write("Store", [PM_SOURCE], store)

    raw = zlib.compressobj(6, zlib.DEFLATED, -15)
    deflated = raw.compress(PAYLOAD) + raw.flush()
    write("Deflate", [ZLIB_SOURCE], [
        {"id": "level6", "steps": [step(deflated, ok_payload())]},
        {"id": "truncated", "steps": [step(deflated[:-4], {"error": "Validation"})]},
        {"id": "trailing-bytes", "steps": [step(deflated + b"\x00", {"error": "Validation"})]},
        {"id": "over-bound", "steps": [step(deflated, {"error": "ResourceLimit"}, max_output=100)]},
        {"id": "bad-level", "steps": [step(deflated, {"error": "Description"}, {"level": 10})]},
    ])

    wrapped = zlib.compress(PAYLOAD, 6)
    write("Zlib", [ZLIB_SOURCE], [
        {"id": "level6", "steps": [step(wrapped, ok_payload())]},
        {"id": "empty", "steps": [step(zlib.compress(b""), {"hex": ""})]},
        {"id": "adler-mismatch", "steps": [step(flip(wrapped, len(wrapped) - 1), {"error": "Checksum"})]},
        {"id": "truncated", "steps": [step(wrapped[:-6], {"error": "Validation"})]},
        {"id": "trailing-refused", "steps": [step(wrapped + b"\x00", {"error": "Validation"})]},
        {"id": "trailing-ignored", "steps": [step(wrapped + b"\x00\x01", ok_payload(), {"trailing": "ignore"})]},
        {"id": "preset-dictionary", "steps": [step(bytes.fromhex("78bb0000000103000000ff"), {"error": "Validation"})]},
        {"id": "over-bound", "steps": [step(wrapped, {"error": "ResourceLimit"}, max_output=100)]},
        {"id": "bad-level", "steps": [step(wrapped, {"error": "Description"}, {"level": 10})]},
        {"id": "bad-trailing", "steps": [step(wrapped, {"error": "Description"}, {"trailing": "maybe"})]},
    ])

    member = gzip.compress(PAYLOAD, compresslevel=6, mtime=0)
    two = hashlib.sha256(PAYLOAD + PAYLOAD).hexdigest()
    write("Gzip", [ZLIB_SOURCE], [
        {"id": "one-member", "steps": [step(member, ok_payload())]},
        {"id": "two-members", "steps": [step(member + member, {"sha256": two, "size": 2 * len(PAYLOAD)})]},
        {"id": "crc-mismatch", "steps": [step(flip(member, len(member) - 8), {"error": "Checksum"})]},
        {"id": "length-mismatch", "steps": [step(flip(member, len(member) - 1), {"error": "Checksum"})]},
        {"id": "trailing-refused", "steps": [step(member + b"junk", {"error": "Validation"})]},
        {"id": "trailing-ignored", "steps": [step(member + b"junk", ok_payload(), {"trailing": "ignore"})]},
        {"id": "empty", "steps": [step(b"", {"error": "Validation"})]},
        {"id": "over-bound", "steps": [step(member, {"error": "ResourceLimit"}, max_output=100)]},
    ])

    write("Delta", [PM_SOURCE], [
        {"id": "chunky-rgb", "steps": [step(bytes([10, 20, 30, 1, 2, 3]), {"hex": "0a141e0b1621"},
                                            {"elementSize": 1, "samplesPerPixel": 3})]},
        {"id": "big-endian-16", "steps": [step(bytes.fromhex("000100010001"), {"hex": "000100020003"},
                                               {"elementSize": 2})]},
        {"id": "little-endian-16", "steps": [step(bytes.fromhex("01000100"), {"hex": "01000200"},
                                                  {"elementSize": 2, "littleEndian": 1})]},
        {"id": "rows-restart", "steps": [step(bytes([1, 1, 1, 1, 5, 1, 1, 1]), {"hex": "0102030405060708"},
                                              {"elementSize": 1, "rowBytes": 4})]},
        {"id": "wraps-modulo", "steps": [step(bytes([250, 10]), {"hex": "fa04"}, {"elementSize": 1})]},
        {"id": "predictor-none", "steps": [step(bytes([1, 1]), {"hex": "0101"}, {"elementSize": 1, "predictor": 1})]},
        {"id": "encode-chunky-rgb", "steps": [step(bytes([10, 20, 30, 11, 22, 33]), {"hex": "0a141e010203"},
                                                   {"elementSize": 1, "samplesPerPixel": 3}, direction="encode")]},
        {"id": "predictor-3-unsupported", "steps": [step(bytes([1]), {"error": "Unsupported"},
                                                         {"elementSize": 1, "predictor": 3})]},
        {"id": "missing-element-size", "steps": [step(bytes([1]), {"error": "Description"})]},
        {"id": "partial-element", "steps": [step(bytes([1, 2, 3]), {"error": "Validation"}, {"elementSize": 2})]},
    ])
    print("PASS: wrote Store, Deflate, Zlib, Gzip and Delta suites")


if __name__ == "__main__":
    sys.exit(main())
