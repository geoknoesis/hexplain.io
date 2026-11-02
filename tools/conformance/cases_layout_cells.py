"""Physical Parser cases: the cells of a chunked layout whose chunk table is in Morton or Hilbert order.

A parsed tree holds a layout field's bytes, which do not show which chunk a table entry was taken for. These cases
use the suite's cell form (specification/conformance/index.html#layout-cells): the manifest's `cells` names the
layout field, and the tree gives that field as its cells in logical order, each addressed through the chunk table. A
processor that orders the table by another key reads other chunks, and other cells.

Both cases use one grid: 3 rows of 6 one-byte cells, in chunks of 1 x 2 cells, so 3 x 3 chunks. The chunks are stored
one after another in row-major order and hold the cell values 0 to 17 in logical order, so the expected cells are
0, 1, ... 17 whatever the table's order; what differs between the cases is the order in which the table lists the
chunks' offsets, which is the order under test. Three chunks per dimension pad to four, two bits each, so both orders
skip keys (those of a chunk index 3) and neither coincides with row- or column-major order.
"""

from __future__ import annotations

from collections.abc import Callable

from cases_physical import pp
from suite import canonical_json

ROWS, COLUMNS, CHUNK_COLUMNS = 3, 6, 2
CHUNKS_Y, CHUNKS_X = ROWS, COLUMNS // CHUNK_COLUMNS
BITS = 2  # the chunk counts, 3 and 3, pad to 4: two bits per dimension
TABLE_BYTES = CHUNKS_Y * CHUNKS_X
FEATURES = {"features": {"requires": ["chunked-cell-access", "chunk-order-other"]}, "cells": ["pixels"]}


def morton_key(chunk: tuple[int, ...]) -> int:
    """The Morton key of dlv:morton: bit j of dimension i is bit j * d + i of the key."""
    d = len(chunk)
    return sum(((index >> j) & 1) << (j * d + i) for i, index in enumerate(chunk) for j in range(BITS))


def hilbert_key(chunk: tuple[int, ...]) -> int:
    """The Hilbert index of dlv:hilbert: Skilling's AxesToTranspose (Programming the Hilbert curve, 2004) over the
    chunk indices, the first declared dimension the first axis, then the transposed bits read as one integer, the
    first axis contributing the most significant bit of each group."""
    x, n = list(chunk), len(chunk)
    top = 1 << (BITS - 1)
    q = top
    while q > 1:  # inverse undo
        p = q - 1
        for i in range(n):
            if x[i] & q:
                x[0] ^= p
            else:
                t = (x[0] ^ x[i]) & p
                x[0] ^= t
                x[i] ^= t
        q >>= 1
    for i in range(1, n):  # Gray encode
        x[i] ^= x[i - 1]
    t, q = 0, top
    while q > 1:
        if x[n - 1] & q:
            t ^= q - 1
        q >>= 1
    x = [v ^ t for v in x]
    key = 0
    for j in range(BITS - 1, -1, -1):
        for i in range(n):
            key = (key << 1) | ((x[i] >> j) & 1)
    return key


def table(key: Callable[[tuple[int, ...]], int]) -> list[int]:
    """The chunk offsets in ascending key over the padded 4 x 4 grid, the keys of chunks outside the real 3 x 3
    skipped. Chunk (y, x) is stored at TABLE_BYTES + 2 * (3 * y + x), from the start of the stream."""
    padded = [(y, x) for y in range(1 << BITS) for x in range(1 << BITS)]
    ordered = [c for c in sorted(padded, key=key) if c[0] < CHUNKS_Y and c[1] < CHUNKS_X]
    return [TABLE_BYTES + CHUNK_COLUMNS * (CHUNKS_X * y + x) for y, x in ordered]


def _is_curve(key: Callable[[tuple[int, ...]], int]) -> bool:
    """A Hilbert curve visits every cell of the padded grid once, each step to an adjacent cell."""
    cells = sorted(((y, x) for y in range(1 << BITS) for x in range(1 << BITS)), key=key)
    steps = zip(cells, cells[1:], strict=False)
    return len({key(c) for c in cells}) == len(cells) and all(abs(a - c) + abs(b - d) == 1 for (a, b), (c, d) in steps)


MORTON, HILBERT = table(morton_key), table(hilbert_key)
# The Morton order of the chunks (y, x): (0,0) (1,0) (0,1) (1,1) (2,0) (2,1) (0,2) (1,2) (2,2).
assert MORTON == [9, 15, 11, 17, 21, 23, 13, 19, 25], MORTON
assert _is_curve(hilbert_key) and hilbert_key((0, 0)) == 0
assert len({tuple(MORTON), tuple(HILBERT), tuple(sorted(MORTON))}) == 3, "the orders under test must differ"

PIXELS = bytes(range(ROWS * COLUMNS))


