# Changelog

Changes to the Hexplain specification family. Version numbers are per module
(`owl:versionInfo` / `owl:versionIRI`); the family has no single version. Local release
snapshots are recorded under `releases/`.

## Unreleased (changes since snapshot 2026-09-24.2)

### Module versions

Every module whose canonical Turtle differs from snapshot 2026-09-24.2 has a new version IRI
naming the version that snapshot froze as `owl:priorVersion`, and `dcterms:modified 2026-09-24`.
Most changed only in their generated scope notes (below); `owl:versionInfo` is now the bare
version number everywhere, and the three working drafts say so with
`schema:creativeWorkStatus "working draft"`. Unchanged: aspect/color, aspect/encoding,
aspect/fsmeta, aspect/networkflow, aspect/pointcloud, aspect/security, aspect/time.

| Module | Was | Now |
|---|---|---|
| archive (axv) | 1.2 | 1.3 |
| aspect/bundle | 1.4 | 1.5 |
| aspect/geometry | 1.3 working draft | 1.4 (working draft) |
| aspect/integrity | 1.1 | 1.2 |
| aspect/packaging | 1.1 | 1.2 |
| aspect/provenance | 1.2 | 1.3 |
| aspect/raster | 1.2 working draft | 1.3 (working draft) |
| aspect/sampling | 1.1 | 1.2 |
| aspect/signal | 1.1 | 1.2 |
| aspect/spatialref | 1.3 working draft | 1.4 (working draft) |
| aspect/tabular | 1.1 | 1.2 |
| audio (adv) | 1.1 | 1.2 |
| bddo | 1.2 | 1.3 |
| conf | 1.2 | 1.3 |
| conf/shapes | 1.2 | 1.3 |
| core (hexplain) | 1.2 | 1.3 |
| dlv | 1.2 | 1.3 |
| docfont (dfv) | 1.2 | 1.3 |
| fn | 0.2 | 0.3 |
| geo (gv) | 1.1 | 1.2 |
| image (idv) | 1.2 | 1.3 |
| net (npv) | 1.2 | 1.3 |
| register/checksum | 1.2 | 1.3 |
| register/color | 1.0 | 1.1 |
| register/geometry-type | 1.2 | 1.3 |
| register/media-encoding | 1.1 | 1.2 |
| register/part-role | 1.0 | 1.1 |
| register/us-nato-security | 1.2 | 1.3 |
| req | 1.2 | 1.3 |
| req/shapes | 1.2 | 1.3 |
| video (vdv) | 1.1 | 1.2 |

### Review of the normative documents (2026-09-27)

- **BCP 14.** Every conventions section (Processing Model, HEL, HDL, the conformance sections of
  conf and req, and the vocabulary pages that have one) now cites RFC 8174 alongside RFC 2119 and
  says the key words carry their meaning only in all capitals.
