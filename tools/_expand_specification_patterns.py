"""Expand private authoring patterns; never introduce public helper shapes.

A templated module is its expanded template, whole: generated editorial annotations live in
the module's sibling <module>-doc.ttl, which this tool never reads. Default mode checks only.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUTHORING = ROOT / "authoring/specification"
TOKEN = re.compile(r"\{\{(constraint|datatype):([a-zA-Z0-9_]+)\}\}")


def load_catalogs() -> tuple[Any, ...]:
    return tuple(
        json.loads((AUTHORING / p).read_text(encoding="utf-8"))
        for p in ["manifest.json", "constraint-patterns.json", "primitive-types.json"]
    )


def within(root: Path, relative: Any) -> Any:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside authoring workspace: {relative}")
    return path


def render(template: Any, constraints: Any, datatypes: dict[str, Any]) -> Any:
    def expand(match):
        kind, name = match.groups()
        if kind == "constraint":
            text = constraints[name]["text"]
        else:
            row = datatypes["presets"][name]
            if row["name"] != name:
                raise ValueError(f"Preset identity mismatch: {name}")
            text = datatypes["formats"][row["format"]]
            fields = set(re.findall(r"@([a-z_]+)@", text))
            if fields != set(row) - {"format"}:
                raise ValueError(f"Missing or unexpected preset parameters: {name}")
            text = re.sub(r"@([a-z_]+)@", lambda m: row[m[1]], text)
        if "{{" in text or "}}" in text:
            raise ValueError("Recursive authoring substitutions are forbidden")
        return text

    expanded = TOKEN.sub(expand, template)
    if "{{" in expanded or "}}" in expanded:
        raise ValueError("Unknown or malformed authoring token")
    return expanded


def outputs() -> Any:
    manifest, constraints, datatypes = load_catalogs()
    result = {}
    for target, source in manifest["templates"].items():
        path = within(ROOT, target)
        if path in result:
            raise ValueError(f"Duplicate output ownership: {target}")
        if not target.startswith("specification/") or not target.endswith(".ttl"):
            raise ValueError(f"Unexpected output: {target}")
        template = within(AUTHORING, source).read_text(encoding="utf-8")
        result[path] = render(template, constraints, datatypes)
    return result


def run(write: bool = False) -> tuple[Any, ...]:
    rendered = outputs()  # Resolve every input before writing any output.
    changed = [p for p, text in rendered.items() if p.read_text(encoding="utf-8") != text]
    if changed and not write:
        raise AssertionError("Stale generated specification: " + ", ".join(str(p.relative_to(ROOT)) for p in changed))
    if write:
        for path in changed:
            path.write_text(rendered[path], encoding="utf-8", newline="\n")
    return len(rendered), len(changed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the expanded modules instead of checking")
    args = parser.parse_args()
    count, changed = run(args.write)
    print(f"PASS: {count} authoring templates expanded; {changed} changed outputs")
