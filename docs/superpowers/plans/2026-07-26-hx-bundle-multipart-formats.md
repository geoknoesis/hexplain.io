# hx-bundle: Multi-File Format Modeling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an aspect that models any format made of multiple physical files (shapefile, glTF, DASH, split archives) as one logical `abnd:Asset` whose unified semantics are the lifted union of its parts' aspect facets.

**Architecture:** New base aspect `hx-bundle` (imports nothing) defines `Asset`/`Part`, four `BindingKind` individuals, a SKOS part-role register, and a `BundleProfile`/`PartSpec` format-template layer. A single SHACL SPARQL rule lifts each part's content-aspect properties onto the Asset, where "content-aspect" is *derived* from the profile's `carriesAspect` + `rdfs:isDefinedBy` (no coupling to any specific aspect). The existing `apkg` (containment) is folded in as a `Containment`-bound specialization. One worked profile (Esri Shapefile) proves the model end-to-end.

**Tech Stack:** RDF 1.1 Turtle, OWL 2, SHACL (+ SHACL-AF rules), SKOS. Validation via Python `rdflib` 7.1.1 (already installed); no new runtime dependency. `pyshacl` is an optional formal check only.

## Global Constraints

Copied verbatim from the family architecture (`specification/architecture/index.html`) and project memory. Every task's requirements implicitly include this section.

- **Pre-release, all modules v1.0.** No `owl:priorVersion`, no change-log, no `(was X)` backrefs, no deprecation, no backward-compatibility layer. New terms are defined directly.
- **Imports point only downward** (the import graph is a DAG). Aspects never import siblings. `hx-bundle` imports nothing. `apkg` MAY import `hx-bundle` (downward edge — legal).
- **One concept, one home.** No duplicated term across modules. If two modules would need a term, it belongs in the more general module both reference.
- **Aspect naming:** namespace `https://hexplain.io/ns/aspect/<name>#`, ontology label `hx-<name>`, preferred prefix carries a leading `a`.
- **Registers** are open `skos:ConceptScheme`s hosted inside the aspect that references them; concepts use `skos:inScheme` + `skos:topConceptOf` + `skos:prefLabel …@en` (+ `skos:notation` where a short code exists).
- **Value modelling:** controlled vocabulary → object property with `rdfs:range skos:Concept` → concept in a register; closed small enum for reasoning → `owl:NamedIndividual` + SHACL `sh:in`; computable scalar → literal + SHACL.
- **Reuse external vocabularies at the leaf** (`dcterms:`, PROV, SOSA/SSN, ODRL, dcat, GeoSPARQL) via `skos:closeMatch`/`owl:equivalentProperty` rather than minting parallels.
- **Ontology boilerplate** (every `owl:Ontology`): `owl:versionIRI <…/1.0>`, `owl:versionInfo "1.0"`, `dcterms:created "2026-07-26"^^xsd:date`, `dcterms:creator <https://geoknoesis.com>`, `dcterms:license <https://creativecommons.org/licenses/by/4.0/>`, `vann:preferredNamespacePrefix`, `vann:preferredNamespaceUri`.
- **Per-task gate:** every touched `.ttl` parses as Turtle **and** no term is duplicated across modules. Behavior tasks additionally run their SPARQL check green.
- **Term reference check (must match the existing ontologies exactly):**
  `ageom:geometryType` (range `skos:Concept`; values incl. `ageom:MultiLineString`, `ageom:LineString`, `ageom:Point`) · `ageom:dimensionality` · `asref:wktString` · `asref:epsgCode` · `atab:rowCount` · `atab:hasField`/`atab:Field`/`atab:fieldName`/`atab:fieldDataType` · `aenc:` has **no** charset/codepage property (do not invent one) · `bddo:Struct` exists, no dBASE layout individual exists. Aspect ontology IRIs (for `carriesAspect`/`isDefinedBy`) are the **slash** forms, e.g. `<https://hexplain.io/ns/aspect/geometry>` (no `#`).

---

## File Structure

**Created**
- `specification/aspect/bundle/bundle.ttl` — the `hx-bundle` aspect: vocabulary, binding-kind enum, part-role register, profile/partspec terms, and (added incrementally) the lift rule + conformance shapes.
- `specification/profiles/shapefile/shapefile.ttl` — the Esri Shapefile `BundleProfile` (reusable format definition). Seeds the family's `profiles/` area.
- `specification/profiles/shapefile/example.ttl` — a valid worked instance (`roads.*`) used as the behavior-test fixture.
- `specification/profiles/shapefile/example-invalid.ttl` — an instance missing the required `.shp` part (negative fixture for conformance).
- `tools/test_lift.py` — rdflib script: loads the composed graph, runs the authored lift CONSTRUCT, asserts Asset-level facets appear.
- `tools/test_conformance.py` — rdflib script: runs the authored required-parts SELECT, asserts 0 violations for the valid instance and ≥1 for the invalid one.
- `tools/validate_all.py` — rdflib script: parses every `.ttl` in `specification/` (family-wide parse regression).

**Modified**
- `specification/aspect/packaging/packaging.ttl` — add `owl:imports` bundle + three subclass/subproperty axioms (fold-in).
- `specification/architecture/index.html` — §3.7 (hx-bundle as container-tier base), §4 (dependency shape), §5 (profiles note).

