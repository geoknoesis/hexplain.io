# Changelog

Changes to the Hexplain specification family. Version numbers are per module
(`owl:versionInfo` / `owl:versionIRI`); the family has no single version. Local release
snapshots are recorded under `releases/`.

## Unreleased (changes since snapshot 2026-09-24.2)

### Language and processing rules settled for the conformance suite (round 4)

Processing Model:

- Optional features have normative feature tokens (`tree-documents`, `grouped-headers`,
  `nested-profiles`, `chunked-cell-access`, `chunk-order-other`, `hel-ext-text`,
  `hel-ext-temporal`, `hel-ext-quantifier`, `hel-ext-geometry`, `hel-ext-register`,
  `codecs-beyond-minimum`); each HEL extension group is its own feature. Claims, suite
  manifests and unsupported-feature reports name features by token.
- Fixed values (`req-pm-parsefield-2`, reworded): only an `xsd:hexBinary` literal denotes
  bytes. Any other string literal denotes characters: on a bytes field it is compared as its
  UTF-8 encoding (`"CAFE"` is `43 41 46 45`, not `CA FE`), on a string field by code points in
  any encoding. A numeric literal is compared by value at the field's width, a float32 field
  against the literal rounded to float32.
- Conflicting forms the text does not order are a Description error, raised at load: a repeat
  count together with a repeat-until condition, two offset forms, a dispatch table together
  with conditional type rules, and more than one value of a functional property. The
  precedence of the four size forms is unchanged.
- `streamEnd` counts back from |S|, the length of the current stream; a decoded sub-stream is
  a stream, a bounded region is not.
- New section Recovery in a Lenient Mode: a failed pointer read does not move the cursor; a
  counted sequence of known-width elements skips count × width (bounded by the region); any
  other read failure abandons everything up to the nearest known end (a sized field, a bounded
  sequence, a decoded block or a sized struct), recording one error and no follow-up error.
  A failed check on a value read in full is recorded and parsing continues. Fixed strings on
  string fields are compared after `bddo:trimNull`.
- The steps of ParseStruct and ParseField, the bit-cursor, size-resolution, terminator,
  byte-order, text-number, record, key/value, table and emission rules are now stated as
  requirements, so the conformance suite can cite each rule by identifier.
- A key/value header field with no `bddo:key` is located by its simple key; a reference to an
  external XML entity is a Validation error whether or not the declaration is read; a carried
  (unparsed) bundle part is still minted as `<part>#root`; `hexplain:mapsToObjectProperty`
  emits the struct instance's IRI or the matched enumeration symbol's IRI.

HEL:

- A Float is never an Integer where a context requires one, even `2.0`
  (`req-hel-conformance-6`, reworded; any other result type stays an error).
- String literals may hold any control character literally (the `SChar` production now agrees
  with the prose and the lexer); the new informative Canonical Form section defines expression
  equivalence (the suite compares HEL-bearing literals by it) and the spelling the reference
  serializer writes, which escapes controls other than tab, LF and CR as `\xHH`.
- Expression depth: a left-associative chain of one binary operator counts as one n-ary node
  for the nesting-depth limit.
- `and`/`or` evaluating both operands, and `evaluationInstant()` never reading the wall clock,
  are stated as requirements; a call to a function outside the core set and every group is a
  load-time Type / HEL error.

HDL:

- Forward references are compile-time errors wherever statically determinable: bare names in
  every expression role, `root.` paths the compiler can follow, and `parent.` paths from a
  struct with a single container (`req-hdl-conformance-section-5`, reworded: it claimed every
  forward reference was determinable).
- New ERRORs: a bracket size on a fixed-width numeric type (`u32[4]`); a second clause of one
  kind (size, count, offset, fixed, endian, type selection); `derive` with `repeat`;
  `@pipeline` with `@encoded-with`; duplicate struct declarations; negative literal sizes,
  counts and offsets; `stride 0`; float literals in size, count and offset positions;
  non-ASCII digits; lone surrogate escapes; duplicate YAML keys and null YAML list entries.
