"""A stand-in writer and parser, for probing the runner (tools/test_conformance_suite.py): it implements nothing.

    python stub_processor.py write <case-dir> <out> <err> [--refuse CATEGORY]
    python stub_processor.py parse <case-dir> <out> <err> [--other-tree] [--refuse CATEGORY]

`write` "serialises" a case's tree by copying the stream the case already has (a Physical Parser case's input.bin,
which is a stream its expected tree was parsed from; for a Writer case, its tree.json, any bytes), or refuses with
the category given. `parse` "parses" by copying the case's expected.json, or, with --other-tree, a tree that differs
from it. Run as the --w-cmd and --pp-cmd of run_suite.py they make every outcome of a round trip on demand, so the
runner's verdicts can be checked without an implementation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    mode, case, out, err, *options = argv
    case_dir = Path(case)
    if "--refuse" in options:
        category = options[options.index("--refuse") + 1]
        Path(err).write_text(json.dumps({"category": category}), encoding="utf-8")
        return 1
    if mode == "write":
        source = case_dir / "input.bin"
        Path(out).write_bytes((source if source.is_file() else case_dir / "tree.json").read_bytes())
        return 0
    tree = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    Path(out).write_text(json.dumps({"other": tree} if "--other-tree" in options else tree), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
