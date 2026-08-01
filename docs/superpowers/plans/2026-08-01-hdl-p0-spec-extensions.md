# HDL P0 Specification Extensions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the four P0 proposals from [the GDAL survey improvements note](../notes/2026-08-01-spec-improvements-from-gdal-survey.md) in the Hexplain specification — ASCII-numeric datatypes, data-dependent endianness, chunked data layout, and a delimited-record primitive.

**Architecture:** Purely additive vocabulary changes to BDDO and DLV, each paired with SHACL shapes and a valid/invalid fixture pair. Two infrastructure tasks come first: a gate that keeps each module's `index.html` in sync with its `.ttl`, and a generic fixture runner so every later task is pure TDD. HEL gains three string functions and one clarified coercion rule. The HDL design doc gains the matching authoring surface.

**Tech Stack:** Turtle/OWL, SHACL (incl. SPARQL constraints), ReSpec HTML, Python 3.11 with `rdflib` 7.1.1 and `pyshacl` 0.30.1 (both already installed).

## Global Constraints

- Branch: `feat/hdl-p0-spec-extensions` (already created off `feat/hx-bundle`).
- **All changes are additive.** No existing IRI changes meaning, cardinality, or range. Existing profiles (`specification/profiles/nitf`, `.../shapefile`) must keep validating unchanged.
- **Every `.ttl` edit must be mirrored into that module's `index.html`.** The `<pre class="nohighlight">` blocks in `specification/<mod>/index.html` contain a complete, HTML-escaped copy of `specification/<mod>/<mod>.ttl`. Escape `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. Task 1 adds a gate that enforces this.
- Modeling convention (stated at the top of `bddo.ttl`): properties declare `rdfs:range` only. **Never add `rdfs:domain`.** Domain and cardinality live in SHACL.
- Vocabulary version stays `1.0` — these modules are pre-release. Do not bump `owl:versionIRI`.
- Run all commands from the repo root `d:\work\hexplain.io`.
- Full regression suite (all four must pass before every commit):
  ```
  python tools/validate_all.py
  python tools/test_shapes.py
  python tools/test_conformance.py
  python tools/test_lift.py
  ```

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `tools/test_html_sync.py` | **New.** Gate: each `<mod>/index.html` embeds a graph isomorphic to `<mod>.ttl` | 1 |
| `tools/test_vocab_shapes.py` | **New.** Gate: every `specification/*/test/*-valid.ttl` conforms, every `*-invalid.ttl` does not | 2 |
| `specification/bddo/bddo.ttl` | ASCII-numeric types, conditional endianness, delimited records | 3, 4, 6 |
| `specification/bddo/index.html` | Mirror of the above + prose + JSON-LD context | 3, 4, 6 |
| `specification/bddo/test/*.ttl` | Fixture pairs for the three BDDO features | 3, 4, 6 |
| `specification/dlv/dlv.ttl` | Chunked layout | 1, 5 |
| `specification/dlv/index.html` | Mirror + prose + JSON-LD context | 1, 5 |
| `specification/dlv/test/*.ttl` | Fixture pair for chunked layout | 5 |
| `specification/hel/index.html` | String functions, string context, datatype-to-HEL-type rule | 3, 7 |
| `docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md` | HDL authoring surface (§6.1, §6.2, §9, §13) | 3, 4, 5, 6 |

**Fixture convention (established by Task 2):** `specification/<mod>/test/<feature>-valid.ttl` and `<feature>-invalid.ttl`. Both must *parse* (they are picked up by `validate_all.py`); only the `-invalid` one must fail SHACL. Each `-invalid.ttl` carries an `rdfs:comment` naming the shape it is expected to trip.

---

### Task 1: TTL ↔ index.html sync gate

The specification ships each vocabulary twice — once as `.ttl`, once embedded in `index.html`. They have already drifted: `dlv.ttl` gives `dlv:dimensionStride` an `rdfs:comment` that `dlv/index.html` lacks. Every later task edits both files, so lock this down first.

**Files:**
- Create: `tools/test_html_sync.py`
- Modify: `specification/dlv/index.html` (fix the existing drift)

**Interfaces:**
- Produces: a suite command `python tools/test_html_sync.py` that later tasks run before every commit.

- [ ] **Step 1: Write the failing test**

Create `tools/test_html_sync.py`:

```python
"""Each specification module ships its vocabulary twice: as <mod>/<mod>.ttl and
embedded (HTML-escaped) in <mod>/index.html. This gate parses both and compares
them as RDF graphs, so formatting differs freely but triples may not.
"""
import html
import pathlib
import re
import sys

import rdflib
from rdflib.compare import graph_diff, to_isomorphic

MODULES = ["bddo", "dlv"]
# Only the normative sections are the vocabulary's second copy. Non-normative
# example blocks are valid Turtle too, but they are meant to differ from the
# .ttl, so comparing them would be measuring the wrong thing.
NORMATIVE_SECTIONS = ("normative-owl", "normative-shacl")
PRE = re.compile(r'<pre class="nohighlight">(.*?)</pre>', re.S)


def _section(text, section_id):
    """The inner HTML of <section id="..."> ... </section>, or "" if absent."""
    m = re.search(rf'<section id="{section_id}">(.*?)</section>', text, re.S)
    return m.group(1) if m else ""


def embedded_graph(doc_path):
    """Parse the Turtle embedded in the page's normative sections."""
    text = doc_path.read_text(encoding="utf-8")
    g = rdflib.Graph()
    for section_id in NORMATIVE_SECTIONS:
        for block in PRE.findall(_section(text, section_id)):
            g.parse(data=html.unescape(block), format="turtle")
    return g


failures = []
for mod in MODULES:
    ttl_path = pathlib.Path(f"specification/{mod}/{mod}.ttl")
    doc_path = pathlib.Path(f"specification/{mod}/index.html")
    if not ttl_path.exists() or not doc_path.exists():
        failures.append(f"{mod}: missing {ttl_path} or {doc_path}")
        continue
    canonical = to_isomorphic(rdflib.Graph().parse(ttl_path, format="turtle"))
    embedded = to_isomorphic(embedded_graph(doc_path))
    if canonical == embedded:
        continue
    _, only_ttl, only_html = graph_diff(canonical, embedded)
    lines = [f"{mod}: index.html does not match {mod}.ttl"]
    for s, p, o in sorted(only_ttl, key=str)[:10]:
        lines.append(f"    in .ttl only : {s} {p} {o}")
    for s, p, o in sorted(only_html, key=str)[:10]:
        lines.append(f"    in .html only: {s} {p} {o}")
    failures.append("\n".join(lines))

if failures:
    print("FAIL:\n" + "\n\n".join(failures))
    sys.exit(1)
print(f"PASS: {len(MODULES)} modules' index.html match their .ttl")
```

Only the normative sections are compared — the pages also carry non-normative example Turtle that is meant to differ from the .ttl.

- [ ] **Step 2: Run it and watch it fail on the known dlv drift**

Run: `python tools/test_html_sync.py`
Expected: FAIL, reporting `dlv: index.html does not match dlv.ttl` with an `in .ttl only` line for the `dimensionStride` `rdfs:comment`.

> If `bddo` also reports a difference, that is additional pre-existing drift. Fix `bddo/index.html` the same way as Step 3 — copy the authoritative text from `bddo.ttl`, HTML-escaping `&`, `<`, `>`. The `.ttl` is always the source of truth.

- [ ] **Step 3: Fix the dlv drift**

In `specification/dlv/index.html`, find the embedded `:dimensionStride` line (around line 118) and replace it with the full text from `dlv.ttl:33-34`, HTML-escaped:

```
:dimensionStride a owl:DatatypeProperty ; rdfs:label "dimension stride" ; rdfs:range xsd:positiveInteger ; rdfs:isDefinedBy &lt;https://hexplain.io/ns/dlv&gt; ;
    rdfs:comment "Bytes to advance per step along this dimension (pitch). When absent, addressing is contiguous (stride = size of the next-faster block). Use for padded/aligned rows, e.g. BMP's 4-byte row padding." .
```

- [ ] **Step 4: Run the gate and the full suite**

