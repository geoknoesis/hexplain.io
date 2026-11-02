# Independent ontology review instructions

Status: awaiting a reviewer independent of the implementation. This package is prepared by the implementing assistant and is not an external approval.

Review the pinned canonical files, not only generated HTML. Record your name/organization, independence/conflicts, date and reviewed hashes. Complete every module row and priority question. For each finding record severity, affected IRIs, a positive/negative counterexample, expected result, proposed disposition and compatibility impact. Retain unresolved findings; never infer approval from absence of comments.

Acceptance requires completed module coverage, dispositions for all findings, reproducible regressions for accepted corrections, and an explicit signed-off or rejected decision from the reviewer. An empty decision or reviewer field is pending, never a pass. No statement here certifies all possible combinations of terms.

## Priority questions

- **ORT-01 Geometry type coverage:** Verify all seven measured WKB families map to distinct geometry-type concepts, including GeometryCollection; identify required curve/surface/mesh extensions.
- **ORT-02 Ordinate semantics:** Verify XYM is not treated as XYZ, M is not implicitly time/elevation, and unknown flags are distinct from false.
- **ORT-03 CRS and coordinate order:** Check stored GeoPackage x/y order versus CRS authority axis order; distinguish SRS identifiers from verified transformations and coordinate epochs.
- **ORT-04 Null and empty:** Check NULL geometry, empty Point and empty collections remain distinct; assess missing vs unknown vs invalid semantic values.
- **ORT-05 Envelope semantics:** Review XYZ/XYM subset envelopes on XYZM data and rejection of out-of-bounds ordinates against GeoPackage requirements.
- **ORT-06 Targets and entailment:** Audit SHACL activation, referenced helper shapes, primaryPart handling and vacuous conformance when external profile definitions are absent.
- **ORT-07 Compound and security scope:** Review nesting, ownership, controlled concepts and profiles. Confirm containment does not confer authorization or security inheritance.
- **ORT-08 Numbers and physical layout:** Review counts, strides, packing width, integral datatype families, rational quantities, sentinel extents and signedness.
- **ORT-09 Vocabulary architecture:** For every module, review term labels/definitions/scopes, reuse, domain/range choices, cardinality and open-world ontology vs validation contracts.
- **ORT-10 Compatibility and publication:** Assess stricter shape revisions, retained immutable artifacts, namespace policy (live deployment deferred and excluded), and migration impact.

## Module-by-module record

| Module | Resources | Reviewer finding / disposition |
|---|---:|---|
| specification/adv | 15 | Unreviewed |
| specification/aspect/bundle | 37 | Unreviewed |
| specification/aspect/color | 2 | Unreviewed |
| specification/aspect/encoding | 6 | Unreviewed |
| specification/aspect/fsmeta | 8 | Unreviewed |
| specification/aspect/geometry | 16 | Unreviewed |
| specification/aspect/integrity | 4 | Unreviewed |
| specification/aspect/networkflow | 12 | Unreviewed |
| specification/aspect/packaging | 7 | Unreviewed |
| specification/aspect/pointcloud | 5 | Unreviewed |
| specification/aspect/protection | 23 | Unreviewed |
| specification/aspect/provenance | 10 | Unreviewed |
| specification/aspect/raster | 48 | Unreviewed |
| specification/aspect/sampling | 12 | Unreviewed |
| specification/aspect/security | 16 | Unreviewed |
| specification/aspect/signal | 3 | Unreviewed |
| specification/aspect/spatialref | 56 | Unreviewed |
| specification/aspect/structure | 18 | Unreviewed |
| specification/aspect/tabular | 14 | Unreviewed |
| specification/aspect/time | 3 | Unreviewed |
| specification/axv | 10 | Unreviewed |
| specification/bddo | 312 | Unreviewed |
| specification/conf | 66 | Unreviewed |
| specification/dfv | 28 | Unreviewed |
| specification/dlv | 52 | Unreviewed |
| specification/fn | 44 | Unreviewed |
| specification/gv | 15 | Unreviewed |
| specification/hexplain | 99 | Unreviewed |
| specification/idv | 13 | Unreviewed |
| specification/npv | 11 | Unreviewed |
| specification/register/checksum | 18 | Unreviewed |
| specification/register/color | 6 | Unreviewed |
| specification/register/geometry-type | 9 | Unreviewed |
| specification/register/media-encoding | 203 | Unreviewed |
| specification/register/part-role | 14 | Unreviewed |
| specification/register/protection | 16 | Unreviewed |
| specification/register/us-nato-security | 90 | Unreviewed |
| specification/req | 236 | Unreviewed |
| specification/vdv | 18 | Unreviewed |

