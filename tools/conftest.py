"""pytest collection for the gates: each ``tools/test_*.py`` is one test that runs the gate.

The gates are standalone scripts with a ``main()`` and a ``__main__`` guard, run by
``tools/run_gates.py`` under a timeout, memory sampling and the source-hash manifest. This
file lets ``pytest tools`` (or ``pytest tools -n auto`` with pytest-xdist installed) run the
same scripts as subprocesses, mapping exit status 77 to a pytest skip and any other non-zero
status to a failure. It is a convenience for editors and IDEs; ``run_gates.py --strict`` remains
the acceptance command, and pytest is not part of the hash-pinned requirements.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_EXIT = 77


class GateItem(pytest.Item):
    def runtest(self) -> None:
        result = subprocess.run(
            [sys.executable, "-u", str(self.path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == SKIP_EXIT:
            pytest.skip(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "gate skipped")
        if result.returncode:
            raise GateFailure(result.returncode, result.stdout + result.stderr)

    def repr_failure(self, excinfo: pytest.ExceptionInfo[BaseException]) -> str:
        if isinstance(excinfo.value, GateFailure):
            code, output = excinfo.value.args
            return f"{self.path.name} exited {code}\n{output}"
        return str(super().repr_failure(excinfo))

    def reportinfo(self) -> tuple[Path, int | None, str]:
        return self.path, 0, self.path.name


class GateFailure(Exception):
    pass


class GateFile(pytest.File):
    def collect(self):  # type: ignore[no-untyped-def]
        yield GateItem.from_parent(self, name=self.path.stem)


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    if file_path.parent == ROOT / "tools" and file_path.name.startswith("test_") and file_path.suffix == ".py":
        return GateFile.from_parent(parent, path=file_path)
    return None
