"""Concurrent, bounded gate execution with explicit PASS/SKIP/FAIL outcomes.

Gates are independent scripts under tools/, declared in tools/gates.json. The runner schedules
them across worker threads, each launching one subprocess (tools/_gate_process.py), and bounds
the concurrency three ways (tools/_gate_schedule.py): ``--jobs`` (default: the smaller of the CPU
count and four), a process budget from each gate's effective process count, and a memory budget
against the peak RSS the tracked cost record (tools/gate-costs.json, tools/_gate_cost.py) holds
for the gate. Output is buffered per gate and flushed when the gate finishes, so interleaving
never garbles a report; with ``--jobs 1`` it streams live. The summary lists gates in name order
whatever the completion order.

A gate reports SKIP by exiting with status 77; any other non-zero status is a FAIL. Nothing is
inferred from a gate's stdout.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import platform
import sys
import threading
import time
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _gate_cost import COSTS, TIMEOUT_CAP, GateCost, derive_timeouts, load_costs, record_costs
from _gate_process import run_gate
from _gate_schedule import Gate, MemoryBudget, Scheduler, effective_procs

try:
    import psutil
except ImportError:
    psutil = None

#: Interpreter floor; pyproject.toml states the same bound for installers.
PYTHON_FLOOR = (3, 11)
#: Gate classes a manifest may declare and what runs them.
GATE_CLASSES = ("offline", "docker", "browser")
#: Environment variable through which the runner hands gates the source manifest digest.
MANIFEST_ENV = "HEXPLAIN_SOURCE_MANIFEST_SHA256"
#: Environment variable bounding the worker processes of a parallel gate.
WORKERS_ENV = "HEXPLAIN_GATE_WORKERS"
#: The most worker processes a gate fans out to, whoever asks.
WORKER_CAP = 8
#: How often the run record's atomic replace is tried before a PermissionError is let through.
REPLACE_ATTEMPTS = 20


def requested_workers() -> int | None:
    """``HEXPLAIN_GATE_WORKERS`` as a positive integer, None when unset; anything else is an error."""
    requested = os.environ.get(WORKERS_ENV)
    if not requested:
        return None
    try:
        count = int(requested)
    except ValueError:
        raise ValueError(f"{WORKERS_ENV} must be an integer, not {requested!r}") from None
    if count < 1:
        raise ValueError(f"{WORKERS_ENV} must be at least 1")
    return count


def gate_workers(default_cap: int = WORKER_CAP) -> int:
    """Worker-process count for a gate that fans out: ``HEXPLAIN_GATE_WORKERS``, bounded by ``default_cap``.

    Bounded whichever way the count arrives, because an earlier concurrent run exhausted host
    memory: the cap is a property of the gate, and an environment variable that lifted it would
    reopen that failure. The runner sets the variable per gate, to the gate's effective process
    count, so that concurrently scheduled gates do not multiply.
    """
    requested = requested_workers()
    count = requested if requested is not None else (os.cpu_count() or 1)
    return max(1, min(count, default_cap))


# Editor, coverage and staged-write droppings change under a run without being validation inputs.
TRANSIENT = (".coverage", ".coverage.*", "*.swp", "*.swo", "*~", ".#*", ".report-*.tmp", ".DS_Store")


def transient(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in TRANSIENT)


def source_manifest(root: Path, excluded: set[Path] | None = None) -> dict[str, str]:
    """Byte hashes for declared local validation inputs; no external-file traversal."""
    # Published documents are validation inputs too: link, governance and page-equality
    # gates read them, so a document changed during a run must invalidate acceptance the
    # same way a changed shape or script does.
    # Scan source directories in full: binary vectors and archives are validation inputs too.
    # Local caches/results and the rebuilt candidate ZIP are outputs, not source inputs.
    paths: list[Path] = []
    ignored = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    for directory in ("tools", "specification", "authoring", "deployment", ".github", "assets", "releases"):
        base = root / directory
        if base.exists():
            paths.extend(
                p
                for p in base.rglob("*")
                if p.is_file()
                and not ignored.intersection(p.relative_to(root).parts)
                and not transient(p.name)
                and p.relative_to(root).as_posix() != "specification/ontology-review/ontology-review-candidate.zip"
            )
    paths.extend(p for p in root.iterdir() if p.is_file() and not transient(p.name))
    result = {}
    excluded_paths = {p.resolve() for p in excluded or set()}
    for path in sorted(set(paths)):
        if path.resolve() in excluded_paths:
            continue
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Validation input escapes repository: {path}")
        try:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        except FileNotFoundError:
            continue  # Removed after the scan listed it; the comparison records it as changed.
        result[path.relative_to(root).as_posix()] = digest
    return result


def manifest_digest(manifest: dict[str, str]) -> str:
    """One digest over a source manifest, the key under which gates may cache derived inputs."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()


