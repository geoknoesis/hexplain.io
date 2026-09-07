# HEIF / ISO BMFF Profile Implementation Plan (milestones M1–M3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A parse-verified Hexplain description of HEIF/HEIC and AVIF built on a reusable ISO/IEC 14496-12 base module, plus the three specification/compiler/engine changes that make the reuse real: keyed open dispatch (G2), stream-scoped pointer reads (G3, revised), and HDL modules with `import` (G1).

**Architecture:** One `.hx` module per standard (`iso-bmff`, `heif`, `codec-hevc`, `codec-av1`) and one tiny leaf profile per format (`heic`, `avif`), related by `owl:imports`. Box-type dispatch is a `bddo:DispatchTable` whose arms are independent RDF resources, so an importing module contributes arms without rewriting a list. Item payloads are read where their offsets are parsed (in `iloc`), through a pointer read that may leave the enclosing bounded region (`bddo:seekScope bddo:streamScope`). Verification is behavioural: the compiled descriptions parse libheif's own `example.heic` and `example.avif`, and the parsed values are compared with ground truth computed independently.

**Tech Stack:** Kotlin 2.2 / Gradle 8.7 / Jena (hexplain-tools: `hdl` compiler + `core` engine, JUnit 5); Turtle + SHACL + Python 3 gates (hexplain.io spec, `pyshacl`/`rdflib`); HDL profiles + Python gates (hexplain-profiles).

**Spec:** `docs/superpowers/specs/2026-09-06-heif-isobmff-profile-design.html` (this repo). Read §4 and §5 before starting.

## Global Constraints

- Three sibling checkouts, all used by absolute path: spec `d:/work/hexplain.io`, engine+compiler `d:/work/hexplain-tools`, profile library `d:/work/hexplain-profiles`. Bash tool paths: `/d/work/...`.
- **Vocabulary neutrality is a hard gate** (`tools/test_vocab_neutrality.py`): no term added to BDDO/Core/DLV/aspects may name a format (`box`, `heif`, `isobmff`, `mp4`, `item`… are format words — do not use them in BDDO term names; `dispatch`, `arm`, `key`, `seek`, `scope` are fine).
- Every new BDDO term needs `rdfs:label`, `rdfs:isDefinedBy <https://hexplain.io/ns/bddo>` and an `rdfs:comment` longer than 25 characters (the editorial pipeline turns the comment into `skos:definition`; `tools/test_term_reference.py` asserts it).
- After editing `specification/bddo/bddo.ttl`: run `python tools/_build_term_reference.py --enrich` from `d:/work/hexplain.io`, then `python tools/run_gates.py` (27 gates; all pass at baseline, ~12 minutes). Never hand-edit the generated `<section id="normative-owl">` or the `<!-- BEGIN GENERATED TERM REFERENCE -->` block in an `index.html`.
- After the spec changes land: run `python tools/sync_spec.py` from `d:/work/hexplain-tools` (updates `core/src/main/resources/bddo.ttl`), or `SpecSyncTest` fails.
- Gradle: `./gradlew -q --offline :hdl:test --tests "<fqcn>"` / `:core:test`. A single test class run takes ~35 s. Full `:core:test` takes several minutes; run it at each task's commit step where stated.
- HDL clause scoping (verified empirically, see design §4): `bytes[expr]`, `if expr`, `repeat <count>`, `@valid`, `derive`, struct `@size` resolve bare names against the **current struct** (`instance.x`); `switch` conditions, `dispatch … on`, `repeat until`, `@at expr` resolve bare names to `parent.x` (evaluated with parent aliased to the current struct for switch/dispatch). Inside any expression, `parent.<x>` written explicitly means the **enclosing** struct. Backtick expressions pass through verbatim. When in doubt use `derive` fields to name what you need, then reference the derived name as a lone sibling.
- Commit messages: end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Commit only the files each task names (`git add <paths>`), never `git add -A` — both `hexplain.io` and `hexplain-tools` carry the user's uncommitted work.
- Decisions locked by this plan (deviations from the design doc, recorded in Task 12): G3 is implemented as a pointer read at the `iloc` extent with `bddo:seekScope`, not an extent table; `offsetBaseField` and `construction_method` 1/2 are out of scope; G1 lowers by reference (`owl:imports`), no inlining; qualified references to imported structs use CURIE syntax (`iso:Box`, the import alias is a prefix); the box `@size` uses `stream.remaining + 4`; G4/M4 (semantic mapping) is a follow-up plan.

## File map

| Repo | Path | Responsibility |
|---|---|---|
| tools | `hdl/src/test/resources/heif/example.heic`, `example.avif` | libheif sample files (fixtures) |
| tools | `hdl/src/test/resources/profiles/<module>/<module>.hx` | test copies of the profiles (canonical copies live in hexplain-profiles; drift gate in Task 2) |
| tools | `hdl/src/test/kotlin/io/hexplain/hdl/parity/IsobmffParityTest.kt` | M1/M2 behavioural verification against both samples |
| tools | `hdl/src/test/kotlin/io/hexplain/hdl/parity/HeifModulesParityTest.kt` | M3 verification through imports |
| tools | `core/src/main/kotlin/io/hexplain/core/ir/Model.kt` | `DispatchTableIR`, `SeekScope`, new `FieldIR` members |
| tools | `core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt`, `IR.kt` | new constants |
| tools | `core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt` | compile dispatch tables (arms collected across the merged graph) and seek scope |
| tools | `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt`, `Metawriter.kt` | keyed dispatch in type resolution; stream-scoped pointer read |
| tools | `core/src/main/kotlin/io/hexplain/core/semantic/SemanticLifter.kt`, `conformance/ConformanceEngine.kt`, `rdf/FormatIRToRdf.kt` | mirror dispatch in every other consumer of `conditionalDataTypes` |
| tools | `hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt`, `parse/Parser.kt`, `resolve/Resolver.kt`, `emit/TurtleEmitter.kt`, `HdlCompiler.kt`, `cli/Main.kt` | `dispatch`, `extend dispatch`, `@seek`, `module`, `import` |
| tools | `hdl/src/main/kotlin/io/hexplain/hdl/imports/ImportResolver.kt` (new) | locating imported `.hx` sources |
| spec | `specification/bddo/bddo.ttl`, `bddo/test/dispatch-table-{valid,invalid}.ttl`, `bddo/test/seek-scope-{valid,invalid}.ttl` | vocabulary, shapes, fixtures |
| spec | `specification/bddo/index.html`, `specification/processing/index.html`, `specification/hdl/index.html` | prose (generated sections regenerate) |
| spec | `tools/_term_editorial.py` | editorial definitions for the new terms |
| profiles | `profiles/iso-bmff/`, `profiles/heif/`, `profiles/codec-hevc/`, `profiles/codec-av1/`, `profiles/heic/`, `profiles/avif/` | canonical descriptions + compiled Turtle |
| profiles | `tools/test_profile_library.py`, `tools/test_tools_fixtures.py` (new), `README.md` | import-aware validation; fixture drift gate |

---

### Task 0: Branches, stashes and fixtures

**Files:**
- Create: `d:/work/hexplain-tools/hdl/src/test/resources/heif/example.heic`, `example.avif`, `NOTICE.txt`

