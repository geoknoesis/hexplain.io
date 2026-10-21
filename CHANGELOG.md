# Changelog

Changes to the Hexplain specification family. Version numbers are per module
(`owl:versionInfo` / `owl:versionIRI`); the family has no single version. Local release
snapshots are recorded under `releases/`.

## Unreleased (changes since snapshot 2026-09-24.2)

### Element index of a repetition

A `repeat` clause can pass the element index to its element arguments and `until` condition as `repeat.index`, so a description no longer needs a self-recursive struct, one nesting level per element, to number its elements. New requirements: `req-hel-reserved-roots-6` (the `repeat` root and where it is valid), `req-hdl-expressions-6` (a compiler rejects `repeat.index` elsewhere), `req-pm-parsefield-37` (a reader binds it) and `req-pm-serialisation-39` (a Writer binds it). Nesting: `req-hel-reserved-roots-7` and `req-hdl-expressions-7` bind `repeat.index` to the innermost repetition whose element arguments or condition contain the expression. The text of `req-pm-parsefield-37` and `req-pm-serialisation-39` now states the same binding for the Processing Model. Cases `pp-repeat-index-nested` and `w-repeat-index-nested` exercise it. The HEL grammar's `Root` production and the reserved-root lists now include `repeat`; `req-hel-formal-grammar-4` changed so that `repeat()` and `x.repeat` are syntax errors like the other roots. No requirement from the last released snapshot changed; running the registry tool also anchored three already-drafted HEL quantifier sentences, `req-hel-ext-quantifiers-5` to `-7`. Cases: `pp-repeat-index`, `w-repeat-index`, `hc-repeat-index-outside-repeat`.
### Reference-engine follow-ups (2026-11-02)

- `dlv:DataLayoutShape`: the constraint that every rule of `dlv:hasConditionalDimensionOrder`
  names the same Dimension nodes as the first rule never fired on a SPARQL engine that evaluates
  a UNION branch before joining it (Jena, TopBraid), as SPARQL 1.1 section 18.2 states: its
  `FILTER NOT EXISTS` sat inside the branches, where `?rule` and `?first` are unbound. The test
  now sits in a top-level FILTER, so the rule is enforced on every conforming SHACL-SPARQL engine,
  not only on pySHACL. The reference engine's Jena replay of the family contracts found it.
- The reference engine's implementation report of the current suite (939 cases, digest
  e2530a9831d3, engine commit 9f44e9f9) is published: 935 cases pass, none fail, and 4 are
  skipped as not applicable (two refusals of a codec the engine decodes, and the two
  chunk-order cases it does not claim). The Writer claim cites it, all 88 Writer cases passing.
- `araster:SampleArrayShape`: the unterminated-list branch of the dimension-list constraint bound
  its list head inside the branch for the same reason. Any such list is also caught by the
  missing-cell and cycle branches, so no result changes.
