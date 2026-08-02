# Design — HDL: A DSL for Authoring Hexplain Format Descriptions

**Status:** Draft for review · **Date:** 2026-07-26 · **Author:** Stephane Fellah
**Family:** Hexplain aspect-oriented ontology (pre-release, all modules v1.0)
**Working name:** **HDL — Hexplain Description Language** (rename freely)

## 1. Problem

A "Hexplain description of a format" is today authored as raw RDF/Turtle spanning
several vocabularies:

- **BDDO** — physical byte structure (`Struct`, `Field`, `DataType`, `Enumeration`,
  `Checksum`; sizing, offsets, repetition, conditional type dispatch, endianness).
- **HEL** — the expression language for dynamic sizing/presence/conditions
  (`instance` / `parent` / `root` / `self` / `stream` roots).
- **hexplain core** — the bytes→meaning mapping (`mapsToClass`, `mapsToProperty`,
  `hasConditionalMapping`, `valueExpression`, `isEncodedWith`).
- **DLV** — multi-dimensional array layout over a byte block (`DataLayout`, `Dimension`,
  axes, stride).
- **hx-bundle** — multi-file / multipart formats (`Asset`, `Part`, `BundleProfile`,
  `PartSpec`, binding kinds, facet lifting).

Authoring this by hand is verbose and error-prone: every field is a separate subject,
field order is carried by `rdf:List`, enums/checksums/layouts/part-specs are blank-node
soup, and HEL must be written in full (`instance.parent.ChunkLength`). The PNG chunk
example in the BDDO spec is representative — small format, large Turtle.

**Goal:** a concise, human-authored surface language that compiles to the *canonical*
BDDO/core/DLV/hx-bundle Turtle, so authors describe a format the way they think about it
while the RDF toolchain (SHACL, `owl:imports`, aspect composition) remains the source of
truth.

## 2. Locked decisions (from brainstorming)

1. **Role = authoring front-end → Turtle (one-way).** The DSL compiles to the canonical
   Turtle, which stays the validated source of truth. The DSL must be *expressively
   complete* (it can say everything the vocabs need, so no hand-editing of output is
   required), but the compiler is one-directional. Round-trip (Turtle→DSL) is out of scope.
2. **Two concrete syntaxes over one shared model.** A compact purpose-built text syntax
   (`.hx`) for authoring, and an isomorphic **YAML** projection (`.hx.yaml`) for tooling
   and interchange. Both parse to the same AST and lower through the same compiler.
3. **Full coverage.** BDDO (physical) + hexplain core (semantic mapping) + HEL
   expressions (first-class) + DLV (layout) + hx-bundle (multipart).
4. **Approach C — ergonomic core + explicit escape hatch.** High-level sugar for the
   common 90%; a `raw-turtle { … }` block and a `@prop <curie> <value>` fallback for the
   long tail. Completeness never depends on the sugar being exhaustive — important because
   the ontology is pre-release and the aspects keep moving.

## 3. Architecture

```
   .hx  (compact text)  ─┐
                         ├─►  parser ─►  AST  ─►  compiler ─►  <format>.ttl  ─► [SHACL]
   .hx.yaml (YAML)     ─┘        (shared model)     (lowering)   (canonical)   (existing shapes)
```

- **One abstract model (AST).** A tree: `Format → { Struct → Field*, Enum*, Layout*,
  Bundle*, Asset* }`, plus prefix declarations. Structs/fields carry optional semantic
  (`means`, `value`, `map`, `@encoded-with`) and layout (`layout`) annotations.
- **Two parsers, one AST.** The text and YAML surfaces are two projections of the same
  node set; every text clause has a YAML key and vice versa. text↔YAML conversion is
  therefore trivial and lossless.
- **One compiler.** Lowers the AST to Turtle: emits the `@prefix` block, `bddo:Struct`s
  with ordered `bddo:hasField ( … )` lists, blank nodes for enums/checksums/layouts/
  part-specs, and core/DLV/bundle triples. Optionally runs the existing SHACL shapes on
  the output and maps violations back to DSL source spans.

### 3.1 Units and boundaries

- **Lexer/Parser (text)** → AST. Depends on: the grammar (§13). Testable via
  source-string → AST fixtures.
- **YAML loader** → AST. Depends on: a YAML library + the same AST schema. Testable via
  YAML → AST fixtures; and via text-AST ≡ YAML-AST equivalence fixtures.
