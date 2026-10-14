"""Write or check the transport integer boundary corpus.

``specification/validation/test/network-competency.tsv`` is generated: ten values per transport
integer property (zero, maximum, overflow, negative, fractions, a string, a typed integer, a
non-finite double and two values), including RFC 768's absent-source-port encoding, as the
four-column corpus rows Jena and the constraint ledger consume. ``--write`` regenerates it;
``--check`` exits 1 when the file is not byte-for-byte what the cases render to. The gate
``tools/test_network_contract.py`` validates the cases against net.ttl and checks the file is
current; it writes nothing.

After ``--write``, rerun ``python tools/_constraint_coverage.py`` and
``python tools/_render_constraint_coverage.py``: the ledger hashes this file.
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "specification/validation/test/network-competency.tsv"
NS = "https://hexplain.io/ns/aspect/networkflow#"
FIELDS = [
    ("sourcePort", 65535),
    ("destinationPort", 65535),
    ("sequenceNumber", 4294967295),
    ("acknowledgmentNumber", 4294967295),
]

#: One case: (name, Turtle, expected conformance, expected result path IRI or "").
Case = tuple[str, str, bool, str]


def cases() -> list[Case]:
    """Every case, property by property; a rejection must report the property as its result path."""
    rows: list[Case] = []
    for field, maximum in FIELDS:
        values = [
            ("zero", "0", True),
            ("maximum", str(maximum), True),
            ("overflow", str(maximum + 1), False),
            ("negative", "-1", False),
            ("fraction", "1.5", False),
            ("decimal integer", "1.0", False),
            ("string", '"1"', False),
            ("typed integer", '"1"^^<http://www.w3.org/2001/XMLSchema#unsignedShort>', True),
            ("nonfinite", '"INF"^^<http://www.w3.org/2001/XMLSchema#double>', False),
            ("two values", "1, 2", False),
        ]
        for label, value, expected in values:
            source = f"<urn:packet> <{NS + field}> {value} ."
            rows.append((field + " " + label, source, expected, NS + field if not expected else ""))
    return rows


def render(rows: list[Case]) -> str:
    """The corpus file: a header line, then one tab-separated line per case."""
    lines = ["# name\tconforms\texpected-path\tbase64 Turtle"]
    for name, source, expected, path in rows:
        lines.append("\t".join([name, str(expected).lower(), path, base64.b64encode(source.encode()).decode()]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate the corpus from the cases")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the corpus is not what --write produces")
    args = parser.parse_args(argv)
    rows = cases()
    rendered = render(rows)
    relative = CORPUS.relative_to(ROOT).as_posix()
    if args.write:
        CORPUS.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {len(rows)} transport boundary cases to {relative}; rerun tools/_constraint_coverage.py")
        return 0
    if not CORPUS.is_file() or CORPUS.read_text(encoding="utf-8") != rendered:
        print(f"STALE: {relative} is not what the cases render to; run this builder with --write")
        return 1
    print(f"CURRENT: {relative} holds the {len(rows)} transport boundary cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