---

## Task 1: `hx-bundle` core vocabulary, binding enum, role register

**Files:**
- Create: `specification/aspect/bundle/bundle.ttl`

**Interfaces:**
- Produces (classes): `abnd:Asset`, `abnd:Part`, `abnd:BindingKind`, `abnd:BundleProfile`, `abnd:PartSpec`.
- Produces (properties): `abnd:hasPart` (Asset→Part), `abnd:partOf` (inverse), `abnd:primaryPart` (⊑hasPart), `abnd:partRole` (Part→skos:Concept), `abnd:boundBy` (Asset→BindingKind), `abnd:partIndex` (Part→nonNegativeInteger), `abnd:stem` (Asset→string), `abnd:partSpec` (BundleProfile→PartSpec), `abnd:carriesAspect` (PartSpec→owl:Ontology), `abnd:describedBy` (PartSpec→bddo:Struct), `abnd:required` (PartSpec→boolean), `abnd:extension` (PartSpec→string), `abnd:primary` (PartSpec→boolean).
- Produces (individuals): `abnd:Containment`, `abnd:NamingConvention`, `abnd:ManifestReference`, `abnd:Concatenation`.
- Produces (register): `abnd:PartRoleScheme` with concepts `abnd:GeometryCarrier`, `abnd:AttributeTable`, `abnd:SpatialReference`, `abnd:CharacterEncoding`, `abnd:SpatialIndex`, `abnd:Manifest`, `abnd:Segment`, `abnd:Sidecar`, `abnd:Metadata`, `abnd:Thumbnail`, `abnd:Checksum`, `abnd:Payload`.

- [ ] **Step 1: Write the failing parse test**

Run (from repo root `d:\work\hexplain.io`):

```
python -c "import rdflib; g=rdflib.Graph(); g.parse('specification/aspect/bundle/bundle.ttl', format='turtle'); print('triples', len(g))"
```

Expected: FAIL — `FileNotFoundError` (the file does not exist yet).

- [ ] **Step 2: Create `specification/aspect/bundle/bundle.ttl`**