- **Name/IRI resolver** → annotated AST (every term has a full IRI; every bare expression
  identifier resolved). Depends on: prefix table + struct/field scope. Testable in
  isolation.
- **HEL synthesizer** → canonical HEL strings, and the `…FromField` vs `…FromExpression`
  decision. Depends on: the resolver. Testable via expression → HEL fixtures.
- **Turtle emitter** → `.ttl`. Depends on: the resolved AST + the ontology term set.
  Testable via AST → Turtle golden files.
- **Validator (DSL-level)** → diagnostics with source spans (§12). Independent of the
  emitter.

## 4. Naming & IRI conventions (all overridable)

- `format png` declares base namespace `https://hexplain.io/formats/png#` by default
  (matches the `png:` / `tiff:` convention in the existing BDDO examples). Override with
  `@namespace "…"`.
- `struct Chunk` → `png:Chunk` (a `bddo:Struct`).
- field `length` in `struct Chunk` → `png:Chunk.length` (dot-separated fragment; legal in
  a `#` namespace and shows containment). Override any single term's local name with
  `as`: `length as ChunkLength` → `png:ChunkLength`.
- `use ageom: <https://hexplain.io/ns/aspect/raster#>` style prefix decls let aspect terms
  be named as CURIEs (`ageom:width`) in `means` / `carries` / `@encoded-with` / `@prop`.
- A small set of prefixes is **predeclared**: `bddo:`, `dlv:`, `hexplain:` (core),
  `abnd:` (hx-bundle), `role:` (= `abnd:` PartRoleScheme), `xsd:`, `rdfs:`, `skos:`,
  `dcterms:`, `owl:`. Authors add the aspect prefixes they use.

## 5. Lexical model (text surface)

- **Comments:** `//` to end of line; `/* … */` block.
- **Whitespace-insensitive** within a declaration; a field declaration may wrap across
  lines (continuation is implied until the next `field-name :` or `}` — see §13).
- **Identifiers:** `[A-Za-z_][A-Za-z0-9_]*`. **CURIEs:** `prefix:local`.
- **Literals:** integers (`42`, `0x2A`, `0b1010`), floats (`1.5`), strings (`"…"` with
  standard escapes), hex byte strings (`0x89504E47`), booleans (`true`/`false`).
- **Annotations** start with `@` (`@endian`, `@at`, `@fixed`, …). **Keywords:** `format
  struct enum bundle asset use means value map switch when repeat until if from cell dim
  axis role required optional primary carries described-by as raw-turtle`.

## 6. Structural syntax (BDDO)

Field grammar: **`name : type clause*`**. Worked example — the PNG chunk (TLV with
conditional dispatch and a CRC), the exact case from the BDDO spec:

```
format png
  @namespace "https://hexplain.io/formats/png#"
  @endian big

struct Chunk {
  length : u32
  type   : ascii[4]
  data   : bytes[length]                 // lone sibling ⇒ bddo:sizeFromField
             switch type {               // ⇒ bddo:hasConditionalDataType
               "IHDR" => IHDR_ChunkData
               "PLTE" => PLTE_ChunkData
             }
  crc    : u32 @checksum crc32(type .. data)   // coversFromField .. coversToField
}
```

### 6.1 Types

| DSL type | BDDO |
|---|---|
| `u8 i8 u16 u16le u16be u32 u32be u64 … i16 … i64` | `bddo:uint8` / `int16be` / … individuals |
| `f32 f32le f32be f64 …` | `bddo:float32` / … |
| `bytes` | `bddo:bytes` (needs a size/terminator) |
| `str` | `bddo:string`, encoding `utf8` (default) |
| `ascii utf8 utf16le utf16be latin1` | `bddo:string` + `bddo:encoding <that>` |
| `anum` | `bddo:asciiInteger` — an integer written as text; needs a width, e.g. `anum[5]` |
| `adec` | `bddo:asciiDecimal` — a decimal written as text; needs a width |
| `bits[N]` | a field with `bddo:bitLength N` |
| `<StructName>` | nested/typed field (`bddo:dataType <that Struct>`) |

`[n]` after `bytes`/a string type sets the **byte size** (see §6.2).

### 6.2 Clauses

