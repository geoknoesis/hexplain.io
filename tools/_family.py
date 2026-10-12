"""Load the complete, versioned specification family; missing files fail closed."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rdflib import Graph


def family_paths(root: Path, manifest: Path | None = None) -> list[Any]:
    root = Path(root).resolve()
    manifest = Path(manifest) if manifest else root / "family.json"
    contract = json.loads(manifest.read_text(encoding="utf-8"))
    if contract["schema_version"] != 1:
        raise ValueError("Unsupported specification family schema")
    files = contract["files"]
    discovered = sorted(
        p.relative_to(root).as_posix()
        for pattern in ("*/*.ttl", "aspect/*/*.ttl", "register/*/*.ttl")
        for p in root.glob(pattern)
    )
    if files != sorted(set(files)) or files != discovered:
        raise ValueError(
            f"Specification family inventory differs: missing={set(files) - set(discovered)}, "
            f"unlisted={set(discovered) - set(files)}"
        )
    return [str(root / name) for name in files]


def load(paths: Iterable[Any]) -> Any:
    graph = Graph()
    for path in paths:
        graph.parse(data=Path(path).read_text(encoding="utf-8"), format="turtle")
    return graph
