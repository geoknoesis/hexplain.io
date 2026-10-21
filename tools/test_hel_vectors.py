"""The HEL vectors assert error conditions, never the words of a diagnostic.

specification/validation/test/hel-vectors.tsv is the executable statement of HEL. An error row used to pass when
an evaluator's diagnostic contained a fragment of the reference implementation's English, which tied conformance to
one engine's messages. Each error row now names one of the conditions of HEL's Error conditions table
(specification/hel/index.html#error-conditions) and carries the old fragment only as an informative sixth column.
This gate keeps the file in that shape: every row has the columns its kind needs, every expected value is JSON or a
typed number (int:3, float:2 -- the form that can say a result is the Float 2.0, not the Integer 2), every message is
JSON, every context is base64 JSON whose tree form uses only the members the file defines, every error names a
condition the HEL page defines, and every condition the page defines is exercised by at least one row. The functions
that read the run -- evaluationInstant() and partExtension() -- and the result types of abs, min and max over mixed
Integer and Float arguments each have rows, so the gaps the file once declared stay closed. Every function of
the quantifiers group has at least one value row and one error row.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "specification/validation/test/hel-vectors.tsv"
HEL = ROOT / "specification/hel/index.html"


def conditions() -> list[str]:
    return re.findall(r'<tr data-condition="([a-z-]+)">', HEL.read_text(encoding="utf-8"))


#: The members of a tree context ({"$tree": {...}}), as the vector file's header defines them.
TREE_MEMBERS = frozenset(
    {"root", "instance", "self", "stream", "param", "unparsed", "extents", "registers", "instant", "asset"}
)
TYPED = re.compile(r"^(int|float):(.+)$")
#: What the file must exercise: (what a row's expression contains, the expectation kind, what its expected column
#: starts with).
REQUIRED_ROWS: tuple[tuple[str, str, str], ...] = (
    ("evaluationInstant(", "value", "int:"),
    ("evaluationInstant(", "error", '"argument"'),
    ("partExtension(", "value", '"'),
    ("partExtension(", "error", '"undefined-name"'),
    ("abs(", "value", "float:"),
    ("abs(", "value", "int:"),
    ("max(", "value", "float:"),
    ("max(", "value", "int:"),
    ("min(", "value", "float:"),
    ("min(", "value", "int:"),
)
#: Every function of the quantifiers group has at least one value row and one error row of its own.
QUANTIFIER_FUNCTIONS = (
    "all",
    "any",
    "countWhere",
    "sumOf",
    "project",
    "concatOf",
    "repeatValue",
    "concatArrays",
    "concatBytes",
    "slice",
    "integralScan",
    "modularAdd",
    "integerBytes",
    "integerText",
    "unicodeText",
    "join",
    "integerPrecision",
    "decimalText",
    "floatCast",
    "fromIEEE",
    "patchValues",
)
REQUIRED_ROWS += tuple((f"{name}(", kind, "") for name in QUANTIFIER_FUNCTIONS for kind in ("value", "error"))


def expected_value(text: str) -> object:
    """The expected column of a value row: a JSON literal, or int:<number> / float:<number> stating the type."""
    typed = TYPED.match(text)
    if not typed:
        return json.loads(text)
    number = json.loads(typed.group(2))
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        raise ValueError(f"{text!r}: a typed expectation holds a JSON number")
    if typed.group(1) == "int" and not isinstance(number, int):
        raise ValueError(f"{text!r}: an int: expectation holds a whole number")
    return int(number) if typed.group(1) == "int" else float(number)


def context_problems(context: object) -> list[str]:
    """A tree context holds only the members the file defines, with an integer instant and an asset of file lists."""
    if not isinstance(context, dict) or "$tree" not in context:
        return []
    tree = context["$tree"]
    problems = [f"unknown tree-context member {key!r}" for key in sorted(set(tree) - TREE_MEMBERS)]
    if "instant" in tree and (isinstance(tree["instant"], bool) or not isinstance(tree["instant"], int)):
        problems.append("the instant is an integer number of seconds")
    asset = tree.get("asset", {})
    if not isinstance(asset, dict) or not all(
        isinstance(files, list) and all(isinstance(name, str) for name in files) for files in asset.values()
    ):
        problems.append("the asset maps each part name to a list of file names")
    return problems


def row_problems(cols: list[str], kind: str, defined: list[str]) -> tuple[list[str], str | None]:
    """The problems of one well-sized row, and the condition an error row raises."""
    try:
        expected = json.loads(cols[3]) if kind == "error" else expected_value(cols[3])
        context = json.loads(base64.b64decode(cols[4], validate=True).decode("utf-8"))
        problems = context_problems(context)
        if kind == "error" and not isinstance(json.loads(cols[5]), str):
            raise ValueError("the message is not a JSON string")
    except ValueError as exc:
        return [str(exc)], None
    if kind != "error":
        return problems, None
    if expected not in defined:
        problems.append(f"{expected!r} is not a condition of hel/index.html#error-conditions")
    return problems, str(expected)


def required_rows_met(cols: list[str], kind: str) -> set[tuple[str, str, str]]:
    """The REQUIRED_ROWS entries one row satisfies."""
    return {r for r in REQUIRED_ROWS if r[0] in cols[1] and r[1] == kind and cols[3].startswith(r[2])}


def check(text: str, defined: list[str]) -> tuple[int, list[str]]:
    problems: list[str] = []
    used: set[str] = set()
    seen: set[tuple[str, str, str]] = set()
    rows = 0
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip() or line.startswith("#"):
            continue
        rows += 1
        cols = line.split("\t")
        kind = cols[2] if len(cols) > 2 else ""
        want = {"value": 5, "error": 6}.get(kind)
        if want is None:
            problems.append(f"line {number}: expectation {kind!r} is neither value nor error")
            continue
        if len(cols) != want:
            problems.append(f"line {number}: a {kind} row has {want} columns, not {len(cols)}")
            continue
        found, condition = row_problems(cols, kind, defined)
        problems += [f"line {number}: {p}" for p in found]
        if condition is not None:
            used.add(condition)
        seen |= required_rows_met(cols, kind)
    problems += [f"no row raises the condition {missing!r}" for missing in sorted(set(defined) - used)]
    for call, kind, start in sorted(set(REQUIRED_ROWS) - seen):
        problems.append(f"no {kind} row calls {call}...) with an expected column starting {start}")
    return rows, problems


def main() -> int:
    defined = conditions()
    if len(defined) < 5:
        print(f"FAIL: only {len(defined)} error conditions found in {HEL.relative_to(ROOT).as_posix()}")
        return 1
    probe = 'x\t1 / 0\terror\t"nonsense"\t' + base64.b64encode(b"{}").decode() + '\t"zero"'
    assert check(probe, defined)[1], "the gate no longer notices an unknown condition"
    assert expected_value("float:2") == 2.0 and isinstance(expected_value("float:2"), float)
    assert expected_value("int:3") == 3 and isinstance(expected_value("int:3"), int)
    for bad in ("int:2.5", "float:true", 'float:"2"', "double:2"):
        try:
            expected_value(bad)
        except ValueError:
            continue
        raise AssertionError(f"the gate accepts the expectation {bad}")
    assert context_problems({"$tree": {"root": {}, "clock": 1}}), "an unknown tree-context member went unnoticed"
    assert context_problems({"$tree": {"root": {}, "instant": "now"}}), "a non-integer instant went unnoticed"
    assert len(check(probe, defined)[1]) > len(REQUIRED_ROWS), "the gate no longer requires the run-reading rows"
    rows, problems = check(VECTORS.read_text(encoding="utf-8"), defined)
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(f"PASS: {rows} HEL vectors; every error row names one of {len(defined)} error conditions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
