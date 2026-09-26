"""LZ4 block and frame writers and a block reader, in plain Python, for the conformance suite.

The suite's LZ4 inputs are built here, byte by byte, so that they are reviewable and reproducible
without a third-party package: a greedy block compressor that emits real match sequences (so a
decoder is exercised on copies, overlapping ones included, not only on literals), the frame
format around it, and xxHash-32 for the frame's header, block and content checksums. The reader
decodes a block by the LZ4 Block Format Description and is used to check every block the writer
makes before a case uses it.

References: LZ4 Block Format Description and LZ4 Frame Format Description (lz4/lz4, doc/),
and the xxHash specification (Cyan4973/xxHash, doc/xxhash_spec.md).
"""
import struct

MASK32 = 0xFFFFFFFF
P1, P2, P3, P4, P5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393
FRAME_MAGIC = b"\x04\x22\x4d\x18"


def _rotl(x, r):
    return ((x << r) | (x >> (32 - r))) & MASK32


def xxh32(data, seed=0):
    """xxHash-32 of `data`."""
    n = len(data)
    i = 0
    if n >= 16:
        v = [(seed + P1 + P2) & MASK32, (seed + P2) & MASK32, seed & MASK32, (seed - P1) & MASK32]
        while i + 16 <= n:
            for k in range(4):
                lane = struct.unpack_from("<I", data, i + 4 * k)[0]
                v[k] = (_rotl((v[k] + lane * P2) & MASK32, 13) * P1) & MASK32
            i += 16
        h = (_rotl(v[0], 1) + _rotl(v[1], 7) + _rotl(v[2], 12) + _rotl(v[3], 18)) & MASK32
    else:
        h = (seed + P5) & MASK32
    h = (h + n) & MASK32
    while i + 4 <= n:
        h = (h + struct.unpack_from("<I", data, i)[0] * P3) & MASK32
        h = (_rotl(h, 17) * P4) & MASK32
        i += 4
    while i < n:
        h = (h + data[i] * P5) & MASK32
        h = (_rotl(h, 11) * P1) & MASK32
        i += 1
    h ^= h >> 15
    h = (h * P2) & MASK32
    h ^= h >> 13
    h = (h * P3) & MASK32
    h ^= h >> 16
    return h


assert xxh32(b"") == 0x02CC5D05  # the specification's test value for the empty input


def _length(n):
    """The 255-run extension bytes of a literal or match length beyond its 4-bit field."""
    out = bytearray()
    while n >= 255:
        out.append(255)
        n -= 255
    out.append(n)
    return bytes(out)


def _sequence(literals, offset=None, match=0):
    lit = len(literals)
    token_lit = min(lit, 15)
    if offset is None:
        token = token_lit << 4
        return bytes([token]) + (_length(lit - 15) if lit >= 15 else b"") + literals
    m = match - 4
    token = (token_lit << 4) | min(m, 15)
    out = bytes([token]) + (_length(lit - 15) if lit >= 15 else b"") + literals + struct.pack("<H", offset)
    return out + (_length(m - 15) if m >= 15 else b"")


def compress_block(data):
    """One LZ4 block: greedy 4-byte matching, honouring the end-of-block rules (the last five bytes
    are literals, and no match starts in the last twelve)."""
    n = len(data)
    out = bytearray()
    anchor = i = 0
    last_match_start = n - 12
    table = {}
    while i < last_match_start:
        key = data[i:i + 4]
        candidate = table.get(key)
        table[key] = i
        if candidate is not None and i - candidate <= 0xFFFF:
            length = 4
            while i + length < n - 5 and data[candidate + length] == data[i + length]:
                length += 1
            out += _sequence(data[anchor:i], i - candidate, length)
            for j in range(i + 1, min(i + length, last_match_start)):
                table[data[j:j + 4]] = j
            i += length
            anchor = i
        else:
            i += 1
    out += _sequence(data[anchor:])
    return bytes(out)


class Malformed(ValueError):
    """Not a well-formed LZ4 block."""


def decompress_block(block, size):
    """Decode one LZ4 block that must yield exactly `size` bytes."""
    out = bytearray()
    i = 0
    while True:
        if i >= len(block):
            raise Malformed("block ends inside a sequence")
        token = block[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                if i >= len(block):
                    raise Malformed("block ends inside a literal length")
                b = block[i]
                i += 1
                lit += b
                if b != 255:
                    break
        if i + lit > len(block):
            raise Malformed("literals run past the block")
        out += block[i:i + lit]
        i += lit
        if i == len(block):
            break
        if i + 2 > len(block):
            raise Malformed("block ends inside an offset")
        offset = struct.unpack_from("<H", block, i)[0]
        i += 2
        if offset == 0 or offset > len(out):
            raise Malformed(f"match offset {offset} reaches before the output")
        match = (token & 15) + 4
        if token & 15 == 15:
            while True:
                if i >= len(block):
                    raise Malformed("block ends inside a match length")
                b = block[i]
                i += 1
                match += b
                if b != 255:
                    break
        for _ in range(match):
            out.append(out[-offset])
        if len(out) > size:
            raise Malformed("block decodes to more than its size")
    if len(out) != size:
        raise Malformed(f"block decodes to {len(out)} bytes, not {size}")
    return bytes(out)


def frame(content, block_checksum=False, content_checksum=True, content_size=False, blocks=None):
    """An LZ4 frame holding `content`: linked blocks of at most 64 KiB, each compressed (or stored
    when compression does not help), with the checksums asked for."""
    flg = 0x40 | 0x20                  # version 01, blocks independent
    if block_checksum:
        flg |= 0x10
    if content_size:
        flg |= 0x08
    if content_checksum:
        flg |= 0x04
    bd = 0x40                          # 64 KiB maximum block size
    descriptor = bytes([flg, bd]) + (struct.pack("<Q", len(content)) if content_size else b"")
    header = FRAME_MAGIC + descriptor + bytes([(xxh32(descriptor) >> 8) & 0xFF])
    out = bytearray(header)
    for start in range(0, len(content), 65536) if blocks is None else blocks:
        chunk = content[start:start + 65536]
        packed = compress_block(chunk)
        assert decompress_block(packed, len(chunk)) == chunk
        if len(packed) < len(chunk):
            body, size = packed, len(packed)
        else:
            body, size = chunk, len(chunk) | 0x80000000
        out += struct.pack("<I", size) + body
        if block_checksum:
            out += struct.pack("<I", xxh32(body))
    out += b"\x00\x00\x00\x00"
    if content_checksum:
        out += struct.pack("<I", xxh32(content))
    return bytes(out)