```turtle
# Hexplain Aspect — Bundle (hx-bundle) 1.0
# Base container-tier aspect: one logical Asset realized by N physical Parts, bound by
# containment / naming-convention / manifest-reference / concatenation. Imports nothing.
# Unified semantics: each Part carries an aspect facet; a SHACL rule lifts those facets
# onto the Asset (see LiftByCarriedAspectRule, added with the profile layer).
@prefix :        <https://hexplain.io/ns/aspect/bundle#> .
@prefix abnd:    <https://hexplain.io/ns/aspect/bundle#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix sh:      <http://www.w3.org/ns/shacl#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix dcat:    <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann:    <http://purl.org/vocab/vann/> .

<https://hexplain.io/ns/aspect/bundle> a owl:Ontology ;
    owl:versionIRI <https://hexplain.io/ns/aspect/bundle/1.0> ; owl:versionInfo "1.0" ;
    rdfs:label "Hexplain Aspect — Bundle (hx-bundle)" ;
    rdfs:comment "Base aspect for multi-part assets: one logical Asset realized by N physical Parts, bound by containment, naming-convention, manifest-reference, or concatenation. Part aspect facets lift onto the Asset for a unified semantic view." ;
    dcterms:created "2026-07-26"^^xsd:date ; dcterms:creator <https://geoknoesis.com> ;
    dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
    vann:preferredNamespacePrefix "abnd" ; vann:preferredNamespaceUri "https://hexplain.io/ns/aspect/bundle#" .

# ---------- Classes ----------
:Asset a owl:Class ; rdfs:label "Asset" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    skos:closeMatch dcat:Dataset ;
    rdfs:comment "A logical resource realized by one or more physical Parts. The single unified semantic subject." .
:Part a owl:Class ; rdfs:label "Part" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:comment "One physical carrier (a byte stream / file) contributing to an Asset. Composes with hx-fsmeta and BDDO at instance level." .
:BindingKind a owl:Class ; rdfs:label "Binding Kind" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:comment "The mechanism binding an Asset's Parts. Closed enumeration." .
:BundleProfile a owl:Class ; rdfs:label "Bundle Profile" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:comment "A reusable format template: its binding kind plus the set of expected member PartSpecs." .
:PartSpec a owl:Class ; rdfs:label "Part Spec" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:comment "One expected member of a BundleProfile: role, extension, requiredness, and the aspect it carries." .

# ---------- Instance-level properties ----------
:hasPart a owl:ObjectProperty ; rdfs:label "has part" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range :Part ; owl:inverseOf :partOf .
:partOf a owl:ObjectProperty ; rdfs:label "part of" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range :Asset .
:primaryPart a owl:ObjectProperty ; rdfs:label "primary part" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:subPropertyOf :hasPart ; rdfs:range :Part ;
    rdfs:comment "The recognition anchor / manifest part (e.g. .shp, .gltf, .mpd)." .
:partRole a owl:ObjectProperty ; rdfs:label "part role" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range skos:Concept ; rdfs:comment "The role a Part or PartSpec plays, from abnd:PartRoleScheme." .
:boundBy a owl:ObjectProperty ; rdfs:label "bound by" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range :BindingKind .
:partIndex a owl:DatatypeProperty ; rdfs:label "part index" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range xsd:nonNegativeInteger ; rdfs:comment "Ordinal of a Part within a segmented/concatenated Asset." .
:stem a owl:DatatypeProperty ; rdfs:label "stem" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range xsd:string ; rdfs:comment "Shared basename of a naming-convention bundle (e.g. \"roads\")." .

# ---------- Profile-level properties ----------
:partSpec a owl:ObjectProperty ; rdfs:label "part spec" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range :PartSpec .
:carriesAspect a owl:ObjectProperty ; rdfs:label "carries aspect" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range owl:Ontology ;
    rdfs:comment "The aspect ontology whose properties this part contributes. Drives facet lifting. An annotation-style link, NOT an owl:import — orthogonality is preserved." .
:describedBy a owl:ObjectProperty ; rdfs:label "described by" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range <https://hexplain.io/ns/bddo#Struct> ;
    rdfs:comment "The BDDO byte-layout struct describing this part's bytes (optional)." .
:required a owl:DatatypeProperty ; rdfs:label "required" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range xsd:boolean .
:extension a owl:DatatypeProperty ; rdfs:label "extension" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range xsd:string ; rdfs:comment "Filename extension identifying this member (e.g. \".dbf\")." .
:primary a owl:DatatypeProperty ; rdfs:label "primary" ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:range xsd:boolean ; rdfs:comment "Marks the PartSpec whose instance is the Asset's primaryPart." .

# ---------- Binding-kind enumeration (NamedIndividual + sh:in) ----------
:Containment a owl:NamedIndividual, :BindingKind ; rdfs:label "Containment" ;
    rdfs:comment "Parts are physically nested inside one byte stream (ZIP, TAR)." .
:NamingConvention a owl:NamedIndividual, :BindingKind ; rdfs:label "Naming Convention" ;
    rdfs:comment "Sibling files sharing a stem, one role per extension (Shapefile, ENVI)." .
:ManifestReference a owl:NamedIndividual, :BindingKind ; rdfs:label "Manifest Reference" ;
    rdfs:comment "A primary part references members by path/URI (glTF, DASH, HLS, VRT)." .
:Concatenation a owl:NamedIndividual, :BindingKind ; rdfs:label "Concatenation" ;
    rdfs:comment "Parts are ordered fragments of one logical byte stream (multi-volume archives)." .

# ---------- Part-role register (SKOS, open) ----------
:PartRoleScheme a skos:ConceptScheme ; rdfs:isDefinedBy <https://hexplain.io/ns/aspect/bundle> ;
    skos:prefLabel "Part Role Register"@en .
:GeometryCarrier   a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Geometry carrier"@en .
:AttributeTable    a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Attribute table"@en .
:SpatialReference  a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Spatial reference"@en .
:CharacterEncoding a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Character encoding"@en .
:SpatialIndex      a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Spatial index"@en .
:Manifest          a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Manifest"@en .
:Segment           a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Segment"@en .
:Sidecar           a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Sidecar"@en .
:Metadata          a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Metadata"@en .
:Thumbnail         a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Thumbnail"@en .
:Checksum          a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Checksum"@en .
:Payload           a skos:Concept ; skos:inScheme :PartRoleScheme ; skos:topConceptOf :PartRoleScheme ; skos:prefLabel "Payload"@en .

# ---------- Structural SHACL ----------
:AssetShape a sh:NodeShape ; sh:targetClass :Asset ;
    sh:property [ sh:path :boundBy ; sh:maxCount 1 ;
        sh:in ( :Containment :NamingConvention :ManifestReference :Concatenation ) ;
        sh:message "abnd:boundBy must be one of the four BindingKind individuals." ] ;
    sh:property [ sh:path :primaryPart ; sh:maxCount 1 ; sh:class :Part ;
        sh:message "An Asset has at most one primaryPart." ] .
:PartShape a sh:NodeShape ; sh:targetClass :Part ;
    sh:property [ sh:path :partRole ; sh:class skos:Concept ;
        sh:message "abnd:partRole must be a skos:Concept (from abnd:PartRoleScheme)." ] .
```

- [ ] **Step 3: Run the parse test to verify it passes**

Run:

```
python -c "import rdflib; g=rdflib.Graph(); g.parse('specification/aspect/bundle/bundle.ttl', format='turtle'); print('triples', len(g))"
```

Expected: PASS — prints e.g. `triples 140` (any positive number; no traceback).

- [ ] **Step 4: Verify no duplicated term (one-concept-one-home)**

Run:

```
python -c "import rdflib; g=rdflib.Graph(); g.parse('specification/aspect/bundle/bundle.ttl',format='turtle'); B='https://hexplain.io/ns/aspect/bundle#'; ext=[str(s) for s in set(g.subjects()) if str(s).startswith('http') and not str(s).startswith(B) and 'shacl' not in str(s) and 'skos' not in str(s) and 'w3.org' not in str(s) and 'purl.org' not in str(s) and 'qudt' not in str(s)]; print('external subjects defined here (should be []):', ext)"
```