def description(order: str) -> str:
    return f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:offsets ex:pixels ) .
   ex:offsets a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount {TABLE_BYTES} .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:chunkOffsetsFromField ex:offsets ;
       dlv:chunkOffsetBase bddo:streamStart ; dlv:chunkOrder dlv:{order} ; dlv:hasDimension ( ex:DimY ex:DimX ) .
   ex:DimY a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSize {ROWS} ; dlv:chunkSize 1 .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSize {COLUMNS} ; dlv:chunkSize {CHUNK_COLUMNS} .
   """


pp(
    "layout-cells-morton",
    "The chunk table of a dlv:morton layout is in ascending Morton key",
    "The chunk indices (y, x) are interleaved least significant bit first, y, the first declared dimension, "
    "giving the lowest bit of each pair; keys of a chunk index 3, outside the real 3 x 3 chunks, take no entry. "
    "The table therefore lists the chunks (0,0) (1,0) (0,1) (1,1) (2,0) (2,1) (0,2) (1,2) (2,2), and the cell at "
    "row r and column c is byte c mod 2 of the chunk (r, c div 2). Read so, the cells are 0 to 17 in order.",
    ["req-pm-data-layouts-3"],
    ["data-layouts", "conformance-classes"],
    description("morton"),
    bytes(MORTON) + PIXELS,
    {"offsets": MORTON, "pixels": list(PIXELS)},
    manifest=FEATURES,
)

pp(
    "layout-cells-hilbert",
    "The chunk table of a dlv:hilbert layout is in ascending Hilbert index",
    "The Hilbert index of each chunk (y, x) is computed by Skilling's algorithm with two bits per dimension, y "
    "the first axis; keys of a chunk index 3 take no entry. The table lists the chunks in that order, and the "
    "cells, read through it, are 0 to 17 in order. (A processor that orders the table by the Morton key, or by "
    "rows, reads other chunks.)",
    ["req-pm-data-layouts-3"],
    ["data-layouts", "conformance-classes"],
    description("hilbert"),
    bytes(HILBERT) + PIXELS,
    {"offsets": HILBERT, "pixels": list(PIXELS)},
    manifest=FEATURES,
)


# Overlapping rules make first-match semantics observable, including reversed list order.
for reverse in (False, True):
    suffix = "reverse" if reverse else "forward"
    types = ["uint16", "int16"]
    if reverse:
        types.reverse()
    rules = " ".join(
        f'[ a dlv:CellDataTypeRule; bddo:condition "true"; dlv:ruleCellDataType bddo:{kind} ]' for kind in types
    )
    source = (
        """
    ex:Root a bddo:Struct; bddo:hasField (ex:pixels).
    ex:pixels a bddo:Field; bddo:dataType bddo:bytes; bddo:size 2; hexplain:hasDataLayout ex:Layout.
    ex:Dim a dlv:Dimension; dlv:hasAxis dlv:axisX; dlv:dimensionSize 1.
    """
        + f"ex:Layout a dlv:DataLayout; dlv:hasConditionalCellDataType ({rules}); dlv:hasDimension (ex:Dim)."
    )
    pp(
        "layout-cell-type-first-" + suffix,
        "Overlapping cell-type rules select the first arm",
        "Both predicates hold. Reversing the rules changes 0xfffe from unsigned 65534 to signed -2.",
        ["req-dlv-conditional-1", "req-pm-data-layouts-1"],
        ["dlv#conditional", "data-layouts"],
        source,
        bytes.fromhex("fffe"),
        {"pixels": [-2 if reverse else 65534]},
        manifest={"cells": ["pixels"]},
        files={"round-trip-tree.json": canonical_json({"pixels": bytes.fromhex("fffe")})},
    )
    orders = ["ex:Y ex:X", "ex:X ex:Y"]
    if reverse:
        orders.reverse()
    rules = " ".join(
        f'[ a dlv:DimensionOrderRule; bddo:condition "true"; dlv:ruleDimensionOrder ({order}) ]' for order in orders
    )
    source = (
        """
    ex:Root a bddo:Struct; bddo:hasField (ex:pixels).
    ex:pixels a bddo:Field; bddo:dataType bddo:bytes; bddo:size 6; hexplain:hasDataLayout ex:Layout.
    ex:Y a dlv:Dimension; dlv:hasAxis dlv:axisY; dlv:dimensionSize 2; dlv:dimensionStride 3.
    ex:X a dlv:Dimension; dlv:hasAxis dlv:axisX; dlv:dimensionSize 3; dlv:dimensionStride 1.
    """
        + f"ex:Layout a dlv:DataLayout; dlv:cellDataType bddo:uint8; dlv:hasConditionalDimensionOrder ({rules})."
    )
    values = [0, 3, 1, 4, 2, 5] if reverse else list(range(6))
    pp(
        "layout-dimension-order-first-" + suffix,
        "Overlapping dimension-order rules select the first arm",
        "Fixed Y/X strides isolate selection order: X-major traversal reads 0,3,1,4,2,5; Y-major reads 0..5.",
        ["req-dlv-conditional-1", "req-pm-data-layouts-1"],
        ["dlv#conditional", "data-layouts"],
        source,
        bytes(range(6)),
        {"pixels": values},
        manifest={"cells": ["pixels"]},
        files={"round-trip-tree.json": canonical_json({"pixels": bytes(range(6))})},
    )
