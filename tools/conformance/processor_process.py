"""Bound processor output and execution while keeping stderr diagnostics separate from stdout."""

from __future__ import annotations

import math
import queue
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _gate_process import _Reader, _reap, terminate  # noqa: E402

MAX_OUTPUT_CHARS = 1_000_000
EXIT_GRACE = 2.0  # Seconds to drain pipes after the process exits; a descendant may hold them open indefinitely.


def cleanup(
    proc: subprocess.Popen[str], readers: list[_Reader], closed: set[int], close_job: Callable[[], None] | None
) -> None:
    """Reap the process and close every pipe, including partially initialized readers."""
    try:
        if close_job is not None:
            close_job()
    finally:
        try:
            if len(closed) < 2 or proc.poll() is None:
                terminate(proc)  # Descendants may still hold a reader's pipe open.
        finally:
            for reader in readers:
                reader.stopped.set()
            try:
                _reap(proc)
            finally:
                for reader in readers:
                    reader.close()
                for pipe in (proc.stdout, proc.stderr):
                    if pipe is not None and not any(reader.stream is pipe for reader in readers):
                        pipe.close()


def collect(
    proc: subprocess.Popen[str], timeout: float, close_job: Callable[[], None] | None = None
) -> tuple[str, str | None]:
    """Drain both pipes with bounded queues and an aggregate output budget."""
    readers: list[_Reader] = []
    closed: set[int] = set()
    diagnostics: list[str] = []
    retained = 0
    deadline = time.monotonic() + timeout
    exited: float | None = None
    try:
        assert proc.stderr is not None
        readers.append(_Reader(proc))
        readers.append(_Reader(proc, proc.stderr))
        while len(closed) < 2 or proc.poll() is None:
            now = time.monotonic()
            if exited is None and proc.poll() is not None:
                exited = now
            if exited is not None and now - exited >= EXIT_GRACE:
                break  # Cleanup terminates the descendants still holding a pipe.
            if now >= deadline:
                return "", f"timed out after {timeout}s"
            for index, reader in enumerate(readers):
                if index in closed:
                    continue
                try:
                    chunk = reader.chunks.get_nowait()
                except queue.Empty:
                    continue
                if chunk is None:
                    closed.add(index)
                else:
                    retained += len(chunk)
                    if retained > MAX_OUTPUT_CHARS:
                        return "", f"command output exceeded {MAX_OUTPUT_CHARS} characters"
                    if index == 1:
                        diagnostics.append(chunk)
            time.sleep(0.005)
        return "".join(diagnostics), None
    finally:
        cleanup(proc, readers, closed, close_job)


def execute(command: list[str], cwd: Path, timeout: float) -> tuple[int, str, str | None]:
    """Return exit code, stderr and containment failure; launch errors are handled by the caller."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    if sys.platform == "win32":
        from windows_job import Job, launch

        job = Job()
        try:
            proc = launch(command, cwd, job)
            stderr, failure = collect(proc, timeout, job.close)
        finally:
            job.close()
    else:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stderr, failure = collect(proc, timeout)
    return proc.returncode if proc.returncode is not None else -1, stderr, failure