Expected: PASS — prints `external subjects defined here (should be []): []` (the aspect defines only `abnd:` terms).

- [ ] **Step 5: Commit**

```
git add specification/aspect/bundle/bundle.ttl
git commit -m "feat(bundle): add hx-bundle aspect vocabulary, binding enum, role register"
```

---

## Task 2: Fold `apkg` in as a Containment-bound specialization

**Files:**
- Modify: `specification/aspect/packaging/packaging.ttl`

**Interfaces:**
- Consumes: `abnd:Asset`, `abnd:Part`, `abnd:hasPart` (Task 1).
- Produces: `apkg:Container ⊑ abnd:Asset`, `apkg:Entry ⊑ abnd:Part`, `apkg:hasEntry ⊑ abnd:hasPart`; `apkg` now `owl:imports` bundle.

- [ ] **Step 1: Write the failing subclass test**

Run:

```
python -c "import rdflib; from rdflib import RDFS; g=rdflib.Graph(); [g.parse(f,format='turtle') for f in ['specification/aspect/bundle/bundle.ttl','specification/aspect/packaging/packaging.ttl']]; C=rdflib.URIRef('https://hexplain.io/ns/aspect/packaging#Container'); A=rdflib.URIRef('https://hexplain.io/ns/aspect/bundle#Asset'); print('Container subClassOf Asset:', (C,RDFS.subClassOf,A) in g)"
```

Expected: FAIL — prints `Container subClassOf Asset: False`.

- [ ] **Step 2: Add the import + alignment axioms to `packaging.ttl`**

In `specification/aspect/packaging/packaging.ttl`, add `abnd` to the prefix block (after the `apkg:` line, line 5):

```turtle
@prefix abnd:   <https://hexplain.io/ns/aspect/bundle#> .
```

Add `owl:imports` to the ontology header — change the existing header block (the `<https://hexplain.io/ns/aspect/packaging> a owl:Ontology ;` statement) so it includes, right after the `owl:versionInfo "1.0" ;` line:

```turtle
    owl:imports <https://hexplain.io/ns/aspect/bundle> ;
```

Append the alignment axioms after the last term (after the `:entryPath` line):

```turtle
# ---------- Bundle alignment: containment is one binding kind ----------
:Container rdfs:subClassOf abnd:Asset .
:Entry     rdfs:subClassOf abnd:Part .
:hasEntry  rdfs:subPropertyOf abnd:hasPart .
```

- [ ] **Step 3: Run the subclass test to verify it passes**

Run the same command as Step 1.

Expected: PASS — prints `Container subClassOf Asset: True`.

- [ ] **Step 4: Verify the downstream consumer still parses (blast-radius check)**

Run:

```
python -c "import rdflib; [rdflib.Graph().parse(f,format='turtle') for f in ['specification/aspect/packaging/packaging.ttl','specification/axv/archive.ttl']]; print('packaging + axv parse OK')"
```

Expected: PASS — prints `packaging + axv parse OK`.

- [ ] **Step 5: Commit**

```
git add specification/aspect/packaging/packaging.ttl
git commit -m "feat(packaging): fold apkg Container/Entry under abnd:Asset/Part"
```

---

## Task 3: Esri Shapefile profile + worked instance fixtures

**Files:**
- Create: `specification/profiles/shapefile/shapefile.ttl`
- Create: `specification/profiles/shapefile/example.ttl`
- Create: `specification/profiles/shapefile/example-invalid.ttl`

**Interfaces:**
- Consumes: `abnd:BundleProfile`, `abnd:PartSpec`, `abnd:partSpec`, `abnd:boundBy`, `abnd:NamingConvention`, `abnd:partRole`, `abnd:carriesAspect`, `abnd:required`, `abnd:extension`, `abnd:primary`, the role concepts, `abnd:Asset`, `abnd:Part`, `abnd:hasPart`, `abnd:primaryPart`, `abnd:stem` (Task 1); aspect terms `ageom:geometryType`/`ageom:dimensionality`/`ageom:MultiLineString`, `asref:wktString`/`asref:epsgCode`, `atab:rowCount`/`atab:hasField`/`atab:fieldName`/`atab:fieldDataType`, `afs:fileName`.
- Produces: `fmt:Shapefile` (a `BundleProfile`); instance `ex:roads` (valid); instance `ex:roads_broken` (missing `.shp`).

- [ ] **Step 1: Write the failing parse test**

Run:

```
python -c "import rdflib; [rdflib.Graph().parse(f,format='turtle') for f in ['specification/profiles/shapefile/shapefile.ttl','specification/profiles/shapefile/example.ttl','specification/profiles/shapefile/example-invalid.ttl']]; print('shapefile artifacts parse OK')"
```

Expected: FAIL — `FileNotFoundError`.

- [ ] **Step 2: Create `specification/profiles/shapefile/shapefile.ttl`**

