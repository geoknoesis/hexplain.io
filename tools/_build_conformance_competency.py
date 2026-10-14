"""Write or check the conformance, requirement and function competency corpus.

``specification/validation/test/conformance-competency.tsv`` is generated: it is the cases
authored here -- one conforming and one or more non-conforming per competency question of the
conf, req and fn vocabularies -- in the four-column corpus format (name, conforms, expected result
path, base64 Turtle). ``--write`` regenerates it; ``--check`` exits 1 when the file is not
byte-for-byte what the cases render to. The gate ``tools/test_conformance_competency.py``
validates the cases against the conf, req and fn shapes and checks the file is current; it
writes nothing.

After ``--write``, rerun ``python tools/_constraint_coverage.py`` and
``python tools/_render_constraint_coverage.py``: the ledger hashes this file.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "specification/validation/test/conformance-competency.tsv"

P = """@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req: <https://hexplain.io/ns/req#> .
@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix hxf: <https://hexplain.io/ns/fn#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:conformance-competency:> .
"""
REQ = """ex:r1 a req:Requirement ; req:requirementId "R-1" ; req:fromStandard "Example Format 2.0" ;
    req:statement "The magic shall be HX." ; req:discrepancyType req:Syntactic ; req:appliesToVersion "2.0" .
ex:r2 a req:Requirement ; req:requirementId "R-2" ; req:fromStandard "Example Format 2.0" ;
    req:statement "The count shall be positive." ; req:discrepancyType req:Semantic .
ex:Header a bddo:Struct . ex:count a bddo:Field .
"""
CON = """ex:c1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HX'" ;
    conf:satisfies ex:r1 ; conf:message "Magic is {value}." ; conf:severity sh:Violation .
ex:c2 a conf:Constraint ; conf:scope ex:count ; conf:assertion "self > 0" ;
    conf:satisfies ex:r2 ; conf:message "{field} is {value}, not positive." ; conf:severity sh:Warning .
