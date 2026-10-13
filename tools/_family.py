"""Load the complete, versioned specification family; missing files fail closed.

``family.json`` lists every Turtle file of the family under ``files``. Each canonical module
(the vocabulary, its shapes) has a sibling annotation graph, ``<module>-doc.ttl``, holding the
generated editorial annotations (labels, definitions and scope notes written by
``tools/_build_term_reference.py --enrich``); ``documentation`` maps each module to it. The
annotation graph declares no ontology of its own: its statements annotate the module's terms,
and the module validates identically without it. Loading the family loads both, so a consumer
that reads ``files`` sees the same graph it always did.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from rdflib import Graph

#: The suffix that distinguishes a module's generated annotation graph from the module.
DOC_SUFFIX = "-doc.ttl"


def documentation_name(name: str) -> str:
    """The family-relative name of the annotation graph beside the canonical module ``name``."""
    assert name.endswith(".ttl") and not name.endswith(DOC_SUFFIX), name
    return name[: -len(".ttl")] + DOC_SUFFIX


def is_documentation(name: str | Path) -> bool:
    """Whether a family file is a generated annotation graph rather than a canonical module."""
    return str(name).endswith(DOC_SUFFIX)


def _contract(root: Path, manifest: Path | None = None) -> dict[str, Any]:
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
    canonical = [f for f in files if not is_documentation(f)]
    expected = {f: documentation_name(f) for f in canonical}
    if contract.get("documentation") != expected or set(expected.values()) != set(files) - set(canonical):
        raise ValueError(
            "Specification family documentation map differs: every canonical module has exactly one "
            f"sibling <module>{DOC_SUFFIX}, listed in files and mapped under documentation"
        )
    return contract


def family_paths(root: Path, manifest: Path | None = None) -> list[Any]:
    """Every family file, canonical modules and their annotation graphs, as absolute paths."""
    root = Path(root).resolve()
    return [str(root / name) for name in _contract(root, manifest)["files"]]


def canonical_files(root: Path, manifest: Path | None = None) -> list[str]:
    """The family-relative names of the canonical modules: the files that declare terms and shapes."""
    return [name for name in _contract(root, manifest)["files"] if not is_documentation(name)]


def documentation_files(root: Path, manifest: Path | None = None) -> dict[str, str]:
    """Canonical module name -> the name of its generated annotation graph (both family-relative)."""
    return dict(_contract(root, manifest)["documentation"])


def load(paths: Iterable[Any]) -> Any:
    graph = Graph()
    for path in paths:
        graph.parse(data=Path(path).read_text(encoding="utf-8"), format="turtle")
    return graph
