"""The extraction must conserve every concept triple: for each aspect, the union of the
trimmed aspect and its new register must equal the ORIGINAL aspect graph, after (a) rewriting
concept/scheme IRIs into the register namespace and (b) removing skos:notation.

Guards a specific, one-time 111-concept mechanical move (commit 2596596) that no human will
diff line by line. Two independent guards, on purpose:

  1. A historical comparison against the commit immediately BEFORE that migration landed
     (PRE_MIGRATION_SHA, below) -- pinned to a fixed sha, deliberately NOT HEAD or HEAD~1.
     Both of those drift as later commits land; HEAD in particular went vacuous the moment
     the migration itself was committed, since at that point HEAD *is* the post-extraction
     tree and there is nothing left to diff against (this is exactly how this test broke the
     first time -- see task-3-report.md, "Fix round 1", Finding 1). A fixed sha keeps this
     half of the test meaningful forever, at the cost of it only ever describing this one
     migration.
  2. Durable invariants that don't touch git history at all (EXPECTED_COUNTS, the
     no-notation check, and the no-leftover-concepts/-schemes/-collections check), so the
     file keeps earning its place long after PRE_MIGRATION_SHA is ancient and largely
     irrelevant.

Two portability/scope fixes applied over the originally-drafted version, both verified against
the actual us-nato-security extraction before being adopted (see task-3-report.md "Judgment
calls" for the full evidence trail):

1. `git show` is piped through `text=True` without an explicit encoding. On this Windows/Python
   3.11 environment that decodes the UTF-8 blob using the process's locale codepage (cp1252),
   silently mangling every non-ASCII character (em dashes in rdfs:label/comment) before any
   comparison runs. Decoding is now pinned to utf-8, matching how the .ttl files are written.

2. The docstring says the comparison rewrites "concept/scheme IRIs", but the original `rewrite()`
   substring-replaced the aspect namespace on *every* URIRef in the graph, including properties
   and classes that never move (e.g. asec:classification). Since the aspect's own properties are
   never expected to gain a register-namespace twin, this produced ~94 guaranteed-missing false
   positives per aspect regardless of how correct the extraction was. `old_wanted` is now scoped
   to triples whose subject is one of the entities that actually migrates (skos:Concept,
   skos:ConceptScheme, skos:Collection in the ORIGINAL graph), matching the docstring's own
   stated scope; the notation- and no-concepts-left checks are untouched and just as strict.

   A related, narrower case: a moved scheme's `rdfs:isDefinedBy` correctly retargets from the
   aspect ontology IRI to the register ontology IRI (no trailing '#'), but a_ns/r_ns both carry a
   trailing '#', so that object is never touched by the substring rewrite -- old_wanted keeps
   demanding the untouched (pre-retarget) object forever, which no correct retarget can satisfy.
   rdfs:isDefinedBy is excluded from the generic scheme/concept comparison the same way
   skos:notation already is, and replaced with an explicit, more precise check: every migrated
   scheme's rdfs:isDefinedBy in the new data must equal the register ontology IRI.

3. A later fix-wave (2026-08-08, "final fix report", Finding C) made two further, intentional
   changes to the us-nato-security register on top of the mechanical move this test otherwise
   guards: it renumbered the six moved schemes' owl:versionInfo from "1.1" (inherited from the
   aspect they came from) to "1.0" (the register ontology's own version), and it deleted a
   skos:note on MarkingScheme that described NITF digraph notations -- the only format-specific
   detail that had been living in register DATA rather than a comment. Both are one-time,
   fully-enumerated exceptions (DELIBERATELY_CHANGED, below), not a blanket predicate exclusion,
   so the test stays strict about anything else moving.
"""
import subprocess, sys
import rdflib

SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = rdflib.Namespace("http://www.w3.org/2002/07/owl#")
PAIRS = [("security", "us-nato-security"), ("encoding", "media-encoding"),
         ("color", "color"), ("integrity", "checksum"),
         ("bundle", "part-role"), ("geometry", "geometry-type")]

# The commit immediately BEFORE the six-registers extraction (2596596) landed. Fixed on
# purpose -- see the module docstring. Do not change this to HEAD/HEAD~1/a branch name.
# Deliberately a fixed historical commit, not a moving ref -- written as the full 40-char
# sha (rather than the abbreviated form) so a future rebase or hash collision cannot make
# this lookup ambiguous.
PRE_MIGRATION_SHA = "7e92f4bc020ba5d6a7ee24edae7c3cd4ded90eb1"