- HEL: `req-hel-array-values-4` is changed. The review fixes of 2026-11-01 made any array value or
  struct node an error as the result of a `bddo:valueFromExpression`, which refused a derived field
  that names one of two version-specific repeated fields (ISO-BMFF `iref`'s `toItemIds`, a
  pattern the reference engine's bundled profile uses). Only a computed array, which is not a
  node of the parsed tree, is now an error there; an array node or a struct node reached by an
  accessor is named by the derived field, as before 2026-11-01. The `hexplain:valueExpression`
  rule is unchanged. The name binding table's row for `bddo:valueFromExpression` follows.

### Review fixes (2026-11-01)

A six-area review of the specification found 77 problems; this section records their fixes.

**HEL arrays, element-scoped arguments and parameters.** HEL now defines **array values**: an array
node, or an array a `quantifiers` function computes (`project`, `repeatValue`, `concatArrays`,
`slice`, `integralScan`, `patchValues`), with subscript, `len`, no comparison, no byte extent or
holder, and never the result of a value expression (req-hel-array-values-1 to -4). The second
argument of `all`, `any`, `countWhere`, `sumOf` and `project` is an **element-scoped argument**;
every other argument is evaluated once, before the call (req-hel-ext-quantifiers-1, -2, -8 to
-11). Each function of the group states its argument types, ranges and errors, and an exact charge
against the element budget, made after argument checks and before allocation
(req-hel-ext-quantifiers-4 to -6, -12); the error table and 84 new vectors cover them, and
`tools/test_hel_vectors.py` requires a value and an error row per function. Specification coverage
credits a requirement to named HEL vector rows (status `hel-vector-cited`, checked to exist), and
`pp-hel-computed-array-result` (939 processor cases) shows a computed array is no field value;
req-hel-ext-quantifiers-9, -10 and -12 are recorded as not observable by a black-box case. The group was extended
before the HEL 1.0 snapshot, and the feature token `hel-ext-quantifier` names the whole group.
req-hel-ext-quantifiers-7 is withdrawn: an evaluator without the group rejects it at load time
(req-hel-extension-groups-1). Node and array parameters now work in HEL `param` paths, in
ParseField (req-pm-parsefield-11, req-pm-context-4), in HDL's `ParamType` grammar (`array`, `node`)
and in BDDO. The limits table names `maxHelDepth`, `maxHelLength`, `maxTriples` and `maxFindings`,
and req-pm-resource-limits-4 covers every limit. Also changed: req-hel-reserved-roots-3,
req-hel-key-resolution-2, req-hel-name-binding-1, req-hel-conformance-8,
req-pm-computed-values-9, req-hdl-parameters-2, req-hdl-expressions-1. The Processing Model's
cryptography non-goal now excepts the scoped-key ciphers and `menc:VerifyCRC32`, which run only
when a description names them.
Requirements of the quantifiers group changed: req-hel-ext-quantifiers-1, req-hel-ext-quantifiers-2,
req-hel-ext-quantifiers-4, req-hel-ext-quantifiers-5, req-hel-ext-quantifiers-6; added:
req-hel-ext-quantifiers-8 to req-hel-ext-quantifiers-12; withdrawn: req-hel-ext-quantifiers-7.

**Shapes.** Arity is checked for every kind of struct, delimited tables and tree documents
included. `bddo:hasArgument` is rejected unless the type it accompanies is a struct that declares
parameters, and `bddo:dispatchDefault` may not name a parameterised struct
(`bddo:DispatchDefaultShape`). A derived field may not also state `bddo:hasDispatchTable` or
`bddo:hasArgument`. `bddo:bcd false`, the default, no longer counts as an integer-only
representation, and every BCD and numeric-representation rule reports its own message. The
deprecated `bddo:integer`, `bddo:float` and `bddo:hasEndianness` are accepted and reported at
`sh:Warning`; `bddo:hasEndianness` is constrained like `bddo:endianness`. Tree-document fields
reject every byte-offset form. In DLV, a layout chunked through `dlv:hasConditionalDimensionOrder`
must declare its chunk offsets, each order rule must name the same dimensions exactly once, and the
Hilbert key width is log2 of the largest padded count. A run that omits
`conf:versionScopingApplied` may not report `conf:NotApplicable` for a version-scoped requirement.
`hxf:isNoData` compares integer formats exactly, and `hxf:bytes` is unbound when the slice leaves
the node. The structure aspect adds `st:elementCount` and `st:byteCount` beside `st:count`,
documents `st:hasMember` and `st:hasItem`, links its terms to their tabular counterparts with
`rdfs:seeAlso`, and gains test fixtures. 49 authored contracts witness these fixes.

**Codecs.** The LZ4 suite's overlapping-match frame broke the block format's end-of-block rules
and liblz4 rejected it; a conforming frame verified with liblz4 1.9.4 replaces it, and the LZ4
vector suite moves to version 2. The eleven new codecs are valid top concepts of their schemes.
Their definitions state the AES-GCM tag position and AAD order (prefix, then `aad`), the AES-CTR
counter (the whole 128-bit block incremented big-endian, as SP 800-38A specifies), nonce
uniqueness, the error each failure raises (a wrong-length iv is a Description error, a tag
mismatch Checksum), trailing data and length mismatches for the raw compressors, Hadoop LZ4's
zero-sized blocks and ByteResource's check order. New known-answer vectors pin encoder output,
including NIST GCM Test Case 4 and SP 800-38A F.5.1. ByteTranspose is related to Shuffle,
Snappy to SnappyRaw and LZ4Block to HadoopLz4; the codec page lists all 45 suites and documents
the manifest's `inputs`; each suite's sources say how its vectors were verified; shared parameter
specs are labelled by every contract that uses them; every current security marking is a top
concept of its scheme. The Checksum row of the error table names AEAD tag mismatches.

**Conformance tooling.** The comparator reads processor JSON strictly (repeated members and
NaN/Infinity are rejected), an error case requires the error artifact, simple literals equal their
`xsd:string` form and HDL Compiler decimals compare by value. Physical-extent annotations are
ignored only when they are valid `xsd:nonNegativeInteger` values on resources the expected graph
or the case's base mints. HEL canonicalisation and round-trip dependency analysis are iterative, so
512-deep expressions compare. `run_suite.py` ignores a reported base when the manifest gives one,
accepts `--category-map`, keeps Windows backslashes in command templates and requires `--claims`
for an implementation report. Report validation checks historical reports against a new register of
past suites (`reports/suite-digests.json`) and rejects results that contradict applicability,
claims outside the closed lists and future run dates. `test_doc_terms` derives its prefix table
from the family and now checks every Hexplain prefix; `test_strict_profile` fails when it lints
nothing; the review package holds only tracked files; `tools/test_types.py` allows the four JSON
readers' `-> Any` returns. Suite citations are corrected: req-pm-resource-limits-3 is not
suite-testable, and the conditional-layout and custom-CRC citations are narrowed.

**Documents and claims.** The homepage example uses real terms (`bddo:dataType`,
`bddo:endianness`, `araster:width`, `acolor:colorSpace`, `aprov:platformName`). The landing and
architecture pages describe alignment as the design rules do (`rdfs:seeAlso`, SKOS for concepts
only) and list the structure and bundle aspects; the architecture page gains an hx-structure row,
hx-protection in its import diagram and `st` as the one prefix exception, also documented on the
ontology-design page. The Writer claim now cites the report of suite 665b443c5f01 as superseded,
the quantifier claim lists all 20 functions, README counts 39 module rows, CONTRIBUTING documents
`_build_ontology_docs.py`, `_build_conformance_page.py`, `_requirement_ids.py` and the conformance
case procedure and corrects the order of the coverage builders, and `_build_ontology_docs.py` keeps
the print-stylesheet link on the pages it writes.

### Outcome contracts, scoped round trips and validation evidence

Required-error cases now reject successful process/artifact outcomes, even when their bodies
look like errors. Evaluator alternatives must likewise use a nonzero exit and the error artifact.
Round-trip exemptions now use field paths and dependency analysis for encoded lengths,
checksums and derived expressions; unrelated names, constants and decoded-stream metadata
remain compared, and exemptions preserve node kinds, binding and shape. Unproved dynamic
relationships remain strict rather than receiving a blanket exemption. Windows gate cleanup
falls back to killing the gate when taskkill returns failure as well as when it raises.
Validation evidence now hashes configuration, workflows, publication files, binary fixtures,
release archives and root inputs, excluding runtime caches and explicit output records.
Regression controls cover the reported false passes, scoped repeated fields, bounded regions,
configuration changes during a run and custom result-file destinations.

### Comparator artifact boundaries

Malformed evaluator error artifacts no longer pass success cases by matching an absent or
null `orError`. An alternative error requires an explicit registered category and a matching
reported category. A Physical Parser error artifact cannot pass as a successful parsed tree
merely because their JSON contents match. Category mapping is applied consistently to JSON
and RDF evaluator alternatives. Regression controls reject malformed errors against every
success expectation and preserve the suite's expected-artifact controls.

### Validated report writes and run provenance

The conformance runner checks report metadata before launching processors and validates the
complete result before publication. New reports and completed reports share an atomic writer:
validation, serialization or replacement failures leave the existing file unchanged. The
completion command accepts `--suite` for validation against the matching suite. Report
validation now requires a nonempty runner identity and a valid ISO 8601 UTC timestamp,
including for retained historical reports. Regression tests cover invalid revisions, missing
or malformed provenance, unchanged files after rejected completion, and interrupted writes.

### Follow-up conformance and review-package corrections

Windows processor invocations now enter a Job Object before launching the implementation;
closing the job also terminates descendants whose parent has exited. Partial runs cannot
write implementation reports. Shared applicability rules prevent absent commands from
silently skipping claimed cases and reject applicable SKIPs in current-suite reports.
Report validation checks SHA-256 syntax, totals and duplicate identifiers for all suites;
coverage of a different suite is explicitly unverified unless that suite is supplied.
Historical publication retention checks structure without certifying coverage. The review
archive now contains the conformance tooling and data, preserves exact case bytes, and is
tested by executing its conformance and report gates from an isolated extraction.

### Conformance runner and CI

The conformance runner now enforces process exit status against success/error artifacts,
rejects conflicting artifacts, bounds combined stdout/stderr capture, and terminates timed-out
or flooding process trees. Compiler diagnostics remain separate from stdout. Malformed
processor output and launch failures become per-case failures without dropping subsequent
results or the implementation report. Regression probes exercise these failure paths and
round-trip output parsing. The offline CI matrix now covers both supported Python versions,
3.11 and 3.12, on Windows and Linux. Independent semantic acceptance remains pending; the
review candidate is regenerated against the corrected tooling without assigning a reviewer
or recording an acceptance decision.

### Contract, coverage and review-package follow-ups

- Hardened JSON report comparison with exact scalar types and order-independent one-to-one
  finding matching, including overlapping partial expectations.
- Bounded processor artifact reads to 16 MiB per artifact and isolated parsing/comparison
  under a subprocess deadline, with failure-local diagnostics and regression probes.

- Added 56 authored protection, acquisition and temporal contracts, including missing,
  duplicate, wrong-class and numeric boundary counterexamples. Every documented module
  publishing shapes now has positive and negative authored contracts.
- Capability schema 2 reports authored contracts separately from competency TSV references;
  traceability includes both corpora without equating term mentions with semantic acceptance.
- Corrected all 38 module rows and resource counts in the independent-review instructions;
  package checks prevent drift and include capability evidence. Independent sign-off remains pending.

- Validate acceptance dates, decision consistency and explicit module decisions; reject
  malformed records without implying reviewer authentication.
- Resolve repeated-record round-trip dependencies per array element, preserving strict
  comparison for unaffected first records and bounded regions.
- Require diagnostic path, source shape and severity on the same validation result.
- Correct round-trip documentation and inventory every registered normative clause,
  measured SHACL obligation and vocabulary declaration, keeping review-only gaps explicit.

- Added four ordered-layout processor cases (both orders of overlapping cell-type and
  dimension-order rules), bringing the processor corpus to 935 cases. Cell-observation cases
  provide their raw logical tree separately for Writer symmetry checks.
- Execute all six published pure SPARQL bodies with 55 success, boundary and unbound-result
  probes, including registration invariance and negative floors. RDFLib's mixed numeric
  promotion limitation is explicitly scoped in the calibration datatype assertion.
- Explicitly map 27 description/advisory clauses to measured property contracts and three
  affine clauses to executable function bodies; retain inspection-only and external-runtime
  requirements as exceptions, never as completed behavioral tests.

### Codecs for columnar stores, typed parameters and HEL collection functions

The media-encoding register gains 11 concepts with codec contracts and vector suites: the raw
compression streams `menc:SnappyRaw`, `menc:LzoRaw` (with a required `decodedSize`),
`menc:Brotli` and `menc:HadoopLz4`; the reversible `menc:ByteTranspose` (`elementSize`); the
virtual inputs `menc:ByteSource` and `menc:ByteResource`, which return previously bound bytes
or an operation-scoped resource from an empty physical input; the scoped-key ciphers
`menc:AESGCM`, `menc:AESCTR` and `menc:AESGCMSignature`, whose shared `menc:Cipher.*`
parameters name keys by reference and never embed key material; and `menc:VerifyCRC32`. The
vector manifest schema adds `inputs`, operation-scoped external bytes (cipher keys,
additional-data prefixes, resources) that are neither codec parameters nor format fields.
`bddo:parameterType` accepts `bddo:ArrayParameter` and `bddo:NodeParameter`, an existing HEL
array or struct node passed by identity, and HDL spells them `array` and `node`. HEL's
quantifier extension adds collection, byte and integer-text functions (`countWhere`, `sumOf`,
`project`, `repeatValue`, `concatArrays`, `concatBytes`, `slice`, `integralScan`, `modularAdd`,
`integerBytes`, `integerText`, `unicodeText`, `join`, `integerPrecision`, `decimalText`, `floatCast`,
`fromIEEE`, `patchValues`) under requirements for one shared element budget and for ResourceLimit
before an oversized output is allocated (completed by the review fixes above). The Processing Model's `maxQuantifierEvaluations`
now names that shared budget, and three ResourceLimit cases (`pp-limit-collection-output`,
`pp-limit-collection-traversal`, `pp-limit-text-conversion`) bring the processor corpus to 938
cases. The prose term check reads a dotted local name
(`menc:Cipher.keyRef`) as one term.

### Structure aspect (working draft 0.1)

`https://hexplain.io/ns/aspect/structure` (prefix `st`) joins the family: application-independent
decoded records (`st:Record`), named members (`st:Member`, `st:name`, `st:identifier`) and
collection items (`st:Item`), with `st:value` keeping each literal's datatype. Its shapes require
one name per member, at most one identifier and value per member, item or record, and integer
and string datatypes for the declared ranges; 20 authored contracts witness them. Physical layout
stays in BDDO, and format profiles supply member meanings. The `spatialref` page builder now
carries the requirement wording settled on 2026-10-15, so regenerating the page no longer reverts it.

### Module versions

Every module whose canonical Turtle differs from snapshot 2026-09-24.2 has a new version IRI
naming the version that snapshot froze as `owl:priorVersion`, and a `dcterms:modified` of the day
its canonical Turtle last changed (2026-10-13; 2026-10-14 for aspect/geometry, aspect/tabular, aspect/raster and
aspect/sampling; 2026-11-01 for bddo, register/media-encoding, aspect/structure and req/requirements). Most changed only in their generated
documentation (below); `owl:versionInfo` is now the bare version number everywhere, and the four
working drafts say so with `schema:creativeWorkStatus "working draft"`. aspect/color,
aspect/encoding, aspect/fsmeta, aspect/networkflow, aspect/pointcloud, aspect/security and
aspect/time, unchanged until then, took a new version when their generated documentation was
rewritten.

| Module | Was | Now |
|---|---|---|
| archive (axv) | 1.2 | 1.3 |
| aspect/bundle | 1.4 | 1.5 |
| aspect/color | 1.0 | 1.1 |
| aspect/encoding | 1.1 | 1.2 |
| aspect/fsmeta | 1.1 | 1.2 |
| aspect/geometry | 1.3 working draft | 1.4 (working draft) |
| aspect/integrity | 1.1 | 1.2 |
| aspect/networkflow | 1.2 | 1.3 |
| aspect/packaging | 1.1 | 1.2 |
| aspect/pointcloud | 1.1 | 1.2 |
| aspect/protection | (new) | 1.0 |
| aspect/provenance | 1.2 | 1.3 |
| aspect/raster | 1.2 working draft | 1.3 (working draft) |
| aspect/sampling | 1.1 | 1.2 |
| aspect/security | 2.1 | 2.2 |
| aspect/signal | 1.1 | 1.2 |
| aspect/spatialref | 1.3 working draft | 1.4 (working draft) |
| aspect/structure | (new) | 0.1 (working draft) |
| aspect/tabular | 1.1 | 1.2 |
| aspect/time | 1.0 | 1.1 |
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
| register/protection | (new) | 1.0 |
| register/us-nato-security | 1.2 | 1.3 |
| req | 1.2 | 1.3 |
| req/requirements | (new) | 1.0 |
| req/shapes | 1.2 | 1.3 |
| video (vdv) | 1.1 | 1.2 |

### The reference implementation's report of the then-current suite (2026-10-15)

The implementation report of the then-current suite (931 cases, digest 665b443c5f01, since superseded) is published under
`specification/conformance/reports/hexplain-tools/`, written by the engine's `conformanceReport`
task at engine commit 1d3df9ad and published unchanged: 927 PASS, 0 FAIL, 4 SKIP (two codec-refusal
cases for codecs it decodes, two chunk-order cases for features it does not claim), the Writer
class 88 of 88. The engine also passes the round-trip mode (247 of 249 trees; the other two need
the unclaimed chunk features). `writer` stayed claimed, then on a report of the current suite:
`reference-engine-claims.json` and the Processing Model's reference-implementation note say so. The
conformance page's table of published reports marks each report of an earlier suite superseded
(`#superseded-reports`), and `tools/test_types.py` holds `-> Any` returns to the two in use.

### Points the reference implementation found (2026-10-15)

- **Packed decimal is unsigned only.** `bddo:BcdShape`, the `bddo:bcd` comment and the Processing
  Model already made `bddo:bcd true` on a signed type a description error, but the Writer cases
  `w-bcd`, `w-bcd-negative` and `w-bcd-too-many-digits` stated it on a `bddo:int16`. Their field
  `s` is now a `bddo:uint16`; `w-bcd-negative` keeps its intent, a negative value written into an
  unsigned packed-decimal field being a validation error. The new case `pp-bcd-signed` asserts the
  description error.
- **Codec HEL literals compare as HEL.** `hexplain:parameterExpression` and
  `hexplain:codecFromExpression` have rows in HEL's name-binding table, and the conformance
  comparator canonicalises their literals as it does every other HEL-bearing property's
  (`hc-codec-switch-and-session` and its YAML twin).
- **Round trips honour an allowed error.** `run_suite.py --round-trip` passes a Physical Parser
  case whose manifest allows an error outcome (`orError`) when the writer or the parser under test
  refuses with that category, with no symmetry to check (`pp-limit-regex-idle-iterations`,
  `pp-limit-regex-counted-bound-above-cap`); the runner's self-test probes it.
- **HDL clauses for two origins.** `@at <expr> from field-start <name>` compiles to
  `bddo:offsetBase bddo:fieldStart` and `bddo:offsetBaseField` (req-hdl-clauses-9; an ERROR when
  the name is not an earlier field of the struct), and `@align <n> from struct|stream` to
  `bddo:alignmentOrigin` (req-hdl-clauses-10); on the YAML surface `at: { offset, from, field }`
  and `align: { to, from }`. The list of BDDO terms without a clause names the VAX formats
  `bddo:vaxD` and `bddo:vaxG` beside `bddo:vaxF`, and a struct's alignment origin. Cases
  `hc-offset-field-start` (and its YAML twin), `hc-offset-field-start-later-field`,
  `hc-offset-field-start-not-a-field`, `hc-offset-field-start-yaml-no-field`,
  `hc-offset-field-yaml-other-base`, `hc-align-origin` (and its YAML twin),
  `hc-align-origin-unknown` and `hc-float-format-vax` (and its YAML twin).

### Classes and terms for the bundled table, geometry and raster profiles (2026-10-14)

The engine's bundled profiles had nothing to map some root structs and stored facts to. The
modules keep their unreleased versions (tabular 1.2, geometry 1.4, raster 1.3, sampling 1.2).

- **aspect/tabular.** `atab:Table` (a schema of columns and the records under it) and
  `atab:Record` (one row), linked by `atab:hasRecord`; `atab:TableShape`, `atab:RecordShape`
  (a record belongs to at most one table) and `atab:RecordCountShape` (no more records than
  `atab:rowCount`). A dBASE file's root struct maps to `atab:Table`, its repeated record struct
  to `atab:Record`.
- **aspect/geometry.** `ageom:Geometry` (one encoded geometry, at every nesting level),
  `ageom:GeometryRecord` (a stored geometry with its container's header, such as a GeoPackage
  geometry blob), `ageom:hasGeometry` and `ageom:hasMember` (acyclic membership of a
  multi-geometry or collection); `ageom:GeometryShape`, `ageom:GeometryMembershipShape`,
  `ageom:GeometryRecordShape`. A WKB root struct maps to `ageom:Geometry`, a GeoPackage blob's
  to `ageom:GeometryRecord`.
- **aspect/raster.** `araster:formatNoDataValue`, the no-data value a format fixes when the file
  stores none (DTED -32767, SRTM -32768), overridden by a stored `araster:noDataValue`; stored
  bounds as the file states them, `araster:boundsMinX`, `araster:boundsMaxX`,
  `araster:boundsMinY`, `araster:boundsMaxY`, with `araster:boundsRegistration`
  (`araster:nodeRegistration` or `araster:cellRegistration`, class `araster:BoundsRegistration`),
  distinct from the computed geotransform; a stated value range, `araster:minimumValue` and
  `araster:maximumValue`; shapes `araster:FormatNoDataShape`, `araster:StoredBoundsShape` (a
  minimum bound is not above its maximum) and `araster:ValueRangeShape`. `araster:sampleScale`
  and `araster:sampleOffset` may be stated of a grid whose format has no band structure; a band's
  own value takes precedence.
- **aspect/sampling.** `asamp:sampleFormatName`, the sample format as a literal token
  (`"signedInteger"`, `"unsignedInteger"`, `"float"`), because a mapping from a field or a
  constant yields a literal and `asamp:sampleFormat` takes an IRI;
  `asamp:SampleFormatAgreementShape` holds the two to the same format when both are stated.

### Integration of round 2: the forthcoming terms are normative (2026-10-14)

The Processing Model's informative note on forthcoming terms (`#forthcoming-terms`) is gone: the
ontology terms it announced exist, and each point now stands in the section it named, behind
requirement identifiers.

- **What makes a description valid** (`#valid-description`, Inputs and Outputs). A description
  is valid when validation yields no `sh:Violation`; a processor must not refuse a description,
  or report it invalid, for `sh:Warning` or `sh:Info` results alone.
- **The alignment origin** (`#alignment-origin`). `bddo:alignmentOrigin` selects
  `bddo:streamOrigin` (the default) or `bddo:structOrigin` for a subject's `bddo:alignment` and
  `bddo:padTo`; the Writer's padding rule (req-pm-serialisation-25) measures from the same
  origin. `bddo:alignment` or `bddo:padTo` on a derived field is a description error.
- **Three VAX formats** (`#float-formats`). `bddo:vaxF` is the 32-bit F_floating
  (req-pm-numeric-representation-4); `bddo:vaxD` and `bddo:vaxG` are the 64-bit D_floating and
  G_floating; a 64-bit `bddo:vaxF` is the deprecated spelling of `bddo:vaxD`, read as it is and
  reported at `sh:Warning`. The conversion rule (req-pm-numeric-representation-6), the width rule
  (req-pm-numeric-representation-7) and the Writer's VAX rules (req-pm-serialisation-34,
  req-pm-serialisation-36) cover the three. `bddo:bcd` on a signed type is a description error.
- **Offsets from a sibling** (`#field-start`). `bddo:offsetBase bddo:fieldStart` with
  `bddo:offsetBaseField` counts from the start of an earlier sibling; it is a fixed-origin base
  for the negative-value rule (req-pm-parsefield-32, req-pm-parsefield-7), a target outside the
  region is a bounds error, and a base field not read before the offset is a description error.
- **Protection is a non-goal** (`#non-goal-protection`): the protection aspect describes and
  obliges no processing.
- **Every codec contract states `hexplain:encodes`** (`#codec-contracts`), true or false.
- **A non-positive stride** that a field or an expression supplies is a description error when
  the layout is resolved (`#data-layouts`).