- Literal positions: `@prop` takes an IRI, CURIE or literal but never a bare name; a bare-name
  switch key is a string key; `@fixed` rejects names, CURIEs and Booleans.
- `root.<k>` is accepted for any identifier when a struct declares `@root-key`; a
  `repeat until` bare name falls back from the element to the containing struct (`parent.x`),
  an ambiguous name being an ERROR; a quoted header key is reachable only through its alias,
  and an unquoted header field is located by its own name; a key step on a scalar, or on a
  repeated field without a subscript (`es.size`), is an ERROR.
- Literal ranges: a size or struct `@size` below 1, a count or offset below 0, a stride below 1
  and a float in any of these positions are ERRORs; a `bytes` or string field of a binary
  struct with neither size nor terminator is an ERROR; `@fixed` rejects a string on a numeric
  field and an integer on a bytes field; YAML `hdl:` is spelt exactly `1.0` or `"1.0"`.
- YAML: scalars follow YAML's own quoting and escaping; the layout keys (`cell dims order
  chunks cell-bits packing`) belong to the `layout:` mapping, not to the field.
- Import resolution documents the reference CLI's `--vocab`, `--no-validate` and default SHACL
  validation.

### Processor conformance suite, round 4

- 450 cases (272 Physical Parser, 16 Semantic Emitter, 13 Bundle Processor, 118 HDL Compiler,
  31 Conformance Evaluator), up from 320; nine more Conformance Evaluator cases, whose
  `expected-report.ttl` states the run in the conf run terms (`conf:verdict`, `conf:finding`,
  `conf:truncated`, `conf:versionScopingApplied`, `conf:fileVersion`, `conf:failOn`,
  `conf:profile`, `conf:input`), are generated once the conf vocabulary declares those terms.
- New cases cover the rules above and the round-3 regressions: string fixed values on bytes and
  UTF-16 fields, float32 fixed values, conflicting forms, `streamEnd` in a sub-stream and in a
  region, lenient recovery after pointer, counted-sequence and other read failures, the
  Dispatch category, integral Float results, control characters in HEL strings, n-ary
  expression depth, the geometry and register groups, XML external entities and DTDs, a
  base-less emission, a processor's claims statement, invalid conformance profiles, exact
  version matching (`"2.0"` is not `"2.00"`), and every new HDL ERROR, with a YAML mirror of each
  successful HDL compilation.
- Manifests name optional features by token and may withdraw claims (`claims.withdraw`);
  every case cites at least one specific requirement; `ce-parse-attribution` records exactly one
  error whatever a lenient parse does next; `hc-import-outside-root` imports a module inside its
  own case directory that lies outside the import root.
- Comparison: HDL literal datatypes match exactly, the `owl:Ontology` header is compared only
  when a case asks, HEL-bearing literals compare by expression equivalence, and an HDL error
  line is compared only when the case states it.
- `tools/conformance/compare.py` (with a HEL parser and canonical serializer in `hel.py`) is a
  standalone comparator for any implementation's outputs, and `tools/conformance/run_suite.py`
  runs an implementation's command lines through the suite; the gate
  `test_conformance_comparator` tests every comparison rule. The coverage table leaves out
  blanket requirements and description-audience requirements, and reports processor MUST
  coverage per conformance class.

### Processor conformance suite

`specification/conformance/` is an executable, portable conformance suite for the five
conformance classes of the Processing Model: 320 cases (239 Physical Parser, 15 Semantic
Emitter, 13 Bundle Processor, 36 HDL Compiler, 17 Conformance Evaluator), each a description,
an input and the parsed tree, graph, error category, compiled graph or conformance report the
specification requires. The expected outputs are read off the specification text. The cases
are generated from `tools/conformance/` (binary inputs built in Python, so every byte is
reviewable); `specification/conformance/index.html` defines the case format and the canonical
forms outputs are compared in, and reports requirement coverage. The `pp-hel-` cases carry the
parse-context HEL behaviour the vector format cannot express (undefined names after the first
path step, forward references, Bytes values, uint64 values above 2^63-1, sizeof, stream
metadata, the asset root outside an asset); the header of `validation/test/hel-vectors.tsv`
now points to them.

Every RFC 2119 requirement sentence of the Processing Model, HEL, HDL and the conformance
sections of conf and req now carries a stable anchor (`req-pm-…`, `req-hel-…`, `req-hdl-…`,
`req-ce-conf-…`, `req-ce-req-…`), and the items of a list or table introduced by a
"…MUST:" sentence get their own. `specification/conformance/requirements.json` registers each
with a hash of its text. New gates: `test_requirement_ids` (every requirement anchored once,
registry current, an identifier that changes text or disappears is named here) and
`test_conformance_suite` (suite generated, manifests complete, every cited requirement and
section exists, exactly one expected artifact per case, coverage page current).

### Processing Model clarifications found while deriving the cases

- `bddo:syncOnMarker`: the cursor advances *past* the marker; the marker is consumed and the
  struct begins after it (the text said "to the next occurrence", which read either way).
- Bit fields: every bit keeps its significance; under `bddo:LSBFirst` the first bit taken is
  the least significant bit of the value (the text said values are assembled
  most-significant-bit first, which contradicted every LSB-first format it exists for).
- Checksums: coverage by `bddo:coversFromExpression` / `bddo:coversToExpression` (start
  inclusive, end exclusive) is now stated beside the field form and the deprecated
  `bddo:coversExpression`.
- Error table: a malformed HEL expression, and the `asset` root or `partExtension()` in a part
  parsed on its own, are Type / HEL errors, even when found as the description is loaded
  (`req-pm-errors-6`, and the new `req-pm-errors-15`); the Unsupported feature row no longer
  gives the asset root as its example, which contradicted Multi-part Assets
  (`req-pm-errors-10`).
- A negative repeat count is a bounds error, as a negative size is (`req-pm-size-resolution-3`).
- Semantic triple emission: a repeated field emits one triple per element; a processor MAY
  annotate each minted resource with `hexplain:byteOffset` / `hexplain:byteLength`, typed
  `xsd:nonNegativeInteger`, and the graph holds nothing else beyond the mapping.

## Snapshot 2026-09-24.2 (changes since snapshot 2026-09-24.1)

### Module versions

Every module whose canonical Turtle changed after snapshot 2026-09-24.1 has a new version IRI,
an `owl:priorVersion` naming the version that snapshot froze, and `dcterms:modified 2026-09-24`.

| Module | Was | Now |
|---|---|---|
| aspect/bundle | 1.3 | 1.4 |
| aspect/provenance | 1.1 | 1.2 |
| aspect/spatialref | 1.2 working draft | 1.3 working draft |
| bddo | 1.1 | 1.2 |
| conf | 1.1 | 1.2 |
| conf/shapes (new ontology document) | — | 1.2 |
| dfv (docfont) | 1.1 | 1.2 |
| fn | 0.1 | 0.2 |
| hexplain (core) | 1.1 | 1.2 |
| idv (image) | 1.1 | 1.2 |
| register/checksum | 1.1 | 1.2 |
| register/geometry-type | 1.1 | 1.2 |
| register/media-encoding | 1.0 | 1.1 |
| register/us-nato-security | 1.1 | 1.2 |
| req | 1.1 | 1.2 |
| req/shapes (new ontology document) | — | 1.2 |

`conf/shapes.ttl` and `req/shapes.ttl` are now ontology documents of their own
(`<https://hexplain.io/ns/conf/shapes>`, `<https://hexplain.io/ns/req/shapes>`), importing the
vocabulary they validate; their terms stay in the `conf:` and `req:` namespaces. `conf.ttl` now
imports only `req`; `conf/shapes.ttl` imports `core`.

