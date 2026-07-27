# Design — Security Marking aspect (hx-security), full ISM-aligned

**Status:** approved design, pending spec review
**Date:** 2026-07-27
**Author:** Stephane Fellah / Geoknoesis LLC
**Motivation:** NITF completeness surfaced that `aspect/security` defines exactly one property (`asec:classificationLevel`), while NITF's security block carries ~16 marking attributes. Security marking is cross-cutting (every classified format needs it), so it belongs in the aspect layer, not a NITF-specific vocabulary. Filling it advances the whole framework and is a core GEOINT differentiator.

## 1. Goal & locked decisions

Extend the Hexplain **security-marking aspect** (`asec`) to full marking coverage, aligned to the IC Information Security Marking (ISM) semantics, with controlled values as inline SKOS registers.

Locked (via brainstorming):
- **Scope:** full NITF-security-block parity — all ~16 marking attributes, so every `FSCLAS…FSCTLN` / `ISCLAS…ISCTLN` field can lift.
- **Alignment:** IC ISM / CAPCO — reuse ISM attribute semantics; controlled values modeled as SKOS concepts whose `skos:notation` mirrors the ISM/NITF wire tokens.
- **Structure:** flat, composable properties (matching every other aspect); no `SecurityMarking` node.
- **SHACL:** none in the aspect (matches the `encoding`/`security` convention; profile-layer shapes validate).

## 2. Convention followed (from `aspect/encoding/encoding.ttl`)

- Controlled-value property → `rdfs:range skos:Concept`, with a note naming its register.
- Register → an inline `skos:ConceptScheme` (`rdfs:isDefinedBy` the ontology).
- Value → `skos:Concept ; skos:inScheme <scheme> ; skos:topConceptOf <scheme> ; skos:prefLabel …@en ; skos:notation "<wire token>"` (+ `skos:altLabel`, `skos:exactMatch`/`skos:seeAlso` where a citable external exists).
- `skos:Collection` groups concepts for convenience.

The physical→semantic bridge already exists: `bddo:EnumValue` has `enumRawValue` + `enumSymbol` (an IRI). So a profile enum value `"U"` gains `bddo:enumSymbol asec:Unclassified`, and the field's `hexplain:mapsToProperty asec:classification` lifts the resolved concept. **That enum enrichment + field mapping is a downstream profile task (§7), not part of this aspect module.**

## 3. Architecture & files

- **Extend in place:** `specification/aspect/security/security.ttl` — add the 15 new properties and the SKOS registers inline; bump `owl:versionInfo` to `1.1`.
- Keep the namespace/prefix (`asec` / `https://hexplain.io/ns/aspect/security#`), `dcterms:creator`, CC-BY-4.0.
- If the registers later outgrow the file, they may split into `security-register.ttl` — deferred; inline for now to match `encoding.ttl`.

## 4. Properties (16, = NITF security block 1:1)

Value-controlled properties are `owl:ObjectProperty` ranging over `skos:Concept`; free-text/temporal are `owl:DatatypeProperty`.

| `asec:` property | kind / range | register (§5) | NITF field(s) |
|---|---|---|---|
| `classification` *(new)* | Object → Concept | ClassificationLevel | FSCLAS/ISCLAS/SSCLAS/TSCLAS/DECLAS/RECLAS |
| `classificationLevel` *(existing, keep)* | Datatype → xsd:string | — | verbatim level marking |
| `classificationSystem` | Datatype → xsd:string | — | FSCLSY (FIPS 10-4 / "XN") |
| `compartment` *(repeatable)* | Object → Concept | Marking | FSCODE codewords |
| `controlAndHandling` *(repeatable)* | Object → Concept | Marking | FSCTLH |
| `releasableTo` *(repeatable)* | Datatype → xsd:string | *(country — deferred)* | FSREL |
| `declassificationType` | Object → Concept | DeclassType | FSDCTP |
| `declassificationDate` | Datatype → xsd:date | — | FSDCDT |
| `declassificationExemption` | Object → Concept | Exemption | FSDCXM |
| `downgradeTo` | Object → Concept | ClassificationLevel | FSDG |
| `downgradeDate` | Datatype → xsd:date | — | FSDGDT |
| `classificationText` | Datatype → xsd:string | — | FSCLTX |
| `classificationAuthorityType` | Object → Concept | AuthorityType | FSCATP |
| `classificationAuthority` | Datatype → xsd:string | — | FSCAUT |
| `classificationReason` | Object → Concept | ClassificationReason | FSCRSN |
| `securitySourceDate` | Datatype → xsd:date | — | FSSRDT |
| `securityControlNumber` | Datatype → xsd:string | — | FSCTLN |

Every property: `rdfs:label`, `rdfs:isDefinedBy <…/aspect/security>`, `rdfs:comment`. Repeatable properties noted as such in comments (no OWL cardinality; cardinality is a profile concern).

**Backward compatibility:** `classificationLevel` (string, verbatim marking) is retained; `classification` (concept, interoperable) is added alongside. Existing consumers and the current NITF `FSCLAS→classificationLevel` mapping keep working; the concept form is additive.

## 5. SKOS registers (inline, ISM-aligned)

All concept IRIs under the `asec:` namespace. `skos:notation` mirrors the wire token. Values enumerated below so the plan can transcribe them verbatim.