- **The history replay judges archived cases as their gates did, and records what changed.**
  `python tools/test_release_contract.py --replay-history` failed on snapshot 2026-09-06.1. The
  replay validated retained family contracts without `allowWarnings` and without SHACL Advanced
  Features, so a snapshot's advisory-only cases failed against its own shapes; it now uses
  `test_family_contract.case_failure`, and Advanced Features for the TSV corpora. Against the
  current shapes, 113 archived cases (285 copies across the seven snapshots) have another outcome
  because of recorded changes; `releases/compatibility.json` lists each under its change, and
  the replay fails on a divergence it does not list or a listed one that no longer occurs. No
  archive is rewritten. One of those changes was not in this changelog: a `bddo:Checksum` must
  state the start and the end of its covered range (since 2026-10-12), which the retained BDDO
  contracts sharing a range-less checksum prelude no longer meet.
- **Suite cases.** New: `pp-align-struct-origin-padding`, `pp-align-struct-origin-field`,
  `pp-align-derived-field`, `pp-offset-field-start`, `pp-offset-field-start-outside`,
  `pp-offset-field-start-absent-base`, `pp-float-vax-d-g`, `pp-float-vax-f-64-deprecated`,
  `pp-valid-despite-warning`, `pp-layout-stride-from-field-zero`, `pp-separated-abutting-regions`,
  `w-pad-to-struct-origin`, `w-separated-region-start`. Changed: `pp-float-vax` reads its 64-bit
  field as `bddo:vaxD`; `w-float-vax`, `w-float-vax-infinity` and `w-float-vax-negative-zero`
  write a `bddo:vaxD` and a `bddo:vaxG` field.

### Gate tooling: second review pass (2026-10-13)

No vocabulary, shape or published document changes. The validation evidence that is regenerated
is the constraint ledger and its page, the retained family contracts and the review manifest.

- **Cases are validated against the modules they involve, not the family.**
  `test_packaging_contract`, `test_video_math`, `test_numeric_boundaries`,
  `test_conformance_competency`, `test_vocab_shapes` and the ledger builder loaded all forty
  modules as data and as shapes for every case. `specgraph.modules_used_by(case)`
  (`tools/_module_selection.py`) now names the modules a case involves: the homes of its terms,
  every module with a shape aimed at a class, property or node the case states (including the
  classes the family gives a term the case mentions), and what those import. The assertions are
  unchanged and so is every pySHACL outcome: verdict and result multiset are identical before and
  after for the 58 cases of the four gates and for all 151 vocabulary fixtures.
  `tools/test_specgraph.py` checks the selection against every target in the family and
  validates two fixtures both ways.
- **A shapes graph is never also a data graph.** pySHACL writes `owl:Class rdfs:subClassOf
  rdfs:Class` and `owl:DatatypeProperty rdfs:subClassOf rdf:Property` into the graph it is given
  as shapes. `test_packaging_contract` used one graph in both roles, so every case after the first
  was validated with those axioms in its data, where they change what `sh:class` accepts; no
  verdict of its eleven cases depended on it, but the order of cases could have decided one.
  `specgraph.context_and_shapes` returns two graphs, and the gates and the ledger builder use it.
- **The constraint ledger is measured in parallel and stored compactly.**
  `tools/_constraint_coverage.py` runs the corpora as 71 tasks across a process pool
  (`tools/_coverage_corpora.py`); the result is byte-identical at 8 and at 12 workers, and with
  the old whole-family context it reproduces the previous ledger exactly. Measuring takes eight
  to ten minutes on a host whose processors are fully used by other work, where it took forty.
  With cases validated in context, 33,644 of the 234,248 booked evaluations are gone: each was an
  outcome the family's own triples produce with no case at all, booked to whichever case was
  running. All 1,991 obligations are still two-sided. `constraint-coverage.json` is one JSON
  document with an obligation per line and cases as indices into a name table (16.5 MB to
  2.2 MB), read back with `_constraint_coverage.read_ledger()`; `constraint-coverage.html` holds
  the names once and fills a list when it is opened (14.6 MB to 2.6 MB), and
  `test_constraint_coverage` now fails unless the page is the ledger rendered. The page stays
  tracked because the site is served from the committed tree.
- **Gate scheduling.** `tools/gate-costs.json` is the tracked record of each gate's duration,
  peak RSS and process count, written by `python tools/run_gates.py --strict --record-costs` from
  a complete, unfiltered run and merged by gate; the runner orders gates and estimates memory
  from it, in CI as locally, and no longer reads the ignored `.gate-results/summary.json`.
  `--derive-timeouts` writes every timeout in `tools/gates.json` as ten times the recorded
  duration, rounded up to five minutes, from five minutes to an hour, and `test_gate_manifest`
  asserts that for every gate, that the workflow job limits leave room for the gate timeouts
  (`site.yml` allowed twenty minutes for gates that could take thirty-five), and that the
  figures under "Gate cost" in `CONTRIBUTING.md` are the record's own. A gate's effective process
  count, `min(declared, max(1, cpu // jobs))` and never more than eight, is both what the process
  budget counts and the `HEXPLAIN_GATE_WORKERS` the gate is given; the cap holds on the
  environment path too. The memory budget is read from the host at every scheduling decision,
  against what the running gates hold, or fixed with `HEXPLAIN_GATE_MEMORY_MB`;
  `test_gate_runner` pins it (on a host with less than 1.5 GiB free its three probes were run one
  at a time and timed out waiting for each other) and proves that a tight budget serialises. A
  `taskkill` that hangs or is missing no longer aborts the run. `_gate_cost.py` reports wall
  clock and the sum of durations separately; `pytest tools` collects the offline gates of
  `gates.json` with their timeouts.
- **Types and complexity.** `python -m mypy tools` runs (explicit package bases) and
  `tools/test_types.py` gates it: untyped definitions are disallowed and bodies checked. mypy
  1.20.1 is in both hash-pinned locks. `ruff.toml` adds ANN and C901 at a complexity of 15; the
  functions above it are split, as is the 394-line probe builder of `_review_mutation_cases`
  (the 150 probes are unchanged, compared as graphs). The modules of the conformance suite, the codec tooling,
  the requirement registry and the shape-text renderer, and the expectation half of
  `test_vocab_shapes`, do not meet the new rules yet and are listed (`ruff.toml` per-file
  entries, `PENDING` in `test_types`); `test_lint` and `test_types` fail when a listed module no
  longer has a finding, so the lists only shrink.
- **Smaller points.** Every `_*_cases.py` library builds its prefix declarations with
  `prefix_block()` from `PREFIXES` (each case's graph is isomorphic to what it was, and
  `family-contracts.json` is rewritten from them). `test_lint` rejects a text write without
  `newline=`. `tools/_build_family_contracts.py --write/--check` replaces the `--write` mode of
  `test_family_contract`, which only checks. The family pickle cache keeps its three newest
  entries and a failed write leaves no temporary file.

### Second re-review of the normative documents (2026-10-13)

- **Registry entries read alone (F16).** `tools/_requirement_ids.py` gives a `context` to every
  requirement that cannot be read on its own: a list head (a sentence ending in a colon or in
  "as follows.") records what it introduces -- the items of the list or table it governs, the
  grammar after it, or the rules that follow in its paragraph -- and a sentence shorter than 60
  characters records its table row (header cell first) or the term its definition belongs to, and
  the sentence before it. No requirement text or hash changes. `test_conformance_suite.py` fails
  on a live entry of either kind without a context.

- **Serialisation rules completed (N1).** Processing Model, Serialisation:
  - *Extent inference has its own requirements.* Rule 3 is restated as requirement sentences
    (req-pm-serialisation-26 to req-pm-serialisation-32): the extent of a field without a region
    (bits, fixed width, the shortest varint); the separator byte; a literal region filled or
    refused; an encoded field in a literal region (longer: validation error; shorter: written
    only when the filled region decodes to the bytes that were encoded); a scalar under a bound
    length; a terminated field; a to-end `repeatUntil` sequence not padded.
  - *A scalar sized by a bound `bddo:sizeFromField`* (previously readable two ways): the bound
    length is the region. A `bddo:trimNull` string is NUL-padded to it and a text number padded
    as rule 5 states; any other value must be exactly that long, and a longer value is always a
    validation error. An unbound length field is still filled with the value's own length.
    req-pm-serialisation-23 (rule 5) says so for the `trimNull` string and adds that an infinite
    Float in a text number is a validation error.
  - *Numeric representations* (new rule 9, req-pm-serialisation-33 to req-pm-serialisation-38):
    `bddo:ibmHexadecimal`, `bddo:vaxF` and `bddo:bfloat16` fields are written as the bit pattern
    that reads back as the value, and a value with none is a validation error (NaN or an infinity
    in IBM or VAX, a magnitude out of range, a negative zero in VAX, a significand the format
    cannot carry, a binary32 with low bits set in bfloat16); a `bddo:bcd` field is written as
    zero-padded digits, a negative value or one of too many digits being a validation error;
    `bddo:fixedPointScale` changes nothing (the tree holds the raw integer, written unchanged);
    an IEEE 754 field is written as the nearest value of its width, a finite value beyond the
    width's range being a validation error. Scope is now rule 10.
  - req-pm-serialisation-18 (rule 7): an encode output that exceeds the decoded-byte limit is a
    resource-limit error; the Writer class admits the category.
  - req-pm-serialisation-24 (symmetry): *isomorphic* is defined in its own paragraph
    (`#tree-isomorphism`): the same keys, node kinds, array lengths and values, except a
    recomputed derived value (the length of an encoded field, a checksum whose covered range
    includes one), which must equal its recomputation over the written stream. The refusal
    families are listed completely (`#write-refusals`): four validation families, Unsupported
    feature, a description error and the resource-limit error, with the three a parsed tree can
    meet.

- **Writer class extended, and a round-trip mode (N2).** Thirty-four Writer cases
  (`tools/conformance/cases_writer_forms.py`, 86 in the class): the shortest varint; a to-end
  `repeatUntil` sequence not padded; a parameterised struct and a conditional data type (selected,
  default, wrong members); LSB-first bit fields and a field-level `bddo:bitOrder`; IBM, VAX and
  bfloat16 floats and packed decimal, each with its no-inverse refusals; a fixed-point field; a
  terminator inside the value; an offset target before the stream; a pipeline whose kinds do not
  connect (Description); an encode output beyond the decoded-byte limit (ResourceLimit: the class
  now admits the four categories a Writer raises); an encoded field in a literal region (fits,
  overflows, too short); a `trimNull` string under a bound, an unbound and a too-short length; an
  infinite Float as text; and `w-codec-compressor-round-trip`, a Deflate field with
  `"verify": "round-trip"`, whose stream is parsed back with `--pp-cmd` and compared with its
  `expected.json` instead of with bytes. Existing cases cite the new extent requirements they
  exercise (`w-region-filled`, `w-region-overflow`, `w-separated-tokens`,
  `w-length-terminator-included`).
  `run_suite.py --round-trip` runs the symmetry requirement over every Physical Parser case that
  states a tree: the tree is written with `--w-cmd`, the stream parsed with `--pp-cmd`, and the
  trees compared by the Processing Model's isomorphism (recomputed derived values exempt), against
  `specification/conformance/writer/round-trip-expectations.json` (case to `round-trip`,
  `Unsupported` or `Validation`), which is generated with the suite from
  `tools/conformance/round_trip.py` and checked for completeness by `test_conformance_suite.py`.
  req-pm-serialisation-24 is cited by that mode, no longer by two cases, and a processor may
  claim `writer` when the class passes and the mode reports no failure. The comparator keeps the
  sign of a zero (`-0.0` is not `0.0`), and `orError` now applies to a Physical Parser case too.
