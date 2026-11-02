"""Executable outcome/timeout probes; optional dependencies cannot masquerade as passes."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import _gate_process
from _gate_process import SKIP_EXIT, kill_tree_windows, run_gate
from _gate_runner import WORKER_CAP, gate_workers, load_gate_manifest, source_manifest
from _gate_runner import main as run_gates
from _gate_schedule import MEMORY_ENV


@contextlib.contextmanager
def environment(**values: str) -> Iterator[None]:
    """Set environment variables for a block and restore whatever was there before."""
    saved = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


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
    overrides = {"PYTHONUTF8": "0", "PYTHONUNBUFFERED": "0", "PYTHONOPTIMIZE": "2"}
    original = overrides.copy()
    with environment(HEXPLAIN_ENV_PROBE="inherited"):
        overridden = run_gate(
            [
                sys.executable,
                "-c",
                "import json, os, sys; print(json.dumps([os.environ.get('PYTHONUTF8'), "
                "os.environ.get('PYTHONUNBUFFERED'), os.environ.get('HEXPLAIN_ENV_PROBE'), "
                "sys.flags.optimize]))",
            ],
            root,
            10,
            stream=False,
            env=overrides,
        )
    assert overridden["status"] == "PASS", overridden
    assert json.loads(overridden["output"]) == ["0", "0", "inherited", 0], overridden
    assert overrides == original, "launching a gate must not mutate its caller's environment mapping"


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


def check_source_inputs(root: Path) -> None:
    """Configuration and binary fixtures affect the run identity; custom output records do not."""
    names = (
        "ruff.toml",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        ".github/workflows/validate.yml",
        "deployment/publication.conf",
        "specification/input.bin",
        "releases/snapshot.zip",
    )
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"original")
        before = source_manifest(root)
        path.write_bytes(b"changed")
        after = source_manifest(root)
        assert before[name] != after[name], name
        path.unlink()
    gate = root / "tools/test_optional.py"
    gate.write_text(
        "from pathlib import Path\nPath('ruff.toml').write_text('changed')\n", encoding="utf-8", newline="\n"
    )
    (root / "ruff.toml").write_text("original", encoding="utf-8", newline="\n")
    assert run_gates(root, set(), ["--strict"]) == 1
    record = json.loads((root / ".gate-results/summary.json").read_text())
    assert record["changed_sources"] == ["ruff.toml"]
    gate.write_text("print('PASS')\n", encoding="utf-8", newline="\n")
    assert run_gates(root, set(), ["--strict", "--json", "custom-results.json"]) == 0
    assert "custom-results.json" not in json.loads((root / "custom-results.json").read_text())["source_sha256"]


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
    # The budget is pinned: read from the host it would depend on what else the machine is doing,
    # and three default-sized estimates (1.5 GiB) do not fit a host with less than that free --
    # the probes then ran one at a time and each timed out waiting for the others.
    with contextlib.redirect_stdout(out), environment(**{MEMORY_ENV: "65536"}):
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


def check_tight_budget_serialises(root: Path) -> None:
    """A memory budget smaller than two estimates runs the gates one at a time, whatever --jobs says."""
    tools = root / "tools"
    for gate in tools.glob("test_*.py"):
        gate.unlink()
    for name in ("test_a", "test_b", "test_c"):
        (tools / f"{name}.py").write_text(
            # Each gate fails if another is running beside it: it holds a marker for its whole
            # life and looks for anyone else's. The pause gives an overlapping gate time to appear.
            "import time\n"
            "from pathlib import Path\n"
            f"mine = Path('.gate-results/{name}.alone')\n"
            "mine.write_text('running')\n"
            "time.sleep(0.4)\n"
            "others = [p.name for p in Path('.gate-results').glob('*.alone') if p != mine]\n"
            "mine.unlink()\n"
            "raise SystemExit(4 if others else 0)\n",
            encoding="utf-8",
            newline="\n",
        )
    out = io.StringIO()
    # 600 MiB holds one unrecorded gate (512 MiB estimated) and never two.
    with contextlib.redirect_stdout(out), environment(**{MEMORY_ENV: "600"}):
        assert run_gates(root, set(), ["--jobs", "3"]) == 0, out.getvalue()
    saved = json.loads((root / ".gate-results/summary.json").read_text())
    assert saved["counts"] == {"PASS": 3, "SKIP": 0, "FAIL": 0}, saved["counts"]
    assert saved["memory_budget"] == "fixed at 600 MiB", saved["memory_budget"]
    # The same gates under a budget that holds all three do overlap, so the probe can tell.
    with contextlib.redirect_stdout(out), environment(**{MEMORY_ENV: "65536"}):
        assert run_gates(root, set(), ["--jobs", "3"]) == 1, "the overlap probe did not detect concurrent gates"
    for bad in ("0", "-5", "lots"):
        with environment(**{MEMORY_ENV: bad}):
            try:
                run_gates(root, set(), [])
                raise AssertionError(f"accepted {MEMORY_ENV}={bad}")
            except SystemExit as refused:
                assert refused.code == 2, refused.code


def check_effective_procs(root: Path) -> None:
    """A gate is told to use exactly the processes the budget counted for it."""
    tools = root / "tools"
    for gate in tools.glob("test_*.py"):
        gate.unlink()
    (tools / "_check_docker.py").unlink(missing_ok=True)
    expected = max(1, min(WORKER_CAP, (os.cpu_count() or 1) // 2))
    for name in ("test_fan", "test_single"):
        (tools / f"{name}.py").write_text(
            "import os\nprint('WORKERS=' + os.environ['HEXPLAIN_GATE_WORKERS'])\n", encoding="utf-8", newline="\n"
        )
    (tools / "gates.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                gates=[dict(name="test_fan", timeout=30, procs=64), dict(name="test_single", timeout=30)],
            )
        ),
        encoding="utf-8",
        newline="\n",
    )
    out = io.StringIO()
    with contextlib.redirect_stdout(out), environment(**{MEMORY_ENV: "65536"}):
        assert run_gates(root, set(), ["--strict", "--jobs", "2"]) == 0, out.getvalue()
    rows = {r["gate"]: r for r in json.loads((root / ".gate-results/summary.json").read_text())["gates"]}
    # Declared 64, but the gate's share of the machine at two jobs and the worker cap both bind;
    # the budget's number and the gate's HEXPLAIN_GATE_WORKERS are the same number.
    assert rows["test_fan"]["procs"] == expected, rows["test_fan"]
    assert rows["test_fan"]["output"].strip() == f"WORKERS={expected}", rows["test_fan"]["output"]
    assert rows["test_single"]["procs"] == 1 and rows["test_single"]["output"].strip() == "WORKERS=1", rows
    # An explicit HEXPLAIN_GATE_WORKERS in the caller's environment is a further cap, never a raise.
    with contextlib.redirect_stdout(out), environment(**{MEMORY_ENV: "65536", "HEXPLAIN_GATE_WORKERS": "1"}):
        assert run_gates(root, set(), ["--strict", "--jobs", "2"]) == 0, out.getvalue()
    rows = {r["gate"]: r for r in json.loads((root / ".gate-results/summary.json").read_text())["gates"]}
    assert rows["test_fan"]["procs"] == 1 and rows["test_fan"]["output"].strip() == "WORKERS=1", rows["test_fan"]
    (tools / "gates.json").unlink()


def check_kill_fallback() -> None:
    """A tree kill that hangs or cannot start degrades to killing the gate; it never raises."""
    for failure in (subprocess.TimeoutExpired("taskkill", 10), FileNotFoundError("taskkill")):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], text=True)

        def unavailable(*_args: object, _failure: BaseException = failure, **_kwargs: object) -> None:
            raise _failure

        kill_tree_windows(proc, run=unavailable)
        assert proc.wait(timeout=30) != 0, "the gate survived a failed tree kill"
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], text=True)
    try:
        kill_tree_windows(proc, run=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1))
        assert proc.wait(timeout=10) != 0, "the gate survived a nonzero taskkill result"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)


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
    assert set(load_gate_manifest(root) or {}) == {"test_listed", "_check_docker"}
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


def check_manifest_boundaries(root: Path) -> None:
    """Malformed manifests fail at loading, before any gate can be launched."""
    manifest = root / "tools/gates.json"
    valid = dict(name="test_listed", timeout=30, procs=1)
    invalid: list[object] = [None, [], {"schema_version": 1}, {"schema_version": 1, "gates": {}}]
    invalid_entries: list[object] = [None, [], "test_listed"]
    invalid_entries += [dict(valid, timeout=value) for value in (True, float("nan"), float("inf"), 10**400, "30")]
    invalid_entries += [dict(valid, procs=value) for value in (True, 0, -1, 1.5, "2")]
    invalid_names: tuple[object, ...] = (None, [], {}, True, "", "  ")
    invalid_entries += [dict(valid, name=value) for value in invalid_names]
    invalid += [{"schema_version": 1, "gates": [entry]} for entry in invalid_entries]
    for document in invalid:
        manifest.write_text(json.dumps(document), encoding="utf-8", newline="\n")
        try:
            load_gate_manifest(root)
            raise AssertionError(f"accepted malformed manifest {document!r}")
        except ValueError as error:
            assert str(manifest) in str(error), error
    for timeout in (0.5, 30, 1e308):
        manifest.write_text(
            json.dumps({"schema_version": 1, "gates": [dict(valid, timeout=timeout)]}),
            encoding="utf-8",
            newline="\n",
        )
        loaded = load_gate_manifest(root)
        assert loaded is not None and loaded["test_listed"]["timeout"] == timeout


def check_launch_failures(root: Path) -> None:
    """A worker exception is a recorded FAIL; other gates still run and the report closes."""
    (root / "tools").mkdir(parents=True)
    for name in ("test_broken", "test_healthy"):
        (root / "tools" / f"{name}.py").write_text("print('PASS')\n", encoding="utf-8", newline="\n")
    for jobs in (1, 2):
        for failure in (OSError("process creation failed"), RuntimeError("worker failed")):

            def launch(command: list[str], cwd: Path, timeout: float, **kwargs: Any) -> dict[str, Any]:
                if Path(command[-1]).stem == "test_broken":
                    raise failure
                return run_gate(command, cwd, timeout, **kwargs)

            with patch("_gate_runner.run_gate", side_effect=launch):
                assert run_gates(root, set(), ["--strict", "--jobs", str(jobs)]) == 1
            saved = json.loads((root / ".gate-results/summary.json").read_text())
            assert saved["status"] == "failed" and saved["counts"] == {"PASS": 1, "SKIP": 0, "FAIL": 1}, saved
            rows = {row["gate"]: row for row in saved["gates"]}
            assert rows["test_healthy"]["status"] == "PASS", rows
            broken = rows["test_broken"]
            assert broken["status"] == "FAIL" and broken["exit_code"] is None, broken
            assert broken["worker_error"] == type(failure).__name__ and str(failure) in broken["output"], broken
            assert broken["duration_seconds"] >= 0 and broken["peak_rss_bytes"] is None, broken
            assert saved["changed_sources"] == [], saved


def cleanup_interrupted_probe(captured: dict[str, Any]) -> None:
    """Keep a failing regression from leaving its probe process or reader behind."""
    if "sampling_stopped" in captured:
        captured["sampling_stopped"].set()
    if "process" in captured:
        proc = captured["process"]
        if proc.poll() is None:
            _gate_process.terminate(proc)
        proc.wait(timeout=10)
    if "reader" in captured:
        captured["reader"].close()


def check_interrupted_cleanup(root: Path) -> None:
    """Real children and background readers are cleaned up when setup or collection fails."""
    create_process = subprocess.Popen
    sample_memory = _gate_process.sample_memory
    start_thread = threading.Thread.start
    for stage in ("collector", "reader", "sampler"):
        captured: dict[str, Any] = {}

        def create(*args: Any, **kwargs: Any) -> subprocess.Popen[str]:
            proc = create_process(*args, **kwargs)
            if args[0][0] == sys.executable:
                captured["process"] = proc
            return proc

        def sample(*args: Any, **kwargs: Any) -> dict[str, Any]:
            captured["sampling_stopped"] = args[1]
            return sample_memory(*args, **kwargs)

        def interrupted(*args: Any) -> None:
            captured["reader"] = args[1]
            raise RuntimeError("collector interrupted")

        def fail_sampler_once(thread: threading.Thread) -> None:
            if not captured.get("sampler_failed"):
                captured["sampler_failed"] = True
                raise RuntimeError("sampler failed")
            start_thread(thread)

        try:
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch("_gate_process.subprocess.Popen", side_effect=create))
                stack.enter_context(patch("_gate_process.sample_memory", side_effect=sample))
                if stage == "collector":
                    stack.enter_context(patch("_gate_process._collect", side_effect=interrupted))
                elif stage == "reader":
                    stack.enter_context(patch("_gate_process._Reader", side_effect=RuntimeError("reader failed")))
                else:
                    stack.enter_context(patch("threading.Thread.start", new=fail_sampler_once))
                try:
                    run_gate([sys.executable, "-c", "import time; time.sleep(60)"], root, 10, stream=False)
                    raise AssertionError(f"{stage} failure was swallowed")
                except RuntimeError:
                    pass
            proc = captured["process"]
            assert proc.poll() is not None and proc.stdout.closed, (stage, proc.pid)
            if stage != "sampler":
                assert captured["sampling_stopped"].is_set(), stage
            if stage == "collector":
                assert not captured["reader"].thread.is_alive(), stage
        finally:
            cleanup_interrupted_probe(captured)


def check_workers() -> None:
    """The shared worker-count helper validates HEXPLAIN_GATE_WORKERS and bounds the default."""
    saved = os.environ.pop("HEXPLAIN_GATE_WORKERS", None)
    try:
        assert 1 <= gate_workers() <= WORKER_CAP
        os.environ["HEXPLAIN_GATE_WORKERS"] = "3"
        assert gate_workers() == 3
        # The cap holds on the environment path too: the variable narrows a gate, it never widens it.
        os.environ["HEXPLAIN_GATE_WORKERS"] = "64"
        assert gate_workers() == WORKER_CAP, gate_workers()
        assert gate_workers(default_cap=2) == 2
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
    # Under the runner this gate is itself handed a worker count; the runs it starts must be
    # planned as a standalone run would be, not capped by what the outer run gave this gate.
    inherited = os.environ.pop("HEXPLAIN_GATE_WORKERS", None)
    try:
        with (
            tempfile.TemporaryDirectory() as temp,
            contextlib.redirect_stdout(quiet),
            contextlib.redirect_stderr(quiet),
        ):
            run_checks(Path(temp))
    finally:
        if inherited is not None:
            os.environ["HEXPLAIN_GATE_WORKERS"] = inherited
    print(
        "PASS: exit-status outcomes, timeout, strict rejection, concurrent scheduling, a tight memory budget "
        "serialising, the gate manifest, effective process counts, the worker helper, the tree-kill fallback "
        "and sampled memory"
    )
    return 0


def run_checks(root: Path) -> None:
    """Every check, in the order they build on the shared tree."""
    check_outcomes(root)
    check_runner(root)
    check_source_inputs(root)
    check_concurrency(root)
    check_tight_budget_serialises(root)
    check_manifest(root)
    check_manifest_boundaries(root)
    check_launch_failures(root / "launch-failures")
    check_interrupted_cleanup(root)
    check_effective_procs(root)
    check_workers()
    check_kill_fallback()
    check_memory_sampling(root)


if __name__ == "__main__":
    raise SystemExit(main())
