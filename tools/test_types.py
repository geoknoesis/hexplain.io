"""Static types over the tooling: mypy with the configuration in pyproject.toml.

Every function is annotated and checked (``disallow_untyped_defs``, ``check_untyped_defs``, no
implicit Optional), and a finding in any module fails the gate.

``Any`` is the honest type of parsed JSON and of values from untyped dependencies, so it is not
banned; as a *return* type it is how an unannotated function used to be papered over, and the
number of ``-> Any`` signatures is held under :data:`ANY_RETURNS`.

mypy is in the hash-pinned requirements; where it is not installed the gate reports that it
could not run (exit 77) rather than passing.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_EXIT = 77
#: Ceiling on ``-> Any`` return annotations.
ANY_RETURNS = 10
FINDING = re.compile(r"^(?P<path>[^:\n]+\.py):(?P<line>\d+): error: (?P<message>.*)$", re.M)
ANY_RETURN = re.compile(r"\)\s*->\s*Any\s*:")


def findings(output: str) -> list[str]:
    """mypy's errors, each as ``path:line: message`` with a repository-relative POSIX path."""
    errors = []
    for found in FINDING.finditer(output):
        path = found["path"].replace("\\", "/")
        errors.append(f"{path}:{found['line']}: {found['message']}")
    return errors


def any_returns() -> list[str]:
    """Every ``-> Any`` signature, as ``path:line``."""
    sites = []
    for source in sorted((ROOT / "tools").rglob("*.py")):
        relative = source.relative_to(ROOT).as_posix()
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if ANY_RETURN.search(line):
                sites.append(f"{relative}:{number}")
    return sites


def main() -> int:
    if importlib.util.find_spec("mypy") is None:
        print("SKIP: mypy is not installed; add it from requirements.txt")
        return SKIP_EXIT
    run = subprocess.run(
        [sys.executable, "-m", "mypy", "tools", "--no-color-output", "--no-error-summary", "--hide-error-context"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    # 0: clean; 1: findings. Anything else is mypy itself failing (a broken configuration), not a result.
    assert run.returncode in (0, 1), f"mypy could not run (exit {run.returncode}):\n{run.stdout}{run.stderr}"
    errors = findings(run.stdout)
    assert run.returncode == 0 or errors, f"mypy failed without a finding this gate can read:\n{run.stdout}"
    assert not errors, f"{len(errors)} type errors:\n  " + "\n  ".join(errors)
    returns = any_returns()
    assert len(returns) < ANY_RETURNS, (
        f"{len(returns)} `-> Any` return annotations (ceiling {ANY_RETURNS}); give the newest a real type:\n  "
        + "\n  ".join(returns)
    )
    checked = len(list((ROOT / "tools").rglob("*.py")))
    print(
        f"PASS: {checked} tool modules type-check under the pyproject.toml configuration; "
        f"{len(returns)} `-> Any` returns (ceiling {ANY_RETURNS})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
