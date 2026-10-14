"""Static defect and style checks over the offline tooling, using the shared lint contract.

`ruff check` applies ruff.toml (defect rules, the 120-column style contract, annotated
signatures and the complexity bound) and `ruff format --check` fails on a module the formatter
would change, so a reformat is never left to the next contributor. tools/conformance/ and
tools/codecs/ are checked with the gates.

No module is exempt: a per-file entry in ruff.toml fails this gate, so a module that breaks a
rule is brought into line rather than listed.

Every text file the tooling writes states its line ending: a ``write_text`` or a text-mode
``open`` for writing without ``newline=`` takes the platform's, and a generator run on Windows
then rewrites a tracked LF file as CRLF.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
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


def exemptions() -> list[str]:
    """The per-file entries of ruff.toml, as ``pattern: codes``: every one exempts modules from the contract."""
    config = tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))["lint"]
    entries: dict[str, list[str]] = config.get("per-file-ignores", {})
    return [f"{pattern}: {', '.join(codes)}" for pattern, codes in entries.items()]


def _write_mode(call: ast.Call) -> str | None:
    """The literal mode of an ``open`` call, positional or keyword, if it has one."""
    positional = call.args[1:] if isinstance(call.func, ast.Name) else call.args
    candidates = [*positional[:1], *(k.value for k in call.keywords if k.arg == "mode")]
    modes = [c.value for c in candidates if isinstance(c, ast.Constant) and isinstance(c.value, str)]
    return modes[-1] if modes else None


def text_writes_without_newline() -> dict[str, list[int]]:
    """Line numbers, by module, of text writes that leave the line ending to the platform."""
    sites: dict[str, list[int]] = {}
    for source in sorted((ROOT / "tools").rglob("*.py")):
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or any(k.arg == "newline" for k in node.keywords):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            mode = _write_mode(node) if name == "open" else None
            if name == "write_text" or (mode is not None and set(mode) & set("wax") and "b" not in mode):
                sites.setdefault(source.relative_to(ROOT).as_posix(), []).append(node.lineno)
    return sites


def check_text_writes() -> None:
    """No text write without ``newline=``."""
    sites = text_writes_without_newline()
    assert not sites, (
        f'text written without newline="\\n" (a tracked file would take the platform line ending): {sites}'
    )


def main() -> int:
    check = ruff("check", "tools", "--no-cache", "--output-format", "concise")
    if check.returncode == 2 and "No module named" in (check.stderr or ""):
        print("SKIP: ruff is not installed; add it from requirements.txt")
        return SKIP_EXIT
    assert check.returncode == 0, (check.stdout or "") + (check.stderr or "")
    formatted = ruff("format", "--check", "tools", "--no-cache")
    assert formatted.returncode == 0, "run `ruff format tools`:\n" + (formatted.stdout or "") + (formatted.stderr or "")
    exempt = exemptions()
    assert not exempt, "ruff.toml exempts modules from the contract; bring them into line instead: " + "; ".join(exempt)
    check_text_writes()
    count = len(list((ROOT / "tools").rglob("*.py")))
    print(
        f"PASS: {count} tool modules pass the shared lint and formatting contract (ruff.toml); every text write "
        "states its line ending"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
