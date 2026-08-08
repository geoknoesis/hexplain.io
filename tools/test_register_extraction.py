"""The extraction must conserve every concept triple: for each aspect, the union of the
trimmed aspect and its new register must equal the ORIGINAL aspect graph, after (a) rewriting
concept/scheme IRIs into the register namespace and (b) removing skos:notation.

Run against git HEAD~1 for the original. Guards a 111-concept mechanical move that no human
will diff line by line.

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
"""
import subprocess, sys
import rdflib

SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
RDFS = rdflib.Namespace("http://www.w3.org/2000/01/rdf-schema#")
PAIRS = [("security", "us-nato-security"), ("encoding", "media-encoding"),
         ("color", "color"), ("integrity", "checksum"),
         ("bundle", "part-role"), ("geometry", "geometry-type")]

def original(aspect):
    blob = subprocess.run(
        ["git", "show", f"HEAD:specification/aspect/{aspect}/{aspect}.ttl"],
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
    moving = (set(old.subjects(rdflib.RDF.type, SKOS.Concept))
              | set(old.subjects(rdflib.RDF.type, SKOS.ConceptScheme))
              | set(old.subjects(rdflib.RDF.type, SKOS.Collection)))

    old_wanted = {rewrite(t) for t in old
                  if t[0] in moving and t[1] not in (SKOS.notation, RDFS.isDefinedBy)}
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
    # every migrated scheme must be rdfs:isDefinedBy the new register ontology, not the old aspect
    reg_ont = rdflib.URIRef(f"https://hexplain.io/ns/register/{reg}")
    for s in old.subjects(rdflib.RDF.type, SKOS.ConceptScheme):
        rewritten_s = rewrite((s,))[0]
        if (rewritten_s, RDFS.isDefinedBy, reg_ont) not in got:
            problems.append(f"{aspect}: {rewritten_s} is not rdfs:isDefinedBy the register ontology")

if problems:
    print("FAIL:\n  " + "\n  ".join(problems)); sys.exit(1)
print(f"PASS: all 6 registers extracted; concepts conserved; notations removed")