- **Text encodings are claimed and observed (N3).** Processing Model, Further encodings: the
  list of well-formedness rules is governed by a requirement (req-pm-text-decoding-9, its items
  req-pm-text-decoding-10 to req-pm-text-decoding-13), and a processor states the further
  encodings it decodes in its claims statement, member `encodings`, an array of `bddo:Encoding`
  IRIs (req-pm-text-decoding-14; req-pm-conformance-classes-5 names the member's subject). A case
  manifest gates on `"encodings": {"requires": [...]}`. Thirty-three `pp-encoding-*` cases: a
  decode of each of the twelve further encodings and every refusal point (UTF-32 surrogates,
  values beyond U+10FFFF and partial code units in both byte orders; UCS-2 surrogates, paired and
  lone; the five unassigned bytes of windows-1252 and the three of ISO-8859-7; a Shift_JIS lead
  byte without a trail byte, a trail byte out of range, 7F, and an unassigned pair).
  `reference-engine-claims.json` lists the engine's seventeen encodings.
- **An observable for chunk order (F17).** A Physical Parser case may ask for the cells of a
  layout field (`"cells": [...]` in the manifest, `{cells}` in the command template;
  conformance page, Layout cells): the tree then gives the field as its cells in logical order,
  each addressed through the chunk table. `pp-layout-cells-morton` and `pp-layout-cells-hilbert`
  cite req-pm-data-layouts-3, which leaves the list of requirements no case can observe.
- **Spatial-reference rules bound to no processor class (N6).** req-spatialref-document-2 now
  binds the description (a description does not use `asref:pixelRegistration` to shift the
  affine; audience `description`), with the evaluation rule a SHOULD on a consumer
  (req-spatialref-document-12); req-spatialref-document-3, req-spatialref-document-10 and
  req-spatialref-document-11 are SHOULDs on a consumer that evaluates the transforms, which no
  conformance class of the Processing Model does (the hxf function library defines the affine
  ones). Six entries leave the not-suite-testable list in all (these four,
  req-pm-data-layouts-3 and req-hel-ext-text-8).

- **The cost of a regular-expression match (HEL-RE).** HEL, group `text`: a processor bounds
  the cost of a match including the iterations that consume no input (req-hel-ext-text-9), may
  refuse with a ResourceLimit error a pattern whose counted quantifier exceeds 65,535 or whose
  nested bounds have a product above 1,000,000, and does not refuse a pattern within both for
  its counted quantifiers (req-hel-ext-text-10). The Processing Model's match-cost row counts
  idle iterations. Cases `pp-limit-regex-idle-iterations` (`((){20000}){200000}`: true or a
  ResourceLimit error, by `orError`), `pp-limit-regex-counted-bound-above-cap` and
  `pp-limit-regex-counted-within-caps`; four vector rows. req-hel-ext-text-8 is now cited by a
  case. req-hel-conformance-9 says that a typed expectation of a vector row fixes the type.
- **HDL: names that must stay apart, and exact YAML mappings.**
  - *IRI Minting.* The table gains the rows for a top-level enum, a dispatch table, its arms, an
    asset's part and a top-level field. Two declarations of one document that mint one IRI are
    an ERROR (req-hdl-iri-minting-1), never renamed, dropped or merged (req-hdl-iri-minting-2).
  - *Dispatch arms.* req-hdl-modules-4: every string-keyed arm carries the suffix `.str` and no
    integer-keyed arm does (`T.arm.ftyp.str`, `T.arm.7.str`, `T.arm.7`); the suffix was written
    only for a string key that spelt an integer, which let the string keys `"7"` and `"7.str"`
    share an IRI. `hc-dispatch-arm-iris` and its YAML mirror expect the new IRIs. **Breaking for
    compiled descriptions that name an arm of a string key.**
  - *Modules.* Two different documents of one compilation with the same ontology IRI (the base
    namespace without one trailing `#` or `/`) are an ERROR on the import that brings in the
    later one; a diamond import of one document is not (req-hdl-modules-5).
  - *YAML Surface.* An unknown key is an ERROR in every mapping of the document, the nested
    clause mappings listed by name, and so are a listed key that nothing reads where it stands
    and a clause mapping without its defining key (req-hdl-yaml-6). A listed key whose value is
    of the wrong kind is an ERROR (req-hdl-yaml-7): scalars are typed (strings, flags that take
    `true` or `false` only, expressions), a null reads as the key left out where a scalar is
    taken and is an ERROR where a mapping or sequence is required, and a value usable only
    through its string form is refused. The key table's `sync` row agrees with the prose (an
    unquoted hex scalar or `{ hex: }`).
  - *Semantic Mapping.* A name in the media-encoding register's namespace that is no concept of
    the register is an ERROR (req-hdl-semantic-2); the WARNING remains for a catalogue-only
    concept the register lists.
  - Thirty-one `hc-` cases (`tools/conformance/cases_hdl_names.py`): `hc-mint-collision-*`,
    `hc-shared-namespace-*`, `hc-yaml-unknown-key-*`, `hc-yaml-value-kind-*`,
    `hc-encoded-with-unknown-register-concept` and `hc-pipeline-unknown-register-concept`.

