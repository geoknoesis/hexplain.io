# Codec generation phase 1: what it demonstrated, and what it left open

**Date:** 2026-09-07
**Branch:** `hexplain-tools` `feature/codec-generation-phase-1` (41+2 commits, off `feature/heif-isobmff`)
**Spec:** `docs/superpowers/specs/2026-09-06-pluggable-codec-generation-design.md`
**Plan:** `docs/superpowers/plans/2026-09-06-codec-generation-phase-1.md`

## What was built

Four Gradle modules in `hexplain-tools`, 333 tests, `core/` unmodified throughout.

| Module | Role |
|---|---|
| `codegen` | Lowers `FormatIR` → `CodecPlan` (CodecIR), validates it, computes capability demands, hosts the backend SPI and the `hxc` CLI |
| `runtime-kotlin` | Hand-written primitives generated codecs link against. **No `:core` dependency** |
| `codegen-kotlin` | Reference backend: emits Kotlin reader and writer source |
| `codegen-verify` | Generates codecs at build time, compiles them, and differential-tests them against the engine |

## What was demonstrated

Generated Kotlin codecs agree with the engine on:

- **Reads** — values, runtime types, map key order, element counts, and failure messages.
- **Writes** — byte-for-byte output equal to `Metawriter`, round trip (parse → write reproduces the original bytes), stability across parse → write → parse → write, and correction of a caller-supplied length that disagrees with reality.
- **Refusals** — both sides reject an invalid descriptor with the same message.

Both gates were confirmed **non-vacuous by mutation**: generated files were mutated and the suites re-run with generation skipped. A runtime-type-only change (`u8()` → `u8().toLong()`, identical value) and a key-order-only change are invisible to value comparison and are caught solely by the `shape` assertion. Eighteen writer mutations were killed; one survivor exposed a missing fixture, which was added.

**On a real format:** PNG (`core/src/main/resources/png-profile.ttl`) generates and passes the differential, on two samples covering 16 of its 17 conditional data-type arms.

**The standalone property is compiler-enforced**, not asserted: `codegen-verify` compiles every generated codec a second time in a `standalone` source set whose only dependency is `runtime-kotlin`. Verified live — injecting an `io.hexplain.core` import lets `compileTestKotlin` succeed while `compileStandaloneKotlin` fails.

## Engine behaviours a future backend author must know

These cost fix rounds to discover. Each is a place where a reasonable guess is wrong.

1. **There are two different field-resolution rules.** `sizeFromField`, `repeatCountFromField` and `atOffsetFromField` are resolved by name with a parent fallback (`Metaparser.sizeFieldValue:834`, `containsKey`-then-parent). HEL's own bare-accessor path has **no** fallback. Conflating them makes a descriptor with the same field name at two nesting levels silently evaluate the wrong one.
2. **`self` is not the current struct.** `HelEvaluator` binds `self` to `selfContext` — the repetition element. `parseStructSequence` binds both `self` *and* a bare accessor to the element, and `parent` to the enclosing struct. A PNG-shaped `repeatUntil: tag == 0` evaluated against the wrong scope runs to end-of-stream and swallows every following field.
3. **A struct is its own parent during conditional dispatch.** `Metaparser.kt:1052` passes `context` as both context and parent (`Metawriter.kt:469` repeats it). Passing the genuine enclosing struct makes every dispatch condition evaluate null.
4. **`and`/`or` are eager; the conditional is lazy.** `evaluateBinaryOp` evaluates both operands before dispatching (215-217), so Kotlin's `&&`/`||` diverge. But the *coercion* short-circuits (221), and the conditional genuinely is lazy (100-105).
5. **Arithmetic dispatches on runtime operand type** — floating point if either side is `Double`/`Float`, else exact truncating integer division via `BigInteger` (413-438). Pre-coercing to `Long` erases both.
6. **Equality throws** on a string-vs-number comparison rather than returning false (533-563); and `!=` is not `!eq` — `OP_NEQ` yields false when either operand is null (220).
7. **Scalars ignore a declared extent.** INTEGER/FLOAT fields read at intrinsic width; only a `terminator` overrides, for any type. A declared `size` on a numeric field is silently discarded by the engine.
8. **Struct extents and field extents type differently.** `resolveStructSize:714` casts `as? Number`, so a *text* struct size resolves to null and the engine applies **no region at all**. Field sizes and counts accept text.
9. **Regions measure from two different origins.** A struct-level size measures from `structStartPos` (`:354`, `:495`); a sequence or nested-field region measures from the current position (`:956`, `:1024`, `readOneElement:1150`). An unresolved extent also means *opposite* things at the two sites — the sequence site reports, the nested site treats null as no region.
10. **Alignment is excluded for offset-addressed fields** (`376-399`) and applied to the computed target instead (`791-796`). Applying it sequentially corrupts where the next field starts.
11. **A constant field's value is stored in the tree**, at its declared type, and the raw span is compared separately (`parseStruct:465`, `511-540`). But the *writer* takes the constant from the descriptor, not the caller (`Metawriter:531`) — the asymmetry is deliberate.
12. **Only SIZE is computed by the writer**, and it silently overwrites a disagreeing caller (`Metawriter:91-96`). COUNT is taken and *checked* with its own diagnostic (404-411); OFFSET is taken unchanged (332-338); CHECKSUM has no writer counterpart.
13. **Unsigned 64-bit widens to `BigInteger`** so the value stays positive (`readUnsignedLong:1281-1296`). This is a JVM workaround — Rust and C have native `u64` and must **not** copy it, which means their differential harnesses need a normalisation step Kotlin's does not.

