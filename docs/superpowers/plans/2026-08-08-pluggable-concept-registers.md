# Pluggable Concept Registers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all 111 SKOS concepts out of the six aspect vocabularies into six externally-swappable register documents, and add a declared, SHACL-enforced binding that says which register supplies a given property's values.

**Architecture:** Aspects keep properties only and import nothing; registers own their own namespaces; the *profile* declares `hexplain:usesRegister` bindings; one generic SHACL-SPARQL constraint in `core` enforces every binding without codegen. Raw codes (`skos:notation`) leave vocabulary entirely and live only as HDL enum raw values, so `RegisterProvider` is reindexed from the compiled profile instead of the vocabulary graph.

**Tech Stack:** RDF/Turtle (Apache Jena 5.5 in Kotlin; rdflib 7.1.1 + pyshacl in Python), SHACL incl. SPARQL-based constraints, Kotlin 2.2 / Gradle, JUnit 5, Python 3.11.

**Spec:** `docs/superpowers/specs/2026-08-08-pluggable-concept-registers-design.md`

## Global Constraints

- **Two repositories.** Vocabulary, profiles and Python gates are in `d:\work\hexplain.io`; `RegisterProvider` and HEL are in `d:\work\hexplain-tools`.
- **Never `git add -A` in either repo.** Both have substantial unrelated in-flight work from a concurrent effort. Stage only the exact paths a task names.
- **Baseline to preserve:** `./gradlew --offline :hdl:test :core:test` → hdl 153 tests, core 395 tests, 0 failures. `tools/test_conformance.py`, `test_lift.py`, `test_shapes.py`, `test_vocab_shapes.py` all exit 0.
- **Known pre-existing failure, not caused by this work and not to be "fixed" here:** `tools/test_html_sync.py` fails on `bddo.ttl` vs `bddo/index.html` drift.
- **Register namespaces** are exactly `https://hexplain.io/ns/register/<name>#`; files are `specification/register/<name>/<name>.ttl`.
- **Aspect *property* IRIs never change.** Only concept and scheme IRIs move.
- **Clean break:** no `skos:exactMatch` aliases back to old concept IRIs.
- Gradle must be run with `--offline`. If the JVM cannot start (this machine has hit commit-limit exhaustion), stop and report — do not mark a Kotlin task done without a green test run.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `specification/hexplain/core.ttl` | `usesRegister`/`RegisterBinding`/`forProperty`/`register` terms; `hexplain:_prefixes`; the generic enforcement shape | 1, 2 |
| `hexplain-tools/core/.../rdf/vocab/HEXPLAIN.kt` | Kotlin constants for the four new terms | 1 |
| `specification/register/<name>/<name>.ttl` | The six extracted registers (new) | 3 |
| `specification/aspect/<name>/<name>.ttl` | Properties only; concepts/schemes/notations removed; `skos:note` texts de-coupled | 3, 6 |
| `hexplain-tools/core/.../conformance/RegisterProvider.kt` | `ProfileRegisterProvider` indexing profile enum mappings | 4 |
| `specification/profiles/nitf/nitf.hx`, `nitf.ttl`, `example.ttl` | Register IRIs + `usesRegister` declarations | 5 |
| `tools/test_register_bindings.py` | New Python gate for binding enforcement | 2 |

---

### Task 1: Register-binding vocabulary

**Files:**
- Modify: `specification/hexplain/core.ttl`
- Modify: `d:\work\hexplain-tools\core\src\main\kotlin\io\hexplain\core\rdf\vocab\HEXPLAIN.kt`
- Test: `tools/test_vocab_shapes.py` (existing, must stay green), plus a new assertion file `d:\work\hexplain-tools\core\src\test\kotlin\io\hexplain\core\rdf\vocab\RegisterVocabTest.kt`

**Interfaces produced** (every later task consumes these):
- `hexplain:usesRegister`, `hexplain:RegisterBinding`, `hexplain:forProperty`, `hexplain:register`
- Kotlin: `HEXPLAIN.usesRegister`, `HEXPLAIN.RegisterBinding`, `HEXPLAIN.forProperty`, `HEXPLAIN.register`

- [ ] **Step 1: Write the failing Kotlin test.** Create `RegisterVocabTest.kt`:

```kotlin
package io.hexplain.core.rdf.vocab

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class RegisterVocabTest {
    private val ns = "https://hexplain.io/ns/core#"

    @Test fun registerBindingTermsMatchTheNormativeIris() {
        assertEquals(ns + "usesRegister", HEXPLAIN.usesRegister.uri)
        assertEquals(ns + "RegisterBinding", HEXPLAIN.RegisterBinding.uri)
        assertEquals(ns + "forProperty", HEXPLAIN.forProperty.uri)
        assertEquals(ns + "register", HEXPLAIN.register.uri)
    }
}
```

