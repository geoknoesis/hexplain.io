# Pluggable codec generation: format-specific codecs in a target language

**Date:** 2026-09-06
**Status:** approved design, not started
**Repos touched:** `hexplain.io` (spec), `hexplain-tools` (`codegen` modules, target runtimes)

## Why

The metaengine interprets. `Metaparser` walks `FormatIR` per field, per byte, deciding at
runtime — by null-checking `size` against `sizeFromField` against `sizeFromExpression` against
`terminator` against `sizeToEndOfStream` — what this field means. That is the right default: one
engine reads every descriptor, and a new format costs a descriptor rather than a release.

It has four costs, and all four matter at once.

**Reach.** The engine is Kotlin on the JVM. A hexplain descriptor cannot be read on an embedded
device, inside a GDAL native plugin, in a browser, or anywhere a customer's stack does not admit
a JVM. Every format hexplain describes is, today, a format only hexplain's JVM can read.

**Speed.** The IR walk costs map lookups and boxing on paths that run per cell. A parser
specialised to one format resolves at compile time what the interpreter resolves per field.

**Deliverable.** "Compile my format description into a codec in my language" is a product
surface the interpreter cannot offer.

**Proof.** The strongest available evidence that a descriptor carries a whole format is that it
can drive a code generator to a working codec — one that agrees with the interpreter, byte for
byte and triple for triple, on the existing fixture corpus. "Our interpreter reads it" is a
weaker claim about the same artefact.

This design adds a second backend behind the same descriptor. It does not replace the
metaengine, and it does not modify it.

## Prior art

This is a well-trodden shape. Four systems are worth naming, because each settles a question
this design would otherwise have to argue from first principles.

**Apache Daffodil** is the closest structural match. DFDL schemas normally run on an
interpreter, exactly like the metaengine; Daffodil added `daffodil-codegen-c` (originally
`daffodil-runtime2`) as a *second backend* emitting C from the same schema, invoked by a
`generate` CLI verb, aimed at embedded targets. It confirms both the shape and the honest
limitation: the codegen backend covers a documented *subset* of the specification, and says so.
See §6 — capability tiers are that admission, made structural.

**Kaitai Struct** is the reference for pluggability. Its compiler runs load → precompile (type
inference, name resolution, sanity checks) → compile, and a target language is an implementation
of `LanguageCompiler`; most reuse a shared `ClassCompiler` skeleton, and non-code targets
(GraphViz) plug in higher, at `AbstractCompiler`. A dozen-plus targets, each with a small
hand-written runtime library. §4 and §5 follow it closely.

**Spicy** (Zeek, successor to BinPAC) compiles a declarative format specification through an
intermediate language, **HILTI**, to C++. It is the argument for §2: a second, lower-level IR
between the format model and the emitters is what keeps the emitters small. Spicy also moved
*away* from LLVM bitcode to plain C++ for portability and maintainability, which is why this
design emits source rather than IR or machine code.

**EverParse / 3D** (Microsoft) compiles binary-format specifications to C with machine-checked
proofs of memory safety, arithmetic safety and double-fetch freedom, and ships in the Windows 11
kernel. It is the ceiling: a generated codec can carry guarantees an interpreter cannot. Nothing
here attempts formal proof, but it sets the standard that §7's negative-fixture and fuzzing
obligations exist to approximate.

Two more, for the plugin protocol specifically: **protoc** defines a backend as any executable
speaking `CodeGeneratorRequest`/`CodeGeneratorResponse` over stdin/stdout, which is why §5 has an
out-of-process tier; **OpenAPI Generator** and **ANTLR** use per-target classes plus templates,
which is the in-process tier.

None of them starts from an ontology-grounded description, and none carries a symmetric writer,
semantic mappings and conformance rules in the same artefact. That combination is the part that
is ours, and §6's tiers T2 and T3 have no equivalent in any system above.

## What is already in place

The layering this needs mostly exists, and none of it needs unpicking.

`Model.kt`'s header already states that the IR "serves as the universal blueprint for both the
metaparser and the code generators". `FormatIR` is fully decoupled from RDF and from Jena.

