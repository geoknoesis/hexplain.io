"""Zstandard inputs of the conformance suite, and the checks that keep them honest.

A Zstandard compressor is too large to write here, so the compressed frames are pre-made (with
python-zstandard 0.25, level 3, content size and content checksum written) and committed as hex,
each pinned by its SHA-256. What is checked without any package: the pin, the frame magic, and
the content checksum trailer, recomputed with the XXH64 below from the content the case expects.
When python-zstandard happens to be installed the generator also decodes every frame with it; it
is not a dependency of the suite.

Frames hand-built here instead (a raw-block frame naming a dictionary) are assembled field by
field from RFC 8878.
"""
import hashlib
import struct

M64 = (1 << 64) - 1
Q1, Q2, Q3, Q4, Q5 = (11400714785074694791, 14029467366897019727, 1609587929392839161,
                      9650029242287828579, 2870177450012600261)
MAGIC = b"\x28\xb5\x2f\xfd"


def _rotl(x, r):
    return ((x << r) | (x >> (64 - r))) & M64


def _round(acc, lane):
    acc = (acc + lane * Q2) & M64
    return (_rotl(acc, 31) * Q1) & M64


def _merge(acc, val):
    acc ^= _round(0, val)
    return (acc * Q1 + Q4) & M64


def xxh64(data, seed=0):
    """XXH64 of `data` (xxHash specification, doc/xxhash_spec.md)."""
    n = len(data)
    i = 0
    if n >= 32:
        v = [(seed + Q1 + Q2) & M64, (seed + Q2) & M64, seed & M64, (seed - Q1) & M64]
        while i + 32 <= n:
            for k in range(4):
                v[k] = _round(v[k], struct.unpack_from("<Q", data, i + 8 * k)[0])
            i += 32
        h = (_rotl(v[0], 1) + _rotl(v[1], 7) + _rotl(v[2], 12) + _rotl(v[3], 18)) & M64
        for k in range(4):
            h = _merge(h, v[k])
    else:
        h = (seed + Q5) & M64
    h = (h + n) & M64
    while i + 8 <= n:
        h ^= _round(0, struct.unpack_from("<Q", data, i)[0])
        h = (_rotl(h, 27) * Q1 + Q4) & M64
        i += 8
    if i + 4 <= n:
        h ^= (struct.unpack_from("<I", data, i)[0] * Q1) & M64
        h = (_rotl(h, 23) * Q2 + Q3) & M64
        i += 4
    while i < n:
        h ^= (data[i] * Q5) & M64
        h = (_rotl(h, 11) * Q1) & M64
        i += 1
    h ^= h >> 33
    h = (h * Q2) & M64
    h ^= h >> 29
    h = (h * Q3) & M64
    h ^= h >> 32
    return h


assert xxh64(b"") == 0xEF46DB3751D8E999  # the specification's value for the empty input

#: content -> (frame hex, sha256 prefix). Each frame declares its content size and a content checksum.
CONTENT_1 = b"Hexplain Zstandard frame: " + b"abcabcabcabcabcabc" * 10
CONTENT_2 = b"second frame"
FRAMES = {
    CONTENT_1: ("28b52ffd24ce250100e8486578706c61696e205a7374616e64617264206672616d653a206162630100b9a49c13a42a614b",
                "b5f4163f4dd3085e"),
    CONTENT_2: ("28b52ffd240c6100007365636f6e64206672616d65176407b6", "0d3004a4989bed77"),
}


def frame(content):
    """The pre-made frame of `content`, after checking its pin, magic and checksum trailer."""
    hexed, pin = FRAMES[content]
    data = bytes.fromhex(hexed)
    assert hashlib.sha256(data).hexdigest()[:16] == pin, "a committed Zstandard frame changed"
    assert data[:4] == MAGIC
    assert struct.unpack("<I", data[-4:])[0] == xxh64(content) & 0xFFFFFFFF, "checksum trailer"
    try:
        import zstandard
    except ImportError:
        return data
    assert zstandard.ZstdDecompressor().decompress(data) == content
    return data


def content_size_mismatch_frame(content):
    """The pre-made frame of `content` with its Frame_Content_Size one larger than the content. The frame is
    single-segment with a one-byte content size (Frame_Header_Descriptor 0x24: Single_Segment_flag and
    Content_Checksum_flag), so the size is the byte after the descriptor; the window is that size, so the block
    still fits it, and the content checksum still matches the content: only the declared size is wrong."""
    data = bytearray(frame(content))
    assert data[4] == 0x24 and data[5] == len(content) < 255
    data[5] = len(content) + 1
    return bytes(data)


def dictionary_frame(content, dictionary_id):
    """A single-segment frame of one raw block that names a dictionary: Frame_Header_Descriptor
    0x21 (Single_Segment_flag, a one-byte Dictionary_ID, a one-byte Frame_Content_Size, no
    checksum), then the dictionary ID, the content size, and a last raw block."""
    assert len(content) < 256 and 0 < dictionary_id < 256
    block_header = (1 | (0 << 1) | (len(content) << 3)).to_bytes(3, "little")
    return MAGIC + bytes([0x21, dictionary_id, len(content)]) + block_header + content