Both `hexplain.io` and `hexplain-tools` have uncommitted tracked changes (the user's in-progress work: DLV/raster in the spec, `Metaparser.kt`/`Metawriter.kt` hardening in tools). This plan's commits must not absorb them, and Tasks 6–7 edit `Metaparser.kt`. Stashing tracked changes is reversible (`git stash pop`); untracked files are left alone.

- [ ] **Step 1: Stash tracked WIP and branch (spec)**

```bash
cd /d/work/hexplain.io && git stash push -m "WIP before heif-isobmff plan" && git switch -c feature/heif-isobmff && git status --short | grep -v '^??' ; echo "clean tracked tree expected"
```

- [ ] **Step 2: Stash tracked WIP and branch (tools)**

```bash
cd /d/work/hexplain-tools && git stash push -m "hardening WIP before heif-isobmff plan" && git switch -c feature/heif-isobmff && git status --short | grep -v '^??' ; echo "clean tracked tree expected"
```

- [ ] **Step 3: Branch (profiles, already clean)**

```bash
cd /d/work/hexplain-profiles && git switch -c feature/heif-isobmff
```

- [ ] **Step 4: Download the libheif samples into tools test resources**

```bash
mkdir -p /d/work/hexplain-tools/hdl/src/test/resources/heif && cd /d/work/hexplain-tools/hdl/src/test/resources/heif && \
curl -sL -o example.heic https://raw.githubusercontent.com/strukturag/libheif/master/examples/example.heic && \
curl -sL -o example.avif https://raw.githubusercontent.com/strukturag/libheif/master/examples/example.avif && \
python -c "import hashlib;[print(f, hashlib.sha256(open(f,'rb').read()).hexdigest(), __import__('os').path.getsize(f)) for f in ('example.heic','example.avif')]"
```
Expected sizes: `example.heic` 718114 bytes, `example.avif` 113604 bytes. Record the two sha256 values in `NOTICE.txt`:

```
Sample files from https://github.com/strukturag/libheif/tree/master/examples (example.heic, example.avif),
used only as test fixtures for behavioural verification of the ISO BMFF / HEIF / AVIF profiles.
Not redistributed as part of any published artifact.
sha256 example.heic: <value>
sha256 example.avif: <value>
```

- [ ] **Step 5: Verify the build still works on the clean branch**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:compileTestKotlin`
Expected: exit 0.

- [ ] **Step 6: Commit fixtures**

```bash
cd /d/work/hexplain-tools && git add hdl/src/test/resources/heif && git commit -m "test(hdl): add libheif example.heic/example.avif as parity fixtures

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 1: M1 — ISO BMFF box walker profile, parse-verified

**Files:**
- Create: `d:/work/hexplain-tools/hdl/src/test/resources/profiles/isobmff/isobmff.hx`
- Create: `d:/work/hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/IsobmffParityTest.kt`

**Interfaces:**
- Produces: struct IRIs under `https://hexplain.io/ns/profile/isobmff#` — `File` (root), `Box`, `FullBoxHeader`, `FileTypeBox`, `Brand`, `MetaBox`, `ContainerPayload`, `ItemInfoBox`; parsed maps with keys `boxes`, `size`, `type`, `payload`, `children`, `hdr`, `majorBrand`, `compatibleBrands`. Task 9 extends this file in place.

- [ ] **Step 1: Write the failing parity test**

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.ir.FormatIR
import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.ProfileLoader
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * Behavioural verification of the ISO BMFF description against libheif's own sample files.
 * Every expected value below was computed independently with a hand-written Python box walker
 * (see the design document, §8.1): box offsets/sizes, brands, and the meta box's children.
 */
class IsobmffParityTest {
    private fun res(name: String) =
        this::class.java.classLoader.getResourceAsStream(name) ?: error("missing resource $name")

    private fun formatIR(): FormatIR {
        val hx = res("profiles/isobmff/isobmff.hx").readBytes().toString(Charsets.UTF_8)
        val r = HdlCompiler().compile(hx)
        assertTrue(r.ok, "compile diagnostics: ${r.diagnostics}")
        return RdfToIrCompiler(ProfileLoader().loadFromString(r.toTurtle()))
            .compile("https://hexplain.io/ns/profile/isobmff#File")
    }

    private fun parse(file: String): Map<*, *> =
        Metaparser(formatIR(), recordByteRange = true).parse(res(file).readBytes()) as Map<*, *>

    private fun boxes(m: Map<*, *>): List<Map<*, *>> = (m["boxes"] as List<*>).map { it as Map<*, *> }
    private fun children(box: Map<*, *>): List<Map<*, *>> =
        ((box["payload"] as Map<*, *>)["children"] as List<*>).map { it as Map<*, *> }
    private fun child(box: Map<*, *>, type: String): Map<*, *> =
        children(box).first { it["type"] == type }

    @Test fun `heic top-level boxes match the reference walker`() {
        val top = boxes(parse("heif/example.heic"))
        assertEquals(listOf("ftyp", "meta", "mdat", "mdat", "mdat", "mdat", "mdat"), top.map { it["type"] })
        assertEquals(listOf(0, 28, 949, 334661, 359192, 689332, 718098), top.map { it["__byteOffset"] })
        assertEquals(listOf(28, 921, 333712, 24531, 330140, 28766, 16), top.map { it["__byteLength"] })
    }

    @Test fun `heic ftyp brands`() {
        val ftyp = boxes(parse("heif/example.heic"))[0]["payload"] as Map<*, *>
        assertEquals("mif1", ftyp["majorBrand"])
        assertEquals(0L, (ftyp["minorVersion"] as Number).toLong())
        val brands = (ftyp["compatibleBrands"] as List<*>).map { (it as Map<*, *>)["code"] }
        assertEquals(listOf("mif1", "heic", "hevc"), brands)
    }

    @Test fun `heic meta tree`() {
        val meta = boxes(parse("heif/example.heic"))[1]
        assertEquals(listOf("hdlr", "pitm", "iloc", "iinf", "iref", "iprp"), children(meta).map { it["type"] })
        val iprp = child(meta, "iprp")
        assertEquals(listOf("ipco", "ipma"), children(iprp).map { it["type"] })
        assertEquals(listOf("hvcC", "ispe", "hvcC", "ispe", "hvcC", "hvcC"), children(child(iprp, "ipco")).map { it["type"] })
        val iinf = child(meta, "iinf")["payload"] as Map<*, *>
        assertEquals(0L, ((iinf["hdr"] as Map<*, *>)["version"] as Number).toLong())
        assertEquals(4, (iinf["entries"] as List<*>).size)
    }

    @Test fun `avif top-level boxes and property container`() {
        val top = boxes(parse("heif/example.avif"))
        assertEquals(listOf("ftyp", "meta", "mdat"), top.map { it["type"] })
        assertEquals(listOf(24, 248, 113332), top.map { it["__byteLength"] })
        val ftyp = top[0]["payload"] as Map<*, *>
        assertEquals("avif", ftyp["majorBrand"])
        val ipco = child(child(top[1], "iprp"), "ipco")
        assertEquals(listOf("colr", "av1C", "ispe"), children(ipco).map { it["type"] })
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.parity.IsobmffParityTest"`
Expected: FAIL with `missing resource profiles/isobmff/isobmff.hx`.

- [ ] **Step 3: Write the M1 profile**

`hdl/src/test/resources/profiles/isobmff/isobmff.hx`:

```
// Hexplain Profile — ISO base media file format (ISO/IEC 14496-12), box framing and item machinery
//
// The container every HEIF, AVIF, MP4 and JPEG-XL-in-BMFF file shares. A file is a sequence of
// boxes; a box is a 32-bit size, a four-character type, an optional 64-bit largesize (size == 1),
// an optional 16-byte UUID (type == "uuid"), and a payload that runs to the end of the box.
// size == 0 means "to the end of the enclosing container".
//
// The struct-level @size below is re-evaluated after each field until it can be computed. It
// resolves right after `size` is read, when only those four bytes have been consumed, which is
// why the size == 0 arm is `stream.remaining + 4`: remaining is measured from the cursor, the
// region from the struct start. (Processing Model §3.1: a descendant's eof() is the region end.)
//
// Source: ISO/IEC 14496-12:2022, clauses 4.2 (Box), 4.3 (ftyp), 8.11 (meta and item boxes).
// Verification status: parse-verified against libheif examples/example.heic and example.avif
// (hexplain-tools IsobmffParityTest).

format isobmff @namespace "https://hexplain.io/ns/profile/isobmff#" @endian big

@root struct File
  @label "ISO base media file"
  @comment "A sequence of boxes to the end of the stream."
{
  boxes : Box repeat until eof()
}

struct Box
  @label "Box"
  @size `instance.size == 1 ? instance.largesize : (instance.size == 0 ? stream.remaining + 4 : instance.size)`
{
  size      : u32 @label "size" @comment "Total box size including this header; 1 = largesize follows; 0 = to the end of the enclosing container."
  type      : ascii[4] @label "type"
  largesize : u64 if size == 1 @label "largesize"
  usertype  : bytes[16] if type == "uuid" @label "extended type (UUID)"
  payload   : bytes[..] switch type {
    "ftyp" => FileTypeBox
    "meta" => MetaBox
    "iinf" => ItemInfoBox
    "iprp" => ContainerPayload
    "ipco" => ContainerPayload
    "dinf" => ContainerPayload
    "grpl" => ContainerPayload
    "moov" => ContainerPayload
    "trak" => ContainerPayload
    "mdia" => ContainerPayload
    "minf" => ContainerPayload
    "stbl" => ContainerPayload
    "edts" => ContainerPayload
    "udta" => ContainerPayload
  }
}

struct FullBoxHeader
  @label "FullBox header"
  @comment "Version byte and 24 flag bits that prefix a FullBox payload."
{
  version : u8
  flags   : bits[24]
}

struct ContainerPayload
  @label "container box payload"
{
  children : Box repeat until eof()
}

struct FileTypeBox
  @label "ftyp — file type and compatibility"
{
  majorBrand       : ascii[4]
  minorVersion     : u32
  compatibleBrands : Brand repeat until eof()
}

struct Brand { code : ascii[4] }

struct MetaBox
  @label "meta — metadata container"
  @comment "A FullBox whose payload is a sequence of child boxes (hdlr, pitm, iloc, iinf, iref, iprp, idat, dinf, grpl)."
{
  hdr      : FullBoxHeader
  children : Box repeat until eof()
}

struct ItemInfoBox
  @label "iinf — item information"
{
  hdr          : FullBoxHeader
  entryCount16 : u16 if hdr.version == 0
  entryCount32 : u32 if hdr.version != 0
  entryCount   : derive [ hdr.version == 0 ? entryCount16 : entryCount32 ]
  entries      : Box repeat until eof()
}

// ---------- LIMITS OF THIS DESCRIPTION (M1) ----------
// 1. Only container framing is described. hdlr, pitm, iloc, infe, iref, ipma, dref and every
//    item property are opaque bytes until milestone M2 replaces this switch with an open
//    dispatch table and adds the item machinery.
// 2. Track boxes (moov/trak/…) are walked as containers; their leaf boxes are opaque.
// 3. A uuid box's extended type is read; its payload is never dispatched on it.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.parity.IsobmffParityTest"`
Expected: PASS (4 tests). If `heic meta tree` fails on `entries` count, check that `iinf`'s `entryCount16` was read before the children (the `derive` must precede `entries`).

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools && git add hdl/src/test/resources/profiles/isobmff/isobmff.hx hdl/src/test/kotlin/io/hexplain/hdl/parity/IsobmffParityTest.kt && git commit -m "feat(profiles): ISO BMFF box walker, parse-verified against libheif samples

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Profile library entry and the fixture drift gate

**Files:**
- Create: `d:/work/hexplain-profiles/profiles/isobmff/isobmff.hx` (copy of Task 1's file), `profiles/isobmff/isobmff.ttl` (compiled)
- Create: `d:/work/hexplain-profiles/tools/test_tools_fixtures.py`

**Interfaces:**
- Produces: the convention that `hexplain-tools/hdl/src/test/resources/profiles/<p>/<p>.hx` is a byte-identical copy of `hexplain-profiles/profiles/<p>/<p>.hx`, enforced by the gate. Tasks 9 and 11 rely on it.

- [ ] **Step 1: Write the drift gate**

`tools/test_tools_fixtures.py`:

```python
"""A profile that hexplain-tools verifies behaviourally is copied into that repo as a test
fixture. Copies drift, and a fixture that drifts silently passes against a description the
library no longer ships. This gate compares each pair byte for byte.

Skip discipline mirrors test_profile_library: a MISSING tools checkout skips with a message;
a present checkout with a differing copy FAILS.
"""

import glob
import os
import pathlib
import sys


def main():
    tools = pathlib.Path(os.environ.get("HEXPLAIN_TOOLS", "../hexplain-tools"))
    fixtures = tools / "hdl/src/test/resources/profiles"
    if not tools.is_dir():
        print(f"SKIP: hexplain-tools checkout not found at {tools} (set HEXPLAIN_TOOLS to override)")
        return 0
    if not fixtures.is_dir():
        print(f"SKIP: {fixtures} does not exist -- no verified fixtures yet")
        return 0
    failures, compared = [], 0
    for copy in sorted(glob.glob(str(fixtures / "*/*.hx"))):
        rel = pathlib.Path(copy).relative_to(fixtures)
        canonical = pathlib.Path("profiles") / rel
        if not canonical.is_file():
            failures.append(f"{copy}: no canonical profile at {canonical}")
            continue
        a = canonical.read_text(encoding="utf-8").replace("\r\n", "\n")
        b = pathlib.Path(copy).read_text(encoding="utf-8").replace("\r\n", "\n")
        compared += 1
        if a != b:
            failures.append(f"{canonical} and {copy} differ; copy the canonical file over the fixture")
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        return 1
    print(f"PASS: {compared} verified fixture(s) match their canonical profile")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it to verify it fails (no canonical profile yet)**

Run: `cd /d/work/hexplain-profiles && python tools/test_tools_fixtures.py`
Expected: `FAIL:` naming `profiles/isobmff/isobmff.hx` as missing.

- [ ] **Step 3: Add the canonical profile and compile it**

```bash
mkdir -p /d/work/hexplain-profiles/profiles/isobmff && cp /d/work/hexplain-tools/hdl/src/test/resources/profiles/isobmff/isobmff.hx /d/work/hexplain-profiles/profiles/isobmff/isobmff.hx && \
cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:run --args="/d/work/hexplain-profiles/profiles/isobmff/isobmff.hx -o /d/work/hexplain-profiles/profiles/isobmff/isobmff.ttl" && head -5 /d/work/hexplain-profiles/profiles/isobmff/isobmff.ttl
```

- [ ] **Step 4: Run all library gates**

Run: `cd /d/work/hexplain-profiles && python tools/run_gates.py`
Expected: `PASS test_profile_library` (now 7 profiles), `PASS test_tools_fixtures` (1 fixture), `PASS test_hx_roundtrip`.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-profiles && git add profiles/isobmff tools/test_tools_fixtures.py && git commit -m "feat: ISO BMFF box-walker profile; gate that tools fixtures match canonical profiles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: BDDO vocabulary — keyed dispatch tables and seek scope (spec repo)

**Files:**
- Modify: `d:/work/hexplain.io/specification/bddo/bddo.ttl` (classes after line 38 `:EndiannessRule`; properties after line 97 `:hasConditionalDataType`; individuals after line 240 `:currentPosition`; shapes after `bddo:DataTypeRuleShape`, ~line 462; the `bddo:FieldShape` block ~line 344)
- Create: `specification/bddo/test/dispatch-table-valid.ttl`, `dispatch-table-invalid.ttl`, `seek-scope-valid.ttl`, `seek-scope-invalid.ttl`
- Modify: `tools/_term_editorial.py` (the `group('bddo', ...)` block)
- Modify: `specification/bddo/index.html` (prose in the "Field Properties" `<dl>`, ~line 283) and `specification/processing/index.html` (ParseField list, lines 75 and 78)

**Interfaces:**
- Produces the IRIs every later task uses: `bddo:DispatchTable`, `bddo:DispatchArm`, `bddo:SeekScope` (classes); `bddo:hasDispatchTable`, `bddo:dispatchOnField`, `bddo:dispatchOnExpression`, `bddo:dispatchDefault`, `bddo:armTable`, `bddo:armKey`, `bddo:armDataType`, `bddo:seekScope` (properties); `bddo:regionScope`, `bddo:streamScope` (individuals); shapes `bddo:DispatchTableShape`, `bddo:DispatchArmShape`, `bddo:DispatchKeyUniquenessShape`, `bddo:TypeSelectionExclusivityShape`, `bddo:SeekScopeShape`.

- [ ] **Step 1: Write the positive and negative fixtures**

`specification/bddo/test/dispatch-table-valid.ttl`:
```turtle
# A keyed dispatch table declared on one field, with one arm contributed "from outside" (a
# separate subject, not a list member), an integer-keyed arm, and a default. Must conform.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/dispatch-valid#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:Record a bddo:Struct ; bddo:endianness bddo:BigEndian ;
    bddo:hasField ( ex:Record.tag ex:Record.body ) .
ex:Record.tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
ex:Record.body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ;
    bddo:hasDispatchTable ex:BodyDispatch .

ex:BodyDispatch a bddo:DispatchTable ;
    bddo:dispatchOnField ex:Record.tag ;
    bddo:dispatchDefault ex:Unknown .

ex:Unknown a bddo:Struct ; bddo:hasField ( ex:Unknown.raw ) .
ex:Unknown.raw a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
ex:Header a bddo:Struct ; bddo:hasField ( ex:Header.v ) .
ex:Header.v a bddo:Field ; bddo:dataType bddo:uint32 .

[] a bddo:DispatchArm ; bddo:armTable ex:BodyDispatch ; bddo:armKey "hdr " ; bddo:armDataType ex:Header .
[] a bddo:DispatchArm ; bddo:armTable ex:BodyDispatch ; bddo:armKey 7 ; bddo:armDataType bddo:uint32 .
```

`specification/bddo/test/dispatch-table-invalid.ttl`:
```turtle
# Three violations: two arms share a key; a field declares both selection mechanisms; a table
# names neither a key field nor a key expression.
# Expected to trip bddo:DispatchKeyUniquenessShape, bddo:TypeSelectionExclusivityShape and
# bddo:DispatchTableShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/dispatch-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Record a bddo:Struct ;
    rdfs:comment "Expected to trip bddo:DispatchKeyUniquenessShape, bddo:TypeSelectionExclusivityShape and bddo:DispatchTableShape." ;
    bddo:hasField ( ex:Record.tag ex:Record.body ) .
ex:Record.tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 .
ex:Record.body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ;
    bddo:hasDispatchTable ex:BodyDispatch ;
    bddo:hasConditionalDataType ( [ a bddo:DataTypeRule ; bddo:condition "parent.tag == 'x'" ; bddo:ruleDataType bddo:uint8 ] ) .

ex:BodyDispatch a bddo:DispatchTable .

[] a bddo:DispatchArm ; bddo:armTable ex:BodyDispatch ; bddo:armKey "dup" ; bddo:armDataType bddo:uint8 .
[] a bddo:DispatchArm ; bddo:armTable ex:BodyDispatch ; bddo:armKey "dup" ; bddo:armDataType bddo:uint16 .
```

`specification/bddo/test/seek-scope-valid.ttl`:
```turtle
# A pointer read allowed to leave its bounded region. Must conform.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/seek-valid#> .

ex:Extent a bddo:Struct ; bddo:hasField ( ex:Extent.offset ex:Extent.length ex:Extent.data ) .
ex:Extent.offset a bddo:Field ; bddo:dataType bddo:uint32 .
ex:Extent.length a bddo:Field ; bddo:dataType bddo:uint32 .
ex:Extent.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:Extent.length ;
    bddo:atOffsetFromField ex:Extent.offset ; bddo:offsetBase bddo:streamStart ;
    bddo:seekScope bddo:streamScope .
```

`specification/bddo/test/seek-scope-invalid.ttl`:
```turtle
# seekScope on a field that is not offset-addressed, and a value outside the controlled set.
# Expected to trip bddo:SeekScopeShape and bddo:FieldShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/seek-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Bad a bddo:Struct ;
    rdfs:comment "Expected to trip bddo:SeekScopeShape and bddo:FieldShape." ;
    bddo:hasField ( ex:Bad.sequential ex:Bad.wrongValue ) .
ex:Bad.sequential a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:seekScope bddo:streamScope .
ex:Bad.wrongValue a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 4 ; bddo:seekScope ex:elsewhere .
```

- [ ] **Step 2: Run the fixture gate to verify the new fixtures fail**

Run: `cd /d/work/hexplain.io && python tools/test_vocab_shapes.py`
Expected: FAIL — the two `-invalid` fixtures conform (no shapes exist yet) and are reported.

- [ ] **Step 3: Add the vocabulary to `bddo.ttl`**

Classes (after `:EndiannessRule`):
```turtle
:DispatchTable a owl:Class ; rdfs:label "Dispatch Table" ; rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "A keyed, open selection of a Field's effective type. The value of the key (dispatchOnField or dispatchOnExpression) is matched by equality against the armKey of the table's DispatchArms; the matching arm's armDataType is the effective type, else dispatchDefault, else the Field's dataType. Arms are independent resources rather than list members, so a description that imports this one can contribute an arm without rewriting anything. Contrast hasConditionalDataType, whose ordered predicate rules are closed and may overlap." .
:DispatchArm a owl:Class ; rdfs:label "Dispatch Arm" ; rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "One key-to-type association of a DispatchTable: the type a field takes when the table's key equals armKey. Keys are unique within a table across every graph that contributes to it." .
:SeekScope a owl:Class ; rdfs:label "Seek Scope" ; rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "How far an offset-addressed read may reach: the innermost bounded region (the default, regionScope) or the whole stream (streamScope)." .
```

Properties (after `:hasConditionalDataType`):
```turtle
:hasDispatchTable       a owl:ObjectProperty ; rdfs:label "has dispatch table" ; rdfs:range :DispatchTable ;
    rdfs:comment "The keyed DispatchTable that selects this Field's effective type. Mutually exclusive with hasConditionalDataType." .
:dispatchOnField        a owl:ObjectProperty ; rdfs:label "dispatch on field" ; rdfs:range :Field ;
    rdfs:comment "The sibling Field whose parsed value is the dispatch key." .
:dispatchOnExpression   a owl:DatatypeProperty ; rdfs:label "dispatch on expression" ; rdfs:range xsd:string ;
    rdfs:comment "A HEL expression whose value is the dispatch key, evaluated as a hasConditionalDataType condition is." .
:dispatchDefault        a owl:ObjectProperty ; rdfs:label "dispatch default" ; rdfs:range :DataTypeOrStruct ;
    rdfs:comment "The type selected when no arm's key equals the dispatch key. Absent means the Field's own dataType applies." .
:armTable               a owl:ObjectProperty ; rdfs:label "arm table" ; rdfs:range :DispatchTable ;
    rdfs:comment "The DispatchTable this DispatchArm contributes to. Declared on the arm so that any graph may add arms to a table defined elsewhere." .
:armKey                 a owl:DatatypeProperty ; rdfs:label "arm key" ;
    rdfs:comment "The key value this arm matches: an xsd:string compared by code points, or an xsd:integer compared numerically." .
:armDataType            a owl:ObjectProperty ; rdfs:label "arm data type" ; rdfs:range :DataTypeOrStruct ;
    rdfs:comment "The datatype or structure selected when this arm's key matches." .
:seekScope              a owl:ObjectProperty ; rdfs:label "seek scope" ; rdfs:range :SeekScope ;
    rdfs:comment "For an offset-addressed Field, whether the read may leave the innermost bounded region (streamScope) or is confined to it (regionScope, the default). The region bound is suspended only for that one read. Used where a table inside one length-delimited container locates payloads stored in another." .
```

Individuals (after `:currentPosition`):
```turtle
:regionScope a owl:NamedIndividual, :SeekScope ; rdfs:label "Seek scope: bounded region" ;
    rdfs:comment "The default: an offset-addressed read must stay within the innermost enclosing bounded region." .
:streamScope a owl:NamedIndividual, :SeekScope ; rdfs:label "Seek scope: whole stream" ;
    rdfs:comment "The read is resolved against the whole stream; the enclosing region bound does not apply to it." .
```

Shapes. In `bddo:FieldShape` add, after the `hasConditionalDataType` list-member property:
```turtle
    sh:property [ sh:path bddo:hasDispatchTable ; sh:maxCount 1 ; sh:class bddo:DispatchTable ] ;
    sh:property [ sh:path bddo:seekScope ; sh:maxCount 1 ; sh:in ( bddo:regionScope bddo:streamScope ) ] ;
```
and extend the `sh:or` at the top of `bddo:FieldShape` with a fourth alternative `[ sh:property [ sh:path bddo:hasDispatchTable ; sh:minCount 1 ] ]`.

After `bddo:DataTypeRuleShape`:
```turtle
bddo:DispatchTableShape a sh:NodeShape ;
    sh:targetClass bddo:DispatchTable ;
    sh:xone (
        [ sh:property [ sh:path bddo:dispatchOnField ; sh:minCount 1 ] ]
        [ sh:property [ sh:path bddo:dispatchOnExpression ; sh:minCount 1 ] ]
    ) ;
    sh:property [ sh:path bddo:dispatchOnField ; sh:maxCount 1 ; sh:class bddo:Field ] ;
    sh:property [ sh:path bddo:dispatchOnExpression ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
    sh:property [ sh:path bddo:dispatchDefault ; sh:maxCount 1 ; sh:nodeKind sh:IRI ;
        sh:or ( [ sh:class bddo:DataType ] [ sh:class bddo:Struct ] ) ] .

bddo:DispatchArmShape a sh:NodeShape ;
    sh:targetClass bddo:DispatchArm ;
    sh:property [ sh:path bddo:armTable ; sh:minCount 1 ; sh:maxCount 1 ; sh:class bddo:DispatchTable ] ;
    sh:property [ sh:path bddo:armKey ; sh:minCount 1 ; sh:maxCount 1 ;
        sh:or ( [ sh:datatype xsd:string ] [ sh:datatype xsd:integer ] ) ] ;
    sh:property [ sh:path bddo:armDataType ; sh:minCount 1 ; sh:maxCount 1 ; sh:nodeKind sh:IRI ;
        sh:or ( [ sh:class bddo:DataType ] [ sh:class bddo:Struct ] ) ] .

# Keys are unique per table across every contributing graph: two arms with one key would make
# the selection depend on graph order, which is exactly what a keyed table exists to rule out.
bddo:DispatchKeyUniquenessShape a sh:NodeShape ;
    sh:targetClass bddo:DispatchTable ;
    sh:sparql [ sh:message "Two DispatchArms of one DispatchTable declare the same armKey." ;
        sh:prefixes bddo:_prefixes ;
        sh:select """SELECT $this ?key WHERE {
            ?a bddo:armTable $this ; bddo:armKey ?key .
            ?b bddo:armTable $this ; bddo:armKey ?key .
            FILTER(?a != ?b)
        }""" ] .

# A field selects its type one way: keyed (open, disjoint) or ordered predicates (closed).
bddo:TypeSelectionExclusivityShape a sh:NodeShape ;
    sh:targetClass bddo:Field ;
    sh:sparql [ sh:message "A bddo:Field must not declare both hasDispatchTable and hasConditionalDataType." ;
        sh:prefixes bddo:_prefixes ;
        sh:select """SELECT $this WHERE {
            $this bddo:hasDispatchTable ?t ; bddo:hasConditionalDataType ?c .
        }""" ] .

# seekScope describes an offset-addressed read; on a sequential field it describes nothing.
bddo:SeekScopeShape a sh:NodeShape ;
    sh:targetClass bddo:Field ;
    sh:sparql [ sh:message "bddo:seekScope is only meaningful on an offset-addressed Field (atOffset / atOffsetFromField / atOffsetFromExpression)." ;
        sh:prefixes bddo:_prefixes ;
        sh:select """SELECT $this WHERE {
            $this bddo:seekScope ?s .
            FILTER NOT EXISTS { $this ?p ?v . FILTER(?p IN (bddo:atOffset, bddo:atOffsetFromField, bddo:atOffsetFromExpression)) }
        }""" ] .
```

- [ ] **Step 4: Add editorial definitions**

In `tools/_term_editorial.py`, inside the `group('bddo', ''' ... ''')` block, add lines:
```
DispatchTable|A keyed, open selection of a field's effective type: the dispatch key is matched by equality against the keys of arms that any importing description may contribute.
DispatchArm|One key-to-type association contributed to a dispatch table; keys are unique within a table across all contributing graphs.
SeekScope|The reach of an offset-addressed read: the innermost bounded region, or the whole stream.
hasDispatchTable|The keyed dispatch table that selects this field's effective type; exclusive with the ordered conditional datatype rules.
dispatchOnField|The sibling field whose parsed value is the dispatch key.
dispatchOnExpression|A HEL expression whose value is the dispatch key.
dispatchDefault|The type selected when no arm matches the dispatch key.
armTable|The dispatch table an arm contributes to.
armKey|The string or integer key value an arm matches by equality.
armDataType|The datatype or structure selected when an arm's key matches.
seekScope|Whether an offset-addressed read is confined to its bounded region or resolved against the whole stream.
regionScope|Seek scope confining an offset-addressed read to the innermost bounded region; the default.
streamScope|Seek scope resolving an offset-addressed read against the whole stream, suspending the region bound for that read.
```

- [ ] **Step 5: Regenerate the documentation and run the fixture gate**

Run: `cd /d/work/hexplain.io && python tools/_term_editorial.py >/dev/null; python tools/_build_term_reference.py --enrich && python tools/test_vocab_shapes.py`
Expected: the `--enrich` run appends `skos:definition`/`skos:scopeNote` triples for the 13 new terms after the `# Editorial annotations only` marker in `bddo.ttl` and regenerates `specification/bddo/index.html`'s generated sections; `test_vocab_shapes` prints `PASS: 41 vocabulary fixtures behave as expected`.

- [ ] **Step 6: Document the terms in prose**

In `specification/bddo/index.html`, in the Field Properties `<dl>` right after the `bddo:hasConditionalDataType` `<dd>` (~line 286), add:
```html
                <dt><code>bddo:hasDispatchTable</code></dt>
                <dd>A <code>bddo:DispatchTable</code> selecting the Field's type by <b>key</b>: the parsed value of <code>bddo:dispatchOnField</code> (or the value of <code>bddo:dispatchOnExpression</code>) is compared by equality with the <code>bddo:armKey</code> of every <code>bddo:DispatchArm</code> whose <code>bddo:armTable</code> is this table; the matching arm's <code>bddo:armDataType</code> is the effective type, else <code>bddo:dispatchDefault</code>, else the Field's <code>bddo:dataType</code>. Arms are independent subjects, not list members, so a description that <code>owl:imports</code> another may add arms to its tables — the mechanism for open type registries (container box types, tagged extensions). Keys MUST be unique per table across all contributing graphs. Mutually exclusive with <code>bddo:hasConditionalDataType</code>, which remains the form for ordered, possibly overlapping predicate rules.</dd>
                <dt><code>bddo:seekScope</code></dt>
                <dd>On an offset-addressed Field: <code>bddo:regionScope</code> (default) confines the read to the innermost bounded region; <code>bddo:streamScope</code> resolves the target against the whole stream and suspends the region bound for that one read. Needed when a table inside one length-delimited container locates payloads stored in another.</dd>
```

In `specification/processing/index.html`, replace the Addressing item (line 75) with:
```html
                <li><b>Addressing.</b> If an offset property is present, compute the target offset from <code>bddo:atOffset</code> / <code>atOffsetFromField</code> / <code>atOffsetFromExpression</code>, relative to <code>bddo:offsetBase</code> (default <code>streamStart</code>; <code>streamEnd</code> counts backward from <code>|S|</code>). Save the current cursor, seek to the target, parse, then restore the saved cursor (an offset field does not advance sibling parsing) unless <code>offsetBase</code> is <code>currentPosition</code>. A target outside the innermost bounded region raises a <i>bounds error</i>, unless the field declares <code>bddo:seekScope bddo:streamScope</code>: then the target is resolved against the whole stream <code>[0, |S|)</code> and the region bound is suspended for the duration of this one read (and restored before the cursor is).</li>
```
and replace the Type selection item (line 78) with:
```html
                <li><b>Type selection.</b> If <code>bddo:hasDispatchTable</code> is present, evaluate the table's key — the parsed value of <code>bddo:dispatchOnField</code>, or <code>bddo:dispatchOnExpression</code> evaluated exactly as a <code>bddo:DataTypeRule</code> condition is — and select the <code>bddo:DispatchArm</code> of that table whose <code>bddo:armKey</code> equals it (strings by code points, integers numerically); if none matches, use <code>bddo:dispatchDefault</code>, else <code>bddo:dataType</code>. A processor MUST collect arms from the whole description graph, including imported ontologies; two arms with one key are a description error. Otherwise, if <code>bddo:hasConditionalDataType</code> is present, evaluate each <code>bddo:DataTypeRule</code> in list order; the first whose <code>bddo:condition</code> is <code>true</code> supplies the effective type via <code>bddo:ruleDataType</code>. Otherwise use <code>bddo:dataType</code>. It is an error if none yields a type, or if both selection mechanisms are declared.</li>
```

- [ ] **Step 7: Run every spec gate**

Run: `cd /d/work/hexplain.io && python tools/run_gates.py`
Expected: `27/27 gates passed`. If `test_term_reference` reports stale content, rerun `python tools/_build_term_reference.py` (no flags) and retry. If `test_vocab_neutrality` fails, a term name contains a format word — rename it.

- [ ] **Step 8: Commit**

```bash
cd /d/work/hexplain.io && git add specification/bddo/bddo.ttl specification/bddo/index.html specification/bddo/test/dispatch-table-valid.ttl specification/bddo/test/dispatch-table-invalid.ttl specification/bddo/test/seek-scope-valid.ttl specification/bddo/test/seek-scope-invalid.ttl specification/processing/index.html specification/reference/manifest.json specification/reference/index.html tools/_term_editorial.py && git commit -m "spec(bddo): keyed open dispatch tables and seek scope for offset reads

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
(If `git status` shows other regenerated `index.html` files changed by `_build_term_reference.py`, inspect the diff; only add them if the change is the navigation/term-count line, which is expected.)

---

### Task 4: Sync the bundle and add the Kotlin vocabulary constants

**Files:**
- Modify: `d:/work/hexplain-tools/core/src/main/resources/bddo.ttl` (via `sync_spec.py`)
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt`
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/vocab/IR.kt`
- Test: `d:/work/hexplain-tools/core/src/test/kotlin/io/hexplain/core/rdf/vocab/DispatchVocabTest.kt`

**Interfaces:**
- Produces: `BDDO.DispatchTable`, `BDDO.DispatchArm`, `BDDO.SeekScope`, `BDDO.hasDispatchTable`, `BDDO.dispatchOnField`, `BDDO.dispatchOnExpression`, `BDDO.dispatchDefault`, `BDDO.armTable`, `BDDO.armKey`, `BDDO.armDataType`, `BDDO.seekScope`, `BDDO.regionScope`, `BDDO.streamScope`; `IR.DispatchTable`, `IR.DispatchArm`, `IR.hasDispatchTable`, `IR.dispatchOnField`, `IR.dispatchOnExpression`, `IR.dispatchDefault`, `IR.armKey`, `IR.armDataType`, `IR.seekScope`.

- [ ] **Step 1: Write the failing constants test**

`core/src/test/kotlin/io/hexplain/core/rdf/vocab/DispatchVocabTest.kt`:
```kotlin
package io.hexplain.core.rdf.vocab

import org.apache.jena.rdf.model.ModelFactory
import org.apache.jena.riot.Lang
import org.apache.jena.riot.RDFDataMgr
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/** Locks the keyed-dispatch and seek-scope constants to the bundled bddo.ttl. */
class DispatchVocabTest {
    private val bddo = "https://hexplain.io/ns/bddo#"

    @Test fun `constants match the normative IRIs`() {
        assertEquals(bddo + "DispatchTable", BDDO.DispatchTable.uri)
        assertEquals(bddo + "DispatchArm", BDDO.DispatchArm.uri)
        assertEquals(bddo + "SeekScope", BDDO.SeekScope.uri)
        assertEquals(bddo + "hasDispatchTable", BDDO.hasDispatchTable.uri)
        assertEquals(bddo + "dispatchOnField", BDDO.dispatchOnField.uri)
        assertEquals(bddo + "dispatchOnExpression", BDDO.dispatchOnExpression.uri)
        assertEquals(bddo + "dispatchDefault", BDDO.dispatchDefault.uri)
        assertEquals(bddo + "armTable", BDDO.armTable.uri)
        assertEquals(bddo + "armKey", BDDO.armKey.uri)
        assertEquals(bddo + "armDataType", BDDO.armDataType.uri)
        assertEquals(bddo + "seekScope", BDDO.seekScope.uri)
        assertEquals(bddo + "regionScope", BDDO.regionScope.uri)
        assertEquals(bddo + "streamScope", BDDO.streamScope.uri)
    }

    @Test fun `the bundled bddo ttl declares every constant`() {
        val m = ModelFactory.createDefaultModel()
        javaClass.classLoader.getResourceAsStream("bddo.ttl")!!.use { RDFDataMgr.read(m, it, Lang.TTL) }
        for (r in listOf(BDDO.DispatchTable, BDDO.DispatchArm, BDDO.SeekScope, BDDO.regionScope, BDDO.streamScope)) {
            assertTrue(m.contains(r, RDF.type), "bundled bddo.ttl lacks $r — run python tools/sync_spec.py")
        }
        for (p in listOf(BDDO.hasDispatchTable, BDDO.dispatchOnField, BDDO.dispatchOnExpression, BDDO.dispatchDefault,
                BDDO.armTable, BDDO.armKey, BDDO.armDataType, BDDO.seekScope)) {
            assertTrue(m.contains(p, RDF.type), "bundled bddo.ttl lacks $p — run python tools/sync_spec.py")
        }
    }
}
```

- [ ] **Step 2: Run it to verify it fails to compile**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.rdf.vocab.DispatchVocabTest"`
Expected: compilation error `Unresolved reference: DispatchTable`.

- [ ] **Step 3: Sync the bundle and add the constants**

Run: `cd /d/work/hexplain-tools && python tools/sync_spec.py` — expected output lists `core/src/main/resources/bddo.ttl (stale)` and possibly other stale files from the spec's HEAD; all are written.

In `BDDO.kt`, after the `// --- Conditional endianness ---` block:
```kotlin
    // --- Keyed dispatch tables (open type selection; arms may come from an importing graph) ---
    val DispatchTable: Resource = m_resource("DispatchTable")
    val DispatchArm: Resource = m_resource("DispatchArm")
    val hasDispatchTable: Property = m_property("hasDispatchTable")
    val dispatchOnField: Property = m_property("dispatchOnField")
    val dispatchOnExpression: Property = m_property("dispatchOnExpression")
    val dispatchDefault: Property = m_property("dispatchDefault")
    val armTable: Property = m_property("armTable")
    val armKey: Property = m_property("armKey")
    val armDataType: Property = m_property("armDataType")

    // --- Seek scope of an offset-addressed read ---
    val SeekScope: Resource = m_resource("SeekScope")
    val seekScope: Property = m_property("seekScope")
    val regionScope: Resource = m_resource("regionScope")
    val streamScope: Resource = m_resource("streamScope")
```

In `IR.kt`, after `val hasDataLayout`:
```kotlin
    val hasDispatchTable: Property = m_property("hasDispatchTable")
    val dispatchOnField: Property = m_property("dispatchOnField")
    val dispatchOnExpression: Property = m_property("dispatchOnExpression")
    val dispatchDefault: Property = m_property("dispatchDefault")
    val armKey: Property = m_property("armKey")
    val armDataType: Property = m_property("armDataType")
    val seekScope: Property = m_property("seekScope")
```
and in the classes block: `val DispatchTable: Resource = m_resource("DispatchTable")`, `val DispatchArm: Resource = m_resource("DispatchArm")`.

- [ ] **Step 4: Run the test and the sync/alignment tests**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.rdf.vocab.*" --tests "io.hexplain.core.rdf.SpecSyncTest" --tests "io.hexplain.core.rdf.BundledShapesTest"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools && git add core/src/main/resources core/src/main/kotlin/io/hexplain/core/rdf/vocab/BDDO.kt core/src/main/kotlin/io/hexplain/core/rdf/vocab/IR.kt core/src/test/kotlin/io/hexplain/core/rdf/vocab/DispatchVocabTest.kt && git commit -m "feat(core): BDDO dispatch-table and seek-scope vocabulary; sync bundled ontologies

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
(`git add core/src/main/resources` may pick up other files `sync_spec.py` refreshed from the spec's HEAD — that is correct: the bundle must match the spec.)

---

### Task 5: IR and RDF→IR compilation of dispatch tables and seek scope

**Files:**
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/ir/Model.kt`
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt` (`compileField`, ~line 253–300 and the `return FieldIR(...)` block ~line 415)
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/rdf/FormatIRToRdf.kt` (after the `conditionalDataTypes` block, ~line 114)
- Test: `d:/work/hexplain-tools/core/src/test/kotlin/io/hexplain/core/rdf/DispatchTableCompilationTest.kt`

**Interfaces:**
- Produces:
```kotlin
enum class SeekScope { REGION, STREAM }
data class DispatchTableIR(val name: String, val keyField: String? = null, val keyExpression: HELExpression? = null,
                           val arms: Map<Any, DataTypeIR>, val default: DataTypeIR? = null) {
    fun select(key: Any?): DataTypeIR?   // arm for the normalised key, else default, else null
}
// FieldIR gains: val dispatchTable: DispatchTableIR? = null, val seekScope: SeekScope = SeekScope.REGION
```
Keys are normalised: any `Number` → `Long`; `String` unchanged; anything else matches no arm.

- [ ] **Step 1: Write the failing compilation test**

```kotlin
package io.hexplain.core.rdf

import io.hexplain.core.ir.SeekScope
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test

class DispatchTableCompilationTest {
    private val ns = "https://ex.org/d#"
    private val base = """
        @prefix bddo: <https://hexplain.io/ns/bddo#> .
        @prefix ex: <$ns> .
        ex:Record a bddo:Struct ; bddo:hasField ( ex:Record.tag ex:Record.body ex:Record.ptr ) .
        ex:Record.tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 .
        ex:Record.body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; bddo:hasDispatchTable ex:BodyDispatch .
        ex:Record.ptr a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 0 ; bddo:seekScope bddo:streamScope .
        ex:BodyDispatch a bddo:DispatchTable ; bddo:dispatchOnField ex:Record.tag ; bddo:dispatchDefault ex:Unknown .
        ex:Unknown a bddo:Struct ; bddo:hasField ( ex:Unknown.raw ) .
        ex:Unknown.raw a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true .
        ex:Header a bddo:Struct ; bddo:hasField ( ex:Header.v ) .
        ex:Header.v a bddo:Field ; bddo:dataType bddo:uint32 .
        [] a bddo:DispatchArm ; bddo:armTable ex:BodyDispatch ; bddo:armKey "hdr " ; bddo:armDataType ex:Header .
    """.trimIndent()

    /** An arm contributed by a SECOND graph, as an importing module would. */
    private val extension = """
        @prefix bddo: <https://hexplain.io/ns/bddo#> .
        @prefix ex: <$ns> .
        [] a bddo:DispatchArm ; bddo:armTable ex:BodyDispatch ; bddo:armKey 7 ; bddo:armDataType bddo:uint16 .
    """.trimIndent()

    private fun compile(vararg turtles: String) = ProfileLoader().loadFromString(turtles[0]).also { m ->
        turtles.drop(1).forEach { m.add(ProfileLoader().loadFromString(it)) }
    }.let { RdfToIrCompiler(it).compile(ns + "Record") }

    @Test fun `arms are collected across the merged graph and keys normalised`() {
        val body = compile(base, extension).structs[ns + "Record"]!!.fields.first { it.name == "body" }
        val table = assertNotNull(body.dispatchTable)
        assertEquals("tag", table.keyField)
        assertEquals(ns + "Header", table.select("hdr ")!!.name)
        assertEquals("https://hexplain.io/ns/bddo#uint16", table.select(7)!!.name)        // Int key → Long
        assertEquals("https://hexplain.io/ns/bddo#uint16", table.select(7L)!!.name)
        assertEquals(ns + "Unknown", table.select("zzzz")!!.name)                          // default
        assertEquals(ns + "Unknown", table.select(null)!!.name)                            // an absent key also takes the default
        assertNull(table.copy(default = null).select("zzzz"))
    }

    @Test fun `seek scope is compiled`() {
        val fields = compile(base).structs[ns + "Record"]!!.fields
        assertEquals(SeekScope.STREAM, fields.first { it.name == "ptr" }.seekScope)
        assertEquals(SeekScope.REGION, fields.first { it.name == "tag" }.seekScope)
    }

    @Test fun `duplicate keys are refused at compile time`() {
        val dup = extension.replace("bddo:armKey 7", "bddo:armKey \"hdr \"")
        assertThrows(HexplainProfileLoadException::class.java) { compile(base, dup) }
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.rdf.DispatchTableCompilationTest"`
Expected: compilation error (`dispatchTable`, `SeekScope` unresolved).

- [ ] **Step 3: Extend the IR**

In `Model.kt`, after `enum class BitOrder`:
```kotlin
/** Reach of an offset-addressed read (bddo:seekScope): the innermost bounded region, or the whole stream. */
enum class SeekScope { REGION, STREAM }
```
After `data class ConditionalDataTypeRuleIR`:
```kotlin
/**
 * A keyed, open type selection (bddo:DispatchTable). The key -- a sibling field's value
 * ([keyField]) or a HEL expression ([keyExpression]) -- is matched by equality against [arms];
 * the matching type applies, else [default], else the field's own dataType. Arms may be
 * contributed by any graph that imports the table, which is what makes the set open; the
 * compiler collects them across the merged description graph.
 *
 * Keys are normalised so that `7` written as xsd:integer matches a parsed uint8 as well as a
 * parsed uint64: every Number becomes a Long, a String stays a String, anything else matches no arm.
 */
data class DispatchTableIR(
    val name: String, // Full URI of the table
    val keyField: String? = null,
    val keyExpression: HELExpression? = null,
    val arms: Map<Any, DataTypeIR>,
    val default: DataTypeIR? = null
) {
    fun select(key: Any?): DataTypeIR? = (normalise(key)?.let { arms[it] }) ?: default

    companion object {
        fun normalise(key: Any?): Any? = when (key) {
            is Number -> key.toLong()
            is String -> key
            else -> null
        }
    }
}
```
In `FieldIR`, after `val conditionalDataTypes`:
```kotlin
    /** Keyed, open type selection (bddo:hasDispatchTable); exclusive with [conditionalDataTypes]. */
    val dispatchTable: DispatchTableIR? = null,
```
and after `val alignment`:
```kotlin
    /** Whether an offset-addressed read may leave the innermost bounded region (bddo:seekScope). */
    val seekScope: SeekScope = SeekScope.REGION,
```

- [ ] **Step 4: Compile dispatch tables and seek scope from RDF**

In `RdfToIrCompiler`, add the helper (next to `parseHel`):
```kotlin
    /** The [DataTypeIR] of a bddo:DataType individual or a bddo:Struct referenced as a type. */
    private fun dataTypeIrOf(res: Resource): DataTypeIR {
        val (baseType, bitWidth) = resolveBaseTypeAndBitWidth(res)
        return DataTypeIR(
            name = res.uri,
            baseType = baseType,
            bitWidth = bitWidth,
            isSigned = res.getProperty(BDDO.isSigned)?.literal?.boolean,
            hasEndianness = readEndianness(res),
            xsdType = res.getProperty(BDDO.xsdType)?.`object`?.asResource()?.uri
        )
    }

    /**
     * Compiles a bddo:DispatchTable, collecting its arms from the WHOLE model rather than from
     * the table's own description: an arm is any subject whose bddo:armTable is this table, so
     * an importing ontology's contributions are found the moment its graph is merged in.
     * Duplicate keys are refused here rather than resolved by graph order -- the shape forbids
     * them, but a loader that skipped validation must not silently pick one.
     */
    private fun compileDispatchTable(tableRes: Resource): DispatchTableIR {
        val keyField = tableRes.getProperty(BDDO.dispatchOnField)?.`object`?.asResource()?.simpleFieldName()
        val keyExpression = tableRes.getProperty(BDDO.dispatchOnExpression)?.string?.let { parseHel(it) }
        if (keyField == null && keyExpression == null) {
            throw HexplainProfileLoadException("Dispatch table ${tableRes.uri} declares neither bddo:dispatchOnField nor bddo:dispatchOnExpression.")
        }
        val arms = LinkedHashMap<Any, DataTypeIR>()
        for (armRes in model.listSubjectsWithProperty(BDDO.armTable, tableRes).toList().sortedBy { it.toString() }) {
            val keyLit = armRes.getProperty(BDDO.armKey)?.literal
                ?: throw HexplainProfileLoadException("Dispatch arm of ${tableRes.uri} has no bddo:armKey.")
            val isString = keyLit.datatypeURI == null || keyLit.datatypeURI.endsWith("#string")
            val key: Any = if (isString) keyLit.lexicalForm
                else keyLit.lexicalForm.toLongOrNull()
                    ?: throw HexplainProfileLoadException("Dispatch arm key '${keyLit.lexicalForm}' of ${tableRes.uri} is neither a string nor an integer.")
            val typeRes = armRes.getProperty(BDDO.armDataType)?.`object`?.asResource()
                ?: throw HexplainProfileLoadException("Dispatch arm '$key' of ${tableRes.uri} has no bddo:armDataType.")
            if (arms.containsKey(key)) throw HexplainProfileLoadException("Dispatch table ${tableRes.uri} has two arms for key '$key'.")
            arms[key] = dataTypeIrOf(typeRes)
        }
        val default = tableRes.getProperty(BDDO.dispatchDefault)?.`object`?.asResource()?.let { dataTypeIrOf(it) }
        return DispatchTableIR(tableRes.uri, keyField, keyExpression, arms, default)
    }
```
In `compileField`, after the conditional-data-type block:
```kotlin
        val dispatchTable = fieldRes.getProperty(BDDO.hasDispatchTable)?.`object`?.asResource()?.let { compileDispatchTable(it) }
        if (dispatchTable != null && conditionalDataTypes.isNotEmpty()) {
            throw HexplainProfileLoadException("Field ${fieldRes.uri} declares both bddo:hasDispatchTable and bddo:hasConditionalDataType.")
        }
        val seekScope = when (fieldRes.getProperty(BDDO.seekScope)?.`object`?.asResource()) {
            BDDO.streamScope -> SeekScope.STREAM
            else -> SeekScope.REGION
        }
```
and pass `dispatchTable = dispatchTable, seekScope = seekScope` in the `FieldIR(...)` constructor call. Add `import io.hexplain.core.ir.SeekScope` if the wildcard import does not already cover it (it does: `io.hexplain.core.ir.*`).

In `FormatIRToRdf.kt`, after the `conditionalDataTypes` block:
```kotlin
        field.dispatchTable?.let { table ->
            val tableRes = model.createResource(table.name).addProperty(RDF.type, IR.DispatchTable)
            table.keyField?.let { tableRes.addProperty(IR.dispatchOnField, it) }
            table.keyExpression?.let { tableRes.addProperty(IR.dispatchOnExpression, HelUnparser.toSource(it)) }
            table.default?.let { tableRes.addProperty(IR.dispatchDefault, dataTypeResource(it)) }
            for ((key, type) in table.arms) {
                model.createResource().addProperty(RDF.type, IR.DispatchArm)
                    .addProperty(IR.armKey, model.createTypedLiteral(key))
                    .addProperty(IR.armDataType, dataTypeResource(type))
                    .addProperty(IR.hasDispatchTable, tableRes)
            }
            fieldRes.addProperty(IR.hasDispatchTable, tableRes)
        }
        if (field.seekScope == SeekScope.STREAM) fieldRes.addProperty(IR.seekScope, "stream")
```
(add `import io.hexplain.core.ir.SeekScope` there if needed.)

- [ ] **Step 5: Run the test and the existing RDF tests**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.rdf.*"`
Expected: PASS, including `DispatchTableCompilationTest` (3 tests) and `FormatIRToRdfTest`.

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools && git add core/src/main/kotlin/io/hexplain/core/ir/Model.kt core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt core/src/main/kotlin/io/hexplain/core/rdf/FormatIRToRdf.kt core/src/test/kotlin/io/hexplain/core/rdf/DispatchTableCompilationTest.kt && git commit -m "feat(core): compile keyed dispatch tables (arms across the merged graph) and seek scope into the IR

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Keyed dispatch in the engine and its mirrors

**Files:**
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (`resolveEffectiveDataType`, ~line 1038)
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt` (`resolveEffectiveType` ~line 466; the auto-length guard ~line 200)
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/semantic/SemanticLifter.kt` (`resolveStructForMap`, ~line 386)
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/conformance/ConformanceEngine.kt` (`requireResolvableDispatch`, ~line 96)
- Test: `d:/work/hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/DispatchTableParseTest.kt`

**Interfaces:**
- Consumes `DispatchTableIR.select`, `FieldIR.dispatchTable` from Task 5.
- Produces: the parse-time rule "dispatch table wins over conditional rules (they are exclusive anyway); key from `keyField` looked up in the current struct's map, or `keyExpression` evaluated with parent aliased to the current struct, exactly like a `DataTypeRule` condition".

- [ ] **Step 1: Write the failing parse test**

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertArrayEquals
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

/** A keyed table selects the struct a payload is parsed as; an unknown key takes the default. */
class DispatchTableParseTest {
    private val ascii4 = DataTypeIR("bddo:string", BaseType.STRING, 8)
    private val bytes = DataTypeIR("bddo:Bytes", BaseType.BYTES, 8)
    private val u16 = DataTypeIR("uint16be", BaseType.INTEGER, 16, isSigned = false, hasEndianness = Endianness.BIG_ENDIAN)
    private val header = StructIR("t:Header", listOf(FieldIR("v", u16)))
    private val unknown = StructIR("t:Unknown", listOf(FieldIR("raw", bytes, sizeToEndOfStream = true)))
    private val structType = { s: StructIR -> DataTypeIR(s.name, BaseType.BYTES, 8) }

    private fun format(keyField: String? = "tag", keyExpression: String? = null): FormatIR {
        val table = DispatchTableIR(
            name = "t:Dispatch", keyField = keyField,
            keyExpression = keyExpression?.let { HelParserHelper.parse(it) },
            arms = mapOf("hdr " to structType(header)), default = structType(unknown),
        )
        val record = StructIR("t:Record", listOf(
            FieldIR("tag", ascii4, size = 4, encoding = "US-ASCII"),
            FieldIR("body", bytes, sizeToEndOfStream = true, dispatchTable = table),
        ))
        return FormatIR("t", "t:Record", mapOf("t:Record" to record, "t:Header" to header, "t:Unknown" to unknown))
    }

    @Test fun `matching key parses the arm's struct`() {
        val out = Metaparser(format()).parse("hdr \u0001\u0002".toByteArray(Charsets.ISO_8859_1)) as Map<*, *>
        assertEquals(258, ((out["body"] as Map<*, *>)["v"] as Number).toInt())
    }

    @Test fun `unknown key takes the default`() {
        val out = Metaparser(format()).parse("zzzzAB".toByteArray()) as Map<*, *>
        assertArrayEquals("AB".toByteArray(), (out["body"] as Map<*, *>)["raw"] as ByteArray)
    }

    @Test fun `a key expression is evaluated like a conditional-type condition`() {
        val out = Metaparser(format(keyField = null, keyExpression = "parent.tag")).parse("hdr \u0000\u0007".toByteArray(Charsets.ISO_8859_1)) as Map<*, *>
        assertEquals(7, ((out["body"] as Map<*, *>)["v"] as Number).toInt())
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.metacodec.DispatchTableParseTest"`
Expected: FAIL — `body` is parsed as raw bytes (a `ByteArray`, so the `Map` cast throws `ClassCastException`).

- [ ] **Step 3: Implement dispatch in `resolveEffectiveDataType`**

Replace the body of `Metaparser.resolveEffectiveDataType` so it begins:
```kotlin
        fieldDef.dispatchTable?.let { table ->
            // Same self-alias evaluator as the rule list below: `parent` and `instance` both name
            // the containing struct, so a key expression reads exactly like a rule condition.
            val key: Any? = when {
                table.keyField != null -> context[table.keyField]
                else -> HelEvaluator(context, context, rootContext, streamContext = streamCtx(buffer)).evaluate(table.keyExpression!!)
            }
            return table.select(key) ?: fieldDef.dataType
        }
        if (fieldDef.conditionalDataTypes.isEmpty()) return fieldDef.dataType
```
(the existing rule-list loop follows unchanged.)

- [ ] **Step 4: Mirror the rule in the writer, the lifter and the conformance engine**

`Metawriter.resolveEffectiveType` — prepend the same block:
```kotlin
        fieldDef.dispatchTable?.let { table ->
            val key: Any? = if (table.keyField != null) context[table.keyField]
                else HelEvaluator(context, context, rootContext).evaluate(table.keyExpression!!)
            return table.select(key) ?: fieldDef.dataType
        }
```
and in the auto-length guard (~line 200) change `field.conditionalDataTypes.isEmpty()` to `field.conditionalDataTypes.isEmpty() && field.dispatchTable == null`.

`SemanticLifter.resolveStructForMap` — before the `if (field.conditionalDataTypes.isNotEmpty())`:
```kotlin
        field.dispatchTable?.let { table ->
            val evaluator = HelEvaluator(context = valueMap as Map<String, Any>, parentContext = parentMap as Map<String, Any>, rootContext = rootContext as Map<String, Any>)
            val key: Any? = if (table.keyField != null) parentMap[table.keyField]
                else evaluator.evaluate(table.keyExpression!!)
            return table.select(key)?.let { formatIR.structs[it.name] }
        }
```
(In the lifter, `valueMap` is the dispatched value and `parentMap` the struct that carries the field, so the key field is read from `parentMap`.)

`ConformanceEngine.requireResolvableDispatch` — change the condition to `if (field.conditionalDataTypes.isNotEmpty() || field.dispatchTable != null)` and the message's `bddo:hasConditionalDataType` to `bddo:hasConditionalDataType or bddo:hasDispatchTable`.

- [ ] **Step 5: Run the new test and the whole core suite**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test`
Expected: PASS (the full suite; note the run time so later tasks can budget for it).

- [ ] **Step 6: Commit**

```bash
cd /d/work/hexplain-tools && git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt core/src/main/kotlin/io/hexplain/core/semantic/SemanticLifter.kt core/src/main/kotlin/io/hexplain/core/conformance/ConformanceEngine.kt core/src/test/kotlin/io/hexplain/core/metacodec/DispatchTableParseTest.kt && git commit -m "feat(core): keyed dispatch tables select a field's effective type (parser, writer, lifter, conformance)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Stream-scoped pointer reads in the engine

**Files:**
- Modify: `d:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` (`readField` pointer branch ~line 748; `resolveOffsetTarget` bound check ~line 805)
- Test: `d:/work/hexplain-tools/core/src/test/kotlin/io/hexplain/core/metacodec/SeekScopeTest.kt`

**Interfaces:**
- Consumes `FieldIR.seekScope` from Task 5.
- Produces: with `SeekScope.STREAM`, a pointer read's target is checked against `buffer.capacity()`, the limit is raised to the capacity for the read, and both limit and position are restored afterwards — even if the read throws.

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.core.metacodec

import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.assertArrayEquals
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test

/**
 * A pointer read inside a bounded region normally may not leave it (Processing Model §3.2). A
 * table of extents inside one length-delimited container that locates payloads in another --
 * ISOBMFF's iloc pointing into mdat -- needs exactly that, and declares bddo:seekScope
 * bddo:streamScope to say so. The bound is suspended for that one read only.
 */
class SeekScopeTest {
    private val bytes = DataTypeIR("bddo:Bytes", BaseType.BYTES, 8)
    private val u8 = DataTypeIR("uint8", BaseType.INTEGER, 8, isSigned = false)

    /** REGION(4 bytes): offset(1) length(1) data(pointer) pad(2) ; then TAIL(4 bytes) = the target. */
    private fun format(scope: SeekScope): FormatIR {
        val region = StructIR("t:Region", listOf(
            FieldIR("offset", u8),
            FieldIR("length", u8),
            FieldIR("data", bytes, sizeFromField = "length", atOffsetFromField = "offset", seekScope = scope),
            FieldIR("pad", bytes, size = 2),
        ), size = 4)
        val root = StructIR("t:Outer", listOf(
            FieldIR("REGION", DataTypeIR("t:Region", BaseType.BYTES, 8)),
            FieldIR("TAIL", bytes, size = 4),
        ))
        return FormatIR("t", "t:Outer", mapOf("t:Outer" to root, "t:Region" to region))
    }

    // offset 5, length 2 -> bytes "BC" of the tail "ABCD"; region = 05 02 'p' 'p'
    private val input = byteArrayOf(5, 2, 'p'.code.toByte(), 'p'.code.toByte()) + "ABCD".toByteArray()

    @Test fun `region scope refuses a target outside the region`() {
        assertThrows(HexplainParsingException::class.java) { Metaparser(format(SeekScope.REGION)).parse(input) }
    }

    @Test fun `stream scope reads the target and restores the region afterwards`() {
        val out = Metaparser(format(SeekScope.STREAM)).parse(input) as Map<*, *>
        val region = out["REGION"] as Map<*, *>
        assertArrayEquals("BC".toByteArray(), region["data"] as ByteArray)
        assertArrayEquals("pp".toByteArray(), region["pad"] as ByteArray)     // sequential cursor untouched
        assertArrayEquals("ABCD".toByteArray(), out["TAIL"] as ByteArray)      // region end still honoured
    }

    @Test fun `stream scope still bounds the read at the end of the stream`() {
        val truncated = byteArrayOf(5, 9, 'p'.code.toByte(), 'p'.code.toByte()) + "ABCD".toByteArray()
        val e = assertThrows(HexplainParsingException::class.java) { Metaparser(format(SeekScope.STREAM)).parse(truncated) }
        assertEquals(HexplainErrorKind.BOUNDS, e.kind)
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.metacodec.SeekScopeTest"`
Expected: `region scope …` passes already; `stream scope reads …` FAILS with a bounds `HexplainParsingException` (offset 5 outside 0..4).

- [ ] **Step 3: Implement the scoped read**

In `resolveOffsetTarget`, replace the final bound check:
```kotlin
        // A stream-scoped read (bddo:seekScope bddo:streamScope) is bounded by the whole stream,
        // not by the innermost region; readField raises the limit for the read itself.
        val bound = if (fieldDef.seekScope == SeekScope.STREAM) buffer.capacity() else buffer.limit()
        if (pos > bound) {
            throw HexplainParsingException("Field '${fieldDef.name}' offset $pos is outside the ${if (fieldDef.seekScope == SeekScope.STREAM) "stream" else "region"} (0..$bound).", HexplainErrorKind.BOUNDS)
        }
        return pos.toInt()
```
and, in the same function, make `OffsetBase.STREAM_END` subtract from that same `bound` rather than `buffer.limit()` (compute `bound` before the `when`).

In `readField`, replace the pointer branch:
```kotlin
        if (target != null) {
            val saved = buffer.position()
            val savedLimit = buffer.limit()
            // Suspend the region bound for this one read only; restore both limit and cursor even
            // if the read throws, or the enclosing struct's recovery path sees a stream that ends
            // at the wrong place.
            if (fieldDef.seekScope == SeekScope.STREAM) buffer.limit(buffer.capacity())
            try {
                buffer.position(target)
                // A pointer read starts a fresh bit alignment at the target position.
                return readFieldBody(fieldDef, buffer, context, parentContext, rootContext, structEndianness, BitCursor(buffer, bitCursor.msbFirst), baseOffset, ancestors, contextSchema, fieldByteLengths, fieldEncodings, structName)
            } finally {
                buffer.limit(savedLimit)
                buffer.position(saved)
            }
        }
```

- [ ] **Step 4: Run the test and the metacodec suite**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test --tests "io.hexplain.core.metacodec.*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /d/work/hexplain-tools && git add core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt core/src/test/kotlin/io/hexplain/core/metacodec/SeekScopeTest.kt && git commit -m "feat(core): stream-scoped pointer reads may leave the enclosing bounded region

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: HDL surface — `dispatch`, `extend dispatch`, `@seek`

**Files:**
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt`
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` (`parse()` top-level loop; `parseClauses`; `EXPR_STOPPERS`)
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt`
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt`
- Test: `d:/work/hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitDispatchTableTest.kt`

**Interfaces:**
- Produces the surface:
```
payload : bytes[..] dispatch BoxPayload on type [default Unknown] { "ftyp" => FileTypeBox  7 => Header }
extend dispatch BoxPayload { "meta" => MetaBox }          // top-level; table name may be a CURIE after Task 10
data : bytes[len] @at off from stream-start @seek stream  // @seek stream | region
```
- Lowering: `dispatch <Name>` mints `<baseNs><Name>` as `bddo:DispatchTable`; a lone sibling in `on` → `bddo:dispatchOnField`, else `bddo:dispatchOnExpression` (HEL via `HelSynth.toHel`, the switch convention); arms are blank-node `bddo:DispatchArm`s with `bddo:armTable`, `bddo:armKey` (`literalNode`), `bddo:armDataType`; `@seek stream` → `bddo:seekScope bddo:streamScope`.
- AST names used by Task 10: `DispatchArm`, `DispatchClause`, `DispatchExtension`, `SeekClause`, `Document.dispatchExtensions`, `ResolvedDoc.dispatchTables: Map<String, String>`.

- [ ] **Step 1: Write the failing emitter test**

```kotlin
package io.hexplain.hdl.emit

import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.hdl.HdlCompiler
import io.hexplain.hdl.diag.Severity
import org.apache.jena.rdf.model.RDFNode
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class EmitDispatchTableTest {
    private val ns = "https://hexplain.io/formats/t#"
    private fun compile(src: String) = HdlCompiler().compile(src.trimIndent())

    private val SRC = """
        format t
        @root struct Box {
          size : u32
          type : ascii[4]
          payload : bytes[..] dispatch BoxPayload on type default Unknown {
            "ftyp" => FileType
            7 => Header
          }
        }
        struct FileType { major : ascii[4] }
        struct Header { v : u32 }
        struct Unknown { raw : bytes[..] }
        struct Extent {
          off : u32
          len : u32
          data : bytes[len] @at off from stream-start @seek stream
        }
        extend dispatch BoxPayload { "meta" => Header }
    """

    @Test fun `dispatch clause lowers to a named table with independent arms`() {
        val r = compile(SRC); assertTrue(r.ok, r.diagnostics.toString())
        val m = r.model
        val table = m.getResource(ns + "BoxPayload")
        assertTrue(m.contains(table, RDF.type, BDDO.DispatchTable))
        assertTrue(m.contains(table, BDDO.dispatchOnField, m.getResource(ns + "Box.type")))
        assertTrue(m.contains(table, BDDO.dispatchDefault, m.getResource(ns + "Unknown")))
        assertTrue(m.contains(m.getResource(ns + "Box.payload"), BDDO.hasDispatchTable, table))
        val arms = m.listSubjectsWithProperty(BDDO.armTable, table).toList()
        assertEquals(3, arms.size)
        val keys = arms.map { it.getProperty(BDDO.armKey).literal.lexicalForm }.toSet()
        assertEquals(setOf("ftyp", "7", "meta"), keys)
        val seven = arms.first { it.getProperty(BDDO.armKey).literal.lexicalForm == "7" }
        assertEquals("http://www.w3.org/2001/XMLSchema#integer", seven.getProperty(BDDO.armKey).literal.datatypeURI)
        assertTrue(m.contains(seven, BDDO.armDataType, m.getResource(ns + "Header")))
        assertFalse(m.contains(m.getResource(ns + "Box.payload"), BDDO.hasConditionalDataType, null as RDFNode?))
    }

    @Test fun `key expression that is not a lone sibling lowers to dispatchOnExpression`() {
        // A double-quoted HDL string renders as a single-quoted HEL literal in the synthesized expression.
        val r = compile(SRC.replace("on type default", "on type + \"x\" default")); assertTrue(r.ok, r.diagnostics.toString())
        val table = r.model.getResource(ns + "BoxPayload")
        assertEquals("parent.type + 'x'", table.getProperty(BDDO.dispatchOnExpression).string)
        assertFalse(table.hasProperty(BDDO.dispatchOnField))
    }

    @Test fun `seek clause lowers to seekScope`() {
        val r = compile(SRC); assertTrue(r.ok)
        assertTrue(r.model.contains(r.model.getResource(ns + "Extent.data"), BDDO.seekScope, BDDO.streamScope))
    }

    @Test fun `duplicate keys, unknown targets and unknown tables are compile errors`() {
        val dup = compile(SRC.replace("\"meta\" => Header", "\"ftyp\" => Header"))
        assertTrue(dup.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("duplicate dispatch key 'ftyp'") }, dup.diagnostics.toString())
        val badTarget = compile(SRC.replace("\"meta\" => Header", "\"meta\" => Nope"))
        assertTrue(badTarget.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("names no declared struct") }, badTarget.diagnostics.toString())
        val badTable = compile(SRC.replace("extend dispatch BoxPayload", "extend dispatch Elsewhere"))
        assertTrue(badTable.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("unknown dispatch table 'Elsewhere'") }, badTable.diagnostics.toString())
        val both = compile(SRC.replace("payload : bytes[..] dispatch", "payload : bytes[..] switch type { \"a\" => Header } dispatch"))
        assertTrue(both.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("both 'switch' and 'dispatch'") }, both.diagnostics.toString())
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.emit.EmitDispatchTableTest"`
Expected: FAIL — the parser reports `unexpected token 'dispatch'` style diagnostics, so `r.ok` is false.

- [ ] **Step 3: AST**

In `Ast.kt` add:
```kotlin
/** One `<key> => <Struct>` arm of a keyed dispatch table; [key] is a string or integer literal. */
data class DispatchArm(val key: LiteralValue, val struct: String, val span: Span)

/**
 * `dispatch <Name> on <expr> [default <Struct>] { <key> => <Struct> … }` — declares a keyed, OPEN
 * bddo:DispatchTable on this field. Unlike `switch`, whose ordered rule list is closed, a table's
 * arms are independent resources, so `extend dispatch` (here or in an importing module) can add
 * keys without rewriting anything. [name] mints the table's IRI in the format namespace.
 */
data class DispatchClause(val name: String, val on: Expr, val default: String?, val arms: List<DispatchArm>, val span: Span) : Clause

/** `@seek stream|region` — bddo:seekScope on an offset-addressed field. */
data class SeekClause(val stream: Boolean) : Clause

/** Top-level `extend dispatch <Table> { arms }`: contributes arms to a table declared in this
 *  document (bare name) or in an imported module (CURIE, Task 10). */
data class DispatchExtension(val table: String, val arms: List<DispatchArm>, val span: Span)
```
In `Clause.expressions()` add the branch `is DispatchClause -> listOf(on)`. In `Document` add `val dispatchExtensions: List<DispatchExtension> = emptyList()`.

- [ ] **Step 4: Parser**

In `parse()` add to the top-level `when`: `atText("extend") -> dispatchExtensions.add(parseDispatchExtension())` (declare `val dispatchExtensions = ArrayList<DispatchExtension>()` and pass it as `dispatchExtensions = dispatchExtensions` to `Document`).

In `parseClauses()` add before the `at(TokKind.ANNOT)` branch: `atText("dispatch") -> out.add(parseDispatch())`, and inside the annotation `when`: `"@seek" -> { next(); out.add(SeekClause(parseSeekScope())) }`.

Add to `EXPR_STOPPERS`: `"dispatch"`, `"default"`, `"on"`.

New parser functions:
```kotlin
    /** `dispatch <Name> on <expr> [default <Struct>] { arms }` */
    private fun parseDispatch(): DispatchClause {
        val span = next().span // 'dispatch'
        val name = expect(TokKind.IDENT).text
        if (!atText("on")) err("dispatch '$name' needs a key: 'dispatch $name on <expr> { ... }'")
        else next()
        val on = exprFromAccessorRun()
        var default: String? = null
        if (atText("default")) { next(); default = expect(TokKind.IDENT).text }
        return DispatchClause(name, on, default, parseDispatchArms(), span)
    }

    /** `extend dispatch <Table> { arms }` */
    private fun parseDispatchExtension(): DispatchExtension {
        val span = next().span // 'extend'
        if (!atText("dispatch")) err("expected 'dispatch' after 'extend'") else next()
        val table = expect(TokKind.IDENT).text
        return DispatchExtension(table, parseDispatchArms(), span)
    }

    /** `{ <string|int> => <Struct> , … }` — only literal keys; a `when` guard belongs to `switch`. */
    private fun parseDispatchArms(): List<DispatchArm> {
        expect(TokKind.LBRACE)
        val arms = ArrayList<DispatchArm>()
        while (!at(TokKind.RBRACE) && !at(TokKind.EOF)) {
            val span = peek().span
            val key = parseLiteral()
            if (key !is StrLit && key !is IntLit) err("a dispatch key must be a string or integer literal")
            expect(TokKind.ARROW)
            arms.add(DispatchArm(key, expect(TokKind.IDENT).text, span))
            if (at(TokKind.COMMA)) next()
        }
        expect(TokKind.RBRACE)
        return arms
    }

    private fun parseSeekScope(): Boolean =
        when (val t = expect(TokKind.IDENT).text) { "stream" -> true; "region" -> false; else -> { err("bad seek scope '$t' (stream|region)"); false } }
```

- [ ] **Step 5: Resolver**

Add to `ResolvedDoc`: `val dispatchTables: Map<String, String> = emptyMap()` (DSL table name → minted IRI) and `val dispatchExtensions: List<DispatchExtension> = emptyList()`.

In `Resolver.resolve`, after `structs` are built:
```kotlin
        // Every `dispatch <Name>` mints one table in the format namespace; names are unique.
        val dispatchTables = LinkedHashMap<String, String>()
        for (rs in structs) for (rf in rs.fields) for (c in rf.decl.clauses) if (c is DispatchClause) {
            if (dispatchTables.put(c.name, baseNs + c.name) != null)
                diags.add(Diagnostic(Severity.ERROR, "duplicate dispatch table '${c.name}'", c.span))
        }
        for (x in doc.dispatchExtensions) {
            if (!x.table.contains(':') && x.table !in dispatchTables)
                diags.add(Diagnostic(Severity.ERROR, "unknown dispatch table '${x.table}'", x.span))
        }
        validateDispatchKeys(structs, doc.dispatchExtensions, dispatchTables.keys, diags)
```
and pass `dispatchTables = dispatchTables, dispatchExtensions = doc.dispatchExtensions` to `ResolvedDoc`.

In `validateTypeReferences`, inside the clause `when`, add:
```kotlin
                    is DispatchClause -> {
                        c.arms.forEach { if (!it.struct.contains(':')) check(it.struct, "dispatch arm type", it.span) }
                        c.default?.let { if (!it.contains(':')) check(it, "dispatch default type", f.span) }
                    }
```
and after the loop over fields in `resolve` (top level) validate extension arms the same way:
```kotlin
        for (x in doc.dispatchExtensions) for (a in x.arms) if (!a.struct.contains(':') && a.struct !in declared)
            diags.add(Diagnostic(Severity.ERROR, "dispatch arm type '${a.struct}' names no declared struct", a.span))
```

New function:
```kotlin
    /** A key is unique per table across the declaring clause and every local extension; two arms
     *  with one key would make the choice depend on order, which is what a keyed table rules out.
     *  A field carrying both `switch` and `dispatch` is refused for the same reason. */
    private fun validateDispatchKeys(structs: List<ResolvedStruct>, extensions: List<DispatchExtension>, tables: Set<String>, diags: MutableList<Diagnostic>) {
        val seen = HashMap<String, MutableSet<String>>()
        fun keyText(v: LiteralValue) = when (v) { is StrLit -> v.value; is IntLit -> v.value.toString(); else -> v.toString() }
        fun record(table: String, arm: DispatchArm) {
            if (!seen.getOrPut(table) { HashSet() }.add(keyText(arm.key)))
                diags.add(Diagnostic(Severity.ERROR, "duplicate dispatch key '${keyText(arm.key)}' in table '$table'", arm.span))
        }
        for (rs in structs) for (rf in rs.fields) {
            val clauses = rf.decl.clauses
            if (clauses.any { it is SwitchClause } && clauses.any { it is DispatchClause })
                diags.add(Diagnostic(Severity.ERROR, "field '${rf.decl.name}' declares both 'switch' and 'dispatch'; a field selects its type one way", rf.decl.span))
            for (c in clauses) if (c is DispatchClause) c.arms.forEach { record(c.name, it) }
        }
        for (x in extensions) if (x.table in tables) x.arms.forEach { record(x.table, it) }
    }
```

- [ ] **Step 6: Emitter**

In `emitClauses` add `is DispatchClause -> emitDispatch(f, c, owner)` and `is SeekClause -> f.addProperty(BDDO.seekScope, if (c.stream) BDDO.streamScope else BDDO.regionScope)`.

Add:
```kotlin
    /** The IRI a struct reference resolves to: a declared struct's minted IRI (honouring `as`),
     *  an imported struct's IRI (Task 10), or the naive expansion for a forward reference. */
    private fun structUri(ref: String): String =
        doc.structs.firstOrNull { it.decl.name == ref }?.uri
            ?: if (ref.contains(':')) doc.expandCurie(ref) else doc.baseNs + ref

    private fun tableUri(ref: String): String =
        doc.dispatchTables[ref] ?: if (ref.contains(':')) doc.expandCurie(ref) else doc.baseNs + ref

    private fun emitDispatch(f: Resource, c: DispatchClause, owner: ResolvedStruct?) {
        val table = m.createResource(tableUri(c.name)).addProperty(RDF.type, BDDO.DispatchTable)
        val lone = HelSynth.isLoneSibling(c.on)
        val siblingUri = if (lone != null && owner != null) doc.siblingUri(owner, lone) else null
        if (siblingUri != null) table.addProperty(BDDO.dispatchOnField, m.getResource(siblingUri))
        else table.addProperty(BDDO.dispatchOnExpression, m.createLiteral(HelSynth.toHel(c.on, siblingRenamer(owner))))
        c.default?.let { table.addProperty(BDDO.dispatchDefault, m.createResource(structUri(it))) }
        f.addProperty(BDDO.hasDispatchTable, table)
        emitDispatchArms(table, c.arms)
    }

    private fun emitDispatchArms(table: Resource, arms: List<DispatchArm>) {
        for (a in arms) m.createResource()
            .addProperty(RDF.type, BDDO.DispatchArm)
            .addProperty(BDDO.armTable, table)
            .addProperty(BDDO.armKey, literalNode(a.key))
            .addProperty(BDDO.armDataType, m.createResource(structUri(a.struct)))
    }
```
In `emit()` after the struct loop: `for (x in doc.dispatchExtensions) emitDispatchArms(m.createResource(tableUri(x.table)), x.arms)`. Replace the two existing `doc.structs.firstOrNull { it.decl.name == … }?.uri ?: (doc.baseNs + …)` lookups in `emitField` (StructRef) and `emitSwitch` with `structUri(...)`.

`literalNode(IntLit)` produces an `xsd:long` typed literal via `createTypedLiteral(Long)`; the arm shape accepts `xsd:integer` only, so in `emitDispatchArms` map integer keys explicitly: `if (a.key is IntLit) m.createTypedLiteral(a.key.value.toString(), XSDDatatype.XSDinteger) else literalNode(a.key)`.

- [ ] **Step 7: Run the test, then the whole hdl suite**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test`
Expected: PASS, including the golden-snapshot parity tests (nothing emitted changes for documents without `dispatch`).

- [ ] **Step 8: Commit**

```bash
cd /d/work/hexplain-tools && git add hdl/src/main/kotlin/io/hexplain/hdl hdl/src/test/kotlin/io/hexplain/hdl/emit/EmitDispatchTableTest.kt && git commit -m "feat(hdl): dispatch tables, extend dispatch, and @seek

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: M2 — item machinery: `iloc`, `iinf`/`infe`, `iref`, `ipma`, `pitm`, `hdlr`, extent payloads

**Files:**
- Modify: `d:/work/hexplain-tools/hdl/src/test/resources/profiles/isobmff/isobmff.hx` (replace the `switch` with a dispatch table; add the item structs)
- Modify: `d:/work/hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/parity/IsobmffParityTest.kt`
- Modify (copy): `d:/work/hexplain-profiles/profiles/isobmff/isobmff.hx`, `isobmff.ttl`

**Interfaces:**
- Produces struct names used by Task 11's leaf profiles: `BoxPayload` (the table), `HandlerBox`, `PrimaryItemBox`, `ItemLocationBox`, `IlocItem`, `IlocExtent`, `ItemInfoEntry`, `ItemReferenceBox`, `ItemReference`, `ItemPropertyAssociationBox`, `IpmaEntry`, `IpmaAssociation`, `DataReferenceBox`. Parsed keys: `itemId`, `baseOffset`, `extents`, `extentOffset`, `extentLength`, `absoluteOffset`, `data`, `itemType`, `itemName`, `referenceType`, `fromItemId`, `toItemIds`, `essential`, `propertyIndex`.

- [ ] **Step 1: Extend the parity test with item-level expectations**

Add to `IsobmffParityTest`:
```kotlin
    private fun sha256(b: ByteArray) = java.security.MessageDigest.getInstance("SHA-256").digest(b).joinToString("") { "%02x".format(it) }
    private fun payload(box: Map<*, *>) = box["payload"] as Map<*, *>
    private fun n(v: Any?) = (v as Number).toLong()

    @Test fun `heic items, extents and payload bytes`() {
        val meta = boxes(parse("heif/example.heic"))[1]
        assertEquals("pict", payload(child(meta, "hdlr"))["handlerType"])
        assertEquals(20004L, n(payload(child(meta, "pitm"))["itemId"]))

        val iloc = payload(child(meta, "iloc"))
        assertEquals(listOf(4L, 4L, 4L, 0L), listOf("offsetSize", "lengthSize", "baseOffsetSize", "indexSize").map { n(iloc[it]) })
        val items = (iloc["items"] as List<*>).map { it as Map<*, *> }
        assertEquals(listOf(20004L, 20005L, 20006L, 20007L), items.map { n(it["itemId"]) })
        assertEquals(listOf(957L, 334669L, 359200L, 689340L), items.map { n(it["baseOffset"]) })
        val extents = items.map { ((it["extents"] as List<*>).single()) as Map<*, *> }
        assertEquals(listOf(333704L, 24523L, 330132L, 28758L), extents.map { n(it["extentLength"]) })
        assertEquals(listOf(957L, 334669L, 359200L, 689340L), extents.map { n(it["absoluteOffset"]) })
        assertEquals(listOf(
            "8b26880fe5d682be53546cdfc7c04d78b4dc7d51a087a6cce8c561fbe19a9fd6",
            "cfbb00ce5d73a431b6ccfb19b8aa22efa47bf9a9cd2c2c292b00800dc97cc134",
            "601e3d318d3a7508ed6a1d36e9558af3747716211252e09ae1fe30c62f03d66b",
            "01a7920307dcb72ccff3d25d286e56efbf931e010a6bf2601337c29ebfcd5e77",
        ), extents.map { sha256(it["data"] as ByteArray) })

        val infos = (payload(child(meta, "iinf"))["entries"] as List<*>).map { payload(it as Map<*, *>) }
        assertEquals(listOf(20004L, 20005L, 20006L, 20007L), infos.map { n(it["itemId"]) })
        assertEquals(List(4) { "hvc1" }, infos.map { it["itemType"] })
        assertEquals(List(4) { "HEVC Image" }, infos.map { it["itemName"] })

        val refs = (payload(child(meta, "iref"))["references"] as List<*>).map { it as Map<*, *> }
        assertEquals(listOf("thmb", "thmb"), refs.map { it["referenceType"] })
        assertEquals(listOf(20005L, 20007L), refs.map { n(it["fromItemId"]) })
        assertEquals(listOf(listOf(20004L), listOf(20006L)), refs.map { (it["toItemIds"] as List<*>).map { id -> n(id) } })

        val ipma = payload(child(child(meta, "iprp"), "ipma"))
        val entries = (ipma["entries"] as List<*>).map { it as Map<*, *> }
        assertEquals(listOf(20004L, 20005L, 20006L, 20007L), entries.map { n(it["itemId"]) })
        val assoc = { e: Map<*, *> -> (e["associations"] as List<*>).map { a -> a as Map<*, *> }.map { n(it["essential"]) to n(it["propertyIndex"]) } }
        assertEquals(listOf(1L to 1L, 0L to 2L), assoc(entries[0]))
        assertEquals(listOf(1L to 6L, 0L to 4L), assoc(entries[3]))
    }

    @Test fun `avif single item`() {
        val meta = boxes(parse("heif/example.avif"))[1]
        assertEquals(1L, n(payload(child(meta, "pitm"))["itemId"]))
        val info = payload((payload(child(meta, "iinf"))["entries"] as List<*>).single() as Map<*, *>)
        assertEquals("av01", info["itemType"])
        val item = (payload(child(meta, "iloc"))["items"] as List<*>).single() as Map<*, *>
        val extent = (item["extents"] as List<*>).single() as Map<*, *>
        assertEquals(280L, n(extent["absoluteOffset"]))
        assertEquals("77521db0cff42126b3373e42609b5cd90669dd44d22b71429f14312422502a38", sha256(extent["data"] as ByteArray))
        val assoc = ((payload(child(child(meta, "iprp"), "ipma"))["entries"] as List<*>).single() as Map<*, *>)["associations"] as List<*>
        assertEquals(listOf(1L to 1L, 1L to 2L, 0L to 3L), assoc.map { a -> (a as Map<*, *>).let { n(it["essential"]) to n(it["propertyIndex"]) } })
    }
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.parity.IsobmffParityTest"`
Expected: the two new tests FAIL (`hdlr` payload is a `ByteArray`, `ClassCastException`); the M1 tests still pass.

- [ ] **Step 3: Replace the switch with a dispatch table and add the item structs**

In `isobmff.hx`, replace the `payload` field of `Box` with:
```
  payload   : bytes[..] dispatch BoxPayload on type {
    "ftyp" => FileTypeBox
    "meta" => MetaBox
    "hdlr" => HandlerBox
    "pitm" => PrimaryItemBox
    "iloc" => ItemLocationBox
    "iinf" => ItemInfoBox
    "infe" => ItemInfoEntry
    "iref" => ItemReferenceBox
    "iprp" => ContainerPayload
    "ipco" => ContainerPayload
    "ipma" => ItemPropertyAssociationBox
    "dinf" => ContainerPayload
    "dref" => DataReferenceBox
    "grpl" => ContainerPayload
    "moov" => ContainerPayload
    "trak" => ContainerPayload
    "mdia" => ContainerPayload
    "minf" => ContainerPayload
    "stbl" => ContainerPayload
    "edts" => ContainerPayload
    "udta" => ContainerPayload
  }
```
Change `FullBoxHeader.flags` from Task 1's `bytes[3]` workaround back to `flags : bits[24]` (Task 1b made `bits[N]` loadable) and delete LIMITS bullet 4 about it. Keep `File`, `ContainerPayload`, `FileTypeBox`, `Brand`, `MetaBox`, `ItemInfoBox` as written in Task 1 (note: `ItemInfoBox.entryCount` is already written as `derive [ ... ]`). Append the item structs:
```
struct HandlerBox
  @label "hdlr — handler reference"
{
  hdr         : FullBoxHeader
  preDefined  : u32
  handlerType : ascii[4] @comment "'pict' for still images."
  reserved    : bytes[12]
  name        : str[..] @trim-null
}

struct PrimaryItemBox
  @label "pitm — primary item"
{
  hdr      : FullBoxHeader
  itemId16 : u16 if hdr.version == 0
  itemId32 : u32 if hdr.version != 0
  itemId   : derive [ hdr.version == 0 ? itemId16 : itemId32 ]
}

// iloc: three nibbles choose the byte width (0, 4 or 8) of three later fields, independently,
// and width 0 means the field is absent. Each width is a presence-conditioned field plus a
// derived value, so later clauses reference one name whatever the width.
struct ItemLocationBox
  @label "iloc — item locations"
{
  hdr            : FullBoxHeader
  offsetSize     : bits[4]
  lengthSize     : bits[4]
  baseOffsetSize : bits[4]
  indexSize      : bits[4] @comment "Reserved (0) when version == 0."
  itemCount16    : u16 if hdr.version < 2
  itemCount32    : u32 if hdr.version == 2
  itemCount      : derive [ hdr.version < 2 ? itemCount16 : itemCount32 ]
  items          : IlocItem repeat itemCount
}

struct IlocItem
  @label "iloc item entry"
{
  itemId16           : u16 if parent.hdr.version < 2
  itemId32           : u32 if parent.hdr.version == 2
  itemId             : derive [ parent.hdr.version < 2 ? itemId16 : itemId32 ]
  reserved           : bits[12] if parent.hdr.version >= 1
  constructionMethod : bits[4]  if parent.hdr.version >= 1
  method             : derive [ parent.hdr.version == 0 ? 0 : constructionMethod ]
  dataReferenceIndex : u16
  baseOffset32       : u32 if parent.baseOffsetSize == 4
  baseOffset64       : u64 if parent.baseOffsetSize == 8
  baseOffset         : derive [ parent.baseOffsetSize == 4 ? baseOffset32 : (parent.baseOffsetSize == 8 ? baseOffset64 : 0) ]
  extentCount        : u16
  extents            : IlocExtent repeat extentCount
}

struct IlocExtent
  @label "iloc extent"
{
  extentIndex32  : u32 if parent.parent.hdr.version >= 1 and parent.parent.indexSize == 4
  extentIndex64  : u64 if parent.parent.hdr.version >= 1 and parent.parent.indexSize == 8
  extentOffset32 : u32 if parent.parent.offsetSize == 4
  extentOffset64 : u64 if parent.parent.offsetSize == 8
  extentOffset   : derive [ parent.parent.offsetSize == 4 ? extentOffset32 : (parent.parent.offsetSize == 8 ? extentOffset64 : 0) ]
  extentLength32 : u32 if parent.parent.lengthSize == 4
  extentLength64 : u64 if parent.parent.lengthSize == 8
  extentLength   : derive [ parent.parent.lengthSize == 4 ? extentLength32 : (parent.parent.lengthSize == 8 ? extentLength64 : 0) ]
  absoluteOffset : derive [ parent.baseOffset + extentOffset ]
  // The payload lives in mdat, outside the meta box's region: a stream-scoped pointer read.
  // Only construction method 0 (file offsets) is described; see LIMITS.
  data           : bytes[extentLength] @at absoluteOffset from stream-start @seek stream if parent.method == 0
}

struct ItemInfoEntry
  @label "infe — item information entry"
{
  hdr                 : FullBoxHeader
  itemId16            : u16 if hdr.version < 3
  itemId32            : u32 if hdr.version == 3
  itemId              : derive [ hdr.version < 3 ? itemId16 : itemId32 ]
  itemProtectionIndex : u16
  itemType            : ascii[4] if hdr.version >= 2
  itemName            : str @terminator 0x00
  contentType         : str @terminator 0x00 if hdr.version < 2 or itemType == "mime"
  contentEncoding     : str @terminator 0x00 if (hdr.version < 2 or itemType == "mime") and not eof()
  itemUriType         : str @terminator 0x00 if hdr.version >= 2 and itemType == "uri "
}

struct ItemReferenceBox
  @label "iref — item references"
{
  hdr        : FullBoxHeader
  references : ItemReference repeat until eof()
}

// Each reference is box-framed, but its type is the reference type (thmb, dimg, cdsc, auxl, …),
// an open set, so it is a plain sized record rather than a dispatched Box.
struct ItemReference
  @label "item reference"
  @size size
{
  size           : u32
  referenceType  : ascii[4]
  fromItemId16   : u16 if parent.hdr.version == 0
  fromItemId32   : u32 if parent.hdr.version == 1
  fromItemId     : derive [ parent.hdr.version == 0 ? fromItemId16 : fromItemId32 ]
  referenceCount : u16
  toItemIds16    : u16 repeat referenceCount if parent.hdr.version == 0
  toItemIds32    : u32 repeat referenceCount if parent.hdr.version == 1
  toItemIds      : derive [ parent.hdr.version == 0 ? toItemIds16 : toItemIds32 ]
}

struct ItemPropertyAssociationBox
  @label "ipma — item/property associations"
{
  hdr        : FullBoxHeader
  wideIndex  : derive [ (hdr.flags & 1) == 1 ]
  entryCount : u32
  entries    : IpmaEntry repeat entryCount
}

struct IpmaEntry
{
  itemId16         : u16 if parent.hdr.version < 1
  itemId32         : u32 if parent.hdr.version >= 1
  itemId           : derive [ parent.hdr.version < 1 ? itemId16 : itemId32 ]
  associationCount : u8
  associations     : IpmaAssociation repeat associationCount
}

struct IpmaAssociation
{
  essential       : bits[1]
  propertyIndex7  : bits[7]  if not parent.parent.wideIndex
  propertyIndex15 : bits[15] if parent.parent.wideIndex
  propertyIndex   : derive [ parent.parent.wideIndex ? propertyIndex15 : propertyIndex7 ]
}

struct DataReferenceBox
  @label "dref — data references"
{
  hdr        : FullBoxHeader
  entryCount : u32
  entries    : Box repeat until eof()
}
```
Replace the LIMITS section with:
```
// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. Item payloads are read only for iloc construction_method 0 (file offsets). Method 1 (offsets
//    into idat) needs an offset base of "the start of a sibling box's payload", which BDDO cannot
//    name; method 2 (offsets into another item) is a forward reference. Both are left as opaque.
// 2. infe versions 0 and 1 are read as far as item_name; their trailing content_type /
//    content_encoding pair is not distinguished from version 2's mime case.
// 3. Track boxes (moov/trak/…) are walked as containers; their leaf boxes are opaque.
// 4. A uuid box's extended type is read; its payload is never dispatched on it.
// 5. Image properties (ispe, pixi, colr, …) and codec configurations belong to the heif and
//    codec modules that extend this table; here they are opaque bytes.
```

- [ ] **Step 4: Run the parity test until it passes**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.parity.IsobmffParityTest" -i 2>&1 | grep -E "PASSED|FAILED|Exception|expected" | head -30`
Expected: PASS (6 tests). Likely first-round failures and their fixes: `toItemIds16 … repeat … if` — if the parser rejects the clause order, put `if` before `repeat`; `not parent.parent.wideIndex` — if HEL rejects `not` on a Boolean accessor, write `parent.parent.wideIndex == false`; `(hdr.flags & 1) == 1` — if the bracket run swallows the parenthesised expression, write it as `` derive `(instance.hdr.flags & 1) == 1` ``.

- [ ] **Step 5: Copy to the profile library, recompile, run its gates**

```bash
cp /d/work/hexplain-tools/hdl/src/test/resources/profiles/isobmff/isobmff.hx /d/work/hexplain-profiles/profiles/isobmff/isobmff.hx && cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:run --args="/d/work/hexplain-profiles/profiles/isobmff/isobmff.hx -o /d/work/hexplain-profiles/profiles/isobmff/isobmff.ttl" && cd /d/work/hexplain-profiles && python tools/run_gates.py
```
Expected: all gates PASS (`test_profile_library` validates the compiled Turtle against the Task 3 shapes — a `DispatchArmShape` violation here means the emitter's key literal datatype is wrong).

- [ ] **Step 6: Commit both repos**

```bash
cd /d/work/hexplain-tools && git add hdl/src/test/resources/profiles/isobmff/isobmff.hx hdl/src/test/kotlin/io/hexplain/hdl/parity/IsobmffParityTest.kt && git commit -m "feat(profiles): ISO BMFF item machinery with dispatch table and stream-scoped extent reads, parse-verified

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd /d/work/hexplain-profiles && git add profiles/isobmff && git commit -m "feat: ISO BMFF item machinery (iloc, iinf, iref, ipma) on a keyed dispatch table

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: HDL modules and `import`

**Files:**
- Create: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/imports/ImportResolver.kt`
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/ast/Ast.kt` (`FormatDecl`, `Document`, new `ImportDecl`)
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/parse/Parser.kt` (`parse()`, `parseFormat`)
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/resolve/Resolver.kt`
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/emit/TurtleEmitter.kt`
- Modify: `d:/work/hexplain-tools/hdl/src/main/kotlin/io/hexplain/hdl/HdlCompiler.kt`, `cli/Main.kt`
- Test: `d:/work/hexplain-tools/hdl/src/test/kotlin/io/hexplain/hdl/imports/ImportTest.kt`

**Interfaces:**
- Surface: `module <name> @namespace "…"` (a `format` that is not a file format: no root required, ontology header emitted) and `import "<relative path>" as <alias>`. In the importing document, `alias:Name` names an imported struct in any type position (field type, `switch`/`dispatch` arm, `dispatch … default`) and `alias:Table` names an imported dispatch table in `extend dispatch`.
- Lowering: nothing of the imported module is re-emitted; the importer's ontology `<baseNs without #>` gets `a owl:Ontology ; owl:imports <imported ontology IRI>`; references point at the imported IRIs.
- API:
```kotlin
fun interface ImportResolver { fun resolve(importPath: String): ImportSource? }
data class ImportSource(val id: String, val text: String, val resolver: ImportResolver)
class FileImportResolver(baseDir: java.nio.file.Path) : ImportResolver
object NoImports : ImportResolver
data class ImportedModule(val alias: String, val namespace: String, val ontologyIri: String,
                          val structUris: Map<String, String>, val dispatchTableUris: Map<String, String>, val result: CompileResult)
class HdlCompiler { fun compile(source: String, imports: ImportResolver = NoImports): CompileResult
                    fun compileFile(path: java.nio.file.Path): CompileResult }
CompileResult += val imports: List<CompileResult>; fun mergedModel(): Model   // importer ∪ all transitive imports
ResolvedDoc += val imports: Map<String, ImportedModule>; fun importedStructUri(curie: String): String?; fun importedTableUri(curie: String): String?
```

- [ ] **Step 1: Write the failing test**

```kotlin
package io.hexplain.hdl.imports

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.core.rdf.vocab.BDDO
import io.hexplain.hdl.HdlCompiler
import io.hexplain.hdl.diag.Severity
import org.apache.jena.vocabulary.OWL
import org.apache.jena.vocabulary.RDF
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class ImportTest {
    private val BASE = """
        module base @namespace "https://ex.org/base#" @endian big
        struct Header { version : u8  flags : bits[24] }
        @root struct Record {
          tag  : ascii[4]
          body : bytes[..] dispatch BodyDispatch on tag { "hdr " => Header }
        }
    """.trimIndent()

    private val LEAF = """
        format leaf @namespace "https://ex.org/leaf#" @endian big
        import "base.hx" as base
        extend dispatch base:BodyDispatch { "wide" => Wide }
        struct Wide { hdr : base:Header  width : u32 }
        @root struct File { records : base:Record repeat until eof() }
    """.trimIndent()

    private fun resolver(files: Map<String, String>): ImportResolver = object : ImportResolver {
        override fun resolve(importPath: String): ImportSource? =
            files[importPath]?.let { ImportSource(importPath, it, this) }
    }

    @Test fun `imported structs and tables are referenced by IRI, and the ontology imports the module`() {
        val r = HdlCompiler().compile(LEAF, resolver(mapOf("base.hx" to BASE)))
        assertTrue(r.ok, r.diagnostics.toString())
        val m = r.model
        val ontology = m.getResource("https://ex.org/leaf")
        assertTrue(m.contains(ontology, RDF.type, OWL.Ontology))
        assertTrue(m.contains(ontology, OWL.imports, m.getResource("https://ex.org/base")))
        assertTrue(m.contains(m.getResource("https://ex.org/leaf#Wide.hdr"), BDDO.dataType, m.getResource("https://ex.org/base#Header")))
        assertTrue(m.contains(m.getResource("https://ex.org/leaf#File.records"), BDDO.dataType, m.getResource("https://ex.org/base#Record")))
        val arm = m.listSubjectsWithProperty(BDDO.armTable, m.getResource("https://ex.org/base#BodyDispatch")).toList().single()
        assertEquals("wide", arm.getProperty(BDDO.armKey).string)
        // Nothing of the base module is re-emitted.
        assertFalse(m.contains(m.getResource("https://ex.org/base#Header"), RDF.type, BDDO.Struct))
        assertEquals(1, r.imports.size)
    }

    @Test fun `the merged model parses through the imported table`() {
        val r = HdlCompiler().compile(LEAF, resolver(mapOf("base.hx" to BASE)))
        val ir = RdfToIrCompiler(r.mergedModel()).compile("https://ex.org/leaf#File")
        // record 1: "hdr " + version 2 + flags 0; record 2: "wide" + Header(1,0,0,0) + width 800
        val bytes = "hdr \u0002\u0000\u0000\u0000wide\u0001\u0000\u0000\u0000\u0000\u0000\u0003\u0020".toByteArray(Charsets.ISO_8859_1)
        val out = Metaparser(ir).parse(bytes) as Map<*, *>
        val records = (out["records"] as List<*>).map { it as Map<*, *> }
        assertEquals(2, ((records[0]["body"] as Map<*, *>)["version"] as Number).toInt())
        assertEquals(800, ((records[1]["body"] as Map<*, *>)["width"] as Number).toInt())
    }

    @Test fun `unresolvable import, unknown imported name, and import cycles are errors`() {
        val missing = HdlCompiler().compile(LEAF, NoImports)
        assertTrue(missing.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("cannot resolve import 'base.hx'") }, missing.diagnostics.toString())
        val unknown = HdlCompiler().compile(LEAF.replace("base:Header", "base:Nope"), resolver(mapOf("base.hx" to BASE)))
        assertTrue(unknown.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("'base:Nope'") && it.message.contains("module 'base'") }, unknown.diagnostics.toString())
        val a = "module a @namespace \"https://ex.org/a#\"\nimport \"b.hx\" as b\nstruct A { x : u8 }"
        val b = "module b @namespace \"https://ex.org/b#\"\nimport \"a.hx\" as a\nstruct B { x : u8 }"
        val cyc = HdlCompiler().compile(a, resolver(mapOf("a.hx" to a, "b.hx" to b)))
        assertTrue(cyc.diagnostics.any { it.severity == Severity.ERROR && it.message.contains("import cycle") }, cyc.diagnostics.toString())
    }

    @Test fun `a module with no root struct compiles without the no-struct error`() {
        val r = HdlCompiler().compile("module m @namespace \"https://ex.org/m#\"\nstruct Only { x : u8 }")
        assertTrue(r.ok, r.diagnostics.toString())
        assertTrue(r.model.contains(r.model.getResource("https://ex.org/m"), RDF.type, OWL.Ontology))
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.imports.ImportTest"`
Expected: compilation error (`ImportResolver` unresolved).

- [ ] **Step 3: AST and parser**

`Ast.kt`: add `val isModule: Boolean = false` to `FormatDecl`; add
```kotlin
/** `import "<path>" as <alias>` — the imported module's structs and dispatch tables are named
 *  `alias:Name`. The alias is a prefix bound to the module's namespace; nothing is copied. */
data class ImportDecl(val path: String, val alias: String, val span: Span)
```
and `val imports: List<ImportDecl> = emptyList()` on `Document`.

`Parser.kt`: in `parse()` add `atText("module") -> format = parseFormat(isModule = true)` and `atText("import") -> imports.add(parseImport())`; give `parseFormat` a parameter `isModule: Boolean = false` passed into `FormatDecl(name, ns, endian, bitOrder, span, isModule = isModule)`. Add:
```kotlin
    private fun parseImport(): ImportDecl {
        val span = next().span // 'import'
        val path = expect(TokKind.STRING).text
        if (!atText("as")) err("import needs an alias: import \"$path\" as <prefix>") else next()
        return ImportDecl(path, expect(TokKind.IDENT).text.trimEnd(':'), span)
    }
```

- [ ] **Step 4: Import resolution**

`hdl/src/main/kotlin/io/hexplain/hdl/imports/ImportResolver.kt`:
```kotlin
package io.hexplain.hdl.imports

import java.nio.file.Files
import java.nio.file.Path

/** Locates the source of an `import "<path>"`. [ImportSource.id] identifies the file for cycle
 *  detection; [ImportSource.resolver] resolves that file's own imports (relative to it). */
fun interface ImportResolver { fun resolve(importPath: String): ImportSource? }

data class ImportSource(val id: String, val text: String, val resolver: ImportResolver)

object NoImports : ImportResolver { override fun resolve(importPath: String): ImportSource? = null }

class FileImportResolver(private val baseDir: Path) : ImportResolver {
    override fun resolve(importPath: String): ImportSource? {
        val p = baseDir.resolve(importPath).normalize()
        if (!Files.isRegularFile(p)) return null
        return ImportSource(p.toAbsolutePath().toString(), Files.readString(p), FileImportResolver(p.toAbsolutePath().parent))
    }
}
```

`HdlCompiler.kt`:
```kotlin
data class ImportedModule(
    val alias: String, val namespace: String, val ontologyIri: String,
    val structUris: Map<String, String>, val dispatchTableUris: Map<String, String>, val result: CompileResult,
)

data class CompileResult(val model: Model, val rootStructUri: String, val diagnostics: List<Diagnostic>,
                         val imports: List<CompileResult> = emptyList()) {
    val ok: Boolean get() = diagnostics.none { it.severity == Severity.ERROR }
    fun toTurtle(): String { … unchanged … }
    /** This document's triples plus every transitive import's: what a loader needs to compile the IR. */
    fun mergedModel(): Model = ModelFactory.createDefaultModel().also { m -> m.add(model); imports.forEach { m.add(it.mergedModel()) } }
}

class HdlCompiler {
    /** A compiled document plus its resolution, so an importer can read the module's minted IRIs
     *  without resolving it a second time. */
    private data class Compiled(val result: CompileResult, val resolved: ResolvedDoc)

    fun compile(source: String, imports: ImportResolver = NoImports): CompileResult {
        val parsed = HdlParser(HdlLexer(source).tokenize()).parse()
        return compileDocument(parsed.document, parsed.diagnostics, imports, emptySet()).result
    }
    fun compileFile(path: java.nio.file.Path): CompileResult {
        val abs = path.toAbsolutePath()
        val parsed = HdlParser(HdlLexer(java.nio.file.Files.readString(abs)).tokenize()).parse()
        return compileDocument(parsed.document, parsed.diagnostics, FileImportResolver(abs.parent), setOf(abs.toString())).result
    }
    fun compileYaml(yaml: String): CompileResult {
        val parsed = io.hexplain.hdl.yaml.YamlLoader().load(yaml)
        return compileDocument(parsed.document, parsed.diagnostics, NoImports, emptySet()).result
    }

    private fun compileDocument(document: Document, parseDiagnostics: List<Diagnostic>, resolver: ImportResolver, inProgress: Set<String>): Compiled {
        val diags = ArrayList<Diagnostic>(parseDiagnostics)
        val imported = LinkedHashMap<String, ImportedModule>()
        val importResults = ArrayList<CompileResult>()
        for (decl in document.imports) {
            val src = resolver.resolve(decl.path)
            if (src == null) { diags.add(Diagnostic(Severity.ERROR, "cannot resolve import '${decl.path}'", decl.span)); continue }
            if (src.id in inProgress) { diags.add(Diagnostic(Severity.ERROR, "import cycle through '${decl.path}'", decl.span)); continue }
            val sub = HdlParser(HdlLexer(src.text).tokenize()).parse()
            val compiled = compileDocument(sub.document, sub.diagnostics, src.resolver, inProgress + src.id)
            for (d in compiled.result.diagnostics) if (d.severity == Severity.ERROR)
                diags.add(Diagnostic(Severity.ERROR, "in import '${decl.path}': ${d.message}", decl.span))
            importResults.add(compiled.result)
            imported[decl.alias] = ImportedModule(
                alias = decl.alias, namespace = compiled.resolved.baseNs,
                ontologyIri = compiled.resolved.baseNs.trimEnd('#', '/'),
                structUris = compiled.resolved.structs.associate { it.decl.name to it.uri },
                dispatchTableUris = compiled.resolved.dispatchTables, result = compiled.result,
            )
        }
        val resolved = Resolver().resolve(document, imported)
        diags.addAll(resolved.diagnostics)
        validateExpressions(resolved, diags); validateEnumeratedValues(resolved, diags)
        validateSwitchDiscriminators(resolved, diags); validateBundlesAndAssets(resolved, diags)
        val model = TurtleEmitter(resolved).emit()
        return Compiled(CompileResult(model, resolved.rootStructUri, diags, importResults), resolved)
    }
}
```

- [ ] **Step 5: Resolver**

`Resolver.resolve(doc: Document, imports: Map<String, ImportedModule> = emptyMap())`:
- after `for (p in doc.prefixes) prefixes[p.prefix] = p.iri`: for each import, `if (prefixes.containsKey(alias) && prefixes[alias] != module.namespace) diags ERROR "import alias '$alias' collides with a 'use' prefix"`; then `prefixes[alias] = module.namespace`.
- the "format has no struct" error: add `&& doc.format?.isModule != true`.
- pass `imports = imports` to `ResolvedDoc`, which gains:
```kotlin
    val imports: Map<String, ImportedModule> = emptyMap()
    private fun split(curie: String): Pair<String, String>? = curie.indexOf(':').takeIf { it > 0 }?.let { curie.substring(0, it) to curie.substring(it + 1) }
    fun importedStructUri(curie: String): String? = split(curie)?.let { (p, l) -> imports[p]?.structUris?.get(l) }
    fun importedTableUri(curie: String): String? = split(curie)?.let { (p, l) -> imports[p]?.dispatchTableUris?.get(l) }
    /** True when [curie]'s prefix is an import alias (so an unknown local name is an error, not a custom datatype). */
    fun isImportRef(curie: String): Boolean = split(curie)?.let { imports.containsKey(it.first) } ?: false
```
(`ImportedModule` lives in `io.hexplain.hdl.HdlCompiler.kt`; import it. If that creates a package cycle you dislike, move `ImportedModule` to `io.hexplain.hdl.imports`.)
- In `validateTypeReferences`, extend `check` to handle CURIEs: pass `imports` in, and
```kotlin
        fun check(ref: String, kind: String, span: Span) {
            if (ref.contains(':')) {
                val prefix = ref.substringBefore(':'); val module = imports[prefix] ?: return   // a `use` prefix: custom datatype, not ours to check
                if (ref.substringAfter(':') !in module.structUris)
                    diags.add(Diagnostic(Severity.ERROR, "$kind '$ref'$where names no struct of module '$prefix'" +
                        (nearest(ref.substringAfter(':'), module.structUris.keys)?.let { "; did you mean '$prefix:$it'?" } ?: ""), span))
                return
            }
            if (ref in declared) return
            …existing…
        }
```
and also check `DataTypeRef` field types through it: `(f.type as? DataTypeRef)?.let { check(it.curie, "unknown type", f.span) }`; drop the `if (!it.struct.contains(':'))` guards added in Task 8 so CURIE arms/defaults go through `check` too.
- Extensions: `x.table.contains(':')` → require `importedTableUri(x.table) != null` else ERROR `unknown dispatch table '${x.table}'`.

- [ ] **Step 6: Emitter**

- `structUri(ref)`: `doc.structs.firstOrNull { it.decl.name == ref }?.uri ?: doc.importedStructUri(ref) ?: if (ref.contains(':')) doc.expandCurie(ref) else doc.baseNs + ref`.
- `tableUri(ref)`: `doc.dispatchTables[ref] ?: doc.importedTableUri(ref) ?: …`.
- `emitField` `is DataTypeRef` branch: `f.addProperty(BDDO.dataType, m.createResource(doc.importedStructUri(t.curie) ?: doc.expandCurie(t.curie)))`.
- In `emit()`, before the struct loop:
```kotlin
        if (doc.imports.isNotEmpty() || doc.isModule) {
            val ontology = m.createResource(doc.baseNs.trimEnd('#', '/')).addProperty(RDF.type, OWL.Ontology)
            for (imp in doc.imports.values) ontology.addProperty(OWL.imports, m.createResource(imp.ontologyIri))
        }
```
(`ResolvedDoc` gets `val isModule: Boolean = false` from `doc.format?.isModule == true`; `m.setNsPrefix("owl", OWL.getURI())`.)

- [ ] **Step 7: CLI**

`Main.kt`: for a `.hx` input use `HdlCompiler().compileFile(java.nio.file.Path.of(input))`; YAML unchanged (YAML has no `imports:` key yet — document in Task 12).

- [ ] **Step 8: Run the test and the whole hdl suite**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test`
Expected: PASS. The golden snapshots (`png`, `tiff`, `shapefile`) must be unchanged — no ontology header is emitted for a plain `format` without imports.

- [ ] **Step 9: Commit**

```bash
cd /d/work/hexplain-tools && git add hdl/src/main/kotlin/io/hexplain/hdl hdl/src/test/kotlin/io/hexplain/hdl/imports/ImportTest.kt && git commit -m "feat(hdl): modules and import — cross-module struct and dispatch-table references by IRI, owl:imports

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: M3 — split into modules; HEIF, codec and leaf profiles; import-aware library gate

**Files:**
- Create (tools test resources, then copied to the library): `hdl/src/test/resources/profiles/iso-bmff/iso-bmff.hx`, `profiles/heif/heif.hx`, `profiles/codec-hevc/codec-hevc.hx`, `profiles/codec-av1/codec-av1.hx`, `profiles/heic/heic.hx`, `profiles/avif/avif.hx`
- Delete: `hdl/src/test/resources/profiles/isobmff/` and `hexplain-profiles/profiles/isobmff/` (renamed to `iso-bmff`, now a module)
- Create: `hdl/src/test/kotlin/io/hexplain/hdl/parity/HeifModulesParityTest.kt`; modify `IsobmffParityTest` to compile `iso-bmff/iso-bmff.hx` via `compileFile`
- Modify: `d:/work/hexplain-profiles/tools/test_profile_library.py`, `README.md`

**Interfaces:**
- Consumes `HdlCompiler.compileFile`, `CompileResult.mergedModel` (Task 10).
- Produces namespaces `https://hexplain.io/ns/profile/iso-bmff#`, `…/profile/heif#`, `…/profile/codec/hevc#`, `…/profile/codec/av1#`, `…/profile/heic#`, `…/profile/avif#`; roots `heic:HeicFile`, `avif:AvifFile`, `iso:File`.

- [ ] **Step 1: Write the failing modules parity test**

```kotlin
package io.hexplain.hdl.parity

import io.hexplain.core.metacodec.Metaparser
import io.hexplain.core.rdf.RdfToIrCompiler
import io.hexplain.hdl.HdlCompiler
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.nio.file.Paths

/** The split modules, compiled through `import`, parse the same files and now yield property values. */
class HeifModulesParityTest {
    private fun res(name: String) = this::class.java.classLoader.getResourceAsStream(name) ?: error("missing resource $name")
    private fun n(v: Any?) = (v as Number).toLong()
    private fun payload(box: Map<*, *>) = box["payload"] as Map<*, *>
    private fun children(box: Map<*, *>) = (payload(box)["children"] as List<*>).map { it as Map<*, *> }
    private fun child(box: Map<*, *>, type: String) = children(box).first { it["type"] == type }

    private fun parse(profile: String, root: String, file: String): List<Map<*, *>> {
        val r = HdlCompiler().compileFile(Paths.get("src/test/resources/profiles/$profile/$profile.hx"))
        assertTrue(r.ok, "compile diagnostics: ${r.diagnostics}")
        val ir = RdfToIrCompiler(r.mergedModel()).compile(root)
        val out = Metaparser(ir).parse(res(file).readBytes()) as Map<*, *>
        return (out["boxes"] as List<*>).map { it as Map<*, *> }
    }

    @Test fun `heic profile parses image properties and the HEVC configuration`() {
        val top = parse("heic", "https://hexplain.io/ns/profile/heic#HeicFile", "heif/example.heic")
        val ipco = children(child(child(top[1], "iprp"), "ipco"))
        val ispe = ipco.filter { it["type"] == "ispe" }.map { payload(it) }
        assertEquals(listOf(1280L to 854L, 320L to 212L), ispe.map { n(it["width"]) to n(it["height"]) })
        val hvcc = payload(ipco.first { it["type"] == "hvcC" })["record"] as Map<*, *>
        assertEquals(1L, n(hvcc["configurationVersion"]))
        assertEquals(1L, n(hvcc["generalProfileIdc"]))
        assertEquals(120L, n(hvcc["generalLevelIdc"]))
        assertEquals(1L, n(hvcc["chromaFormat"]))
        assertEquals(3L, n(hvcc["lengthSizeMinusOne"]))
        val arrays = (hvcc["arrays"] as List<*>).map { it as Map<*, *> }
        assertEquals(listOf(32L, 33L, 34L), arrays.map { n(it["nalUnitType"]) })
        assertEquals(listOf(25, 48, 7), arrays.map { ((it["nalus"] as List<*>).single() as Map<*, *>)["nalUnit"].let { u -> (u as ByteArray).size } })
    }

    @Test fun `avif profile parses colr, av1C and ispe`() {
        val top = parse("avif", "https://hexplain.io/ns/profile/avif#AvifFile", "heif/example.avif")
        val ipco = children(child(child(top[1], "iprp"), "ipco"))
        val colr = payload(ipco.first { it["type"] == "colr" })
        assertEquals("nclx", colr["colourType"])
        val nclx = colr["body"] as Map<*, *>
        assertEquals(listOf(2L, 2L, 6L, 1L), listOf("colourPrimaries", "transferCharacteristics", "matrixCoefficients", "fullRangeFlag").map { n(nclx[it]) })
        val av1c = payload(ipco.first { it["type"] == "av1C" })
        assertEquals(listOf(1L, 1L, 0L, 13L, 1L, 1L), listOf("marker", "version", "seqProfile", "seqLevelIdx0", "chromaSubsamplingX", "chromaSubsamplingY").map { n(av1c[it]) })
        val ispe = payload(ipco.first { it["type"] == "ispe" })
        assertEquals(800L to 533L, n(ispe["width"]) to n(ispe["height"]))
    }

    @Test fun `the base module alone still walks both files`() {
        assertEquals(7, parse("iso-bmff", "https://hexplain.io/ns/profile/iso-bmff#File", "heif/example.heic").size)
        assertEquals(3, parse("iso-bmff", "https://hexplain.io/ns/profile/iso-bmff#File", "heif/example.avif").size)
    }
}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.parity.HeifModulesParityTest"`
Expected: FAIL — `NoSuchFileException` for `profiles/heic/heic.hx`.

- [ ] **Step 3: Rename the base to a module**

```bash
cd /d/work/hexplain-tools/hdl/src/test/resources/profiles && git mv isobmff iso-bmff && git mv iso-bmff/isobmff.hx iso-bmff/iso-bmff.hx
```
Edit its header: `format isobmff @namespace "https://hexplain.io/ns/profile/isobmff#" @endian big` → `module isobmff @namespace "https://hexplain.io/ns/profile/iso-bmff#" @endian big`, and the first comment line to `// Hexplain Profile module — ISO base media file format (ISO/IEC 14496-12)`. Update `IsobmffParityTest.formatIR()` to `HdlCompiler().compileFile(java.nio.file.Paths.get("src/test/resources/profiles/iso-bmff/iso-bmff.hx"))` (the Gradle test working directory is the `hdl/` module directory), use `r.mergedModel()` in place of `ProfileLoader().loadFromString(r.toTurtle())`, and change the root IRI to `https://hexplain.io/ns/profile/iso-bmff#File`.

- [ ] **Step 4: Write the HEIF module**

`hdl/src/test/resources/profiles/heif/heif.hx`:
```
// Hexplain Profile module — HEIF image item properties (ISO/IEC 23008-12)
//
// Everything structural is inherited from iso-bmff: the box, the meta box, items, locations,
// references and property associations are ISO/IEC 14496-12. This module adds the LEAF boxes
// that give an image item its meaning, by contributing arms to the base dispatch table.
// Codec configurations (hvcC, av1C, …) are NOT here: a configuration record is shared with
// video tracks and belongs to a codec module, which is what lets AVIF import this module
// without dragging HEVC in.
//
// Source: ISO/IEC 23008-12:2022, clause 6.5 (image item properties).
// Verification status: parse-verified through heic and avif (hexplain-tools HeifModulesParityTest).

module heif @namespace "https://hexplain.io/ns/profile/heif#" @endian big
import "../iso-bmff/iso-bmff.hx" as iso

extend dispatch iso:BoxPayload {
  "ispe" => ImageSpatialExtents
  "pixi" => PixelInformation
  "irot" => ImageRotation
  "imir" => ImageMirror
  "clap" => CleanAperture
  "pasp" => PixelAspectRatio
  "colr" => ColourInformation
  "auxC" => AuxiliaryType
}

struct ImageSpatialExtents @label "ispe — image spatial extents" {
  hdr    : iso:FullBoxHeader
  width  : u32
  height : u32
}

struct PixelInformation @label "pixi — bits per channel" {
  hdr          : iso:FullBoxHeader
  channelCount : u8
  channels     : ChannelDepth repeat channelCount
}
struct ChannelDepth { bitsPerChannel : u8 }

struct ImageRotation @label "irot — rotation (angle × 90° anticlockwise)" {
  reserved : bits[6]
  angle    : bits[2]
}

struct ImageMirror @label "imir — mirror axis" {
  reserved : bits[7]
  axis     : bits[1]
}

struct CleanAperture @label "clap — clean aperture (four rationals)" {
  widthN : u32   widthD : u32
  heightN : u32  heightD : u32
  horizOffN : u32  horizOffD : u32
  vertOffN : u32   vertOffD : u32
}

struct PixelAspectRatio @label "pasp — pixel aspect ratio" {
  hSpacing : u32
  vSpacing : u32
}

struct ColourInformation @label "colr — colour information" {
  colourType : ascii[4]
  body       : bytes[..] switch colourType {
    "nclx" => NclxColour
    "rICC" => IccProfile
    "prof" => IccProfile
  }
}
struct NclxColour @label "CICP colour description (ISO/IEC 23091-2 code points)" {
  colourPrimaries         : u16
  transferCharacteristics : u16
  matrixCoefficients      : u16
  fullRangeFlag           : bits[1]
  reserved                : bits[7]
}
struct IccProfile { profile : bytes[..] }

struct AuxiliaryType @label "auxC — auxiliary image type" {
  hdr        : iso:FullBoxHeader
  auxType    : str @terminator 0x00
  auxSubtype : bytes[..]
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. Derived items (grid, iovl, iden, tili) and their payloads are not described yet.
// 2. HDR metadata (clli, mdcv, amve), camera (cmin, cmex) and timing (taic, itai) properties
//    are opaque bytes.
// 3. Which property belongs to which item is a join through ipma; that resolution (design G4)
//    is not expressed here, so ispe.width is a fact about a property box, not yet about an image.
```

- [ ] **Step 5: Write the codec modules and the leaf profiles**

`profiles/codec-hevc/codec-hevc.hx`:
```
// Hexplain Profile module — HEVC decoder configuration record (ISO/IEC 14496-15, clause 8.3.3)
// Shared by HEIC image items and HEVC video tracks, so it imports only the base module.
// Verification status: parse-verified through heic (hexplain-tools HeifModulesParityTest).

module codec_hevc @namespace "https://hexplain.io/ns/profile/codec/hevc#" @endian big
import "../iso-bmff/iso-bmff.hx" as iso

extend dispatch iso:BoxPayload { "hvcC" => HevcConfigurationBox }

struct HevcConfigurationBox @label "hvcC" { record : HevcDecoderConfigurationRecord }

struct HevcDecoderConfigurationRecord {
  configurationVersion             : u8
  generalProfileSpace              : bits[2]
  generalTierFlag                  : bits[1]
  generalProfileIdc                : bits[5]
  generalProfileCompatibilityFlags : u32
  generalConstraintIndicatorFlags  : bytes[6]
  generalLevelIdc                  : u8
  reserved1                        : bits[4]
  minSpatialSegmentationIdc        : bits[12]
  reserved2                        : bits[6]
  parallelismType                  : bits[2]
  reserved3                        : bits[6]
  chromaFormat                     : bits[2]
  reserved4                        : bits[5]
  bitDepthLumaMinus8               : bits[3]
  reserved5                        : bits[5]
  bitDepthChromaMinus8             : bits[3]
  avgFrameRate                     : u16
  constantFrameRate                : bits[2]
  numTemporalLayers                : bits[3]
  temporalIdNested                 : bits[1]
  lengthSizeMinusOne               : bits[2]
  numOfArrays                      : u8
  arrays                           : HevcNalArray repeat numOfArrays
}
struct HevcNalArray {
  arrayCompleteness : bits[1]
  reserved          : bits[1]
  nalUnitType       : bits[6]
  numNalus          : u16
  nalus             : HevcNalUnit repeat numNalus
}
struct HevcNalUnit {
  nalUnitLength : u16
  nalUnit       : bytes[nalUnitLength]
}
// LIMITS: the parameter sets are carried as bytes; the HEVC bitstream itself is a named codec
// primitive (menc:HEVC), never described.
```

`profiles/codec-av1/codec-av1.hx`:
```
// Hexplain Profile module — AV1 codec configuration record (AV1 ISOBMFF binding, clause 2.3)
// Verification status: parse-verified through avif (hexplain-tools HeifModulesParityTest).

module codec_av1 @namespace "https://hexplain.io/ns/profile/codec/av1#" @endian big
import "../iso-bmff/iso-bmff.hx" as iso

extend dispatch iso:BoxPayload { "av1C" => Av1ConfigurationBox }

struct Av1ConfigurationBox @label "av1C" {
  marker                            : bits[1]
  version                           : bits[7]
  seqProfile                        : bits[3]
  seqLevelIdx0                      : bits[5]
  seqTier0                          : bits[1]
  highBitdepth                      : bits[1]
  twelveBit                         : bits[1]
  monochrome                        : bits[1]
  chromaSubsamplingX                : bits[1]
  chromaSubsamplingY                : bits[1]
  chromaSamplePosition              : bits[2]
  reserved                          : bits[3]
  initialPresentationDelayPresent   : bits[1]
  initialPresentationDelayMinusOne  : bits[4]
  configOBUs                        : bytes[..]
}
```

`profiles/heic/heic.hx`:
```
// Hexplain Profile — HEIC (HEVC-coded HEIF still image; brands heic/heix/mif1)
// Everything is inherited: the base container, the HEIF properties, the HEVC configuration.
// Verification status: parse-verified against libheif examples/example.heic.

format heic @namespace "https://hexplain.io/ns/profile/heic#" @endian big
import "../iso-bmff/iso-bmff.hx" as iso
import "../heif/heif.hx" as heif
import "../codec-hevc/codec-hevc.hx" as hevc

@root struct HeicFile @label "HEIC file" { boxes : iso:Box repeat until eof() }

// LIMITS: brand conformance (ftyp must list heic/heix and mif1) is not yet a checkable rule;
// see the design's §7 for the req/conf plan.
```

`profiles/avif/avif.hx`:
```
// Hexplain Profile — AVIF (AV1-coded HEIF still image; brands avif/avis/mif1)
// Verification status: parse-verified against libheif examples/example.avif.

format avif @namespace "https://hexplain.io/ns/profile/avif#" @endian big
import "../iso-bmff/iso-bmff.hx" as iso
import "../heif/heif.hx" as heif
import "../codec-av1/codec-av1.hx" as av1

@root struct AvifFile @label "AVIF file" { boxes : iso:Box repeat until eof() }
```

- [ ] **Step 6: Run both parity tests until green**

Run: `cd /d/work/hexplain-tools && ./gradlew -q --offline :hdl:test --tests "io.hexplain.hdl.parity.*"`
Expected: PASS. If `heif.hx` fails to compile with "unknown dispatch table 'iso:BoxPayload'", the imported module's `dispatchTableUris` is empty — check that `ResolvedDoc.dispatchTables` is populated in the Resolver before it is read in `HdlCompiler`. If two imports of `iso-bmff` (direct, and through `heif`) produce a duplicate-key diagnostic, keys must be de-duplicated per *table IRI* in `RdfToIrCompiler` only when the arms are the same blank node — they are not, so this cannot happen: arms are emitted once per declaring document, and the merged model contains each document once (`mergedModel` must `add` each import result exactly once — de-duplicate by `rootStructUri`/namespace if a diamond import appears: keep a `HashSet<String>` of namespaces already merged).

- [ ] **Step 7: Move to the profile library and make its gate import-aware**

```bash
cd /d/work/hexplain-profiles && git rm -r -q profiles/isobmff && for p in iso-bmff heif codec-hevc codec-av1 heic avif; do mkdir -p profiles/$p && cp /d/work/hexplain-tools/hdl/src/test/resources/profiles/$p/$p.hx profiles/$p/$p.hx; done && cd /d/work/hexplain-tools && for p in iso-bmff heif codec-hevc codec-av1 heic avif; do ./gradlew -q --offline :hdl:run --args="/d/work/hexplain-profiles/profiles/$p/$p.hx -o /d/work/hexplain-profiles/profiles/$p/$p.ttl"; done
```

In `tools/test_profile_library.py` add, after `messages()`:
```python
def ontology_index(profile_dirs):
    """ontology IRI -> the .ttl files of the directory that declares it, for owl:imports."""
    from rdflib import OWL, RDF
    index = {}
    for d in profile_dirs:
        unit = [f for f in sorted(glob.glob(f"{d}/**/*.ttl", recursive=True)) if not f.endswith("-invalid.ttl")]
        for f in unit:
            g = specgraph.load([f])
            for iri in g.subjects(RDF.type, OWL.Ontology):
                index[str(iri)] = unit
    return index


def with_imports(files, index):
    """`files` plus, transitively, every profile directory their owl:imports name."""
    from rdflib import OWL
    out, seen = list(files), set(files)
    queue = list(files)
    while queue:
        g = specgraph.load([queue.pop()])
        for target in g.objects(None, OWL.imports):
            for f in index.get(str(target), []):
                if f not in seen:
                    seen.add(f); out.append(f); queue.append(f)
    return out
```
In `main()`, compute `index = ontology_index(dirs)` before the loop; validate a compiled `.hx` with `g = specgraph.load(ontologies + with_imports([str(out)], index))` (note `out` is the temp `.ttl` written by the compiler — `with_imports` reads it for its `owl:imports`); validate the directory unit with `specgraph.load(ontologies + with_imports(unit, index))` and each `-invalid` fixture with `with_imports(unit, index) + [bad]`. Update the module docstring's bullet list with: "a directory whose Turtle `owl:imports` another profile's ontology is validated together with that profile's Turtle, transitively — a HEIF module references structs and a dispatch table the base module declares".

Update `README.md` §Layout to:
```
profiles/<module>/
    <module>.hx      the description (preferred) — a `format` (a file format) or a `module` (a reusable block other profiles import)
    <module>.ttl     compiled or hand-written Turtle
    example.ttl      a worked instance, optional
    *-invalid.ttl    a fixture that MUST NOT conform, optional
```
and add a paragraph under "What a profile claims":
"A `module` is not a format anyone opens; it is a block other profiles `import`. `iso-bmff` (ISO/IEC 14496-12 boxes and items) is imported by `heif`, `codec-hevc`, `codec-av1`, and by the leaf formats `heic` and `avif`, each of which is a handful of lines. The gate validates a directory together with the directories it imports."

- [ ] **Step 8: Run the library gates**

Run: `cd /d/work/hexplain-profiles && python tools/run_gates.py`
Expected: all PASS — `test_profile_library` reports 12 profiles compiled/conforming; `test_tools_fixtures` reports 6 fixtures matching.

- [ ] **Step 9: Commit both repos**

```bash
cd /d/work/hexplain-tools && git add -A hdl/src/test/resources/profiles hdl/src/test/kotlin/io/hexplain/hdl/parity && git commit -m "feat(profiles): split ISO BMFF into a module; HEIF, HEVC and AV1 modules; HEIC and AVIF leaf profiles, parse-verified

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
cd /d/work/hexplain-profiles && git add -A profiles tools/test_profile_library.py README.md && git commit -m "feat: modular ISO BMFF / HEIF / codec / HEIC / AVIF profiles; import-aware validation

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: Documentation, design-doc corrections, final gate runs, stash restore

**Files:**
- Modify: `d:/work/hexplain.io/specification/hdl/index.html` (keywords line ~103; grammar `<pre class="abnf">` ~line 545; new section before `<section id="conformance-section">`)
- Modify: `d:/work/hexplain.io/docs/superpowers/specs/2026-09-06-heif-isobmff-profile-design.html` (§4.1 `+ 8` → `+ 4`; G3 proposal; G1 lowering; status panel)

- [ ] **Step 1: HDL specification**

Keywords line: append ` module import extend dispatch on default` to the keyword list. Grammar: add
```
document     = *( use-decl / import-decl / format-decl / module-decl / struct-decl / field-decl
                / bundle-decl / asset-decl / extend-decl )
module-decl  = "module" IDENT *( "@namespace" STRING / "@endian" endian / "@bit-order" bitorder )
import-decl  = "import" STRING "as" IDENT
extend-decl  = "extend" "dispatch" table-ref "{" *disparm "}"
disparm      = ( STRING / INT ) "=&gt;" struct-ref
```
and to `clause`: `/ "dispatch" IDENT "on" expr [ "default" struct-ref ] "{" *disparm "}"` and `/ "@seek" ( "stream" / "region" )`; note under the grammar: `struct-ref` and `table-ref` are a bare name or `alias:Name` where `alias` is an import alias.

New section (before the Conformance section):
```html
    <section id="modules">
        <h2>Modules, imports and keyed dispatch</h2>
        <p>A <code>module</code> is a format description that is not a file format: it declares a namespace and structs for other descriptions to <code>import</code>. An <code>import "&lt;path&gt;" as &lt;alias&gt;</code> binds the alias as a prefix to the module's namespace; the imported module is compiled, not copied, and the importing document's ontology carries <code>owl:imports</code> for it. <code>alias:Name</code> then names an imported struct in any type position and an imported dispatch table in <code>extend dispatch</code>. Nothing of the imported module is re-emitted, so a fix to the base is a fix for every importer.</p>
        <pre>
module isobmff @namespace "https://hexplain.io/ns/profile/iso-bmff#" @endian big
struct Box @size `instance.size == 1 ? instance.largesize : (instance.size == 0 ? stream.remaining + 4 : instance.size)` {
  size    : u32
  type    : ascii[4]
  payload : bytes[..] dispatch BoxPayload on type { "ftyp" =&gt; FileTypeBox  "meta" =&gt; MetaBox }
}

module heif @namespace "https://hexplain.io/ns/profile/heif#"
import "../iso-bmff/iso-bmff.hx" as iso
extend dispatch iso:BoxPayload { "ispe" =&gt; ImageSpatialExtents }
struct ImageSpatialExtents { hdr : iso:FullBoxHeader  width : u32  height : u32 }</pre>
        <p><b>Keyed dispatch.</b> <code>dispatch &lt;Name&gt; on &lt;expr&gt; [default &lt;Struct&gt;] { &lt;key&gt; =&gt; &lt;Struct&gt; … }</code> lowers to a named <code>bddo:DispatchTable</code> whose arms are independent <code>bddo:DispatchArm</code> resources (<code>bddo:armTable</code>, <code>bddo:armKey</code>, <code>bddo:armDataType</code>). A lone sibling in <code>on</code> becomes <code>bddo:dispatchOnField</code>; any other expression becomes <code>bddo:dispatchOnExpression</code>, resolved like a <code>switch</code> condition. Keys are string or integer literals, unique per table across the declaring document and every extension; the compiler reports a duplicate. <code>switch</code> remains the form for ordered, possibly overlapping guards; a field uses one or the other. <code>extend dispatch</code> at top level contributes arms to a table declared in this document or in an imported module — the mechanism for open type registries.</p>
        <p><b>Seek scope.</b> <code>@seek stream</code> on an offset-addressed field (<code>bddo:seekScope bddo:streamScope</code>) lets that one read leave the innermost bounded region; the default <code>@seek region</code> keeps the Processing Model's containment rule. An item-location table inside a <code>meta</code> box that points into <code>mdat</code> is the motivating case.</p>
        <p>The YAML surface has no <code>imports:</code> key yet; a document that imports must use the text surface.</p>
    </section>
```

- [ ] **Step 2: Design document corrections**

In the design HTML: §4.1 — replace `stream.remaining + 8` with `stream.remaining + 4` in the code block and change the "Rough edge" paragraph's `+ 8` to `+ 4` ("only the four size bytes have been consumed when the expression first resolves"). In G3's proposal table add a row `<b>G3c. Pointer read at the extent</b> <span class="badge new">implemented</span>` — "the extent's offset and length are parsed in <code>iloc</code>; a stream-scoped pointer read (<code>bddo:seekScope</code>) fetches the bytes right there. No extent table, no iteration variable, no <code>LayoutExecutor</code> dependency. Construction methods 1 and 2 stay out of scope." In G1's verdict column, mark option B as implemented and A as not needed. Add a `<div class="callout good">` at the top of §5 stating: "Implemented 2026-09: G1 (modules/import), G2 (dispatch tables), G3 (as G3c) — see `docs/superpowers/plans/2026-09-06-heif-isobmff-profile.md`. G4 is open."

- [ ] **Step 3: Final gate runs, all three repos**

```bash
cd /d/work/hexplain.io && python tools/run_gates.py
cd /d/work/hexplain-tools && ./gradlew -q --offline :core:test :hdl:test
cd /d/work/hexplain-profiles && python tools/run_gates.py
```
Expected: 27/27 spec gates; all Gradle tests green; all library gates PASS.

- [ ] **Step 4: Commit the docs**

```bash
cd /d/work/hexplain.io && git add specification/hdl/index.html docs/superpowers/specs/2026-09-06-heif-isobmff-profile-design.html docs/superpowers/plans/2026-09-06-heif-isobmff-profile.md && git commit -m "docs(hdl): modules, imports, keyed dispatch and seek scope; record the HEIF plan's deviations in the design

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 5: Restore the user's stashed work**

Do this only after every commit above is in place, and report the outcome verbatim:
```bash
cd /d/work/hexplain-tools && git switch hardening/observability-and-engine-fixes && git stash pop && git status --short | head
cd /d/work/hexplain.io && git switch main && git stash pop && git status --short | head
```
If `stash pop` reports conflicts (expected candidates: `core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt` in tools; the regenerated `specification/reference/index.html` and `manifest.json` in the spec — both generated, so the resolution there is to take either side and rerun `python tools/_build_term_reference.py`), leave the conflict markers in place, do not resolve them unilaterally, and tell the user which files conflict and that `git checkout --theirs`/`--ours` plus a re-run of the affected tests is the resolution path. The feature branches remain intact either way.
