"""Run one gate as a bounded subprocess: timeout, output limit, sampled memory, explicit outcome.

A gate reports SKIP by exiting with status 77 (``SKIP_EXIT``); any other non-zero status is a
FAIL. Nothing is inferred from a gate's stdout.
"""

from __future__ import annotations

import contextlib
import math
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # Recorded as "not sampled" rather than failing a gate run.
    psutil = None

#: Exit status by which a gate reports that it did not run (optional dependency absent, ...).
SKIP_EXIT = 77
#: Seconds the tree kill and each wait for the gate's end may take.
KILL_TIMEOUT = 10

#: A gate's record: JSON-shaped, written verbatim into the run record.
Record = dict[str, Any]


def _unsampled(note: str) -> Record:
    return dict(peak_rss_bytes=None, peak_processes=None, rss_samples=0, memory_note=note)


def _tree_rss(parent: Any) -> tuple[int, int]:
    """Resident bytes and live process count of ``parent`` and its descendants, now."""
    total, live = 0, 0
    for process in [parent, *parent.children(recursive=True)]:
        try:
            total += process.memory_info().rss
            live += 1
        except psutil.Error:
            continue
    return total, live


def sample_memory(
    pid: int,
    stopped: threading.Event,
    interval: float = 0.05,
    publish: Callable[[int], None] | None = None,
) -> Record:
    """Peak resident bytes of a gate and its descendants, and the peak process count.

    The parallel gates fan out into worker processes, and it was a concurrent run exhausting host
    memory that forced the worker cap -- so the number that matters is the whole tree's, not the
    parent's. Sampling is a lower bound on the true peak: a spike between samples is missed, and a
    process that exits between samples is never seen at all. ``publish`` receives every sample,
    which is how the scheduler learns what a running gate holds at the moment.
    """
    if psutil is None:
        return _unsampled("psutil is not installed; gate memory was not sampled")
    try:
        parent = psutil.Process(pid)
    except psutil.Error:
        return _unsampled("gate process exited before sampling began")
    peak, processes, samples = 0, 0, 0
    while not stopped.is_set():
        try:
            total, live = _tree_rss(parent)
        except psutil.Error:
            break
        if live:
            samples += 1
            peak = max(peak, total)
            processes = max(processes, live)
            if publish is not None:
                publish(total)
        stopped.wait(interval)
    return dict(
        peak_rss_bytes=peak,
        peak_processes=processes,
        rss_samples=samples,
        memory_note="sampled sum of the gate and its descendants; a lower bound, not an exact peak",
    )


def kill_tree_windows(proc: subprocess.Popen[str], run: Callable[..., Any] = subprocess.run) -> None:
    """Kill a gate and its descendants with taskkill, bounded; fall back to the gate alone.

    taskkill is itself a process that can hang or be missing. Its timeout used to propagate out
    of the runner and abort the whole run on the one path that exists to contain a stuck gate;
    now a failed tree kill degrades to killing the gate's own process, and the caller's bounded
    wait reports whatever survives.
    """
    try:
        run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=KILL_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError):
        with contextlib.suppress(OSError):
            proc.kill()


def terminate(proc: subprocess.Popen[str]) -> None:
    """Kill the gate's whole process tree."""
    if sys.platform == "win32":
        kill_tree_windows(proc)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)


class _Reader:
    """Reads a gate's output on a thread into a bounded queue, so a timeout can interrupt the wait."""

    def __init__(self, proc: subprocess.Popen[str]) -> None:
        assert proc.stdout is not None
        self.stream = proc.stdout
        self.chunks: queue.Queue[str | None] = queue.Queue(maxsize=16)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _enqueue(self, value: str | None) -> None:
        while not self.stopped.is_set():
            try:
                self.chunks.put(value, timeout=0.1)
                return
            except queue.Full:
                pass

    def _read(self) -> None:
        try:
            while not self.stopped.is_set():
                chunk = self.stream.read(4096)
                if not chunk:
                    break
                self._enqueue(chunk)
        finally:
            self._enqueue(None)

    def close(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=1)
        if not self.thread.is_alive():
            self.stream.close()


def _collect(
    proc: subprocess.Popen[str],
    reader: _Reader,
    label: str,
    started: float,
    timeout: float,
    heartbeat: float,
    max_output_chars: int,
    stream: bool,
) -> tuple[str, bool, bool]:
    """Retain the gate's output until it ends, times out or floods: (text, timed out, flooded)."""
    lines: list[str] = []
    retained, next_heartbeat = 0, started + heartbeat
    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            terminate(proc)
            return "".join(lines), True, False
        try:
            chunk = reader.chunks.get(timeout=min(1, max(0.01, timeout - elapsed)))
        except queue.Empty:
            chunk = ""
        if chunk is None:
            return "".join(lines), False, False
        if chunk:
            available = max_output_chars - retained
            kept = chunk[:available]
            lines.append(kept)
            retained += len(kept)
            if stream:
                print(kept, end="", flush=True)
            if len(chunk) > available:
                terminate(proc)
                return "".join(lines), False, True
        if stream and time.monotonic() >= next_heartbeat:
            print(f"  RUNNING {label}: {elapsed:.0f}s", flush=True)
            next_heartbeat = time.monotonic() + heartbeat


def _reap(proc: subprocess.Popen[str]) -> None:
    """Wait for the gate's end, bounded; kill the tree once more if it ignored the first."""
    try:
        proc.wait(timeout=KILL_TIMEOUT)
    except subprocess.TimeoutExpired:
        # The gate ignored its end (a timed-out gate that survived the kill, or a gate whose
        # pipe closed before it exited): kill the tree and wait once more, bounded.
        terminate(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=KILL_TIMEOUT)


def _status(returncode: int | None, expired: bool, flooded: bool) -> str:
    if expired or flooded or returncode is None or (returncode and returncode != SKIP_EXIT):
        return "FAIL"
    return "SKIP" if returncode == SKIP_EXIT else "PASS"


def run_gate(
    command: list[str],
    cwd: Path,
    timeout: float,
    heartbeat: float = 15,
    max_output_chars: int = 1_000_000,
    stream: bool = True,
    env: dict[str, str] | None = None,
    publish: Callable[[int], None] | None = None,
) -> Record:
    """Run one gate to completion, bounded by ``timeout`` seconds and ``max_output_chars`` of output.

    With ``stream`` the gate's output is echoed as it arrives; otherwise it is only retained in the
    returned record, for a caller that prints it once the gate is done. ``publish`` receives each
    memory sample of the gate's process tree while it runs.
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
        start_new_session=(sys.platform != "win32"),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    sampled: Record = {}
    sampling_stopped = threading.Event()
    sampler = threading.Thread(
        target=lambda: sampled.update(sample_memory(proc.pid, sampling_stopped, publish=publish)), daemon=True
    )
    sampler.start()
    reader = _Reader(proc)
    label = Path(command[-1]).name
    text, expired, flooded = _collect(proc, reader, label, started, timeout, heartbeat, max_output_chars, stream)
    reader.stopped.set()
    _reap(proc)
    sampling_stopped.set()
    sampler.join(timeout=5)
    reader.close()
    return dict(
        status=_status(proc.returncode, expired, flooded),
        exit_code=proc.returncode,
        timed_out=expired,
        output_limit_exceeded=flooded,
        duration_seconds=round(time.monotonic() - started, 3),
        **sampled,
        output=text,
    )