```turtle
# Hexplain Profile — Esri Shapefile 1.0
# A naming-convention BundleProfile: sibling files sharing a stem, one role per extension.
# Imports hx-bundle; references (does not import) the aspects each part carries.
@prefix fmt:     <https://hexplain.io/ns/profile/shapefile#> .
@prefix abnd:    <https://hexplain.io/ns/aspect/bundle#> .
@prefix owl:     <http://www.w3.org/2002/07/owl#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix vann:    <http://purl.org/vocab/vann/> .

<https://hexplain.io/ns/profile/shapefile> a owl:Ontology ;
    owl:versionIRI <https://hexplain.io/ns/profile/shapefile/1.0> ; owl:versionInfo "1.0" ;
    owl:imports <https://hexplain.io/ns/aspect/bundle> ;
    rdfs:label "Hexplain Profile — Esri Shapefile" ;
    rdfs:comment "Multi-file vector format: .shp geometry + .shx index + .dbf attributes (+ .prj CRS, .cpg code page), bound by shared basename." ;
    dcterms:created "2026-07-26"^^xsd:date ; dcterms:creator <https://geoknoesis.com> ;
    dcterms:license <https://creativecommons.org/licenses/by/4.0/> ;
    vann:preferredNamespacePrefix "fmt" ; vann:preferredNamespaceUri "https://hexplain.io/ns/profile/shapefile#" .

fmt:Shapefile a abnd:BundleProfile ; rdfs:label "Esri Shapefile" ;
    abnd:boundBy abnd:NamingConvention ;
    abnd:partSpec fmt:shpSpec , fmt:shxSpec , fmt:dbfSpec , fmt:prjSpec , fmt:cpgSpec .

fmt:shpSpec a abnd:PartSpec ; abnd:extension ".shp" ; abnd:partRole abnd:GeometryCarrier ;
    abnd:required true ; abnd:primary true ; abnd:carriesAspect <https://hexplain.io/ns/aspect/geometry> .
fmt:shxSpec a abnd:PartSpec ; abnd:extension ".shx" ; abnd:partRole abnd:SpatialIndex ;
    abnd:required true .
fmt:dbfSpec a abnd:PartSpec ; abnd:extension ".dbf" ; abnd:partRole abnd:AttributeTable ;
    abnd:required true ; abnd:carriesAspect <https://hexplain.io/ns/aspect/tabular> .
fmt:prjSpec a abnd:PartSpec ; abnd:extension ".prj" ; abnd:partRole abnd:SpatialReference ;
    abnd:required false ; abnd:carriesAspect <https://hexplain.io/ns/aspect/spatialref> .
fmt:cpgSpec a abnd:PartSpec ; abnd:extension ".cpg" ; abnd:partRole abnd:CharacterEncoding ;
    abnd:required false .
# Note: .cpg carries a code page; hx-encoding has no charset property yet, so no aspect is
# declared for it and nothing lifts from it. Add carriesAspect once aenc mints a charset term.
```

- [ ] **Step 3: Create `specification/profiles/shapefile/example.ttl` (valid instance)**

```turtle
# Worked instance: roads.* — a complete, valid Shapefile Asset.
@prefix ex:      <https://example.org/data/> .
@prefix abnd:    <https://hexplain.io/ns/aspect/bundle#> .
@prefix fmt:     <https://hexplain.io/ns/profile/shapefile#> .
@prefix ageom:   <https://hexplain.io/ns/aspect/geometry#> .
@prefix asref:   <https://hexplain.io/ns/aspect/spatialref#> .
@prefix atab:    <https://hexplain.io/ns/aspect/tabular#> .
@prefix afs:     <https://hexplain.io/ns/aspect/fsmeta#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

ex:roads a abnd:Asset ; dcterms:conformsTo fmt:Shapefile ;
    abnd:boundBy abnd:NamingConvention ; abnd:stem "roads" ;
    abnd:primaryPart ex:roads.shp ;
    abnd:hasPart ex:roads.shp , ex:roads.shx , ex:roads.dbf , ex:roads.prj , ex:roads.cpg .

ex:roads.shp a abnd:Part ; abnd:partRole abnd:GeometryCarrier ; afs:fileName "roads.shp" ;
    ageom:geometryType ageom:MultiLineString ; ageom:dimensionality 2 .
ex:roads.shx a abnd:Part ; abnd:partRole abnd:SpatialIndex ; afs:fileName "roads.shx" .
ex:roads.dbf a abnd:Part ; abnd:partRole abnd:AttributeTable ; afs:fileName "roads.dbf" ;
    atab:rowCount 1200 ; atab:hasField [ atab:fieldName "NAME" ; atab:fieldDataType "C" ] .
ex:roads.prj a abnd:Part ; abnd:partRole abnd:SpatialReference ; afs:fileName "roads.prj" ;
    asref:wktString "GEOGCS[\"WGS 84\",DATUM[\"WGS_1984\"]]" ; asref:epsgCode 4326 .
ex:roads.cpg a abnd:Part ; abnd:partRole abnd:CharacterEncoding ; afs:fileName "roads.cpg" .
```

- [ ] **Step 4: Create `specification/profiles/shapefile/example-invalid.ttl` (missing required .shp)**