| Clause | Example | Compiles to |
|---|---|---|
| byte size | `bytes[length]` · `bytes[len-4]` · `bytes[..]` | `sizeFromField` · `sizeFromExpression` · `sizeToEndOfStream` |
| array count | `IFDEntry repeat numEntries` · `Item repeat until eof()` | `repeatCountFromField`/`…FromExpression` · `repeatUntil` |
| offset | `@at ifdOffset from stream-start` | `atOffset*` + `offsetBase` |
| presence | `if hasGamma == 1` | `isPresentIf` |
| fixed value | `@fixed 0x89504E470D0A1A0A` | `hasFixedValue` |
| enum | `u8 enum { 0=>Grayscale, 2=>RGB, 3=>Indexed }` · `enum flags {…}` · `enum ColorType` | inline/`ref` `Enumeration`+`EnumValue`, `enumIsFlags` |
| checksum | `@checksum crc32(type .. data)` · `@checksum crc32 covers(<expr>)` | inline `Checksum` (`coversFromField..coversToField` / `coversExpression`) |
| bit slice | `flags : bits[3]` | `bitLength 3` |
| terminator | `str @terminator 0x00` | `terminator` (`@trim-null` → `trimNull`) |
| overrides | `@endian little` · `@align 4` · `@bit-order lsb` · `@encoding latin1` | per-field props |
| numeric base | `anum[2] @base 16` | `numericBase` |
| conditional type | `switch <expr?> { <val|when expr> => <Struct> … }` | `hasConditionalDataType` (`DataTypeRule` list) |
| conditional endianness | `@endian switch { when ByteOrder == 0x4949 => little, when ByteOrder == 0x4D4D => big }` | `hasConditionalEndianness` (`EndiannessRule` list) |
| key (in a header) | `"samples" : anum means araster:width` | `key` |

`offsetBase` keywords: `stream-start stream-end parent-start current`. `@fixed` accepts a
hex byte string, an integer, or a string literal.

### 6.3 The field-form vs expression-form rule (normative)

For any size/offset/count clause: **when the expression is exactly one sibling field name,
emit the specific `…FromField` object property; otherwise emit the `…FromExpression`
datatype property with a synthesized HEL string.** This is deterministic, produces clean
Turtle for the common case (matching the hand-authored examples), and is identical across
the text and YAML surfaces. (DLV `dimensionSize` has no expression form: a bare integer →
`dimensionSize`, a sibling name → `dimensionSizeFromField`.)

### 6.4 Count-array / enum / offset example (the TIFF sketch)

```
format tiff  @namespace "https://hexplain.io/formats/tiff#"

struct IFD {
  numEntries : u16
  entries    : IFDEntry repeat numEntries      // repeatCountFromField
  nextIFD    : u32
}

field ColorType : u8 enum { 0=>Grayscale, 2=>RGB, 3=>Indexed }

field FirstIFD : IFD @at ifdOffset from stream-start   // atOffsetFromField + offsetBase
```
(`field` at top level declares a standalone `bddo:Field`, for fields shared across structs
or defined out of line, mirroring the standalone subjects in the TIFF sketch.)

### 6.5 Delimited text (`header` / `table`)

```
header EnviHeader @separator "=" @comment ";" @trim @ci {
  "samples" : anum means araster:width
  "lines"   : anum means araster:height
}

table PointCsv @separator "," @quote '"' @skip 1 {
  x : adec
  y : adec
  z : adec
}
```

`header` → `bddo:KeyValueHeader`, `table` → `bddo:DelimitedTable`. Annotations:
`@record-separator` (default LF) → `recordDelimiter`; `@separator` →
`keyValueSeparator` on a `header`, `fieldDelimiter` on a `table`; `@quote` →
`quoteChar`; `@escape` → `escapeChar`; `@comment` → `commentPrefix`; `@skip` →
`skipRecords`; `@trim` → `trimWhitespace`; `@ci` → `keyIsCaseInsensitive`. A
quoted field name in a `header` is its `bddo:key`.

## 7. Field references → HEL (first-class expressions)

Within any expression clause, identifiers resolve as:

- a **sibling field name** → canonical `instance.parent.<Name>` (so bare `length` in
  `bytes[length]` and bare `type` in `switch type` work directly);
- the roots `instance parent root self stream` and the functions `sizeof len count eof`
  pass through unchanged;
- dotted paths and subscripts pass through: `root.Directory[i].Entries[0].Tag`.

Operators, precedence, and value/coercion semantics are exactly HEL's — the DSL does not
introduce a new expression language, only nicer *references* into it.

