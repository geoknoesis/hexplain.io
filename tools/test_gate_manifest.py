"""tools/gates.json declares every gate, and only gates that exist, with mechanically derived limits.

The runner (tools/_gate_runner.py) takes its gate list, per-gate timeouts and process counts
from the manifest; the site workflow runs the docker and browser classes through the same
runner. A gate script that is not declared is never run, so the manifest is checked against
the tree here: every tools/test_*.py and validate_all.py is listed as an offline gate, every
listed gate has a script, and the classes and process counts are well formed.

No timeout is chosen by hand. Each is what tools/_gate_cost.derive_timeout makes of the gate's
duration in the tracked cost record (tools/gate-costs.json): ten times the recorded duration,
rounded up to five minutes, at least five minutes and at most an hour; a gate added since the last
recording has no duration yet and gets the minimum. The record names no gate the manifest lacks,
and the workflow job limits must leave room for the gate timeouts they contain. ``pytest tools``
must collect the same offline gates.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from _gate_cost import COSTS, derive_timeout, load_costs, read_record
from _gate_runner import GATE_CLASSES, WORKER_CAP, Gate, load_gate_manifest

ROOT = Path(__file__).resolve().parents[1]
#: Scripts under tools/ that the offline suite runs although their name is not test_*.
OFFLINE_EXTRAS = {"validate_all"}
#: The workflow that must run the non-offline classes through the runner.
SITE_WORKFLOW = ROOT / ".github/workflows/site.yml"
#: The workflow that runs the offline class.
VALIDATE_WORKFLOW = ROOT / ".github/workflows/validate.yml"


def check_declarations(manifest: dict[str, Gate]) -> None:
    """Every gate script is declared, every declaration has a script, and the fields are sound."""
    scripts = {p.stem for p in (ROOT / "tools").glob("test_*.py")} | OFFLINE_EXTRAS
    offline = {name for name, entry in manifest.items() if entry["class"] == "offline"}
    missing = sorted(scripts - offline)
    assert not missing, "gates in tools/ not declared offline in tools/gates.json: " + ", ".join(missing)
    unknown = sorted(name for name in manifest if not (ROOT / "tools" / f"{name}.py").is_file())
    assert not unknown, "tools/gates.json declares gates without a script: " + ", ".join(unknown)
    stray = sorted(offline - scripts)
    assert not stray, "offline gates that are neither test_*.py nor validate_all: " + ", ".join(stray)
    assert {entry["class"] for entry in manifest.values()} <= set(GATE_CLASSES)
    for name, entry in manifest.items():
        # A gate cannot fan out beyond the worker cap, so a larger declaration only distorts the budget.
        assert 1 <= entry.get("procs", 1) <= WORKER_CAP, (name, entry.get("procs"))
    # The manifest file itself is what the runner reads; it must stay the canonical JSON form.
    text = (ROOT / "tools/gates.json").read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=2) + "\n", "tools/gates.json is not canonically formatted"


def check_timeouts(manifest: dict[str, Gate]) -> str:
    """Every timeout is the rule applied to the tracked record; returns what the record covers."""
    costs = load_costs(ROOT)
    undeclared = sorted(set(costs) - set(manifest))
    assert not undeclared, f"{COSTS} records gates the manifest does not declare: " + ", ".join(undeclared)
    wrong = []
    for name, entry in sorted(manifest.items()):
        cost = costs.get(name)
        expected = derive_timeout(None if cost is None else cost.duration_s)
        if entry["timeout"] != expected:
            wrong.append(f"{name}: {entry['timeout']} s declared, {expected} s derived")
    assert not wrong, (
        "timeouts that do not follow the rule (run `python tools/run_gates.py --derive-timeouts`):\n  "
        + "\n  ".join(wrong)
    )
    text = (ROOT / COSTS).read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=2) + "\n", f"{COSTS} is not canonically formatted"
    assert "offline" in read_record(ROOT)["runs"], f"{COSTS} does not say which offline run it was measured from"
    unrecorded = sorted(name for name, entry in manifest.items() if entry["class"] == "offline" and name not in costs)
    covered = f"{len(costs)} recorded costs"
    return covered + (f" ({', '.join(unrecorded)} not yet recorded: minimum timeout)" if unrecorded else "")


def job_limit_seconds(workflow: Path, job: str) -> int:
    """The ``timeout-minutes`` of one job of a workflow, in seconds."""
    text = workflow.read_text(encoding="utf-8")
    found = re.search(rf"^  {re.escape(job)}:\n(?:(?:    .*)?\n)*?    timeout-minutes: (\d+)\n", text, re.M)
    assert found, f"{workflow.name}: job {job} declares no timeout-minutes"
    return int(found.group(1)) * 60


def check_workflows(manifest: dict[str, Gate]) -> None:
    """The workflows run every class through the runner, within job limits the gate timeouts fit in."""
    site = SITE_WORKFLOW.read_text(encoding="utf-8")
    classes = {entry["class"] for entry in manifest.values()} - {"offline"}
    for gate_class in sorted(classes):
        assert f"--class {gate_class}" in site, f"site.yml does not run the {gate_class} gates through the runner"
    # The site job runs its classes one after the other, so a gate that uses its whole timeout in
    # each must still end before the job is cancelled: a cancelled job uploads no gate record.
    within = sum(entry["timeout"] for entry in manifest.values() if entry["class"] in classes)
    limit = job_limit_seconds(SITE_WORKFLOW, "publication")
    assert limit > within, f"site.yml allows the job {limit} s but its gates may take {within} s"
    longest = max(entry["timeout"] for entry in manifest.values() if entry["class"] == "offline")
    limit = job_limit_seconds(VALIDATE_WORKFLOW, "validate")
    assert limit > longest, f"validate.yml allows the job {limit} s but one gate may take {longest} s"


def check_pytest_collection(manifest: dict[str, Gate]) -> str:
    """``pytest tools`` collects exactly the offline gates; checked when pytest is installed."""
    conftest = (ROOT / "tools/conftest.py").read_text(encoding="utf-8")
    assert "load_gate_manifest" in conftest and "timeout=self.timeout" in conftest, (
        "tools/conftest.py must take its gate list and timeouts from tools/gates.json"
    )
    if importlib.util.find_spec("pytest") is None:
        return "pytest is not installed, so its collection was checked statically only"
    listed = subprocess.run(
        [sys.executable, "-m", "pytest", "tools", "--collect-only", "-q", "-p", "no:xdist"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
        check=False,
    )
    collected = {line.split("::")[1] for line in listed.stdout.splitlines() if "::" in line}
    offline = {name for name, entry in manifest.items() if entry["class"] == "offline"}
    assert collected == offline, (
        "pytest collects a different gate set than tools/gates.json declares offline",
        sorted(collected ^ offline),
        listed.stdout[-2000:] + listed.stderr[-2000:],
    )
    return f"pytest collects the same {len(collected)} offline gates"


def main() -> int:
    manifest = load_gate_manifest(ROOT)
    assert manifest, "tools/gates.json is missing or declares no gates"
    check_declarations(manifest)
    recorded = check_timeouts(manifest)
    check_workflows(manifest)
    collection = check_pytest_collection(manifest)
    by_class = {c: sum(e["class"] == c for e in manifest.values()) for c in GATE_CLASSES}
    print(
        f"PASS: tools/gates.json declares {len(manifest)} gates ({by_class}); every tools/test_*.py is among them; "
        f"every timeout is derived from the {recorded}; {collection}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