### Validation compatibility (stricter shapes)

- **Class-only activation closed.** Shapes that fired only on `rdf:type` now also fire on the
  properties their class alone uses: `conf:ConstraintShape` (subjects of `conf:assertion`,
  `conf:scope`, `conf:message`; objects of `conf:findingConstraint`), `conf:FindingShape`,
  `req:RequirementShape`, `req:RequirementIdentityShape`, `abnd:PartSpecShape` (objects of
  `abnd:partSpec`), `abnd:AssetShape`/`abnd:PartShape` (via `abnd:primaryPart`, `abnd:boundBy`),
  `bddo:DispatchArmShape`, `bddo:ChecksumShape`, `bddo:NamespaceBindingShape`,
  `bddo:NodePathShape`, `hexplain:EncodingStepShape`, `hexplain:CodecParameterShape`. An untyped
  node carrying those properties used to validate unchecked.
- **conf findings.** `conf:findingKind` admits `conf:Parse`. A `conf:Violation` or
  `conf:RuleError` finding must name its constraint and at least one requirement, and may cite
  only requirements its constraint cites; a Parse finding names no constraint, states
  `conf:errorCategory`, and may cite none. A parse-recovery finding written as a constraint-less
  `conf:Violation` (valid before) now fails: write it as `conf:Parse`.