`ConformanceIR` is already a list of `(scope, HEL assertion, requirementIds, message)` producing
`Finding(requirementId, discrepancyType, message, byteOffset, scope, fieldName, constraintId)`.
There is no conformance *engine* to port — tier 3 is HEL evaluation plus a findings sink, which
makes it the cheapest of the four tiers rather than the most expensive.

`Codec` and `CodecRegistry` already draw the named-primitive boundary the raster design settled:
the descriptor names a codec, the engine supplies the algorithm. A generated codec inherits that
boundary unchanged — it names `menc:LZW`, and its target runtime supplies LZW.

The HEL AST is six node kinds: `LiteralNode`, `AccessorNode` (a path of `Key`/`Index` steps),
`UnaryOpNode`, `BinaryOpNode`, `FunctionCallNode`, `ConditionalNode`.

## The boundary

Stated explicitly, because it decides what "generated codec" means:

- **Lowering owns execution semantics.** Every precedence rule, offset-base resolution, region
  bound and cursor-versus-pointer decision is made once, in Kotlin, at lower time.
- **A backend owns syntax only.** It spells a step and a HEL expression in its language. A
  backend author need not read `Metaparser.kt`.
- **The target runtime owns the hard mechanics.** Bit cursors, region stacks, fixpoint length
  resolution, codecs, checksums, chunked layout. Hand-written per language, small, audited.
- **Codec algorithms stay named primitives.** Unchanged from the raster design.
- **Format identification stays out of scope.** The caller names the descriptor, as everywhere
  else in hexplain.

## 1. Architecture

```
descriptor.hx ──HdlCompiler──▶ BDDO/DLV/CONF Turtle ──ProfileLoader──▶ RdfToIrCompiler
                                                                              │
                                                        FormatIR + ConformanceIR
                                                                              │
                                                              Lowering (NEW, written once)
                                                                              ▼
                                                                         CodecIR
                                                                              │
                                                              Backend SPI (NEW, pluggable)
                        ┌────────────┬────────────┬────────────┬─────────────┴──────┐
                     Kotlin        Rust          C          TypeScript           Python
                        └────────────┴────────────┴──── links against ───┴────────────┘
                                                    ▼
                                            hexplain-rt-<lang>
```

`Metaparser` and `Metawriter` are unchanged. They become the reference implementation and the
differential oracle of §7 — which is what gives the equivalence claim its force.

## 2. CodecIR

### 2.1 A structured plan, not a bytecode VM

The raster design ruled out turning HEL into a bytecode VM. This holds that line for the same
reason plus one more: a generated codec is a customer-facing artefact, and a customer's security
team has to be able to read it. So a `CodecPlan` is a **tree of steps**, with control flow as
explicit nested nodes rather than jumps. An emitter maps a step to a statement and nesting to
nesting; the generated source has the shape a competent engineer would have written by hand.

```kotlin
data class CodecPlan(
    val format: String,
    val root: String,
    val structs: Map<String, StructPlan>,
    val enums: Map<String, EnumTable>,
    val registers: Map<String, RegisterTable>,   // static SKOS tables for inRegister
    val requirements: Map<String, RequirementIR>,
    val demands: Set<Capability>,                // what this plan requires of a backend
)

data class StructPlan(
    val name: String,
    val byteOrder: ByteOrderPlan,                // fixed, or resolved from a discriminator slot
    val bitOrder: BitOrder,
    val slots: List<Slot>,                       // named locals, in declaration order
    val steps: List<Step>,
    val semanticClass: ClassSelection?,          // fixed IRI, or first-match rule list
)
```

### 2.2 Step families

