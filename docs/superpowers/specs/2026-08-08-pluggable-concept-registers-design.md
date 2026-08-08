# Pluggable Concept Registers — Design

**Date:** 2026-08-08
**Status:** Approved, not yet implemented
**Affects:** `specification/aspect/*`, new `specification/register/*`, `specification/hexplain/core.ttl`, `hexplain-tools` (`RegisterProvider`), the NITF profile

## Problem

The aspect vocabularies bundle two different things in one document: the **properties** that describe a
concern (`asec:classification`, `abnd:partRole`) and the **concept registers** that supply those
properties' values (`asec:TopSecret`, `abnd:GeometryCarrier`).

For most aspects that is merely untidy. For `security` it is a correctness problem: its registers encode
US/NATO classification policy — EO 12958, DOD 5200.1-R, FIPS 10-4 — so an aspect that presents itself as
"security" can only serve one jurisdiction. A second jurisdiction cannot supply its own levels without
either forking the aspect or minting concepts into a namespace it does not own.

A related leak sits in `skos:notation`. 96 notations across the aspects carry single-character codes, and
their provenance is mixed: `ReasonA skos:notation "A"` follows EO 12958 §1.5(a), but
`TopSecret skos:notation "T"` and `Oadr skos:notation "O"` are NITF field encodings — the US standard
writes "TOP SECRET". A format encoding Top Secret as `"TS"` would contradict the register.

### What is already true

The properties are **not** hard-wired to their registers. Every one is `rdfs:range skos:Concept`, with the
scheme named only in an advisory `skos:note` ("Value drawn from asec:ClassificationLevelScheme.", 8
occurrences in `security.ttl`). There are **zero** `rdfs:range` references to a scheme. Only one place in
the whole specification enforces scheme membership: `specification/aspect/bundle/bundle.ttl:108`, a SHACL
`sh:hasValue :PartRoleScheme`.

So the registers are not wired in — they are only *packaged* together. The work is therefore mostly
repackaging plus a declaration mechanism, not a mechanism rewrite.

## Decisions

Each was decided explicitly during design; the rationale is recorded so a later reader does not re-open
them by accident.

1. **Scope: all six aspects that carry registers**, not security alone. It was noted during design that
   only `security` has genuine jurisdictional variance — `encoding` (H264/HEVC), `color` (BT601/BT709),
   `integrity` (CRC32/MD5) and `geometry` (Point/LineString) are universal standards, and
   `bundle`'s `PartRoleScheme` is Hexplain's own vocabulary. Uniform structure was chosen over
   variance-driven scoping anyway, so that every aspect reads the same way and no future author has to
   judge which rule applies.
2. **Clean break on concept IRIs.** Registers move to namespaces they own; the old aspect-namespace
   concept IRIs are retired outright, with no `skos:exactMatch` alias period. Every reference is rewritten
   in the same change.
3. **Bindings are declared and enforced.** A profile states which register supplies each bound property,
   and SHACL rejects values from anywhere else.
4. **The profile owns the code.** Registers become code-free: all 96 `skos:notation` values are deleted
   from vocabulary and re-expressed as HDL enum raw values in the profile that reads them.
5. **`inRegister()` is reindexed, not retired.** See §5.

## 1. Architecture

An aspect keeps its properties and **does not** import any register — that absence is what makes the
register pluggable. The profile supplies the binding.

```
specification/aspect/security/security.ttl        properties only; rdfs:range skos:Concept (unchanged)
specification/register/us-nato-security/          the 6 schemes + 70 concepts, own namespace
```

Registers live at `https://hexplain.io/ns/register/<name>#` and are grouped **one register per aspect**,
not one per scheme: a jurisdiction replaces its six security schemes together, so splitting them into six
documents would create six things that must always be swapped in lockstep.

File layout mirrors `specification/aspect/<name>/<name>.ttl` exactly:
`specification/register/<name>/<name>.ttl`, e.g.
`specification/register/us-nato-security/us-nato-security.ttl`.

### Register inventory

| register | source aspect | schemes | concepts | notations dropped |
|---|---|---|---|---|
| `us-nato-security` | security | 6 | 70 | 73 |
| `media-encoding` | encoding | 2 (Codec, Compression) | 15 | 15 |
| `color` | color | 1 (ColorSpace) | 4 | 4 |
| `checksum` | integrity | 1 (ChecksumAlgorithm) | 4 | 4 |
| `part-role` | bundle | 1 (PartRole) | 12 | 0 |
| `geometry-type` | geometry | 1 (GeometryType) | 6 | 0 |
| **total** | | **12** | **111** | **96** |

The security register is named for its jurisdiction (`us-nato-security`), not for its aspect, because the
whole point is that a sibling `eu-security` register can exist beside it. The other five are named for
their subject matter since no variant is anticipated.

## 2. Register contract — additions to `core`

Three generic terms. Nothing format-, jurisdiction- or aspect-specific enters `core`.

