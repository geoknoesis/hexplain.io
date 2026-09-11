"""Executable outcome/timeout probes; optional dependencies cannot masquerade as passes."""
from pathlib import Path
import sys
import tempfile
import contextlib
import io
from _gate_runner import run_gate, main

with contextlib.redirect_stdout(io.StringIO()), tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    for text, expected in [("print('PASS: checked')", "PASS"), ("print('SKIP: dependency absent')", "SKIP"), ("raise SystemExit(1)", "FAIL")]:
        result = run_gate([sys.executable, "-c", text], root, 10)
        assert result["status"] == expected, result
    assert run_gate([sys.executable, "-c", "import time; time.sleep(60)"], root, 0.2)["timed_out"]
    (root/"tools").mkdir()
    (root/"tools/test_optional.py").write_text("print('SKIP: dependency absent')", encoding="utf-8")
    assert main(root, set(), ["--strict"]) == 1
    assert main(root, set(), []) == 0
print("PASS: distinct outcomes, timeout, strict rejection and optional local skips")