def load_gate_manifest(root: Path) -> dict[str, Gate] | None:
    """The declared gates of tools/gates.json by name, or None when a tree declares none.

    Without a manifest the runner discovers ``tools/*.py`` (test fixtures use that); with one,
    every discovered ``test_*.py`` must be declared, or the run fails closed.
    """
    path = root / "tools/gates.json"
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path}: gate manifest must be an object")
    if document.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported gate manifest schema {document.get('schema_version')!r}")
    entries = document.get("gates")
    if not isinstance(entries, list):
        raise ValueError(f"{path}: gates must be an array of objects")
    gates: dict[str, Gate] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: each gate must be an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{path}: each gate needs a nonempty string name")
        if name in gates:
            raise ValueError(f"{path}: gate {name} is declared twice")
        if entry.get("class", "offline") not in GATE_CLASSES:
            raise ValueError(f"{path}: gate {name} has unknown class {entry.get('class')!r}")
        timeout = entry.get("timeout")
        if isinstance(timeout, bool) or not isinstance(timeout, int | float) or not 0 < timeout <= sys.float_info.max:
            raise ValueError(f"{path}: gate {name} needs a positive finite timeout representable as a float")
        if type(entry.get("procs", 1)) is not int or entry.get("procs", 1) < 1:
            raise ValueError(f"{path}: gate {name} needs a positive procs count")
        gates[name] = dict(entry)
    return gates


def _select_gates(
    root: Path,
    excluded: set[str],
    manifest: dict[str, Gate] | None,
    gate_class: str,
    filters: list[str],
    default_timeout: float,
) -> list[Gate]:
    tools = root / "tools"
    gates: list[Gate]
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


def _parser() -> argparse.ArgumentParser:
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
    parser.add_argument(
        "--record-costs",
        action="store_true",
        help=f"After a complete, unfiltered run, merge its durations and peak memory into the tracked {COSTS}",
    )
    parser.add_argument(
        "--derive-timeouts",
        action="store_true",
        help=f"Rewrite the tools/gates.json timeouts from {COSTS} (10x the recorded duration, rounded up to "
        "5 minutes, at least 5 minutes, at most an hour) and exit without running a gate",
    )
    return parser


