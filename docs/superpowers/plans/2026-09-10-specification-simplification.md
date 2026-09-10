# Specification simplification ? prerelease implementation

Status: the seven selected simplifications and the current generated-code follow-through are implemented in the isolated `prerelease-current-contract` branches. Local full-build, specification and staged-consumer acceptance are complete; external release acceptance is separate. This revision supersedes the original compatibility-preserving plan. Breaking changes are permitted before release; historical replay and live deployment are not acceptance requirements.

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
- Interpreter zlib/raw-DEFLATE level parameters are now supported (-1 or 0..9). Generated Kotlin readers and writers now preserve the same settings on supported byte fields. Single and counted encoded byte/struct blocks support fixed, field-referenced and expression extents. Per-element inferred lengths must agree; declared encoded-size checks run only after layout convergence. Encoded repeat-until blocks remain rejected because this subset does not define their per-element framing. Other codec parameters and unsupported encoded dispatch/layout combinations also reject.
- No production deployment, fresh GDAL oracle generation or independent ontology acceptance is claimed. Human browser/print acceptance and remote/hosted release acceptance remain separate. The complete local build, all specification gates, artifact staging and separate consumers now pass.

Generated-runtime follow-through: [compiled codec option evidence](../../../review-2026-09-05/generated-codec-options.html).

## Generated-code adversarial follow-through

Implemented a deterministic 180-combination payload corpus, every strict compressed prefix for six short-payload pipelines, trailing-byte rejection and exact cumulative budget boundaries. The 50-test generated-code verification suite passes. See [adversarial evidence](../../../review-2026-09-05/generated-codec-adversarial.html). This partially addresses the carried-forward negative/fuzz work; coverage-guided campaigns and additional format families remain open.

Generated counted-block follow-through: [implementation and verification](../../../review-2026-09-05/counted-codec-blocks.html). Positive fixed-size counted byte blocks now decode per element. The new rejection test also fixed generated writer encoded-size enforcement. This historical boundary is superseded by the completion evidence below for dynamic extents and single/counted encoded structs. Unframed repeat-until remains an explicit unsupported contract.

## Completion evidence ? September 10, 2026

- Added explicit encoded extent, pipeline and options to nested generated operations; decoded substreams preserve parent/root contexts and share request work, depth and cumulative decoding budgets.
- Counted byte blocks support field/expression lengths. Writer inference measures each element, rejects shared-length conflicts and preserves the following trailer.
- Deferred encoded-size validation runs only on the converged pass, avoiding premature rejection of backpatched sizes. Invalid final lengths reject before bytes return.
- Exact JDK wire fixtures cover single/count encoded structs and decoded-stream offsets. Negative tests cover decoded underflow, work/depth/decoded-byte limits and conflicting lengths.
- Full engine build: 3,002 passed, eight existing skips, no failures/errors. All 37 specification gates pass.
- Six local release modules staged; independent library and generated-code consumer projects pass, including RDF-to-generated parameterized counted nested frames. Generated release CI now explicitly includes standalone compilation via `:codegen-verify:check`.

See [completion report and logs](../../../review-2026-09-05/simplification-complete.html). No GDAL wave-2a expansion or codec-generation phase-2 work was included, as agreed with the user. No live deployment or external reviewer acceptance is claimed.
