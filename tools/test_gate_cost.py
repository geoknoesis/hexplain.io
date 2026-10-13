"""The cost of a gate run is evidence too: its summary, the tracked record and the timeouts derived from it."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any

from _gate_cost import COSTS, derive_timeout, derive_timeouts, load_costs, read_record, render, summarise
from _gate_runner import main as run_gates

MIB = 1024 * 1024


def gate_row(name: str, seconds: float, rss_mib: int | None, processes: int | None) -> dict[str, Any]:
    return dict(
        gate=name,
        status="PASS",
        duration_seconds=seconds,
        peak_rss_bytes=None if rss_mib is None else rss_mib * MIB,
        peak_processes=processes,
        rss_samples=0 if rss_mib is None else 30,
    )


def write_report(path: Path, **record: Any) -> None:
    path.write_text(json.dumps(record), encoding="utf-8", newline="\n")


def check_summary(temp: Path) -> None:
    """Wall clock and the sum of durations are separate figures; an unfinished run is not summarised."""
    report = temp / "summary.json"
    write_report(
        report,
        status="complete",
        jobs=4,
        wall_clock_seconds=125.0,
        counts=dict(PASS=2, SKIP=0, FAIL=0),
        gates=[gate_row("test_slow", 120.0, 900, 9), gate_row("test_fast", 61.5, 30, 1)],
    )
    summary = summarise(report)
    # Two gates of 120 s and 61.5 s that ran side by side: 181.5 s of work in 125 s of wall clock.
    assert summary["gate_seconds_sum"] == 181.5, summary
    assert summary["wall_clock_seconds"] == 125.0, summary
    assert summary["peak_rss_bytes"] == 900 * MIB, summary
    assert summary["peak_processes"] == 9, summary
    # Ordered by cost, so the gate worth attention is the first line and not the twentieth.
    assert [row["gate"] for row in summary["by_duration"]] == ["test_slow", "test_fast"], summary
    assert [row["gate"] for row in summary["by_memory"]] == ["test_slow", "test_fast"], summary
    text = render(summary)
    assert "test_slow" in text and "900" in text.replace(",", ""), text
    assert "wall clock 125.0s at --jobs 4" in text and "sum of gate durations 181.5s" in text, text

    # A record written before the wall clock was kept says so rather than passing the sum off as it.
    write_report(
        report, status="complete", counts=dict(PASS=1, SKIP=0, FAIL=0), gates=[gate_row("test_fast", 1.0, None, None)]
    )
    summary = summarise(report)
    assert summary["wall_clock_seconds"] is None and "wall clock not recorded" in render(summary), render(summary)
    # A run where nothing sampled memory must say so rather than report a peak of zero.
    assert summary["peak_rss_bytes"] is None, summary
    assert "not sampled" in render(summary), render(summary)

    # An incomplete run is not summarised as though it finished.
    write_report(report, status="running", gates=[])
    try:
        summarise(report)
        raise AssertionError("summarised an unfinished run")
    except SystemExit as failure:
        assert "running" in str(failure), failure
    try:
        summarise(temp / "absent.json")
        raise AssertionError("summarised a missing report")
    except SystemExit:
        pass


def check_timeout_rule() -> None:
    """Ten times the recorded duration, rounded up to five minutes, from five minutes to an hour."""
    for seconds, expected in [
        (None, 300),
        (0.0, 300),
        (1.2, 300),
        (30.0, 300),
        (30.1, 600),
        (60.0, 600),
        (85.0, 900),
        (330.0, 3300),
        (360.0, 3600),
        (361.0, 3600),
        (5000.0, 3600),
    ]:
        assert derive_timeout(seconds) == expected, (seconds, derive_timeout(seconds), expected)
    for invalid in (-1.0, float("nan"), float("inf")):
        try:
            derive_timeout(invalid)
            raise AssertionError(f"derived a timeout from {invalid}")
        except ValueError:
            pass


def gate_tree(root: Path) -> None:
    """A tree with a manifest: two offline gates and one docker gate."""
    tools = root / "tools"
    tools.mkdir(parents=True)
    for name in ("test_one", "test_two", "_check_docker"):
        (tools / f"{name}.py").write_text("print('PASS')\n", encoding="utf-8", newline="\n")
    (tools / "gates.json").write_text(
        json.dumps(
            dict(
                schema_version=1,
                gates=[
                    dict(name="test_one", **{"class": "offline"}, timeout=900),
                    dict(name="test_two", **{"class": "offline"}, timeout=300),
                    dict(name="_check_docker", **{"class": "docker"}, timeout=300),
                ],
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refused(root: Path, argv: list[str]) -> bool:
    try:
        run_gates(root, set(), argv)
    except SystemExit as error:
        return error.code == 2
    return False


def check_record(root: Path) -> None:
    """The tracked record is written by a complete unfiltered run, merged by gate, and never by a partial one."""
    gate_tree(root)
    record = root / COSTS
    assert load_costs(root) == {}, "a tree without a record has no costs"
    # A filtered run, or one with a clamped timeout, is refused before any gate starts.
    assert refused(root, ["--record-costs", "test_one"]), "a filtered run was allowed to record costs"
    assert refused(root, ["--record-costs", "--timeout", "5"]), "a clamped run was allowed to record costs"
    assert not record.exists()
    # A failed run leaves the record alone.
    (root / "tools/test_two.py").write_text("raise SystemExit(1)\n", encoding="utf-8", newline="\n")
    assert run_gates(root, set(), ["--strict", "--record-costs"]) == 1
    assert not record.exists(), "a failed run was recorded"
    (root / "tools/test_two.py").write_text("print('PASS')\n", encoding="utf-8", newline="\n")
    assert run_gates(root, set(), ["--strict", "--record-costs"]) == 0
    first = read_record(root)
    assert sorted(first["gates"]) == ["test_one", "test_two"], first["gates"]
    assert set(first["gates"]["test_one"]) == {"duration_s", "peak_rss_mb", "procs"}, first["gates"]["test_one"]
    run = first["runs"]["offline"]
    assert run["gates"] == 2 and run["jobs"] >= 1 and run["wall_clock_s"] > 0 and run["sequential_sum_s"] > 0, run
    described = {"recorded_utc", "platform", "python", "cpu_count", "memory_mb"}
    assert described | {"available_mb_at_start", "cpu_busy_percent_at_start"} <= set(run), run
    # Recording another class merges: the offline entries and the offline run header stay.
    assert run_gates(root, set(), ["--strict", "--class", "docker", "--record-costs"]) == 0
    merged = read_record(root)
    assert sorted(merged["gates"]) == ["_check_docker", "test_one", "test_two"], merged["gates"]
    assert merged["gates"]["test_one"] == first["gates"]["test_one"], "recording docker rewrote an offline entry"
    assert sorted(merged["runs"]) == ["docker", "offline"] and merged["runs"]["offline"] == run, merged["runs"]
    # A plain run -- filtered or not -- never touches the tracked record.
    before = record.read_bytes()
    assert run_gates(root, set(), ["--strict", "test_one"]) == 0
    assert run_gates(root, set(), ["--strict"]) == 0
    assert record.read_bytes() == before, "a run without --record-costs changed the tracked record"
    assert record.read_text(encoding="utf-8") == json.dumps(merged, indent=2) + "\n", "record is not canonical JSON"
    # A gate removed from the manifest leaves the record with the next recording.
    manifest = root / "tools/gates.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["gates"] = [g for g in document["gates"] if g["name"] != "test_two"]
    manifest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    (root / "tools/test_two.py").unlink()
    assert run_gates(root, set(), ["--strict", "--record-costs"]) == 0
    assert sorted(read_record(root)["gates"]) == ["_check_docker", "test_one"]


def check_derived_timeouts(root: Path) -> None:
    """--derive-timeouts rewrites the manifest from the record and runs nothing."""
    manifest = root / "tools/gates.json"
    document = read_record(root)
    document["gates"]["test_one"]["duration_s"] = 45.0
    (root / COSTS).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert derive_timeouts(root) == ["test_one"], "expected exactly the gate whose recorded duration moved"
    timeouts = {g["name"]: g["timeout"] for g in json.loads(manifest.read_text(encoding="utf-8"))["gates"]}
    assert timeouts == {"test_one": 600, "_check_docker": 300}, timeouts
    assert derive_timeouts(root) == [], "a second derivation changed something"
    document["gates"]["test_one"]["duration_s"] = 1.0
    (root / COSTS).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    (root / ".gate-results/summary.json").unlink()
    assert run_gates(root, set(), ["--derive-timeouts"]) == 0
    assert not (root / ".gate-results/summary.json").exists(), "--derive-timeouts ran the gates"
    timeouts = {g["name"]: g["timeout"] for g in json.loads(manifest.read_text(encoding="utf-8"))["gates"]}
    assert timeouts == {"test_one": 300, "_check_docker": 300}, timeouts
    # A malformed entry is an error, not a default.
    document["gates"]["test_one"] = dict(duration_s="soon")
    (root / COSTS).write_text(json.dumps(document), encoding="utf-8", newline="\n")
    try:
        load_costs(root)
        raise AssertionError("accepted a malformed cost entry")
    except ValueError as error:
        assert "test_one" in str(error), error


def main() -> int:
    quiet = io.StringIO()
    with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet), tempfile.TemporaryDirectory() as temp:
        check_summary(Path(temp))
        check_timeout_rule()
        root = Path(temp) / "tree"
        check_record(root)
        check_derived_timeouts(root)
    print(
        "PASS: gate cost summary separates wall clock from the duration sum and refuses partial runs; the tracked "
        "record merges by gate and only from a complete unfiltered run; timeouts follow the 10x rule"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