```
python tools/test_html_sync.py
python tools/validate_all.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS (`test_shapes.py` may print SKIP only if pyshacl is absent; it is installed, so expect PASS).

- [ ] **Step 5: Commit**

```bash
git add tools/test_html_sync.py specification/dlv/index.html
git commit -m "test(spec): gate index.html against its .ttl; fix dlv dimensionStride drift"
```

---

### Task 2: Vocabulary SHACL fixture runner

Tasks 3–6 each add SHACL shapes. They need a runner that proves a valid fixture conforms and an invalid one does not — the same convention `tools/test_shapes.py` already uses for the bundle module, generalised so later tasks only drop in fixture files.

**Files:**
- Create: `tools/test_vocab_shapes.py`
- Create: `specification/bddo/test/smoke-valid.ttl`
- Create: `specification/bddo/test/smoke-invalid.ttl`

**Interfaces:**
- Consumes: nothing.
- Produces: the command `python tools/test_vocab_shapes.py`, and the fixture convention `specification/<mod>/test/<feature>-{valid,invalid}.ttl`. Later tasks add fixture pairs only — no runner changes.

- [ ] **Step 1: Write the failing test**

Create `tools/test_vocab_shapes.py`:

```python
"""Run the BDDO + DLV + core SHACL shapes over every vocabulary fixture.

Convention: specification/<mod>/test/<feature>-valid.ttl must conform;
specification/<mod>/test/<feature>-invalid.ttl must NOT. Each -invalid file
carries an rdfs:comment naming the shape it is expected to trip.
"""
import glob
import sys

import rdflib
from pyshacl import validate

ONT = [
    "specification/bddo/bddo.ttl",
    "specification/dlv/dlv.ttl",
    "specification/hexplain/core.ttl",
]
SHAPES = ONT


def load(paths):
    g = rdflib.Graph()
    for p in paths:
        g.parse(p, format="turtle")
    return g


shapes = load(SHAPES)
fixtures = sorted(glob.glob("specification/*/test/*-valid.ttl")) + sorted(
    glob.glob("specification/*/test/*-invalid.ttl")
)
if not fixtures:
    sys.exit("FAIL: no fixtures found (wrong working directory?)")

failures = []
for path in fixtures:
    should_conform = path.endswith("-valid.ttl")
    data = load(ONT + [path])
    conforms, _, report = validate(
        data, shacl_graph=shapes, inference="none", advanced=True, meta_shacl=False
    )
    if conforms and not should_conform:
        failures.append(f"{path}: expected SHACL violation, but it conformed")
    elif not conforms and should_conform:
        failures.append(f"{path}: expected to conform, but did not:\n{report}")

if failures:
    print("FAIL:\n" + "\n".join(failures))
    sys.exit(1)
print(f"PASS: {len(fixtures)} vocabulary fixtures behave as expected")
```

Create `specification/bddo/test/smoke-valid.ttl` — a minimal well-formed struct that must conform:

```turtle
# Smoke fixture: a minimal well-formed BDDO struct. Must conform.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/smoke#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Header a bddo:Struct ;
    rdfs:label "Smoke header" ;
    bddo:endianness bddo:BigEndian ;
    bddo:hasField ( ex:Header.magic ex:Header.count ) .

ex:Header.magic a bddo:Field ; bddo:dataType bddo:uint32 ; bddo:hasFixedValue "0xCAFEBABE" .
ex:Header.count a bddo:Field ; bddo:dataType bddo:uint16 .
```

Create `specification/bddo/test/smoke-invalid.ttl` — trips the existing `bddo:FieldShape`, which requires every Field to declare `dataType` or `hasConditionalDataType`:

```turtle
# Smoke fixture: a Field with neither dataType nor hasConditionalDataType.
# Expected to trip bddo:FieldShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/smoke-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Broken a bddo:Struct ;
    rdfs:comment "Expected to trip bddo:FieldShape (field has no data type)." ;
    bddo:hasField ( ex:Broken.nameless ) .

ex:Broken.nameless a bddo:Field ; rdfs:label "no data type declared" .
```

- [ ] **Step 2: Run it to verify both fixtures behave**

Run: `python tools/test_vocab_shapes.py`
Expected: `PASS: 2 vocabulary fixtures behave as expected`.

> If `smoke-invalid.ttl` unexpectedly conforms, the runner is not reaching `bddo:FieldShape` — check that `advanced=True` is set and that `SHAPES` includes `bddo.ttl`. Do not weaken the fixture to make it pass.

- [ ] **Step 3: Confirm the new fixtures do not break the parse gate**

Run: `python tools/validate_all.py`
Expected: PASS, with the file count increased by 2.

- [ ] **Step 4: Commit**

```bash
git add tools/test_vocab_shapes.py specification/bddo/test/
git commit -m "test(spec): add vocabulary SHACL fixture runner and convention"
```

---

### Task 3: P0-3 — ASCII-numeric datatypes

BDDO's primitives are fixed-width binary plus `bddo:string`, so an ASCII-coded integer parses to a String. HEL errors on arithmetic with a non-numeric operand, so an ASCII length field cannot drive `sizeFromExpression`, `atOffsetFromExpression`, or `repeatCountFromExpression`. This blocks NITF segment offsets (`LISH`/`LI`), FITS `NAXISn`, USGSDEM, DTED, S-57, ESAT, FAST, CTG, TIGER, UK .NTF and PCIDSK.

**Files:**
- Modify: `specification/bddo/bddo.ttl` (datatype block ~line 153; SHACL section)
- Modify: `specification/bddo/index.html` (mirror + `<dl>` prose + JSON-LD context)
- Modify: `specification/hel/index.html` (Value Types paragraph, ~line 159)
- Modify: `docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md` (§6.1 type table)
- Create: `specification/bddo/test/ascii-numeric-valid.ttl`, `specification/bddo/test/ascii-numeric-invalid.ttl`

**Interfaces:**
- Consumes: the fixture convention and runner from Task 2.
- Produces: `bddo:asciiInteger`, `bddo:asciiDecimal` (both `bddo:DataType` individuals), `bddo:numericBase` (`owl:DatatypeProperty`, range `xsd:positiveInteger`), and the shapes `bddo:AsciiNumericWidthShape`, `bddo:NumericBaseShape`. Task 6 reuses `bddo:asciiInteger` for header entry values.

- [ ] **Step 1: Write the failing fixtures**

Create `specification/bddo/test/ascii-numeric-valid.ttl`:

```turtle
# An ASCII-coded length field driving a sibling's size — the NITF/FITS pattern.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/ascii#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Segment a bddo:Struct ;
    rdfs:label "Segment with an ASCII length prefix" ;
    bddo:hasField ( ex:Segment.length ex:Segment.payload ex:Segment.flags ) .

ex:Segment.length a bddo:Field ;
    rdfs:comment "Five ASCII digits, e.g. \"00512\"." ;
    bddo:dataType bddo:asciiInteger ; bddo:size 5 .

ex:Segment.payload a bddo:Field ;
    bddo:dataType bddo:bytes ;
    bddo:sizeFromField ex:Segment.length .

ex:Segment.flags a bddo:Field ;
    rdfs:comment "Two ASCII hex digits." ;
    bddo:dataType bddo:asciiInteger ; bddo:size 2 ; bddo:numericBase 16 .
```

Create `specification/bddo/test/ascii-numeric-invalid.ttl`:

```turtle
# Two violations: an asciiInteger field with no width, and numericBase on a binary field.
# Expected to trip bddo:AsciiNumericWidthShape and bddo:NumericBaseShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/ascii-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Bad a bddo:Struct ;
    rdfs:comment "Expected to trip bddo:AsciiNumericWidthShape and bddo:NumericBaseShape." ;
    bddo:hasField ( ex:Bad.unsized ex:Bad.wrongBase ) .

ex:Bad.unsized a bddo:Field ;
    bddo:dataType bddo:asciiInteger .

ex:Bad.wrongBase a bddo:Field ;
    bddo:dataType bddo:uint32 ; bddo:numericBase 16 .
```

- [ ] **Step 2: Run to verify the valid fixture fails**

Run: `python tools/test_vocab_shapes.py`
Expected: FAIL — `ascii-numeric-valid.ttl: expected to conform, but did not`, because `bddo:asciiInteger` is not yet a `bddo:DataType` and `bddo:FieldShape` requires `bddo:dataType` to be a `bddo:DataType` or `bddo:Struct`.

- [ ] **Step 3: Add the datatypes and property to `bddo.ttl`**

In `specification/bddo/bddo.ttl`, immediately after `:string a :DataType …` (line 153), add:

```turtle