- [ ] **Step 2: Run it and confirm it fails.**

Run (from `d:\work\hexplain-tools`): `./gradlew --offline :core:test --tests '*RegisterVocabTest*'`
Expected: FAIL — `Unresolved reference 'usesRegister'`.

- [ ] **Step 3: Add the terms to `core.ttl`.** Append after the last property declaration, before any shapes section:

```turtle
#################### Register bindings ####################
# A profile states which controlled register supplies the values of a property whose range is
# skos:Concept. Aspects deliberately do NOT import registers -- that absence is what makes a
# register swappable -- so the binding is declared here, per profile, and enforced by
# hexplain:RegisterBindingShape.
hexplain:RegisterBinding a owl:Class ; rdfs:label "register binding" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/core> ;
    rdfs:comment "A statement that one property draws its values from one controlled register." .
hexplain:usesRegister a owl:ObjectProperty ; rdfs:label "uses register" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/core> ; rdfs:range hexplain:RegisterBinding ;
    rdfs:comment "Binds a property used by this profile to the register supplying its values." .
hexplain:forProperty a owl:ObjectProperty ; rdfs:label "for property" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/core> ; rdfs:domain hexplain:RegisterBinding ;
    rdfs:comment "The property being bound." .
hexplain:register a owl:ObjectProperty ; rdfs:label "register" ;
    rdfs:isDefinedBy <https://hexplain.io/ns/core> ; rdfs:domain hexplain:RegisterBinding ;
    rdfs:range skos:ConceptScheme ;
    rdfs:comment "The skos:ConceptScheme whose members are the permitted values." .
```

- [ ] **Step 4: Add the Kotlin constants.** In `HEXPLAIN.kt`, immediately before the closing `}`:

```kotlin
    /** Binds a property to the controlled register supplying its values (on a profile ontology). */
    val usesRegister: Property = m_property("usesRegister")
    /** The property being bound by a hexplain:usesRegister statement. */
    val forProperty: Property = m_property("forProperty")
    /** The skos:ConceptScheme a binding points at. */
    val register: Property = m_property("register")
    /** Class of a register-binding node. */
    val RegisterBinding: Resource = m_resource("RegisterBinding")
```

`m_resource` and `m_property` are the existing private helpers at `HEXPLAIN.kt:19-20`; `HEXPLAIN.ClassMappingRule` (line 24) is the pattern to copy for the class constant.

- [ ] **Step 5: Run both gates.**

Run: `./gradlew --offline :core:test --tests '*RegisterVocabTest*'` → PASS
Run (from `d:\work\hexplain.io`): `python tools/test_vocab_shapes.py` → exit 0

- [ ] **Step 6: Commit.**

```bash
git -C d:/work/hexplain.io add specification/hexplain/core.ttl
git -C d:/work/hexplain.io commit -m "feat(core): add register-binding vocabulary"
git -C d:/work/hexplain-tools add core/src/main/kotlin/io/hexplain/core/rdf/vocab/HEXPLAIN.kt core/src/test/kotlin/io/hexplain/core/rdf/vocab/RegisterVocabTest.kt
git -C d:/work/hexplain-tools commit -m "feat(vocab): Kotlin constants for register bindings"
```

---

### Task 2: Generic SHACL-SPARQL enforcement

**Files:**
- Modify: `specification/hexplain/core.ttl`
- Create: `tools/test_register_bindings.py`
- Create: `specification/hexplain/test/register-binding-valid.ttl`, `.../register-binding-invalid.ttl`

**Interfaces consumed:** the four terms from Task 1.
**Interfaces produced:** `hexplain:RegisterBindingShape`; `hexplain:_prefixes`.

`core.ttl` has no `sh:prefixes` declaration node yet — this task creates one, mirroring `bddo:_prefixes` at `specification/bddo/bddo.ttl:212`.

- [ ] **Step 1: Write the two fixtures.** `specification/hexplain/test/register-binding-valid.ttl`:

```turtle
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix skos:     <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:       <https://example.org/ex#> .
@prefix reg:      <https://example.org/reg#> .

reg:LevelScheme a skos:ConceptScheme .
reg:Secret a skos:Concept ; skos:inScheme reg:LevelScheme .

<https://example.org/profile> hexplain:usesRegister
    [ a hexplain:RegisterBinding ; hexplain:forProperty ex:classification ;
      hexplain:register reg:LevelScheme ] .

ex:dataset1 ex:classification reg:Secret .
```