- **req identity.** The (fromStandard, requirementId) uniqueness check trims both values and
  ignores the standard's case; `req:fromStandard` and `req:statement` must be non-empty.
- **bundle profiles.** A part spec needs an `abnd:extension` or an `abnd:pathPattern`; an
  extension starts with a dot; a pattern may not contain a `..` segment or start with `/`; a
  profile has at most one primary spec and no two specs described by structs with one local name.
- **bddo.** A node may not be two of Struct, Field and DataType (`bddo:DisjointKindsShape`); a
  tree document's `bddo:nodePath` must follow JSON Pointer or the XML path syntax, every prefix it
  uses must be bound, once; `bddo:namespaceIRI` must be absolute.
- **Looser:** `asref:skewX`/`asref:skewY` are optional (absent means zero); `dcterms:creator` on a
  `dfv:Document` may be an agent IRI or blank node and may repeat.

### Additions

- conf: `conf:Run`, `conf:outcome`, `conf:outcomeRequirement`, `conf:outcomeValue`,
  `conf:NotReached`, `conf:ParseAttribution`, `conf:errorCategory`, `conf:Parse`;
  `conf:severity` is also stated on findings.
- core: `hexplain:RegisterStatus` (`hexplain:statusValid`, `hexplain:statusDeprecated`,
  `hexplain:statusSuperseded`), `hexplain:status`, `hexplain:RegisterStatusShape`,
  `hexplain:correspondsTo`.
- bundle: `abnd:liftsProperty` (explicit facet lifting), `abnd:BundleProfileShape`.
- bddo: `bddo:DisjointKindsShape`, `bddo:TreePrefixBindingShape`.
- us-nato-security: `usnato:NatoClassificationLevelScheme` with its five levels,
  `usnato:UsClassificationLevelOrder`, `usnato:NatoClassificationLevelOrder`, `usnato:Cui`.

### Deprecations (IRIs kept, `owl:deprecated true`)

- us-nato-security: `usnato:Restricted` (→ `usnato:NatoRestricted`), `usnato:Fouo`
  (→ `usnato:Cui`), `usnato:ClassificationLevelOrder` (→ the US and NATO orders), each with a
  `hexplain:status`, a history note and `dcterms:isReplacedBy`. The register cites the current
  authorities (EO 13526, DoD Manual 5200.01, 32 CFR Part 2002; FIPS 10-4 withdrawn).
- idv: `img:colorType`, `img:compressionMethod`, `img:filterMethod`, `img:interlaceMethod`
  (PNG wire codes; they belong in a PNG profile).
- dfv: `dfv:Object`, `dfv:Stream`, `dfv:Trailer`, `dfv:CrossReferenceTable` (PDF structures).

### Corrected mappings and semantics

- The checksum register links its concepts to bddo algorithms with `hexplain:correspondsTo`
  (was `skos:exactMatch` to OWL individuals) and imports core; H.264's `skos:exactMatch` to an
  ISO web page is `rdfs:seeAlso`; geometry types `skos:closeMatch` the Simple Features classes
  (`sf:Point`, ...), not the non-existent `geosparql:Point`.
