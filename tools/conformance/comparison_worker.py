"""Isolated artifact comparison, bounded by the runner's deadline, one request or a stream of them."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import compare
import round_trip

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024


def artifact_problem(path: Path) -> str | None:
    if path.is_file() and path.stat().st_size > MAX_ARTIFACT_BYTES:
        return f"artifact {path.name} exceeds {MAX_ARTIFACT_BYTES} bytes"
    return None


def comparison(mode: str, case: Path, actual: Path, base: str, category_map: dict[str, str] | None = None) -> list[str]:
    """The bounded problems of one comparison; malformed artifacts are case failures, not worker failures.
    [category_map] maps the implementation's error names to the Processing Model's categories (--category-map)."""
    try:
        problem = artifact_problem(actual)
        if problem:
            problems = [problem]
        elif mode == "case":
            problems = compare.compare_case(case, actual, reported_base=base or None, category_map=category_map)
        else:
            manifest = json.loads((case / "manifest.json").read_text(encoding="utf-8"))
            tree = json.loads((case / "expected.json").read_text(encoding="utf-8"))
            exempt = round_trip.recomputed_paths(case / "description.ttl", manifest.get("root"), tree)
            problems = round_trip.isomorphism_problems(
                tree,
                compare.read_actual_json(actual),
                exempt,
            )
    except RecursionError:
        problems = ["the output could not be compared: it is nested more deeply than the comparator can follow"]
    except Exception as exc:  # noqa: BLE001 -- malformed artifacts are case failures
        problems = [f"the output could not be compared: {exc}"]
    # Never return an unbounded diagnostic to the parent.
    return [str(p)[:2000] for p in problems[:20]]


def serve() -> int:
    """Answer one JSON request per stdin line with one JSON line, so imports are paid once per run."""
    for stream in (sys.stdin, sys.stdout):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")  # Paths need not be ASCII.
    replies = sys.stdout
    sys.stdout = sys.stderr  # Stray prints from a comparison must not corrupt the reply stream.
    for line in sys.stdin:
        request = json.loads(line)
        problems = comparison(
            request["mode"],
            Path(request["case"]),
            Path(request["actual"]),
            request["base"],
            request.get("categories") or None,
        )
        replies.write(json.dumps(problems) + "\n")
        replies.flush()
    return 0


def main() -> int:
    if sys.argv[1:] == ["--serve"]:
        return serve()
    mode, case_arg, actual_arg, result_arg, base = sys.argv[1:]
    problems = comparison(mode, Path(case_arg), Path(actual_arg), base)
    Path(result_arg).write_text(json.dumps(problems), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