Two payoffs: (1) authors never hand-write `instance.parent.…`; (2) the compiler validates
that every bare name resolves to a declared sibling, so typos become source-located
compile errors (raw Turtle cannot catch these). **Escape hatch:** a backtick-quoted string
passes a literal HEL expression straight through, e.g.
``bytes[`instance.parent.ChunkLength - (sizeof(instance.parent.Keyword) + 1)`]``.

## 8. Semantic mapping (hexplain core)

One keyword, `means`, carries the OWL 2 punning core already uses: on a **struct** it
emits `hexplain:mapsToClass`; on a **field**, `hexplain:mapsToProperty`.

```
struct IHDR_ChunkData means araster:RasterImage {
  width  : u32 means araster:width
  height : u32 means araster:height
  gamma  : u32 means acolor:gamma value gamma / 100000 @datatype xsd:double
  data   : bytes[..] @encoded-with aenc:deflate
}
```

| DSL | Turtle |
|---|---|
| `means <Class>` (struct) | `hexplain:mapsToClass <Class>` |
| `means <Property>` (field) | `hexplain:mapsToProperty <Property>` |
| `value <expr> @datatype <dt>` | `hexplain:valueExpression "…HEL…"` [+ `hexplain:valueDatatype <dt>`] |
| `@encoded-with <concept>` | `hexplain:isEncodedWith <concept>` |

A field's `value` expression may reference itself by its own name (`gamma` →
`instance.parent.gamma`), consistent with §7. **Conditional mapping**
(`hexplain:hasConditionalMapping`) mirrors `switch` using `map`:

```
text : str[..] map {
  when keyword == "Title"  => dcterms:title
  when keyword == "Author" => dcterms:creator value trim(text)
}
```
→ a `hexplain:MappingRule` list, each with `hexplain:condition` + `hexplain:semanticProperty`
(and optional per-arm `valueExpression`/`valueDatatype`).

## 9. Multi-dimensional layout (DLV)

A `layout` clause on a field emits `hexplain:hasDataLayout` → a `dlv:DataLayout`.
Dimensions are listed **slowest → fastest** (the `dlv:hasDimension` list order).

Plain contiguous (optionally strided) layout — no `chunk`, no `chunks`:

```
pixels : bytes[..] layout cell u8 {
  dim axis Y    size height  stride rowBytes   // dimensionSizeFromField + dimensionStride
  dim axis X    size width
  dim axis Band size 3                         // literal ⇒ dimensionSize
}
```

Chunked (tiled/blocked) layout — every `dim` MAY carry a `chunk` extent, and the
`chunks` clause says where the chunks are:

```
pixels : bytes[..] layout cell u8 {
  dim axis Y size height chunk tileLength
  dim axis X size width  chunk tileWidth
  chunks offsets TileOffsets lengths TileByteCounts base stream-start order row-major
}
```

- `layout cell <type> { … }` → `DataLayout` with `dlv:cellDataType <that bddo:DataType>`.
- `dim axis <A> size <int|sibling> [stride <int|expr>]` → a `dlv:Dimension` with
  `dlv:hasAxis dlv:axis<A>`, `dlv:dimensionSize`/`dlv:dimensionSizeFromField`, and optional
  `dlv:dimensionStride`.
- Axes: `X Y Z Band Time` → `dlv:axisX/axisY/axisZ/axisBand/axisTime`.
- `dim … chunk <int|sibling>` → `dlv:chunkSize` / `dlv:chunkSizeFromField`. At most one of
  the two per `dim`. In a chunked layout, a `dim` with no `chunk` is chunked at its full
  `size`, and `stride` addresses cells within a chunk.
- `chunks offsets <field> [lengths <field>] [base <offsetbase>] [order <order>]` →
  `dlv:chunkOffsetsFromField`, `dlv:chunkLengthsFromField`, `dlv:chunkOffsetBase`,
  `dlv:chunkOrder`. Orders: `row-major column-major morton hilbert`.
  Required whenever any `dim` declares a `chunk` extent.

## 10. hx-bundle (profiles & instances)

The primary bundle artifact for a *format* is the reusable **profile**. The shapefile
profile from the hx-bundle design becomes:

