"""Run every gate in this directory and report a single verdict.

CI and local checks share this runner so newly added gates cannot be forgotten.

So this discovers gates rather than listing them, and does it by EXCLUSION: everything in
tools/ is a gate unless named below. An include-pattern (test_*.py) would have silently
skipped validate_all.py, which is a gate under a different name -- and, worse, would silently
skip the next gate that does not match the pattern, which is the exact failure this file
exists to prevent. Exclusion fails the other way: forget to list a new helper and it gets
run, errors, and you notice. Loud beats silent.

Gates are independent, so a failure does not stop the run -- one broken gate should not hide
the state of the others. Exit code is 0 only if every gate passed.

    python tools/run_gates.py            # all gates
    python tools/run_gates.py hx round   # only gates whose name contains "hx" or "round"
"""

import glob
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Not gates. `specgraph` is a library; `shacl_check` is an interactive CLI that validates a
#: file you name, so it has no fixed subject to check and nothing to assert without one.
NOT_GATES = {"run_gates", "specgraph", "shacl_check"}


def main(filters):
    gates = sorted(
        g for g in glob.glob("tools/*.py", root_dir=ROOT)
        if pathlib.Path(g).stem not in NOT_GATES and not pathlib.Path(g).stem.startswith("_")
    )
    if filters:
        gates = [g for g in gates if any(f in g for f in filters)]
    if not gates:
        sys.exit(f"FAIL: no gates matched {filters or '(none)'}")

    failed = []
    for gate in gates:
        proc = subprocess.run(
            [sys.executable, gate], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
        )
        name = pathlib.Path(gate).stem
        if proc.returncode == 0:
            # Gates print their own one-line PASS summary; keep it, it carries the counts.
            last = [ln for ln in proc.stdout.splitlines() if ln.strip()]
            print(f"PASS  {name:28} {last[-1].strip() if last else ''}")
        else:
            failed.append((name, proc.stdout + proc.stderr))
            print(f"FAIL  {name}")

    for name, output in failed:
        print(f"\n{'=' * 70}\n{name}\n{'=' * 70}\n{output.rstrip()}")

    print(f"\n{len(gates) - len(failed)}/{len(gates)} gates passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