## Evidence boundaries

The constraint ledger (`specification/validation/constraint-coverage.json`) records actual component evaluations, including nested branches, rather than inferring coverage from term mentions. The shared module corpus is `specification/validation/test/family-contracts.json`; its expectations are authored in the `_...contract_cases.py` helpers and replayed in pySHACL and Apache Jena. One case explicitly adds a target node to reuse a named shape outside its automatic target; this activation is recorded in the fixture, not silently added to the published vocabulary. Empty-value successes count only for cardinality components. A passing and failing evaluation of each component does not prove every parameter is necessary or every combination of vocabulary terms is semantically adequate. Review those questions independently.

The generated GDAL corpus covers seven ISO-WKB families, four ordinate layouts, empty/nonempty geometries and two byte orders. Actual GeoPackage tables cover 60 rows with geometry/null distinction, exact integer attributes and SRS identifiers. It does not prove native Shapefile/FlatGeobuf/GeoParquet decoding, CRS reprojection, topology, curves, arbitrary mixed-dimensional collections or all external format variants.

The reviewer should specifically assess whether dimensionality documentation adequately distinguishes total ordinate count from spatial dimension, and whether additional profile-specific constraints are needed. Broader interoperability and ontology adequacy are separate questions.

Sources: [OGC GeoPackage](https://www.geopackage.org/spec140/index.html), [W3C SHACL](https://www.w3.org/TR/shacl/), [RDF vocabulary publication](https://www.w3.org/TR/swbp-vocab-pub/).

## Reproduce the packaged conformance checks

Extract the candidate into an empty directory, install its hash-pinned `requirements.txt`,
and run `python tools/test_conformance_suite.py` and
`python tools/test_implementation_reports.py` there. The candidate includes their generators,
runner and fixture data, and CI tests these commands from an isolated extraction. Other
repository-wide gates may require the full checkout; this package is scoped to semantic
review and the packaged conformance checks. A superseded implementation report passes only
structural archive-retention checks without its historical suite; supply the matching suite
to verify its coverage. None of these checks supplies independent acceptance.

## Acceptance handoff

The module table above must match the reference manifest (39 modules); the package gate
checks it. The reviewer completes the matching rows in `review-manifest.json` and records
name, organization, independence/conflicts, UTC review date, exact archive SHA-256, and an
explicit decision. For each finding retain severity, affected IRIs, counterexample, expected
result, disposition, regression evidence and compatibility impact. Attach both validator
versions/reports and any independent format comparisons to the review record. Unresolved
items remain visible. Updating source files invalidates acceptance of the affected hashes.

The implementing assistant has not supplied an independent reviewer identity, decision,
conflict attestation or signature. A maintainer must obtain that review against the pinned
candidate. Passing the package gate verifies reproducibility and record structure only.

The capability matrix now distinguishes competency-TSV references from authored family
contracts. Every module publishing shapes has positive and negative authored contracts.
Resource references remain discovery aids: they do not establish that every axiom, term
combination, profile or external format variant has been semantically accepted.

## Record validation and construct inventory

For a completed decision, top-level `status` equals `decision` (`accepted`, `rejected` or
`changes requested`), `reviewed_at` is a UTC ISO timestamp, and each module has an explicit
decision from that same vocabulary. An overall acceptance requires all module decisions to
be accepted. These checks validate record structure, not reviewer identity or independence.

`../validation/construct-coverage.json` inventories every live registered normative clause,
every measured SHACL component obligation and every documented vocabulary declaration.
It separates processor-case citations, measured positive/negative witnesses, declaration
checks and remaining semantic review obligations. A case citation is not an implementation
execution result. Review-only clauses are explicitly not counted as tested. Resolve those
clauses against the candidate before claiming complete specification acceptance.

A completed machine-readable record also supplies nonblank `organization`, `conflicts`
(`none declared` is explicit), and `reviewed_scope`; the reviewer sets
`independence_attested: true` and binds `reviewed_archive_sha256` to `archive_sha256`.
Each module records a nonblank `disposition`. `findings` is an explicit list (empty if none),
with `id`, `severity`, `affected_iris`, `counterexample`, `expected_result`, `disposition`,
`regression_evidence`, and `compatibility_impact` for every finding. These attestations are
supplied by the reviewer; the implementing assistant leaves them absent while review is pending.

Finding text members are nonblank strings, IDs are unique, and `affected_iris` is a nonempty
list of absolute IRIs. Each finding has `status`: `resolved`, `open`, `not a defect`, or
`accepted limitation`. An overall accepted decision cannot contain an open finding.
These checks establish record consistency; they do not establish that a claimed correction
or an attestation is true.