`register-binding-invalid.ttl` is identical except the last line and an extra concept:

```turtle
reg:Other a skos:Concept ; skos:inScheme reg:OtherScheme .
ex:dataset1 ex:classification reg:Other .
```

- [ ] **Step 2: Write the failing gate.** Create `tools/test_register_bindings.py`:

```python
"""hexplain:usesRegister must be enforced: a value outside the declared register FAILS.

Mirrors tools/test_shapes.py's optional-pyshacl skip so the rdflib-only suite stays green.
"""
import sys
try:
    from pyshacl import validate
except ImportError:
    print("SKIP: pyshacl not installed (optional formal SHACL gate)")
    sys.exit(0)

import rdflib

shapes = rdflib.Graph()
shapes.parse("specification/hexplain/core.ttl", format="turtle")

def conforms(path):
    data = rdflib.Graph()
    data.parse(path, format="turtle")
    ok, _, text = validate(data, shacl_graph=shapes, advanced=True)
    return ok, text

valid_ok, valid_text = conforms("specification/hexplain/test/register-binding-valid.ttl")
invalid_ok, _ = conforms("specification/hexplain/test/register-binding-invalid.ttl")

problems = []
if not valid_ok:
    problems.append("value inside the declared register did NOT conform:\n" + valid_text)
if invalid_ok:
    problems.append("value OUTSIDE the declared register conformed (binding not enforced)")
if problems:
    print("FAIL:\n" + "\n".join(problems))
    sys.exit(1)
print("PASS: register bindings enforced (in-register conforms, out-of-register rejected)")
```

- [ ] **Step 3: Run it and confirm it fails.**

Run: `python tools/test_register_bindings.py`
Expected: FAIL — "value OUTSIDE the declared register conformed (binding not enforced)". (Nothing enforces it yet.)

- [ ] **Step 4: Add the prefix node and the shape to `core.ttl`.**

```turtle
hexplain:_prefixes sh:declare
    [ sh:prefix "hexplain" ; sh:namespace "https://hexplain.io/ns/core#"^^xsd:anyURI ] ,
    [ sh:prefix "skos" ; sh:namespace "http://www.w3.org/2004/02/skos/core#"^^xsd:anyURI ] .

# One shape enforces EVERY hexplain:usesRegister declaration, so adding a binding needs no new
# shape and no generated artifact. Targets exactly those nodes that use a bound property.
hexplain:RegisterBindingShape a sh:NodeShape ;
    sh:target [ a sh:SPARQLTarget ;
        sh:prefixes hexplain:_prefixes ;
        sh:select """SELECT ?this WHERE {
            ?binding hexplain:forProperty ?p .
            ?this ?p ?v .
        }""" ] ;
    sh:sparql [
        sh:message "Value {?value} of {?p} is not skos:inScheme the declared register {?scheme}." ;
        sh:prefixes hexplain:_prefixes ;
        sh:select """SELECT $this ?p ?value ?scheme WHERE {
            ?binding hexplain:forProperty ?p ; hexplain:register ?scheme .
            $this ?p ?value .
            FILTER NOT EXISTS { ?value skos:inScheme ?scheme }
        }""" ] .
```

- [ ] **Step 5: Run the gate again.**

Run: `python tools/test_register_bindings.py`
Expected: PASS.

If the valid fixture fails, the usual cause is `advanced=True` missing (SPARQL constraints are an advanced feature) — it is already set in Step 2.

- [ ] **Step 6: Confirm nothing else regressed.**

Run: `python tools/test_shapes.py && python tools/test_vocab_shapes.py && python tools/test_conformance.py`
Expected: all exit 0.

- [ ] **Step 7: Commit.**

```bash
git add specification/hexplain/core.ttl specification/hexplain/test/register-binding-valid.ttl specification/hexplain/test/register-binding-invalid.ttl tools/test_register_bindings.py
git commit -m "feat(core): enforce register bindings with one generic SHACL-SPARQL shape"
```

---

### Task 3: Extract the six registers

**Files:**
- Create: `specification/register/{us-nato-security,media-encoding,color,checksum,part-role,geometry-type}/<same>.ttl`
- Modify: `specification/aspect/{security,encoding,color,integrity,bundle,geometry}/<same>.ttl`
- Create: `tools/test_register_extraction.py`

**Interfaces produced:** register namespaces `https://hexplain.io/ns/register/<name>#` and their scheme IRIs, consumed by Tasks 5 and 6.

Mapping (source aspect → register name → namespace prefix):