- Scheme-level `owl:versionInfo "1.0"` inside the security register is removed.
- The normalized affine is corner-based; `asref:pixelRegistration` never shifts it, and
  `hxf:column`/`hxf:row` no longer add half a pixel. The affine functions and `hxf:calibrate` are
  unbound for a multi-valued or uncastable coefficient; `hxf:isNoData` compares in the band's
  declared type; `hxf:stat` excludes no-data and NaN cells.
- provenance: `aprov:Platform rdfs:subClassOf sosa:Platform`; the other PROV/SOSA links stay
  `rdfs:seeAlso`.

### Specification text

- Processing Model: a fifth conformance class, Conformance Evaluator, and its section; refusal
  limited to unclaimed classes and a closed list of optional features; the reference
  implementation's capability statement, `specification/reference-engine-claims.json`; Delta
  parameters; codec error categories; strict text-container decoding and row-count checks;
  Description errors for packed non-integer cells, malformed fixed values and repeat-until over
  a text container; configurable limits with depth counted from the root; the ResourceLimit
  marker.
- HEL: one escape set shared with HDL (`\\ \' \" \n \t \r \0 \xHH \uHHHH`); ASCII lexing;
  `1e999` is a syntax error; strict `datetime`; no `.size`; repeat-until bindings over structs;
  the `parent` alias in dispatch conditions is deprecated.
- HDL: the grammar of the finished compiler; `asset` is reserved; forward references are
  compile-time errors; Delta is part of the minimum codec set.
- conf and req pages have RFC 2119 conformance sections; module pages take their lead from the
  ontology's comment.

### Tooling

- New gates: `test_register_lifecycle`, `test_line_endings`, `test_reference_claims`,
  `test_controlled_values`, `test_strict_profile`, `test_conformance_competency`.
- `test_shape_activation` also checks class-targeted shapes; `test_html_sync` checks page leads;
  fixtures may declare `# expect-only`.
- Generators write LF on every platform.

## Snapshot 2026-09-24.1 (changes since snapshot 2026-09-08.2)

### Module versions

Every module whose canonical Turtle changed after snapshot 2026-09-08.2 has a new version
IRI, an `owl:priorVersion` naming the snapshot's version and `dcterms:modified 2026-09-23`.

| Module | Was | Now |
|---|---|---|
| adv (audio) | 1.0 | 1.1 |
| aspect/bundle | 1.2 | 1.3 |
| aspect/encoding | 1.0 | 1.1 |
| aspect/fsmeta | 1.0 | 1.1 |
| aspect/geometry | 1.2 working draft | 1.3 working draft |
| aspect/integrity | 1.0 | 1.1 |
| aspect/networkflow | 1.1 | 1.2 |
| aspect/pointcloud | 1.0 | 1.1 |
| aspect/provenance | 1.0 | 1.1 |
| aspect/raster | 1.1 working draft | 1.2 working draft |
| aspect/security | 2.0 | 2.1 |
| aspect/spatialref | 1.1 working draft | 1.2 working draft |
| aspect/tabular | 1.0 | 1.1 |
| axv (archive) | 1.1 | 1.2 |
| bddo | 1.0 | 1.1 |
| conf | 1.0 (no version IRI) | 1.1 |
| dfv (docfont) | 1.0 | 1.1 |
| dlv | 1.1 | 1.2 |
| gv (geo) | 1.0 | 1.1 |
| hexplain (core) | 1.0 | 1.1 |
| idv (image) | 1.0 | 1.1 |
| npv (net) | 1.1 | 1.2 |
| register/checksum | 1.0 | 1.1 |
| register/us-nato-security | 1.0 | 1.1 |
| req | 1.0 (no version IRI) | 1.1 |
| vdv (video) | 1.0 | 1.1 |

bddo, core, dlv, aspect/security, aspect/bundle, npv and register/us-nato-security had
already changed after the snapshot without a version bump; they are bumped here as well.
`fn` (0.1) is not in the snapshot and keeps its version. conf and req had no version IRI in
snapshot 2026-09-08.2, so 1.1 is their first version and has no `owl:priorVersion`.