# ---------- ASCII-coded numeric types ----------
# Numbers written as text in a fixed-width field (NITF BCS-N, FITS card values,
# USGSDEM Fortran fields). The parsed HEL value is numeric, so these fields may
# drive sizing, offset and repeat expressions — which bddo:string cannot.
:asciiInteger a :DataType ; rdfs:label "asciiInteger" ; :baseType :baseInteger ; :encoding :ascii ; :xsdType xsd:integer ;
    rdfs:comment "An integer written as text, occupying the field's declared width (bddo:size) or ending at its terminator. Surrounding space and a leading '+'/'-' are accepted. Radix is bddo:numericBase, default 10. Yields a HEL Integer." .
:asciiDecimal a :DataType ; rdfs:label "asciiDecimal" ; :baseType :baseFloat ; :encoding :ascii ; :xsdType xsd:decimal ;
    rdfs:comment "A fixed- or floating-point number written as text, occupying the field's declared width or ending at its terminator. Accepts leading sign, decimal point and exponent. Yields a HEL Float." .
```

In the "Field properties" block, after `:encoding` (line 66), add:

```turtle
:numericBase            a owl:DatatypeProperty ; rdfs:label "numeric base" ; rdfs:range xsd:positiveInteger ;
    rdfs:comment "Radix used to read an :asciiInteger field: 8, 10 or 16. Default 10." .
```

- [ ] **Step 4: Add the SHACL shapes to `bddo.ttl`**

Append to the SHACL section of `specification/bddo/bddo.ttl` (after the last existing shape):

```turtle

# An ASCII-coded numeric field must have a width or a terminator, or it cannot be read.
bddo:AsciiNumericWidthShape a sh:NodeShape ;
    sh:targetClass bddo:Field ;
    sh:sparql [ sh:message "A bddo:asciiInteger / bddo:asciiDecimal field must declare a width (size / sizeFromField / sizeFromExpression) or a terminator." ;
        sh:prefixes bddo:_prefixes ;
        sh:select """SELECT $this WHERE {
            $this bddo:dataType ?dt .
            FILTER(?dt IN (bddo:asciiInteger, bddo:asciiDecimal))
            FILTER NOT EXISTS { $this bddo:size ?s }
            FILTER NOT EXISTS { $this bddo:sizeFromField ?f }
            FILTER NOT EXISTS { $this bddo:sizeFromExpression ?e }
            FILTER NOT EXISTS { $this bddo:terminator ?t }
        }""" ] .

# numericBase is meaningful only for :asciiInteger.
bddo:NumericBaseShape a sh:NodeShape ;
    sh:targetSubjectsOf bddo:numericBase ;
    sh:property [ sh:path bddo:numericBase ; sh:maxCount 1 ; sh:in ( 8 10 16 ) ;
        sh:message "bddo:numericBase must be 8, 10 or 16." ] ;
    sh:property [ sh:path bddo:dataType ; sh:hasValue bddo:asciiInteger ;
        sh:message "bddo:numericBase applies only to a field whose bddo:dataType is bddo:asciiInteger." ] .
```

- [ ] **Step 5: Run to verify both fixtures now behave**

Run: `python tools/test_vocab_shapes.py`
Expected: PASS, 4 fixtures.

- [ ] **Step 6: Mirror into `bddo/index.html`**

Three edits to `specification/bddo/index.html`:

1. In the `<pre class="nohighlight">` vocabulary block, insert the same Turtle from Steps 3 and 4, HTML-escaped (`<` → `&lt;`, `>` → `&gt;`), at the matching positions.
2. In `<h3>Field Properties</h3>`'s `<dl>` (around line 151), add:

```html
                <dt><code>bddo:numericBase</code></dt>
                <dd>Radix (8, 10 or 16) for reading a <code>bddo:asciiInteger</code> field. Default 10.</dd>
```

3. In the JSON-LD context block, add `"numericBase": "bddo:numericBase",` alongside the other property entries.

Also add a short subsection after `<h3>Floating-Point &amp; Other Types</h3>`:

```html
        <h3>ASCII-Coded Numeric Types</h3>
        <p>Many record-oriented formats write numbers as text in fixed-width fields — NITF BCS-N, FITS card values, USGS DEM Fortran fields. <code>bddo:asciiInteger</code> and <code>bddo:asciiDecimal</code> read such a field as a number rather than a string, so its value may drive <code>bddo:sizeFromExpression</code>, <code>bddo:atOffsetFromExpression</code> and <code>bddo:repeatCountFromExpression</code>. The field's width comes from <code>bddo:size</code> (or a terminator); <code>bddo:numericBase</code> selects the radix.</p>
```

- [ ] **Step 7: Verify the sync gate passes**

Run: `python tools/test_html_sync.py`
Expected: PASS. If it reports triples `in .ttl only`, a line was missed in the mirror; if `in .html only`, an escaping error created a spurious triple.

- [ ] **Step 8: Clarify the HEL value-type rule**

In `specification/hel/index.html`, in the Value Types paragraph (~line 159), replace:

> A field's parsed value takes the natural HEL type of its `bddo:DataType` (integer types → Integer, float types → Float, `bddo:string` → String, `bddo:bytes` → Bytes).

with:

```html
            <p>Every HEL value is one of: <b>Integer</b>, <b>Float</b>, <b>Boolean</b>, <b>String</b>, <b>Bytes</b>, or <b>Null</b> (an absent/optional field). A field's parsed value takes the HEL type implied by its <code>bddo:DataType</code>'s <code>bddo:baseType</code>: <code>bddo:baseInteger</code> → Integer, <code>bddo:baseFloat</code> → Float, <code>bddo:baseString</code> → String, <code>bddo:baseBytes</code> → Bytes. This is determined by <code>baseType</code> alone, so the ASCII-coded numeric types <code>bddo:asciiInteger</code> and <code>bddo:asciiDecimal</code> yield Integer and Float respectively and may be used wherever a number is required.</p>
```

- [ ] **Step 9: Add the HDL surface**

In `docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md` §6.1, add two rows to the type table after the `ascii utf8 …` row:

```markdown
| `anum` | `bddo:asciiInteger` — an integer written as text; needs a width, e.g. `anum[5]` |
| `adec` | `bddo:asciiDecimal` — a decimal written as text; needs a width |
```

And a row to the §6.2 clause table:

```markdown
| numeric base | `anum[2] @base 16` | `numericBase` |
```

In §13's grammar sketch, extend `type` and `clause`:

```ebnf
type         = prim | "bytes" | strtype | "anum" | "adec" | "bits" "[" expr "]" | struct-ref ;
```
and add `| "@base" INT` to the `clause` alternatives.

- [ ] **Step 10: Run the full suite**

```
python tools/test_html_sync.py
python tools/test_vocab_shapes.py
python tools/validate_all.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add specification/bddo/ specification/hel/index.html docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md
git commit -m "feat(bddo): add asciiInteger/asciiDecimal datatypes and numericBase

ASCII-coded numeric fields now parse to HEL numbers, so they can drive
sizeFromExpression / atOffsetFromExpression / repeatCountFromExpression.
Unblocks NITF segment offsets, FITS NAXISn, USGSDEM, DTED, S-57 and others.
Implements P0-3 of docs/superpowers/notes/2026-08-01-spec-improvements-from-gdal-survey.md"
```

---

### Task 4: P0-4 — Data-dependent endianness

`bddo:endianness` ranges over two fixed individuals, so a file that declares its own byte order cannot be described. The shipped TIFF profile documents this in a comment and then hardcodes `bddo:LittleEndian` on every struct, making it incorrect for big-endian (MM) TIFF.

The improvements note floated `endiannessFromExpression`, which would need a conditional operator in HEL. **This plan uses the rule-list form instead** — it mirrors the existing `bddo:hasConditionalDataType` / `bddo:DataTypeRule` idiom exactly and requires no HEL change at all.

**Files:**
- Modify: `specification/bddo/bddo.ttl`
- Modify: `specification/bddo/index.html`
- Modify: `docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md` (§6.2, §13)
- Create: `specification/bddo/test/conditional-endianness-valid.ttl`, `…-invalid.ttl`

**Interfaces:**
- Consumes: Task 2's runner.
- Produces: `bddo:hasConditionalEndianness` (`owl:ObjectProperty`, range `rdf:List`), `bddo:EndiannessRule` (`owl:Class`), `bddo:ruleEndianness` (`owl:ObjectProperty`, range `bddo:Endianness`), and `bddo:ConditionalEndiannessShape`. Reuses the existing `bddo:condition` property.

- [ ] **Step 1: Write the failing fixtures**

Create `specification/bddo/test/conditional-endianness-valid.ttl`:

```turtle
# The TIFF II/MM case: byte order declared by the file's own first field.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ex:   <https://hexplain.io/test/endian#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:TIFFHeader a bddo:Struct ;
    rdfs:label "TIFF image file header" ;
    bddo:hasConditionalEndianness (
        [ a bddo:EndiannessRule ; bddo:condition "instance.ByteOrder == 0x4949" ; bddo:ruleEndianness bddo:LittleEndian ]
        [ a bddo:EndiannessRule ; bddo:condition "instance.ByteOrder == 0x4D4D" ; bddo:ruleEndianness bddo:BigEndian ]
    ) ;
    bddo:hasField ( ex:TIFFHeader.ByteOrder ex:TIFFHeader.Version ) .

