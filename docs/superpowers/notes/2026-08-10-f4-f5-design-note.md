# F4 and F5: Where Description Ends

**Date:** 2026-08-10 · **Status:** Design note, no implementation
**Input:** [2026-08-09-gdal-coverage-next-features.md](2026-08-09-gdal-coverage-next-features.md) §F4, §F5

F4 (self-describing record schemas, 8 drivers) and F5 (keyed container traversal, 7 drivers)
are the two remaining features that push on Hexplain's central constraint: **HDL describes, it
does not execute.** This note asks whether that constraint actually excludes them, and
concludes that most of what they need is not execution at all — but that the part which is
should be handled by one mechanism rather than two, and that mechanism already exists in
embryo.

---

## 1. What the constraint is actually for

"Describe, don't execute" is not asceticism. It buys three things:

- **A description is checkable by reading it.** SHACL can say a checksum's coverage is
  self-consistent; it cannot say a decompressor terminates.
- **A description outlives its processors.** Entropy coders are identified, never implemented,
  so a 2026 description of a JPEG is still true when everyone's Huffman code has been rewritten.
- **Nobody has to implement HDL twice.** The moment a description can express a loop with
  state, every conforming processor must agree on evaluation order, termination and failure.

Anything that keeps those three properties is inside the line, whatever it looks like.

## 2. F4 is three problems, not one

The roadmap treated "self-describing record schemas" as one bucket. It is three, and they sit
in different places relative to the line.

### (a) Dynamic offsets, static field set — Arrow, FlatGeobuf, MVT · 3 drivers

A flatbuffer vtable gives the byte offset of each field within a table; protobuf gives a field
number and wire type per field, in any order. **The field set is known at authoring time** —
it comes from the `.fbs` or `.proto`, which the profile author has. What is not known is where
each field sits in a given record.

This is pointer-chasing, which BDDO already does with `bddo:atOffsetFromField` and
`bddo:atOffsetFromExpression`. The gap is narrow: those resolve a single pointer, and a vtable
is a **table indexed by field identity**. DLV has the positional analogue already —
`dlv:chunkOffsetsFromField` is a table of offsets indexed by chunk number.

**Verdict: inside the line, and small.** It needs a keyed-lookup form — read the offset for
*this* field from *that* table, keyed by a number the description states. No loop, no state,
no search; a table lookup at a computed index, which `atOffsetFromExpression` can nearly
express today. Roughly the size of the chunked-layout work.

### (b) Skip-unknown — MVT, and protobuf generally · shares the 3 above

Protobuf requires a reader to skip fields it does not recognise, using the wire type to
determine the length. A description that enumerates known fields and stops is wrong on any
file written by a newer producer.

**Verdict: inside the line, and bounded.** This is a conditional length rule — given a wire
type, the field is 1 varint, 8 bytes, 4 bytes, or a length prefix followed by that many bytes.
`bddo:hasConditionalDataType` already dispatches on a discriminator. What is missing is an
explicit "and anything else is skipped, with its length determined thus" arm, which is a
default case rather than new machinery.

### (c) Schema in the file — HFA, Parquet, CAD/DWG, PGeo · 5 drivers

Erdas `.img` carries a dictionary string that defines its record layouts; Parquet carries a
Thrift-encoded schema in its footer. **The field set does not exist until the file is open.**
A description cannot enumerate what it does not know.

**Verdict: this one genuinely crosses the line — but not where it looks.** The temptation is
to make HDL able to *interpret* the dictionary, which would mean embedding a second description
language inside the first. That is the move to refuse.

The alternative is to describe **where the schema is and what language it is in**, and hand
off. See §4.

## 3. F5 is one problem, and it is the same one

Reaching a tile in MBTiles means: parse the SQLite header, find `sqlite_master`'s root page,
descend its B-tree to the row describing the `tiles` table, take that table's root page,
descend *its* B-tree by rowid, and read a BLOB that may be spilled across overflow pages.

Every step is documented and none is expressible. Descent is a loop with state and a
comparison at each level — precisely what §1 says must not enter the language. Writing a
`bddo:BTreeDescent` vocabulary would be writing a query engine in RDF, and every processor
would then have to agree on it.

But notice what the description actually wants to say. Not *how to descend* — that is SQLite's
business and is already specified elsewhere — but:

> the payload is the `tile_data` column of the `tiles` row whose `zoom_level`, `tile_column`
> and `tile_row` are these

That is a **statement of location in a language someone else defines**. It is not an algorithm
any more than `hexplain:isEncodedWith menc:Deflate` is an algorithm.

## 4. The unifying move: delegated access

