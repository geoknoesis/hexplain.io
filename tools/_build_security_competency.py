"""Write or check the opt-in security profile competency corpus.

``specification/validation/test/security-competency.tsv`` is generated: the security profile's
cases authored here, including compound-resource scoping, as the four-column corpus rows Jena and
the constraint ledger consume. ``--write`` regenerates it; ``--check`` exits 1 when the file is
not byte-for-byte what the cases render to. The gate ``tools/test_security_profile.py``
validates the cases against security-profile.ttl and checks the file is current; it writes
nothing.

After ``--write``, rerun ``python tools/_constraint_coverage.py`` and
``python tools/_render_constraint_coverage.py``: the ledger hashes this file.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "specification/validation/test/security-competency.tsv"
SEC = "https://hexplain.io/ns/aspect/security#"

#: One case: (name, Turtle, expected conformance, expected result path IRI or "").
Case = tuple[str, str, bool, str]


def cases() -> list[Case]:
    """Every authored case, with the shared prefix and register declarations in its Turtle."""
    prefix = """@prefix ex:<urn:hexplain:security-example:> .
@prefix sec:<https://hexplain.io/ns/aspect/security#> .
@prefix skos:<http://www.w3.org/2004/02/skos/core#> .
@prefix pack:<https://hexplain.io/ns/aspect/packaging#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
ex:Low a skos:Concept; skos:inScheme ex:Levels .
ex:Control a skos:Concept; skos:inScheme ex:Controls .
"""
    valid = 'ex:file a ex:Marked; sec:markingSystem "Example"; sec:sensitivityLevel ex:Low .'
    cases: list[tuple[str, str, bool, str | None]] = [
        ("resolved level", valid, True, None),
        ("unrelated unmarked data", 'ex:other sec:sensitivityLevel "verbatim".', True, None),
        ("missing system", valid.replace('sec:markingSystem "Example";', ""), False, "markingSystem"),
        ("two systems", valid + 'ex:file sec:markingSystem "Other".', False, "markingSystem"),
        (
            "literal level",
            valid.replace("sec:sensitivityLevel ex:Low", 'sec:sensitivityLevel "Low"'),
            False,
            "sensitivityLevel",
        ),
        (
            "wrong register",
            valid.replace("sec:sensitivityLevel ex:Low", "sec:sensitivityLevel ex:Control"),
            False,
            "sensitivityLevel",
        ),
        (
            "undeclared concept",
            valid.replace("sec:sensitivityLevel ex:Low", "sec:sensitivityLevel ex:Unknown"),
            False,
            "sensitivityLevel",
        ),
        ("retained source text", valid + 'ex:file sec:sensitivityLevelText "RAW LOW".', True, None),
        ("repeatable controls", valid + "ex:file sec:marking ex:Low,ex:Control.", True, None),
        ("literal control", valid + 'ex:file sec:marking "Control".', False, "marking"),
        ("typed date", valid + 'ex:file sec:markingDate "2026-09-06"^^xsd:date.', True, None),
        ("untyped date", valid + 'ex:file sec:markingDate "2026-09-06".', False, "markingDate"),
        (
            "compound scope",
            valid + "ex:file a pack:Container; pack:hasEntry ex:child. ex:child a pack:Entry.",
            True,
            None,
        ),
    ]
    cases.extend(
        [
            ("missing level", valid.replace("; sec:sensitivityLevel ex:Low", ""), False, "sensitivityLevel"),
            (
                "two levels",
                valid + "ex:Other a skos:Concept; skos:inScheme ex:Levels. ex:file sec:sensitivityLevel ex:Other.",
                False,
                "sensitivityLevel",
            ),
            (
                "child independently marked missing system",
                valid + "ex:file pack:hasEntry ex:child. ex:child a ex:Marked; sec:sensitivityLevel ex:Low.",
                False,
                "markingSystem",
            ),
            (
                "child independently valid",
                valid + 'ex:file pack:hasEntry ex:child. ex:child a ex:Marked; sec:markingSystem "Other"; '
                "sec:sensitivityLevel ex:Low.",
                True,
                None,
            ),
            (
                "child marking does not repair parent",
                valid.replace('sec:markingSystem "Example";', "")
                + 'ex:file pack:hasEntry ex:child. ex:child sec:markingSystem "Example".',
                False,
                "markingSystem",
            ),
            (
                "multiple raw source labels",
                valid + 'ex:file sec:sensitivityLevelText "LOW", "L".',
                False,
                "sensitivityLevelText",
            ),
        ]
    )
    return [(name, prefix + data, expected, SEC + path if path else "") for name, data, expected, path in cases]


def render(rows: list[Case]) -> str:
    """The corpus file: a header line, then one tab-separated line per case."""
    lines = ["# name\tconforms\texpected-path\tbase64 Turtle"]
    for name, source, expected, path in rows:
        lines.append("\t".join([name, str(expected).lower(), path, base64.b64encode(source.encode()).decode()]))
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
        print(f"Wrote {len(rows)} security profile cases to {relative}; rerun tools/_constraint_coverage.py")
        return 0
    if not CORPUS.is_file() or CORPUS.read_text(encoding="utf-8") != rendered:
        print(f"STALE: {relative} is not what the authored cases render to; run this builder with --write")
        return 1
    print(f"CURRENT: {relative} holds the {len(rows)} authored security profile cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