# Durable, git-history-independent invariant: exact (schemes, concepts) per register, taken
# from the migration's own design table. Any future edit to a register that changes these
# counts must update this table deliberately, not by accident.
EXPECTED_COUNTS = {
    "us-nato-security": (6, 70),
    "media-encoding": (2, 15),
    "color": (1, 4),
    "checksum": (1, 4),
    "part-role": (1, 12),
    "geometry-type": (1, 6),
}

# Types that mark an entity as belonging to the register, not the aspect, after extraction.
MOVING_TYPES = (SKOS.Concept, SKOS.ConceptScheme, SKOS.Collection)

# See docstring point 3: two fully-enumerated, one-time exceptions applied by a later fix-wave
# on top of the original mechanical move, so the generic "every old triple must survive" check
# below does not flag them as accidental data loss.
_UNS = "https://hexplain.io/ns/register/us-nato-security#"
DELIBERATELY_CHANGED = {
    (rdflib.URIRef(_UNS + "ClassificationLevelScheme"), OWL.versionInfo, rdflib.Literal("1.1")),
    (rdflib.URIRef(_UNS + "MarkingScheme"), OWL.versionInfo, rdflib.Literal("1.1")),
    (rdflib.URIRef(_UNS + "DeclassTypeScheme"), OWL.versionInfo, rdflib.Literal("1.1")),
    (rdflib.URIRef(_UNS + "AuthorityTypeScheme"), OWL.versionInfo, rdflib.Literal("1.1")),
    (rdflib.URIRef(_UNS + "ClassificationReasonScheme"), OWL.versionInfo, rdflib.Literal("1.1")),
    (rdflib.URIRef(_UNS + "ExemptionScheme"), OWL.versionInfo, rdflib.Literal("1.1")),
    (rdflib.URIRef(_UNS + "MarkingScheme"), SKOS.note,
     rdflib.Literal("Digraph notations from NITF MIL-STD-2500C Table A-4; align to the "
                    "current CAPCO Register when applying.")),
}

def original(aspect):
    blob = subprocess.run(
        ["git", "show", f"{PRE_MIGRATION_SHA}:specification/aspect/{aspect}/{aspect}.ttl"],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout
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

    # Entities that actually migrate: concepts, schemes, and collections (per the docstring's
    # "rewriting concept/scheme IRIs" scope) -- not every property/class that merely shares the
    # aspect namespace and stays put.
    moving = set()
    for t in MOVING_TYPES:
        moving |= set(old.subjects(rdflib.RDF.type, t))

    old_wanted = {rewrite(t) for t in old
                  if t[0] in moving and t[1] not in (SKOS.notation, RDFS.isDefinedBy)}
    if aspect == "security":
        old_wanted -= DELIBERATELY_CHANGED
    got = set(new) | set(rgraph)
    missing = old_wanted - got
    if missing:
        problems.append(f"{aspect}: {len(missing)} triple(s) lost, e.g. {sorted(missing, key=str)[:3]}")

    # durable: notations must be gone everywhere, independent of git history
    left = [t for t in got if t[1] == SKOS.notation]
    if left:
        problems.append(f"{aspect}: {len(left)} skos:notation triple(s) survived")

    # durable: the aspect must retain NO concepts, schemes, or collections of its own
    for t in MOVING_TYPES:
        leftover = list(new.subjects(rdflib.RDF.type, t))
        if leftover:
            kind = t.split("#")[-1]
            problems.append(f"{aspect}: {len(leftover)} {kind}(s) still in the aspect")

    # durable: the register must carry exactly the designed scheme/concept counts
    exp_schemes, exp_concepts = EXPECTED_COUNTS[reg]
    got_schemes = len(set(rgraph.subjects(rdflib.RDF.type, SKOS.ConceptScheme)))
    got_concepts = len(set(rgraph.subjects(rdflib.RDF.type, SKOS.Concept)))
    if (got_schemes, got_concepts) != (exp_schemes, exp_concepts):
        problems.append(
            f"{reg}: expected {exp_schemes} scheme(s)/{exp_concepts} concept(s), "
            f"got {got_schemes}/{got_concepts}")

    # every migrated scheme must be rdfs:isDefinedBy the new register ontology, not the old aspect
    reg_ont = rdflib.URIRef(f"https://hexplain.io/ns/register/{reg}")
    for s in old.subjects(rdflib.RDF.type, SKOS.ConceptScheme):
        rewritten_s = rewrite((s,))[0]
        if (rewritten_s, RDFS.isDefinedBy, reg_ont) not in got:
            problems.append(f"{aspect}: {rewritten_s} is not rdfs:isDefinedBy the register ontology")

if problems:
    print("FAIL:\n  " + "\n  ".join(problems)); sys.exit(1)
print(f"PASS: all 6 registers extracted; concepts conserved; notations removed")