- **Requirement register.** `req-pm-emission-9` was registered MUST while its text only permitted
  (MAY per-cell triples); it now states what a processor must do with a field that has a data
  layout: nothing for `hexplain:mapsToProperty`, a link to the field's array node for
  `hexplain:mapsToObjectProperty`, and no per-cell triples, which this version gives no vocabulary
  (the reference engine already behaves so). `req-pm-conformance-classes-9` repeated
  `req-pm-errors-17` word for word and is withdrawn: the refusal paragraph now points to the error
  table, and `req-pm-errors-17` names its subject ("An Unsupported feature error MUST be raised no
  later than ..."). `req-ce-conf-conformance-11` and `req-ce-conf-conformance-12` restated
  `req-pm-conformance-evaluation-7` and `req-pm-conformance-evaluation-8` and are withdrawn; the conf
  page now cites the Processing Model's rules. The registry extraction
  (`tools/_requirement_ids.py`) records, for a requirement that opens with a pronoun ("It MUST
  ..."), the sentence before it as `context`, so an entry read on its own keeps its subject; a
  withdrawn entry recorded before audiences existed (`req-pm-errors-15`) now has one, and its text
  reads its cross-reference as the section title instead of "()". `coverage.json` lists the
  withdrawn identifiers.
- **Natural datatype of a computed value.** "The natural datatype of the HEL result", which
  `req-pm-emission-5` relied on, was never defined. New section `processing#computed-values`
  defines it (`req-pm-computed-values-1`): an Integer is `xsd:long` (a uint64 value beyond it
  `xsd:integer`), a Float `xsd:double` (`NaN`, `INF`, `-INF`), a String `xsd:string`, a Boolean
  `xsd:boolean`, Bytes `xsd:hexBinary`, Null nothing, and a struct or array node a Type / HEL error.
  With a `hexplain:valueDatatype`, the result must have a value in that datatype's value space
  (`req-pm-computed-values-2`); a processor never re-labels the datatype to fit. The HEL
  name-binding row for `hexplain:valueExpression` points to the rule. Fourteen new Semantic Emitter
  cases (`se-value-natural-*`, `se-value-datatype-*`).
- **Decoding text.** Text containers said a malformed sequence is a validation error "never
  replaced silently", HEL said malformed bytes decode to U+FFFD, and plain string fields had no
  rule. New section `processing#text-decoding` gives one: what is well-formed in each
  `bddo:encoding` (RFC 3629 UTF-8, paired UTF-16 surrogates and an even length, ASCII at most
  7F, every Latin-1 byte), no replacement character ever (`req-pm-text-decoding-1`), a validation
  error for text read from the input that is not well-formed, with the field left unbound in a
  lenient mode (`req-pm-text-decoding-2`), and ASCII digits and whitespace in a number written as
  text (`req-pm-text-decoding-3`). `req-pm-delimited-records-2` points to it. In HEL a Bytes value
  that is not well-formed equals no String and is an error where a String is required. New cases
  `pp-str-utf8-malformed`, `pp-str-utf8-overlong`, `pp-str-utf8-encoded-surrogate`,
  `pp-str-utf16-lone-surrogate`, `pp-str-utf16-odd-length`, `pp-str-ascii-high-byte`,
  `pp-str-latin1-every-byte`, `pp-textnum-non-ascii-digit`, `pp-hel-bytes-malformed-argument`,
  `ce-recovery-malformed-text`; `pp-hel-bytes-vs-string` now expects a malformed byte to equal no
  String.
- **Security and Privacy Considerations.** New section `processing#security-privacy` gathers the
  threats a processor faces and the rules that answer them, and adds four: limits apply to the work
  a description causes as much as to the input (`req-pm-security-resources-1`); every codec stage
  counts toward the decoded-byte limit as it is produced, never checked after a full decode, and a
  declared size beyond the limit is ResourceLimit even under a smaller per-block cap
  (`req-pm-security-decompression-1`); nothing an input or description names is fetched
  (`req-pm-security-external-1`); and a base IRI a processor chooses is never derived from the
  input's file name or path (`req-pm-privacy-1`), with a report's `conf:input` likewise not a file
  path the caller did not supply (`req-pm-privacy-2`, SHOULD). The HEL regular-expression cost
  limit and quantifier budget, until now a MAY with no minimum, are normative: new Resource Limits
  rows `maxQuantifierEvaluations` (1,000,000) and `maxRegexSteps` (2,000,000), the reference
  engine's defaults; exceeding either is a ResourceLimit error (`req-hel-ext-text-3`,
  `req-hel-ext-quantifiers-4`, and `req-hel-conformance-8`, which now lists both); the error
  table's ResourceLimit row (`req-pm-errors-12`) names them; the suite manifest may lower both.
  The function library gains a Security and privacy section (`fn#security`): assets resolved only
  from registered roots, per-call byte and cell caps enforced before reading, and the byte and
  value functions kept from parties who may not read every byte. New cases
  `pp-limit-quantifier-evaluations`, `pp-limit-regex-steps`,
  `pp-codec-lz4-block-declared-size-over-limit`, `pp-codec-lz4-frame-declared-size-over-limit`
  and `pp-codec-zstd-declared-size-over-limit` (the first to cite `req-pm-optional-codecs-2`).
- **Sync markers.** `req-pm-parsestruct-3` now bounds the `bddo:syncOnMarker` search: it starts
  at the cursor (a marker exactly there counts) and stops at the current bound, the end of the
  innermost bounded region or of the current stream, so an occurrence that runs past the bound is
  not found; the struct's own size, applied after the seek, is measured from after the marker.
  The error table's Sync row (`req-pm-errors-2`) says so. New cases `pp-sync-marker-at-cursor`,
  `pp-sync-bounded-by-region`, `pp-sync-marker-straddles-bound`,
  `pp-sync-struct-size-after-marker`.
- **IRI minting.** New `req-pm-iri-minting-4`: a `%` in a key is always percent-encoded as `%25`,
  so the keys `a b` and `a%20b` cannot mint one IRI (the reference engine already does this). New
  case `se-key-percent-sign`.

### New language features (bddo 1.3, register/checksum 1.3, register/media-encoding 1.2)

All additions are to the unreleased working versions; no module needed a further version bump.

- **Scalar types.** `bddo:uint24`, `bddo:int24` (three-byte two's complement) and `bddo:float16`
  (IEEE 754 binary16, subnormals, both zeros, both infinities and NaN included; the decoded value
  is the exact binary16 value as a Float), each with `be`/`le` forms (`bddo:uint24be`,
  `bddo:uint24le`, `bddo:int24be`, `bddo:int24le`, `bddo:float16be`, `bddo:float16le`), as
  datatype individuals like the others: `bddo:bitWidth` 24/16, `bddo:xsdType` `xsd:unsignedInt`,
  `xsd:int` and `xsd:float`. HDL: `u24 u24le u24be i24 i24le i24be f16 f16le f16be`. A fixed value
  on a `bddo:float16` field is compared at binary16 width (`req-pm-parsefield-26`); a hex fixed
  value on a 24-bit field is three bytes.
- **CRC variants.** `bddo:crc16` (CRC-16/CCITT-FALSE) and `bddo:crc32` (CRC-32/ISO-HDLC) are
  unchanged in meaning. New named algorithms `bddo:crc8Smbus`, `bddo:crc16Arc`, `bddo:crc16Xmodem`,
  `bddo:crc16Modbus`, `bddo:crc16X25`, `bddo:crc32c`, `bddo:crc32Bzip2`, `bddo:crc32Mpeg2`,
  `bddo:crc64Ecma182`, `bddo:crc64Xz`, each stating its Rocksoft parameters and its catalogue
  check value over "123456789" with the new properties `bddo:crcWidth`, `bddo:crcPolynomial`,
  `bddo:crcInit`, `bddo:crcReflectIn`, `bddo:crcReflectOut`, `bddo:crcXorOut` and `bddo:crcCheck`
  (also stated on `bddo:crc16` and `bddo:crc32`). New class `bddo:CustomCrc`
  (`rdfs:subClassOf bddo:ChecksumAlgorithm`) states any other CRC by the six parameters, all
  required (`bddo:CustomCrcShape`: width 8..64, register values below 2^width).
  `bddo:ChecksumShape` accepts the named algorithms or a `bddo:CustomCrc`. The checksum register
  mirrors every named algorithm (`rck:CRC8SMBus`, `rck:CRC16ARC`, `rck:CRC16XMODEM`,
  `rck:CRC16MODBUS`, `rck:CRC16X25`, `rck:CRC32C`, `rck:CRC32BZIP2`, `rck:CRC32MPEG2`,
  `rck:CRC64ECMA182`, `rck:CRC64XZ`), each `hexplain:correspondsTo` its individual. New gate
  `test_crc_catalogue` recomputes every check value from the stated parameters. HDL:
  `@checksum crc8|crc16arc|crc16xmodem|crc16modbus|crc16x25|crc32c|crc32bzip2|crc32mpeg2|crc64ecma|crc64xz(a .. b)`
  and `@checksum crc(width: 16, poly: 0x8005, init: 0x0000, refin: true, refout: true, xorout: 0x0000)(a .. b)`.
  The checksum value is the checksum field's own value, in its declared type, width and byte order;
  the field's integer width equals the CRC's (anything else is a Description error). YAML:
  `checksum: { crc: { width, poly, init, refin, refout, xorout }, from, to }`.
- **LZ4 and Zstandard.** New register concept `menc:LZ4Block` (a bare LZ4 block); `menc:LZ4` is
  now defined as the LZ4 Frame format and `menc:Zstd` as Zstandard frames. The Processing Model
  defines all three under `codecs-beyond-minimum` (new section `processing#optional-codecs`):
  checksums verified (a mismatch is a Checksum error), dictionaries refused with Unsupported
  feature, malformed data a Validation error, and `menc:LZ4Block`'s required `decodedSize`
  parameter (a missing one is a Description error).
- **Parameterised structs.** New class `bddo:Parameter` and properties `bddo:hasParameter`
  (on a struct), `bddo:parameterType` (class `bddo:ParameterType`, individuals `bddo:IntegerParameter`,
  `bddo:FloatParameter`, `bddo:StringParameter`, `bddo:BytesParameter`, `bddo:BooleanParameter`) and `bddo:hasArgument` (a list of HEL strings on a Field, `bddo:DataTypeRule`
  or `bddo:DispatchArm`, evaluated in the caller's context). New HEL root `param`
  (`param.<name>`), now a reserved word. Shapes `bddo:ParameterisedStructShape`,
  `bddo:ParameterShape`, `bddo:ArgumentListShape` and `bddo:ArgumentArityShape`. Parameters are
  named by the simple key of their IRI, as fields are (BDDO has no separate name property).
  A `bddo:dispatchDefault` never names a parameterised struct (it cannot state arguments).
  HDL: `struct Row(n: int, w) { cells : bytes[w] repeat n }`, `r : Row(hdr.count, 4)`; YAML
  `params: [ { n: int }, w ]` and `type: { struct: Row, args: [ … ] }`.
- **Local bindings.** New class `bddo:LocalBinding`, a member of `bddo:hasField` that is not a
  field, and property `bddo:localExpression`; shape `bddo:LocalBindingShape`. A binding is
  evaluated at its position, is read by bare name or `instance.<name>`, consumes no bytes and is
  neither in the parsed tree nor emitted. `bddo:StructShape` accepts a local binding as a list
  member. HDL: `let area = width * height`; YAML `- let: { name: area, value: "width * height" }`.
- **Reference engine claims.** `codecs-beyond-minimum` is claimed (LZ4 Frame, LZ4 Block,
  Zstandard); `reference-engine-claims.json` and the Processing Model's note say so.

Requirement text changed (the sentences now cover the new constructs): `req-pm-parsefield-11`
(arguments are evaluated before a parameterised struct is parsed), `req-pm-parsefield-16` (the
checksum algorithms include the CRC variants and `bddo:CustomCrc`, computed by the Rocksoft model
and compared at the field's own width), `req-pm-errors-5` (LZ4 and Zstandard checksum and
content-size mismatches), `req-pm-errors-8` (the Description errors of parameters, arguments,
local bindings, CRC fields and `menc:LZ4Block`), `req-hel-key-resolution-2` (a key may name a
local binding or, after `param`, a parameter), `req-hel-key-resolution-3` and
`req-hdl-grammar-keywords-1` (`param` is reserved), `req-hdl-lexical-1` (parameter and binding
names follow the field-name rule), `req-bddo-structural-properties-1` (a `bddo:hasField` list may
hold local bindings).

New requirements: `req-pm-parsestruct-9`, `req-pm-parsestruct-10`, `req-pm-parsefield-26`, `req-pm-emission-10`, `req-pm-optional-codecs-1` to `req-pm-optional-codecs-7`, `req-hel-reserved-roots-2`, `req-hdl-checksums-1`, `req-hdl-checksums-2`, `req-hdl-parameters-1`, `req-bddo-core-datatypes-3`, `req-bddo-core-datatypes-4`, `req-bddo-checksum-algorithms-1` and `req-bddo-parameterised-structs-1` to `req-bddo-parameterised-structs-3`.

New conformance cases, 106 (68 Physical Parser, 1 Semantic Emitter, 37 HDL Compiler): `hc-bracket-size-after-u24`, `hc-checksum-crc-field-width`, `hc-checksum-custom-crc`, `hc-checksum-custom-crc-64-bit`, `hc-checksum-custom-crc-missing-parameter`, `hc-checksum-custom-crc-repeated-parameter`, `hc-checksum-custom-crc-value-too-wide`, `hc-checksum-custom-crc-width-out-of-range`, `hc-checksum-custom-crc-yaml`, `hc-checksum-named-crcs`, `hc-fixed-24-bit-and-half`, `hc-let-binding`, `hc-let-binding-yaml`, `hc-let-forward-reference`, `hc-let-in-header`, `hc-let-name-clash`, `hc-let-reads-parameter`, `hc-let-where-field-required`, `hc-param-argument-forward-reference`, `hc-param-arguments-for-plain-struct`, `hc-param-arity-mismatch`, `hc-param-dispatch-default`, `hc-param-field-clash`, `hc-param-literal-type-mismatch`, `hc-param-missing-arguments`, `hc-param-nested-arguments`, `hc-param-recursion`, `hc-param-reserved-name`, `hc-param-root-struct`, `hc-param-struct`, `hc-param-struct-yaml`, `hc-param-switch-arms`, `hc-param-switch-arms-yaml`, `hc-param-undeclared`, `hc-param-unknown-type`, `hc-types-24-bit-and-half`, `hc-types-24-bit-and-half-yaml`, `pp-codec-lz4-block`, `pp-codec-lz4-block-bad-offset`, `pp-codec-lz4-block-missing-size`, `pp-codec-lz4-block-shorthand`, `pp-codec-lz4-block-size-mismatch`, `pp-codec-lz4-content-checksum-mismatch`, `pp-codec-lz4-frame`, `pp-codec-lz4-frame-block-checksums`, `pp-codec-lz4-frame-concatenated`, `pp-codec-lz4-frame-substream`, `pp-codec-lz4-frame-truncated`, `pp-codec-lz4-header-checksum-mismatch`, `pp-codec-zstd-checksum-mismatch`, `pp-codec-zstd-concatenated`, `pp-codec-zstd-dictionary`, `pp-codec-zstd-frame`, `pp-codec-zstd-parameter-unknown`, `pp-codec-zstd-truncated`, `pp-crc-crc16arc`, `pp-crc-crc16modbus`, `pp-crc-crc16x25`, `pp-crc-crc16xmodem`, `pp-crc-crc32bzip2`, `pp-crc-crc32c`, `pp-crc-crc32mpeg2`, `pp-crc-crc64ecma`, `pp-crc-crc64xz`, `pp-crc-crc8`, `pp-crc-custom`, `pp-crc-custom-24-bit`, `pp-crc-custom-invalid-width`, `pp-crc-custom-mismatch`, `pp-crc-field-too-narrow`, `pp-crc-field-too-wide`, `pp-crc-named-mismatch`, `pp-crc-stored-little-endian`, `pp-float16-fixed-value`, `pp-float16-fixed-value-mismatch`, `pp-float16-fixed-value-overflow`, `pp-float16-infinities-and-nan`, `pp-float16-normal-values`, `pp-float16-subnormals-and-zeros`, `pp-int24-negative`, `pp-int24-repeated`, `pp-let-forward-reference`, `pp-let-in-header`, `pp-let-name-clash`, `pp-let-not-reachable-through-parent`, `pp-let-size-and-count`, `pp-let-struct-size`, `pp-let-with-parameter`, `pp-param-argument-forward-reference`, `pp-param-arguments-without-parameters`, `pp-param-arity-mismatch`, `pp-param-basic`, `pp-param-field-name-clash`, `pp-param-float-accepts-integer`, `pp-param-nested-arguments`, `pp-param-recursion`, `pp-param-recursion-depth-limit`, `pp-param-repeated-field`, `pp-param-root-struct`, `pp-param-rule-and-arm-arguments`, `pp-param-type-mismatch`, `pp-param-undeclared`, `pp-uint24-both-byte-orders`, `pp-uint24-fixed-hex-width`, `pp-uint24-fixed-value`, `se-parameters-and-bindings-not-emitted`. The LZ4 inputs are written by `tools/conformance/lz4frames.py` (a plain-Python block compressor, frame writer and xxHash-32, each block checked by its own decoder); the Zstandard frames are pre-made with python-zstandard 0.25 and committed as hex in `tools/conformance/zstdframes.py`, pinned by SHA-256 and checked against a plain-Python XXH64 of their content, so neither package is a dependency; CRCs come from the Rocksoft model in `tools/conformance/crc.py`.

### Parameters and bindings: three clarifications

- **Argument types.** An argument that is not of its parameter's `bddo:parameterType` is a
  Description error when the description shows it (a literal, or a negated numeric literal, for a
  typed parameter), raised when the description is loaded; any other argument's value is known only
  when it is evaluated, and a mismatch there is a Type / HEL (Expression) error, never a Description
  error. New Processing Model paragraph `processing#argument-types`.
- **Quantifiers over struct elements.** Inside the predicate of `all`/`any` over struct elements
  `instance` is each element, so `param.<name>` and a name that reaches a local binding resolve
  against the element's struct, not the struct holding the expression, and the load-time check of
  `param.<name>` is made against the element's struct wherever the description determines it. The
  same holds for an HDL `repeat until` over struct elements: a bare name that is only a parameter of
  the holding struct is an ERROR there. `self.<name>` never reaches a local binding, even where
  `self` and `instance` are the same element.
- **Text containers.** A delimited, key/value or tree container may declare neither parameters
  (new) nor local bindings (as before); either is a Description error. HDL: `params` beside a YAML
  `kind` other than `struct` is an ERROR.
- **Strict profile.** The optional strict profile now admits `bddo:hasParameter` on a struct and
  `bddo:hasArgument` on a field, data-type rule and dispatch arm, which its closed shapes refused.

Requirement text changed: `req-pm-parsefield-11` (the category of an argument type mismatch
depends on when it is known), `req-pm-errors-6` (an evaluated argument of the wrong type),
`req-pm-errors-8` (a literal argument of the wrong type; `param.<name>` against the element's struct
in a quantifier; parameters or bindings in any text container), `req-hel-reserved-roots-2` (unchanged
sentence, now followed by `req-hel-reserved-roots-3`), `req-bddo-parameterised-structs-3` (text
containers named in full) and `req-hdl-parameters-1` (parameters on a header, table or document).

New requirements: `req-pm-context-3`, `req-pm-context-4`, `req-hel-reserved-roots-3`,
`req-hel-ext-quantifiers-3`, `req-hdl-parameters-2` and `req-bddo-parameterised-structs-4`.

New conformance cases, 8 (5 Physical Parser, 3 HDL Compiler): `pp-param-type-mismatch-evaluated`,
`pp-param-quantifier-element`, `pp-param-quantifier-holding-struct`, `pp-param-on-text-container`,
`pp-let-not-reachable-through-self`, `hc-param-element-scope`,
`hc-param-holding-struct-in-element-scope`, `hc-param-on-header`; `pp-param-type-mismatch` now also
cites `req-pm-context-3`.

### Conformance run reports (conf 1.3)

- **New terms.** `conf:finding` (run to finding), `conf:verdict` with `conf:Verdict`
  (`conf:Conformant`, `conf:NonConformant`), `conf:truncated` (xsd:boolean),
  `conf:truncationReason`, `conf:versionScopingApplied` (xsd:boolean), `conf:fileVersion`,
  `conf:profile`, `conf:input` (IRI or literal), `conf:ruleSet`, `conf:failOn` (sh:Violation,
  sh:Warning or sh:Info). Error categories are individuals: `conf:ErrorCategory` with
  `conf:SyncError`, `conf:BoundsError`, `conf:ValidationError`, `conf:ChecksumError`,
  `conf:ExpressionError`, `conf:DispatchError`, `conf:DescriptionError`,
  `conf:UnsupportedFeature`, each with its old string name as `skos:notation`. `owl:AllDifferent`
  axioms for the finding kinds, outcomes, verdicts and categories.
- **`conf:errorCategory`** takes a `conf:ErrorCategory`. The string names stay accepted as a
  deprecated form of the same value (the engine writes strings today). **Dispatch is its own
  category** (it was folded into Description). **ResourceLimit is not a category**: a resource
  limit is never a finding (it fails or truncates the run), and a parse attribution naming it
  is rejected.
- **Stricter shapes (`conf/shapes.ttl`).** A run states exactly one verdict and one truncated
  flag; a truncated run is non-conformant and only a truncated run states a reason; the verdict
  must follow from the findings, outcomes and `conf:failOn`; `conf:fileVersion` is stated exactly
  when version scoping was applied; `conf:NotApplicable` requires a requirement with
  `req:appliesToVersion` that version scoping excluded; every requirement in the graph gets an
  outcome; every finding of a graph that holds a run is linked by `conf:finding`, from at most one
  run. A finding's severity equals its constraint's (absent reads as sh:Violation), and a rule
  error or Parse finding is at sh:Violation; a Parse finding cites exactly the requirement of its
  category's attribution, or none; `conf:errorCategory` appears only on Parse findings and parse
  attributions; an untyped node stating a category is checked as an attribution
  (`conf:UntypedParseAttributionShape`); a category named once by IRI and once by string is a
  duplicate; `conf:Finding`, `conf:Run`, `conf:Constraint`, `conf:ParseAttribution` and
  `req:Requirement` are disjoint (`conf:DisjointKindsShape`). New shapes:
  `conf:FindingSeverityShape`, `conf:ParseFindingAttributionShape`, `conf:ErrorCategoryUseShape`,
  `conf:UntypedParseAttributionShape`, `conf:DisjointKindsShape`.
- **A report validates on its own.** It carries copies of the requirements, constraints and
  parse attributions it references (Processing Model `req-pm-conformance-evaluation-8`,
  `req-ce-conf-conformance-12`); blank-node requirements are copied under skolem IRIs.

### Requirements (req 1.3)

- `req:requirementId`, `req:fromStandard` and `req:statement` must contain a visible character:
  white space, no-break spaces, zero-width spaces and the byte-order mark alone are rejected.
  The identity check normalises no-break and other Unicode spaces to a space and drops
  zero-width characters before comparing.
- `req:statement` may be language-tagged (`rdf:langString`); its range is now `rdfs:Literal`.

### Registers and core (core 1.3, registers)

- **Lifecycle holes closed** (`hexplain:RegisterStatusShape`, new
  `hexplain:RegisterLifecycleShape`): a `hexplain:statusValid` entry that is `owl:deprecated`, a
  deprecated entry with no status or no `skos:historyNote`/`skos:changeNote`, an entry replaced by
  itself and an entry replaced by a deprecated entry are rejected, as `test_register_lifecycle`
  already required. Using a deprecated register value in a bound property is reported at
  `sh:Warning` (`hexplain:RegisterDeprecatedValueShape`).
- **Bindings read together.** `hexplain:RegisterBindingShape` accepts a value that is in any
  scheme bound to the property: with a US and a NATO binding for one property, every value used
  to fail one of them. Its generated scope note no longer says it has no target.
- **`hexplain:mapsToClass` accepts an `rdfs:Class`** (`hexplain:MapsToClassShape`): the target
  must be typed `owl:Class` or `rdfs:Class`. Requiring `owl:Class` rejected every profile mapping
  a struct to a vocabulary that types its classes `rdfs:Class`, schema.org among them. A term that
  is neither (a property, an untyped IRI, a literal) is still rejected.
  `hexplain:MapsToPropertyShape` already accepted `rdf:Property`.
- **us-nato-security 1.3:** `usnato:Restricted` is no longer a top concept of the US scheme, and
  `usnato:Fouo` is no longer a member of `usnato:HandlingCaveats`; both stay `skos:inScheme`.
- **geometry-type 1.3:** a concept points at its Simple Features class with `rdfs:seeAlso`, not
  `skos:closeMatch` (sf:Point is an OWL class). `test_ontology_design` now also rejects a SKOS
  mapping whose object is an ontology entity.

### Bundle (aspect/bundle 1.5)

- `abnd:extension` and `abnd:pathPattern` are checked as whole strings: an extension is a dot
  and one or more non-empty steps; a pattern is `/`-separated, non-empty segments relative to
  the asset root, never `.` or `..`, with no backslash, drive letter or colon, and not empty.
- A required spec may not state `abnd:maxParts 0`; `abnd:partRole` must be a `skos:Concept` IRI;
  `abnd:liftsProperty` must be an IRI; a profile may not nest itself through
  `abnd:nestedProfile`, directly or through other profiles.

### bddo 1.3

- `bddo:TreePrefixBindingShape` matches a bound prefix literally (a prefix such as `a.b` was a
  regular expression that also matched `axb`).
- `bddo:nodePath` requires every container of the field to be a tree document; a field shared
  with a binary struct used to pass.
- `bddo:KeyValueHeaderShape` accepts a header field with neither `bddo:key` nor `bddo:keyPath`:
  the Processing Model locates such a field by its simple key, and an HDL compiler emits no
  `bddo:key` for an unquoted header field name, but the shape still required one locator of every
  field, so the `hdl` command line rejected its own output for `hc-quoted-header-keys`. A field
  still declares at most one `bddo:key` or one `bddo:keyPath`, never both. The `bddo:KeyValueHeader`
  and `bddo:key` definitions say so.

### fn 0.3

- `hxf:isNoData` is unbound when the sample format or bit depth in effect is ambiguous (several
  on the band, or none on the band and the grids having it disagree), and its body returns one
  answer (`SELECT DISTINCT`).
- `hxf:stat`: over an empty window, or one whose cells are all no-data or NaN, count is 0 and sum
  is 0, and min, max and mean are unbound (the unbound condition no longer also said "empty").
- `hxf:digest` covers the node's extent only: `hxf:digest(<asset#root>)` is the root struct's
  bytes, not the file's.
- The function catalogue of `fn/index.html` is generated from `fn.ttl` (`test_fn_catalogue`); it
  still said `hxf:column`/`hxf:row` round to the nearest cell centre for `asref:PixelCenter`.

### Documentation annotations

- Scope notes are no longer one shared template: a note says "subclass links below" only of a
  class that has one, "SHACL paths are listed below" only of a property a shape uses, and "No
  automatic target" only of a shape without one (a SPARQL-based target counts). Core, conf, req
  and bundle terms have notes of their own; the core module sentence ("use when linking a
  physical format description to semantic RDF output") no longer appears on the register-lifecycle
  terms. New gate `test_scope_notes` checks each templated claim against the graph.
- Mojibake removed from sampling and signal (`â€”` for an em dash) and from the pages generated
  from them.

### Processing Model

- Conformance Evaluation: a ResourceLimit is never a Parse finding (it fails or truncates the
  run, as item 5 and Resource Limits say); Dispatch is a category of its own; the verdict uses the
  run's fail-on severity; a new Report item states what an RDF report carries and that it
  validates on its own. The reference implementation note maps Dispatch to `DISPATCH`.

### Governance and snapshots

- New gate `test_version_immutability`: one `owl:versionIRI` names one graph in every snapshot
  and in the working tree. Two frozen violations (bddo 1.0 and aspect/bundle 1.2 in 2026-09-08.1
  and .2) cannot be rewritten; `releases/ERRATA.md` records them (E1, E2) with the dangling and
  missing `owl:priorVersion` values of frozen versions (E3, E4) and the false "canonical graphs
  unchanged" note (E5), and the gate allows exactly those.
- `releases/lineage.json` records the commit that added each snapshot and every module's
  versions in order, with corrected prior versions.
- `releases/index.html` lists snapshots newest first, no longer says 2026-09-08.1 left the
  canonical graphs unchanged, and is in the sitemap.
- `conf/shapes` and `req/shapes` no longer claim the `conf` and `req` namespace prefixes.

### Strict profile and tooling

- The optional strict profile closes each class over its own properties (25 classes, read from
  the family's shapes) instead of one union of 144, targets by class and by the properties only
  that class uses, and finds engine profiles by their content (bddo terms), which adds
  `core/src/test/resources/nitf/nitf.ttl` and four other descriptions to the lint.
- `test_review_mutations`: 150 probes of the defects above (the pre-review tree gets 97 right: it
  accepts 39 of the defects and rejects 14 valid graphs); 135 of them are also module contracts.
- Pages: `review.html` is marked historical; `shared-patterns` no longer states engine status
  (moved to `reference-engine-claims.json` as `codecs.parameters`); the homepage states the
  number of vocabulary modules (36, checked) and no single family version.

### Requirement registry

- **Changed text, one clause one level.** `req-pm-errors-9` was a fragment ("SHOULD be raised
  when the description is loaded."); it is now "A Description error SHOULD be raised when the
  description is loaded.", which also changes the row `req-pm-errors-8` that contains it.
  `req-pm-errors-11` and `req-pm-conformance-classes-3` each held a SHOULD and a MUST clause;
  each now keeps its SHOULD sentence, and the MUST clause is a sentence of its own
  (`req-pm-errors-17`, `req-pm-conformance-classes-9`).
- **Withdrawn:** `req-pm-errors-15` anchored the same table row as `req-pm-errors-6`. Its
  load-time clause is now a sentence of its own, `req-pm-errors-16` ("A malformed HEL expression
  SHOULD be raised when the description is loaded, and is a Type / HEL error even then"); cite
  `req-pm-errors-6` for the category and `req-pm-errors-16` for the load-time rule.
- **New:** `req-pm-conformance-evaluation-7` (what an RDF run report states) and
  `req-pm-conformance-evaluation-8` (a report validates on its own; blank-node requirements get
  skolem IRIs), restated on the conf page (`req-ce-conf-conformance-11`,
  `req-ce-conf-conformance-12`). `req-ce-conf-conformance-5` now says that the category
  is a `conf:ErrorCategory`, that Dispatch is one of its own, and that a resource limit is never
  a finding.
- **Rendered text.** The registry records a sentence as a reader sees it: an empty link reads as
  the title of the section it points to (ten entries read "(see )" or "()"), and a superscript
  as `^` (2^63 - 1). The recorded text, not the sentence, of these entries changed:
  `req-pm-conformance-1`, `req-pm-conformance-classes-6`, `req-pm-context-1`, `req-pm-emission-1`,
  `req-pm-errors-4`, `req-pm-errors-6` (whose row also lost its load-time clause to
  `req-pm-errors-16`), `req-pm-errors-10`, `req-hel-formal-grammar-2`, `req-hel-numeric-semantics-1`,
  `req-hel-numeric-semantics-4`, `req-hel-numeric-semantics-5`.
- **Class per sentence.** `req-pm-conformance-classes-1` binds the Bundle Processor,
  `req-pm-conformance-classes-2` the HDL Compiler, `req-pm-errors-13` and `req-pm-errors-14` the
  Conformance Evaluator (the lenient mode of a conformance run), and `req-pm-multi-part-assets-3`,
  `req-hdl-layout-1`, `req-pm-emission-1` the Physical Parser.
- **Audience.** Every entry states `audience`: `processor`, or `description` for a rule on a
  description's author that no processor can fail (`req-hel-key-resolution-3`,
  `req-hel-name-binding-2`, `req-pm-context-2`, `req-hel-operator-precedence-1`, and the
  vocabulary-page rules below that constrain descriptions). They are not processor requirements.
- **Vocabulary pages.** The normative sentences of the bddo, dlv, core, bundle, geometry,
  raster and spatialref pages are registered (`req-bddo-…`, `req-dlv-…`, `req-core-…`,
  `req-geometry-…`, `req-raster-…`, `req-spatialref-…`). Those a family shape enforces are of kind
  `shape-backed` and name the shapes.
- **Stricter gate.** A changed or withdrawn requirement must be named as a whole word
  (`req-pm-errors-1` is no longer excused by an entry for `req-pm-errors-10`) in the Unreleased
  section of this file, not anywhere in it.

### Errors table (round-4 integration)

- `req-pm-errors-8` (Description error) now lists the conflicting forms (`#conflicting-forms`),
  two fields of one struct sharing a local name, and states that an invalid profile or rule set
  (one the family's shapes reject: a requirement identity stated twice, a requirement without a
  statement, a parse attribution naming ResourceLimit) is a Description error when it is loaded.
- `req-pm-errors-7`: the Dispatch error row says Dispatch is a category of its own, neither Validation nor Description.
- The nine RDF-form run report cases (`ce-report-rdf-*`) are generated now that the conf vocabulary
  declares the run terms: categories as `conf:*Error` IRIs, `conf:failOn` only when it is not
  `sh:Violation`, `conf:fileVersion` only when version scoping was applied. The comparator's
  self-check compares an expected run report as the pattern it is; shape conformance applies to an
  implementation's report. `pp-hel-reserved-word-key` cites `req-pm-errors-16` in place of the
  withdrawn `req-pm-errors-15`.
- The HEL expression nesting depth limit counts depth as HEL's Expression depth
  (`hel/#expression-depth`) defines, an n-ary chain being one node.

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
- `hc-semantic-mapping` (and its YAML mirror) declares the format-local class and property it
  maps to, in a `raw-turtle` block: `hexplain:MapsToClassShape` and `hexplain:MapsToPropertyShape`
  require a mapped term to be typed as a class or a property, and the HDL specification lets the
  vocabulary's shapes govern the validity of the output, so the undeclared terms made the case's
  description invalid on its own (the `hdl` command line rejected it with validation on).
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
  (`req-pm-errors-6`, and the load-time clause `req-pm-errors-16`; `req-pm-errors-15` is
  withdrawn, see above); the Unsupported feature row no longer
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