ex:TIFFHeader.ByteOrder a bddo:Field ; bddo:dataType bddo:uint16be .
ex:TIFFHeader.Version a bddo:Field ; bddo:dataType bddo:uint16 .
```

Create `specification/bddo/test/conditional-endianness-invalid.ttl`:

```turtle
# Two violations: static and conditional endianness on the same struct, and a
# rule-list member that is not an EndiannessRule.
# Expected to trip bddo:ConditionalEndiannessShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/endian-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Clash a bddo:Struct ;
    rdfs:comment "Expected to trip bddo:ConditionalEndiannessShape." ;
    bddo:endianness bddo:LittleEndian ;
    bddo:hasConditionalEndianness (
        [ a bddo:EndiannessRule ; bddo:condition "instance.Flag == 1" ; bddo:ruleEndianness bddo:BigEndian ]
    ) ;
    bddo:hasField ( ex:Clash.Flag ) .

ex:Clash.Flag a bddo:Field ; bddo:dataType bddo:uint8 .
```

- [ ] **Step 2: Run to verify the valid fixture fails**

Run: `python tools/test_vocab_shapes.py`
Expected: FAIL — the invalid fixture conforms, because `bddo:ConditionalEndiannessShape` does not exist yet. (The valid fixture may already pass, since unknown properties are unconstrained; that is expected. The gate this task adds is the mutual-exclusion rule.)

- [ ] **Step 3: Add the vocabulary to `bddo.ttl`**

In the Classes block, after `:Checksum` (line 36), add:

```turtle
:EndiannessRule a owl:Class ; rdfs:label "Endianness Rule" ; rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "One arm of a hasConditionalEndianness list: a HEL condition and the byte order it selects." .
```

In the Structural properties block, after `:endianness` (line 52), add:

```turtle
:hasConditionalEndianness a owl:ObjectProperty ; rdfs:label "has conditional endianness" ; rdfs:range rdf:List ;
    rdfs:comment "Ordered rdf:List of EndiannessRule. The first rule whose condition holds selects the byte order for this Struct or Field and, as with bddo:endianness, for its descendants unless they override it. Use for formats that declare their own byte order, such as TIFF's 4949h/4D4Dh marker. Mutually exclusive with bddo:endianness." .
```

In the DataType / Rule block, after `:ruleDataType` (line 89), add:

```turtle
:ruleEndianness a owl:ObjectProperty ; rdfs:label "rule endianness" ; rdfs:range :Endianness ;
    rdfs:comment "The byte order selected by an EndiannessRule." .
```

- [ ] **Step 4: Add the SHACL shapes to `bddo.ttl`**

Append to the SHACL section:

```turtle

bddo:EndiannessRuleShape a sh:NodeShape ;
    sh:targetClass bddo:EndiannessRule ;
    sh:property [ sh:path bddo:condition ; sh:datatype xsd:string ; sh:minCount 1 ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:ruleEndianness ; sh:minCount 1 ; sh:maxCount 1 ;
        sh:in ( bddo:BigEndian bddo:LittleEndian ) ;
        sh:message "bddo:ruleEndianness must be bddo:BigEndian or bddo:LittleEndian." ] .

bddo:ConditionalEndiannessShape a sh:NodeShape ;
    sh:targetSubjectsOf bddo:hasConditionalEndianness ;
    sh:property [ sh:path bddo:hasConditionalEndianness ; sh:maxCount 1 ; sh:nodeKind sh:BlankNodeOrIRI ;
        sh:message "bddo:hasConditionalEndianness must point to a single rdf:List." ] ;
    sh:property [ sh:path bddo:endianness ; sh:maxCount 0 ;
        sh:message "bddo:endianness and bddo:hasConditionalEndianness are mutually exclusive." ] ;
    sh:property [ sh:path ( bddo:hasConditionalEndianness [ sh:zeroOrMorePath rdf:rest ] rdf:first ) ;
        sh:class bddo:EndiannessRule ;
        sh:message "Every member of a hasConditionalEndianness list must be a bddo:EndiannessRule." ] .
```

- [ ] **Step 5: Run to verify both fixtures behave**

Run: `python tools/test_vocab_shapes.py`
Expected: PASS, 6 fixtures.

- [ ] **Step 6: Mirror into `bddo/index.html`**

Insert the Turtle from Steps 3 and 4 into the vocabulary and SHACL `<pre>` blocks, HTML-escaped. Add to the Structural Properties `<dl>`:

```html
                <dt><code>bddo:hasConditionalEndianness</code></dt>
                <dd>Ordered list of <code>bddo:EndiannessRule</code>; the first rule whose <code>bddo:condition</code> holds sets the byte order for this term and its descendants. For formats that declare their own byte order. Mutually exclusive with <code>bddo:endianness</code>.</dd>
```

Add to the JSON-LD context: `"hasConditionalEndianness": { "@id": "bddo:hasConditionalEndianness", "@container": "@list" },` and `"ruleEndianness": { "@id": "bddo:ruleEndianness", "@type": "@id" },`.

- [ ] **Step 7: Verify sync**

Run: `python tools/test_html_sync.py`
Expected: PASS.

- [ ] **Step 8: Add the HDL surface**

In §6.2 of the HDL design doc, add a clause row:

```markdown
| conditional endianness | `@endian switch { when ByteOrder == 0x4949 => little, when ByteOrder == 0x4D4D => big }` | `hasConditionalEndianness` (`EndiannessRule` list) |
```

In §13, add to `struct-annot`:

```ebnf
struct-annot = "@endian" endian | "@endian" "switch" "{" { endianarm } "}"
             | "@bit-order" bitorder | "@size" ( INT | ref | "`" HEL "`" ) ;
endianarm    = "when" expr "=>" endian ;
```

- [ ] **Step 9: Run the full suite and commit**

```
python tools/test_html_sync.py
python tools/test_vocab_shapes.py
python tools/validate_all.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS.

```bash
git add specification/bddo/ docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md
git commit -m "feat(bddo): add hasConditionalEndianness for self-declaring byte order

Mirrors the hasConditionalDataType/DataTypeRule idiom, so no HEL change is
needed. Lets TIFF's II/MM marker actually select the byte order instead of
being hardcoded. Implements P0-4 of the GDAL survey improvements note."
```

> **Follow-up, out of scope here:** `hexplain-tools/core/src/main/resources/tiff-profile.ttl` should be rewritten to use this instead of hardcoding `bddo:LittleEndian` on lines 31, 65 and 98. That lives in a different repository; open a separate change.

---

### Task 5: P0-2 — Chunked data layout

`dlv:DataLayout` describes exactly one contiguous strided block. Tiled and chunked rasters — every COG, blocked NITF imagery, HDF5/Zarr chunks, GPKG/MBTiles/MRF tile pyramids, JPEG 2000 tiles — cannot be described. Blocked NITF is on the project's certification path.

**Files:**
- Modify: `specification/dlv/dlv.ttl`
- Modify: `specification/dlv/index.html`
- Modify: `docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md` (§9, §13)
- Create: `specification/dlv/test/chunked-layout-valid.ttl`, `…-invalid.ttl`

**Interfaces:**
- Consumes: Task 2's runner.
- Produces: on `dlv:Dimension` — `dlv:chunkSize` (`xsd:positiveInteger`), `dlv:chunkSizeFromField` (`bddo:Field`); on `dlv:DataLayout` — `dlv:chunkOffsetsFromField` (`bddo:Field`), `dlv:chunkLengthsFromField` (`bddo:Field`), `dlv:chunkOffsetBase` (`bddo:OffsetBase`), `dlv:chunkOrder` (`dlv:ChunkOrder`); the class `dlv:ChunkOrder` with individuals `dlv:rowMajor`, `dlv:columnMajor`, `dlv:morton`, `dlv:hilbert`; the shape `dlv:ChunkedLayoutShape`; and `dlv:_prefixes` for SPARQL constraints.

