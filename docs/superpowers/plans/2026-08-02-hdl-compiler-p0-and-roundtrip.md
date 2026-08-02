# HDL Compiler P0 Support + NITF Round-Trip Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Teach the HDL compiler the P0 vocabulary, rename `nitf.hx` fields to match `nitf.ttl`, and add a CI gate that compiles the `.hx` and diffs it against the hand-written Turtle.

**Architecture:** Additive changes to the `hdl` Kotlin module in `hexplain-tools` (vocab constants → AST → lexer → parser → resolver → emitter, with tests at each layer), then a mechanical rename pass over `nitf.hx` in `hexplain.io`, then a round-trip test.

**Tech Stack:** Kotlin 2.2, Gradle (`./gradlew`), Apache Jena 6.1, JUnit 5. Python 3.11 + rdflib 7.1.1 for the cross-repo gate.

## Global Constraints

- **Two repositories.** Compiler work is in `d:\work\hexplain-tools`; `nitf.hx` and the gate live in `d:\work\hexplain.io`. Never `git add -A` in either — a concurrent effort owns `specification/profiles/nitf/*.ttl` and `docs/superpowers/plans/2026-08-01-nitf-p1-*`.
- **Additive only.** No existing HDL surface changes meaning. Every existing test in `hdl/src/test` must still pass.
- The normative vocabulary is `hexplain.io/specification/bddo/bddo.ttl` and `.../dlv/dlv.ttl`. IRIs in Kotlin constants MUST match those files exactly.
- Build/test: `./gradlew :hdl:test` (and `:core:test` when core changes). Run offline: `./gradlew --offline`.
- Compile a `.hx` with: `./gradlew -q --offline :hdl:run --args="<in.hx> -o <out.ttl>"`.

### Known limitation — do not try to solve it here

`nitf.hx` factors a reusable 16-field `SecurityMarking` struct with 6 nested references; `nitf.ttl` inlines ~96 security fields flat with segment-specific names (`FH_FSCLAS`, `IS_ISCLAS`, …). **Full isomorphism is unreachable until that is decided** ("Step 3", deliberately out of scope). Task 7's gate therefore asserts isomorphism *and reports the exact residual*, which must be the security block and nothing else. A residual containing anything else is a real failure.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `core/.../rdf/vocab/BDDO.kt` | BDDO constants for P0 terms | 1 |
| `core/.../rdf/vocab/DLV.kt` | DLV chunk constants + ChunkOrder individuals | 1 |
| `hdl/.../ast/Ast.kt` | New type variants and clause/decl nodes | 2–5 |
| `hdl/.../parse/Lexer.kt` | New keywords | 3–5 |
| `hdl/.../parse/Parser.kt` | New productions | 2–5 |
| `hdl/.../resolve/Resolver.kt` | Validation for the new forms | 2–5 |
| `hdl/.../emit/DataTypes.kt` | `anum`/`adec` in the type table | 2 |
| `hdl/.../emit/TurtleEmitter.kt` | Emission for each new form | 2–5 |
| `hdl/src/test/.../Emit*Test.kt` | Per-feature tests | 2–5 |
| `hexplain.io/specification/profiles/nitf/nitf.hx` | `as` renames + `raw-turtle` | 6 |
| `hexplain.io/tools/test_hx_roundtrip.py` | The round-trip gate | 7 |

---

### Task 1: Vocabulary constants for the P0 terms

**Files:** Modify `core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt`, `.../DLV.kt`; Test: `core/src/test/kotlin/io/hexplain/core/rdf/vocab/P0VocabTest.kt` (create).

**Interfaces produced** (every later task consumes these):
- `BDDO.asciiInteger`, `BDDO.asciiDecimal`, `BDDO.numericBase`
- `BDDO.EndiannessRule`, `BDDO.hasConditionalEndianness`, `BDDO.ruleEndianness`
- `BDDO.DelimitedRecords`, `BDDO.KeyValueHeader`, `BDDO.DelimitedTable`
- `BDDO.recordDelimiter`, `fieldDelimiter`, `keyValueSeparator`, `quoteChar`, `escapeChar`, `commentPrefix`, `skipRecords`, `trimWhitespace`, `key`, `keyIsCaseInsensitive`
- `DLV.chunkSize`, `chunkSizeFromField`, `chunkOffsetsFromField`, `chunkLengthsFromField`, `chunkOffsetBase`, `chunkOrder`, `ChunkOrder`, `rowMajor`, `columnMajor`, `morton`, `hilbert`

