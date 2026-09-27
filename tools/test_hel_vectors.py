"""The HEL vectors assert error conditions, never the words of a diagnostic.

specification/validation/test/hel-vectors.tsv is the executable statement of HEL. An error row used to pass when
an evaluator's diagnostic contained a fragment of the reference implementation's English, which tied conformance to
one engine's messages. Each error row now names one of the conditions of HEL's Error conditions table
(specification/hel/index.html#error-conditions) and carries the old fragment only as an informative sixth column.
This gate keeps the file in that shape: every row has the columns its kind needs, every expected value and message is
JSON, every context is base64 JSON, every error names a condition the HEL page defines, and every condition the page
defines is exercised by at least one row.
"""
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "specification/validation/test/hel-vectors.tsv"
HEL = ROOT / "specification/hel/index.html"
#: Conditions that a flat data context cannot raise (the vector format's header says why).
NOT_EXPRESSIBLE = {"forward-reference"}


def conditions():
    return re.findall(r'<tr data-condition="([a-z-]+)">', HEL.read_text(encoding="utf-8"))


def check(text, defined):
    problems, used, rows = [], set(), 0
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip() or line.startswith("#"):
            continue
        rows += 1
        cols = line.split("\t")
        kind = cols[2] if len(cols) > 2 else None
        want = {"value": 5, "error": 6}.get(kind)
        if want is None:
            problems.append(f"line {number}: expectation {kind!r} is neither value nor error")
            continue
        if len(cols) != want:
            problems.append(f"line {number}: a {kind} row has {want} columns, not {len(cols)}")
            continue
        try:
            expected = json.loads(cols[3])
            json.loads(base64.b64decode(cols[4], validate=True).decode("utf-8"))
            if kind == "error" and not isinstance(json.loads(cols[5]), str):
                raise ValueError("the message is not a JSON string")
        except ValueError as exc:
            problems.append(f"line {number}: {exc}")
            continue
        if kind == "error":
            if expected not in defined:
                problems.append(f"line {number}: {expected!r} is not a condition of hel/index.html#error-conditions")
            used.add(expected)
    for missing in sorted(set(defined) - used - NOT_EXPRESSIBLE):
        problems.append(f"no row raises the condition {missing!r}")
    return rows, problems


def main():
    defined = conditions()
    if len(defined) < 5:
        print(f"FAIL: only {len(defined)} error conditions found in {HEL.relative_to(ROOT).as_posix()}")
        return 1
    probe = 'x\t1 / 0\terror\t"nonsense"\t' + base64.b64encode(b"{}").decode() + '\t"zero"'
    assert check(probe, defined)[1], "the gate no longer notices an unknown condition"
    rows, problems = check(VECTORS.read_text(encoding="utf-8"), defined)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(f"PASS: {rows} HEL vectors; every error row names one of {len(defined)} error conditions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
