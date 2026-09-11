"""Run discovered offline gates; use --strict for acceptance."""
from pathlib import Path
from _gate_runner import main

if __name__ == "__main__":
    raise SystemExit(main(Path(__file__).resolve().parents[1], {'run_gates', 'shacl_check', 'specgraph', 'check_live_publication'}))