- [ ] **Step 1: Write the failing test** — `P0VocabTest.kt` asserts each constant's IRI string equals the one in the normative `.ttl`. Read the IRIs from `d:\work\hexplain.io\specification\bddo\bddo.ttl` and `.../dlv/dlv.ttl`; do not invent them. Namespaces: `https://hexplain.io/ns/bddo#`, `https://hexplain.io/ns/dlv#`.
- [ ] **Step 2:** `./gradlew --offline :core:test --tests '*P0VocabTest*'` → FAIL (unresolved references).
- [ ] **Step 3:** Add the constants, following the existing declaration style in each file exactly.
- [ ] **Step 4:** Re-run → PASS. Then `./gradlew --offline :core:test` → all pass.
- [ ] **Step 5:** Commit `feat(vocab): add BDDO/DLV constants for the P0 extensions`.

---

### Task 2: `anum` / `adec` types and the `@base` clause

This is the task that unblocks `nitf.hx`, which currently fails with 10 `unknown type 'anum'` errors.

**Files:** `hdl/.../ast/Ast.kt`, `hdl/.../parse/Parser.kt`, `hdl/.../emit/DataTypes.kt`, `hdl/.../emit/TurtleEmitter.kt`, `hdl/.../resolve/Resolver.kt`; Test: `hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitAsciiNumericTest.kt` (create).

**Interfaces:** produces `AsciiNumType(val decimal: Boolean) : TypeRef` and `BaseClause(val radix: Int) : Clause`.

- [ ] **Step 1: Write the failing test.** Compile this source and assert the emitted model:

```kotlin
val src = """
format t @namespace "https://ex.org/t#"
struct S {
  count : anum[5]
  ratio : adec[8]
  flags : anum[2] @base 16
  data  : bytes[count - 3]
}
"""
```
Assert: `t:S.count` has `bddo:dataType bddo:asciiInteger` and `bddo:size 5`; `t:S.ratio` has `bddo:asciiDecimal` and `bddo:size 8`; `t:S.flags` has `bddo:numericBase 16`; `t:S.data` has `bddo:sizeFromExpression` (not `sizeFromField`, since `count - 3` is an expression). Assert `t:S.count` has **no** `bddo:encoding` beyond what the datatype carries.

- [ ] **Step 2:** `./gradlew --offline :hdl:test --tests '*EmitAsciiNumericTest*'` → FAIL.
- [ ] **Step 3: Implement.**
  - `Ast.kt`: add `data class AsciiNumType(val decimal: Boolean) : TypeRef`.
  - `Parser.kt`: in the type parser, recognise `anum` → `AsciiNumType(false)`, `adec` → `AsciiNumType(true)`. They take a `[n]` size clause exactly like `StringType` does — find where `StringType` is accepted with a size and mirror it. Add `@base INT` to the clause parser as `BaseClause`.
  - `DataTypes.kt`: `is AsciiNumType -> if (type.decimal) BDDO.asciiDecimal else BDDO.asciiInteger`, and include `AsciiNumType` in `isStringOrBytes` so the `[n]` size clause is accepted (rename the helper to `takesSizeClause` if that reads better — update all callers).
  - `TurtleEmitter.kt`: emit `bddo:numericBase` for `BaseClause`.
  - `Resolver.kt`: error if `@base` is used on a non-`anum` field, or with a radix other than 8/10/16 — this mirrors `bddo:NumericBaseShape`.
- [ ] **Step 4:** Test passes; `./gradlew --offline :hdl:test` all pass.
- [ ] **Step 5: Verify against the real file.** `./gradlew -q --offline :hdl:run --args="D:/work/hexplain.io/specification/profiles/nitf/nitf.hx -o D:/tmp/t2.ttl"` must now emit Turtle with **zero** errors. Report the diagnostics.
- [ ] **Step 6:** Commit `feat(hdl): support anum/adec types and the @base clause`.

---

### Task 3: `@endian switch` — data-dependent byte order

**Files:** `Ast.kt`, `Lexer.kt`, `Parser.kt`, `TurtleEmitter.kt`; Test: `EmitConditionalEndianTest.kt` (create).

**Interfaces:** produces `EndianSwitch(val arms: List<EndianArm>)` as a struct annotation; `EndianArm(val cond: Expr, val endian: String)`.

- [ ] **Step 1: Write the failing test.**

```kotlin
val src = """
format t @namespace "https://ex.org/t#"
struct H @endian switch { when ByteOrder == 0x4949 => little
                          when ByteOrder == 0x4D4D => big } {
  ByteOrder : u16
}
"""
```
Assert `t:H` has `bddo:hasConditionalEndianness` pointing at an RDF list of two `bddo:EndiannessRule` nodes, in source order, the first with `bddo:ruleEndianness bddo:LittleEndian` and a `bddo:condition` whose HEL text references `ByteOrder`; and that `t:H` has **no** `bddo:endianness` (the two are mutually exclusive per `bddo:ConditionalEndiannessShape`).

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** Model the emission on the existing `switch` / `hasConditionalDataType` code path in `TurtleEmitter.kt` — it already builds an ordered `rdf:List` of rule nodes, so reuse that helper rather than writing a second list builder. Conditions go through `HelSynth` exactly as `switch` arms do.
- [ ] **Step 4:** Test passes; full `:hdl:test` passes.
- [ ] **Step 5:** Commit `feat(hdl): support @endian switch for self-declaring byte order`.