- [ ] **Step 1: Write the failing fixtures**

Create `specification/dlv/test/chunked-layout-valid.ttl`:

```turtle
# A tiled TIFF image: 256x256 tiles located through TileOffsets/TileByteCounts.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix dlv:  <https://hexplain.io/ns/dlv#> .
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix ex:   <https://hexplain.io/test/chunk#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Image a bddo:Struct ;
    bddo:hasField ( ex:Image.width ex:Image.height ex:Image.tileOffsets ex:Image.tileByteCounts ex:Image.pixels ) .

ex:Image.width a bddo:Field ; bddo:dataType bddo:uint32 .
ex:Image.height a bddo:Field ; bddo:dataType bddo:uint32 .
ex:Image.tileOffsets a bddo:Field ; bddo:dataType bddo:uint32 ; bddo:repeatUntil "eof()" .
ex:Image.tileByteCounts a bddo:Field ; bddo:dataType bddo:uint32 ; bddo:repeatUntil "eof()" .

ex:Image.pixels a bddo:Field ;
    bddo:dataType bddo:bytes ;
    bddo:sizeToEndOfStream true ;
    hexplain:hasDataLayout ex:PixelLayout .

ex:PixelLayout a dlv:DataLayout ;
    rdfs:label "Tiled 8-bit grid" ;
    dlv:cellDataType bddo:uint8 ;
    dlv:chunkOffsetsFromField ex:Image.tileOffsets ;
    dlv:chunkLengthsFromField ex:Image.tileByteCounts ;
    dlv:chunkOffsetBase bddo:streamStart ;
    dlv:chunkOrder dlv:rowMajor ;
    dlv:hasDimension ( ex:DimY ex:DimX ) .

ex:DimY a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSizeFromField ex:Image.height ; dlv:chunkSize 256 .
ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:Image.width  ; dlv:chunkSize 256 .
```

Create `specification/dlv/test/chunked-layout-invalid.ttl`:

```turtle
# A chunked layout with no chunk offset table — the chunks cannot be located.
# Expected to trip dlv:ChunkedLayoutShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix dlv:  <https://hexplain.io/ns/dlv#> .
@prefix ex:   <https://hexplain.io/test/chunk-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

ex:Layout a dlv:DataLayout ;
    rdfs:comment "Expected to trip dlv:ChunkedLayoutShape (chunked but no chunkOffsetsFromField)." ;
    dlv:cellDataType bddo:uint8 ;
    dlv:hasDimension ( ex:DimY ex:DimX ) .

ex:DimY a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSize 1024 ; dlv:chunkSize 256 .
ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSize 1024 ; dlv:chunkSize 256 .
```

- [ ] **Step 2: Run to verify the invalid fixture wrongly conforms**

Run: `python tools/test_vocab_shapes.py`
Expected: FAIL — `chunked-layout-invalid.ttl: expected SHACL violation, but it conformed`.

- [ ] **Step 3: Add the vocabulary to `dlv.ttl`**

In `specification/dlv/dlv.ttl`, after `:hasAxis` (line 35), add:

```turtle

# ---------- Chunked (tiled/blocked) layout ----------
:ChunkOrder a owl:Class ; rdfs:label "Chunk Order" ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> ;
    rdfs:comment "The order in which chunks appear in the chunk offset table." .
:chunkSize a owl:DatatypeProperty ; rdfs:label "chunk size" ; rdfs:range xsd:positiveInteger ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> ;
    rdfs:comment "Extent of one chunk (tile/block) along this dimension, in cells. When any Dimension of a DataLayout declares a chunk extent, the layout is chunked: the grid is partitioned into chunks of this shape and each chunk is located through the layout's chunk offset table. A trailing partial chunk is padded to the full chunk extent." .
:chunkSizeFromField a owl:ObjectProperty ; rdfs:label "chunk size from field" ; rdfs:range bddo:Field ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> .
:chunkOffsetsFromField a owl:ObjectProperty ; rdfs:label "chunk offsets from field" ; rdfs:range bddo:Field ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> ;
    rdfs:comment "The repeating Field holding each chunk's byte offset, indexed in chunkOrder (e.g. TIFF TileOffsets, NITF block offsets)." .
:chunkLengthsFromField a owl:ObjectProperty ; rdfs:label "chunk lengths from field" ; rdfs:range bddo:Field ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> ;
    rdfs:comment "The repeating Field holding each chunk's byte length (e.g. TIFF TileByteCounts). Required when chunks are individually encoded; when absent, a chunk's length is its cell count times the cell width." .
:chunkOffsetBase a owl:ObjectProperty ; rdfs:label "chunk offset base" ; rdfs:range bddo:OffsetBase ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> ;
    rdfs:comment "What the chunk offsets are relative to. Default bddo:streamStart." .
:chunkOrder a owl:ObjectProperty ; rdfs:label "chunk order" ; rdfs:range :ChunkOrder ; rdfs:isDefinedBy <https://hexplain.io/ns/dlv> ;
    rdfs:comment "Traversal order of the chunk offset table. Default dlv:rowMajor (chunks vary fastest along the fastest-varying dimension)." .

:rowMajor a owl:NamedIndividual, :ChunkOrder ; rdfs:label "Row-major chunk order" .
:columnMajor a owl:NamedIndividual, :ChunkOrder ; rdfs:label "Column-major chunk order" .
:morton a owl:NamedIndividual, :ChunkOrder ; rdfs:label "Morton (Z-order) chunk order" .
:hilbert a owl:NamedIndividual, :ChunkOrder ; rdfs:label "Hilbert curve chunk order" .
```

Add `@prefix rdf:` is already present; confirm `bddo:` is too (it is, line 10).

- [ ] **Step 4: Add the SHACL shapes to `dlv.ttl`**

Append to the SHACL section of `dlv.ttl`:

```turtle

dlv:_prefixes sh:declare
    [ sh:prefix "dlv" ; sh:namespace "https://hexplain.io/ns/dlv#"^^xsd:anyURI ] ,
    [ sh:prefix "rdf" ; sh:namespace "http://www.w3.org/1999/02/22-rdf-syntax-ns#"^^xsd:anyURI ] .

# A chunked layout must say where its chunks are.
dlv:ChunkedLayoutShape a sh:NodeShape ;
    sh:targetClass dlv:DataLayout ;
    sh:property [ sh:path dlv:chunkOffsetsFromField ; sh:class bddo:Field ; sh:maxCount 1 ] ;
    sh:property [ sh:path dlv:chunkLengthsFromField ; sh:class bddo:Field ; sh:maxCount 1 ] ;
    sh:property [ sh:path dlv:chunkOffsetBase ; sh:maxCount 1 ;
        sh:in ( bddo:streamStart bddo:streamEnd bddo:parentStart bddo:currentPosition ) ] ;
    sh:property [ sh:path dlv:chunkOrder ; sh:maxCount 1 ; sh:class dlv:ChunkOrder ] ;
    sh:sparql [ sh:message "A chunked dlv:DataLayout (any Dimension declaring dlv:chunkSize or dlv:chunkSizeFromField) must declare dlv:chunkOffsetsFromField." ;
        sh:prefixes dlv:_prefixes ;
        sh:select """SELECT $this WHERE {
            $this dlv:hasDimension/rdf:rest*/rdf:first ?d .
            { ?d dlv:chunkSize ?c } UNION { ?d dlv:chunkSizeFromField ?c }
            FILTER NOT EXISTS { $this dlv:chunkOffsetsFromField ?o }
        }""" ] .
```

Extend the existing `dlv:DimensionShape` with chunk cardinality — add these two property shapes inside it:

```turtle
    sh:property [ sh:path dlv:chunkSize ; sh:minExclusive 0 ; sh:maxCount 1 ] ;
    sh:property [ sh:path dlv:chunkSizeFromField ; sh:class bddo:Field ; sh:maxCount 1 ] ;
```

- [ ] **Step 5: Run to verify both fixtures behave**

Run: `python tools/test_vocab_shapes.py`
Expected: PASS, 8 fixtures.

- [ ] **Step 6: Mirror into `dlv/index.html`**

Insert the Turtle from Steps 3 and 4 into the vocabulary and SHACL `<pre>` blocks, HTML-escaped. Add to the properties `<dl>`:

```html
                <dt><code>dlv:chunkSize</code> / <code>dlv:chunkSizeFromField</code></dt>
                <dd>Extent of one chunk (tile/block) along this dimension, in cells. Declaring either on any dimension makes the layout chunked.</dd>
                <dt><code>dlv:chunkOffsetsFromField</code> / <code>dlv:chunkLengthsFromField</code></dt>
                <dd>The repeating fields holding each chunk's byte offset and length — TIFF's <code>TileOffsets</code>/<code>TileByteCounts</code>, NITF's block offsets.</dd>
                <dt><code>dlv:chunkOrder</code> / <code>dlv:chunkOffsetBase</code></dt>
                <dd>Traversal order of the chunk table (default <code>dlv:rowMajor</code>) and what its offsets are relative to (default <code>bddo:streamStart</code>).</dd>
```

Add to the JSON-LD context: `"chunkSize"`, `"chunkSizeFromField"`, `"chunkOffsetsFromField"`, `"chunkLengthsFromField"`, `"chunkOffsetBase"`, `"chunkOrder"` — the object properties with `"@type": "@id"`.

- [ ] **Step 7: Verify sync**

Run: `python tools/test_html_sync.py`
Expected: PASS.

- [ ] **Step 8: Add the HDL surface**

In §9 of the HDL design doc, replace the layout example with one showing both forms and add the chunk clause description:

````markdown
```
pixels : bytes[..] layout cell u8 {
  dim axis Y size height chunk tileLength
  dim axis X size width  chunk tileWidth
  chunks offsets TileOffsets lengths TileByteCounts base stream-start order row-major
}
```

- `dim … chunk <int|sibling>` → `dlv:chunkSize` / `dlv:chunkSizeFromField`.
- `chunks offsets <field> [lengths <field>] [base <offsetbase>] [order <order>]` →
  `dlv:chunkOffsetsFromField`, `dlv:chunkLengthsFromField`, `dlv:chunkOffsetBase`,
  `dlv:chunkOrder`. Orders: `row-major column-major morton hilbert`.
  Required whenever any `dim` declares a `chunk` extent.
````

In §13, extend the layout grammar:

```ebnf
dimdecl      = "dim" "axis" AXIS "size" ( INT | ref ) [ "stride" ( INT | expr ) ]
               [ "chunk" ( INT | ref ) ] ;
chunkdecl    = "chunks" "offsets" ref [ "lengths" ref ] [ "base" offsetbase ]
               [ "order" chunkorder ] ;
chunkorder   = "row-major" | "column-major" | "morton" | "hilbert" ;
```
and add `chunkdecl` to the `layout` clause body alongside `dimdecl`.

- [ ] **Step 9: Run the full suite and commit**

```
python tools/test_html_sync.py
python tools/test_vocab_shapes.py
python tools/validate_all.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS.

```bash
git add specification/dlv/ docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md
git commit -m "feat(dlv): add chunked (tiled/blocked) data layout

Per-dimension chunk extents plus a chunk offset/length table, so tiled and
blocked rasters can be described: COG, blocked NITF, HDF5/Zarr chunks,
GPKG/MBTiles tile pyramids. Implements P0-2 of the GDAL survey improvements note."
```

---

### Task 6: P0-1 — Delimited-record primitive (vocabulary)

BDDO addresses bytes by offset and size only, so there is no way to say "split this run on a delimiter and name the parts". That single absence puts all 43 payload-only formats out of full reach and most delimited text grids out of scope entirely. This task adds a deliberately **non-recursive** two-level splitting primitive — it models line- and character-delimited text, not nested grammars.

**Files:**
- Modify: `specification/bddo/bddo.ttl`
- Modify: `specification/bddo/index.html`
- Modify: `docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md` (§6.2, §11, §13)
- Create: `specification/bddo/test/delimited-valid.ttl`, `…-invalid.ttl`

**Interfaces:**
- Consumes: `bddo:asciiInteger` from Task 3; Task 2's runner.
- Produces: classes `bddo:DelimitedRecords` (subclass of `bddo:Struct`), `bddo:KeyValueHeader`, `bddo:DelimitedTable`; properties `bddo:recordDelimiter`, `bddo:fieldDelimiter`, `bddo:keyValueSeparator`, `bddo:quoteChar`, `bddo:escapeChar`, `bddo:commentPrefix`, `bddo:skipRecords`, `bddo:trimWhitespace`, `bddo:key`, `bddo:keyIsCaseInsensitive`; shapes `bddo:DelimitedRecordsShape`, `bddo:KeyValueHeaderShape`, `bddo:DelimitedTableShape`.

- [ ] **Step 1: Write the failing fixtures**

Create `specification/bddo/test/delimited-valid.ttl`:

```turtle
# Two shapes of delimited text: an ENVI-style key = value header, and a CSV table.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix araster: <https://hexplain.io/ns/aspect/raster#> .
@prefix ex:   <https://hexplain.io/test/delim#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# --- ENVI-style header: "samples = 5000" one per line ---
ex:EnviHeader a bddo:KeyValueHeader ;
    rdfs:label "ENVI .hdr" ;
    bddo:recordDelimiter "0A"^^xsd:hexBinary ;
    bddo:keyValueSeparator "3D"^^xsd:hexBinary ;
    bddo:commentPrefix ";" ;
    bddo:trimWhitespace true ;
    bddo:keyIsCaseInsensitive true ;
    bddo:hasField ( ex:EnviHeader.samples ex:EnviHeader.lines ) .

ex:EnviHeader.samples a bddo:Field ;
    bddo:key "samples" ; bddo:dataType bddo:asciiInteger ; bddo:terminator "0A"^^xsd:hexBinary ;
    hexplain:mapsToProperty araster:width .

ex:EnviHeader.lines a bddo:Field ;
    bddo:key "lines" ; bddo:dataType bddo:asciiInteger ; bddo:terminator "0A"^^xsd:hexBinary ;
    hexplain:mapsToProperty araster:height .

# --- CSV table: positional columns, one header row skipped ---
ex:PointCsv a bddo:DelimitedTable ;
    rdfs:label "XYZ point CSV" ;
    bddo:recordDelimiter "0A"^^xsd:hexBinary ;
    bddo:fieldDelimiter "2C"^^xsd:hexBinary ;
    bddo:quoteChar "22"^^xsd:hexBinary ;
    bddo:skipRecords 1 ;
    bddo:hasField ( ex:PointCsv.x ex:PointCsv.y ex:PointCsv.z ) .

ex:PointCsv.x a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:terminator "2C"^^xsd:hexBinary .
ex:PointCsv.y a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:terminator "2C"^^xsd:hexBinary .
ex:PointCsv.z a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:terminator "0A"^^xsd:hexBinary .
```

Create `specification/bddo/test/delimited-invalid.ttl`:

```turtle
# Two violations: a KeyValueHeader whose field declares no bddo:key, and a
# KeyValueHeader with no keyValueSeparator.
# Expected to trip bddo:KeyValueHeaderShape.
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix ex:   <https://hexplain.io/test/delim-invalid#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

ex:BadHeader a bddo:KeyValueHeader ;
    rdfs:comment "Expected to trip bddo:KeyValueHeaderShape (no keyValueSeparator; field has no key)." ;
    bddo:recordDelimiter "0A"^^xsd:hexBinary ;
    bddo:hasField ( ex:BadHeader.orphan ) .

ex:BadHeader.orphan a bddo:Field ;
    bddo:dataType bddo:asciiInteger ; bddo:terminator "0A"^^xsd:hexBinary .
```

- [ ] **Step 2: Run to verify the invalid fixture wrongly conforms**

Run: `python tools/test_vocab_shapes.py`
Expected: FAIL — `delimited-invalid.ttl: expected SHACL violation, but it conformed`.

- [ ] **Step 3: Add the classes to `bddo.ttl`**

In the Classes block, after `:Checksum`, add:

```turtle
# ---------- Delimited text records ----------
# Deliberately non-recursive: this models line- and character-delimited text
# (key = value headers, CSV, whitespace-separated grids), NOT nested grammars
# such as XML or JSON. Those remain out of scope for BDDO by design.
:DelimitedRecords a owl:Class ; rdfs:subClassOf :Struct ; rdfs:label "Delimited Records" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "A Struct whose children are located by delimiter position rather than byte offset: a byte run split into records by recordDelimiter, each record optionally split into values by fieldDelimiter." .
:KeyValueHeader a owl:Class ; rdfs:subClassOf :DelimitedRecords ; rdfs:label "Key/Value Header" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "DelimitedRecords whose records are key/value pairs split by keyValueSeparator. Each expected key is a Field carrying bddo:key; record order is not significant." .
:DelimitedTable a owl:Class ; rdfs:subClassOf :DelimitedRecords ; rdfs:label "Delimited Table" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/bddo> ;
    rdfs:comment "DelimitedRecords whose records are rows with a fixed column sequence. The hasField list gives the columns in order; the row structure repeats until the byte run is exhausted." .