- **Scope and non-goals in one place (N4).** Processing Model, new informative section
  `#scope-non-goals`, linked from the specification index: streaming; decryption, signature
  verification and error correction (description-only terms may exist and direct no processor);
  speculative or backtracking choice; byte-wise obfuscation transforms, for which a codec
  contract is the extension point; the limits of the Writer; Zstandard dictionaries. The section
  ends with an informative note of four *forthcoming terms*, described ahead of the vocabulary
  revision that adds them and behind no requirement until then: a description is valid when
  validation yields no `sh:Violation` (a Warning or an Info does not invalidate it); an origin
  selector for alignment and padding (the stream's start, the default, or the containing
  struct's); `bddo:vaxF` and two new terms, `vaxD` and `vaxG`, named apart; and `fieldStart`, an
  offset base counting from a sibling field's start.
- **Codec vectors: a parameter is shown by a step that succeeds (N5).**
  `test_codec_vector_completeness.py` counts a declared parameter only when a succeeding step
  passes a value the contract admits, in the direction the parameter applies (the compression
  `level` on an encode step); a step expecting the parameter's refusal no longer counts. Deflate,
  Zlib and XZ gain `round-trip-level-0` and `round-trip-level-9`
  (`tools/codecs/_complete_vectors.py`, confirmed with hexplain-tools 490ff48d). No expectation
  changes, so no suite version is raised.
- **Codec manifests, the lock and typed HEL expectations (N8).** The codecs page states the
  manifest's five members, `unreached` optional, as the schema does. `jsonschema` 4.25.1 is a
  pinned requirement (`requirements.in`; `requirements.txt` regenerated with the documented
  `uv pip compile` command, which also moved `wcwidth` from 0.9.1 to 0.9.2), so every manifest is
  validated against the published schema on every run and the conditional skip is gone.
  `hel-vectors.tsv`: an expected value may state its type (`int:3`, `float:2`), the tree context
  gains `instant` and `asset`, and rows are added for the result types of `abs`, `min` and `max`
  over mixed Integer and Float arguments, for `evaluationInstant()` and for `partExtension()`;
  `test_hel_vectors.py` reads the typed form, checks the tree-context members and requires those
  rows.
- **Reference implementation.** `reference-engine-claims.json` gains `encodings` (the seventeen
  registered encodings the engine decodes) and says that its published report covers the 52
  Writer cases of the earlier suite; the Processing Model's note says the same. Run against this
  suite, hexplain-tools 490ff48d fails ten of the new cases, each an intended change it has not
  made yet: `.str` on every string-keyed arm (2), the shared-namespace ERROR (2), the
  unknown-register-concept ERROR (2), a YAML value of the wrong kind in an optional position
  (`hc-yaml-value-kind-alias-mapping`, `hc-yaml-value-kind-bit-length-sequence`), and two Writer
  cases its runner cannot yet run (`w-codec-compressor-round-trip`, whose `verify` it does not
  read, and `w-codec-encode-exceeds-limit`, whose `limits` it does not pass to the writer). It
  skips the two layout-cell cases with the features it does not claim, and its vendored copy of
  the HEL vectors predates the typed rows. Its own symmetry test agrees with
  `round-trip-expectations.json` entry for entry.

### Ontology re-review fixes (2026-10-13)

The findings of the second ontology review (N1 to N11 and the modelling gaps left open by M8).
Module versions are unchanged: every module changed again under its unreleased version IRI, and
every canonical module's `dcterms:modified` is 2026-10-13. Two modules are new: aspect/protection
1.0 and register/protection 1.0.

- **`req/requirements.ttl` is generated** (N1). `tools/_build_shape_requirements.py` writes one
  `reqs:ShapeRequirement` per named node shape of every module (203, where the hand-maintained
  file covered 81 of 179): the statement is the shape's documented definition, `req:fromStandard`
  the module's label without its version, `req:requirementId` `req-shape-<prefix>-<Local>` always
  with the prefix, and `req:discrepancyType` `req:Syntactic` or `req:Semantic` by the shape's
  constraints (a shape that relates properties or nodes to one another is semantic). The 81
  identifiers minted on 2026-10-12 are replaced; none had been published in a snapshot.
  `tools/test_shape_requirements.py` holds shapes and requirements in bijection.
- **Severity is asserted** (N2). A description is valid when validation yields no result of
  severity `sh:Violation`; `sh:Warning` and `sh:Info` results do not make it invalid
  (Validation contracts, `#description-validity`). A fixture's `# expect:` line takes a severity
  as its last token, a `-valid` fixture declares every advisory result it produces and an
  `-invalid` fixture needs a Violation. `encoding-invalid.ttl` no longer lists an accepted custom
  encoding; `encoding-custom-valid.ttl` uses one and expects exactly the warning.
- **Static errors of the numeric terms are shapes** (N3). `bddo:FloatFormatWidthShape`
  (`bfloat16` at 16 bits, `ibmHexadecimal` at 32 or 64, `vaxF` at 32 or its deprecated 64,
  `vaxD` and `vaxG` at 64), `bddo:BcdShape` (not with `bddo:bitLength`, not on a varint or a text
  number, only on an unsigned type; the `bddo:bcd` comment says so),
  `bddo:FixedPointScaleRangeShape` (outside -4096..4096 is a Warning), and
  `bddo:DerivedFieldShape` now refuses `bddo:alignment` and `bddo:padTo` on a derived field.
- **Every module links its annotation graph** (N4) with `rdfs:seeAlso` on its `owl:Ontology`,
  and each `-doc.ttl` header names `tools/_term_editorial.py` as the source to change. **A
  register is self-describing**: 137 concept definitions moved from the registers' annotation
  graphs into the registers, and the generator no longer defines a register concept.
- **One spelling of the integer family** (N5). Twenty inline unions became
  `sh:node <prefix>:IntegerValueShape` with their bounds; net, video, aspect/raster and
  aspect/sampling carry the shape; `araster:ExtentShape` accepts the same eleven datatypes as
  `araster:PositiveCountShape`; `vdv:audioChannels`, `vdv:frameCount` and the frame-rate terms
  accept every integer datatype within their bounds. `tools/test_integer_value_shape.py` rejects
  an inline integer-family union.
- **New terms** (N6, M8). `bddo:alignmentOrigin` with `bddo:streamOrigin` (the default) and
  `bddo:structOrigin`; `bddo:fieldStart` with `bddo:offsetBaseField`, an offset counted from the
  start of an earlier sibling; `bddo:vaxD` and `bddo:vaxG` beside `bddo:vaxF`, which is now the
  32-bit F_floating and keeps its D_floating reading at 64 bits as a deprecated spelling.
  `hexplain:encodes` is required on every codec contract, like `hexplain:keepsSession`; the 21
  decode-only contracts state `false`. **aspect/protection** (`aprot:EncryptedRegion`,
  `aprot:Signature`, `aprot:ErrorCorrection`, `aprot:ByteRange`) and **register/protection**
  (four ciphers, five signature and authentication algorithms, three error-correcting code
  families) describe protection metadata; a processor is not required to decrypt, verify or
  correct anything.
- **Generated sentences** (N7). A negated conjunction reads "not both ... and ..."; an exclusive
  choice reads "a node that states exactly one of: ...".
- **Single-purpose node shapes** (N8). Eleven shapes carried several node-level constraints
  under one message. The constraints moved to shapes of their own
  (`bddo:SeparatedFieldExtentShape`, `bddo:ChecksumRangeStartShape`,
  `bddo:ChecksumRangeEndShape`, `bddo:CustomEncodingIdentityShape`, `bddo:LocalBindingKindShape`,
  `dlv:CellTypeChoiceShape`, `dlv:DimensionOrderChoiceShape`, `dlv:DimensionExtentShape`,
  `dlv:DimensionChunkExtentShape`), became one constraint (`abnd:PartSpecShape` states one
  `sh:xone`; the value shapes of raster, sampling and spatialref one `sh:and`), or lost a message
  that had no constraint (`bddo:PaddingShape`). `tools/test_shape_messages.py` now refuses a node
  shape with more than one node-level constraint. Results that named `bddo:FieldShape`,
  `bddo:ChecksumShape`, `bddo:LocalBindingShape`, `dlv:DataLayoutShape` or `dlv:DimensionShape`
  as the source of those constraints name the new shape.
- **Codec parameters say what they mean** (N9). Each of the 80 parameter specs of the
  media-encoding register states an `rdfs:comment`; a contract's generated definition lists its
  kind, session, direction, parameters and error categories; the scope note repeated on 114
  contract resources is stated once, on `hexplain:CodecContract` and `hexplain:CodecParameterSpec`.
- **Registered encodings are listed once** (N11). The three `sh:in` lists expand from one
  authoring fragment and `tools/test_encoding_register.py` holds them to the individuals.
  `bddo:CustomEncodingCharsetShape` warns about a custom encoding whose charset is a registered
  encoding's or does not determine a byte order (UTF-16, UTF-32, ISO-10646-UCS-2, UCS-2).
- **`req:RequirementIdentityShape` selects its focus nodes** (req/shapes 1.3). With 203 shape
  requirements in the family graph, comparing every pair of requirements took a minute per
  validation. The shape now has a SPARQL target (`sh:target`) selecting the requirements that
  can share a normalised pair with another: those whose identifier another requirement states
  verbatim, and, when any identifier holds a character the normalisation changes, all of them.
  The constraint and what it reports are unchanged.
- **Stale text** (N10). The architecture page states the number of SHACL-SPARQL constraints,
  which `tools/test_page_governance.py` now checks against the modules; its "Not yet modelled"
  section lists what remains (protection processing, a HEL `offsetof`).

### The reference implementation claims `writer` (2026-10-13)

No requirement text, case or identifier changed; the suite is the 803 cases of digest
`529c1a9c7918`, and module versions are unchanged.

- **`writer` is claimed.** `reference-engine-claims.json` sets `optionalFeatures.writer.claimed`
  to `true`, and the Processing Model's reference-implementation note lists `writer` among the
  claimed features (`tools/test_reference_claims.py` ties the two). The evidence is the one the
  conformance page defines: the engine's `Metawriter` passes every case of the Writer class, in
  its own suite runner and, through its `hexplain-write` command, under
  `run_suite.py --w-cmd "hexplain-write {description} {root} {input} --out {out} --error {err}"`.
  No Writer case was changed to obtain this, and none contradicts the serialisation text.
- **Implementation report of the current suite.**
  `specification/conformance/reports/hexplain-tools/0.1.0-snapshot-529c1a9c7918.json`, a report of
  format version 2 written by the engine's `conformanceReport` task at engine commit `43bf78d1`
  (Windows 11, Eclipse Adoptium 21.0.7, Gradle 8.14.5, Kotlin 2.2.21, Unicode 15.0): 801 PASS,
  0 FAIL, 2 SKIP over the 803 cases -- Physical Parser 466 PASS and 2 SKIP (the two cases that
  check the refusal of `menc:Zstd`, which the engine decodes), Semantic Emitter 49, Bundle
  Processor 13, HDL Compiler 180, Conformance Evaluator 41 and Writer 52, all PASS. The
  conformance page's list of published reports and `coverage.json` carry it; the version-1 report
  of suite `354e7441707e` stays published beside it. The suite digest covers the case directories
  only, so publishing a report does not change it.

### Writer class of the processor conformance suite (2026-10-13)

The suite observes the write direction. No requirement text changed and no identifier was added,
changed or withdrawn; module versions are unchanged.

- **A sixth case class, `writer`.** `specification/conformance/writer/` holds 52 cases named
  `w-*`. A case gives a writer under test a description (`description.ttl`), a root struct
  (`root`) and a logical tree (`tree.json`, in the canonical JSON form of a parsed tree, named by
  the manifest's `input`), and states exactly one of `expected.hex`, the exact bytes of the stream
  (lower-case hexadecimal, white space ignored), and `expected-error.json`, the refusal the rules
  require (`Validation` or `Unsupported`). 29 cases fix bytes and 23 a refusal. It is a class of
  the suite, not a sixth conformance class of the Processing Model: every case requires the
  optional feature `writer`, so the class is skipped for a processor that does not claim it.
- **Every live serialisation requirement is cited** by at least one Writer case
  (`req-pm-serialisation-1`, `-12`, `-14`, `-17`, `-18`, `-19`, `-20`, `-21`, `-22`, `-23`, `-24`,
  `-25`): field order and a consistent tree, fixed values, presence, recomputed and bound lengths,
  counts and checksums, regions and struct sizes, separated tokens, the bit cursor, alignment,
  `bddo:padTo` with `bddo:padByte`, offset-addressed fields, text encodings and canonical text
  numbers, byte order and type selection, encoded fields (`menc:Store`, `menc:Delta`, a codec
  with no `hexplain:encodes`), checksum back-patching, and the constructs outside the Writer's
  scope. The bytes compare exactly, so no case expects the output of a compressing encoder; the
  codec vector suites' round trips remain the evidence for those.
- **Runner, comparator, gates.** `run_suite.py` takes `--w-cmd`: the command is given
  `{description}`, `{root}` and `{input}` (the tree) and writes the stream to `{out}` as the bytes
  themselves, or `{"category": ...}` to `{err}`. `compare.py` compares bytes exactly
  (`compare_bytes`). `test_conformance_suite.py` checks the class's structure (a JSON tree, exactly
  one of the two expectations, well-formed hexadecimal, the `writer` feature required) and fails
  when a live serialisation requirement is cited by no Writer case;
  `test_conformance_comparator.py` tests the byte comparison. `.gitattributes` keeps the class
  directory free of line-ending conversion, as the other five are.
- **Conformance page.** A section *The Writer class* defines the class, its files and the
  command-template contract; the coverage section counts the serialisation requirements
  (12 of 12 MUSTs cited) and has the class's own tables, each serialisation requirement with its
  cases and each case with the outcome it requires. `coverage.json` gains a `writer` member.
- **Claiming `writer`.** The Processing Model's reference-implementation note, its symmetry
  paragraph, the specification index and `reference-engine-claims.json` no longer say that the
  feature cannot be observed: a processor may claim `writer` when it passes the Writer class.
  The reference engine's claim stays `false`: its suite runner does not run the class yet, and
  the claim follows its next published implementation report. The suite digest changes with the
  new class, so the published report (suite `354e7441707e`, already superseded) stays as it is.

### Follow-up pass (2026-10-13)

Nine points left open by the integration review. Module versions are unchanged: bddo 1.3 and
register/media-encoding 1.2 changed again under their unreleased version IRIs.

- **Every contract whose reference implementation encodes says so.** `menc:LZ4`,
  `menc:LZ4Block`, `menc:Zstd`, `menc:XZ`, `menc:LZW` and `menc:PackBits` now state
  `hexplain:encodes true`, beside Store, Deflate, Zlib, Gzip, Delta, FloatingPointPredictor and
  BitReverse: thirteen of the 34 contracts. The other 21 stay decode-only, which is what the
  reference engine implements (the array transforms Shuffle, TypedDelta, FixedScaleOffset,
  Quantize and BitRound, Blosc and BloscLZ, the colour conversions, the CCITT, NeXT, ThunderScan
  and RLE decoders, and the image codecs). Each of the six suites gains a `round-trip` vector. A
  compressor's encoded bytes are its implementation's own, so the encode step expects success
  only and the decode step reads `{"previous": true}` back to the input; LZ4Block passes its
  required `decodedSize` on both steps. `tools/codecs/_complete_vectors.py` builds them.
- **`Description` is declared where a codec raises it.** `menc:Delta` refuses a `rowBytes` that
  is not a whole number of pixels (`elementSize` 2, `rowBytes` 3): each value is one its
  parameter admits, so the load-time check cannot refuse the pair, and the bytes are not at
  fault. Its contract now lists `Description` under `hexplain:raisesCategory`, its suite has the
  vector `row-not-whole-pixels`, and `pp-codec-delta-row-not-whole-pixels` cites
  `req-pm-codec-contracts-6`, which no case cited.
- **UCS-2 byte order.** `bddo:ucs2le` and `bddo:ucs2be` no longer share
  `bddo:ianaCharset "ISO-10646-UCS-2"`, a registry name that determines no byte order and so
  could not tell the two apart: they state none, and their comments say the term gives the byte
  order. A custom encoding has no term to give one, so its `bddo:ianaCharset` MUST name a
  character set that determines byte order (`UTF-16BE`, never `UTF-16` or `ISO-10646-UCS-2`):
  `req-pm-text-decoding-8` in the Processing Model (Further encodings), a rule on a description's author,
  restated in the comments of `bddo:CustomEncoding`, `bddo:ianaCharset` and
  `bddo:CustomEncodingShape`. No shape states it: a pattern over registry names and their aliases
  cannot decide it.
- **A Writer writes the pad byte.** The padding of a `bddo:padTo` is written as the
  `bddo:padByte` declared beside it, and as `0x00` when none is declared; every other fill byte
  stays `0x00`. Serialisation said only that a fill byte is `0x00`, so a Writer following it
  produced padding that a reader verifying `bddo:padByte` refuses. `req-pm-serialisation-15` is
  withdrawn and `req-pm-serialisation-25` replaces it, also saying where `bddo:padTo` padding is written; The
  fill byte (Alignment and padding) and the comment of `bddo:padByte` say the same.
- **Padding of an offset-addressed field.** `req-pm-parsefield-34`: `bddo:padTo` on an offset-addressed field
  applies at the field's target, after its value is read and its checks are made there and
  before the saved cursor is restored; with `bddo:currentPosition`, which restores nothing, the
  cursor is left after the padding. The Addressing step of ParseField and the comment of
  `bddo:padTo` say so. Cases `pp-pad-field-at-offset` and `pp-pad-field-at-offset-checks-first`
  (a failing check is reported, not the padding that would run past the end).
- **Range of `bddo:fixedPointScale`.** A Semantic Emitter MUST support every scale from −4096
  to 4096 (`req-pm-value-mapping-2`, case `se-fixed-point-scale-range`), and a processor MUST raise a
  description error for a scale outside the range it supports rather than emit an approximation
  (`req-pm-value-mapping-3`, which no portable case can observe: the range beyond ±4096 is the processor's
  own). The comment of `bddo:fixedPointScale` says the same. No shape bounds the property: a
  larger scale is not invalid, only not portable.
- **A packed width on a non-integer cell type, whatever its source.** `req-pm-data-layouts-4` makes the rule
  a requirement: a description error raised at load for a literal `dlv:cellBitWidth`, and when
  the layout is resolved for `dlv:cellBitWidthFromField` and `dlv:cellBitWidthFromExpression`,
  never a validation error. Cases `pp-layout-packed-float` (now citing it) and the new
  `pp-layout-packed-float-from-field`.
- **`req-hel-ext-text-7`** gives a neutral example of the Unicode version a processor states
  (`for example 15.0`), and the implementation-report section of the conformance page uses the
  same wording; the requirement itself is unchanged.
- **HDL: a negative literal offset from the cursor.** `@at -2 from current` is accepted, as the
  Processing Model permits a negative offset from `bddo:currentPosition`, and is emitted as
  `bddo:atOffsetFromExpression "-2"`, since `bddo:atOffset` is not negative (`req-hdl-clauses-8`, case
  `hc-negative-offset-from-current`). A negative literal offset from any other base is still an
  `ERROR` (case `hc-negative-offset-from-stream-end`): `req-hdl-clauses-4` is withdrawn and
  `req-hdl-clauses-7` replaces it, and the eight cases that cited it cite the replacement.

### Review integration and follow-ups (2026-10-12)

The tooling, ontology and normative review branches are merged, and the work each left for
another owner is done here. Module versions are unchanged: the canonical graphs of bddo 1.3,
dlv 1.3, core 1.3 and register/media-encoding 1.2 changed again under their unreleased version
IRIs.

- **Generated documentation leaves the canonical Turtle** (ontology finding L5). Each module's
  `GENERATED TERM DOCUMENTATION` block is now a sibling annotation graph, `<module>-doc.ttl`
  (`bddo/bddo-doc.ttl` beside `bddo/bddo.ttl`): `rdfs:label`, `skos:definition` and
  `skos:scopeNote` only, no ontology of its own, written by
  `tools/_build_term_reference.py --enrich`. `specification/family.json` lists the 39 new files
  under `files`, so the family graph a consumer loads is the same graph as before, and maps each
  module to its graph under the new `documentation` key, which `tools/_family.py` checks. The 622
  generated `rdfs:isDefinedBy` statements moved into the canonical files (and the 13 authoring
  templates) as a *Term ownership* section, and `--enrich` now refuses a term without one. The
  documentation generator writes no canonical file any more (the template expander still writes
  the templated modules, and `req/requirements.ttl` has since become generated); the module
  pages embed the authored Turtle only and
  link the annotation graph, which `deployment/publication.conf` serves as Turtle at its own
  path. A consumer that copies single modules (rather than the family) copies the `-doc.ttl`
  beside each to keep the generated labels and definitions.
- **`hexplain:encodes`** (core 1.3). A boolean on the codec contract, checked by
  `hexplain:CodecContractShape`, saying the contract covers the encode direction; stated on the
  seven contracts whose suites hold encode steps (Store, Deflate, Zlib, Gzip, Delta,
  FloatingPointPredictor, BitReverse). `tools/test_codec_vector_completeness.py` reads it instead
  of inferring the direction from the suite, and fails an encode step under a contract that does
  not state it.
- **XZ no longer declares `Unsupported`** (register/media-encoding 1.2). No XZ stream raises it;
  the contract's `hexplain:raisesCategory` and the suite's `unreached` record are withdrawn.
- **Codec status wording.** `processing#codec-status`, the HDL page and the codec-vector page
  said a concept's `hexplain:status` was `contracted` or `catalogue`. `hexplain:status` is the
  register lifecycle status (`hexplain:statusValid` on all 49 media-encoding concepts);
  *contracted* and *catalogue-only* are defined by the presence of `hexplain:codecContract`.
  `req-hdl-semantic-1` reworded to say so (its rule is unchanged).
- **`Description` as a codec error category.** The Processing Model's codec-contract section
  lists it with the four others and says when a codec raises it: a parameter value the contract
  admits but the codec cannot act on once it runs (new `req-pm-codec-contracts-6`; no contract
  declares the category yet, so no case cites it).
- **Alignment and padding** (bddo 1.3). New section `processing#alignment-padding`:
  `bddo:alignment` on a struct aligns every instance before it starts (`req-pm-parsestruct-11`),
  `bddo:padTo` pads a field after its value and a struct after its last member
  (`req-pm-parsefield-31`, `req-pm-parsestruct-12`), both measured from the start of the current
  stream, a skip past the region is a bounds error, and `bddo:padByte` is an optional check
  (`req-pm-alignment-padding-1` to `req-pm-alignment-padding-5`). The comments of
  `bddo:alignment` and `bddo:padTo` said "relative to the start of the enclosing region"; they now
  state the stream origin the Processing Model and the existing alignment cases use. Cases
  `pp-pad-field`, `pp-pad-field-on-boundary`, `pp-pad-repeated-field`, `pp-pad-struct-extent`,
  `pp-pad-origin-is-the-stream`, `pp-pad-past-region`, `pp-pad-byte-without-pad-to`,
  `pp-align-struct` and `pp-align-struct-each-instance`.
- **Float formats, binary-coded decimal and fixed-point scale** (bddo 1.3). New section
  `processing#numeric-representation` defines the bit layouts of `bddo:ibmHexadecimal`,
  `bddo:vaxF` and `bddo:bfloat16` beside `bddo:ieee754`, their conversion to the IEEE 754 format
  of the field's width, `bddo:bcd` and `bddo:fixedPointScale`
  (`req-pm-numeric-representation-1` to `req-pm-numeric-representation-9`); a fixed-point field
  is emitted as its scaled value in an `xsd:decimal` literal (`req-pm-value-mapping-1`). Cases
  `pp-float-ibm-hexadecimal`, `pp-float-vax`, `pp-float-vax-reserved-operand`,
  `pp-float-bfloat16`, `pp-float-format-on-data-type`, `pp-float-format-width`, `pp-bcd`,
  `pp-bcd-invalid-nibble` and `se-fixed-point-scale`.
- **Further encodings and `bddo:CustomEncoding`** (bddo 1.3). `processing#text-encodings` says
  what is well-formed in the twelve encodings registered beyond the original five and in a custom
  encoding named by `bddo:ianaCharset`. A Physical Parser need not decode them: a new refusal
  case (e) and `req-pm-text-decoding-5` to `req-pm-text-decoding-7` make an encoding whose
  character set the processor does not decode an Unsupported feature error, never text read some
  other way. `req-pm-errors-10` reworded to list it. Cases `pp-encoding-custom-unsupported` and
  `pp-encoding-custom-known-charset`.
- **Computed layout extents and chunk-order keys** (dlv 1.3). `req-pm-data-layouts-1` reworded to
  resolve `dlv:dimensionSizeFromExpression`, `dlv:chunkSizeFromExpression` and
  `dlv:cellBitWidthFromExpression` with the stride's; new `req-pm-data-layouts-2` (resolved once,
  before any cell) and `req-pm-data-layouts-3` (the Morton and Hilbert key construction DLV
  defines is the order's meaning). The HEL name-binding table gains the three properties. Cases
  `pp-layout-size-from-expression` and `pp-layout-size-expression-not-integer`.
- **HDL: BDDO terms without a clause.** `hdl#terms-without-a-clause` gives the existing spelling
  of each new term (`@prop` on a field, a `raw-turtle` triple on a struct) and says which are
  RDF-only for now: the encodings beyond the five string types, `bddo:CustomEncoding`, and the
  three computed layout extents. No syntax is added.
- **Checksum fields.** `processing#checksum-field-kinds` states as one requirement
  (`req-pm-parsefield-30`) that a checksum on a field that is not of its algorithm's kind and
  width is a description error: a CRC, a digest, and now `bddo:adler32`, whose 32-bit integer
  field the text described without requiring. `req-pm-parsefield-16` points at it and
  `req-pm-errors-8` lists it, with the other new description errors. Case
  `pp-checksum-adler32-field-width`.
- **Negative offsets.** The rule sat in the `parentStart` paragraph and read as though it bound
  every base. `processing#negative-offsets` states it generally: a negative value is a bounds
  error with `streamStart`, `streamEnd` and `parentStart` (`req-pm-parsefield-32`), while
  `currentPosition` accepts a negative relative offset whose target must still lie inside the
  region (`req-pm-parsefield-33`). `req-pm-parsefield-29` reworded to the `parentStart` target
  rule alone. Cases `pp-offset-negative-stream-start`, `pp-offset-negative-stream-end`,
  `pp-offset-current-negative` and `pp-offset-current-negative-outside`.
- **Enumerated field mapped both ways.** A field with an enumeration and both
  `hexplain:mapsToProperty` and `hexplain:mapsToObjectProperty` emits the literal and the symbol
  on the first and the symbol on the second (`req-pm-emission-13`); cases
  `se-enum-both-properties` and `se-enum-both-properties-no-symbol`.
- **HEL.** A key step on `stream`, `param` or `asset` records no holder, so
  `stream.length.parent` is Null (`req-hel-reserved-roots-5`). Every root is reserved in every
  position: `asset(1)`, `param()` and `x.param` are syntax errors (`req-hel-formal-grammar-4`).
  HEL-RE: an unknown block or category name, a misplaced `-` in a character class and a
  quantifier bound above 2^31-1 are argument errors, a pattern too large to compile is a
  ResourceLimit error, and a processor states the Unicode version its classes follow
  (`req-hel-ext-text-5` to `req-hel-ext-text-8`; the report environment gains the optional
  member `unicode`). The math functions accept an unsigned 64-bit Integer above 2^63-1
  (`req-hel-math-5`). Float rendering is defined without reference to a platform function
  (`req-hel-math-6`), and its definition now includes the rule its own example needed: where one
  digit would round-trip, the nearest two-digit string is written, so the smallest subnormal is
  `4.9E-324`. Thirteen vector rows (`hel-vectors.tsv`, 247 rows), whose header also says that a
  `self` string naming a node path denotes that node; cases `pp-hel-root-as-function-name`,
  `pp-hel-root-as-key`, `pp-hel-stream-key-parent-is-null`, `pp-hel-math-unsigned-64`,
  `pp-hel-math-tostring-shortest-digits`, `pp-hel-regex-hyphen-in-class`,
  `pp-hel-regex-hyphen-misplaced`, `pp-hel-regex-unknown-block` and
  `pp-hel-regex-quantifier-bound`. The reference parser `tools/conformance/hel.py` treated
  `param` as a field name and rendered `5e-324` as `5.0E-324`; both are fixed.
- **Serialisation corrected against a working writer.** Symmetry as written was unachievable: a
  writer cannot reproduce every parsed tree, because an encoded field in a region of literal size
  may re-encode to another length and a text number's canonical rendering may not fit its fixed
  width. `req-pm-serialisation-11` is withdrawn and `req-pm-serialisation-24` replaces it: a
  Writer either produces a stream that parses to an isomorphic tree or raises the error the rules
  require, and never a stream that parses to another tree or does not parse. Dependent values:
  `req-pm-serialisation-13` is withdrawn for `req-pm-serialisation-21` and
  `req-pm-serialisation-22`, under which a length or checksum that rests on codec-produced bytes
  is recomputed even when the tree binds another value, and every other bound dependent value
  that differs is a validation error. Text numbers: `req-pm-serialisation-16` is withdrawn for
  `req-pm-serialisation-23`, which pads `nan` with spaces in a wider fixed field and zero-pads a
  text number whose width a bound field gives. Without a change of identifier: a nested struct
  whose region comes from a field or expression keeps the bound length and is filled to its end,
  a to-end repeat-until sequence that ends early is not padded, a separated element is preceded
  by a separator whenever the bytes before it are a rendered token, "another kind" in rule 1 is
  the node kind, a fixed-value field is written as its constant and a tree that binds another
  value is a validation error, and `req-pm-serialisation-20` names the containers and the chunk
  table properties that are outside the Writer's scope (reworded, same rule).
  `reference-engine-claims.json` still leaves `writer` unclaimed: the file and the Processing
  Model's note give as the reason that the suite has no writer case to observe the claim, and
  that has not changed.
- **Gate manifest.** `test_vocab_shapes` is allowed an hour: it recorded 479 s on a loaded host,
  and the manifest's rule is ten times the recorded duration, at most an hour.
  The runner retries the atomic replace of its run record, which a scanner holding the file
  open made fail with a PermissionError on Windows.
  `test_gate_runner` proves concurrency by having each probe gate wait for the others to start,
  instead of by a 1.5 s clock that a loaded host missed.
- **Suite corrections.** `hc-encoded-with-catalogue-codec` binds `menc:` with `use`, as
  `req-hdl-prefixes-1` requires, so its only possible diagnostic is the warning it tests;
  `pp-claims-statement` accepts the `writer` feature token. The suite has 744 cases and the
  registry 457 entries, 449 of them live.
- **PNG example** (`specification/hexplain/index.html`). The conditional mapping read the sibling
  `Keyword` as `instance.parent.Keyword`. In a `hexplain:condition` on a field's mapping rule
  `instance` is the struct containing the field, so the sibling is `instance.Keyword`; the size
  expression's `sizeof` is corrected likewise, and `instance.parent.ChunkLength`, a field of the
  enclosing chunk, is unchanged.
- **Editorial definitions of `dlv:morton` and `dlv:hilbert`** defer to the terms' comments, which
  now fix the key construction, instead of saying the profile and processor "must agree".
- **Review archive.** `specification/ontology-review/index.html` no longer links
  `ontology-review-candidate.zip`, which is not tracked or deployed: it says the archive is
  produced by `python tools/_review_candidate.py --archive-only` and attached by the validation
  workflow, with the tracked manifest as the reference. The link checker's exemption for that
  file is removed.
- **Tooling.** `ruff.toml` has no per-file exemptions: `_shape_text`, `_build_ontology_docs`,
  `_requirement_ids`, `test_capabilities`, `tools/conformance/` and `tools/codecs/` are formatted
  and annotated like the rest, with long data lines continued so that no published byte changes.
  `tools/gates.json` declares `test_integer_value_shape` and `test_codec_vector_completeness`;
  `test_capabilities` and `test_codec_vector_completeness` have a `main()` and an exit status;
  `test_hel_vectors` no longer exempts `forward-reference`, which the struct-tree contexts raise.

### Normative review fixes (F1–F21)

- **`bddo:parentStart`** (F1). The Processing Model's Addressing step names the fourth offset base,
  and a new paragraph `processing#parent-start` defines it: the start offset of the containing
  struct node as ParseStruct recorded it, after any sync seek; never an ancestor; a negative
  offset or a target outside the region is a bounds error. `req-pm-parsefield-7` reworded to list
  the base; new `req-pm-parsefield-27`, `req-pm-parsefield-28`, `req-pm-parsefield-29`; cases
  `pp-offset-parent-start`, `pp-offset-parent-start-after-sync`, `pp-offset-parent-start-negative`
  and `pp-offset-parent-start-outside-region`.
- **Zlib and Gzip `trailing`** (F2). The two unconditional Validation-error sentences are
  qualified by the step's `trailing` parameter (`req-pm-minimum-codecs-6` and
  `req-pm-minimum-codecs-10` reworded), and the table `processing#framing-parameters` lists the
  Deflate, Zlib and Gzip parameters `level` and `trailing` like Delta's; new
  `req-pm-minimum-codecs-11` says what `ignore` still verifies.
