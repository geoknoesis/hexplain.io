# Changelog

Changes to the Hexplain specification family. Version numbers are per module
(`owl:versionInfo` / `owl:versionIRI`); the family has no single version. Local release
snapshots are recorded under `releases/`.

## Unreleased (since snapshot 2026-09-08.2)

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
`fn` (0.1) is not in the snapshot and keeps its version.

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

### Tooling

New gates: `test_range_datatypes`, `test_shape_activation`, `test_known_terms`,
`test_imports`, `test_checksum_register`; `test_html_sync` also checks versions, header
comments, the namespace registry and the architecture catalogue. `_range_contract_cases.py`
adds two-sided witnesses for every range shape to the family contracts. Invalid SHACL fixtures
declare `# expect:` lines naming the focus node, shape and constraint component they must
trip. `test_conformance.py` is renamed `test_bundle_required_parts.py`. `.gitattributes`
keeps Turtle and TSV LF in working trees.