### Validation compatibility (stricter shapes)

- **XSD ranges are enforced.** Every datatype property with an XSD `rdfs:range` is now
  datatype-checked wherever it is used, activated by `sh:targetSubjectsOf` (one
  `<module>:RangeDatatypeShape` per module). Values that used to validate and now fail
  include `bddo:size 3.5`, `hexplain:byteOffset -5`, `hexplain:byteLength "abc"`,
  `aenc:bitrate 1.5`, `asref:epsgCode 4326.7` and `aintg:checksum "zz"`. Integer ranges
  accept any XSD integer-family datatype within the range's bounds; decimal ranges also accept
  integers; double ranges accept `xsd:double` or `xsd:float`.
- **Shapes activated by one property now also fire on the others they constrain.**
  `adv:TagShape`, `adv:StreamShape`, `dfv:FontShape`, `img:CodeShapes`, `gv:PointCloudShape`,
  `gv:CrsShape`, `gv:OriginShape`, `gv:AcquisitionShape`, `hexplain:ValueExpressionShape` and
  `araster:RasterBandShape` gained targets (for example, `adv:album 42` on a tag without an
  artist now fails).
- `araster:noDataValue` must be numeric (a string sentinel no longer validates); a band belongs
  to at most one grid.
- An XSD-ranged property used outside its usual context is still range-checked: for example
  `dlv:cellBitWidth "verbatim"` on an arbitrary node now fails (it used to be ignored).
- `conf:scope` must be a `bddo:Struct` or `bddo:Field`; `conf:message` must be non-empty;
  (`req:fromStandard`, `req:requirementId`) must identify one requirement.

### Additions

- `conf:Finding`, `conf:FindingKind` (`conf:Violation`, `conf:RuleError`),
  `conf:EvaluationOutcome` (`conf:Evaluated`, `conf:NotExercised`, `conf:Errored`,
  `conf:NotApplicable`), `conf:severity` (default `sh:Violation`), with normative definitions
  of declared and run coverage.
- `rck:CRC16` and `rck:Adler32` in the checksum register; every register concept is
  `skos:exactMatch` its `bddo` checksum individual. `bddo:crc16` is defined as
  CRC-16/CCITT-FALSE and `bddo:crc32` as CRC-32/ISO-HDLC.
- `hxf:maxBytesPerCall` and `hxf:maxCellsPerWindow` with their defaults.
- `owl:AllDisjointClasses` for `bddo:Struct`, `bddo:Field`, `bddo:DataType`; the npv packet
  classes are `rdfs:subClassOf npv:Packet`.

### Deprecations (IRIs kept, `owl:deprecated true`)

- `bddo:hasEndianness` (replaced by `bddo:endianness`), `bddo:usesStruct` (no single
  replacement), `bddo:integer` (by `bddo:baseInteger`), `bddo:float` (by `bddo:baseFloat`):
  pre-release terms processors still read, now declared instead of unknown.
- `gv:axisLatitude`, `gv:axisLongitude`, `gv:axisElevation`, `adv:axisSample`,
  `adv:axisChannel`, `vdv:axisFrame`: duplicates of `dlv:axisY`, `dlv:axisX`, `dlv:axisZ`,
  `dlv:axisTime` and `dlv:axisBand` (`dcterms:isReplacedBy`).

### Imports

Modules import exactly the Hexplain namespaces they use: fn, conf, aspect/bundle,
aspect/pointcloud, adv, vdv and gv gained imports; gv no longer imports security and raster,
raster no longer imports color or sampling (its count shape stays local, because shapes are
validated module by module), pointcloud no longer imports sampling.

### Functions (`fn`)

- `hxf:isNoData` treats a NaN no-data value as matching a NaN sample and is unbound when the
  effective no-data value is ambiguous; `hxf:calibrate` is unbound when scale or offset is
  ambiguous. Failure records are scoped to one query execution. `hxf:window` is documented as
  a Jena property function (not portable).

