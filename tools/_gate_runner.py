"""Streaming, bounded gate execution with explicit PASS/SKIP/FAIL outcomes."""
import argparse
import json
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time


def run_gate(command, cwd, timeout, heartbeat=15):
    started = time.monotonic()
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1")
    env.pop("PYTHONOPTIMIZE", None)
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=(os.name != "nt"), text=True, encoding="utf-8", errors="replace")
    output = queue.Queue()
    def read():
        for line in proc.stdout:
            output.put(line)
        output.put(None)
    threading.Thread(target=read, daemon=True).start()
    lines, expired, next_heartbeat = [], False, started + heartbeat
    while True:
        elapsed = time.monotonic() - started
        if elapsed > timeout:
            expired = True
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            else:
                os.killpg(proc.pid, signal.SIGKILL)
            break
        try:
            line = output.get(timeout=min(1, max(0.01, timeout - elapsed)))
        except queue.Empty:
            line = ""
        if line is None:
            break
        if line:
            lines.append(line)
            print(line, end="", flush=True)
        if time.monotonic() >= next_heartbeat:
            print(f"  RUNNING {Path(command[-1]).name}: {elapsed:.0f}s", flush=True)
            next_heartbeat = time.monotonic() + heartbeat
    proc.wait(timeout=10)
    text = "".join(lines)
    status = "FAIL" if expired or proc.returncode else "SKIP" if re.search(r"(?m)^\s*SKIP\b", text) else "PASS"
    return dict(status=status, exit_code=proc.returncode, timed_out=expired,
                duration_seconds=round(time.monotonic()-started, 3), output=text)


def main(root, excluded, argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filters", nargs="*")
    parser.add_argument("--strict", action="store_true", help="A skipped required check fails acceptance")
    parser.add_argument("--timeout", type=float, default=3600, help="Maximum seconds per gate")
    parser.add_argument("--json", default=".gate-results/summary.json")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
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
    for gate in gates:
        print(f"RUN {gate.stem}", flush=True)
        row = dict(gate=gate.stem, **run_gate([sys.executable, "-u", str(gate)], root, args.timeout))
        records.append(row)
        print(f"{row['status']} {gate.stem} ({row['duration_seconds']:.1f}s)", flush=True)
        destination.write_text(json.dumps(dict(schema_version=1, strict=args.strict, gates=records), indent=2)+"\n", encoding="utf-8")
    counts = {s: sum(r["status"] == s for r in records) for s in ("PASS", "SKIP", "FAIL")}
    print(f"{counts['PASS']} passed, {counts['SKIP']} skipped, {counts['FAIL']} failed", flush=True)
    return int(bool(counts["FAIL"] or (args.strict and counts["SKIP"])))
