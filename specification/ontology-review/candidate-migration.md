# Candidate compatibility and semantic boundaries

This candidate extends evidence and review tooling. It does not change canonical ontology or shape graphs, reuse term IRIs, add implicit defaults or alter authorization behavior. Historical release archives remain byte-for-byte preserved. The new local draft captures the expanded corpus; it is not independent approval or a live release.

## Consumer expectations

Consumers should select explicit modules and retain the selected shape bytes and validator version with their validation report. A vocabulary version alone does not identify an opt-in profile. Preserve raw encoded values separately from interpreted quantities; do not reinterpret a missing value as zero or false. Unknown CRS identifiers do not authorize an axis swap or reprojection. Z and M are distinct, and an M ordinate has no implicit time unit. Empty geometry and absent geometry are different values.

The added layout cases distinguish fixed packing width, field-derived width, bit order and byte stride. A positive integer wider than a machine word can be a valid RDF declaration without being supported by a particular engine. Shape conformance must not be advertised as execution capability. Parent/child membership does not transfer required roles or security markings: each targeted resource is validated in its own scope.

## Evidence changes

- Shared corpora grow from 110 to 133 cases: 69 layout/compound, 19 opt-in security, 36 instance and 9 geometry cases. These are semantic declaration tests, not a claim of complete vocabulary coverage.
- Seven security constraint mutations and five packing/reference mutations test sensitivity independently of the positive controls. Security target-removal tests show why vacuous conformance must remain distinguishable from acceptance.
- The GDAL oracle grows from 112 to 136 geometry cases. The 24 additions cover nested collections, empty members, polygon holes, negative Z/M and finite numeric boundaries in both byte orders. Four GeoPackage layers retain 60 rows. This does not add native driver families, reprojection or topology certification.
- Candidate manifest text hashes normalize source text to LF for portability. Hashes of decoded binary fixtures and immutable historical archives remain byte hashes.

## Remaining acceptance

The independent reviewer must audit normative meanings, nested shape logic, SPARQL requirements and terms that are not exercised by the shared corpora. The generated named-shape inventory does not turn term mentions into constraint coverage. Named maintainers must adopt the governance policy and record dispositions. Live hosting is deferred and excluded from scoring; no successful deployment is inferred from offline compatibility replay.


## Network 1.1 constraint correction

The subsequent constraint audit changes Network and Networkflow to 1.1. Transport ports now include zero and are bounded to 65535; sequence and acknowledgment numbers are bounded to 4294967295. Integer-family datatypes are accepted; fractions, strings and nonfinite values reject. Address, port and TCP shapes activate on either endpoint/number property, rather than relying on only a source field. Forty independent boundary cases run in pySHACL and Jena.

This corrects UDP's optional source-port encoding described by [RFC 768](https://www.rfc-editor.org/rfc/rfc768) and the field widths described by [RFC 9293](https://www.rfc-editor.org/rfc/rfc9293). A zero wire value is representable; the profile still determines whether it denotes a usable endpoint. Existing consumers that relied on unchecked destination-only fields, fractional values or overflow must correct their data. Shapes now reject some previously accepted graphs. Earlier immutable snapshots retain their original contracts. The preceding no-canonical-change statement describes the earlier evidence-only pass, not this subsequent Network 1.1 correction.