```turtle
# Negative fixture: a Shapefile Asset missing its required .shp geometry part.
@prefix ex:      <https://example.org/data/> .
@prefix abnd:    <https://hexplain.io/ns/aspect/bundle#> .
@prefix fmt:     <https://hexplain.io/ns/profile/shapefile#> .
@prefix afs:     <https://hexplain.io/ns/aspect/fsmeta#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

ex:roads_broken a abnd:Asset ; dcterms:conformsTo fmt:Shapefile ;
    abnd:boundBy abnd:NamingConvention ; abnd:stem "roads_broken" ;
    abnd:hasPart ex:roads_broken.shx , ex:roads_broken.dbf .

ex:roads_broken.shx a abnd:Part ; abnd:partRole abnd:SpatialIndex ; afs:fileName "roads_broken.shx" .
ex:roads_broken.dbf a abnd:Part ; abnd:partRole abnd:AttributeTable ; afs:fileName "roads_broken.dbf" .
```

- [ ] **Step 5: Run the parse test to verify it passes**

Run the Step 1 command.

Expected: PASS — prints `shapefile artifacts parse OK`.

- [ ] **Step 6: Commit**

```
git add specification/profiles/shapefile/
git commit -m "feat(profiles): add Esri Shapefile profile and worked instance fixtures"
```

---

## Task 4: Facet-lifting rule + behavior test

**Files:**
- Modify: `specification/aspect/bundle/bundle.ttl` (append the lift rule)
- Create: `tools/test_lift.py`

**Interfaces:**
- Consumes: everything from Tasks 1 & 3.
- Produces: `abnd:LiftByCarriedAspectRule` (a `sh:NodeShape` with an `sh:SPARQLRule`) whose CONSTRUCT lifts, for each Asset, the properties its parts carry that are `rdfs:isDefinedBy` the aspect the profile's matching `PartSpec` declares via `carriesAspect`.

- [ ] **Step 1: Write the failing behavior test — `tools/test_lift.py`**

```python
"""Verify the bundle lift rule projects part aspect facets onto the Asset.
Extracts the authored sh:construct query from bundle.ttl and runs it over the
composed graph (bundle + referenced aspects + shapefile profile + instance),
so the test exercises the real normative query. rdflib only; no pyshacl needed.
"""
import sys
import rdflib

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
FILES = [
    "specification/aspect/bundle/bundle.ttl",
    "specification/aspect/geometry/geometry.ttl",
    "specification/aspect/spatialref/spatialref.ttl",
    "specification/aspect/tabular/tabular.ttl",
    "specification/profiles/shapefile/shapefile.ttl",
    "specification/profiles/shapefile/example.ttl",
]

g = rdflib.Graph()
for f in FILES:
    g.parse(f, format="turtle")

# Pull the authored CONSTRUCT text out of the lift rule.
construct = None
for _, _, q in g.triples((None, SH.construct, None)):
    construct = str(q)
if construct is None:
    print("FAIL: no sh:construct rule found in bundle.ttl")
    sys.exit(1)

# Apply the rule: run the CONSTRUCT and merge results back in ($this acts as a free var).
for triple in g.query(construct):
    g.add(triple)

roads = rdflib.URIRef("https://example.org/data/roads")
AGEOM = rdflib.Namespace("https://hexplain.io/ns/aspect/geometry#")
ASREF = rdflib.Namespace("https://hexplain.io/ns/aspect/spatialref#")
ATAB = rdflib.Namespace("https://hexplain.io/ns/aspect/tabular#")

checks = [
    (roads, AGEOM.geometryType, AGEOM.MultiLineString),  # lifted from .shp
    (roads, ASREF.epsgCode, rdflib.Literal(4326, datatype=rdflib.XSD.positiveInteger)),  # from .prj
    (roads, ATAB.rowCount, rdflib.Literal(1200, datatype=rdflib.XSD.unsignedLong)),  # from .dbf
]
missing = [c for c in checks if c not in g]

# Negative: fsmeta filename must NOT lift (no PartSpec declares afs as a carried aspect).
AFS = rdflib.Namespace("https://hexplain.io/ns/aspect/fsmeta#")
leaked = list(g.triples((roads, AFS.fileName, None)))

if missing:
    print("FAIL: not lifted onto Asset:", missing)
    sys.exit(1)
if leaked:
    print("FAIL: physical afs:fileName leaked onto Asset:", leaked)
    sys.exit(1)
print("PASS: aspect facets lifted onto Asset; physical properties did not leak")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```
python tools/test_lift.py
```

Expected: FAIL — prints `FAIL: no sh:construct rule found in bundle.ttl` and exits non-zero (the rule is not authored yet).

- [ ] **Step 3: Append the lift rule to `bundle.ttl`**

Add at the end of `specification/aspect/bundle/bundle.ttl`:

```turtle
# ---------- Facet lifting (SHACL-AF rule) ----------
# For each Asset, lift the properties its parts carry that are defined by the aspect the
# profile's matching PartSpec declares via carriesAspect. Full IRIs so it runs identically
# under pyshacl and standalone rdflib. Requires the referenced aspect ontologies in the graph.
:LiftByCarriedAspectRule a sh:NodeShape ; sh:targetClass :Asset ;
    sh:rule [ a sh:SPARQLRule ;
        rdfs:label "Lift part facets onto the Asset" ;
        sh:construct """
CONSTRUCT { $this ?p ?v }
WHERE {
  $this <https://hexplain.io/ns/aspect/bundle#hasPart> ?part .
  ?part <https://hexplain.io/ns/aspect/bundle#partRole> ?role ; ?p ?v .
  $this <http://purl.org/dc/terms/conformsTo> ?profile .
  ?profile <https://hexplain.io/ns/aspect/bundle#partSpec> ?spec .
  ?spec <https://hexplain.io/ns/aspect/bundle#partRole> ?role ;
        <https://hexplain.io/ns/aspect/bundle#carriesAspect> ?aspect .
  ?p <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> ?aspect .
}
""" ] .
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```
python tools/test_lift.py
```