| aspect | register | prefix | schemes | concepts |
|---|---|---|---|---|
| security | `us-nato-security` | `usnato` | 6 | 70 |
| encoding | `media-encoding` | `menc` | 2 | 15 |
| color | `color` | `rcol` | 1 | 4 |
| integrity | `checksum` | `rck` | 1 | 4 |
| bundle | `part-role` | `rpr` | 1 | 12 |
| geometry | `geometry-type` | `rgeo` | 1 | 6 |

- [ ] **Step 1: Write the conservation test FIRST.** Create `tools/test_register_extraction.py`. It asserts the move lost nothing except notations:

```python
"""The extraction must conserve every concept triple: for each aspect, the union of the
trimmed aspect and its new register must equal the ORIGINAL aspect graph, after (a) rewriting
concept/scheme IRIs into the register namespace and (b) removing skos:notation.

Run against git HEAD~1 for the original. Guards a 111-concept mechanical move that no human
will diff line by line.
"""
import subprocess, sys
import rdflib

SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
PAIRS = [("security", "us-nato-security"), ("encoding", "media-encoding"),
         ("color", "color"), ("integrity", "checksum"),
         ("bundle", "part-role"), ("geometry", "geometry-type")]

def original(aspect):
    blob = subprocess.run(
        ["git", "show", f"HEAD:specification/aspect/{aspect}/{aspect}.ttl"],
        capture_output=True, text=True, check=True).stdout
    g = rdflib.Graph(); g.parse(data=blob, format="turtle"); return g

problems = []
for aspect, reg in PAIRS:
    old = original(aspect)
    new = rdflib.Graph(); new.parse(f"specification/aspect/{aspect}/{aspect}.ttl", format="turtle")
    rgraph = rdflib.Graph(); rgraph.parse(f"specification/register/{reg}/{reg}.ttl", format="turtle")

    a_ns = f"https://hexplain.io/ns/aspect/{aspect}#"
    r_ns = f"https://hexplain.io/ns/register/{reg}#"

    def rewrite(t):
        return tuple(rdflib.URIRef(str(x).replace(a_ns, r_ns))
                     if isinstance(x, rdflib.URIRef) else x for x in t)

    old_wanted = {rewrite(t) for t in old if t[1] != SKOS.notation}
    got = set(new) | set(rgraph)
    missing = old_wanted - got
    if missing:
        problems.append(f"{aspect}: {len(missing)} triple(s) lost, e.g. {sorted(missing, key=str)[:3]}")
    # notations must be gone everywhere
    left = [t for t in got if t[1] == SKOS.notation]
    if left:
        problems.append(f"{aspect}: {len(left)} skos:notation triple(s) survived")
    # the aspect must retain NO concepts
    concepts = [s for s in new.subjects(rdflib.RDF.type, SKOS.Concept)]
    if concepts:
        problems.append(f"{aspect}: {len(concepts)} concept(s) still in the aspect")

if problems:
    print("FAIL:\n  " + "\n  ".join(problems)); sys.exit(1)
print(f"PASS: all 6 registers extracted; concepts conserved; notations removed")
```

- [ ] **Step 2: Run it and confirm it fails.**

Run: `python tools/test_register_extraction.py`
Expected: FAIL — the `specification/register/...` files do not exist yet (`FileNotFoundError`). That is the expected red.

- [ ] **Step 3: Extract `security` by hand, as the template.** Create `specification/register/us-nato-security/us-nato-security.ttl` with this header, then move lines 78–182 of `security.ttl` (the six `# ----------` register sections) into it, changing the leading `:` of every concept/scheme to `usnato:` and **deleting every `skos:notation` triple**:

```turtle
# Hexplain Register — US/NATO Security Marking 1.0
# Controlled values for the hx-security aspect, as set by US/NATO policy (EO 12958,
# DOD 5200.1-R, FIPS 10-4). Split out of the aspect so another jurisdiction can publish a
# sibling register without forking the aspect or minting into a namespace it does not own.
# Codes are NOT here: a raw wire code belongs to the format that encodes it, and is carried
# by that profile's HDL enum (e.g. "T"=>usnato:TopSecret in nitf.hx).
@prefix usnato: <https://hexplain.io/ns/register/us-nato-security#> .
@prefix owl:    <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms:<http://purl.org/dc/terms/> .
@prefix vann:   <http://purl.org/vocab/vann/> .

<https://hexplain.io/ns/register/us-nato-security> a owl:Ontology ;
    owl:versionIRI <https://hexplain.io/ns/register/us-nato-security/1.0> ; owl:versionInfo "1.0" ;
    rdfs:label "Hexplain Register — US/NATO Security Marking" ;
    dcterms:created "2026-08-08"^^xsd:date ;
    dcterms:creator <https://geoknoesis.com> ;
    dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
    vann:preferredNamespacePrefix "usnato" ;
    vann:preferredNamespaceUri "https://hexplain.io/ns/register/us-nato-security#" .
```