### 5.1 `asec:ClassificationLevelScheme`
`Unclassified` "U", `Restricted` "R", `Confidential` "C", `Secret` "S", `TopSecret` "T".

### 5.2 `asec:MarkingScheme` (Table A-4 digraphs)
One scheme; `skos:notation` = digraph, `skos:prefLabel` = full name. Concepts (notation): ATOMAL `AT`, CNWDI `CN`, COPYRIGHT `PX`, COSMIC `CS`, CRYPTO `CR`, EFTO `TX`, FORMREST-DATA `RF`, FOUO `FO`, GENSER `GS`, LIMOFFUSE `LU`, LIMDIS `DS`, NATO `NS`, NOCONTRACT `NC`, NONCOMPARTMENT `NT`, ORCON `OR`, PERSONAL-DATA `IN`, PROPIN `PI`, RESTRICTED-DATA `RD`, SAO `SA`, SAO-1 `SL`, SAO-2 `HA`, SAO-3 `HB`, SAO-SI-2 `SK`, SAO-SI-3 `HC`, SAO-SI-4 `HD`, SIOP `SH`, SIOP-ESI `SE`, SPECIAL-CONTROL `SC`, SPECIAL-INTEL `SI`, US-ONLY `UO`, WARNING-NOTICE `WN`, WNINTEL `WI`.
`skos:Collection`s group them **indicatively** (grouping is advisory — Table A-4 mixes categories and warns values change): `Compartments` (ATOMAL, COSMIC, CRYPTO, SAO*, SIOP*, SPECIAL-INTEL/CONTROL, CNWDI, RESTRICTED-DATA), `DisseminationControls` (ORCON, PROPIN, US-ONLY, NOCONTRACT, WNINTEL, EFTO), `HandlingCaveats` (FOUO, LIMDIS, LIMOFFUSE, PERSONAL-DATA, NONCOMPARTMENT, FORMREST-DATA, GENSER, NATO, COPYRIGHT, WARNING-NOTICE). Concepts that resist clean assignment stay ungrouped (still `inScheme`).

### 5.3 `asec:DeclassTypeScheme`
`DeclassifyOnDate` "DD", `DeclassifyOnEvent` "DE", `DowngradeOnDate` "GD", `DowngradeOnEvent` "GE", `OADR` "O", `ExemptFromAutomatic` "X".

### 5.4 `asec:AuthorityTypeScheme`
`Original` "O", `DerivativeSingle` "D", `DerivativeMultiple` "M".

### 5.5 `asec:ClassificationReasonScheme`
`ReasonA` "A" … `ReasonG` "G" (correspond to EO 12958 §1.5(a)–(g); `skos:comment` cites the order).

### 5.6 `asec:ExemptionScheme`
`X1`…`X8` (DOD 5200.1-R ¶4-202b(1)-(8)) and `X251`…`X259` (¶4-301a(1)-(9)); notation = the token; `skos:comment` cites the regulation.

## 6. "ISM-aligned" — honesty caveat

There is **no official ISM RDF namespace** to `skos:exactMatch` against; IC ISM is an XML-attribute specification (ISM.XML) governed by CAPCO CVE value lists. "Aligned to ISM" therefore means: concept semantics and `skos:notation` tokens **mirror the ISM/CAPCO values**, and each register/concept cites the governing authority via `rdfs:seeAlso`/`skos:note` (DoDM 5200.01, CAPCO Register, EO 12958, DOD 5200.1-R). The value lists change on CAPCO's cadence; the aspect carries `owl:versionInfo "1.1"` and the registers can be re-versioned independently. No ISM concept IRIs are invented or asserted as canonical.

## 7. Downstream consumer (NITF binding) — separate follow-on, out of scope here

To make NITF actually lift into this aspect (a later profile task, its own spec/plan):
- Enrich the profile's security enums: add `bddo:enumSymbol` on each `EnumValue` → the matching `asec` concept (e.g. `enumRawValue "S"` → `asec:Secret`; declass-type/authority/reason enums likewise). This requires first adding those enums to the profile (only `FSCLASEnum` exists today).
- Add `hexplain:mapsToProperty` on the 16 security fields (per §4's right column) for both the file-header `FS*` block and the image `IS*` block (and later GS/TS/DES/RES).
- Add the aspect's raster/security/etc. to the harness ONT only if new vocab files are referenced (security.ttl is already loaded).

## 8. Scope guard (non-goals)

- No `asec:SecurityMarking` node (flat properties only).
- No SHACL shapes in the aspect (matches convention; profile-layer shapes validate).
- No country/releasability register — `releasableTo` stays a string token; a country register is future work.
- The NITF profile binding (§7) is a separate deliverable, not this module.
- No invented ISM RDF URIs; mirror-tokens-and-cite only.
- NSIF/NATO-specific marking sets beyond Table A-4 are out of scope for cut #1.

## 9. Build sequence (for the implementation plan)

1. Bump `security.ttl` ontology metadata to `1.1`; keep existing `classificationLevel`.
2. Add the 15 new properties (§4) with labels/comments.
3. Add the six SKOS registers (§5) with all enumerated concepts + notations + citations.
4. Validate: `python tools/shacl_check.py specification/aspect/security/security.ttl` conforms (no new shapes; SKOS structure only — confirm it parses and the existing bddo/core shapes find nothing to fault).
5. Sanity: confirm the NITF profile still validates unchanged (it already loads security.ttl via the harness ONT).
