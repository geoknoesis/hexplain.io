"""Run the declared gates (tools/gates.json); use --strict for acceptance."""

from __future__ import annotations

from pathlib import Path

from _gate_runner import main

#: tools/*.py scripts that are not gates, for a tree without a gate manifest.
NOT_GATES = {"run_gates", "shacl_check", "specgraph", "check_live_publication", "conftest"}

if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parents[1], NOT_GATES))
