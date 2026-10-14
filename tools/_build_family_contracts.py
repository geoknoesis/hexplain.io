"""Write or check the retained form of the authored module contracts.

``specification/validation/test/family-contracts.json`` is generated: it is the cases of
``tools/_family_contract_cases.py`` as the plain rows Jena and the constraint ledger consume.
``--write`` regenerates it; ``--check`` exits 1 when the file is not byte-for-byte what the
authored cases render to. The gate ``tools/test_family_contract.py`` validates the cases and
compares them with the retained file as graphs; it writes nothing.

After ``--write``, rerun ``python tools/_constraint_coverage.py`` and
``python tools/_render_constraint_coverage.py``: the ledger hashes this file.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _family_contract_cases import cases

ROOT = Path(__file__).resolve().parents[1]
RETAINED = ROOT / "specification/validation/test/family-contracts.json"


def render(rows: list[dict[str, Any]]) -> str:
    """The retained file's text for ``rows``; case names are evidence identifiers and must be unique."""
    names = [row["name"] for row in rows]
    assert len(set(names)) == len(names), "Case names must be unique evidence identifiers"
    return json.dumps(rows, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate the retained file from the authored cases")
    mode.add_argument("--check", action="store_true", help="Exit 1 if the retained file is not what --write produces")
    args = parser.parse_args(argv)
    rows = cases()
    expected = render(rows)
    relative = RETAINED.relative_to(ROOT).as_posix()
    if args.write:
        RETAINED.write_text(expected, encoding="utf-8", newline="\n")
        print(f"Wrote {len(rows)} cases to {relative}; rerun tools/_constraint_coverage.py")
        return 0
    if not RETAINED.is_file() or RETAINED.read_text(encoding="utf-8") != expected:
        print(f"STALE: {relative} is not what the authored cases render to; run this builder with --write")
        return 1
    print(f"CURRENT: {relative} holds the {len(rows)} authored cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