"""
NS = {"conf": "https://hexplain.io/ns/conf#", "req": "https://hexplain.io/ns/req#", "hxf": "https://hexplain.io/ns/fn#"}


#: One case: (name, expected conformance, expected result path IRI or "", Turtle).
Case = tuple[str, bool, str, str]


def cases() -> list[Case]:
    """Every authored case, grouped by the competency question it answers."""
    rows: list[Case] = []

    def add(name: str, body: str, ok: bool, path: str = "") -> None:
        prefix, local = path.split(":") if path else ("", "")
        rows.append((name, ok, NS[prefix] + local if path else "", P + body))

    # Which requirements does a profile check, and at what severity? (declared coverage)
    add("struct- and field-scoped constraints citing requirements", REQ + CON, True)
    add(
        "constraint citing a non-requirement",
        REQ + CON.replace("conf:satisfies ex:r2", "conf:satisfies ex:count"),
        False,
        "conf:satisfies",
    )
    add(
        "constraint scoped to something that is not a struct or field",
        REQ + CON.replace("conf:scope ex:count", "conf:scope ex:r1"),
        False,
        "conf:scope",
    )
    add(
        "constraint with two severities",
        REQ + CON.replace("conf:severity sh:Warning", "conf:severity sh:Warning , sh:Info"),
        False,
        "conf:severity",
    )
    # Which requirement does a parse error break? (parse attribution)
    add(
        "parse attribution of a checksum error",
        REQ + 'ex:pa a conf:ParseAttribution ; conf:errorCategory "Checksum" ; conf:satisfies ex:r1 .',
        True,
    )
    add(
        "parse attribution naming an unknown category",
        REQ + 'ex:pa a conf:ParseAttribution ; conf:errorCategory "Crc" ; conf:satisfies ex:r1 .',
        False,
        "conf:errorCategory",
    )
    # What did a run find, and how did each requirement fare? (findings and run coverage)
    run = (
        REQ + CON + "ex:f1 a conf:Finding ; conf:findingKind conf:Violation ; conf:findingConstraint ex:c1 ; "
        'conf:findingRequirement ex:r1 ; conf:severity sh:Violation ; conf:findingMessage "Magic is XX." ; '
        "conf:focusNode ex:h0 .\n"
        'ex:f2 a conf:Finding ; conf:findingKind conf:Parse ; conf:errorCategory "Bounds" ; conf:severity '
        "sh:Violation ; "
        'conf:findingMessage "Truncated at byte 12." .\n'
        "ex:run a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:finding ex:f1 , ex:f2 ; "
        "conf:outcome [ conf:outcomeRequirement ex:r1 ; conf:outcomeValue conf:Evaluated ] , "
        "[ conf:outcomeRequirement ex:r2 ; conf:outcomeValue conf:NotReached ] .\n"
    )
    add("run with a violation, an unattributed parse finding and two outcomes", run, True)
    add(
        "finding attributed to a requirement its constraint does not cite",
        run.replace("conf:findingRequirement ex:r1 ;", "conf:findingRequirement ex:r1 , ex:r2 ;"),
        False,
    )
    add(
        "outcome value that is a finding kind",
        run.replace("conf:outcomeValue conf:NotReached", "conf:outcomeValue conf:RuleError"),
        False,
        "conf:outcomeValue",
    )
    add(
        "rule error without its constraint",
        run.replace(
            "conf:findingKind conf:Violation ; conf:findingConstraint ex:c1 ;", "conf:findingKind conf:RuleError ;"
        ),
        False,
    )
    # Does a run report say what it decided, and is the decision consistent? (run report)
    add(
        "conformant verdict despite a violation",
        run.replace("conf:verdict conf:NonConformant", "conf:verdict conf:Conformant"),
        False,
    )
    add(
        "truncated run that is conformant",
        run.replace(
            "conf:verdict conf:NonConformant ; conf:truncated false",
            'conf:verdict conf:Conformant ; conf:truncated true ; conf:truncationReason "finding limit"',
        ),
        False,
    )
    add("run without a verdict", run.replace("conf:verdict conf:NonConformant ; ", ""), False, "conf:verdict")
    add("finding the run does not link", run.replace("conf:finding ex:f1 , ex:f2 ; ", "conf:finding ex:f1 ; "), False)
    add(
        "finding at a severity its constraint does not report",
        run.replace(
            "conf:findingRequirement ex:r1 ; conf:severity sh:Violation",
            "conf:findingRequirement ex:r1 ; conf:severity sh:Info",
        ),
        False,
    )
    add(
        "parse attribution naming a resource limit",
        REQ + 'ex:pa a conf:ParseAttribution ; conf:errorCategory "ResourceLimit" ; conf:satisfies ex:r1 .',
        False,
        "conf:errorCategory",
    )
    add(
        "parse attribution of a dispatch error by category IRI",
        REQ + "ex:pa a conf:ParseAttribution ; conf:errorCategory conf:DispatchError ; conf:satisfies ex:r1 .",
        True,
    )
    # Is a requirement identified once? (requirement identity)
    add(
        "same identifier in two standards",
        REQ + 'ex:r3 a req:Requirement ; req:requirementId "R-1" ; '
        'req:fromStandard "Other Format 1.0" ; req:statement "Other." ; req:discrepancyType req:Functional .',
        True,
    )
    add(
        "same identifier in one standard written with other case",
        REQ + 'ex:r3 a req:Requirement ; req:requirementId "R-1" ; '
        'req:fromStandard "example format 2.0" ; req:statement "Again." ; req:discrepancyType req:Syntactic .',
        False,
    )
    add(
        "empty version",
        REQ.replace('req:appliesToVersion "2.0"', 'req:appliesToVersion ""'),
        False,
        "req:appliesToVersion",
    )
    # Does every native function say when it answers nothing? (function contract)
    add(
        "native function declaring when it is unbound",
        'ex:fn a hxf:Function ; hxf:kind hxf:Native ; hxf:unboundWhen "The index is outside the array."@en .',
        True,
    )
    add("native function declaring nothing", "ex:fn a hxf:Function ; hxf:kind hxf:Native .", False)
    add("window limit of zero", "ex:cfg hxf:maxCellsPerWindow 0 .", False, "hxf:maxCellsPerWindow")
    return rows


def render(rows: list[Case]) -> str:
    """The corpus file: two comment lines, then one tab-separated line per case."""
    lines = [
        "# Conformance, requirement and function competency cases (tools/test_conformance_competency.py --write).",
        "# name\tconforms\texpected-path\tbase64 Turtle",
    ]
    for name, ok, path, body in rows:
        lines.append("\t".join([name, "true" if ok else "false", path, base64.b64encode(body.encode()).decode()]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate the corpus from the authored cases")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the corpus is not what --write produces")
    args = parser.parse_args(argv)
    rows = cases()
    rendered = render(rows)
    relative = CORPUS.relative_to(ROOT).as_posix()
    if args.write:
        CORPUS.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {len(rows)} conformance competency cases to {relative}; rerun tools/_constraint_coverage.py")
        return 0
    if not CORPUS.is_file() or CORPUS.read_text(encoding="utf-8") != rendered:
        print(f"STALE: {relative} is not what the authored cases render to; run this builder with --write")
        return 1
    print(f"CURRENT: {relative} holds the {len(rows)} authored conformance competency cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