def _check_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Refuse an unusable command line; returns the job count."""
    if sys.version_info < PYTHON_FLOOR:
        parser.error(
            f"Python {'.'.join(map(str, PYTHON_FLOOR))} or newer is required; running {platform.python_version()}"
        )
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error("--timeout must be positive")
    jobs: int = args.jobs if args.jobs is not None else max(1, min(os.cpu_count() or 1, 4))
    if jobs < 1:
        parser.error("--jobs must be at least 1")
    if args.strict and os.environ.get("HEXPLAIN_ROUNDTRIP_SKIP_ON_BUILD_ERROR") == "1":
        parser.error("strict mode forbids HEXPLAIN_ROUNDTRIP_SKIP_ON_BUILD_ERROR")
    if args.record_costs and (args.filters or args.timeout is not None):
        # A filtered run measures some gates beside fewer neighbours, and a clamped timeout can
        # cut one short: neither is the cost of the suite, so neither may overwrite the record.
        parser.error("--record-costs needs a complete run: no gate filters and no --timeout override")
    return jobs


def _plan(
    root: Path, excluded: set[str], args: argparse.Namespace, jobs: int, costs: Mapping[str, GateCost]
) -> list[Gate]:
    """The gates this run executes, each with its timeout and effective process count."""
    manifest = load_gate_manifest(root)
    gates = _select_gates(root, excluded, manifest, args.gate_class, args.filters, args.timeout or TIMEOUT_CAP)
    if not gates:
        raise ValueError("no gates matched")
    cpu, requested = os.cpu_count() or 1, requested_workers()
    for gate in gates:
        if args.timeout is not None:
            gate["timeout"] = min(float(gate["timeout"]), args.timeout)
        elif args.record_costs and gate["name"] not in costs:
            # A gate nobody has recorded has the minimum timeout, which is a guess about a gate
            # whose cost is exactly what this run is there to find out: while recording, it gets
            # the cap, or a gate that takes six minutes could never be recorded at all.
            gate["timeout"] = TIMEOUT_CAP
        gate["effective_procs"] = effective_procs(min(gate.get("procs", 1), WORKER_CAP), cpu, jobs, requested)
    return gates


class _Run:
    """One run's record: started before any gate, rewritten after each, closed with the verdict."""

    def __init__(self, root: Path, destination: Path, args: argparse.Namespace, jobs: int, gates: list[Gate]) -> None:
        self.root = root
        self.destination = destination
        self.strict: bool = args.strict
        self.outputs = {destination, destination.with_suffix(destination.suffix + ".tmp")}
        self.sources = source_manifest(root, self.outputs)
        self.records: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.evidence: dict[str, Any] = dict(
            schema_version=5,
            strict=args.strict,
            status="running",
            started_utc=datetime.now(UTC).isoformat(),
            python=sys.version,
            platform=platform.platform(),
            host=_host(),
            jobs=jobs,
            gate_class=args.gate_class,
            source_sha256=self.sources,
            source_manifest_sha256=manifest_digest(self.sources),
            selected_gates=[g["name"] for g in gates],
            gate_sha256={g["name"]: hashlib.sha256(g["path"].read_bytes()).hexdigest() for g in gates},
            gates=[],
        )

    def save(self) -> None:
        with self.lock:
            self.evidence["gates"] = [self.records[name] for name in sorted(self.records)]
            temporary = self.destination.with_suffix(self.destination.suffix + ".tmp")
            temporary.write_text(json.dumps(self.evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
            # On Windows a scanner or indexer that has the record open makes the replace fail with
            # PermissionError for a moment; the record is rewritten after every gate, so a short retry
            # is all it takes, and the last attempt raises like the first would have.
            for attempt in range(REPLACE_ATTEMPTS):
                try:
                    temporary.replace(self.destination)
                    break
                except PermissionError:
                    if attempt == REPLACE_ATTEMPTS - 1:
                        raise
                    time.sleep(0.05 * (attempt + 1))

    def launch(self, gate: Gate, stream: bool, scheduler: Scheduler) -> dict[str, Any]:
        """Run one gate (on a worker thread) and return its row."""
        name = gate["name"]
        env = {MANIFEST_ENV: self.evidence["source_manifest_sha256"], WORKERS_ENV: str(gate["effective_procs"])}
        row = dict(
            gate=name,
            procs=gate["effective_procs"],
            timeout_seconds=float(gate["timeout"]),
            **run_gate(
                [sys.executable, "-u", str(gate["path"])],
                self.root,
                float(gate["timeout"]),
                stream=stream,
                env=env,
                publish=lambda held: scheduler.held.__setitem__(name, held),
            ),
        )
        if hashlib.sha256(gate["path"].read_bytes()).hexdigest() != self.evidence["gate_sha256"][name]:
            row.update(status="FAIL", source_changed=True)
        return row

    def execute(self, scheduler: Scheduler, jobs: int) -> None:
        """Run every pending gate, printing each one's buffered output as it finishes."""
        stream = jobs == 1
        heartbeat_at = time.monotonic() + 15
        launched_at: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            while scheduler.pending or scheduler.running:
                while (gate := scheduler.next_ready()) is not None:
                    print(f"RUN {gate['name']}", flush=True)
                    launched_at[gate["name"]] = time.monotonic()
                    scheduler.started(pool.submit(self.launch, gate, stream, scheduler), gate)
                done, _ = wait(list(scheduler.running), timeout=1, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda f: scheduler.running[f]["name"]):
                    gate = scheduler.finished(future)
                    started = launched_at.pop(gate["name"])
                    try:
                        row = future.result()
                    except Exception as error:  # noqa: BLE001 -- one worker failure must not discard the run
                        row = dict(
                            gate=gate["name"],
                            procs=gate["effective_procs"],
                            timeout_seconds=float(gate["timeout"]),
                            status="FAIL",
                            exit_code=None,
                            timed_out=False,
                            output_limit_exceeded=False,
                            duration_seconds=round(time.monotonic() - started, 3),
                            peak_rss_bytes=None,
                            peak_processes=None,
                            rss_samples=0,
                            memory_note="worker failed; memory measurements unavailable",
                            worker_error=type(error).__name__,
                            output=f"Gate worker failed ({type(error).__name__}): {str(error)[:2000]}\n",
                        )
                    self.records[row["gate"]] = row
                    if row["output"] and (not stream or row.get("worker_error")):
                        print(row["output"], end="" if row["output"].endswith("\n") else "\n", flush=True)
                    print(f"{row['status']} {row['gate']} ({row['duration_seconds']:.1f}s)", flush=True)
                    self.save()
                if not stream and scheduler.running and time.monotonic() >= heartbeat_at:
                    names = ", ".join(sorted(g["name"] for g in scheduler.running.values()))
                    print(f"  RUNNING {names}", flush=True)
                    heartbeat_at = time.monotonic() + 15

    def close(self) -> bool:
        """Count the outcomes, recheck the inputs and write the verdict; True when the run failed."""
        rows = [self.records[name] for name in sorted(self.records)]
        counts = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "SKIP", "FAIL")}
        print(f"{counts['PASS']} passed, {counts['SKIP']} skipped, {counts['FAIL']} failed", flush=True)
        final_sources = source_manifest(self.root, self.outputs)
        changed = sorted(
            path
            for path in self.sources.keys() | final_sources.keys()
            if self.sources.get(path) != final_sources.get(path)
        )
        self.evidence["changed_sources"] = changed
        if changed:
            print(f"FAIL: {len(changed)} validation inputs changed during execution", flush=True)
        failed = bool(changed or counts["FAIL"] or (self.strict and counts["SKIP"]))
        self.evidence.update(
            status="failed" if failed else "complete",
            counts=counts,
            completed_utc=datetime.now(UTC).isoformat(),
            wall_clock_seconds=round(time.monotonic() - self.started, 3),
        )
        self.save()
        return failed


