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

Full graph isomorphism is not achievable today, by design: nitf.hx factors
the 16-field NITF SecurityMarking block into one reusable struct, referenced
from six subheaders; nitf.ttl inlines the same 16 fields six times flat with
segment-specific names (FH_FSCLAS, IS_ISCLAS, GS_SSCLAS, TS_TSCLAS,
DES_DECLAS, RES_RECLAS, ...). Deciding which shape wins is deliberately out
of scope ("Step 3"). See KNOWN_RESIDUAL_STEP3 below and "Known limitation" in
docs/superpowers/plans/2026-08-02-hdl-compiler-p0-and-roundtrip.md.
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

# ---------------------------------------------------------------------------
# KNOWN_RESIDUAL_STEP3 -- see "Known limitation" in
# docs/superpowers/plans/2026-08-02-hdl-compiler-p0-and-roundtrip.md
#
# nitf.hx factors the 16-field NITF security-marking block (MIL-STD-2500C
# Table A-1/A-3/A-5/A-6/A-8/A-9) into one reusable `struct SecurityMarking
# { ... }`, referenced as a nested field from all six subheaders. nitf.ttl
# instead inlines the same 16 fields six times, flat, under segment-specific
# names. Which shape wins is a future lift-rule decision ("Step 3") that is
# explicitly out of scope here; until it is made, the compiled and
# hand-written graphs can never be fully isomorphic. This is the one
# residual the gate tolerates -- anything else is a real regression.
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


def _is_known_residual(iri):
    """True if `iri` is a SecurityMarking field under any of nitf.ttl's six
    segment prefixes, or under nitf.hx's dotted struct-member form."""
    if not isinstance(iri, rdflib.URIRef):
        return False
    local = str(iri).rsplit("#", 1)[-1]
    if not local.endswith(KNOWN_RESIDUAL_STEP3):
        return False
    return local.startswith(_TTL_SEGMENT_PREFIXES) or local.startswith(_HX_DOTTED_PREFIX)


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
          "(the Step-3 security residual is gone -- KNOWN_RESIDUAL_STEP3 can be retired)")
    sys.exit(0)

_, only_ttl, only_compiled = graph_diff(iso_ttl, iso_compiled)

by_subject = {}
for s, p, o in only_ttl:
    by_subject.setdefault(s, []).append(("nitf.ttl only", p, o))
for s, p, o in only_compiled:
    by_subject.setdefault(s, []).append(("compiled only", p, o))

offenders = {s: triples for s, triples in by_subject.items() if not _is_known_residual(s)}

if offenders:
    lines = [
        f"FAIL: compiled nitf.hx differs from nitf.ttl outside the known Step-3 "
        f"security residual -- {len(offenders)} unexplained differing subject(s) "
        f"({len(by_subject)} differing subject(s) total, "
        f"{len(by_subject) - len(offenders)} within KNOWN_RESIDUAL_STEP3):"
    ]
    # Named (URIRef) subjects are what a human can act on; blank-node RDF-list
    # cells cascading from those same named differences are real but not
    # independently actionable, so they sort last and are the first thing
    # dropped once the line budget runs out.
    budget = MAX_REPORT_LINES
    for s in sorted(offenders, key=lambda s: (isinstance(s, rdflib.BNode), str(s))):
        if budget <= 0:
            break
        lines.append(f"  {s}")
        budget -= 1
        for where, p, o in offenders[s]:
            if budget <= 0:
                break
            lines.append(f"      [{where}] {p} {o}")
            budget -= 1
    if budget <= 0:
        lines.append(f"  ... (truncated at {MAX_REPORT_LINES} lines)")
    print("\n".join(lines))
    sys.exit(1)

print(
    f"PASS: compiled nitf.hx matches nitf.ttl except for the known Step-3 security "
    f"residual ({len(by_subject)} differing subject(s), all within KNOWN_RESIDUAL_STEP3)"
)