Every `rdfs:isDefinedBy <https://hexplain.io/ns/aspect/security>` on a moved scheme becomes
`rdfs:isDefinedBy <https://hexplain.io/ns/register/us-nato-security>`.

- [ ] **Step 4: Trim `security.ttl`.** Delete the moved sections. Then fix the 8 advisory notes so they no longer name a scheme that has left the namespace — replace each
`skos:note "Value drawn from asec:XxxScheme."` with the namespace-neutral form, e.g.:

```turtle
    skos:note "Value drawn from the classification-level register bound by the profile (hexplain:usesRegister)." ;
```

Also update the ontology `rdfs:comment` (it currently says "Controlled values are SKOS registers whose skos:notation mirrors the IC ISM / CAPCO wire tokens") to state that controlled values come from a bound external register and that wire tokens live in the profile.

- [ ] **Step 5: Run the conservation test for security only.** Temporarily set `PAIRS` to just `[("security","us-nato-security")]`, run, and expect PASS. Restore `PAIRS` afterwards.

Run: `python tools/test_register_extraction.py`

- [ ] **Step 6: Repeat Steps 3–4 for the remaining five.** Same shape, substituting name/prefix/authority from the table above. For `bundle`, note the register is Hexplain's own vocabulary — say so in the header comment rather than citing an external authority. `bundle` and `geometry` have no notations to remove.

- [ ] **Step 7: Keep `bundle`'s SHACL constraint working (interim).**

`specification/aspect/bundle/bundle.ttl:108` hard-codes `sh:hasValue :PartRoleScheme`. Once Step 6
moves that scheme into the `part-role` register, `:PartRoleScheme` resolves to an aspect-namespace IRI
that no longer exists, and `tools/test_shapes.py` starts failing. Task 6 will delete this clause and
replace it with a register binding, but that task depends on the generic shape from Task 2 — so until
then, repoint the constraint rather than leaving the tree broken across three tasks:

- add `@prefix rpr: <https://hexplain.io/ns/register/part-role#> .` to `bundle.ttl`'s prefixes
- change `sh:hasValue :PartRoleScheme` to `sh:hasValue rpr:PartRoleScheme`
- leave the surrounding `sh:property`/`sh:message` clause otherwise untouched

Add a comment on the clause: `# INTERIM: replaced by a hexplain:usesRegister binding in Task 6.`

- [ ] **Step 8: Run the conservation test and every gate this task can break.**

Run: `python tools/test_register_extraction.py` → PASS (all 6)
Run: `python tools/test_vocab_shapes.py` → exit 0
Run: `python tools/test_shapes.py` → exit 0 (this is the gate Step 7 protects; if it fails, the
`rpr:` repoint is wrong)
Run: `python tools/test_conformance.py` → exit 0

- [ ] **Step 9: Commit.**

```bash
git add specification/register specification/aspect tools/test_register_extraction.py
git commit -m "refactor(spec): extract concept registers out of the six aspects"
```

---

### Task 4: Reindex `RegisterProvider` from profile enums

**Files:**
- Modify: `d:\work\hexplain-tools\core\src\main\kotlin\io\hexplain\core\conformance\RegisterProvider.kt`
- Modify: `d:\work\hexplain-tools\core\src\test\kotlin\io\hexplain\core\conformance\ConformanceEndToEndTest.kt`
- Test: `d:\work\hexplain-tools\core\src\test\kotlin\io\hexplain\core\conformance\ProfileRegisterProviderTest.kt` (create)

**Interfaces consumed:** none from earlier tasks.
**Interfaces produced:** `class ProfileRegisterProvider(model: Model) : RegisterProvider`.

`SkosRegisterProvider` indexes `skos:notation`, which no longer exists after Task 3, so `inRegister()` would never match. The new provider indexes the *profile's* enum mappings instead. Keep `SkosRegisterProvider` — it is still correct for any register that does publish notations — and add the new class beside it.

- [ ] **Step 1: Write the failing test.** Create `ProfileRegisterProviderTest.kt`:

