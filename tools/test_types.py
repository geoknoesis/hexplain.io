"""Static types over the tooling: mypy with the configuration in pyproject.toml.

Every function is annotated and checked (``disallow_untyped_defs``, ``check_untyped_defs``, no
implicit Optional). A finding in any module fails the gate, except in the modules listed in
:data:`PENDING`: those belong to work in progress elsewhere and were not edited when the type
gate was adopted, so their findings are counted and reported rather than failed on. A pending
entry that no longer has a finding fails the gate, so the list can only shrink.

``Any`` is the honest type of parsed JSON and of values from untyped dependencies, so it is not
banned; as a *return* type it is how an unannotated function used to be papered over, and the
number of ``-> Any`` signatures outside the pending modules is held under :data:`ANY_RETURNS`.

mypy is in the hash-pinned requirements; where it is not installed the gate reports that it
could not run (exit 77) rather than passing.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_EXIT = 77
#: Modules whose findings are reported, not failed on (repository-relative glob patterns).
PENDING = (
    "tools/_requirement_ids.py",
)
#: Ceiling on ``-> Any`` return annotations outside the pending modules.
ANY_RETURNS = 10
FINDING = re.compile(r"^(?P<path>[^:\n]+\.py):(?P<line>\d+): error: (?P<message>.*)$", re.M)
ANY_RETURN = re.compile(r"\)\s*->\s*Any\s*:")


def pending(path: str) -> str | None:
    """The pending pattern ``path`` falls under, if any."""
    return next((pattern for pattern in PENDING if fnmatch.fnmatchcase(path, pattern)), None)


def findings(output: str) -> dict[str, list[str]]:
    """mypy's errors by repository-relative POSIX path."""
    by_path: dict[str, list[str]] = {}
    for found in FINDING.finditer(output):
        path = found["path"].replace("\\", "/")
        by_path.setdefault(path, []).append(f"{path}:{found['line']}: {found['message']}")
    return by_path


def any_returns() -> list[str]:
    """Every ``-> Any`` signature outside the pending modules, as ``path:line``."""
    sites = []
    for source in sorted((ROOT / "tools").rglob("*.py")):
        relative = source.relative_to(ROOT).as_posix()
        if pending(relative):
            continue
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
    by_path = findings(run.stdout)
    assert run.returncode == 0 or by_path, f"mypy failed without a finding this gate can read:\n{run.stdout}"
    owned = [line for path, lines in sorted(by_path.items()) if not pending(path) for line in lines]
    assert not owned, f"{len(owned)} type errors:\n  " + "\n  ".join(owned)
    reported = {pattern: sum(len(v) for path, v in by_path.items() if pending(path) == pattern) for pattern in PENDING}
    stale = sorted(pattern for pattern, count in reported.items() if not count)
    assert not stale, "pending modules that are now clean; remove them from PENDING: " + ", ".join(stale)
    returns = any_returns()
    assert len(returns) < ANY_RETURNS, (
        f"{len(returns)} `-> Any` return annotations (ceiling {ANY_RETURNS}); give the newest a real type:\n  "
        + "\n  ".join(returns)
    )
    checked = len(list((ROOT / "tools").rglob("*.py")))
    print(
        f"PASS: {checked} tool modules type-check under the pyproject.toml configuration; "
        f"{len(returns)} `-> Any` returns (ceiling {ANY_RETURNS}); "
        f"{sum(reported.values())} findings reported, not failed on, in {len(PENDING)} pending module patterns"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
