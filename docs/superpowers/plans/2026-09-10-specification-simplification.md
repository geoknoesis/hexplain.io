# Specification simplification ? prerelease implementation

Status: the seven selected simplifications are implemented in the isolated `prerelease-current-contract` branches. This revision supersedes the original compatibility-preserving plan. Breaking changes are permitted before release; historical replay and live deployment are not acceptance requirements.

## Implemented work

| Area | Implementation | Evidence |
|---|---|---|
| Shared constraint authoring | 33 fragments expanded into 13 canonical modules; each fragment has consumers and local activation provenance | `test_specification_patterns.py`, `constraint-inventory.json` |
| Activation separation | Module targets remain local; shared lexical fragments introduce no global targets or helper imports | Current expanded RDF equality and inventory freshness |
| Value sources | One resolution procedure, six family rows for units, evaluation phase, exact conversion and writer inference | Shared processing guide; existing core boundary and writer suites |
| Ordered selection | One first-match explanation with seven family-specific rows, including dispatch as a separate mechanism | Full core suite including conditional and dispatch tests |
| Encoding normalization | Shorthand and step lists share ordered codec identifiers and stage options; zlib/raw-DEFLATE level settings are supported, other parameters reject | `EncodingNormalizationTest`, encoded writer and code-generation tests |
| Primitive presets | 26 presets generated from explicit base/width/signedness/order/datatype entries | Generation gate and full core suite |
| Human reference | 795 complete entries; 679 links to shared exact visible scope notes; detailed comparison tables | Term-reference, HTML synchronization and documentation gates |

## Intentional prerelease changes

- The equivalence gate compares current authoring against current RDF, not against an obsolete immutable working draft. Historical archive hashes remain checked.
- The compiler now honors unparameterized `hasEncodingStep` instead of silently ignoring it.
- Malformed encoding declarations and unsupported `codecParameter` fail at compilation.
- Exported `ir:encodedWith` is one RDF list. Consumers must preserve list order and repeated codec stages instead of reading an unordered property set.

Latest parameterized execution evidence: [codec options](../../../review-2026-09-05/codec-options.html).

## Validation

- Eight affected specification gates pass, including 1,165 two-sided constraint obligations, current generation, 36 synchronized module pages and complete term references.
- Full `:core:test :codegen:test :hdl:test`: 2,657 tests, zero failures/errors, seven skips.
- Independent JDK zlib/gzip vectors check normalized decoding order, writer bytes and nested trailers. Negative tests cover truncated streams, decoded output limits, unknown codecs, malformed lists, cycles and unsupported parameters.
- The pending review package contains 184 files and is reproducible. Independent reviewer acceptance is still pending.

See [current implementation report](../../../review-2026-09-05/simplification-implementation.html) and its linked logs for measured scope.

## Deliberate boundaries

- Field references remain distinct from arbitrary expressions; no general inversion is claimed.
- Physical dimensions, semantic axes, packing width and significant bit depth remain distinct.
- Conditional families retain their own context, fallback and exception semantics.
- Interpreter zlib/raw-DEFLATE level parameters are now supported (-1 or 0..9). Generated Kotlin readers and writers now preserve the same settings on supported byte fields. Fixed-size counted byte blocks now decode and encode per element. Other parameters, encoded nested structs, repeat-until blocks and dynamic encoded element extents retain explicit capability rejection.
- No production deployment, fresh GDAL oracle generation or independent ontology acceptance is claimed. Browser/print manual acceptance and the complete cross-repository release workflow remain separate from the automated checks run here.

Generated-runtime follow-through: [compiled codec option evidence](../../../review-2026-09-05/generated-codec-options.html).

## Generated-code adversarial follow-through

Implemented a deterministic 180-combination payload corpus, every strict compressed prefix for six short-payload pipelines, trailing-byte rejection and exact cumulative budget boundaries. The 50-test generated-code verification suite passes. See [adversarial evidence](../../../review-2026-09-05/generated-codec-adversarial.html). This partially addresses the carried-forward negative/fuzz work; coverage-guided campaigns and additional format families remain open.

Generated counted-block follow-through: [implementation and verification](../../../review-2026-09-05/counted-codec-blocks.html). Positive fixed-size counted byte blocks now decode per element. The new rejection test also fixed generated writer encoded-size enforcement. Dynamic extents, repeat-until and encoded nested structs remain open.
