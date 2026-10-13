"""tools/gates.json declares every gate, and only gates that exist, with sound limits.

The runner (tools/_gate_runner.py) takes its gate list, per-gate timeouts and process counts
from the manifest; the site workflow runs the docker and browser classes through the same
runner. A gate script that is not declared is never run, so the manifest is checked against
the tree here: every tools/test_*.py and validate_all.py is listed as an offline gate, every
listed gate has a script, and the classes, timeouts and process counts are well formed.
"""

from __future__ import annotations

import json
from pathlib import Path

from _gate_runner import GATE_CLASSES, load_gate_manifest

ROOT = Path(__file__).resolve().parents[1]
#: Scripts under tools/ that the offline suite runs although their name is not test_*.
OFFLINE_EXTRAS = {"validate_all"}
#: The workflow that must run the non-offline classes through the runner.
SITE_WORKFLOW = ROOT / ".github/workflows/site.yml"


def main() -> int:
    manifest = load_gate_manifest(ROOT)
    assert manifest, "tools/gates.json is missing or declares no gates"
    scripts = {p.stem for p in (ROOT / "tools").glob("test_*.py")} | OFFLINE_EXTRAS
    offline = {name for name, entry in manifest.items() if entry["class"] == "offline"}
    missing = sorted(scripts - offline)
    assert not missing, "gates in tools/ not declared offline in tools/gates.json: " + ", ".join(missing)
    unknown = sorted(name for name in manifest if not (ROOT / "tools" / f"{name}.py").is_file())
    assert not unknown, "tools/gates.json declares gates without a script: " + ", ".join(unknown)
    stray = sorted(offline - scripts)
    assert not stray, "offline gates that are neither test_*.py nor validate_all: " + ", ".join(stray)
    classes = {entry["class"] for entry in manifest.values()}
    assert classes <= set(GATE_CLASSES), classes
    for name, entry in manifest.items():
        assert 0 < entry["timeout"] <= 3600, (name, entry["timeout"])
        assert entry.get("procs", 1) >= 1, (name, entry.get("procs"))
    # The manifest file itself is what the runner reads; it must stay the canonical JSON form.
    text = (ROOT / "tools/gates.json").read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=2) + "\n", "tools/gates.json is not canonically formatted"
    workflow = SITE_WORKFLOW.read_text(encoding="utf-8")
    for gate_class in sorted(classes - {"offline"}):
        assert f"--class {gate_class}" in workflow, f"site.yml does not run the {gate_class} gates through the runner"
    by_class = {c: sum(e["class"] == c for e in manifest.values()) for c in GATE_CLASSES}
    print(f"PASS: tools/gates.json declares {len(manifest)} gates ({by_class}); every tools/test_*.py is among them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