```
use ageom: <https://hexplain.io/ns/aspect/geometry#>
use atab:  <https://hexplain.io/ns/aspect/tabular#>
use asref: <https://hexplain.io/ns/aspect/spatialref#>
use aenc:  <https://hexplain.io/ns/aspect/encoding#>

bundle Shapefile @bound-by naming-convention {
  part ".shp" role GeometryCarrier   required primary carries ageom: described-by ShpMain
  part ".shx" role SpatialIndex      required
  part ".dbf" role AttributeTable    required          carries atab:
  part ".prj" role SpatialReference  optional          carries asref:
  part ".cpg" role CharacterEncoding optional          carries aenc:
}
```
→
```turtle
fmt:Shapefile a abnd:BundleProfile ;
  abnd:boundBy abnd:NamingConvention ;
  abnd:partSpec
    [ abnd:extension ".shp" ; abnd:partRole abnd:GeometryCarrier ; abnd:required true ;
      abnd:primary true ; abnd:carriesAspect ageom: ; abnd:describedBy fmt:ShpMain ] ,
    [ abnd:extension ".shx" ; abnd:partRole abnd:SpatialIndex ; abnd:required true ] ,
    [ abnd:extension ".dbf" ; abnd:partRole abnd:AttributeTable ; abnd:required true ;
      abnd:carriesAspect atab: ] ,
    [ abnd:extension ".prj" ; abnd:partRole abnd:SpatialReference ; abnd:required false ;
      abnd:carriesAspect asref: ] ,
    [ abnd:extension ".cpg" ; abnd:partRole abnd:CharacterEncoding ; abnd:required false ;
      abnd:carriesAspect aenc: ] .
```

- `@bound-by` keywords: `containment | naming-convention | manifest-reference |
  concatenation` → the four `abnd:BindingKind` individuals.
- `part "<ext>"` → a `PartSpec` blank node; `role X` → `abnd:partRole abnd:X` (or
  `role ns:Custom`); `required`/`optional` → `abnd:required` boolean; `primary` →
  `abnd:primary true`; `carries <prefix>` → `abnd:carriesAspect <that ontology IRI>`;
  `described-by <StructName>` → `abnd:describedBy <that bddo:Struct>`.
- **`carries` resolves to the *ontology* IRI, not the namespace IRI.** `abnd:carriesAspect`
  has range `owl:Ontology`, whose IRI omits the trailing `#` (e.g.
  `https://hexplain.io/ns/aspect/geometry`), whereas the `ageom:` prefix expands *with* it.
  The compiler strips a trailing `#`/`/` when lowering `carries ageom:`. (The hx-bundle
  design writes `abnd:carriesAspect ageom:` as shorthand; HDL emits the canonical ontology IRI.)

**Asset instances** use the same vocabulary and are supported but not the focus (a
recognizer normally emits them):

```
asset roads conforms Shapefile @bound-by naming-convention @stem "roads" @primary roads.shp {
  part roads.shp role GeometryCarrier  { ageom:geometryType = ageom:MultiLineString }
  part roads.prj role SpatialReference { asref:epsgCode = 4326 }
}
```
→ `ex:roads a abnd:Asset ; dcterms:conformsTo fmt:Shapefile ; abnd:boundBy … ; abnd:stem
"roads" ; abnd:primaryPart ex:roads.shp ; abnd:hasPart … .` with each `part` emitting an
`abnd:Part` carrying the given aspect facets. Facet lifting onto the Asset is handled by
the existing `abnd:LiftByCarriedAspectRule` at validation time — the DSL emits only the
part-level truth.

## 11. YAML projection (isomorphic mirror)

The YAML mirrors the AST one-to-one. Field lists are YAML **sequences** (order preserved →
`bddo:hasField` order). Every text clause has a YAML key. Same PNG chunk:

```yaml
format: png
namespace: https://hexplain.io/formats/png#
endian: big
structs:
  Chunk:
    fields:
      - { name: length, type: u32 }
      - { name: type,   type: ascii, size: 4 }
      - name: data
        type: bytes
        size: length                       # sibling ⇒ sizeFromField
        switch: { on: type, cases: { IHDR: IHDR_ChunkData, PLTE: PLTE_ChunkData } }
      - name: crc
        type: u32
        checksum: { algorithm: crc32, from: type, to: data }
```

