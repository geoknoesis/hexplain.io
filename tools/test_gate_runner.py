"""Executable outcome/timeout probes; optional dependencies cannot masquerade as passes."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from _gate_runner import SKIP_EXIT, gate_workers, load_gate_manifest, run_gate
from _gate_runner import main as run_gates


def check_outcomes(root: Path) -> None:
    """PASS, SKIP and FAIL come from the exit status alone; stdout is never interpreted."""
    for text, expected in [
        ("print('PASS: checked')", "PASS"),
        (f"print('SKIP: dependency absent'); raise SystemExit({SKIP_EXIT})", "SKIP"),
        ("raise SystemExit(1)", "FAIL"),
        # A gate that prints SKIP and exits 0 passed as far as the runner knows: the word is not a verdict.
        ("print('SKIP: dependency absent')", "PASS"),
        # A gate that announces failure but exits 0 is likewise a PASS; the exit status is the contract.
        ("print('FAIL')", "PASS"),
    ]:
        result = run_gate([sys.executable, "-c", text], root, 10)
        assert result["status"] == expected, (text, result)
    assert run_gate([sys.executable, "-c", "import time; time.sleep(60)"], root, 0.2)["timed_out"]
    flood = run_gate(
        [sys.executable, "-c", "import sys; sys.stdout.write('x'*100000)"], root, 10, max_output_chars=1024
    )
    assert flood["status"] == "FAIL" and flood["output_limit_exceeded"]
    assert len(flood["output"]) == 1024
    for invalid in (float("nan"), float("inf"), 0, -1):
        try:
            run_gate([sys.executable, "-c", "pass"], root, invalid)
            raise AssertionError("accepted invalid timeout")
        except ValueError:
            pass
    # Buffered mode retains the output without echoing it; the runner prints it on completion.
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet):
        buffered = run_gate([sys.executable, "-c", "print('held back')"], root, 10, stream=False)
    assert buffered["output"].strip() == "held back" and quiet.getvalue() == "", (buffered, quiet.getvalue())


def check_runner(root: Path) -> None:
    """Strictness, the run record, the gate-hash and source-manifest checks."""
    (root / "tools").mkdir()
    gate = root / "tools/test_optional.py"
    gate.write_text(f"print('SKIP: dependency absent'); raise SystemExit({SKIP_EXIT})", encoding="utf-8", newline="\n")
    assert run_gates(root, set(), ["--strict"]) == 1
    report = root / ".gate-results/summary.json"
    assert json.loads(report.read_text())["status"] == "failed"
    assert run_gates(root, set(), []) == 0
    saved = json.loads(report.read_text())
    assert saved["status"] == "complete"
    assert saved["selected_gates"] == ["test_optional"]
    assert saved["gates"][0]["status"] == "SKIP" and saved["gates"][0]["exit_code"] == SKIP_EXIT
    assert saved["gate_sha256"]["test_optional"] == hashlib.sha256(gate.read_bytes()).hexdigest()
    gate.write_text(
        "import json\n"
        "from pathlib import Path\n"
        "report = json.loads(Path('.gate-results/summary.json').read_text())\n"
        "assert report['status'] == 'running'\n"
        "assert report['gates'] == []\n"
        "raise SystemExit(1)\n",
        encoding="utf-8",
        newline="\n",
    )
    assert run_gates(root, set(), ["--strict"]) == 1
    assert json.loads(report.read_text())["status"] == "failed"
    (root / "specification").mkdir()
    fixture = root / "specification/input.ttl"
    fixture.write_text("original", encoding="utf-8", newline="\n")
    gate.write_text(
        "from pathlib import Path; Path('specification/input.ttl').write_text('changed')",
        encoding="utf-8",
        newline="\n",
    )
    assert run_gates(root, set(), ["--strict"]) == 1
    saved = json.loads(report.read_text())
    assert saved["status"] == "failed"
    assert saved["changed_sources"] == ["specification/input.ttl"]
    assert saved["counts"]["PASS"] == 1  # passing script alone is insufficient
    # The source-manifest digest reaches every gate, so a gate may key a derived cache on it.
    gate.write_text(
        "import os, sys; sys.exit(0 if len(os.environ.get('HEXPLAIN_SOURCE_MANIFEST_SHA256', '')) == 64 else 3)",
        encoding="utf-8",
        newline="\n",
    )
    assert run_gates(root, set(), ["--strict"]) == 0


def check_concurrency(root: Path) -> None:
    """Gates run side by side under --jobs, every outcome is recorded, and the record is name-ordered."""
    tools = root / "tools"
    for gate in tools.glob("test_*.py"):
        gate.unlink()
    for name in ("test_c", "test_a", "test_b"):
        (tools / f"{name}.py").write_text(
            # Each gate announces itself, then waits until all three have: a runner that ran them one
            # after another would leave the first waiting for gates that cannot start, and it fails.
            # Waiting on the others, rather than on a clock, keeps the check sound on a loaded host.
            "import time\n"
            "from pathlib import Path\n"
            f"Path('.gate-results/{name}.started').write_text('started')\n"
            "deadline = time.monotonic() + 120\n"
            "names = ('test_a', 'test_b', 'test_c')\n"
            "while not all(Path(f'.gate-results/{n}.started').exists() for n in names):\n"
            "    if time.monotonic() > deadline:\n"
            "        raise SystemExit(3)\n"
            "    time.sleep(0.05)\n"
            f"print('PASS: {name}')\n",
            encoding="utf-8",
            newline="\n",
        )
    (tools / "test_bad.py").write_text("raise SystemExit(2)\n", encoding="utf-8", newline="\n")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = run_gates(root, set(), ["--jobs", "3"])
    assert code == 1
    saved = json.loads((root / ".gate-results/summary.json").read_text())
    assert [g["gate"] for g in saved["gates"]] == ["test_a", "test_b", "test_bad", "test_c"], saved["gates"]
    assert saved["counts"] == {"PASS": 3, "SKIP": 0, "FAIL": 1}
    assert saved["jobs"] == 3
    # Each of the three passed only because it saw the other two start while it was still running.
    assert all((root / f".gate-results/{n}.started").is_file() for n in ("test_a", "test_b", "test_c"))
    text = out.getvalue()
    assert text.count("RUN test_") == 4 and "PASS: test_a" in text and "FAIL test_bad" in text, text


def check_manifest(root: Path) -> None:
    """With tools/gates.json present, the manifest is the gate list; an undeclared test_*.py fails closed."""
    tools = root / "tools"
    for gate in tools.glob("test_*.py"):
        gate.unlink()
    (tools / "test_listed.py").write_text("print('PASS')\n", encoding="utf-8", newline="\n")
    (tools / "_check_docker.py").write_text("raise SystemExit(1)\n", encoding="utf-8", newline="\n")
    manifest = tools / "gates.json"
    manifest.write_text(
        json.dumps(
            dict(
                schema_version=1,
                gates=[
                    dict(name="test_listed", **{"class": "offline"}, timeout=30),
                    dict(name="_check_docker", **{"class": "docker"}, timeout=30, procs=2),
                ],
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    assert set(load_gate_manifest(root)) == {"test_listed", "_check_docker"}
    assert run_gates(root, set(), ["--strict"]) == 0
    saved = json.loads((root / ".gate-results/summary.json").read_text())
    assert saved["selected_gates"] == ["test_listed"], saved["selected_gates"]
    assert run_gates(root, set(), ["--strict", "--class", "docker"]) == 1
    (tools / "test_unlisted.py").write_text("print('PASS')\n", encoding="utf-8", newline="\n")
    try:
        run_gates(root, set(), ["--strict"])
        raise AssertionError("ran with an undeclared gate")
    except SystemExit as refused:
        assert refused.code == 2, refused.code
    manifest.write_text(
        json.dumps(dict(schema_version=1, gates=[dict(name="test_listed", timeout=0)])),
        encoding="utf-8",
        newline="\n",
    )
    try:
        load_gate_manifest(root)
        raise AssertionError("accepted a non-positive timeout")
    except ValueError:
        pass


def check_workers() -> None:
    """The shared worker-count helper validates HEXPLAIN_GATE_WORKERS and bounds the default."""
    saved = os.environ.pop("HEXPLAIN_GATE_WORKERS", None)
    try:
        assert 1 <= gate_workers() <= 8
        os.environ["HEXPLAIN_GATE_WORKERS"] = "3"
        assert gate_workers() == 3
        for bad in ("0", "-1", "many"):
            os.environ["HEXPLAIN_GATE_WORKERS"] = bad
            try:
                gate_workers()
                raise AssertionError(f"accepted HEXPLAIN_GATE_WORKERS={bad}")
            except ValueError:
                pass
    finally:
        os.environ.pop("HEXPLAIN_GATE_WORKERS", None)
        if saved is not None:
            os.environ["HEXPLAIN_GATE_WORKERS"] = saved


def check_memory_sampling(root: Path) -> None:
    # Memory is the gate resource nobody measured: the worker cap in the parallel gates exists
    # because a concurrent run exhausted host memory, and the evidence recorded wall clock only.
    # Child processes are where that memory goes, so the sample has to include them.
    # Held across several sampling intervals on purpose: the sampler is a sampler, and a peak
    # shorter than its interval is genuinely invisible to it.
    child = run_gate(
        [
            sys.executable,
            "-c",
            "import sys, time; block = bytearray(96*1024*1024); time.sleep(1); sys.stdout.write(str(len(block)))",
        ],
        root,
        60,
    )
    assert child["status"] == "PASS", child
    assert child["peak_rss_bytes"] > 64 * 1024 * 1024, child["peak_rss_bytes"]
    assert child["rss_samples"] > 0, child
    spawner = run_gate(
        [
            sys.executable,
            "-c",
            "import subprocess, sys\n"
            'subprocess.run([sys.executable, "-c", "import time; block = bytearray(192*1024*1024); time.sleep(1); '
            'print(len(block))"], check=True)\n',
        ],
        root,
        120,
    )
    assert spawner["status"] == "PASS", spawner
    assert spawner["peak_rss_bytes"] > 160 * 1024 * 1024, spawner["peak_rss_bytes"]
    assert spawner["peak_processes"] >= 2, spawner


def main() -> int:
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet), tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        check_outcomes(root)
        check_runner(root)
        check_concurrency(root)
        check_manifest(root)
        check_workers()
        check_memory_sampling(root)
    print(
        "PASS: exit-status outcomes, timeout, strict rejection, concurrent scheduling, the gate manifest, "
        "the worker helper and sampled memory"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
