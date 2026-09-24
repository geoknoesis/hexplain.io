"""Streaming, bounded gate execution with explicit PASS/SKIP/FAIL outcomes."""
import argparse
import math
import json
import hashlib
import platform
from datetime import datetime, timezone
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time

try:
    import psutil
except ImportError:  # Recorded as "not sampled" rather than failing a gate run.
    psutil = None


def _sample_memory(pid, stopped, interval=0.05):
    """Peak resident bytes of a gate and its descendants, and the peak process count.

    The parallel gates fan out into worker processes, and it was a concurrent run exhausting host
    memory that forced the worker cap -- so the number that matters is the whole tree's, not the
    parent's. Sampling is a lower bound on the true peak: a spike between samples is missed, and a
    process that exits between samples is never seen at all.
    """
    peak, processes, samples = 0, 0, 0
    if psutil is None:
        return dict(peak_rss_bytes=None, peak_processes=None, rss_samples=0,
                    memory_note="psutil is not installed; gate memory was not sampled")
    try:
        parent = psutil.Process(pid)
    except psutil.Error:
        return dict(peak_rss_bytes=None, peak_processes=None, rss_samples=0,
                    memory_note="gate process exited before sampling began")
    while not stopped.is_set():
        total, live = 0, 0
        try:
            for process in [parent] + parent.children(recursive=True):
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
    return dict(peak_rss_bytes=peak, peak_processes=processes, rss_samples=samples,
                memory_note="sampled sum of the gate and its descendants; a lower bound, not an exact peak")


def run_gate(command, cwd, timeout, heartbeat=15, max_output_chars=1_000_000):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    if max_output_chars < 1:
        raise ValueError("output limit must be positive")
    started = time.monotonic()
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    env.pop("PYTHONOPTIMIZE", None)
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=(os.name != "nt"), text=True, encoding="utf-8", errors="replace")
    output = queue.Queue(maxsize=16)
    stopped = threading.Event()
    sampled = {}
    sampling_stopped = threading.Event()
    sampler = threading.Thread(target=lambda: sampled.update(_sample_memory(proc.pid, sampling_stopped)), daemon=True)
    sampler.start()
    def enqueue(value):
        while not stopped.is_set():
            try:
                output.put(value, timeout=0.1)
                return
            except queue.Full:
                pass
    def read():
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
    def terminate():
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    lines, expired, next_heartbeat = [], False, started + heartbeat
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
            print(kept, end="", flush=True)
            if len(line) > available:
                output_exceeded = True
                terminate()
                break
        if time.monotonic() >= next_heartbeat:
            print(f"  RUNNING {Path(command[-1]).name}: {elapsed:.0f}s", flush=True)
            next_heartbeat = time.monotonic() + heartbeat
    stopped.set()
    proc.wait(timeout=10)
    sampling_stopped.set()
    sampler.join(timeout=5)
    reader.join(timeout=1)
    if not reader.is_alive():
        proc.stdout.close()
    text = "".join(lines)
    status = "FAIL" if expired or output_exceeded or proc.returncode else "SKIP" if re.search(r"(?m)^\s*SKIP\b", text) else "PASS"
    return dict(status=status, exit_code=proc.returncode, timed_out=expired, output_limit_exceeded=output_exceeded,
                duration_seconds=round(time.monotonic()-started, 3), **sampled, output=text)


def source_manifest(root):
    """Byte hashes for declared local validation inputs; no external-file traversal."""
    # Published documents are validation inputs too: link, governance and page-equality
    # gates read them, so a document changed during a run must invalidate acceptance the
    # same way a changed shape or script does.
    suffixes = {".py", ".ttl", ".json", ".tsv", ".in", ".txt", ".html", ".css", ".md"}
    paths = []
    for directory in ("tools", "specification", "authoring"):
        base = root / directory
        if base.exists():
            paths.extend(p for p in base.rglob("*") if p.is_file()
                         and p.suffix in suffixes and "__pycache__" not in p.parts)
    # Published root artifacts that gates read but no scanned directory contains.
    paths.extend(p for p in (root / "requirements.txt", root / "pyproject.toml",
                             root / "index.html", root / "robots.txt", root / "sitemap.xml") if p.exists())
    result = {}
    for path in sorted(set(paths)):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Validation input escapes repository: {path}")
        with path.open("rb") as stream:
            result[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def main(root, excluded, argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filters", nargs="*")
    parser.add_argument("--strict", action="store_true", help="A skipped required check fails acceptance")
    parser.add_argument("--timeout", type=float, default=3600, help="Maximum seconds per gate")
    parser.add_argument("--json", default=".gate-results/summary.json")
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.strict and os.environ.get("HEXPLAIN_ROUNDTRIP_SKIP_ON_BUILD_ERROR") == "1":
        parser.error("strict mode forbids HEXPLAIN_ROUNDTRIP_SKIP_ON_BUILD_ERROR")
    gates = sorted(p for p in (root/"tools").glob("*.py") if p.stem not in excluded and not p.stem.startswith("_"))
    gates = [p for p in gates if not args.filters or any(f in p.name for f in args.filters)]
    if not gates:
        parser.error("no gates matched")
    records = []
    destination = root / args.json
    destination.parent.mkdir(parents=True, exist_ok=True)
    evidence = dict(schema_version=3, strict=args.strict, status="running",
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    python=sys.version, platform=platform.platform(),
                    source_sha256=source_manifest(root),
                    selected_gates=[p.stem for p in gates],
                    gate_sha256={p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in gates},
                    gates=records)
    def save():
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8", newline="\n")
        temporary.replace(destination)
    save()  # Replace stale results before starting any gate.
    for gate in gates:
        print(f"RUN {gate.stem}", flush=True)
        row = dict(gate=gate.stem, **run_gate([sys.executable, "-u", str(gate)], root, args.timeout))
        if hashlib.sha256(gate.read_bytes()).hexdigest() != evidence["gate_sha256"][gate.stem]:
            row.update(status="FAIL", source_changed=True)
        records.append(row)
        print(f"{row['status']} {gate.stem} ({row['duration_seconds']:.1f}s)", flush=True)
        save()
    counts = {s: sum(r["status"] == s for r in records) for s in ("PASS", "SKIP", "FAIL")}
    print(f"{counts['PASS']} passed, {counts['SKIP']} skipped, {counts['FAIL']} failed", flush=True)
    final_sources = source_manifest(root)
    original_sources = evidence["source_sha256"]
    changed = sorted(path for path in original_sources.keys() | final_sources.keys()
                     if original_sources.get(path) != final_sources.get(path))
    evidence["changed_sources"] = changed
    if changed:
        print(f"FAIL: {len(changed)} validation inputs changed during execution", flush=True)
    failed = bool(changed or counts["FAIL"] or (args.strict and counts["SKIP"]))
    evidence.update(status="failed" if failed else "complete", counts=counts,
                    completed_utc=datetime.now(timezone.utc).isoformat())
    save()
    return int(failed)