```

- [ ] **Step 4: Add the properties to `bddo.ttl`**

In the Field properties block, after `:encoding`, add:

```turtle
:recordDelimiter        a owl:DatatypeProperty ; rdfs:label "record delimiter" ; rdfs:range xsd:hexBinary ;
    rdfs:comment "Byte sequence separating records. Default 0A (LF); a CR LF pair is also accepted when this is 0A." .
:fieldDelimiter         a owl:DatatypeProperty ; rdfs:label "field delimiter" ; rdfs:range xsd:hexBinary ;
    rdfs:comment "Byte sequence separating values within one record. When absent, a record is a single value." .
:keyValueSeparator      a owl:DatatypeProperty ; rdfs:label "key/value separator" ; rdfs:range xsd:hexBinary ;
    rdfs:comment "Byte sequence separating a key from its value within a record of a KeyValueHeader." .
:quoteChar              a owl:DatatypeProperty ; rdfs:label "quote character" ; rdfs:range xsd:hexBinary ;
    rdfs:comment "Byte that quotes a value, allowing it to contain the field or record delimiter. A doubled quote inside a quoted value denotes a literal quote." .
:escapeChar             a owl:DatatypeProperty ; rdfs:label "escape character" ; rdfs:range xsd:hexBinary ;
    rdfs:comment "Byte that escapes the following byte, suppressing its delimiter or quote meaning." .
:commentPrefix          a owl:DatatypeProperty ; rdfs:label "comment prefix" ; rdfs:range xsd:string ;
    rdfs:comment "A record beginning with this string (after optional whitespace) is ignored." .
:skipRecords            a owl:DatatypeProperty ; rdfs:label "skip records" ; rdfs:range xsd:nonNegativeInteger ;
    rdfs:comment "Number of leading records to discard before parsing, e.g. a CSV column-name row. Default 0." .
:trimWhitespace         a owl:DatatypeProperty ; rdfs:label "trim whitespace" ; rdfs:range xsd:boolean ;
    rdfs:comment "If true, leading and trailing whitespace is removed from every key and value. Default false." .
:key                    a owl:DatatypeProperty ; rdfs:label "key" ; rdfs:range xsd:string ;
    rdfs:comment "The key naming this Field within a KeyValueHeader. Replaces positional location: the Field takes the value of whichever record carries this key." .
:keyIsCaseInsensitive   a owl:DatatypeProperty ; rdfs:label "key is case insensitive" ; rdfs:range xsd:boolean ;
    rdfs:comment "If true, bddo:key matching ignores ASCII case. Default false." .
```

- [ ] **Step 5: Add the SHACL shapes to `bddo.ttl`**

Append to the SHACL section:

```turtle

bddo:DelimitedRecordsShape a sh:NodeShape ;
    sh:targetClass bddo:DelimitedRecords ;
    sh:property [ sh:path bddo:recordDelimiter ; sh:datatype xsd:hexBinary ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:fieldDelimiter ; sh:datatype xsd:hexBinary ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:keyValueSeparator ; sh:datatype xsd:hexBinary ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:quoteChar ; sh:datatype xsd:hexBinary ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:escapeChar ; sh:datatype xsd:hexBinary ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:commentPrefix ; sh:datatype xsd:string ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:skipRecords ; sh:datatype xsd:nonNegativeInteger ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:trimWhitespace ; sh:datatype xsd:boolean ; sh:maxCount 1 ] ;
    sh:property [ sh:path bddo:hasField ; sh:minCount 1 ;
        sh:message "A bddo:DelimitedRecords must declare at least one field." ] .

# A KeyValueHeader needs a separator, and every one of its fields needs a key.
bddo:KeyValueHeaderShape a sh:NodeShape ;
    sh:targetClass bddo:KeyValueHeader ;
    sh:property [ sh:path bddo:keyValueSeparator ; sh:minCount 1 ;
        sh:message "A bddo:KeyValueHeader must declare bddo:keyValueSeparator." ] ;
    sh:property [ sh:path ( bddo:hasField [ sh:zeroOrMorePath rdf:rest ] rdf:first ) ;
        sh:node [ sh:property [ sh:path bddo:key ; sh:minCount 1 ; sh:maxCount 1 ;
            sh:message "Every field of a bddo:KeyValueHeader must declare exactly one bddo:key." ] ] ] .

# bddo:key is meaningful only inside a KeyValueHeader; a table's columns are positional.
bddo:DelimitedTableShape a sh:NodeShape ;
    sh:targetClass bddo:DelimitedTable ;
    sh:property [ sh:path bddo:fieldDelimiter ; sh:minCount 1 ;
        sh:message "A bddo:DelimitedTable must declare bddo:fieldDelimiter." ] ;
    sh:property [ sh:path bddo:keyValueSeparator ; sh:maxCount 0 ;
        sh:message "bddo:keyValueSeparator applies to a KeyValueHeader, not a DelimitedTable." ] .
```

- [ ] **Step 6: Run to verify both fixtures behave**

Run: `python tools/test_vocab_shapes.py`
Expected: PASS, 10 fixtures.

> The valid fixture's `ex:PointCsv` declares `fieldDelimiter` and no `keyValueSeparator`, and `ex:EnviHeader` declares `keyValueSeparator` and gives every field a `key` — so both satisfy the new shapes. If `delimited-valid.ttl` fails, read the pyshacl report's focus node before changing anything: the fixture encodes the intended design.

- [ ] **Step 7: Mirror into `bddo/index.html`**

Insert the Turtle from Steps 3–5 into the vocabulary and SHACL `<pre>` blocks, HTML-escaped. Add a prose section after `<h2>Bit-Level Fields</h2>`:

```html
        <h2>Delimited Text Records</h2>
        <p>Record- and line-oriented text — <code>key = value</code> headers, CSV, whitespace-separated grids — cannot be addressed by byte offset. <code>bddo:DelimitedRecords</code> is a <code>bddo:Struct</code> whose children are located by delimiter position instead: <code>bddo:recordDelimiter</code> splits the byte run into records, and <code>bddo:fieldDelimiter</code> splits each record into values. Its two specialisations cover the common cases — <code>bddo:KeyValueHeader</code>, where each field is matched by <code>bddo:key</code> rather than position, and <code>bddo:DelimitedTable</code>, where <code>bddo:hasField</code> gives an ordered column list that repeats per row.</p>
        <p class="note">This primitive is deliberately non-recursive. It describes flat delimited text only; nested grammars such as XML and JSON are outside BDDO's scope by design.</p>
```

Add each new property to the Field Properties `<dl>` and to the JSON-LD context.

- [ ] **Step 8: Verify sync**

Run: `python tools/test_html_sync.py`
Expected: PASS.

- [ ] **Step 9: Add the HDL surface**

In the HDL design doc §6.2, add clause rows:

```markdown
| key (in a header) | `"samples" : anum means araster:width` | `key` |
```

Add a new §6.5 after the TIFF sketch:

````markdown
### 6.5 Delimited text (`header` / `table`)

```
header EnviHeader @separator "=" @comment ";" @trim @ci {
  "samples" : anum means araster:width
  "lines"   : anum means araster:height
}

table PointCsv @separator "," @quote '"' @skip 1 {
  x : adec
  y : adec
  z : adec
}
```

`header` → `bddo:KeyValueHeader`, `table` → `bddo:DelimitedTable`. Annotations:
`@record-separator` (default LF) → `recordDelimiter`; `@separator` →
`keyValueSeparator` on a `header`, `fieldDelimiter` on a `table`; `@quote` →
`quoteChar`; `@escape` → `escapeChar`; `@comment` → `commentPrefix`; `@skip` →
`skipRecords`; `@trim` → `trimWhitespace`; `@ci` → `keyIsCaseInsensitive`. A
quoted field name in a `header` is its `bddo:key`.
````

In §11 (YAML projection), add the mirror keys: `headers:` and `tables:` top-level maps with `separator`, `record-separator`, `quote`, `escape`, `comment`, `skip`, `trim`, `ci`, and per-entry `key`.

In §13, add:

```ebnf
header-decl  = "header" IDENT { delim-annot } "{" { entry-decl } "}" ;
table-decl   = "table" IDENT { delim-annot } "{" { field-decl } "}" ;
delim-annot  = "@separator" STRING | "@record-separator" STRING | "@quote" STRING
             | "@escape" STRING | "@comment" STRING | "@skip" INT | "@trim" | "@ci" ;