```turtle
hexplain:usesRegister    a owl:ObjectProperty ;   # profile ontology -> hexplain:RegisterBinding
hexplain:RegisterBinding a owl:Class ;
hexplain:forProperty     a owl:ObjectProperty ;   # the aspect property being bound
hexplain:register        a owl:ObjectProperty ;   # the skos:ConceptScheme supplying its values
```

Declared on the profile:

```turtle
<https://hexplain.io/ns/profile/nitf> hexplain:usesRegister
    [ hexplain:forProperty asec:classification ;
      hexplain:register    usnato:ClassificationLevelScheme ] .
```

A property with no binding is unconstrained, exactly as today. Binding is opt-in per profile per property.

## 3. Enforcement — one generic shape, no codegen

`core` ships a single SHACL-SPARQL constraint that reads the `hexplain:usesRegister` declarations and
validates instance data against them. There is no shape-generation step and no per-profile shape to keep
in sync. This follows the `sh:select` pattern already used 7× in `bddo.ttl`, so it needs no new tooling
and works under the existing `pyshacl` runner.

A violation is: a value of a bound property that is not `skos:inScheme` the declared register.

`bundle.ttl:108`'s hard-coded `sh:hasValue :PartRoleScheme` is **deleted** and re-expressed as a binding,
making it the first consumer of the new mechanism rather than a surviving special case.

## 4. Migration

One change, no alias period:

- Move the 111 concepts and 12 scheme declarations out of the six aspect documents.
- Delete all 96 `skos:notation` triples; re-express each as an HDL enum raw value in the profile.
- Rewrite the advisory `skos:note "Value drawn from <scheme>."` texts (8 in `security.ttl`, plus the
  equivalents in the other five aspects). They currently name schemes that will no longer exist in the
  aspect's own namespace. Each becomes a namespace-neutral statement of what kind of register is
  expected — the concrete scheme is now the profile's `hexplain:usesRegister` declaration, not the
  aspect's prose. Leaving these stale would reintroduce, in comments, exactly the coupling this change
  removes.
- Rewrite concept references in `specification/profiles/nitf/nitf.ttl`, `nitf.hx`, `example.ttl`,
  `specification/gv/geo.ttl`, and the affected test fixtures.
- Add `hexplain:usesRegister` declarations to the NITF profile for each bound property.

Aspect **property** IRIs are untouched, so the majority of existing references keep working; only the
concept IRIs move.

## 5. `RegisterProvider` reindexed

`core/src/main/kotlin/io/hexplain/core/conformance/RegisterProvider.kt` currently indexes concepts by
`skos:notation` to answer "is this raw code valid in this scheme". Code-free registers would make
`inRegister()` (HEL builtin, arity 2, `HelEvaluator.kt:340`) unable to ever match.

The provider is therefore rebuilt from the **compiled profile** instead of the vocabulary graph:

```
bddo:enumeration -> bddo:hasEnumValue -> (bddo:enumRawValue, bddo:enumSymbol)
                 -> symbol's skos:inScheme -> index[scheme] += rawValue
```

`inRegister("T", usnato:ClassificationLevelScheme)` keeps its exact signature and meaning; only the source
of truth moves, so no HEL assertion needs rewriting. Codes then exist in exactly one place — the profile.

**Semantic narrowing, stated deliberately:** a code is "in" a register only if some loaded profile maps it.
`inRegister` becomes a question about the profile's declared encoding rather than about the register in the
abstract. This is the intended consequence of decision 4, not an accident.

## 6. Testing

Red-green for each unit:

- **Register-binding enforcement** — valid and invalid fixtures in `tools/test_shapes.py`: a value from the
  declared register passes; a value from a sibling register fails with the expected message.
- **`RegisterProvider`** — a unit test that `inRegister` resolves from profile enum mappings, and returns
  false for a code no profile maps. `ConformanceEndToEndTest` moves to the profile-backed provider.
- **Vocabulary integrity** — `tools/test_vocab_shapes.py` must stay green; aspects must retain their
  properties and lose only concepts.
- **NITF round trip** — `tools/test_hx_roundtrip.py` re-run; every enum symbol in `nitf.hx` changes
  namespace, so this is the widest blast radius in the profile.

No aspect has an `index.html`, so `test_html_sync.py` is unaffected by the move. (It currently fails for an
unrelated, pre-existing `bddo.ttl`/`index.html` drift; that is not in scope here.)

## Risks

- **Published IRIs break with no deprecation path.** Chosen deliberately (decision 2). Anything outside
  these two repositories referencing `asec:TopSecret` and friends will dangle.
- **`inRegister` narrows** to profile-declared codes (§5).
- **Uniform scope costs churn without benefit for five of six aspects**, and externalises Hexplain's own
  `PartRoleScheme`. Raised during design and reaffirmed; recorded here so the trade is visible later.

## Out of scope

- Authoring a second (e.g. EU) security register — the point is that one *can* be added, not that it is.
- The `bddo.ttl` / `index.html` sync failure.
- Byte-level determinism of HDL Turtle emission, and the NITF SecurityMarking "Step 3" flattening
  decision — both tracked separately.