- **Serialisation (write direction)** (F3). New Processing Model section `processing#serialisation`
  with the writer rules derived from the parse rules (field order and presence, derived lengths,
  counts and checksums, extent inference, fill and alignment, text-number rendering, type
  selection, codec encode parameters, checksum back-patching, scope) and the symmetry requirement
  `processing#round-trip`; new requirements `req-pm-serialisation-1`, `req-pm-serialisation-11` to `req-pm-serialisation-20`.
  New optional feature token `writer` (the Writer conformance target, stated in
  `specification/index.html`); `reference-engine-claims.json` leaves it unclaimed. Round-trip
  vectors in the BitReverse, Delta, FloatingPointPredictor and Store suites, and `previous`-fed round
  trips in Deflate, Zlib and Gzip.
- **Codec-contract coverage** (F4). New Physical Parser cases `pp-codec-parameter-*`,
  `pp-codec-pipeline-kinds-disconnected`, `pp-codec-contract-decoded-byte-limit`,
  `pp-codec-selection-*` and `pp-codec-session-per-instance` cite
  `req-pm-codec-contracts-1` to `-4`, `req-pm-codec-selection-1` to `-3`,
  `req-pm-codec-sessions-1` and `req-pm-parameter-expressions-1` to `-3`.
- **Vector completeness** (F5). New gate `tools/test_codec_vector_completeness.py`: every declared
  `hexplain:raisesCategory` expected by a step, every declared parameter passed, a round trip for
  every codec that encodes. The suites gained the missing vectors; each manifest's `sources`
  record where the new expectations come from (an independent library, or the reference engine
  where none exists).
- **`codecs-beyond-minimum`** (F6) is gone from the conformance page's manifest table (which now
  documents the `codecs` member) and from the published report, which is superseded.
- **Vector manifest format** (F7). Published as `specification/codecs/index.html` with the JSON
  Schema `specification/codecs/vector-manifest.schema.json`; the `Description` category is defined
  there and the register's contract shape is to admit it. New input form `{"previous": true}`.
- **Codec status** (F8). `processing#codec-status` defines `contracted` and `catalogue`; an HDL
  compiler warns on a catalogue-only concept (`req-pm-codec-contracts-5`, `req-hdl-semantic-1`).
- **Evaluation over the complete tree** (F9). `req-pm-context-1` reworded to list value
  expressions, map guards and means-when guards among the deferred evaluations; new
  `req-pm-emission-11`; HEL name-binding note `hel#complete-tree` (`req-hel-name-binding-3`); the
  HDL forward-reference bullet aligned.
- **Field-level bit order** (F10). `processing#bit-order` gives the precedence field, struct,
  `bddo:MSBFirst` (`req-pm-byte-order-8`, `req-pm-byte-order-9`; `req-pm-bit-cursor-3` reworded to
  point at it); HDL `hdl#field-bit-order` (`req-hdl-clauses-6`); cases
  `pp-bits-field-order-overrides-struct`, `pp-bits-field-order-without-struct-order` and
  `hc-bit-order-field`.
- **HEL `math` group** (F11): `floor`, `ceil`, `trunc`, `round` (half away from zero), `abs`,
  `min`, `max` and `toString`, with the Float rendering pinned (`hel#math`,
  `req-hel-math-1` to `req-hel-math-4`; `req-hel-core-functions-1` reworded for the variadic
  `min`/`max`); vectors in `hel-vectors.tsv`.
- **Float `%` and the regex dialect** (F12). Float `%` is the truncated remainder
  (`req-hel-numeric-semantics-7`); `matches` patterns are HEL-RE, the XSD 1.1 regular-expression
  language, every other construct an `argument` error (`req-hel-ext-text-4`;
  `req-hel-ext-text-2`, the SHOULD on common constructs, is withdrawn); vectors for both.
- **HEL vectors in a struct tree** (F13). `hel-vectors.tsv` gains a tree context form (`"$tree"`)
  with rows for subscripts, `parent`, `root`, `self`, `stream.*`, `param.*`, `sizeof`, `eof()`,
  forward references, and the geometry and register groups.
- **Lexical forms and `enumSymbol`** (F14). Emitted literals are in XSD 1.1 canonical lexical form
  (`req-pm-emission-12`) and the symbol of a matched enumeration is emitted (`req-pm-emission-2`
  is now a MUST); `tools/conformance/compare.py` compares emitter graphs by lexical form (HDL
  Compiler graphs and run reports still by value); the Semantic Emitter expected graphs are
  canonical.
- **Implementation report format version 2** (F15): `implementation.revision`, `environment`
  (`os`, `jvm`, `toolchain`), `claimsDigest`; a pre-release version only with a revision; reports
  published as `<version>-<suite digest>.json` and kept by digest; `report.py --complete`.
- **Registry context** (F16). `requirements.json` records the introducing sentence as `context`
  for every item of a governed list or table.
- **`dlv:morton` and `dlv:hilbert`** (F17): no page text. Their definitions are the vocabulary's
  (`dlv.ttl`, from which the term reference is generated), so the DLV page is unchanged.
- **Known-length inputs** (F18): the Processing Model's Inputs section states that this version has
  no streaming model (`req-pm-inputs-outputs-1`: the length is known before the first field is read,
  an input of unknown length is read to its end first, and a parse of a prefix is never reported as
  a parse of the input); Security and Privacy, `processing#security-known-length`, restates it for
  the input-byte limit. Case `pp-hel-stream-length-before-first-field`.