### Specification text

- HEL: normative name-binding table for every HEL-bearing property; bare names are shorthand
  for `instance.<name>`; undefined names and forward references are errors; core function
  set and named extension groups; exact `toNumber` grammar; literal typing and escapes;
  numeric edge cases; HEL 1.0 version note. New conformance vectors.
- HDL: complete normative EBNF matching the compiler; undeclared prefixes are errors;
  optional `hdl 1.0` version declaration (first declaration only; any other version is an
  unsupported-language-version error); examples repaired.
- Processing Model: conformance classes (Physical Parser, Semantic Emitter, Bundle
  Processor, HDL Compiler) with an Unsupported-feature error; minimum codec set; resource
  limits and a ResourceLimit error; region-relative `stream.*`/`eof()`; struct size timing;
  terminator and byte-order rules; text, delimited, key/value and tree parsing rules; IRI
  minting `B#root` and `B#root/<path>`.

### Alignment with the reference implementation

- Processing Model: `bddo:alignment` is measured from the start of the current stream (the
  input, or a decoded sub-stream, whose offsets start at 0), not from the innermost bounded
  region; bounded regions do not move the origin. This is what the reference implementation
  does and what the Stream-metadata offsets already assumed.
- Processing Model: tree documents (`bddo:TreeDocument`, `bddo:nodePath`) and grouped key/value
  headers (`bddo:hasGrouping`, `bddo:keyPath`) are optional: no conformance class requires them,
  a processor that claims them implements them as specified, and one that does not rejects them
  at load time with Unsupported feature. The Physical Parser class lists text numbers, delimited
  records and tables and flat key/value headers. Unsupported feature now also names
  `partExtension()` outside a Bundle Processor.
- The reference implementation now executes tree documents and grouped key/value headers, so it
  claims both optional features: XML (with namespace bindings, attribute steps and positions) and
  JSON tree documents, nested tree documents, and keyed, valued and section-headed groups located
  by `bddo:keyPath`. It still rejects at load, with Unsupported feature, a byte-level clause on a
  field located by path, a repeat-until condition on one, a conditional or dispatched type, and a
  tree field typed by a struct that is not a tree document of the same syntax; and a grouping on
  a `bddo:DelimitedTable` or plain `bddo:DelimitedRecords`. Its generated codecs (`hxc`) do not
  read tree documents and refuse them by the capability `TREE_DOCUMENT`.
- Processing Model, tree documents, made precise where the reference implementation had to
  decide: strict RFC 8259 JSON as UTF-8 (a byte order mark is ignored); names matched by namespace
  IRI, an unprefixed attribute step in no namespace, `xml` predeclared; relative XML paths start at
  the context node; a path that does not parse is a description error; a repeating field is one
  that declares a repeat count, the number of selected nodes must equal it, and a JSON pointer
  selecting one array repeats over its elements; JSON `null` leaves a field unbound; a field typed
  by a tree document of the same syntax reads the selected node as its context; a processor MAY
  decline to process a DTD, and an entity only a DTD defines is then a validation error. A
  processor claiming tree documents MAY still reject byte-level clauses on a field found by path.
- Processing Model, grouped headers: tokens and group names compare under
  `bddo:keyIsCaseInsensitive` after trimming; a bare close-token record (ODL `END_OBJECT`) and a
  separator-less `Name Begin` record (ERMapper) are group records; `bddo:key` in a grouped
  container names a record outside every group.
- Processing Model, resource limits: tree nesting depth (`maxTreeDepth`, at least 256) for a
  processor that claims tree documents; tree nodes are visited nodes.
- Processing Model, IRI minting: the simple key of an HDL-minted text-container field
  (`<container>.<key>`) is its key, key path or node path, and a `/` in a key is minted as `%2F`.
- HDL: an unbracketed expression also ends before a quoted-key field (`"key" :` or
  `"key" as name :`) in a `header` or `document`, which it used to run into; an expression reaches
  such a field by its alias.