| Family | Steps |
|---|---|
| Cursor | `Seek(base, expr)`, `Align(n)`, `PushRegion(extent)`, `PopRegion`, `SaveCursor`, `RestoreCursor` |
| Primitive | `Scalar(slot, type, order)`, `Bits(slot, width, order)`, `Bytes(slot, extent)`, `Fixed(bytes)` |
| Aggregate | `Nested(slot, struct)`, `RepeatCount(slot, expr, body)`, `RepeatUntil(slot, expr, body)`, `RepeatToEnd(slot, body)` |
| Control | `If(expr, then, else)`, `Switch(expr, arms, default)` |
| Data | `ChunkTable(layout)`, `Cells(slot, layout)` |
| Transform | `Decode(slot, codecIds)`, `Encode(slot, codecIds)` |
| Semantic | `EmitClass(iri)`, `EmitProperty(iri, value, datatype, unit?, lang?)`, `EmitEdge(objectProperty, target)` |
| Check | `Assert(expr, requirementId, constraintId, message)`, `Checksum(alg, fromExpr, toExpr, slot)`, `EnumMember(slot, enum)` |
| Bind | `Bind(slot, expr)`, `Infer(slot, kind)` |

`Extent` is a single sealed node — `Fixed(n)`, `FromSlot(name)`, `FromExpr(hel)`,
`Terminated(bytes, consume, include)`, `ToRegionEnd` — with exactly one form surviving lowering.

### 2.3 What lowering decides

This is where the design's value sits. Today `Metaparser` re-derives, per field at runtime, a set
of rules that are properties of the descriptor and not of the data:

- which of five mutually-exclusive extent sources applies, and in what precedence;
- what `offsetBase` resolves against, and whether the read advances the cursor (sequential) or
  restores it (pointer);
- where the enclosing region ends, and how `sizeToEndOfStream` resolves inside one;
- when a conditional data type or conditional endianness rule becomes determinate;
- which slot a `sizeFromField` or `repeatCountFromField` name refers to, across parent scopes.

Lowering collapses each to one explicit node. A backend never re-derives any of it. Without this
step, five targets times four tiers is twenty independent opportunities to reimplement the same
judgment slightly differently — and the divergences would surface as a customer's C codec
disagreeing with the SaaS about one field of one file.

Lowering also **validates**: a plan that reaches a backend is well-formed — every slot reference
resolves, every codec id is registrable, every `Extent` is singular. Plan validation is a separate
pass with its own diagnostics, located back to descriptor source spans.

### 2.4 Read and write share one plan

A `StructPlan` is walked in read mode or in write mode. Steps are bidirectional by construction:
`Scalar` reads or writes, `Decode` pairs with `Encode`.

The exception is length and offset resolution. `Metawriter` resolves these by bounded
deterministic fixpoint passes with conflict detection (`Shared length 'x' requires unequal
payload sizes`), over a seek-capable growing buffer. **That algorithm stays in the target runtime,
not in generated code.** The plan emits `Infer(slot, kind)` markers where the writer must compute
a value the caller did not supply; the runtime runs the passes. Reimplementing fixpoint layout
resolution in five languages is the largest avoidable risk on the write path, and this is how it
is avoided.

## 3. HEL

Transpiled, not interpreted. Lowering resolves accessor paths to slot references wherever they
are static, leaving genuinely dynamic paths as runtime lookups. Each backend implements a
`HelEmitter` over the six AST node kinds — roughly 200 lines.

The builtins are not uniform in cost, and the design does not pretend they are:

| Builtins | Requirement |
|---|---|
| `len` `count` `sizeof` `eof` `substr` `substring` `startsWith` `trim` `toNumber` `concat` | None beyond the runtime's own types |
| `matches` | A regex engine — capability `REGEX` |
| `datetime` `evaluationInstant` | Date/time parsing — capability `DATETIME` |
| `inRegister` | The SKOS register emitted as a static table beside the codec — capability `REGISTER_LOOKUP` |
| `ringOrientation` `isSelfIntersecting` | Geometry predicates — capability `GEOMETRY` |

A backend declares which it supports. A descriptor using one a backend lacks is refused at
generation time with a located diagnostic, not discovered at runtime.

## 4. Target runtime libraries

`hexplain-rt-{kotlin,rust,c,ts,python}`: hand-written, small, versioned in lockstep with CodecIR.
Each provides byte-order readers, a bit cursor, a region stack, a growing write buffer with
fixpoint length resolution, a codec registry (Deflate, Zlib, Gzip, LZW, PackBits, Delta,
AdaptivePredictor, RunLength, Store), checksums (crc16-ccitt, crc32, adler32, md5, sha1,
sha256), the chunked-layout executor, a triple sink and a findings sink.

