"""Concurrent, bounded gate execution with explicit PASS/SKIP/FAIL outcomes.

Gates are independent scripts under tools/, declared in tools/gates.json. The runner schedules
them across worker threads, each launching one subprocess, and bounds the concurrency three ways:
``--jobs`` (default: the smaller of the CPU count and four), a process budget from each gate's
declared ``procs``, and a memory budget derived from the peak RSS the previous run recorded for
the gate (a conservative default when nothing was recorded). Output is buffered per gate and
flushed when the gate finishes, so interleaving never garbles a report; with ``--jobs 1`` it
streams live as before. The summary lists gates in name order whatever the completion order.

A gate reports SKIP by exiting with status 77 (``SKIP_EXIT``); any other non-zero status is a
FAIL. Nothing is inferred from a gate's stdout.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import platform
import queue
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # Recorded as "not sampled" rather than failing a gate run.
    psutil = None

#: Exit status by which a gate reports that it did not run (optional dependency absent, ...).
SKIP_EXIT = 77
#: Interpreter floor; pyproject.toml states the same bound for installers.
PYTHON_FLOOR = (3, 11)
#: Memory estimate for a gate the previous run did not sample (bytes).
DEFAULT_GATE_RSS = 512 * 1024 * 1024
#: Gate classes a manifest may declare and what runs them.
GATE_CLASSES = ("offline", "docker", "browser")
#: Environment variable through which the runner hands gates the source manifest digest.
MANIFEST_ENV = "HEXPLAIN_SOURCE_MANIFEST_SHA256"
#: Environment variable bounding the worker processes of a parallel gate.
WORKERS_ENV = "HEXPLAIN_GATE_WORKERS"


def gate_workers(default_cap: int = 8) -> int:
    """Worker-process count for a gate that fans out: ``HEXPLAIN_GATE_WORKERS`` or a bounded default.

    Bounded by default because an earlier concurrent run exhausted host memory. The runner sets
    the variable from its own job count so that concurrently scheduled gates do not multiply.
    """
    requested = os.environ.get(WORKERS_ENV)
    if requested:
        try:
            count = int(requested)
        except ValueError:
            raise ValueError(f"{WORKERS_ENV} must be an integer, not {requested!r}") from None
        if count < 1:
            raise ValueError(f"{WORKERS_ENV} must be at least 1")
        return count
    return max(1, min(os.cpu_count() or 1, default_cap))


def _sample_memory(pid: int, stopped: threading.Event, interval: float = 0.05) -> dict[str, Any]:
    """Peak resident bytes of a gate and its descendants, and the peak process count.

    The parallel gates fan out into worker processes, and it was a concurrent run exhausting host
    memory that forced the worker cap -- so the number that matters is the whole tree's, not the
    parent's. Sampling is a lower bound on the true peak: a spike between samples is missed, and a
    process that exits between samples is never seen at all.
    """
    peak, processes, samples = 0, 0, 0
    if psutil is None:
        return dict(
            peak_rss_bytes=None,
            peak_processes=None,
            rss_samples=0,
            memory_note="psutil is not installed; gate memory was not sampled",
        )
    try:
        parent = psutil.Process(pid)
    except psutil.Error:
        return dict(
            peak_rss_bytes=None,
            peak_processes=None,
            rss_samples=0,
            memory_note="gate process exited before sampling began",
        )
    while not stopped.is_set():
        total, live = 0, 0
        try:
            for process in [parent, *parent.children(recursive=True)]:
                try:
                    total += process.memory_info().rss
                    live += 1
                except psutil.Error:
                    continue
        except psutil.Error:
            break
        if live:
            samples += 1
            peak = max(peak, total)
            processes = max(processes, live)
        stopped.wait(interval)
    return dict(
        peak_rss_bytes=peak,
        peak_processes=processes,
        rss_samples=samples,
        memory_note="sampled sum of the gate and its descendants; a lower bound, not an exact peak",
    )


def run_gate(
    command: list[str],
    cwd: Path,
    timeout: float,
    heartbeat: float = 15,
    max_output_chars: int = 1_000_000,
    stream: bool = True,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run one gate to completion, bounded by ``timeout`` seconds and ``max_output_chars`` of output.

    With ``stream`` the gate's output is echoed as it arrives; otherwise it is only retained in the
    returned record, for a caller that prints it once the gate is done.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    if max_output_chars < 1:
        raise ValueError("output limit must be positive")
    started = time.monotonic()
    environment = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1", **(env or {}))
    environment.pop("PYTHONOPTIMIZE", None)
    proc = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=(os.name != "nt"),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    output: queue.Queue[str | None] = queue.Queue(maxsize=16)
    stopped = threading.Event()
    sampled: dict[str, Any] = {}
    sampling_stopped = threading.Event()
    sampler = threading.Thread(target=lambda: sampled.update(_sample_memory(proc.pid, sampling_stopped)), daemon=True)
    sampler.start()

    def enqueue(value: str | None) -> None:
        while not stopped.is_set():
            try:
                output.put(value, timeout=0.1)
                return
            except queue.Full:
                pass

    def read() -> None:
        try:
            while not stopped.is_set():
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                enqueue(chunk)
        finally:
            enqueue(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def terminate() -> None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)

    lines: list[str] = []
    expired, next_heartbeat = False, started + heartbeat
    retained, output_exceeded = 0, False
    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            expired = True
            terminate()
            break
        try:
            line = output.get(timeout=min(1, max(0.01, timeout - elapsed)))
        except queue.Empty:
            line = ""
        if line is None:
            break
        if line:
            available = max_output_chars - retained
            kept = line[:available]
            lines.append(kept)
            retained += len(kept)
            if stream:
                print(kept, end="", flush=True)
            if len(line) > available:
                output_exceeded = True
                terminate()
                break
        if stream and time.monotonic() >= next_heartbeat:
            print(f"  RUNNING {Path(command[-1]).name}: {elapsed:.0f}s", flush=True)
            next_heartbeat = time.monotonic() + heartbeat
    stopped.set()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # The gate ignored its end (a timed-out gate that survived the kill, or a gate whose
        # pipe closed before it exited): kill the tree and wait once more, bounded.
        terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
    sampling_stopped.set()
    sampler.join(timeout=5)
    reader.join(timeout=1)
    if not reader.is_alive():
        proc.stdout.close()
    text = "".join(lines)
    if expired or output_exceeded or proc.returncode is None or (proc.returncode and proc.returncode != SKIP_EXIT):
        status = "FAIL"
    elif proc.returncode == SKIP_EXIT:
        status = "SKIP"
    else:
        status = "PASS"
    return dict(
        status=status,
        exit_code=proc.returncode,
        timed_out=expired,
        output_limit_exceeded=output_exceeded,
        duration_seconds=round(time.monotonic() - started, 3),
        **sampled,
        output=text,
    )


def source_manifest(root: Path) -> dict[str, str]:
    """Byte hashes for declared local validation inputs; no external-file traversal."""
    # Published documents are validation inputs too: link, governance and page-equality
    # gates read them, so a document changed during a run must invalidate acceptance the
    # same way a changed shape or script does.
    suffixes = {".py", ".ttl", ".json", ".tsv", ".in", ".txt", ".html", ".css", ".md"}
    paths = []
    for directory in ("tools", "specification", "authoring"):
        base = root / directory
        if base.exists():
            paths.extend(
                p for p in base.rglob("*") if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts
            )
    # Published root artifacts that gates read but no scanned directory contains.
    paths.extend(
        p
        for p in (
            root / "requirements.txt",
            root / "pyproject.toml",
            root / "index.html",
            root / "robots.txt",
            root / "sitemap.xml",
        )
        if p.exists()
    )
    result = {}
    for path in sorted(set(paths)):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Validation input escapes repository: {path}")
        with path.open("rb") as stream:
            result[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def manifest_digest(manifest: dict[str, str]) -> str:
    """One digest over a source manifest, the key under which gates may cache derived inputs."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


