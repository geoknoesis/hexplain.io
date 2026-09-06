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
- **ORT-10 Compatibility and publication:** Assess stricter shape revisions, retained immutable artifacts, live dereferencing failure, namespace policy and migration impact.

## Module-by-module record

| Module | Resources | Reviewer finding / disposition |
|---|---:|---|
| specification/adv | 13 | Unreviewed |
| specification/aspect/bundle | 33 | Unreviewed |
| specification/aspect/color | 2 | Unreviewed |
| specification/aspect/encoding | 4 | Unreviewed |
| specification/aspect/fsmeta | 6 | Unreviewed |
| specification/aspect/geometry | 7 | Unreviewed |
| specification/aspect/integrity | 3 | Unreviewed |
| specification/aspect/networkflow | 10 | Unreviewed |
| specification/aspect/packaging | 7 | Unreviewed |
| specification/aspect/pointcloud | 3 | Unreviewed |
| specification/aspect/provenance | 7 | Unreviewed |
| specification/aspect/raster | 32 | Unreviewed |
| specification/aspect/sampling | 9 | Unreviewed |
| specification/aspect/security | 13 | Unreviewed |
| specification/aspect/signal | 3 | Unreviewed |
| specification/aspect/spatialref | 53 | Unreviewed |
| specification/aspect/tabular | 6 | Unreviewed |
| specification/aspect/time | 3 | Unreviewed |
| specification/axv | 8 | Unreviewed |
| specification/bddo | 183 | Unreviewed |
| specification/conf | 7 | Unreviewed |
| specification/dfv | 26 | Unreviewed |
| specification/dlv | 43 | Unreviewed |
| specification/gv | 15 | Unreviewed |
| specification/hexplain | 47 | Unreviewed |
| specification/idv | 11 | Unreviewed |
| specification/npv | 10 | Unreviewed |
| specification/register/checksum | 6 | Unreviewed |
| specification/register/color | 6 | Unreviewed |
| specification/register/geometry-type | 9 | Unreviewed |
| specification/register/media-encoding | 29 | Unreviewed |
| specification/register/part-role | 14 | Unreviewed |
| specification/register/us-nato-security | 80 | Unreviewed |
| specification/req | 12 | Unreviewed |
| specification/vdv | 17 | Unreviewed |

## Evidence boundaries

The generated GDAL corpus covers seven ISO-WKB families, four ordinate layouts, empty/nonempty geometries and two byte orders. Actual GeoPackage tables cover 60 rows with geometry/null distinction, exact integer attributes and SRS identifiers. It does not prove native Shapefile/FlatGeobuf/GeoParquet decoding, CRS reprojection, topology, curves, arbitrary mixed-dimensional collections or all external format variants.

The reviewer should specifically assess whether dimensionality documentation adequately distinguishes total ordinate count from spatial dimension, and whether additional profile-specific constraints are needed. Broader interoperability and ontology adequacy are separate questions.

Sources: [OGC GeoPackage](https://www.geopackage.org/spec140/index.html), [W3C SHACL](https://www.w3.org/TR/shacl/), [RDF vocabulary publication](https://www.w3.org/TR/swbp-vocab-pub/).