```kotlin
package io.hexplain.core.conformance

import org.apache.jena.rdf.model.ModelFactory
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ProfileRegisterProviderTest {
    private val ttl = """
        @prefix bddo: <https://hexplain.io/ns/bddo#> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix usnato: <https://hexplain.io/ns/register/us-nato-security#> .
        @prefix p: <https://example.org/p#> .

        usnato:TopSecret a skos:Concept ; skos:inScheme usnato:ClassificationLevelScheme .
        usnato:Secret    a skos:Concept ; skos:inScheme usnato:ClassificationLevelScheme .

        p:CLAS a bddo:Field ; bddo:enumeration [
            a bddo:Enumeration ;
            bddo:hasEnumValue [ a bddo:EnumValue ; bddo:enumRawValue "T" ; bddo:enumSymbol usnato:TopSecret ] ,
                              [ a bddo:EnumValue ; bddo:enumRawValue "S" ; bddo:enumSymbol usnato:Secret ] ] .
    """.trimIndent()

    private val scheme = "https://hexplain.io/ns/register/us-nato-security#ClassificationLevelScheme"

    private fun provider(): RegisterProvider {
        val m = ModelFactory.createDefaultModel()
        m.read(ttl.byteInputStream(), null, "TTL")
        return ProfileRegisterProvider(m)
    }

    @Test fun aCodeMappedByTheProfileIsInTheRegister() {
        assertTrue(provider().contains(scheme, "T"))
        assertTrue(provider().contains(scheme, "S"))
    }

    @Test fun anUnmappedCodeIsNot() {
        assertFalse(provider().contains(scheme, "X"))
    }

    @Test fun whitespaceIsTrimmedLikeTheOtherProviders() {
        assertTrue(provider().contains(scheme, " T "))
    }
}
```

- [ ] **Step 2: Run it and confirm it fails.**

Run: `./gradlew --offline :core:test --tests '*ProfileRegisterProviderTest*'`
Expected: FAIL — `Unresolved reference 'ProfileRegisterProvider'`.

- [ ] **Step 3: Implement.** Append to `RegisterProvider.kt`:

```kotlin
/**
 * Reads membership from a compiled PROFILE rather than from the register vocabulary.
 *
 * Registers carry no skos:notation: a raw wire code belongs to the format that encodes it, not
 * to the shared concept (a format spelling Top Secret as "TS" would otherwise contradict the
 * register). The profile's enum mapping is therefore the only place a code binds to a concept,
 * and it is what this indexes: enumRawValue -> enumSymbol -> the symbol's skos:inScheme.
 *
 * Consequence, by design: a code is "in" a register only if some loaded profile maps it.
 */
class ProfileRegisterProvider(model: Model) : RegisterProvider {

    private val codesByScheme: Map<String, Set<String>> = buildIndex(model)

    override fun contains(schemeUri: String, value: String): Boolean =
        codesByScheme[schemeUri]?.contains(value.trim()) == true

    private fun buildIndex(model: Model): Map<String, Set<String>> {
        val bddo = "https://hexplain.io/ns/bddo#"
        val rawValue = ResourceFactory.createProperty(bddo + "enumRawValue")
        val symbol = ResourceFactory.createProperty(bddo + "enumSymbol")
        val inScheme = ResourceFactory.createProperty(SkosRegisterProvider.SKOS_NS + "inScheme")
        val index = mutableMapOf<String, MutableSet<String>>()
        val values = model.listStatements(null, symbol, null as org.apache.jena.rdf.model.RDFNode?)
        while (values.hasNext()) {
            val st = values.nextStatement()
            val concept = st.`object`.asResource()
            val code = st.subject.getProperty(rawValue)?.`object`?.asLiteral()?.string?.trim() ?: continue
            val schemes = concept.listProperties(inScheme)
            while (schemes.hasNext()) {
                val schemeUri = schemes.nextStatement().`object`.asResource().uri ?: continue
                index.getOrPut(schemeUri) { mutableSetOf() }.add(code)
            }
        }
        return index
    }
}
```

- [ ] **Step 4: Run the new test.**

Run: `./gradlew --offline :core:test --tests '*ProfileRegisterProviderTest*'` → PASS

- [ ] **Step 5: Point the end-to-end conformance test at the new provider.** In `ConformanceEndToEndTest.kt:22` the fixture is `MapRegisterProvider(mapOf(classScheme to setOf("U","R","C","S","T")))`. Leave `MapRegisterProvider` in place (it is the documented in-memory provider for tests) but add one test proving the profile-backed path works end to end: build a model containing both the register concepts and a profile enum as in Step 1, pass `ProfileRegisterProvider`, and assert an `inRegister(...)` assertion evaluates true.

- [ ] **Step 6: Run the whole Kotlin suite.**

