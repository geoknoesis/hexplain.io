"""What the gates cost: the tracked record that drives scheduling, and a summary of one run.

``tools/gate-costs.json`` is tracked. It holds, per gate, the duration, the sampled peak resident
memory of the gate's process tree and the peak process count that a complete, unfiltered run
measured (``python tools/run_gates.py --strict --record-costs``). The runner reads it to order
gates longest-first and to estimate memory, on a developer's machine and in CI alike, so a fresh
checkout schedules from measurements rather than from a default; ``.gate-results/summary.json``
is local state and nothing tracked depends on it. A recording run replaces the entries of the
gates it ran and keeps every other declared gate's entry, so recording one class never erases
another, and a filtered run is refused.

Timeouts follow from the record mechanically (:func:`derive_timeout`):
``python tools/run_gates.py --derive-timeouts`` writes them into ``tools/gates.json`` and
``tools/test_gate_manifest.py`` asserts the rule for every gate.

Run as a script, this prints the few lines a reviewer reads about one run record and refuses to
summarise a run that did not finish.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The tracked cost record, relative to the repository root.
COSTS = "tools/gate-costs.json"
#: The gate manifest the derived timeouts are written into.
MANIFEST = "tools/gates.json"
MIB = 1024 * 1024
#: Timeout rule: this many times the recorded duration ...
TIMEOUT_FACTOR = 10
#: ... rounded up to a multiple of this many seconds, which is also the minimum ...
TIMEOUT_STEP = 300
#: ... and never more than this.
TIMEOUT_CAP = 3600

#: What the record says about itself; rewritten with every recording so the file explains itself.
DESCRIPTION = (
    "Measured cost of every gate, written by `python tools/run_gates.py --strict --record-costs` from a "
    "complete, unfiltered run and merged by gate (a recording never drops another class's entries). "
    "duration_s is wall clock; peak_rss_mb is the sampled peak resident memory of the gate's process tree "
    "(a lower bound); procs is the peak number of live processes in that tree. The runner schedules from "
    "this file and `--derive-timeouts` computes the tools/gates.json timeouts from it."
)


@dataclass(frozen=True)
class GateCost:
    """One gate's measured cost in the tracked record."""

    duration_s: float
    peak_rss_mb: float | None
    procs: int | None

    @property
    def peak_rss_bytes(self) -> int | None:
        return None if self.peak_rss_mb is None else int(self.peak_rss_mb * MIB)


def derive_timeout(duration_s: float | None) -> int:
    """Ten times the recorded duration, rounded up to five minutes; five minutes to an hour.

    A gate nobody has recorded gets the minimum: the rule has one input, and a hand-picked
    figure for an unmeasured gate is exactly what it replaces.
    """
    if duration_s is None:
        return TIMEOUT_STEP
    if not math.isfinite(duration_s) or duration_s < 0:
        raise ValueError(f"recorded duration must be a finite, non-negative number, not {duration_s!r}")
    stepped = math.ceil(duration_s * TIMEOUT_FACTOR / TIMEOUT_STEP) * TIMEOUT_STEP
    return int(min(TIMEOUT_CAP, max(TIMEOUT_STEP, stepped)))


def read_record(root: Path) -> dict[str, Any]:
    """The tracked record as stored, or an empty one when the tree has none."""
    path = root / COSTS
    if not path.is_file():
        return dict(schema_version=1, runs={}, gates={})
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported gate cost record")
    return document


def load_costs(root: Path) -> dict[str, GateCost]:
    """Recorded cost by gate name; a malformed entry is an error, not a silent default."""
    costs = {}
    for name, entry in read_record(root).get("gates", {}).items():
        try:
            rss, procs = entry.get("peak_rss_mb"), entry.get("procs")
            cost = GateCost(float(entry["duration_s"]), None if rss is None else float(rss), procs)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{root / COSTS}: gate {name} has a malformed cost entry: {error!r}") from error
        if cost.duration_s < 0 or (cost.peak_rss_mb is not None and cost.peak_rss_mb < 0):
            raise ValueError(f"{root / COSTS}: gate {name} records a negative cost")
        costs[name] = cost
    return costs


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")


