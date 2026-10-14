"""Write the processor conformance suite from its case modules.

    python tools/conformance/generate_inputs.py          # (re)write specification/conformance/<class>/
    python tools/conformance/generate_inputs.py --check  # exit 1 if the tree on disk differs

Every case -- its description, its input bytes and its expected output -- is authored in the
cases_*.py modules beside this file, so a binary input is reviewable as the Python that builds it
and reproducible byte for byte. The class directories are generated: edit the modules, not them.
writer/round-trip-expectations.json is generated with them, from round_trip.py.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import CLASSES, PREFIX, SUITE  # noqa: E402

#: Case modules. The physical-parser modules after cases_physical add to its CASES list.
MODULES = (
    "cases_physical",
    "cases_integers",
    "cases_regions",
    "cases_selection",
    "cases_integrity",
    "cases_text",
    "cases_encodings",
    "cases_layout_cells",
    "cases_limits",
    "cases_hel",
    "cases_rules",
    "cases_semantic",
    "cases_bundle",
    "cases_hdl",
    "cases_evaluator",
    "cases_features",
    "cases_features_hdl",
    "cases_hdl_names",
    "cases_terms",
    "cases_writer",
    "cases_writer_forms",
)


def all_cases() -> Any:
    lists = []
    for module in [__import__(name) for name in MODULES]:
        own = getattr(module, "CASES", None)
        if own is not None and not any(own is seen for seen in lists):
            lists.append(own)
    cases = [case for group in lists for case in group]
    seen = set()
    for case in cases:
        if case.cls not in CLASSES:
            raise ValueError(f"{case.id}: unknown class {case.cls}")
        if not case.id.startswith(PREFIX[case.cls] + "-"):
            raise ValueError(f"{case.id}: a {case.cls} case id starts with {PREFIX[case.cls]}-")
        if case.id in seen:
            raise ValueError(f"duplicate case id {case.id}")
        seen.add(case.id)
    return cases


def expected_tree() -> Any:
    """{relative path: bytes} of every generated file: the cases, and the round-trip expectations of the Physical
    Parser cases that state a tree (round_trip.py)."""
    import round_trip

    out = {}
    cases = all_cases()
    for case in cases:
        for name, content in case.artifacts().items():
            out[f"{case.cls}/{case.id}/{name}"] = content
    parsers = {case.id: case for case in cases if case.cls == "physical-parser" and case.description is not None}
    out[round_trip.EXPECTATIONS] = round_trip.expectations_file(parsers)
    return out


def on_disk() -> Any:
    out = {}
    for cls in CLASSES:
        base = SUITE / cls
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file():
                    out[path.relative_to(SUITE).as_posix()] = path.read_bytes()
    return out


def main(argv: list[str]) -> int:
    wanted = expected_tree()
    if "--check" in argv:
        present = on_disk()
        stale = sorted(p for p in wanted.keys() | present.keys() if wanted.get(p) != present.get(p))
        if stale:
            print(
                f"FAIL: {len(stale)} suite file(s) differ from the case modules; run "
                "python tools/conformance/generate_inputs.py\n  " + "\n  ".join(stale[:20])
            )
            return 1
        print(f"PASS: {len(wanted)} suite files match the case modules")
        return 0
    for cls in CLASSES:
        shutil.rmtree(SUITE / cls, ignore_errors=True)
    for rel, content in sorted(wanted.items()):
        target = SUITE / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    counts = {cls: sum(1 for c in all_cases() if c.cls == cls) for cls in CLASSES}
    print(f"wrote {sum(counts.values())} cases: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