## Open gaps carried to phase 2

All are named and commented at their emission sites in the code. None miscompiles silently except where noted.

**Read side.** G3 `sizeof()` over a recorded byte span (needs per-field spans the IR does not carry). G4 bit-cursor scoping across struct and pointer boundaries. G7 bytes-vs-string comparison encoding (always UTF-8; the engine uses the declaring field's `bddo:encoding`). G10 `structRegion` raises where the engine rewinds. **G14 non-leading `.parent` is treated as a member lookup — the one gap most likely to become a wrong answer rather than a refusal, and the first to close.** G15 trailing `.size`. G17 `bddo:usesStruct` refused (unimplemented; the corpus uses it nowhere). G18 `Bind` emitting null.

**Write side.** W6 no region stack, so `stream.length`/`remaining` and `STREAM_END` pointers carry the engine's refusals — both sides refuse, so parity holds. W10 layout keys accumulate where the engine clears per pass. W11 `checkRepeatCount` raises eagerly where the engine defers to end-of-pass.

**Design debt.** `PublishToRoot` mirrors a hard-coded PNG special case from `Metaparser` into the format-neutral IR. It is justified by tests (disabling it fails three), and the neutral alternative — filtering engine-published root keys out of the comparison — was rejected because `IHDR` is a key the descriptor's own HEL references, so filtering would trade a visible difference for a silent one. It remains a wart every future backend inherits.

**Not built, deferred by plan.** The out-of-process backend protocol and its versioned CodecIR JSON schema. That schema's golden-file guard becomes a prerequisite the moment a second backend lands.

## A bug this work found in our own descriptor

`png-profile.ttl`'s `iTXt_Text` size expression is off by one: it counts four singleton bytes where the layout needs five (NUL, flag, method, NUL, NUL). **`Metaparser` itself over-reads on an iTXt chunk.** Pinned by a test asserting the engine currently throws, with a `tEXt` control proving the carrier bytes are well-formed — so the test fails when the descriptor is fixed rather than asserting the bug is correct. `core/` was out of scope for this work; the fix is a follow-up.

## What phase 1 did not demonstrate

- Any target language other than Kotlin. The value of the CodecIR layer is *argued* — that a backend author need not read `Metaparser.kt` — and stays argued until a second backend exists.
- Tiers T2 (semantic emission) and T3 (conformance).
- Negative and fuzz corpora beyond the single failure-parity fixture per path.
- Performance. No benchmark was run; the speed driver is unmeasured.