def record_costs(root: Path, run: dict[str, Any], declared: set[str]) -> list[str]:
    """Merge a complete run record into the tracked record; returns the gates whose entry was written.

    ``run`` is a finished ``summary.json`` document, whose ``host`` block (the machine and how busy
    it was when the run began) is kept with the run's totals; ``declared`` is every gate of the
    manifest, whatever its class, and entries for gates no longer declared are dropped.
    """
    if run.get("status") != "complete":
        raise ValueError(f"only a complete run is recorded; this one is {run.get('status')!r}")
    document = read_record(root)
    gates: dict[str, Any] = {name: entry for name, entry in document.get("gates", {}).items() if name in declared}
    written = []
    for row in run["gates"]:
        rss = row.get("peak_rss_bytes")
        gates[row["gate"]] = dict(
            duration_s=round(float(row["duration_seconds"]), 1),
            peak_rss_mb=None if rss is None else round(rss / MIB, 1),
            procs=row.get("peak_processes"),
        )
        written.append(row["gate"])
    runs = dict(document.get("runs", {}))
    runs[run["gate_class"]] = dict(
        recorded_utc=run["completed_utc"],
        jobs=run["jobs"],
        gates=len(run["gates"]),
        wall_clock_s=round(float(run["wall_clock_seconds"]), 1),
        sequential_sum_s=round(sum(float(row["duration_seconds"]) for row in run["gates"]), 1),
        **run["host"],
    )
    _write_json(
        root / COSTS,
        dict(
            schema_version=1,
            description=DESCRIPTION,
            runs={name: runs[name] for name in sorted(runs)},
            gates={name: gates[name] for name in sorted(gates)},
        ),
    )
    return sorted(written)


def derive_timeouts(root: Path) -> list[str]:
    """Rewrite every timeout in tools/gates.json from the tracked record; returns the gates changed."""
    path = root / MANIFEST
    document = json.loads(path.read_text(encoding="utf-8"))
    costs = load_costs(root)
    changed = []
    for entry in document["gates"]:
        cost = costs.get(entry["name"])
        timeout = derive_timeout(None if cost is None else cost.duration_s)
        if entry.get("timeout") != timeout:
            entry["timeout"] = timeout
            changed.append(entry["name"])
    if changed:
        _write_json(path, document)
    return changed


def summarise(path: Path | str) -> dict[str, Any]:
    """The totals and orderings of one finished run record."""
    path = Path(path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"no gate report at {path}") from None
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"unreadable gate report at {path}: {error}") from error
    status = record.get("status")
    if status not in ("complete", "failed"):
        raise SystemExit(f"gate run is {status!r}; nothing to summarise until it finishes")
    gates = record.get("gates", [])
    sampled = [g for g in gates if g.get("peak_rss_bytes")]
    return dict(
        status=status,
        counts=record.get("counts"),
        gates=len(gates),
        jobs=record.get("jobs"),
        # Two different numbers: how long the run took, and how long its gates took added up.
        # With --jobs above one the sum exceeds the wall clock; calling the sum "wall clock"
        # (as this once did) hid exactly the speed-up the concurrency is there to give.
        wall_clock_seconds=record.get("wall_clock_seconds"),
        gate_seconds_sum=round(sum(g.get("duration_seconds", 0.0) for g in gates), 3),
        peak_rss_bytes=max((g["peak_rss_bytes"] for g in sampled), default=None),
        peak_processes=max((g.get("peak_processes") or 0 for g in sampled), default=None) or None,
        by_duration=sorted(gates, key=lambda g: -g.get("duration_seconds", 0.0)),
        by_memory=sorted(sampled, key=lambda g: -g["peak_rss_bytes"]),
    )


def render(summary: dict[str, Any], top: int = 10) -> str:
    """The summary as the lines a reviewer reads."""
    wall = summary["wall_clock_seconds"]
    lines = [
        f"{summary['gates']} gates, {summary['status']}, {summary['counts']}",
        ("wall clock not recorded" if wall is None else f"wall clock {wall:.1f}s at --jobs {summary['jobs']}"),
        f"sum of gate durations {summary['gate_seconds_sum']:.1f}s (what running them one after another takes)",
    ]
    if summary["peak_rss_bytes"] is None:
        lines.append("memory not sampled (psutil unavailable, or every gate exited between samples)")
    else:
        lines.append(
            f"peak sampled RSS {summary['peak_rss_bytes'] / MIB:,.1f} MiB across at most "
            f"{summary['peak_processes']} processes; a sampled lower bound, not an exact peak"
        )
    lines.append("slowest:")
    for row in summary["by_duration"][:top]:
        lines.append(f"  {row.get('duration_seconds', 0.0):8.1f}s  {row['gate']}")
    if summary["by_memory"]:
        lines.append("largest:")
        for row in summary["by_memory"][:top]:
            lines.append(
                f"  {row['peak_rss_bytes'] / MIB:8,.1f} MiB  {row['gate']} ({row.get('peak_processes')} processes)"
            )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: _gate_cost.py <.gate-results/summary.json>")
    print(render(summarise(argv[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