Mapping of clause → YAML key: `size`, `repeat` (`{ count: … }` | `{ until: … }`), `at`
(`{ offset: …, from: … }`), `if`, `fixed`, `enum` (`{ flags: bool, values: { raw: symbol }}`),
`checksum`, `bits`, `terminator`, `trim-null`, `endian`/`align`/`bit-order`/`encoding`,
`switch` (`{ on, cases }` | `{ when: [ {cond, type} ] }`), `means`, `value`
(`{ expr, datatype }`), `encoded-with`, `map` (list of `{ when, property, value }`),
`layout` (`{ cell, dims: [ { axis, size, stride } ] }`), `prop` (`{ curie: value }`),
`raw-turtle` (string). Bundles under a top-level `bundles:` map; expressions are strings
and use the identical bare-name→HEL resolution.

`header`/`table` mirror under top-level `headers:` and `tables:` maps, keyed by name, with
`separator`, `record-separator`, `quote`, `escape`, `comment`, `skip`, `trim` (same
meaning as the `@`-annotations in §6.5) and an ordered `fields:` sequence. `headers:`
entries additionally take `ci` (`keyIsCaseInsensitive`); it has no meaning for a keyless
`table`. A `header` entry's `key` gives its `bddo:key` (a `table` entry has none — its
position is the key).

## 12. Escape hatch, compilation & validation

**Escape hatch (guarantees full coverage against the evolving ontology):**
- `raw-turtle { … literal turtle … }` at format/struct/field scope injects arbitrary
  triples; at field/struct scope the default subject is the enclosing term.
- `@prop <curie> <value>` sets any BDDO/core/dlv/bundle property the sugar doesn't know by
  name (value may be a literal, CURIE, or `` `…HEL…` `` string).

**Compile pipeline:** parse → resolve prefixes & mint IRIs → resolve expressions
(bare→HEL; pick `…FromField` vs `…FromExpression`) → emit Turtle (`@prefix` block, structs
with `bddo:hasField ( … )` lists, blank nodes for enums/checksums/layouts/part-specs,
core/DLV/bundle triples, injected raw triples) → optionally run the existing
BDDO/core/DLV/bundle **SHACL** on the output.

**DSL-level checks (compile-time, source-located — a strict superset value over
post-hoc SHACL):** unknown sibling reference in an expression; duplicate field name within
a struct; a `bytes`/`str` field with no size/terminator (front-runs
`VariableLengthFieldShape`); more than one sizing/offset/repeat mechanism on a field
(front-runs the BDDO SPARQL shapes); unknown role, prefix, or aspect; `size`/`[…]` on a
non-`bytes`/non-string type; `layout`/`means` targets that don't resolve to a known term.
Each diagnostic carries a `.hx`/`.hx.yaml` line/column.

**Output:** one `<format>.ttl` per format module. Round-trip is out of scope (§2.1).

## 13. Grammar sketch (text surface, informal EBNF)

```ebnf
document     = { use-decl | format-decl | struct-decl | field-decl | enum-decl
               | header-decl | table-decl | bundle-decl | asset-decl } ;
use-decl     = "use" PREFIX IRIREF ;
format-decl  = "format" IDENT { "@namespace" STRING | "@endian" endian
                              | "@bit-order" bitorder } ;
struct-decl  = "struct" IDENT [ "as" IDENT ] [ "means" CURIE ]
               { struct-annot } "{" { field-decl | raw-block | prop-clause } "}" ;
struct-annot = "@endian" endian | "@endian" "switch" "{" { endianarm } "}"
             | "@bit-order" bitorder | "@size" ( INT | ref | "`" HEL "`" ) ;
endianarm    = "when" expr "=>" endian ;
field-decl   = [ "field" ] IDENT [ "as" IDENT ] ":" type { clause } ;
type         = prim | "bytes" | strtype | "anum" | "adec" | "bits" "[" expr "]" | struct-ref ;
strtype      = "str" | "ascii" | "utf8" | "utf16le" | "utf16be" | "latin1" ;
clause       = "[" ( expr | ".." ) "]"                      (* byte size *)
             | "repeat" ( expr | "until" expr )
             | "@at" expr [ "from" offsetbase ]
             | "if" expr
             | "@fixed" ( HEXBYTES | INT | STRING )
             | "enum" [ "flags" ] ( IDENT | "{" enumpair { "," enumpair } "}" )
             | "@checksum" ALGO "(" ( ref ".." ref | "covers" "(" expr ")" ) ")"
             | "@terminator" HEXBYTES | "@trim-null"
             | "@endian" endian | "@align" INT | "@bit-order" bitorder
             | "@encoding" enc | "@base" INT
             | "switch" [ expr ] "{" { swarm } "}"
             | "means" CURIE
             | "value" expr [ "@datatype" CURIE ]
             | "@encoded-with" CURIE
             | "map" "{" { maparm } "}"
             | "layout" "cell" type "{" { dimdecl | chunkdecl } "}"
             | "@prop" CURIE value ;
swarm        = ( value | "when" expr ) "=>" struct-ref ;
maparm       = "when" expr "=>" CURIE [ "value" expr [ "@datatype" CURIE ] ] ;
dimdecl      = "dim" "axis" AXIS "size" ( INT | ref ) [ "stride" ( INT | expr ) ]
               [ "chunk" ( INT | ref ) ] ;
chunkdecl    = "chunks" "offsets" ref [ "lengths" ref ] [ "base" offsetbase ]
               [ "order" chunkorder ] ;
chunkorder   = "row-major" | "column-major" | "morton" | "hilbert" ;
enumpair     = value "=>" IDENT [ "(" STRING ")" ] ;
bundle-decl  = "bundle" IDENT [ "as" IDENT ] "@bound-by" binding "{" { partspec } "}" ;
partspec     = "part" STRING "role" role-ref [ "required" | "optional" ] [ "primary" ]
               [ "carries" PREFIX ] [ "described-by" struct-ref ] ;
asset-decl   = "asset" IDENT "conforms" IDENT { asset-annot } "{" { assetpart } "}" ;
header-decl  = "header" IDENT { delim-annot } "{" { entry-decl } "}" ;
table-decl   = "table" IDENT { delim-annot } "{" { field-decl } "}" ;
delim-annot  = "@separator" STRING | "@record-separator" STRING | "@quote" STRING
             | "@escape" STRING | "@comment" STRING | "@skip" INT | "@trim" | "@ci" ;
entry-decl   = STRING ":" type { clause } ;
expr         = (* HEL expression; bare identifiers = sibling refs, see §7 *) ;
```