def _host() -> dict[str, Any]:
    """The machine a run is measured on, and how busy it already is before the first gate starts.

    A duration means little without the second part: the same suite takes several times as long
    on a host whose processors other work is already using, so the record says what it found.
    """
    host: dict[str, Any] = dict(
        platform=platform.platform(),
        python=platform.python_version(),
        cpu_count=os.cpu_count(),
        memory_mb=None,
        available_mb_at_start=None,
        cpu_busy_percent_at_start=None,
    )
    if psutil is not None:
        memory = psutil.virtual_memory()
        host.update(
            memory_mb=round(memory.total / (1024 * 1024)),
            available_mb_at_start=round(memory.available / (1024 * 1024)),
            cpu_busy_percent_at_start=psutil.cpu_percent(interval=0.5),
        )
    return host


def _record(root: Path, run: _Run) -> None:
    """Merge a finished run into the tracked cost record, or say why it was not."""
    if run.evidence["status"] != "complete":
        print(f"NOT RECORDED: {COSTS} takes a complete run only, and this one failed", flush=True)
        return
    manifest = load_gate_manifest(root) or {}
    written = record_costs(root, run.evidence, set(manifest) or set(run.records))
    print(f"RECORDED: the cost of {len(written)} gates in {COSTS}; now run --derive-timeouts", flush=True)


def main(root: Path, excluded: set[str], argv: list[str] | None = None) -> int:
    """Run the selected gates and write ``.gate-results/summary.json``; 0 when acceptance holds."""
    parser = _parser()
    args = parser.parse_args(argv)
    jobs = _check_arguments(parser, args)
    if args.derive_timeouts:
        changed = derive_timeouts(root)
        print(
            f"tools/gates.json: {len(changed)} timeouts rewritten from {COSTS}" + "".join(f"\n  {n}" for n in changed)
        )
        return 0
    try:
        costs = load_costs(root)
        gates = _plan(root, excluded, args, jobs, costs)
        memory = MemoryBudget.from_environment()
    except ValueError as error:
        parser.error(str(error))
    destination = root / args.json
    destination.parent.mkdir(parents=True, exist_ok=True)
    run = _Run(root, destination, args, jobs, gates)
    run.evidence["memory_budget"] = memory.describe()
    run.save()  # Replace stale results before starting any gate.
    run.execute(Scheduler(gates, jobs, costs, memory, max(os.cpu_count() or 1, jobs)), jobs)
    failed = run.close()
    if args.record_costs:
        # After the inputs were rechecked: the record is itself a tracked input of the next run.
        _record(root, run)
    return int(failed)
