"""The scheduler's three bounds, decided from injected numbers so the proof holds on any host."""

from __future__ import annotations

from concurrent.futures import Future
from typing import Any

from _gate_cost import MIB, GateCost
from _gate_schedule import DEFAULT_GATE_RSS, MEMORY_ENV, Gate, MemoryBudget, Scheduler, effective_procs


def gate(name: str, procs: int = 1) -> Gate:
    return dict(name=name, effective_procs=procs)


def start(scheduler: Scheduler, expected: str) -> Future[dict[str, Any]]:
    """Start the next ready gate, which must be ``expected``."""
    chosen = scheduler.next_ready()
    assert chosen is not None and chosen["name"] == expected, (chosen, expected)
    future: Future[dict[str, Any]] = Future()
    scheduler.started(future, chosen)
    return future


def check_effective_procs() -> None:
    """min(declared, max(1, cpu // jobs)), further capped by an explicit request; never below one."""
    for declared, cpu, jobs, requested, expected in [
        (8, 20, 4, None, 5),
        (8, 20, 2, None, 8),
        (8, 4, 4, None, 1),
        (8, 2, 4, None, 1),  # More jobs than cores: every gate still gets one process.
        (1, 20, 1, None, 1),
        (2, 20, 4, None, 2),
        (8, 20, 1, None, 8),
        (8, 20, 4, 3, 3),
        (8, 20, 4, 64, 5),  # A request above the share does not raise it.
        (2, 20, 4, 64, 2),
    ]:
        actual = effective_procs(declared, cpu, jobs, requested)
        assert actual == expected, (declared, cpu, jobs, requested, actual, expected)


def check_fixed_budget() -> None:
    """A fixed budget bounds the running gates' estimates, or what they hold when that is more."""
    budget = MemoryBudget(fixed=1000)
    assert budget.admits(400, [(500, 0)])
    assert budget.admits(500, [(500, 0)])
    assert not budget.admits(501, [(500, 0)])
    # A running gate that outgrew its estimate claims what it actually holds.
    assert not budget.admits(400, [(500, 700)])
    assert budget.describe() == "fixed at 0 MiB" and MemoryBudget(fixed=600 * MIB).describe() == "fixed at 600 MiB"
    for invalid in (0, -1):
        try:
            MemoryBudget(fixed=invalid)
            raise AssertionError("accepted a non-positive budget")
        except ValueError:
            pass
    assert MemoryBudget.from_environment({MEMORY_ENV: "600"}).fixed == 600 * MIB
    assert MemoryBudget.from_environment({}).fixed is None
    for bad in ("0", "-5", "lots", "1.5"):
        try:
            MemoryBudget.from_environment({MEMORY_ENV: bad})
            raise AssertionError(f"accepted {MEMORY_ENV}={bad}")
        except ValueError:
            pass


def check_host_budget() -> None:
    """Read from the host, the budget is read again at every decision."""
    free = [1000]
    budget = MemoryBudget(available=lambda: free[0])
    # 80 % of 1000 free: 800 for the candidate plus what the running gates have yet to claim.
    assert budget.admits(800, [])
    assert not budget.admits(801, [])
    assert budget.admits(500, [(300, 0)]) and not budget.admits(501, [(300, 0)])
    # What a running gate already holds has left the host's free memory, so it is not counted twice.
    assert budget.admits(800, [(300, 300)]) and budget.admits(800, [(300, 900)])
    assert budget.admits(700, [(300, 200)]) and not budget.admits(701, [(300, 200)])
    # The host tightens while the run is under way: the same candidate no longer fits.
    free[0] = 500
    assert not budget.admits(500, []) and budget.admits(400, [])
    # ... and loosens again.
    free[0] = 2000
    assert budget.admits(1600, [])
    # A host that cannot report its memory imposes no memory bound.
    assert MemoryBudget(available=lambda: None).admits(10**15, [(10**15, 0)])


def check_scheduler() -> None:
    """Longest recorded first; jobs, processes and memory each hold a gate back; something always runs."""
    costs = {
        "test_long": GateCost(90.0, 400.0, 5),
        "test_mid": GateCost(30.0, 700.0, 1),
        "test_short": GateCost(2.0, 100.0, 1),
    }
    gates = [gate("test_unrecorded"), gate("test_short"), gate("test_mid"), gate("test_long", procs=5)]
    scheduler = Scheduler(gates, 3, costs, MemoryBudget(fixed=1000 * MIB), process_budget=8)
    # Recorded duration, longest first; an unrecorded gate sorts last and is estimated at the default.
    assert [g["name"] for g in scheduler.pending] == ["test_long", "test_mid", "test_short", "test_unrecorded"]
    assert scheduler.estimate["test_unrecorded"] == DEFAULT_GATE_RSS
    assert scheduler.estimate["test_long"] == 400 * MIB
    long = start(scheduler, "test_long")
    # test_mid (700 MiB) does not fit beside test_long (400 MiB) in 1000 MiB; test_short does.
    short = start(scheduler, "test_short")
    # 400 + 100 + 512 exceeds the budget, and so does 400 + 100 + 700: nothing else starts.
    assert scheduler.next_ready() is None
    # Published memory samples replace the estimate once the gate holds more than was recorded.
    scheduler.held["test_long"] = 950 * MIB
    scheduler.finished(short)
    assert scheduler.next_ready() is None, "a gate that outgrew its estimate was not counted at what it holds"
    assert "test_short" not in scheduler.held
    scheduler.finished(long)
    assert "test_long" not in scheduler.held
    start(scheduler, "test_mid")

    # The job bound: two jobs, ample memory and processes.
    scheduler = Scheduler([gate("a"), gate("b"), gate("c")], 2, {}, MemoryBudget(fixed=10**12), process_budget=64)
    first = start(scheduler, "a")
    start(scheduler, "b")
    assert scheduler.next_ready() is None
    scheduler.finished(first)
    start(scheduler, "c")

    # The process bound: two five-process gates do not share eight processes; a one-process gate does.
    scheduler = Scheduler(
        [gate("a", 5), gate("b", 5), gate("c", 1)], 3, {}, MemoryBudget(fixed=10**12), process_budget=8
    )
    start(scheduler, "a")
    start(scheduler, "c")
    assert scheduler.next_ready() is None

    # Something always runs: a gate larger than every budget still starts when nothing else is running.
    scheduler = Scheduler([gate("huge", 64)], 1, {"huge": GateCost(1.0, 10**9, 64)}, MemoryBudget(fixed=1), 1)
    start(scheduler, "huge")


def main() -> int:
    check_effective_procs()
    check_fixed_budget()
    check_host_budget()
    check_scheduler()
    print(
        "PASS: effective process counts, fixed and host-read memory budgets, and longest-first scheduling within "
        "the job, process and memory bounds"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