- **`not(` is never a call** (F19): `req-hel-formal-grammar-3`.
- **Digest checksum fields** (F20): a digest's checksum field is a `bddo:bytes` field of literal
  size exactly the digest's length (`req-pm-parsefield-16` and `req-pm-errors-8` reworded); cases
  `pp-checksum-digest-field-width` and `pp-checksum-digest-field-short`.
- **Evidence digests** (F21) are computed over LF-normalised bytes in `tools/test_capabilities.py`.
- **Non-leading `.parent`** (HEL). A `.parent` step after a key step or a subscript yields the
  struct instance holding the field that step names, one more climbs above the node the path
  started from, and above `root`, or after `self`, `stream`, `param`, `asset` or a local binding, it
  is Null (`hel#non-leading-parent`, new `req-hel-reserved-roots-4`; the key-resolution, `param` and
  `stream` sentences except the keyword). Vectors in `hel-vectors.tsv`; case
  `pp-hel-parent-non-leading`.
- **YAML byte strings** (HDL). A quoted `"0x…"` scalar is a string; `{ hex: "0x…" }` is the explicit
  byte-string form; `sync`, `terminator` and a container's delimiters take an unquoted hex scalar,
  that mapping or an integer byte, and a quoted `"0x…"` there is an `ERROR` (new `req-hdl-yaml-3`,
  `req-hdl-yaml-4`, `req-hdl-yaml-5`; the two sentences that still read a quoted hex literal as bytes
  are corrected). Cases `hc-yaml-hex-mapping`, `hc-yaml-quoted-hex-terminator`,
  `hc-yaml-quoted-hex-sync` and `hc-yaml-quoted-hex-separator`.
- **Dispatch arm IRIs** (HDL). The arms of a keyed dispatch are emitted as IRIs
  `<ns#Table.arm.key>`, never blank nodes (new `req-hdl-modules-4`); cases `hc-dispatch-arm-iris`
  and `hc-dispatch-arm-iris-yaml`.
- **Writer requirements** are registered with the class `writer` (the optional Writer target), so
  the coverage tables of the five processor classes do not count them; the conformance page says
  what observes them.
- **Cases for the new requirements.** `pp-hel-math-*`, `pp-hel-float-remainder`,
  `pp-hel-regex-*`, `pp-hel-not-*` and `pp-hel-reserved-word-call` put the HEL additions in a parse;
  `pp-codec-zlib-trailing-ignore*` and `pp-codec-gzip-trailing-ignore*` exercise `trailing`;
  `se-lexical-forms-canonical`, `se-lexical-forms-computed`, `se-enum-symbol-with-literal`,
  `se-enum-value-without-symbol`, `se-enum-flags-symbols-with-literal` and
  `se-*-later-field` exercise the emission rules; `hc-encoded-with-catalogue-codec` compiles a
  catalogue-only codec.
- The HDL format DSL design note under `docs/superpowers/specs/` is marked superseded by
  `specification/hdl/index.html`.

### Codec contracts, claims and profile codec features

- The Processing Model gains Codec contracts (kinds, typed parameters, sessions, error categories
  and their notation, limits, normative vectors, and the bytes a pipeline ending in samples
  yields), Parameter expressions, Run-time codec selection and Codec sessions. New requirements:
  `req-pm-codec-contracts-1`, `req-pm-codec-contracts-2`, `req-pm-codec-contracts-3`,
  `req-pm-codec-contracts-4`, `req-pm-parameter-expressions-1`, `req-pm-parameter-expressions-2`,
  `req-pm-parameter-expressions-3` (a parameter with both or neither of a literal and an
  expression), `req-pm-codec-selection-1`, `req-pm-codec-selection-2`, `req-pm-codec-selection-3`
  (a selecting step with parameters of its own, with both `hexplain:codec` and
  `hexplain:codecFromExpression`, or without candidates) and `req-pm-codec-sessions-1`. The short
  run-time selection paragraph becomes the section `processing#codec-selection`: kinds are checked
  per candidate, and candidates may differ in kind. A pipeline whose first decoded step reads
  samples is a Description error; `hexplain:codecSessionScope` is ignored on a field whose codecs
  keep no session.
- The feature token `codecs-beyond-minimum` is withdrawn: a processor lists the IRIs of the codecs
  it decodes in the `codecs` member of its claims statement, an array only
  (`req-pm-conformance-classes-5` and `req-pm-optional-codecs-3` reworded), and conformance
  manifests name codecs in a `codecs` member. Refusal gains case (d): a parameter value or coding
  feature of a listed codec that its contract defines but the processor does not implement may be
  refused with Unsupported feature (`req-pm-optional-codecs-3`, `req-pm-codec-contracts-1` and
  `req-pm-errors-10` say so). menc:LZ4Block's decodedSize is an integer of at least 1, given as a
  literal or an expression (`req-pm-optional-codecs-7` reworded); a literal out of range is a
  Description error when the description is loaded and an expression's value out of range a
  Validation error when the step runs (`req-pm-optional-codecs-1`). The error table lists the codec
  errors in its rows (`req-pm-errors-4`, `req-pm-errors-8`).
- Run-time codec selection: a local name that more than one candidate shares names none of them,
  a Validation error (`req-pm-codec-selection-2` reworded to say so).
- reference-engine-claims.json lists the 34 codecs the reference engine decodes with their modules,
  and says generated Kotlin code supports parameter expressions, run-time selection and sessions.
- HDL: pipeline parameters take literals of every contract type, bracketed lists and HEL expressions
  (`name value` or `name: value`); `switch <expr> { … }` steps and `@codec switch` select a codec when the
  step runs, its keys all integers or all strings (and, on a bare sibling of known type, of that type);
  `@codec-session instance|layout`; YAML `codec-switch` and `codec-session`. The grammar gains `CodecLiteral`
  and `CodecList`. req-hdl-grammar-fields-1 reworded (a `Literal` other than a `NAME`, a `FLOAT` or a
  `CodecList` is a parameter value; anything else an expression); req-hdl-clauses-3 reworded to name `@codec switch` among the pipeline clauses a field states once;
  the case hc-pipeline-non-integer-parameter becomes hc-pipeline-duplicate-parameter, and
  hc-codec-switch-and-session (with its YAML mirror) is new.
- The codec vocabulary follows the conventions of the 2026-09-27 review: its labels and comments
  are tagged @en, every codec contract and parameter spec is an owl:NamedIndividual, every
  reported property shape of the codec shapes carries an sh:message, and
  `hexplain:parameterExpression` and `hexplain:codecFromExpression` accept an `xsd:string` or a
  `bddo:HelExpression` literal like every other expression-valued property.

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
  cases (`se-value-natural-*`, `se-value-datatype-*`). Clarified for the engine implementer
  (`req-pm-computed-values-2`): a Float never has a value in an integer datatype, even with no
  fractional part (`50.0` typed `xsd:integer` is a Type / HEL error, as a Float is never an Integer
  in HEL), while `xsd:decimal` takes an Integer or a finite Float; and Bytes have a value in both
  `xsd:hexBinary` and `xsd:base64Binary`. New cases `se-value-datatype-integral-float-as-integer`,
  `se-value-datatype-float-as-decimal` and `se-value-datatype-bytes-as-base64`. A Zstandard frame
  whose `Frame_Content_Size` the decoded content does not match stays a Checksum error, as the
  error table says; new case `pp-codec-zstd-content-size-mismatch` checks it.
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
- **Text decoding and `bddo:trimNull`.** The rule said a string field is decoded "before
  `bddo:trimNull` is applied", so uninitialised padding after the terminating NUL -- common in real
  TAR and ZIP names -- made a whole field a validation error. With `bddo:trimNull true` the first
  NUL code unit is now found in the raw bytes, only the bytes before it are the value and are
  decoded, and the NUL and everything after it are padding, never decoded or validated
  (`req-pm-text-decoding-4`; ParseField, Value, and the definition of `bddo:trimNull` say the
  same). New cases
  `pp-str-trim-null-utf16-padding-not-decoded` (a lone UTF-16 surrogate after the NUL unit reads as
  the value before it), `pp-str-trim-null-utf8-padding-not-decoded` and
  `pp-str-trim-null-value-malformed` (value bytes that are not well-formed are still an error).
- **Implementation reports.** New section `conformance#implementation-reports` defines the report an
  implementation publishes for a run over the suite: one JSON file naming the implementation and
  version, its claims, the suite (a digest of its case files), the run, the counts and one result
  per case (PASS, FAIL or SKIP, the error category it reported, and why for a FAIL or SKIP); every
  case listed once, a SKIP only for a case that does not apply. Reports are published as
  `specification/conformance/reports/<implementation>/<version>.json` and listed on the
  conformance page. `tools/conformance/run_suite.py --json` now writes that format
  (`--implementation`, `--implementation-version`), `--check-report` checks one, and the new gate
  `test_implementation_reports` checks every published report.
- **Coverage.** Existing cases now cite the vocabulary-page requirements they already exercise
  (`req-bddo-addressing-1`, `req-bddo-bitfields-1`, `req-bddo-field-properties-8`,
  `req-bddo-structural-properties-4`, `req-bddo-structural-properties-6`,
  `req-core-static-mapping-properties-3`) and the new security requirements; new case
  `pp-hel-temporal-date-only` covers `req-hel-ext-temporal-1`. A processor MUST that no black-box
  case can observe is now marked as such, with the reason, in `tools/_build_conformance_page.py`
  (`NOT_SUITE_TESTABLE`, 11 requirements: the SHACL-validator rule of BDDO, the DL-entailment rule
  of core, the geometry and raster interpretation rules, the spatial-reference evaluation rules,
  the base-IRI privacy rule and the HEL error-condition rule the vectors test); `coverage.json`
  reports them per class as `notSuiteTestable`, and the conformance page lists them. The build
  refuses a stale entry. The four HEL version-marker cases (`pp-hel-version-newer-minor-unknown-function`,
  `pp-hel-version-current-unknown-function`, `pp-hel-version-other-major`,
  `pp-hel-version-malformed`) state `bddo:helVersion` and are generated. Processor MUSTs now
  covered: Physical Parser 202 of 204 (two not testable), Semantic Emitter 21 of 30 (nine not
  testable), Bundle Processor, HDL Compiler and Conformance Evaluator all.
- **Function library status and conformance.** `fn/index.html` defined contracts with no RFC 2119
  keyword, no status statement and no conformance section. It now has a status statement (a
  prerelease working draft, normative for the current toolchain like the rest of the family, with
  its normative and informative parts named), the BCP 14 conventions, and a conformance section: a
  conforming implementation states the functions it installs and, for each, accepts exactly its
  `hxf:signature`, returns what `fn.ttl` defines (a Pure function what its SPARQL body returns),
  is unbound exactly when `hxf:unboundWhen` or a limit says, reads and evaluates as the Processing
  Model and HEL specify, and meets the security rules; `hxf:explain` is never unbound.
- **HEL error conditions.** A HEL error vector passed when the evaluator's diagnostic contained a
  fragment of the reference engine's English, so conformance depended on one engine's wording. New
  section `hel#error-conditions` names eight conditions (`syntax`, `undefined-name`,
  `forward-reference`, `type`, `range`, `overflow`, `division-by-zero`, `argument`), all Type / HEL
  errors of the Processing Model, and an evaluator must be able to say which one an error is
  (`req-hel-error-conditions-1`). `validation/test/hel-vectors.tsv` now expects a condition in the
  fourth column of every error row and keeps the old fragment as an informative sixth column;
  `req-hel-conformance-9` asserts the condition. New gate `test_hel_vectors` checks the file's shape
  and that every condition a flat context can raise is exercised.
- **HEL version marker.** HEL allowed a later 1.x version to add functions, yet an unknown
  function was always a Type / HEL error, so a description written for HEL 1.1 would fail a 1.0
  evaluator as if it were broken. A description now declares its HEL version with
  `bddo:helVersion` ("major.minor", default "1.0") on its `owl:Ontology`
  (`hel#version-marker`): a malformed value is a Description error (`req-hel-versioning-3`),
  another major version is Unsupported feature (`req-hel-versioning-4`), and an unknown function
  is Unsupported feature when the declared version is a later 1.x than the evaluator implements and
  a Type / HEL error otherwise (`req-hel-versioning-5`). The Unsupported feature row of the error
  table (`req-pm-errors-10`) includes it. The marker is the `bddo:helVersion` annotation of BDDO
  1.3 (below), in `bddo` because `bddo` loads without `core`; the text first named it
  `hexplain:helVersion`, and `test_doc_terms` no longer allows that name.
- **Reference engine HEL version.** HEL says every evaluator states the latest HEL version it
  implements with its claims; `reference-engine-claims.json` now does (`"helVersion": "1.0"`), the
  reference-implementation note of the Processing Model restates it, and `test_reference_claims`
  checks that it is a major.minor version of HEL 1 that the HEL specification defines and that the
  note agrees.