Generated code is thin over the runtime. Two consequences justify the duplication: emitters stay
at 1–2k lines each, and per-language safety review concentrates in one auditable place instead of
spreading across generated output that changes with every descriptor.

## 5. Pluggability

Two levels, both consuming the same versioned CodecIR schema.

**In-process** — for first-party backends:

```kotlin
interface CodecBackend {
    val id: String                                  // "rust", "c", "kotlin"
    val capabilities: Set<Capability>
    fun emit(plan: CodecPlan, options: EmitOptions): List<SourceFile>
}
```

Discovered by `ServiceLoader`, so adding a backend is adding a module.

**Out-of-process** — protoc's model, for third-party and other-language backends. CodecIR
serialises to JSON on stdin; source files come back on stdout. A Go or Swift backend needs no
Kotlin, no Gradle and no knowledge of `Metaparser.kt`. Because `FormatIRToRdf` already exists, an
RDF serialisation of the plan comes nearly free for tooling that prefers it.

The CodecIR JSON schema is versioned and guarded by golden-file tests, so a schema change that
would break an out-of-process backend is a visible, reviewed event.

## 6. Capability tiers

Tiers are cumulative:

| Tier | Adds | Oracle |
|---|---|---|
| **T0** Structural read | Parse to a tree | `Metaparser` |
| **T1** Write | Writer, round-trip, `Infer` | `Metawriter` |
| **T2** Semantic | Triple emission from `mapsToClass` / `mapsToProperty` / `valueExpression` | `ExtractSemanticGraph` |
| **T3** Conformance | `ConformanceIR` constraints → `Finding`s | `ConformanceEngine` |

Orthogonal feature capabilities a descriptor may demand: `BITFIELDS`, `POINTERS`,
`CHUNKED_LAYOUT`, `DELIMITED_TEXT`, `CONDITIONAL_ENDIANNESS`, `RECOVERY`, plus the four HEL
capabilities of §3.

`CodecPlan.demands` is computed by lowering. The generator refuses any (descriptor × backend)
pair whose demands exceed the backend's declared capabilities, with a diagnostic naming the
descriptor construct and the missing capability. This is the discipline of
`RdfToIrCompiler.rejectUnsupportedLayout`, promoted from an ad-hoc rejection to a first-class
matrix, and published as a support matrix the way Kaitai publishes one.

The tier system is what lets "all four tiers, five languages" be an honest roadmap rather than a
claim that is quietly untrue in C. A backend states what it does; the tool enforces it.

## 7. Equivalence

Differential testing is the acceptance gate, and simultaneously the product claim.

For every descriptor × fixture × backend, at the backend's declared tier:

- **T0** — the generated parse tree is structurally equal to `Metaparser`'s;
- **T1** — the generated bytes equal `Metawriter`'s, and parse → write → parse is stable;
- **T2** — the generated triples are isomorphic to `ExtractSemanticGraph`'s;
- **T3** — the generated findings equal `ConformanceEngine`'s, by requirement id and byte offset.

The existing corpus is reused unchanged: the GDAL fixtures, the geometry comparisons, the 611
raster pixel-parity comparisons. Their meaning changes. Today they are evidence that the Kotlin is
correct. Run through five backends, they become evidence that **the descriptor is complete** —
which is the claim the project exists to make.

Non-JVM backends run in CI containers behind a thin per-language test driver reading the same
fixture manifest, so a fixture is added once and every backend sees it.

Negative fixtures and fuzzing carry more weight here than for the metaengine, and belong to the
gate rather than to a follow-up: a malformed file that raises an exception on the JVM can corrupt
memory in generated C. The C backend does not ship without a fuzz corpus and sanitiser builds in
CI.

## 8. Module layout

In `hexplain-tools`:

| Module | Contents |
|---|---|
| `codegen` | CodecIR, lowering, plan validation, diagnostics, capability model, backend SPI, JSON schema |
| `codegen-kotlin` | Reference backend |
| `codegen-rust`, `codegen-c`, `codegen-ts`, `codegen-python` | Additional backends |
| `runtime/kotlin`, `runtime/rust`, `runtime/c`, `runtime/ts`, `runtime/python` | Hand-written target runtimes |
| `tests/differential` | Fixture-driven equivalence harness and per-language drivers |
| `tools` | `hxc` CLI |

CLI shape, following Daffodil's `generate` verb:

```
hxc gen --backend rust --tier 3 --out build/gen tiff.hx
hxc backends                       # the support matrix
hxc explain --backend c tiff.hx    # why this descriptor is refused, if it is
```

## 9. Sequencing

1. **`codegen` + CodecIR + Kotlin backend at T0/T1.** The cheapest possible target, and the only
   one where differential testing runs in-process in the same test run. Its real purpose is to
   prove the lowering is complete *before* a second language exists to be broken by a gap in it.
2. **Rust at T0–T2.** Memory safety without a C review burden. Compiles to WASM, which covers the
   browser and most TypeScript demand behind a thin wrapper — materially cheaper than a native TS
   emitter, and it front-loads the reach driver.
3. **T3 conformance on Kotlin and Rust.** Cheap, because `ConformanceIR` is already HEL plus a
   scope plus a message.
4. **C at T0/T1.** Last by design: the opcode set and the runtime contract should have stopped
   moving before work starts on the target where a lowering bug becomes a CVE.
5. **Native Python and TypeScript emitters** only if WASM proves insufficient in practice.

Two alternatives stay recorded rather than pursued. **Emitting `.ksy`** and letting the Kaitai
compiler do the work is a genuine interop escape hatch for reach alone, but it subsets the design
to Kaitai's feature set and discards the writer, the semantic mappings and conformance — three of
the four drivers. **Kotlin Multiplatform**, compiling the metaengine itself to JS and native, is
the cheapest answer to reach in isolation and remains the fallback for TypeScript; it abandons the
speed driver, produces no idiomatic C, and yields no codec specialised to a format.

## 10. Open questions

**Licensing of generated output and of the runtimes.** The project is proprietary and
all-rights-reserved, and artefacts are not published. A generated codec delivered to a customer
cuts across this in two places: what licence the emitted source carries, and on what terms
`hexplain-rt-c` reaches a customer who must link it. This is a commercial decision, not a
technical one, and the design does not presume an answer. It blocks shipping the SaaS deliverable;
it blocks nothing in phases 1–3.

**Recovery semantics.** `Metaparser` has recoverable-error paths that turn parse failures into
`Finding`s rather than exceptions. Whether generated codecs reproduce recovery or fail fast is a
per-tier decision worth settling before T3. Fail-fast is the safer default for C.

**Streaming.** `StreamedBytes` lets the metaengine avoid materialising large payloads. Whether
generated codecs expose incremental parsing — Spicy's central feature — or whole-buffer parsing is
deferred. Whole-buffer is assumed for v1.

## References

- Apache Daffodil, [Daffodil Code Generators](https://cwiki.apache.org/confluence/display/DAFFODIL/Daffodil+Code+Generators)
  and [C Code Generator ToDos](https://daffodil.apache.org/dev/design-notes/daffodilc-todos/)
- Kaitai Struct, [developer introduction](https://doc.kaitai.io/developers_intro.html) (compiler
  phases and `LanguageCompiler`)
- Spicy, [Generating Robust Parsers for Protocols & File Formats](https://docs.zeek.org/projects/spicy)
  and [Announcing the (New) Spicy Parser Generator](https://zeek.org/announcing-the-new-spicy-parser-generator)
- EverParse, [manual](https://project-everest.github.io/everparse/) and
  [Hardening Attack Surfaces with Formally Proven Binary Format Parsers](https://fstar-lang.org/papers/EverParse3D.pdf)
- Internal: `docs/design-hexplain-parser-writer.md` §7 (the earlier KSP sketch this supersedes),
  `docs/comparison-hexplain-kaitai.md` §6.3, and
  `docs/superpowers/specs/2026-09-06-descriptor-driven-raster-design.md` (the codec boundary)