entry-decl   = STRING ":" type { clause } ;
```
and add `header-decl | table-decl` to `document`.

- [ ] **Step 10: Run the full suite and commit**

```
python tools/test_html_sync.py
python tools/test_vocab_shapes.py
python tools/validate_all.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS.

```bash
git add specification/bddo/ docs/superpowers/specs/2026-07-26-hdl-format-dsl-design.md
git commit -m "feat(bddo): add delimited-record primitive for line-oriented text

DelimitedRecords + KeyValueHeader + DelimitedTable locate children by
delimiter position rather than byte offset, covering key=value sidecar
headers and CSV-style grids. Deliberately non-recursive — XML/JSON stay out
of scope. Implements P0-1 of the GDAL survey improvements note."
```

---

### Task 7: P0-1 — HEL string functions

The delimited-record primitive yields string values that must be trimmed and split. HEL's function set is `sizeof`, `len`/`count`, `eof` only. Add the three string functions the primitive needs, plus an explicit String evaluation context.

**Files:**
- Modify: `specification/hel/index.html` (Functions table ~line 126, ABNF ~line 77, Conformance ~line 175, Examples ~line 187)

**Interfaces:**
- Consumes: nothing.
- Produces: `trim(s)`, `substringBefore(s, sep)`, `substringAfter(s, sep)`, `number(s)` — all usable in any HEL expression.

- [ ] **Step 1: Add the functions to the Functions table**

In `specification/hel/index.html`, add these rows to the `<tbody>` of the Functions table (after the `eof()` row):

```html
                    <tr><td><code>trim(string)</code></td><td>The string with leading and trailing whitespace removed.</td></tr>
                    <tr><td><code>substringBefore(string, sep)</code></td><td>The part of <code>string</code> before the first occurrence of <code>sep</code>; the empty string if <code>sep</code> does not occur.</td></tr>
                    <tr><td><code>substringAfter(string, sep)</code></td><td>The part of <code>string</code> after the first occurrence of <code>sep</code>; the empty string if <code>sep</code> does not occur.</td></tr>
                    <tr><td><code>number(string)</code></td><td>The numeric value of <code>string</code>, as Integer when it has no fractional part and Float otherwise. A runtime error if the string is not numeric.</td></tr>
```

- [ ] **Step 2: Add a String evaluation context to Conformance**

In the Conformance `<ol>`, extend item 4 so a String context is normative:

```html
            <li>Yield a Boolean in a boolean context (e.g. <code>bddo:isPresentIf</code>, <code>bddo:repeatUntil</code>, conditions), an Integer in a numeric context (e.g. <code>bddo:sizeFromExpression</code>, <code>bddo:repeatCountFromExpression</code>, <code>bddo:atOffsetFromExpression</code>), and a String in a string context (e.g. a <code>hexplain:valueExpression</code> whose <code>hexplain:valueDatatype</code> is <code>xsd:string</code>).</li>
```

- [ ] **Step 3: Add worked examples**

In the Examples `<dl>`, add:

```html
            <dt>Trimming a delimited header value</dt>
            <dd><pre>hexplain:valueExpression "trim(instance.parent.description)"</pre></dd>
            <dt>Splitting a compound header value</dt>
            <dd><pre>hexplain:valueExpression "number(substringBefore(instance.parent.mapInfo, ','))"</pre></dd>
```

- [ ] **Step 4: Check the ABNF already admits these calls**

Read the `Formal Grammar (ABNF)` block (from line 77). The existing production for a function call is generic — a name followed by a parenthesised argument list. Confirm it admits two-argument calls; if it hardcodes a single argument, change that production to:

```abnf
function-call = name "(" [ expression *( "," expression ) ] ")"
```

Record which case applied in the commit message.

- [ ] **Step 5: Verify nothing regressed**

HEL has no `.ttl`, so no vocabulary gate applies. Run the full suite to confirm the HTML edit did not disturb anything:

```
python tools/validate_all.py
python tools/test_html_sync.py
python tools/test_vocab_shapes.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add specification/hel/index.html
git commit -m "feat(hel): add trim/substringBefore/substringAfter/number and a String context

The delimited-record primitive yields string values that need trimming and
splitting. Completes P0-1 of the GDAL survey improvements note."
```

---

### Task 8: Record P0 completion

Close the loop so the survey and improvements notes reflect what shipped, including the one design change from the proposal (P0-4 uses a rule list, not an expression).

**Files:**
- Modify: `docs/superpowers/notes/2026-08-01-spec-improvements-from-gdal-survey.md`

- [ ] **Step 1: Mark the P0 rows implemented**

In the Summary table, prefix each P0 row's proposal cell with `✅ ` and append a new column note. Under each P0 section, add a status line, e.g.:

```markdown
> **Implemented** on `feat/hdl-p0-spec-extensions` — see
> [the P0 plan](../plans/2026-08-01-hdl-p0-spec-extensions.md).
```

- [ ] **Step 2: Record the P0-4 design change**

In the P0-4 section, replace the `endiannessFromExpression` proposal paragraph with a note that the implementation used the rule-list form:

```markdown
**Implemented as a rule list, not an expression.** `bddo:hasConditionalEndianness` →
an ordered list of `bddo:EndiannessRule` (`bddo:condition` + `bddo:ruleEndianness`),
mirroring the existing `hasConditionalDataType` / `DataTypeRule` idiom. This needs no
conditional operator in HEL, which the `endiannessFromExpression` form would have required.
```

- [ ] **Step 3: Note the remaining follow-up**

Append to the P0-4 section:

```markdown
**Outstanding:** `hexplain-tools/core/src/main/resources/tiff-profile.ttl` still hardcodes
`bddo:LittleEndian` (lines 31, 65, 98). Rewriting it to use `bddo:hasConditionalEndianness`
is a separate change in the `hexplain-tools` repository.
```

- [ ] **Step 4: Run the full suite and commit**

```
python tools/validate_all.py
python tools/test_html_sync.py
python tools/test_vocab_shapes.py
python tools/test_shapes.py
python tools/test_conformance.py
python tools/test_lift.py
```
Expected: all PASS.

```bash
git add docs/superpowers/notes/2026-08-01-spec-improvements-from-gdal-survey.md
git commit -m "docs: mark P0 implemented; record the P0-4 rule-list design change"
```

---

## Self-Review

**Spec coverage.** All four P0 proposals have tasks: P0-1 → Tasks 6 and 7; P0-2 → Task 5; P0-3 → Task 3; P0-4 → Task 4. Tasks 1 and 2 are infrastructure the others depend on; Task 8 closes the documentation loop. P1 and P2 proposals are explicitly out of scope for this plan.

**Deviation from the source note, recorded deliberately.** P0-4 in the improvements note proposed `bddo:endiannessFromExpression` yielding `"big"`/`"little"`, which requires a conditional operator HEL does not have. This plan implements the rule-list form instead — same capability, no HEL change, and consistent with the existing `hasConditionalDataType` idiom. Task 8 records this.

**Type consistency.** `bddo:asciiInteger` is introduced in Task 3 and reused in Task 6's fixtures. `bddo:Field` is the range of every `…FromField` property including the new `dlv:chunk*FromField`. `bddo:condition` is reused by `bddo:EndiannessRule` rather than a new property. `bddo:OffsetBase` individuals (`streamStart`, `streamEnd`, `parentStart`, `currentPosition`) are referenced by `dlv:chunkOffsetBase` with the exact names from `bddo.ttl:109-112`. `dlv:_prefixes` is introduced in Task 5 because `dlv.ttl` has no `sh:declare` yet, mirroring `bddo:_prefixes` at `bddo.ttl:158`.

**Ordering dependency.** Task 2 must precede Tasks 3–6 (they add fixtures its runner consumes). Task 3 must precede Task 6 (`asciiInteger` is used in the delimited fixtures). Tasks 4 and 5 are independent of each other and of Task 6.

**Known risk.** Task 1 Step 2 may reveal `bddo/index.html` drift beyond the known `dlv` case. The step tells the implementer to fix it from the `.ttl` rather than weaken the gate.