- **Expression literals.** New section `hel#expression-literals`: an expression is the lexical form
  of a literal typed `xsd:string` or `bddo:HelExpression`; authoring tools SHOULD write the latter
  (`req-hel-expression-literals-2`, a rule on descriptions), and a processor MUST accept both and
  evaluate them alike (`req-hel-expression-literals-1`). `processing#context` points to it. New case
  `pp-hel-expression-datatype`. The suite's graph comparison (`conformance#canonicalisation`,
  `tools/conformance/compare.py`) compares a HEL-bearing literal typed `bddo:HelExpression` as the
  same expression as an `xsd:string` one, so an HDL compiler that follows the SHOULD still matches
  the expected graphs; `test_conformance_comparator` checks it.
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
- **HDL as the compiler now implements it.** The YAML surface is no longer a subset: the
  sentence making `module`, `import`/`imports`, `extend`, `dispatch` and `seek` text-only and
  rejected is gone (`hdl#yaml`). New top-level keys `module: <name>` (a document has `format:` or
  `module:`, not both), `imports: { alias: "path" }` and `extend: { Table: { key: Struct } }`, and
  field keys `dispatch: { name, on, default, cases }`, whose case keys are typed as in text, and
  `seek: stream|region`; `import:` is an unknown key. `req-hdl-conformance-section-2` no longer
  carves out the text-only constructs. Import resolution (`hdl#import-resolution`): YAML imports
  resolve like text imports through the same sandbox, and an imported module's surface follows its
  file name (`.hx` text, `.yaml`/`.yml` YAML); a compiler bounds what imports read, per file and per
  compilation, and reports an import over a bound as an `ERROR` on its line
  (`req-hdl-modules-3`, marked not suite-testable: the bounds are the compiler's own; the reference
  compiler's are 1 MiB per file and 16 MiB per compilation). IRI minting (`hdl#iri-minting`): a
  quoted key without an alias mints `<struct>.<key>` with the characters Turtle cannot hold in an
  IRI percent-encoded, a key already valid keeping its IRI, and the runtime name is the last
  segment decoded; `@namespace` and `use` IRIs must be absolute, and an invalid `@namespace` is an
  `ERROR` after which the default namespace is used. The command-line tool reports a diagnostic
  from an imported module at the module's own `file:line:column`, followed by where it was
  imported. New HDL Compiler cases `hc-import-within-root-yaml`, `hc-import-yaml-module`,
  `hc-quoted-key-percent-encoded` (and its `-yaml` mirror), `hc-yaml-import-key`,
  `hc-yaml-format-and-module`, `hc-yaml-seek-without-at`, `hc-yaml-switch-and-dispatch`,
  `hc-namespace-not-absolute` and `hc-use-not-absolute`.

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

### Licensing

- `conf`, `conf/shapes`, `req`, `req/shapes` and `fn` declare `dcterms:license
  <https://creativecommons.org/licenses/by/4.0/>`, like the other 33 modules; every ontology
  module is now CC BY 4.0 with `dcterms:creator <https://geoknoesis.com>` as its attribution.
- New root `LICENSE`: everything in the repository without a notice of its own (tools and code,
  profiles, documentation, site) is proprietary, all rights reserved (Stephane Fellah /
  Geoknoesis). It does not override per-file or RDF licence declarations, and the ontology content
  a page reproduces keeps its CC BY 4.0 licence. `LICENSING.md` states the two regimes.
- New gate `test_ontology_licenses`: every module declares exactly the CC BY 4.0 licence and its
  creator, and `LICENSE` and `LICENSING.md` state both regimes.

### Validation messages (review fixes)

- Every property shape whose results a validator reports carries an `sh:message` (223 shapes
  and 14 shared constraint patterns gained one; 59% had none). Each states the property's whole
  contract, generated from its constraints by `tools/_shape_text.py` and reviewed ("atime:duration
  takes at most one value; each is an xsd:decimal or xsd:integer literal at least 0"). Shapes
  nested in `sh:not`, `sh:or`, `sh:and`, `sh:xone` or `sh:node` are exempt, because SHACL reports
  the enclosing constraint with the enclosing message; where a nested node shape carried the only
  message (three `bddo:hasField` list constraints), the reported shape now carries it too. New
  gate `test_shape_messages`, which also rejects a SPARQL placeholder in a property shape's
  message.
- Severity audit: every shape reporting at `sh:Violation` enforces a MUST; the two SHOULD-level
  rules the shapes enforce (use of a deprecated register value, a sensitivity level without its
  verbatim text) already report at `sh:Warning`. No severity changed; `specification/ontology-design`
  states the mapping (MUST: Violation, SHOULD: Warning, MAY: Info or no shape) and that a new
  Warning or Info shape is itself a compatibility change, since any result makes `sh:conforms`
  false.

### Namespace prefixes and shape packaging (review fixes)

- `specification/family.json` gains a `namespaces` list: for each vocabulary, its prefix,
  namespace IRI, ontology IRI, directory and file. It is the authoritative table for the prefixes
  that do not match their namespace or directory (`adv` for /ns/audio#, `img` in directory `idv`,
  `gv` for /ns/geo#, `hexplain` for /ns/core#, `hxf` for /ns/fn#, `menc` and `usnato` among the
  `r…` register prefixes); nothing is renamed. `specification/ontology-design` shows the table.
  New gate `test_namespace_prefixes`: every module declares exactly its row, no prefix or
  namespace repeats, and the page lists every row. The `files` list is unchanged.
- `specification/ontology-design` states where shapes live: in the module, except `conf` and
  `req`, whose shapes are separate ontologies because the conformance shapes need `core` and
  `bddo`, which report readers should not have to load (`req` follows `conf`'s layout).

### Language tags and named individuals (review fixes)

- Every `rdfs:label`, `rdfs:comment` and SKOS documentation literal of a family term is tagged
  `@en` (1,162 literals, 710 of them labels, were plain), in the Turtle and the authoring
  templates and presets alike. New gate `test_language_tags`.
- Every individual of a family class is declared `owl:NamedIndividual` (the `bddo:DataType`
  primitives, the `dlv:Axis` values, the hxf functions and kinds, the conf and req closed sets,
  the register lifecycle statuses: 104 were not). New gate `test_named_individuals`.
- No individual is renamed. `specification/ontology-design` (Naming) states the convention for
  new ones: UpperCamelCase, except that a value joins its set's existing case and a value with an
  established spelling (a primitive, an encoding, a function) keeps it.

### Standards alignments (review fixes)

Only true statements are asserted: `rdfs:subPropertyOf` where every use of the family term
entails the external one, `rdfs:seeAlso` otherwise (SKOS mapping properties relate concepts only,
`test_ontology_design`).

- `asref:footprintWKT` accepts `geosparql:wktLiteral`, which new data SHOULD use; its range is
  the union of `xsd:string` and `geosparql:wktLiteral`, so existing string footprints stay
  valid. A typed literal follows GeoSPARQL: its CRS is the IRI prefixing the text, CRS84 when
  none does; a string footprint is still in the resource's CRS. It is not a subproperty of
  `geosparql:asWKT`, whose domain is `geosparql:Geometry`.
- `asref:epsgCode` and `asref:crsIdentifier` link each other: EPSG code n is the CRS
  `<http://www.opengis.net/def/crs/EPSG/0/n>`, which `asref:crsIdentifier` states and new data
  SHOULD give.
- `atime:duration` links OWL-Time's `time:hasDuration` and `time:numericDuration`; it is not their
  subproperty, since they relate temporal entities and durations while `atime:duration` relates
  content to seconds.
- New `aprov:hasPlatform` and `aprov:hasSensorModel` relate an `aprov:AcquisitionInfo` to its
  `aprov:Platform` and `aprov:SensorModel` (linked to `sosa:isHostedBy`, `sosa:madeBySensor`,
  `prov:wasAssociatedWith`, `prov:used`), checked by the new `aprov:AcquisitionInfoShape`.
- `afs:modificationTime` and `afs:creationTime` are subproperties of `dcterms:modified` and
  `dcterms:created` (they were `rdfs:seeAlso`); `abnd:hasPart` and `abnd:partOf` of
  `dcterms:hasPart` and `dcterms:isPartOf`, so `apkg:hasEntry` is one too. `afs:fileSize` links
  `dcat:byteSize`, whose `dcat:Distribution` domain an archive entry need not satisfy.

### HEL expressions as a datatype (bddo 1.3)

- New datatype `bddo:HelExpression` (`rdfs:subClassOf xsd:string`): its lexical space is HEL
  expression text and a literal's value is that string, so every expression-valued property
  keeps its `xsd:string` range. The shapes of all 17 expression-valued properties
  (`bddo:sizeFromExpression`, `bddo:condition`, `bddo:validIf`, `bddo:isPresentIf`,
  `bddo:repeatUntil`, `bddo:valueFromExpression`, `bddo:localExpression`,
  `bddo:dispatchOnExpression`, `bddo:atOffsetFromExpression`, `bddo:repeatCountFromExpression`,
  the three `bddo:covers…Expression`, `hexplain:condition`, `hexplain:valueExpression`,
  `dlv:dimensionStrideFromExpression`, `conf:assertion`) and the members of `bddo:hasArgument`
  accept `xsd:string` or `bddo:HelExpression` through the new `bddo:HelExpressionValueShape`.
  Authoring tools SHOULD emit the new datatype; every existing description stays valid.
- New optional annotation `bddo:helVersion` on a description's ontology: the HEL version,
  major.minor ("1.0"), its expressions are written against; absent, the specification edition's.
  `bddo:HelVersionShape` allows one value matching `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`: two
  decimal numbers without leading zeros, as HEL's version marker requires, so `"01.0"`, which HEL
  makes a Description error, is a violation too.
- Both are in `bddo`, not `core`: `bddo` is the lowest layer that holds expressions and loads
  without `core`, which imports it.

### Ranges, shapes and deprecations (review fixes)

- `hexplain:unit` has range `rdfs:Resource` instead of `skos:Concept`, which typed every QUDT unit
  and UCUM-based unit IRI a `skos:Concept`. The shape still requires an IRI; nothing that
  validated stops validating.
- `qudt:hasUnit` and `qudt:hasQuantityKind` are no longer asserted on `atime:duration`,
  `aenc:bitrate`, `asamp:bitDepth`, `asig:sampleRate` and `vdv:frameRate`: they describe a
  quantity, not a property. Each property links its QUDT unit and quantity kind with
  `rdfs:seeAlso` and states the unit in its definition.
- `asref` coefficients: `xsd:float` literals are accepted and the ranges say so. The 23 ranges
  that were `xsd:double` are the union `[ owl:unionOf ( xsd:double xsd:float ) ]` (the two value
  spaces are disjoint, so a float value of a double-ranged property was an inconsistency), and
  `asref:FiniteDoubleShape` accepts a finite `xsd:float` as the range datatype shape already did:
  a geotransform read from float32 fields conformed to one shape and failed the other. Data typed
  `xsd:float` keeps validating; NaN and infinities are still rejected. `test_range_datatypes` no
  longer treats `xsd:double` and `xsd:float` as interchangeable, and understands union ranges and
  datatypes declared `rdfs:subClassOf` a range.
- `hexplain:ClassMappingRuleShape` accepts an `rdfs:Class` for `hexplain:semanticClass`, as
  `hexplain:MapsToClassShape` accepts it for `hexplain:mapsToClass`.
- `bddo:condition` and `hexplain:condition` are not the same property and now say so: the first
  guards a physical parsing rule while bytes are read, the second a semantic mapping rule after
  parsing. Their definitions are sharpened and each links the other with `rdfs:seeAlso`; neither
  is deprecated.
- `bddo:coversExpression` names its replacements (`bddo:coversFromExpression`,
  `bddo:coversToExpression`) with `dcterms:isReplacedBy`; `bddo:usesStruct` explains in a
  `skos:historyNote` why it has none. New gate `test_deprecations`: every deprecated term names a
  current replacement or explains why there is none.

### Documentation annotations

- One definition rule: a term's `rdfs:comment` is its definition; the generator adds a
  `skos:definition` only where it says what no comment says (an editorial definition, or a
  shape's or primitive's generated one). 267 generated definitions that repeated their comment
  word for word are gone, and so is the hand-written duplicate on `rgeo:GeometryCollection`.
  The term reference shows the `skos:definition`, else the comment.
- Generated scope notes are only the module note on each ontology and the editorial notes of
  `_term_editorial.SCOPE_NOTES`; the 987 templated notes (module sentence, "Use it as a
  predicate", a shape's activation) are gone. A shape's activation and a property's shape usage
  remain rows of every term card.
- Shape definitions no longer open "A reusable validation contract for": they state the shape's
  activation and what it checks, from its messages or, lacking one, from its constraints
  (`tools/_shape_text.py`). A message naming SPARQL result variables is never copied, so the six
  definitions that read "{?s} declares {?np} parameter(s)" are gone; `bddo:ArgumentArityShape`
  and `bddo:TreePrefixBindingShape` have editorial comments instead.
- The generated block is readable Turtle with its own `@prefix` lines and one statement per
  term, instead of N-Triples.
- New gate `test_documentation_annotations`: no placeholder in any label, comment, definition or
  scope note, no definition repeating its comment, no retired template, no N-Triples block.
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
- **Published review evidence.** The root folder `review-2026-09-05/` (300 files) was served with
  the public site, and most of it was the proprietary engine's and hosted service's working
  evidence (engine test logs and probes, backend, tenancy and CI logs, the review report that
  discussed them). Only the nine files a published page links to or a tool reads remain public,
  moved to `specification/evidence/2026-09-05/` (the simplification baseline, `vector-depth.json`,
  `layout-competency.json`, `readiness-security-gates.log`, `live-publication.json`,
  `specification-acceptance.html` and its `specification-depth-evidence.json`); a new historical
  page, `specification/evidence/2026-09-05/index.html`, stands in for the review report, lists
  them, and states that the engine-side evidence is held privately. Links that pointed at private
  files (the vector-depth core/adapter log, the Jena security-mutation run, the simplification
  progress reports) now point to that statement. `tools/_review_candidate.py`,
  `tools/test_simplification_equivalence.py`, `tools/check_live_publication.py` and the
  `live-publication` workflow use the new paths; both evidence pages are registered historical.
  Git history is unchanged.

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

### CI and dependencies

- Every GitHub Actions `uses:` is pinned to a full commit SHA with its release in a comment
  (`actions/checkout` v4.4.0, `actions/setup-python` v5.6.0, `actions/upload-artifact` v4.6.2);
  checkouts set `persist-credentials: false`; workflows grant only `contents: read`.
- New `actionlint` job in the gates workflow (actionlint 1.7.7 pinned by SHA-256, with shellcheck).
- `requirements.txt` and `requirements-browser.txt` are now hash-pinned locks compiled with
  `uv pip compile --generate-hashes` from `requirements.in` and `requirements-browser.in`, and CI
  installs them with `--require-hashes`. Playwright stays pinned at 1.60.0, which fixes the
  Chromium build the browser check installs.
- `.github/dependabot.yml`: weekly grouped updates for pip and GitHub Actions.

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