---

### Task 4: `chunk` and `chunks` — tiled/blocked layouts

**Files:** `Ast.kt`, `Lexer.kt`, `Parser.kt`, `TurtleEmitter.kt`, `Resolver.kt`; Test: `EmitChunkedLayoutTest.kt` (create).

**Interfaces:** extends `DimDecl` with `chunk: Expr?`; adds `ChunkSpec(offsets: String, lengths: String?, base: String?, order: String?)` to `LayoutClause`.

- [ ] **Step 1: Write the failing test.**

```kotlin
val src = """
format t @namespace "https://ex.org/t#"
struct S {
  w : u32
  h : u32
  tileOffsets : u32 repeat until eof()
  tileLengths : u32 repeat until eof()
  pixels : bytes[..] layout cell u8 {
    dim axis Y size h chunk 256
    dim axis X size w chunk 256
    chunks offsets tileOffsets lengths tileLengths base stream-start order row-major
  }
}
"""
```
Assert the `dlv:DataLayout` carries `dlv:chunkOffsetsFromField t:S.tileOffsets`, `dlv:chunkLengthsFromField t:S.tileLengths`, `dlv:chunkOffsetBase bddo:streamStart`, `dlv:chunkOrder dlv:rowMajor`, and that each `dlv:Dimension` carries `dlv:chunkSize 256`.

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** `chunk <int|sibling>` on a `dim` → `dlv:chunkSize` for a literal, `dlv:chunkSizeFromField` for a sibling name (the §6.3 field-form/expression-form rule already implemented for `size` — reuse that decision helper). Order keywords: `row-major column-major morton hilbert`. Base keywords reuse the existing `offsetbase` parser.
- [ ] **Step 4:** Add a **negative** resolver test: a `dim` with `chunk` but no `chunks offsets …` must be a source-located ERROR, mirroring `dlv:ChunkedLayoutShape`. Assert the diagnostic, not just the absence of output.
- [ ] **Step 5:** Full `:hdl:test` passes. Commit `feat(hdl): support chunked layout (chunk / chunks clauses)`.

---

### Task 5: `header` and `table` — delimited text records

The largest compiler task. Two new top-level declarations.

**Files:** `Ast.kt`, `Lexer.kt`, `Parser.kt`, `Resolver.kt`, `TurtleEmitter.kt`; Test: `EmitDelimitedTest.kt` (create).

**Interfaces:** produces `HeaderDecl` and `TableDecl` (both carrying `DelimOpts(separator, recordSeparator, quote, escape, comment, skip, trim, ci)` plus a field list); header entries carry a `key: String`.

- [ ] **Step 1: Write the failing test.**

```kotlin
val src = """
format t @namespace "https://ex.org/t#"
use ar: <https://hexplain.io/ns/aspect/raster#>
header EnviHeader @separator "=" @comment ";" @trim @ci {
  "samples" : anum means ar:width
  "lines"   : anum means ar:height
}
table PointCsv @separator "," @quote '"' @skip 1 {
  x : adec
  y : adec
}
"""
```
Assert `t:EnviHeader a bddo:KeyValueHeader` with `bddo:keyValueSeparator "3D"^^xsd:hexBinary`, `bddo:commentPrefix ";"`, `bddo:trimWhitespace true`, `bddo:keyIsCaseInsensitive true`; its two fields carry `bddo:key "samples"`/`"lines"` and the `hexplain:mapsToProperty` targets. Assert `t:PointCsv a bddo:DelimitedTable` with `bddo:fieldDelimiter "2C"^^xsd:hexBinary`, `bddo:quoteChar "22"^^xsd:hexBinary`, `bddo:skipRecords 1`, and **no** `bddo:keyValueSeparator`.

> Delimiter annotations are written as characters in HDL but MUST be emitted as `xsd:hexBinary` — `"="` → `"3D"`, `","` → `"2C"`, `'"'` → `"22"`. Encode as UTF-8 bytes, uppercase hex.

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** `header`/`table` are top-level declarations like `struct`; both lower to a `bddo:Struct` subclass with `bddo:hasField` in source order, so the existing struct emission path is the base — add the class IRI and the delimiter properties on top. Default `recordDelimiter` to `0A` when `@record-separator` is absent.
- [ ] **Step 4:** Negative resolver tests: a `header` without `@separator` is an ERROR; a `header` field without a quoted key is an ERROR; `@ci` on a `table` is an ERROR (meaningless without keys). These mirror `bddo:KeyValueHeaderShape` / `DelimitedTableShape`.
- [ ] **Step 5:** Full `:hdl:test` passes. Commit `feat(hdl): support header/table delimited-record declarations`.