Run: `./gradlew --offline :hdl:test :core:test`
Expected: BUILD SUCCESSFUL, hdl 153, core 400, 0 failures — 395 baseline + 1 (`RegisterVocabTest`, Task 1) + 3 (`ProfileRegisterProviderTest`) + 1 (end-to-end, Step 5). Confirm counts from `build-root/*/test-results/test/*.xml`; "BUILD SUCCESSFUL" alone is not evidence, because an up-to-date task runs no tests.

- [ ] **Step 7: Commit.**

```bash
git -C d:/work/hexplain-tools add core/src/main/kotlin/io/hexplain/core/conformance/RegisterProvider.kt core/src/test/kotlin/io/hexplain/core/conformance/
git -C d:/work/hexplain-tools commit -m "feat(conformance): index register membership from profile enum mappings"
```

---

### Task 5: Migrate the NITF profile

**Files:**
- Modify: `specification/profiles/nitf/nitf.hx`, `nitf.ttl`, `example.ttl`
- Modify: `specification/gv/geo.ttl` (prefix declaration only — it has no concept references)

**Interfaces consumed:** register namespaces from Task 3; `hexplain:usesRegister` from Task 1.

- [ ] **Step 1: Rewrite concept references in `nitf.hx`.** Change the `use` line and all 21 enum symbols:

```
use usnato: <https://hexplain.io/ns/register/us-nato-security#>
```

and each `"T"=>asec:TopSecret` becomes `"T"=>usnato:TopSecret`, etc. The `means asec:classification` property references are **unchanged** — only concepts moved.

- [ ] **Step 2: Compile and confirm zero diagnostics.**

Run (from `d:\work\hexplain-tools`):
`./gradlew -q --offline :hdl:run --args="D:/work/hexplain.io/specification/profiles/nitf/nitf.hx -o D:/tmp/nitf.check.ttl"`
Expected: exit 0, no stderr diagnostics.

- [ ] **Step 3: Rewrite `nitf.ttl` and `example.ttl` the same way**, then add the binding declarations to `nitf.ttl`'s ontology header — one per bound property (`asec:classification`, `asec:declassificationType`, `asec:declassificationExemption`, `asec:downgradeTo`, `asec:classificationAuthorityType`, `asec:classificationReason`):

```turtle
<https://hexplain.io/ns/profile/nitf> hexplain:usesRegister
    [ a hexplain:RegisterBinding ; hexplain:forProperty asec:classification ;
      hexplain:register usnato:ClassificationLevelScheme ] ,
    [ a hexplain:RegisterBinding ; hexplain:forProperty asec:declassificationType ;
      hexplain:register usnato:DeclassTypeScheme ] ,
    [ a hexplain:RegisterBinding ; hexplain:forProperty asec:declassificationExemption ;
      hexplain:register usnato:ExemptionScheme ] ,
    [ a hexplain:RegisterBinding ; hexplain:forProperty asec:downgradeTo ;
      hexplain:register usnato:ClassificationLevelScheme ] ,
    [ a hexplain:RegisterBinding ; hexplain:forProperty asec:classificationAuthorityType ;
      hexplain:register usnato:AuthorityTypeScheme ] ,
    [ a hexplain:RegisterBinding ; hexplain:forProperty asec:classificationReason ;
      hexplain:register usnato:ClassificationReasonScheme ] .
```

Add `@prefix hexplain:` and `@prefix usnato:` to `nitf.ttl` if absent.

- [ ] **Step 4: In `geo.ttl`, delete the now-dangling `@prefix asec:` line** if nothing else uses it, and update the line-44 comment that says "classificationLevel in asec:" to name the property, not a concept.

- [ ] **Step 5: Run the profile gates.**

Run: `python tools/test_conformance.py` → exit 0
Run: `python tools/test_lift.py` → exit 0
Run: `python tools/test_register_bindings.py` → exit 0

- [ ] **Step 6: Run the round-trip gate and record the numbers.**

Run: `python tools/test_hx_roundtrip.py`
Expected: it will still FAIL (that is pre-existing and out of scope), but `UNEXPLAINED` must not be **worse** than the pre-task figure of 264 differing-subject baseline. Record the before/after counts in the commit message. If UNEXPLAINED rises, the enum symbol rewrite is inconsistent between `.hx` and `.ttl` — fix before committing.

- [ ] **Step 7: Commit.**

```bash
git add specification/profiles/nitf/nitf.hx specification/profiles/nitf/nitf.ttl specification/profiles/nitf/example.ttl specification/gv/geo.ttl
git commit -m "refactor(nitf): draw security concepts from the us-nato-security register"
```

---

### Task 6: Convert `bundle`'s hard-coded constraint to a binding

