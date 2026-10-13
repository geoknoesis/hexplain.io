"""Which gate may start next: the job, process and memory bounds of a concurrent run.

Three bounds apply together. ``jobs`` gates at most run side by side. Each gate claims its
*effective* process count -- what it declares in tools/gates.json, capped by its share of the
machine (:func:`effective_procs`) -- and the claims of the running gates stay within the process
budget; the same number is handed to the gate as ``HEXPLAIN_GATE_WORKERS``, so the budget counts
the processes the gate will really start. And each gate claims the peak resident memory the
tracked cost record (tools/gate-costs.json) measured for it, a conservative default when it has
none, within a memory budget.

The memory budget is either fixed (a constructor argument, or ``HEXPLAIN_GATE_MEMORY_MB`` for a
whole run, which is what makes a scheduling test deterministic on any host) or read from the
host every time a gate is considered: what is free now must cover the candidate's estimate plus
whatever the running gates have yet to claim of theirs.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from typing import Any

from _gate_cost import MIB, GateCost

try:
    import psutil
except ImportError:
    psutil = None

#: Memory estimate for a gate the cost record does not hold (bytes).
DEFAULT_GATE_RSS = 512 * MIB
#: Environment variable fixing the memory budget of a run, in MiB.
MEMORY_ENV = "HEXPLAIN_GATE_MEMORY_MB"
#: Share of the host's free memory the gates may claim when the budget is read from the host.
HOST_SHARE = 0.8

#: A gate as the runner selected it: the manifest entry plus its path and effective process count.
Gate = dict[str, Any]


def effective_procs(declared: int, cpu: int, jobs: int, requested: int | None = None) -> int:
    """Processes a gate runs with: its declared count, capped by its share of the machine.

    ``requested`` is an explicit ``HEXPLAIN_GATE_WORKERS`` from the caller's environment, a
    further cap. The result is both the gate's claim on the process budget and the worker count
    it is told to use; when those two were computed separately the budget counted processes the
    gate never started, or missed ones it did.
    """
    share = max(1, cpu // jobs)
    return max(1, min(declared, share, requested if requested is not None else declared))


def available_memory() -> int | None:
    """Bytes the host has free now, or None when that cannot be read."""
    if psutil is None:
        return None
    try:
        return int(psutil.virtual_memory().available)
    except psutil.Error:
        return None


class MemoryBudget:
    """Admits a gate when its estimate fits beside the running gates.

    ``fixed`` (bytes) is a budget for all running gates together. Without it the budget is the
    host's free memory, read again at every decision through ``available``; a host that cannot
    report it imposes no memory bound.
    """

    def __init__(self, fixed: int | None = None, available: Callable[[], int | None] = available_memory) -> None:
        if fixed is not None and fixed < 1:
            raise ValueError("a fixed memory budget must be positive")
        self.fixed = fixed
        self.available = available

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] = os.environ) -> MemoryBudget:
        """The fixed budget ``HEXPLAIN_GATE_MEMORY_MB`` names, else the host's free memory."""
        requested = environ.get(MEMORY_ENV)
        if not requested:
            return cls()
        try:
            megabytes = int(requested)
        except ValueError:
            raise ValueError(f"{MEMORY_ENV} must be an integer number of MiB, not {requested!r}") from None
        if megabytes < 1:
            raise ValueError(f"{MEMORY_ENV} must be at least 1")
        return cls(megabytes * MIB)

    def admits(self, candidate: int, running: list[tuple[int, int]]) -> bool:
        """Whether a gate estimated at ``candidate`` bytes fits; ``running`` is (estimate, held) per gate."""
        if self.fixed is not None:
            return candidate + sum(max(estimate, held) for estimate, held in running) <= self.fixed
        free = self.available()
        if free is None:
            return True
        unclaimed = sum(max(0, estimate - held) for estimate, held in running)
        return candidate + unclaimed <= free * HOST_SHARE

    def describe(self) -> str:
        if self.fixed is not None:
            return f"fixed at {self.fixed // MIB} MiB"
        return f"{HOST_SHARE:.0%} of the host's free memory, read at every scheduling decision"


class Scheduler:
    """Launch gates as the job, process and memory bounds allow; longest recorded gate first."""

    def __init__(
        self,
        gates: list[Gate],
        jobs: int,
        costs: Mapping[str, GateCost],
        memory: MemoryBudget,
        process_budget: int,
    ) -> None:
        self.jobs = jobs
        self.memory = memory
        self.process_budget = process_budget
        self.estimate = {g["name"]: self._estimate(costs.get(g["name"])) for g in gates}
        # Longest first: the recorded duration, then the name, so the order is reproducible.
        self.pending = sorted(gates, key=lambda g: (-self._duration(costs.get(g["name"])), g["name"]))
        self.running: dict[Future[dict[str, Any]], Gate] = {}
        #: Bytes each running gate's process tree holds now, published by its memory sampler.
        self.held: dict[str, int] = {}

    @staticmethod
    def _estimate(cost: GateCost | None) -> int:
        return (cost.peak_rss_bytes if cost is not None else None) or DEFAULT_GATE_RSS

    @staticmethod
    def _duration(cost: GateCost | None) -> float:
        return cost.duration_s if cost is not None else 0.0

    def fits(self, gate: Gate) -> bool:
        if not self.running:
            return True  # Something always runs, however large.
        if len(self.running) >= self.jobs:
            return False
        procs = sum(g["effective_procs"] for g in self.running.values()) + gate["effective_procs"]
        if procs > self.process_budget:
            return False
        claims = [(self.estimate[g["name"]], self.held.get(g["name"], 0)) for g in self.running.values()]
        return self.memory.admits(self.estimate[gate["name"]], claims)

    def next_ready(self) -> Gate | None:
        for index, gate in enumerate(self.pending):
            if self.fits(gate):
                return self.pending.pop(index)
        return None

    def started(self, future: Future[dict[str, Any]], gate: Gate) -> None:
        self.running[future] = gate

    def finished(self, future: Future[dict[str, Any]]) -> Gate:
        gate = self.running.pop(future)
        self.held.pop(gate["name"], None)
        return gate