- Processing Model: the error categories are categories, not names; an informative table maps
  them to the reference implementation's exception types and `HexplainErrorKind` values
  (ResourceLimit is `ParseLimitException`, Description error is `HexplainProfileLoadException`,
  Unsupported feature is `HexplainUnsupportedFeatureException` / `UNSUPPORTED`).
- HDL: the reference compiler accepts `hdl 1.0`.
- `conf/test/conf-finding-valid.ttl` wrote its assertion with `&&`, which is not HEL; it now uses
  `and`.
- Core page states the family is RDFS + SHACL (OWL 2 Full), not OWL 2 DL.
- Namespace registry lists all 36 namespaces; the architecture catalogue is generated from
  the Turtle.

### Bundle Processor

The Bundle Processor class was underspecified; the Processing Model's Multi-part Assets section
now states what a conforming processor does, and the reference implementation claims the class.

- **Assembly.** An `abnd:extension` is the shorthand for the pattern `*<ext>` (a file at the
  asset root) compared ignoring ASCII case; several extension or pattern values are alternatives.
  A file matching no part spec or several is a validation error, as is a part count outside
  `abnd:minParts` (default 1 if required, else 0) .. `abnd:maxParts` (default 1 for an extension
  spec, unbounded for a pattern). `partExtension()` is the extension alternative a part matched,
  or its file name from the last `.` for a pattern part.
- **Order.** A part's description is the struct it is described by and every struct reachable
  from it; `partExtension(asset.X)` imposes no order; a part reading its own content through
  `asset` is a cycle; two part specs described by structs sharing a local name, and cyclic
  references, are description errors raised before any part is parsed. Reading a key a part's
  root struct does not declare, or naming a part several files matched, is a HEL error.
- **Cross-part references are written with `asset`.** The bundle aspect's comment said a
  `…FromField` property could name another part's field; nothing resolved it that way, and the
  Processing Model now says a `…FromField` resolves within the part being parsed (bring a value
  into scope with a derived field, as the HDL example does). Comment-only change to
  `aspect/bundle/bundle.ttl`.
- **Lifting.** The asset is linked to the primary part by `abnd:primaryPart` when exactly one
  file matched the primary spec; the graph carries the bundle profile, not the descriptions of
  the parts' bytes; no inverse edge is added.
- `abnd:nestedProfile` is optional in this version: a Bundle Processor that does not assemble
  nested profiles rejects it with Unsupported feature.
- Error table: the new validation and description errors are listed; the informative mapping
  adds `BundleAssemblyException`, `BundleCycleException` and `HelLimitException`.
- HEL: `asset` and `partExtension` state the errors above, and that `partExtension` does not
  evaluate its accessor; a HEL conformance item requires 512 levels of nesting and makes
  exceeding a nesting or length limit the ResourceLimit error, never a syntax or runtime error.
- HDL: the conditional-layout example named the grid part `asset.Raster`, but a part is named by
  the struct it is described by (`Grid`); it now reads `partExtension(asset.Grid)` and is
  completed with its header part and bundle, so it compiles and runs end to end. A `part` may list
  several locators, which are alternatives (`part ".bil" ".flt" role Payload`; YAML
  `extension: [".bil", ".flt"]`) -- HDL had no way to write the alternatives the bundle aspect
  defines. The YAML surface gains `hdl: 1.0`, the spelling of the `hdl 1.0` declaration.
- The reference implementation claims Physical Parser, Semantic Emitter, Bundle Processor
  (without `abnd:nestedProfile`) and HDL Compiler (informative note under Conformance Classes).

### Tooling

New gates: `test_range_datatypes`, `test_shape_activation`, `test_known_terms`,
`test_imports`, `test_checksum_register`; `test_html_sync` also checks versions, header
comments, the namespace registry and the architecture catalogue. `_range_contract_cases.py`
adds two-sided witnesses for every range shape to the family contracts. Invalid SHACL fixtures
declare `# expect:` lines naming the focus node, shape and constraint component they must
trip. `test_conformance.py` is renamed `test_bundle_required_parts.py`. `.gitattributes`
keeps Turtle and TSV LF in working trees.