Expected: PASS — prints `PASS: aspect facets lifted onto Asset; physical properties did not leak`.

- [ ] **Step 5: Commit**

```
git add specification/aspect/bundle/bundle.ttl tools/test_lift.py
git commit -m "feat(bundle): add carriesAspect-derived facet-lifting rule + test"
```

---

## Task 5: Profile conformance shape + behavior test

**Files:**
- Modify: `specification/aspect/bundle/bundle.ttl` (append the required-parts constraint)
- Create: `tools/test_conformance.py`

**Interfaces:**
- Consumes: everything from Tasks 1 & 3.
- Produces: `abnd:RequiredPartsShape` (a `sh:NodeShape` with an `sh:SPARQLConstraint`) that flags any Asset whose conformed profile has a `required` PartSpec role not present among its parts.

- [ ] **Step 1: Write the failing behavior test — `tools/test_conformance.py`**

```python
"""Verify the required-parts conformance constraint.
Extracts the authored sh:select from bundle.ttl and runs it over each instance:
the valid roads.* yields zero violation rows; the .shp-less instance yields >=1.
rdflib only.
"""
import sys
import rdflib

SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
BASE = [
    "specification/aspect/bundle/bundle.ttl",
    "specification/profiles/shapefile/shapefile.ttl",
]

# Grab the authored SELECT from the constraint.
gb = rdflib.Graph()
for f in BASE:
    gb.parse(f, format="turtle")
select = None
for _, _, q in gb.triples((None, SH.select, None)):
    select = str(q)
if select is None:
    print("FAIL: no sh:select constraint found in bundle.ttl")
    sys.exit(1)

def violations(instance_file):
    g = rdflib.Graph()
    for f in BASE + [instance_file]:
        g.parse(f, format="turtle")
    return list(g.query(select))

valid = violations("specification/profiles/shapefile/example.ttl")
invalid = violations("specification/profiles/shapefile/example-invalid.ttl")

if valid:
    print("FAIL: valid instance reported violations:", valid)
    sys.exit(1)
if not invalid:
    print("FAIL: invalid instance (missing .shp) reported no violation")
    sys.exit(1)
print(f"PASS: valid=0 violations, invalid={len(invalid)} violation(s)")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```
python tools/test_conformance.py
```

Expected: FAIL — prints `FAIL: no sh:select constraint found in bundle.ttl` and exits non-zero.

- [ ] **Step 3: Append the conformance constraint to `bundle.ttl`**

Add at the end of `specification/aspect/bundle/bundle.ttl`:

```turtle
# ---------- Profile conformance (required parts present) ----------
:RequiredPartsShape a sh:NodeShape ; sh:targetClass :Asset ;
    sh:sparql [ a sh:SPARQLConstraint ;
        sh:message "A required part role declared by the conformed profile is missing." ;
        sh:select """
SELECT $this ?role
WHERE {
  $this <http://purl.org/dc/terms/conformsTo> ?profile .
  ?profile <https://hexplain.io/ns/aspect/bundle#partSpec> ?spec .
  ?spec <https://hexplain.io/ns/aspect/bundle#required> true ;
        <https://hexplain.io/ns/aspect/bundle#partRole> ?role .
  FILTER NOT EXISTS {
    $this <https://hexplain.io/ns/aspect/bundle#hasPart> ?p .
    ?p <https://hexplain.io/ns/aspect/bundle#partRole> ?role .
  }
}
""" ] .
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```
python tools/test_conformance.py
```

Expected: PASS — prints `PASS: valid=0 violations, invalid=1 violation(s)`.

- [ ] **Step 5: Commit**

```
git add specification/aspect/bundle/bundle.ttl tools/test_conformance.py
git commit -m "feat(bundle): add required-parts conformance constraint + test"
```

---

## Task 6: Architecture-doc updates + family-wide parse regression

**Files:**
- Modify: `specification/architecture/index.html`
- Create: `tools/validate_all.py`

**Interfaces:**
- Consumes: the finished `bundle.ttl` and `packaging.ttl`.
- Produces: `tools/validate_all.py` (parses every `.ttl` under `specification/`).

- [ ] **Step 1: Write the failing family-parse test — `tools/validate_all.py`**

```python
"""Parse every .ttl under specification/ — the family-wide regression gate."""
import glob
import sys
import rdflib

failures = []
files = sorted(glob.glob("specification/**/*.ttl", recursive=True))
for f in files:
    try:
        rdflib.Graph().parse(f, format="turtle")
    except Exception as e:  # noqa: BLE001 — report any parse failure
        failures.append((f, str(e)))

if failures:
    for f, e in failures:
        print("FAIL", f, "->", e)
    sys.exit(1)
print(f"PASS: all {len(files)} ttl files parse")
```