F4(c) and F5 want the same thing, and Hexplain already does it once — for compression.

`hexplain:isEncodedWith` says: *these bytes are deflated; a processor that knows deflate can
produce the real bytes, which the rest of this description then describes.* HDL never says how
to inflate. The codec is a **named concept from a register**, so two processors agree by
naming the same thing rather than by reimplementing it, and a processor that does not know the
codec fails honestly instead of mis-parsing.

Generalise the noun and it covers both features:

> **Delegated access.** A byte run is identified as an instance of a named ACCESS METHOD, with
> named parameters. A processor that knows the method returns a byte run; the existing
> vocabulary describes that byte run as it would any other.

For F5, the method is SQLite and the parameters are a table, a column and a key. For F4(c),
the method is a schema language and the parameter is where the schema sits:

```
# F5 -- shape only, not proposed syntax
mbtiles:TileBlob a bddo:Field ;
    hexplain:accessedBy [ hexplain:accessMethod ram:sqlite3 ;
                          hexplain:accessParameter [ name "table"  ; value "tiles" ] ,
                                                   [ name "column" ; value "tile_data" ] ] .

# F4(c)
hfa:Node a bddo:Struct ;
    bddo:layoutFromField hfa:DictionaryString ;
    bddo:layoutLanguage ram:erdasHfaDictionary .
```

**Why this stays inside the line.** It preserves all three properties of §1. A description
remains checkable by reading — SHACL can verify the method is a registered concept and the
required parameters are present, exactly as `hexplain:EncodingStep` is checked today. It
outlives its processors, because it names SQLite rather than embedding a B-tree. And nobody
implements HDL twice: the delegated work is done by an implementation that already exists and
is already specified by someone else.

It also composes correctly. Delegated access yields *bytes*, which is the same thing
`isEncodedWith` yields, so it slots into the pipeline at the same point and everything
downstream — layouts, mappings, checksums — works unchanged.

**What it costs, stated plainly.**

- **A description becomes conditionally readable.** Today a processor either understands a
  description or does not, on syntax alone. With delegation it may understand the description
  and still be unable to read the file. That is already true of `isEncodedWith`, so it is a
  widening of an accepted cost rather than a new one — but the widening is real, because
  compression is universal infrastructure and SQLite is not.
- **The register becomes load-bearing.** An access method with no agreed parameter names is
  useless. The register must fix the parameter vocabulary per method, which is more governance
  than a codec register needs.
- **It is an obvious dumping ground.** Anything hard becomes a new access method. The
  discipline has to be a stated bar: a method is admissible only when it is (i) specified by a
  public document not controlled by this project, and (ii) already implemented independently
  more than once. SQLite and Thrift pass; a bespoke per-format quirk does not.

## 5. Recommendation

**Do F4(a) and F4(b) as ordinary vocabulary work.** Keyed offset lookup and a wire-type skip
rule are inside the line by any reading, and they unlock Arrow, FlatGeobuf and MVT — 3 drivers
— with no architectural question attached. These are the cheap half of F4 and should not wait
for the expensive half.

**Prototype delegated access on F5 before committing to it**, and specifically on MBTiles
rather than GPKG. MBTiles is the smallest honest test: one table, one blob column, an integer
key, and no geometry semantics to argue about. If the shape survives that, GPKG follows for
free and F4(c) reuses it. If it does not, 7 drivers stay at container level, which is where
they are now — the status quo is not a failure state.

**Do not do F4(c) first.** A schema language is a harder delegation than a query: the returned
thing is a *description*, not bytes, so it re-enters compilation rather than the byte pipeline.
That is a second mechanism wearing the same name, and it should be designed only once the
simpler one has proven itself.

**Expected coverage.** F4(a)+(b) takes 139 → 142. Delegated access on F5 takes it to 149; F4(c)
would reach 154. The residue is then 42: the entropy-coded ◐ tier (34), the bespoke line
grammars (6), and `GXF`/`VDV` (2) — all out of scope by design rather than by omission.

## 6. The option worth keeping open

None of this is urgent. At 139 of 196, the drivers behind F4 and F5 are 15 of the remaining 57,
and every one of them is *already* describable at container level — framing, integrity,
provenance and metadata all work today; only the payload is opaque. That is precisely the level
the ◐ tier was defined for, and it is genuinely useful.

The honest question is not "can we reach 154" but "is a description that cannot be read without
SQLite still a Hexplain description". I lean yes, on the `isEncodedWith` precedent. But the
precedent is being stretched, and it is worth deciding that deliberately rather than discovering
it later in a register full of access methods nobody agreed to.
