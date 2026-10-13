"""Static defect and style checks over the offline tooling, using the shared lint contract.

`ruff check` applies ruff.toml (defect rules plus the 120-column style contract) and
`ruff format --check` fails on a module the formatter would change, so a reformat is never
left to the next contributor. No module is exempt: tools/conformance/ and tools/codecs/ are
checked with the gates.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_EXIT = 77


def ruff(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run ruff with ``arguments`` from the repository root and capture its output."""
    return subprocess.run(
        [sys.executable, "-m", "ruff", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    check = ruff("check", "tools", "--no-cache", "--output-format", "concise")
    if check.returncode == 2 and "No module named" in (check.stderr or ""):
        print("SKIP: ruff is not installed; add it from requirements.txt")
        return SKIP_EXIT
    assert check.returncode == 0, (check.stdout or "") + (check.stderr or "")
    formatted = ruff("format", "--check", "tools", "--no-cache")
    assert formatted.returncode == 0, "run `ruff format tools`:\n" + (formatted.stdout or "") + (formatted.stderr or "")
    count = len(list((ROOT / "tools").rglob("*.py")))
    print(f"PASS: {count} tool modules pass the shared lint and formatting contract (ruff.toml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
