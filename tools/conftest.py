"""pytest collection for the gates: each offline gate of ``tools/gates.json`` is one test.

The gates are standalone scripts with a ``main()`` and a ``__main__`` guard, run by
``tools/run_gates.py`` under a timeout, memory sampling and the source-hash manifest. This
file lets ``pytest tools`` (or ``pytest tools -n auto`` with pytest-xdist installed) run the
same scripts as subprocesses, mapping exit status 77 to a pytest skip and any other non-zero
status to a failure. The gate list and each gate's timeout come from the manifest, exactly as
the runner takes them, so a gate that is not named ``test_*.py`` (``validate_all``) is collected
and a hung gate fails instead of hanging the session. It is a convenience for editors and IDEs;
``run_gates.py --strict`` remains the acceptance command, and pytest is not part of the
hash-pinned requirements.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from _gate_process import SKIP_EXIT
from _gate_runner import load_gate_manifest

ROOT = Path(__file__).resolve().parents[1]


def offline_gates(root: Path = ROOT) -> dict[str, float]:
    """Timeout in seconds by script name, for every gate the manifest declares offline."""
    manifest = load_gate_manifest(root) or {}
    return {
        name: float(entry["timeout"]) for name, entry in manifest.items() if entry.get("class", "offline") == "offline"
    }


class GateFailure(Exception):
    pass


class GateItem(pytest.Item):
    def __init__(self, *, timeout: float, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.timeout = timeout

    def runtest(self) -> None:
        try:
            result = subprocess.run(
                [sys.executable, "-u", str(self.path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as expired:
            output = expired.stdout if isinstance(expired.stdout, str) else ""
            raise GateFailure(f"timed out after {self.timeout:.0f}s", output) from None
        if result.returncode == SKIP_EXIT:
            pytest.skip(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "gate skipped")
        if result.returncode:
            raise GateFailure(f"exited {result.returncode}", result.stdout + result.stderr)

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException], style: object = None) -> str:
        if isinstance(excinfo.value, GateFailure):
            reason, output = excinfo.value.args
            return f"{self.path.name} {reason}\n{output}"
        return str(super().repr_failure(excinfo))

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, 0, self.path.name


class GateFile(pytest.File):
    def collect(self) -> Iterator[GateItem]:
        yield GateItem.from_parent(self, name=self.path.stem, timeout=offline_gates()[self.path.stem])


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    if file_path.parent == ROOT / "tools" and file_path.suffix == ".py" and file_path.stem in offline_gates():
        return GateFile.from_parent(parent, path=file_path)
    return None
