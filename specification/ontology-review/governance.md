# Specification maintenance and release policy

This is the candidate maintenance policy. Adoption and named role assignments require maintainer sign-off; this document is not evidence that those assignments occurred.

## Responsibilities

The release maintainer freezes the candidate and records the source revision, artifact hashes, gate results and outstanding issues. Each module needs an accountable modeling owner. An independent reviewer records identity, affiliation, conflicts, scope, findings and an explicit decision against those hashes. The implementation author cannot supply that independent decision.

## Change classification

Editorial changes must preserve graph meaning and validation behavior. Vocabulary additions need definitions, scope, reuse rationale and competency evidence. Changed shape targets, stricter constraints, altered units, defaults or interpretations require compatibility review even if every term IRI is unchanged. Existing release archives must never be overwritten. Deprecated IRIs retain their meaning and a documented replacement/migration path; do not silently reuse an IRI.

## Normative contract checklist

For every named shape and normative statement, record its owner, source, focus-node scope, selected modules, inference policy, applicable paths, positive case, negative case, boundary case and expected report component/path. The generated constraint inventory is a starting list, not automatic coverage certification. Record why a requirement needs a mathematical argument, independent format comparison or human review instead of SHACL. Missing values do not imply zero, false, permission or inherited values. Explicit defaults and conversions require a profile contract. Byte layout, numeric interpretation, units and coordinate order must remain separate claims.

The SHACL data/shape graph and target distinction follows the [W3C SHACL Recommendation](https://www.w3.org/TR/shacl/). A conforming report with no focus nodes is not semantic acceptance. RDFS/OWL axioms describe meaning; constraints validate selected graphs. Neither security markings nor container membership perform authorization.

## Acceptance record

Before release promotion retain: exact candidate revision; all package entry hashes; both validator versions and reports; current and historical compatibility replay; independent semantic comparisons with unsupported variants; reviewer identity and decision; dispositions and executable regressions for blockers; migration notes; license and dependency inventory; named rollback owner. Run all offline gates from a clean checkout. Rebuild the review package using `python tools/_review_candidate.py` and check it using `python tools/test_review_candidate.py`.

No unresolved correctness blocker may be waived by a numerical score. Exceptions need an accountable owner, bounded impact, rationale and review date. Live publication is deferred and outside the current scoring scope. New modeling changes invalidate acceptance of affected hashes and require re-review. Local candidate packaging is not registry publication or deployed consumer acceptance.