**Files:**
- Modify: `specification/aspect/bundle/bundle.ttl` (remove lines 108–109's `sh:node`/`sh:message`)
- Modify: `specification/profiles/shapefile/*.ttl` (whichever declares the profile ontology)

`bundle.ttl:108` currently hard-codes `sh:property [ sh:path skos:inScheme ; sh:hasValue :PartRoleScheme ]`. After Task 3 that scheme lives in the `part-role` register, so the constraint both dangles and contradicts pluggability.

- [ ] **Step 1: Confirm the current constraint is load-bearing.** Run `python tools/test_shapes.py` and check it passes; then temporarily change the shapefile invalid fixture's `abnd:partRole` to a non-register value and confirm the suite still fails. Restore the fixture.

- [ ] **Step 2: Delete the `sh:node`/`sh:message` clause** at `bundle.ttl:108-109`, leaving the rest of the `abnd:partRole` property shape intact.

- [ ] **Step 3: Add the equivalent binding** to the shapefile profile's ontology node:

```turtle
<https://hexplain.io/ns/profile/shapefile> hexplain:usesRegister
    [ a hexplain:RegisterBinding ; hexplain:forProperty abnd:partRole ;
      hexplain:register rpr:PartRoleScheme ] .
```

- [ ] **Step 4: Run the shapes gate.**

Run: `python tools/test_shapes.py`
Expected: exit 0 — the valid fixture conforms and the invalid one still fails, now via the generic shape rather than the hard-coded one.

- [ ] **Step 5: Commit.**

```bash
git add specification/aspect/bundle/bundle.ttl specification/profiles/shapefile
git commit -m "refactor(bundle): express the part-role constraint as a register binding"
```

---

### Task 7: Full verification

- [ ] **Step 1: Kotlin suites.**

Run (from `d:\work\hexplain-tools`): `./gradlew --offline :hdl:test :core:test`
Expected: BUILD SUCCESSFUL, 0 failures. Read the counts out of `build-root/hdl/test-results/test/*.xml` and `build-root/core/test-results/test/*.xml` — do not trust "BUILD SUCCESSFUL" alone, an up-to-date task runs no tests.

- [ ] **Step 2: Every Python gate.**

```bash
for t in test_conformance test_lift test_shapes test_vocab_shapes test_register_bindings test_register_extraction test_hx_roundtrip; do
  echo -n "$t: "; python tools/$t.py >/dev/null 2>&1; echo "exit=$?"
done
```

Expected: all `exit=0` except `test_hx_roundtrip` (pre-existing failure, out of scope) and `test_html_sync` (pre-existing, not in the list).

- [ ] **Step 3: Prove pluggability with a throwaway.** Write a second register `/tmp/eu-security.ttl` declaring `eu:LevelScheme` with one concept, point a copy of the valid fixture at it, and confirm it conforms without touching any aspect file. Delete both afterwards. This is the acceptance test for the whole change — if it needs an aspect edit, the design was not achieved.

- [ ] **Step 4: Confirm no stray files and only intended paths staged.**

```bash
git -C d:/work/hexplain.io status --short
git -C d:/work/hexplain-tools status --short
```

Expected: no `hs_err_*.log`, no `.kotlin/`, and the concurrent effort's unrelated modifications still present and unstaged.

---

## Self-Review

**Spec coverage.** §1 architecture → Task 3. §2 vocabulary → Task 1. §3 enforcement → Task 2, with `bundle` migrated in Task 6. §4 migration → Tasks 3 and 5. §5 `RegisterProvider` → Task 4. §6 testing → the test step inside every task plus Task 7. The spec's "prove a sibling register works" intent is Task 7 Step 3.

**Ordering.** 1 → 2 (the shape needs the terms). 3 is independent of 1–2 and could run first, but is placed after so the enforcement mechanism exists before anything depends on it. 5 needs 3 (register IRIs) and 1 (binding terms). 6 needs 2, 3 and 5's pattern. 7 is last.

**Type consistency.** `ProfileRegisterProvider(model: Model) : RegisterProvider` with `contains(schemeUri: String, value: String): Boolean` is used identically in Task 4's test and implementation, and matches the existing `RegisterProvider` interface. `SkosRegisterProvider.SKOS_NS` is referenced from the new class and does exist as a `companion object const`. The four vocabulary terms are spelled identically in Tasks 1, 2, 5 and 6.

**Known gap, deliberately left:** `test_hx_roundtrip.py` will still fail after this plan. Its residual is the NITF SecurityMarking "Step 3" flattening and the TRE payload files, both explicitly out of scope in the spec.
