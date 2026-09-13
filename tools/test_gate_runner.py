"""Executable outcome/timeout probes; optional dependencies cannot masquerade as passes."""
from pathlib import Path
import sys
import tempfile
import contextlib
import io
import json
import hashlib
from _gate_runner import run_gate, main

with contextlib.redirect_stdout(io.StringIO()), tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    for text, expected in [("print('PASS: checked')", "PASS"), ("print('SKIP: dependency absent')", "SKIP"), ("raise SystemExit(1)", "FAIL")]:
        result = run_gate([sys.executable, "-c", text], root, 10)
        assert result["status"] == expected, result
    assert run_gate([sys.executable, "-c", "import time; time.sleep(60)"], root, 0.2)["timed_out"]
    flood = run_gate([sys.executable, "-c", "import sys; sys.stdout.write('x'*100000)"], root, 10, max_output_chars=1024)
    assert flood["status"] == "FAIL" and flood["output_limit_exceeded"]
    assert len(flood["output"]) == 1024
    for invalid in (float('nan'), float('inf'), 0, -1):
        try:
            run_gate([sys.executable, "-c", "pass"], root, invalid)
            raise AssertionError("accepted invalid timeout")
        except ValueError:
            pass
    (root/"tools").mkdir()
    (root/"tools/test_optional.py").write_text("print('SKIP: dependency absent')", encoding="utf-8")
    assert main(root, set(), ["--strict"]) == 1
    report = root/".gate-results/summary.json"
    assert json.loads(report.read_text())["status"] == "failed"
    assert main(root, set(), []) == 0
    saved = json.loads(report.read_text())
    assert saved["status"] == "complete"
    assert saved["selected_gates"] == ["test_optional"]
    assert saved["gate_sha256"]["test_optional"] == hashlib.sha256((root/"tools/test_optional.py").read_bytes()).hexdigest()
    (root/"tools/test_optional.py").write_text("""import json
from pathlib import Path
report = json.loads(Path('.gate-results/summary.json').read_text())
assert report['status'] == 'running'
assert report['gates'] == []
raise SystemExit(1)
""", encoding="utf-8")
    assert main(root, set(), ["--strict"]) == 1
    assert json.loads(report.read_text())["status"] == "failed"
    (root/"specification").mkdir()
    fixture = root/"specification/input.ttl"
    fixture.write_text("original", encoding="utf-8")
    (root/"tools/test_optional.py").write_text("from pathlib import Path; Path('specification/input.ttl').write_text('changed')", encoding="utf-8")
    assert main(root, set(), ["--strict"]) == 1
    saved = json.loads(report.read_text())
    assert saved["status"] == "failed"
    assert saved["changed_sources"] == ["specification/input.ttl"]
    assert saved["counts"]["PASS"] == 1  # passing script alone is insufficient
print("PASS: distinct outcomes, timeout, strict rejection and optional local skips")