---

### Task 6: Rename `nitf.hx` fields to match `nitf.ttl` (Steps 2 + 4)

**Files:** Modify `d:\work\hexplain.io\specification\profiles\nitf\nitf.hx`.

Two mechanical changes so the compiled output can be compared to the hand-written Turtle.

**Step 2 — `as` renames.** HDL mints `nitf:FileHeader.FHDR`; the TTL uses `nitf:FH_FHDR`. Add `as <PREFIX>_<NAME>` to every field, using this struct→prefix map (verify each against `nitf.ttl` before applying):

| Struct | Prefix | Struct | Prefix |
|---|---|---|---|
| `FileHeader` | `FH` | `TextSubheader` | `TS` |
| `ImageSubheader` | `IS` | `DESubheader` | `DES` |
| `ImageBand` | `IB` | `RESubheader` | `RES` |
| `GraphicSubheader` | `GS` | `TRE` | `TRE` |

**Do not rename `SecurityMarking`'s 16 fields** — they have no single TTL counterpart (that is the out-of-scope Step 3). Leave them and let Task 7's gate report them as the residual.

**Step 4 — `raw-turtle` for what HDL cannot declare.** Add a format-level `raw-turtle { … }` block carrying (a) the four custom `bddo:DataType` individuals `nitf:BCSA`, `nitf:BCSN`, `nitf:BCSNpos`, `nitf:ECSA` copied verbatim from `nitf.ttl`, and (b) the ontology header (`owl:Ontology`, `owl:imports`, `dcterms:created/creator/license`, `vann:preferredNamespacePrefix/Uri`) also copied verbatim.

- [ ] **Step 1:** Script the `as` renames (a regex pass per struct block is fine); print the count changed per struct and check the totals against `nitf.ttl`'s per-prefix field counts: FH 58, IS 56, IB 5, GS 32, TS 26, DES 24, RES 22, TRE 3.
- [ ] **Step 2:** Add the two `raw-turtle` blocks.
- [ ] **Step 3:** Compile: `./gradlew -q --offline :hdl:run --args="D:/work/hexplain.io/specification/profiles/nitf/nitf.hx -o D:/tmp/t6.ttl"` — zero errors.
- [ ] **Step 4:** Commit in `hexplain.io`, staging only `specification/profiles/nitf/nitf.hx`.

---

### Task 7: The round-trip gate (Step 5)

**Files:** Create `d:\work\hexplain.io\tools\test_hx_roundtrip.py`.

- [ ] **Step 1: Write the gate.** It must: locate the `hexplain-tools` checkout (env var `HEXPLAIN_TOOLS`, default `../hexplain-tools`); run the compiler via `./gradlew -q --offline :hdl:run`; parse both the emitted Turtle and `specification/profiles/nitf/nitf.ttl` with rdflib; compare with `to_isomorphic`. **SKIP (exit 0) with a clear message if the toolchain is absent** — mirror how `tools/test_shapes.py` skips when pyshacl is missing, so the rdflib-only suite stays green.
- [ ] **Step 2:** On mismatch, print the residual as `graph_diff` output grouped by subject, capped at 40 lines.
- [ ] **Step 3: Encode the known residual.** The gate PASSES when the only differing subjects are the `SecurityMarking` fields and the six segment security blocks. Express this as an explicit allow-list constant `KNOWN_RESIDUAL_STEP3` with a comment pointing at this plan's "Known limitation" section. **Any subject outside that list fails the gate.**
- [ ] **Step 4:** Run it. Report the actual residual. If it contains anything beyond the security block, that is a real finding — report it rather than widening the allow-list.
- [ ] **Step 5:** Commit `test(spec): add HDL round-trip gate for the NITF profile`.

---

## Self-Review

**Coverage.** Step 1 → Tasks 1–5 (vocab, then one task per surface). Step 2 → Task 6. Step 4 → Task 6. Step 5 → Task 7. Step 3 is explicitly out of scope and is the documented residual.

**Ordering.** Task 1 must precede 2–5 (they consume its constants). Task 2 must precede 6 (`nitf.hx` uses `anum`). Tasks 3–5 are independent of each other and of 6, but 7 depends on 2 and 6.

**Type consistency.** `AsciiNumType` is introduced in Task 2 and reused in Task 5's fixtures. `DimDecl.chunk` extends the existing node rather than adding a parallel one. The `rdf:List` helper used in Task 3 is the one already used for `hasConditionalDataType`.

**Risk.** Task 5 is the largest and least constrained. If it overruns, Tasks 6–7 still deliver value without it — `header`/`table` are not used by `nitf.hx`. Sequence it last among the compiler tasks for that reason.