- [ ] **Step 2: Run it — confirm the whole family (including new files) parses**

Run:

```
python tools/validate_all.py
```

Expected: PASS — prints `PASS: all <N> ttl files parse`. (If any pre-existing file fails, stop and investigate before continuing — the new work must not have broken a sibling.)

- [ ] **Step 3: Update the architecture document**

In `specification/architecture/index.html`, §3.7 table (the "Container & system" table, currently starting with the `hx-packaging` row), add a new first row **above** the `hx-packaging` row:

```html
                <tr><td><code>hx-bundle</code> ✓</td><td>multi-part asset: N carriers → 1 logical Asset</td><td>Asset, Part, hasPart, primaryPart, partRole ▸reg, boundBy {containment∣naming∣manifest∣concatenation}, BundleProfile, PartSpec, carriesAspect</td></tr>
```

Then change the existing `hx-packaging` row's key-terms cell to note it now refines bundle — replace its `<td>hasEntry, entryPath, entryOffset, memberOf</td>` with:

```html
<td>hasEntry (⊑abnd:hasPart), entryPath — Container ⊑ abnd:Asset (Containment binding)</td>
```

In §4 "Dependency Shape", update the container line of the `<pre>` block. Replace the line:

```
   … hx-time, hx-encoding, hx-spatialref, hx-provenance, hx-security, … are independent siblings
```

with:

```
   … hx-time, hx-encoding, hx-spatialref, hx-provenance, hx-security, … are independent siblings
hx-bundle  (container-tier base)  ◀── hx-packaging refines it (Container = Containment-bound Asset)
```

In §5 "Domains as Compositions", add this row to the table (after the `AXV` row):

```html
                <tr><td><b>Shapefile</b> <span class="note">(profile)</span></td><td>bundle + geometry + tabular + spatialref</td><td>PartSpecs (.shp/.shx/.dbf/.prj/.cpg), NamingConvention binding</td></tr>
```

- [ ] **Step 4: Verify the architecture HTML still opens and contains the edits**

Run:

```
python -c "t=open('specification/architecture/index.html',encoding='utf-8').read(); assert 'hx-bundle' in t and 'Containment-bound' in t and 'Shapefile' in t, 'architecture edits missing'; print('architecture doc updated OK')"
```

Expected: PASS — prints `architecture doc updated OK`.

- [ ] **Step 5: Re-run all three test scripts as a final gate**

Run:

```
python tools/validate_all.py && python tools/test_lift.py && python tools/test_conformance.py
```

Expected: three PASS lines, no non-zero exit.

- [ ] **Step 6: Commit**

```
git add specification/architecture/index.html tools/validate_all.py
git commit -m "docs(architecture): register hx-bundle in catalogue + family parse gate"
```

---

## Self-Review

**1. Spec coverage** (checking the design doc section-by-section):
- §2/§4 aspect + classes/properties → Task 1. ✓
- §5 four binding kinds (NamedIndividual + sh:in) → Task 1 (enum) + `AssetShape`. ✓
- §5.1 apkg fold-in → Task 2. ✓
- §6 role register → Task 1. ✓
- §7 BundleProfile/PartSpec/carriesAspect/describedBy → Task 1 (terms) + Task 3 (shapefile use). ✓
- §8 lift rule (carriesAspect-derived) → Task 4. ✓
- §9.1 shapefile worked example → Task 3 + Tasks 4/5 tests. ✓
- §9.2 glTF / §9.3 multi-volume ZIP → illustrative only in the spec; NOT built here (YAGNI — one worked profile). Called out in §13 as future. ✓ (no gap)
- §10 SHACL conformance (required parts, primaryPart cardinality, roles in register) → `RequiredPartsShape` (Task 5) + `AssetShape`/`PartShape` (Task 1). ✓
- §11 blast radius / align-only fallback → Task 2 Step 4 verifies AXV; fallback documented, not implemented (full fold-in chosen). ✓
- §12 architecture-doc updates → Task 6. ✓
- §13 out-of-scope items → intentionally omitted. ✓

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N". Every TTL block and test is complete. ✓

**3. Type consistency:** Property/class/individual names are identical across Tasks 1→3→4→5 (`abnd:hasPart`, `abnd:partRole`, `abnd:carriesAspect`, `abnd:partSpec`, `abnd:required`, role concepts, binding individuals). Aspect terms match the real ontologies verified pre-plan (`ageom:MultiLineString`, `asref:epsgCode` typed `xsd:positiveInteger`, `atab:rowCount` typed `xsd:unsignedLong` — reflected in the test's typed literals). Aspect IRIs in `carriesAspect` use the slash form matching `rdfs:isDefinedBy` in the source ontologies. ✓

**One risk flagged for the implementer:** the lift test compares typed literals (`4326^^xsd:positiveInteger`, `1200^^xsd:unsignedLong`). If rdflib normalizes a literal differently, prefer asserting the predicate exists on the Asset (`(roads, ASREF.epsgCode, None) in g` via `g.value`) over exact-literal equality. The datatypes above are copied from the source ontologies, so exact match is expected to hold.