## 14. Worked round-trip: PNG chunk (text → Turtle)

Input (§6) compiles to exactly the canonical form already in the BDDO spec:

```turtle
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix png:  <https://hexplain.io/formats/png#> .

png:Chunk a bddo:Struct ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( png:Chunk.length png:Chunk.type png:Chunk.data png:Chunk.crc ) .

png:Chunk.length a bddo:Field ; bddo:dataType bddo:uint32 .
png:Chunk.type   a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
png:Chunk.data a bddo:Field ;
    bddo:dataType bddo:bytes ;
    bddo:sizeFromField png:Chunk.length ;
    bddo:hasConditionalDataType (
        [ a bddo:DataTypeRule ; bddo:condition "instance.parent.type == 'IHDR'" ; bddo:ruleDataType png:IHDR_ChunkData ]
        [ a bddo:DataTypeRule ; bddo:condition "instance.parent.type == 'PLTE'" ; bddo:ruleDataType png:PLTE_ChunkData ]
    ) .
png:Chunk.crc a bddo:Field ;
    bddo:dataType bddo:uint32 ;
    bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ;
        bddo:coversFromField png:Chunk.type ; bddo:coversToField png:Chunk.data ] .
```

(The only cosmetic difference from the hand-authored example is deterministic field IRIs
`png:Chunk.length` vs the ad-hoc `png:ChunkLength`; `as` recovers the latter where desired.)

## 15. Out of scope / future (lazy-factoring)

- **Round-trip** Turtle→DSL (§2.1). Add a decompiler later if a consumer needs it.
- **A reference runtime parser** that *executes* a description against bytes — HDL
  describes; execution is a separate engine.
- **Editor tooling** (LSP, textmate grammar, schema for the YAML) — follows once the
  grammar stabilizes.
- **A profile library** (glTF, DASH, GeoTIFF bundles) — ships as authored `.hx` files, not
  language features.

## 16. Open questions for review

1. **Language name / extensions** — `HDL` + `.hx` / `.hx.yaml`? (HEL is taken by the
   expression language; avoid collision.)
2. **Field IRI separator** — `png:Chunk.length` (proposed) vs `png:Chunk_length` vs
   nested-path IRIs. Dots are legal and readable; confirm.
3. **`means` overload** — one keyword for both class- and property-mapping (relies on
   struct-vs-field context) vs two distinct keywords. Proposed: overload (parallels core's
   `mapsToClass`/`mapsToProperty`).
4. **Implementation language/host** for the compiler (not required for the design; affects
   the plan) — e.g. Python (rdflib + a PEG/Lark grammar) vs TypeScript.