def load_gate_manifest(root: Path) -> dict[str, dict[str, Any]] | None:
    """The declared gates of tools/gates.json by name, or None when a tree declares none.

    Without a manifest the runner discovers ``tools/*.py`` (test fixtures use that); with one,
    every discovered ``test_*.py`` must be declared, or the run fails closed.
    """
    path = root / "tools/gates.json"
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported gate manifest schema {document.get('schema_version')!r}")
    gates: dict[str, dict[str, Any]] = {}
    for entry in document["gates"]:
        name = entry["name"]
        if name in gates:
            raise ValueError(f"{path}: gate {name} is declared twice")
        if entry.get("class", "offline") not in GATE_CLASSES:
            raise ValueError(f"{path}: gate {name} has unknown class {entry.get('class')!r}")
        if not isinstance(entry.get("timeout"), int | float) or entry["timeout"] <= 0:
            raise ValueError(f"{path}: gate {name} needs a positive timeout")
        if not isinstance(entry.get("procs", 1), int) or entry.get("procs", 1) < 1:
            raise ValueError(f"{path}: gate {name} needs a positive procs count")
        gates[name] = dict(entry)
    return gates


def _previous_costs(path: Path) -> dict[str, dict[str, Any]]:
    """Duration and sampled peak RSS per gate from the last complete summary, if readable."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(record, dict):
        return {}
    costs = {}
    for row in record.get("gates", []):
        if isinstance(row, dict) and isinstance(row.get("gate"), str):
            costs[row["gate"]] = row
    return costs


def _memory_budget() -> int | None:
    """Bytes the concurrently running gates may claim together, from what the host has free now."""
    if psutil is None:
        return None
    try:
        return int(psutil.virtual_memory().available * 0.8)
    except psutil.Error:
        return None


class _Scheduler:
    """Launch gates as jobs, process and memory budgets allow; longest recorded gate first."""

    def __init__(
        self,
        gates: list[dict[str, Any]],
        jobs: int,
        previous: dict[str, dict[str, Any]],
        memory_budget: int | None,
        process_budget: int,
    ) -> None:
        self.jobs = jobs
        self.memory_budget = memory_budget
        self.process_budget = process_budget
        self.estimate = {
            g["name"]: (previous.get(g["name"], {}).get("peak_rss_bytes") or DEFAULT_GATE_RSS) for g in gates
        }
        # Longest first: the recorded duration, then the name, so the order is reproducible.
        self.pending = sorted(
            gates, key=lambda g: (-(previous.get(g["name"], {}).get("duration_seconds") or 0.0), g["name"])
        )
        self.running: dict[Future[dict[str, Any]], dict[str, Any]] = {}

    def _fits(self, gate: dict[str, Any]) -> bool:
        if not self.running:
            return True  # Something always runs, however large.
        if len(self.running) >= self.jobs:
            return False
        memory = sum(self.estimate[g["name"]] for g in self.running.values()) + self.estimate[gate["name"]]
        if self.memory_budget is not None and memory > self.memory_budget:
            return False
        procs = sum(g.get("procs", 1) for g in self.running.values()) + gate.get("procs", 1)
        return procs <= self.process_budget

    def next_ready(self) -> dict[str, Any] | None:
        for index, gate in enumerate(self.pending):
            if self._fits(gate):
                return self.pending.pop(index)
        return None


def _python_floor(parser: argparse.ArgumentParser) -> None:
    if sys.version_info < PYTHON_FLOOR:
        parser.error(
            f"Python {'.'.join(map(str, PYTHON_FLOOR))} or newer is required; running {platform.python_version()}"
        )


def _select_gates(
    root: Path,
    excluded: set[str],
    manifest: dict[str, dict[str, Any]] | None,
    gate_class: str,
    filters: list[str],
    default_timeout: float,
) -> list[dict[str, Any]]:
    tools = root / "tools"
    if manifest is None:
        discovered = sorted(p for p in tools.glob("*.py") if p.stem not in excluded and not p.stem.startswith("_"))
        gates = [dict(name=p.stem, path=p, timeout=default_timeout, procs=1) for p in discovered]
    else:
        unlisted = sorted(p.stem for p in tools.glob("test_*.py") if p.stem not in manifest)
        if unlisted:
            raise ValueError("gates not declared in tools/gates.json: " + ", ".join(unlisted))
        gates = []
        for name, entry in sorted(manifest.items()):
            if entry.get("class", "offline") != gate_class:
                continue
            path = tools / f"{name}.py"
            if not path.is_file():
                raise ValueError(f"tools/gates.json declares {name} but tools/{name}.py does not exist")
            gates.append(dict(entry, name=name, path=path))
    if filters:
        gates = [g for g in gates if any(f in g["name"] for f in filters)]
    return gates


def main(root: Path, excluded: set[str], argv: list[str] | None = None) -> int:
    """Run the selected gates and write ``.gate-results/summary.json``; 0 when acceptance holds."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("filters", nargs="*", help="Run only gates whose name contains one of these")
    parser.add_argument("--strict", action="store_true", help="A skipped required check fails acceptance")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum seconds per gate; overrides the manifest's per-gate timeouts (default: the manifest, else 3600)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="Gates to run concurrently (default: min(CPU count, 4); 1 streams each gate's output live)",
    )
    parser.add_argument(
        "--class",
        dest="gate_class",
        choices=GATE_CLASSES,
        default="offline",
        help="Which declared gate class to run (default: offline)",
    )
    parser.add_argument("--json", default=".gate-results/summary.json", help="Where to write the run record")
    args = parser.parse_args(argv)
    _python_floor(parser)
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error("--timeout must be positive")
    jobs = args.jobs if args.jobs is not None else max(1, min(os.cpu_count() or 1, 4))
    if jobs < 1:
        parser.error("--jobs must be at least 1")
    if args.strict and os.environ.get("HEXPLAIN_ROUNDTRIP_SKIP_ON_BUILD_ERROR") == "1":
        parser.error("strict mode forbids HEXPLAIN_ROUNDTRIP_SKIP_ON_BUILD_ERROR")
    try:
        manifest = load_gate_manifest(root)
        gates = _select_gates(root, excluded, manifest, args.gate_class, args.filters, args.timeout or 3600)
    except ValueError as error:
        parser.error(str(error))
    if not gates:
        parser.error("no gates matched")
    if args.timeout is not None:
        for gate in gates:
            gate["timeout"] = min(float(gate["timeout"]), args.timeout)
    destination = root / args.json
    destination.parent.mkdir(parents=True, exist_ok=True)
    previous = _previous_costs(destination)
    sources = source_manifest(root)
    records: dict[str, dict[str, Any]] = {}
    evidence: dict[str, Any] = dict(
        schema_version=4,
        strict=args.strict,
        status="running",
        started_utc=datetime.now(UTC).isoformat(),
        python=sys.version,
        platform=platform.platform(),
        jobs=jobs,
        gate_class=args.gate_class,
        source_sha256=sources,
        source_manifest_sha256=manifest_digest(sources),
        selected_gates=[g["name"] for g in gates],
        gate_sha256={g["name"]: hashlib.sha256(g["path"].read_bytes()).hexdigest() for g in gates},
        gates=[],
    )
    lock = threading.Lock()

    def save() -> None:
        with lock:
            evidence["gates"] = [records[name] for name in sorted(records)]
            temporary = destination.with_suffix(destination.suffix + ".tmp")
            temporary.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
            temporary.replace(destination)

    save()  # Replace stale results before starting any gate.
    stream = jobs == 1
    # A gate that fans out gets a share of the machine, not all of it, when others run beside it.
    child_env = {MANIFEST_ENV: evidence["source_manifest_sha256"]}
    if WORKERS_ENV not in os.environ and jobs > 1:
        child_env[WORKERS_ENV] = str(max(1, (os.cpu_count() or 1) // jobs))
    scheduler = _Scheduler(gates, jobs, previous, _memory_budget(), max(os.cpu_count() or 1, jobs))

    def launch(gate: dict[str, Any]) -> dict[str, Any]:
        row = dict(
            gate=gate["name"],
            **run_gate(
                [sys.executable, "-u", str(gate["path"])],
                root,
                float(gate["timeout"]),
                stream=stream,
                env=child_env,
            ),
        )
        if hashlib.sha256(gate["path"].read_bytes()).hexdigest() != evidence["gate_sha256"][gate["name"]]:
            row.update(status="FAIL", source_changed=True)
        return row

    heartbeat_at = time.monotonic() + 15
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        while scheduler.pending or scheduler.running:
            while (gate := scheduler.next_ready()) is not None:
                print(f"RUN {gate['name']}", flush=True)
                scheduler.running[pool.submit(launch, gate)] = gate
            done, _ = wait(list(scheduler.running), timeout=1, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda f: scheduler.running[f]["name"]):
                scheduler.running.pop(future)
                row = future.result()
                records[row["gate"]] = row
                if not stream and row["output"]:
                    print(row["output"], end="" if row["output"].endswith("\n") else "\n", flush=True)
                print(f"{row['status']} {row['gate']} ({row['duration_seconds']:.1f}s)", flush=True)
                save()
            if not stream and scheduler.running and time.monotonic() >= heartbeat_at:
                names = ", ".join(sorted(g["name"] for g in scheduler.running.values()))
                print(f"  RUNNING {names}", flush=True)
                heartbeat_at = time.monotonic() + 15
    rows = [records[name] for name in sorted(records)]
    counts = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "SKIP", "FAIL")}
    print(f"{counts['PASS']} passed, {counts['SKIP']} skipped, {counts['FAIL']} failed", flush=True)
    final_sources = source_manifest(root)
    changed = sorted(
        path for path in sources.keys() | final_sources.keys() if sources.get(path) != final_sources.get(path)
    )
    evidence["changed_sources"] = changed
    if changed:
        print(f"FAIL: {len(changed)} validation inputs changed during execution", flush=True)
    failed = bool(changed or counts["FAIL"] or (args.strict and counts["SKIP"]))
    evidence.update(
        status="failed" if failed else "complete", counts=counts, completed_utc=datetime.now(UTC).isoformat()
    )
    save()
    return int(failed)
