# Numeric and codec boundary revision — 5 September 2026

This revision corrects the 1.1 raster/spatial-reference working drafts and adds one controlled encoding value. Stable term IRIs remain unchanged. These draft constraints are stricter; a graph passing the earlier draft can now fail for the cases below.

- Finite calibration, affine and RPC coefficients are checked by numeric value as well as lexical spelling. A literal such as `"1e309"^^xsd:double` maps to infinity and must fail even though it is not spelled `INF`. Finite binary64 extremes, signed zero and NaN used specifically as a no-data sentinel remain supported by their applicable contracts.
- Two bands cannot use the same numeric index under different integer datatypes. Index uniqueness compares numeric values.
- RDF list well-formedness compares RDF term identity. Two equal-valued but distinct literals are still two `rdf:first` values and make that cell malformed. This differs deliberately from numeric band-index comparison.
- `menc:Zlib` explicitly identifies RFC 1950 framing. `menc:Deflate` identifies raw RFC 1951 DEFLATE. The reference engine now dispatches these identifiers accordingly; PNG profile declarations using the previous zlib alias must migrate to `menc:Zlib` or the RFC 1950 IRI. Gzip remains a separate encoding.

The reference engine rejects known DLV declarations that its current IR cannot represent, including chunk addressing, conditional layouts, packed cell declarations and dynamic strides. A declaration being expressible in the vocabulary is not evidence of runtime support. Consumers must surface the unsupported-capability diagnostic instead of substituting a contiguous interpretation.

Validation evidence is in `tools/test_numeric_boundaries.py`, the existing geospatial competency cases, and the engine's `NumericShapeBoundaryTest`. The latter repeats finite-value and band-index checks using Jena, independently of pySHACL.

The packaging and archive 1.1 drafts add scoped membership/path validation and correct archive target leakage. `axv:ArchiveShape` now targets `axv:Archive`, rather than every subject using the shared `apkg:hasEntry` property. Archive entry constraints target archive entry instances and archive-specific properties, rather than every resource with a filename. The generic packaging contract requires resource-valued, typed members and at most one string path per entry. It permits empty containers, unnamed entries and duplicate paths on distinct entries. Verbatim paths are not normalized and are not authorization to extract to a filesystem destination. Earlier graphs with literal members or conflicting paths on one entry now fail. Eleven positive/negative competency cases run with inference disabled and assert the failing property path.

See [SPARQL RDF term identity](https://www.w3.org/TR/sparql11-query/#func-sameTerm), [XML Schema double values](https://www.w3.org/TR/xmlschema11-2/#double), [RFC 1950](https://www.rfc-editor.org/rfc/rfc1950) and [RFC 1951](https://www.rfc-editor.org/rfc/rfc1951).


## Emitted graph and sampling revision

Sampling and Signal 1.1 add selected instance constraints for sample counts and rates. Counts remain positive integers; rates now admit positive finite decimals such as 0.5 Hz. Numeric strings, fractions as counts, nonpositive rates and binary floating literals do not conform to these shapes. Existing valid integer-family rates remain valid. Sample format is restricted to this revision's three declared interpretations when SamplingShape is selected.

The [validation contract](../validation/index.html) distinguishes description checks, parsing, emitted-instance validation and interoperability. The shared 36-case corpus runs in pySHACL and Jena; its first immutable local snapshot is [2026-09-05.1](../../releases/2026-09-05.1/manifest.json). It is a local working-draft artifact, not a claim of deployed namespace negotiation.

The engine's TIFF and PNG profiles now declare their mapping targets and pass description SHACL without the former expected residual violations. TIFF physical tag metadata moves from undeclared image-vocabulary names to the profile-owned `https://hexplain.io/formats/tiff#` namespace. Width, height and bit depth use the raster/sampling aspect IRIs. TIFF scalar meanings are emitted only after resolving the inline value; RATIONAL pointers are no longer emitted as resolutions. Extraction still covers the first classic-TIFF directory, not complete TIFF semantics.

PNG's unscaled gAMA integer, pHYs counts/unit and tIME second component now use explicit profile-owned raw properties (`gammaEncoded`, `pixelsPerUnitX`, `pixelsPerUnitY`, `unitSpecifier`, `modificationSecond`); a second component is not a complete modification date. Text titles and authors use `dcterms:title` and `dcterms:creator`. Consumers of the previous emitted IRIs must migrate deliberately. These profile corrections do not change the independent raster pixel adapter's GDAL comparison scope.


## DLV and Bundle 1.1: integral quantities (6 September 2026)

DLV cellBitWidth, dimensionSize, dimensionStride and chunkSize now require positive XML Schema integer-family literals. Bundle minParts and maxParts require nonnegative integer-family literals. Decimal values (including 3.0), floating-point values and strings are rejected; migrate exact whole values to xsd:integer. Fractional quantities cannot represent these counts. Term IRIs are unchanged; this is a stricter validation contract and ontology versions advance to 1.1. Archived snapshots remain unchanged.

The shared layout-competency.tsv has 47 positive/negative cases. It tests fixed/dynamic packing, bit order, numeric boundaries, required compound roles, nested assets, primary-part typing and count contradictions without inference or SHACL-AF rule execution. It does not certify decoded pixel arithmetic, arbitrary nesting, every vocabulary combination, or external ontology review. Missing profile definitions are not proof of conformance to an unavailable profile.

Datatype alternatives follow the [SHACL datatype constraint](https://www.w3.org/TR/shacl/#DatatypeConstraintComponent): datatype identity is checked explicitly rather than inferred from numeric comparisons.


## Bundle 1.2: explicit primary membership (6 September 2026)

Required-role checks now follow both hasPart and primaryPart without relying on RDFS materialization. A primary-only carrier with the required role satisfies that requirement. AssetShape now rejects literal and untyped hasPart values; assert Part explicitly on each member. Unrelated resources remain outside the Asset target scope. This stricter member-typing contract advances Bundle to 1.2. The layout/compound corpus grows from 47 to 52 cases; prior immutable snapshots are retained.

This change does not materialize subproperties or run facet-lifting rules. Profile definitions must still be supplied; generic SHACL validation cannot infer unavailable external profile requirements.


## Geometry-type register 1.1 (6 September 2026)

Adds GeometryCollection, the missing concept for ISO WKB type 7. The existing six simple-feature concepts retain their IRIs. A collection does not imply identical member types; dimensional homogeneity remains a format-profile constraint. No globally shared CRS, topology or nonemptiness is inferred from collection membership. This addition completes the seven-family mapping used by the measured GDAL WKB corpus; it does not add curve, surface or mesh concepts.


## Geometry 1.2 validation (production follow-up)

Selecting geometry shapes now validates geometryType as an explicitly typed SKOS concept IRI and dimensionality as one positive integer-family value. Zero, negative, decimal and string dimensions reject. This tightens conformance without changing property IRIs. Supply concept definitions in the selected data/vocabulary graph. Missing dimensionality and Z/M flags remain unknown; no false values are inferred and no fixed 2?4 dimensional limit is imposed globally.

## Fixed terminated fields and scan budgets

The writer rejects fixedValue plus terminator explicitly: existing raw fixed-value validation does not define a compatible framing contract. It no longer returns incomplete wire data for this combination. Ordinary terminated fields retain their tested contract. Automatic fixed-length inference remains a separately restricted contract. Parser sentinel scanning is linear-time, accounts for the failure table before allocation and charges scanned bytes plus the copied result to materialization limits. Inputs close to old materialization limits may now fail earlier; raise limits only within the deployment's memory budget.
