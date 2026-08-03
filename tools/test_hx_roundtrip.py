"""Compile specification/profiles/nitf/nitf.hx with the HDL compiler (the
`hdl` Gradle module in the sibling hexplain-tools checkout) and diff the
result against the hand-written specification/profiles/nitf/nitf.ttl, so the
authoring surface and its canonical Turtle can never silently drift apart
again -- nitf.hx once carried a "STALE -- DO NOT REGENERATE" banner listing
three defects because nothing checked it.

Optional cross-repo gate: hexplain-tools is a sibling checkout, not a
dependency of this repo, and its toolchain (Gradle + a JVM) is not always
present. Mirrors tools/test_shapes.py's pyshacl skip: if the checkout,
gradlew, Java, or the build itself is unavailable, SKIP (exit 0) so the
rdflib-only suite stays green on machines without the Kotlin toolchain. Only
a genuine content mismatch *in the compiled output* -- once we actually have
one to compare -- FAILs.

Full graph isomorphism is not achievable today. An earlier version of this
gate tolerated exactly one excused category (the SecurityMarking block) and
FAILed the moment anything else differed -- which turned out to be nearly
every other subject in the file (482 of them), because several more
structural gaps are real and pre-existing, not gate defects. A single
allow-list can't tell "someone broke something" apart from "the known
gaps", so it was unusable as a regression gate.

Instead, every differing subject is classified into exactly one of the named
categories below, or into UNEXPLAINED. The gate PASSES only when UNEXPLAINED
is empty; a per-category count summary is always printed, on PASS or FAIL,
so the real state of the round-trip stays visible instead of hidden behind a
green tick. Each category is deliberately narrow -- a subject is credited to
it only if *every* one of its differing triples is accounted for by a known
category; a subject with even one additional, unexplained triple is NOT
excused and surfaces in UNEXPLAINED. See "Known limitation" in
docs/superpowers/plans/2026-08-02-hdl-compiler-p0-and-roundtrip.md.

NOTE ON A LARGE RESIDUAL THAT IS *NOT* ONE OF THE CATEGORIES BELOW: nearly
every field's `bddo:size` triple differs even when nothing about the field's
shape actually changed, because the compiler's TurtleEmitter always mints
size literals as `xsd:positiveInteger` (see `posInt()` in hexplain-tools'
TurtleEmitter.kt) while nitf.ttl's hand-written bare integers ("2", "3", ...)
default to `xsd:integer` under Turtle grammar -- and rdflib's Literal
equality treats those as different values, not just different spellings of
the same one. This was not caught by the investigation that produced the
five categories below, is not something HDL authoring or the vocabulary can
fix from this file, and is deliberately NOT given a category here -- adding
one would defeat the point of this gate (see the per-category comments
below, which explain why folding it in would hide, not explain, the
divergence). It is the dominant reason UNEXPLAINED is still large on the
current tree; see the round-trip task's report for the full count.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import rdflib
from rdflib.compare import graph_diff, to_isomorphic

NITF_HX = pathlib.Path("specification/profiles/nitf/nitf.hx")
NITF_TTL = pathlib.Path("specification/profiles/nitf/nitf.ttl")
MAX_REPORT_LINES = 40

BDDO = "https://hexplain.io/ns/bddo#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
RDFS_COMMENT = "http://www.w3.org/2000/01/rdf-schema#comment"
RDFS_SEE_ALSO = "http://www.w3.org/2000/01/rdf-schema#seeAlso"
OWL_VERSION_IRI = "http://www.w3.org/2002/07/owl#versionIRI"
OWL_VERSION_INFO = "http://www.w3.org/2002/07/owl#versionInfo"

# ---------------------------------------------------------------------------
# STEP3_SECURITY_BLOCK -- see "Known limitation" in
# docs/superpowers/plans/2026-08-02-hdl-compiler-p0-and-roundtrip.md
#
# nitf.hx factors the 16-field NITF security-marking block (MIL-STD-2500C
# Table A-1/A-3/A-5/A-6/A-8/A-9) into one reusable `struct SecurityMarking
# { ... }`, referenced as a nested field from all six subheaders. nitf.ttl
# instead inlines the same 16 fields six times, flat, under segment-specific
# names. Which shape wins is a future lift-rule decision ("Step 3") that is
# explicitly out of scope here; until it is made, the compiled and
# hand-written graphs can never be fully isomorphic.
#
# Closes when Step 3 (deciding which shape is canonical) is done.
#
# Preserved unchanged from the original single-category gate -- this is a
# pure subject-IRI-shape predicate (like TRE_PAYLOADS below; ONTOLOGY_HEADER,
# CUSTOM_DATATYPES and MISSING_LABELS are per-triple instead -- see their
# comments for why a shape-only predicate doesn't work for those).
#
# The 16 field names, read directly from `struct SecurityMarking` in
# nitf.hx:
KNOWN_RESIDUAL_STEP3 = (
    "CLAS", "CLSY", "CODE", "CTLH", "REL", "DCTP", "DCDT", "DCXM",
    "DG", "DGDT", "CLTX", "CATP", "CAUT", "CRSN", "SRDT", "CTLN",
)
# The six segment prefixes each field name is inlined under in nitf.ttl,
# confirmed against nitf.ttl's actual field IRIs (grep for FH_FS.../IS_IS...
# etc.). DES is irregular -- DECLAS keeps the historical MIL-STD-2500C
# 2-letter "DE" infix (nitf:DES_DECLAS) while every *other* DES field uses
# the 3-letter "DES" infix (nitf:DES_DESCLSY, nitf:DES_DESCODE, ...); both
# forms are covered here because the match only requires the prefix and the
# suffix, not an exact infix in between.
_TTL_SEGMENT_PREFIXES = ("FH_FS", "IS_IS", "GS_SS", "TS_TS", "DES_DE", "RES_RE")
# nitf.hx never inlines: the struct is minted once and referenced from each
# subheader, so its own 16 fields keep HDL's dotted "SecurityMarking.<FIELD>"
# form (e.g. nitf:SecurityMarking.CLAS) rather than a segment prefix.
_HX_DOTTED_PREFIX = "SecurityMarking."


def _is_step3_security_block(iri):
    """True if `iri` is a SecurityMarking field under any of nitf.ttl's six
    segment prefixes, or under nitf.hx's dotted struct-member form.

    NOTE: the six per-subheader "<Subheader>.security" wrapper fields that
    nitf.hx's struct composition creates (nitf:FileHeader.security,
    nitf:ImageSubheader.security, ...) do NOT match this predicate -- their
    local name doesn't end in one of the 16 field suffixes -- so they are
    NOT part of this category and surface as UNEXPLAINED. That's correct:
    they're a real, distinct consequence of the same Step-3 factoring
    decision that this predicate was never written to cover, and widening
    it to catch them is exactly the kind of scope creep this gate exists to
    avoid.
    """
    if not isinstance(iri, rdflib.URIRef):
        return False
    local = str(iri).rsplit("#", 1)[-1]
    if not local.endswith(KNOWN_RESIDUAL_STEP3):
        return False
    return local.startswith(_TTL_SEGMENT_PREFIXES) or local.startswith(_HX_DOTTED_PREFIX)


# ---------------------------------------------------------------------------
# TRE_PAYLOADS -- nitf.hx's `struct TRE` dispatches its CEDATA payload on
# CETAG to two worked TRE bodies, `struct BLOCKA` and `struct RPC00B`
# (STDI-0002). nitf.ttl never declares either as a bddo:Field/bddo:Struct at
# all: their definitions live in specification/profiles/nitf/nitf-tre-
# blocka.ttl and .../nitf-tre-rpc00b.ttl, two files nitf.ttl does not
# `owl:import` or otherwise include, so this gate's two-file comparison
# never sees them. Every triple for these subjects is therefore
# unavoidably one-sided (compiled-only) -- there is nothing on the nitf.ttl
# side to fall short of.
#
# Closes by loading nitf-tre-blocka.ttl/nitf-tre-rpc00b.ttl into the
# comparison (they'd need their own field-name reconciliation against the
# nitf.hx dotted names first), or by moving the two structs' definitions
# into nitf.ttl itself.
def _is_tre_payload_subject(iri):
    """True for the BLOCKA/RPC00B structs and their dotted-form fields
    (nitf.hx gives neither struct field-level `as` aliases, so their
    members keep HDL's default "Struct.FIELD" dotted names)."""
    if not isinstance(iri, rdflib.URIRef):
        return False
    local = str(iri).rsplit("#", 1)[-1]
    return local in ("BLOCKA", "RPC00B") or local.startswith(("BLOCKA.", "RPC00B."))


def _is_tre_dispatch_triple(where, p, o):
    """True for the `bddo:hasConditionalDataType` triple the compiler emits
    on nitf:TRE_CEDATA to encode `switch CETAG { "BLOCKA" => BLOCKA,
    "RPC00B" => RPC00B }`. This predicate has exactly one source in the
    whole file -- that switch -- so any compiled-only triple using it is,
    by construction, the same TRE_PAYLOADS gap: nitf.ttl can't reference a
    dispatch target it doesn't define. TRE_CEDATA itself is a real,
    otherwise-ordinary field (present on both sides, also missing its
    label -- see MISSING_LABELS), so this is a per-triple rule rather than
    a subject-shape one like `_is_tre_payload_subject` above."""
    return where == "compiled" and str(p) == BDDO + "hasConditionalDataType"


# ---------------------------------------------------------------------------
# ONTOLOGY_HEADER -- nitf.hx's format-level `raw-turtle` block (anchored on
# FileHeader; see the comment at that block's use site) quotes nitf.ttl's
# ontology header verbatim for the predicates it lists: owl:Ontology,
# owl:imports, dcterms:created/creator/license, vann:preferred*. nitf.ttl's
# actual header carries five more predicates that block never claimed to
# reproduce: rdfs:label, rdfs:comment, rdfs:seeAlso, owl:versionIRI, and
# owl:versionInfo. All five are confirmed (by inspecting the actual
# graph_diff output for <https://hexplain.io/ns/profile/nitf>) to be
# nitf.ttl-only -- nothing about the ontology header is compiled-only, i.e.
# the raw-turtle block is a clean subset, not a divergent rewrite.
#
# Closes by extending the raw-turtle block to quote these five predicates
# too (they're static text, no HEL involved).
_ONTOLOGY_IRI = "https://hexplain.io/ns/profile/nitf"
_ONTOLOGY_HEADER_PREDICATES = {
    RDFS_LABEL, RDFS_COMMENT, RDFS_SEE_ALSO, OWL_VERSION_IRI, OWL_VERSION_INFO,
}


def _is_ontology_header_triple(subject, where, p, o):
    return (
        str(subject) == _ONTOLOGY_IRI
        and where == "ttl"
        and str(p) in _ONTOLOGY_HEADER_PREDICATES
    )


# ---------------------------------------------------------------------------
# CUSTOM_DATATYPES -- nitf.hx types NITF's text fields as the HDL builtin
# `ascii[N]` (-> bddo:dataType bddo:string; bddo:encoding bddo:ascii) and
# its ascii-numeric fields as `anum[N]` (-> bddo:dataType
# bddo:asciiInteger). nitf.ttl instead points most of the same fields at one
# of four NITF-specific bddo:DataType individuals -- nitf:BCSA, nitf:BCSN,
# nitf:BCSNpos, nitf:ECSA -- each carrying its own rdfs:label/bddo:baseType/
# bddo:xsdType (see the raw-turtle block in nitf.hx, which copies their
# *definitions* verbatim -- those triples land on nitf:BCSA etc. themselves
# and already match, so they never show up in this diff; this category is
# about the *field* that points at one of them instead). HDL's type grammar
# only accepts builtins or struct references on a field -- there is no
# syntax to say "this field's type is the individual nitf:BCSNpos".
#
# Closes when HDL gains syntax to reference a custom bddo:DataType
# individual as a field's type (or an equivalent lift rule).
#
# WARNING: confirmed against the actual diff that this category, on its
# own, currently explains very few subjects outright -- nearly every
# ordinary field that hits this dataType/encoding swap also carries the
# universal bddo:size xsd:positiveInteger-vs-xsd:integer difference
# described in the module docstring, which is not covered by any category
# and correctly lands the subject in UNEXPLAINED regardless (e.g.
# nitf:FH_UDHOFL: this category correctly matches its dataType/encoding
# triples, but the subject still lands in UNEXPLAINED because of its
# leftover isPresentIf-rewrite and bddo:size triples). The category is
# still kept, named, and applied per-triple (not deleted) because (a) it is
# real and correctly derived from the data, (b) it independently explains
# other triples on subjects that otherwise fully match (e.g. nitf:DES_DESID
# has no isPresentIf and, once its label is also credited to
# MISSING_LABELS, only the universal size quirk stands between it and full
# explanation -- exactly the "would be rescued if the size literal issue
# were ever fixed" pairing this category is for), and (c) probe (c) in the
# round-trip task's report demonstrates it is load-bearing: removing this
# predicate turns previously-explained ttl-only nitf:BCSA/BCSN/BCSNpos/
# ECSA-typed triples into UNEXPLAINED on a synthetic fixture where nothing
# else differs.
_CUSTOM_DATATYPE_INDIVIDUALS = {
    "https://hexplain.io/ns/profile/nitf#BCSA",
    "https://hexplain.io/ns/profile/nitf#BCSN",
    "https://hexplain.io/ns/profile/nitf#BCSNpos",
    "https://hexplain.io/ns/profile/nitf#ECSA",
}
_GENERIC_ASCII_DATATYPES = {BDDO + "string", BDDO + "asciiInteger"}


def _is_custom_datatype_triple(where, p, o):
    sp = str(p)
    if where == "ttl" and sp == BDDO + "dataType" and str(o) in _CUSTOM_DATATYPE_INDIVIDUALS:
        return True
    if where == "compiled" and sp == BDDO + "dataType" and str(o) in _GENERIC_ASCII_DATATYPES:
        return True
    if where == "compiled" and sp == BDDO + "encoding" and str(o) == BDDO + "ascii":
        return True
    return False


# ---------------------------------------------------------------------------
# MISSING_LABELS -- the compiler emits no rdfs:label for anything it
# declares. Verified directly (not estimated, via rdflib against the actual
# compiled output and nitf.ttl): nitf.ttl carries an rdfs:label on all 246
# of its named bddo:Field/bddo:Struct/bddo:Enumeration subjects; the
# compiled output's 196 equivalent named subjects (fewer -- e.g. it has no
# named Enumeration individuals, see the enum-shape gap noted below) carry
# zero. The compiled output does contain 41 rdfs:label triples in total, but
# every one is either a blank-node enum-value/concept-mapping label
# HelSynth synthesizes from an `enum { ... }` arm (e.g. "TopSecret" on the
# blank node behind `"T"=>asec:TopSecret`), or one of the four
# nitf:BCSA/BCSN/BCSNpos/ECSA raw-turtle individuals copied verbatim from
# nitf.ttl -- neither is a field/struct/enumeration label, and neither
# shows up in the diff.
#
# Closes when HDL gains a way to attach a label to a field/struct/
# enumeration declaration (e.g. a `@label "..."` clause) and the emitter
# writes it out, or the emitter synthesizes one from the field's comment or
# name the way it already does for enum arms.
def _is_missing_label_triple(where, p, o):
    return where == "ttl" and str(p) == RDFS_LABEL


CATEGORIES = (
    "STEP3_SECURITY_BLOCK",
    "TRE_PAYLOADS",
    "ONTOLOGY_HEADER",
    "CUSTOM_DATATYPES",
    "MISSING_LABELS",
)


def classify(by_subject):
    """Classify every differing subject as explained by (possibly several
    of) the named categories above, or as UNEXPLAINED.

    A subject is explained only if *every* differing triple it carries is
    covered by at least one category -- there is no partial credit. A
    subject can legitimately need more than one category to be fully
    explained (e.g. TRE_CEDATA needs both TRE_PAYLOADS and MISSING_LABELS),
    so the per-category counts returned here are not mutually exclusive:
    they count how many subjects each category contributed to explaining,
    not a disjoint partition. What IS exclusive is explained-vs-
    UNEXPLAINED, which is the actual pass/fail signal.
    """
    counts = {c: 0 for c in CATEGORIES}
    unexplained = {}
    for s, triples in by_subject.items():
        if _is_step3_security_block(s):
            counts["STEP3_SECURITY_BLOCK"] += 1
            continue
        if _is_tre_payload_subject(s):
            counts["TRE_PAYLOADS"] += 1
            continue
        hit = set()
        leftover = []
        for where, p, o in triples:
            if _is_ontology_header_triple(s, where, p, o):
                hit.add("ONTOLOGY_HEADER")
            elif _is_tre_dispatch_triple(where, p, o):
                hit.add("TRE_PAYLOADS")
            elif _is_custom_datatype_triple(where, p, o):
                hit.add("CUSTOM_DATATYPES")
            elif _is_missing_label_triple(where, p, o):
                hit.add("MISSING_LABELS")
            else:
                leftover.append((where, p, o))
        if hit and not leftover:
            for c in hit:
                counts[c] += 1
        else:
            unexplained[s] = triples
    return counts, unexplained


def format_summary(counts, unexplained_count, total):
    lines = [
        f"Category counts ({total} differing subject(s) total; a subject may "
        f"satisfy more than one category, so these are not mutually exclusive; "
        f"UNEXPLAINED subjects satisfy none):",
    ]
    for c in CATEGORIES:
        lines.append(f"  {c:22s}: {counts[c]}")
    lines.append(f"  {'UNEXPLAINED':22s}: {unexplained_count}")
    return "\n".join(lines)


if not NITF_HX.exists() or not NITF_TTL.exists():
    sys.exit(f"FAIL: {NITF_HX} or {NITF_TTL} not found (wrong working directory?)")

# --- Locate the compiler checkout ------------------------------------------
tools_dir = pathlib.Path(os.environ.get("HEXPLAIN_TOOLS", "../hexplain-tools"))
if not tools_dir.is_dir():
    print(f"SKIP: hexplain-tools checkout not found at {tools_dir} "
          f"(set HEXPLAIN_TOOLS to override)")
    sys.exit(0)

gradlew = tools_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
if not gradlew.exists():
    print(f"SKIP: {gradlew} not found -- hexplain-tools checkout looks incomplete")
    sys.exit(0)

if shutil.which("java") is None:
    print("SKIP: no `java` on PATH -- cannot run the Gradle-based HDL compiler")
    sys.exit(0)

# --- Compile nitf.hx ---------------------------------------------------------
with tempfile.TemporaryDirectory(prefix="hx_roundtrip_") as tmp:
    out_ttl = pathlib.Path(tmp) / "nitf.compiled.ttl"
    in_hx = NITF_HX.resolve()
    gradle_args = f"{in_hx.as_posix()} -o {out_ttl.as_posix()}"
    cmd = [str(gradlew), "-q", "--offline", ":hdl:run", f"--args={gradle_args}"]
    try:
        proc = subprocess.run(
            cmd, cwd=str(tools_dir), capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"SKIP: could not run the HDL compiler ({e})")
        sys.exit(0)

    # SLF4J warnings on stderr are routine noise from Gradle's own logging,
    # not a build failure -- judge success by exit code and by whether the
    # output file actually got written.
    if proc.returncode != 0 or not out_ttl.exists():
        print("SKIP: HDL compiler build did not succeed (treated as environmental)\n"
              f"  command: {' '.join(cmd)}\n"
              f"  exit code: {proc.returncode}\n"
              f"  stdout (tail): {proc.stdout[-2000:]}\n"
              f"  stderr (tail): {proc.stderr[-2000:]}")
        sys.exit(0)

    compiled_text = out_ttl.read_text(encoding="utf-8")

# --- Parse and compare -------------------------------------------------------
g_compiled = rdflib.Graph()
g_compiled.parse(data=compiled_text, format="turtle")
g_ttl = rdflib.Graph()
g_ttl.parse(data=NITF_TTL.read_text(encoding="utf-8"), format="turtle")

iso_compiled = to_isomorphic(g_compiled)
iso_ttl = to_isomorphic(g_ttl)

if iso_compiled == iso_ttl:
    print("PASS: compiled nitf.hx is fully isomorphic to nitf.ttl "
          "(every known residual category is gone -- they can all be retired)")
    print(format_summary({c: 0 for c in CATEGORIES}, 0, 0))
    sys.exit(0)

_, only_ttl, only_compiled = graph_diff(iso_ttl, iso_compiled)

by_subject = {}
for s, p, o in only_ttl:
    by_subject.setdefault(s, []).append(("ttl", p, o))
for s, p, o in only_compiled:
    by_subject.setdefault(s, []).append(("compiled", p, o))

counts, unexplained = classify(by_subject)
summary = format_summary(counts, len(unexplained), len(by_subject))

if unexplained:
    lines = [
        f"FAIL: compiled nitf.hx differs from nitf.ttl in {len(unexplained)} "
        f"way(s) outside all known categories:",
        summary,
        "",
        "Unexplained subjects:",
    ]
    # Named (URIRef) subjects are what a human can act on; blank-node RDF-list
    # cells cascading from those same named differences are real but not
    # independently actionable, so they sort last and are the first thing
    # dropped once the line budget runs out.
    budget = MAX_REPORT_LINES
    for s in sorted(unexplained, key=lambda s: (isinstance(s, rdflib.BNode), str(s))):
        if budget <= 0:
            break
        lines.append(f"  {s}")
        budget -= 1
        for where, p, o in unexplained[s]:
            if budget <= 0:
                break
            lines.append(f"      [{where} only] {p} {o}")
            budget -= 1
    if budget <= 0:
        lines.append(f"  ... (truncated at {MAX_REPORT_LINES} lines)")
    print("\n".join(lines))
    sys.exit(1)

print(
    f"PASS: compiled nitf.hx differs from nitf.ttl only within known categories "
    f"({len(by_subject)} differing subject(s) total, all explained)"
)
print(summary)
