"""Canonical ontology and shape loading through specification/family.json.

The family graph is parsed by two dozen gates. Parsing it costs well under a second, but a
pickled copy loads several times faster, so :func:`ontologies` keeps one under
``.gate-results/family-cache/`` keyed on the runner's source manifest digest
(``HEXPLAIN_SOURCE_MANIFEST_SHA256``, set by tools/_gate_runner.py for every gate it launches)
or, outside the runner, on the digest of the family files themselves. A key mismatch, a
missing cache or any failure to read it falls back to parsing; the cache is never the source
of truth, only a copy of what the Turtle files say.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from collections.abc import Iterable
from pathlib import Path

import rdflib
from _family import family_paths
from _family import load as _load_files
from rdflib import OWL, RDF, Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
VANN_URI = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
CACHE_DIR = ROOT / ".gate-results/family-cache"
MANIFEST_ENV = "HEXPLAIN_SOURCE_MANIFEST_SHA256"


def load(paths: Iterable[str | Path]) -> Graph:
    """One graph from Turtle files; a relative path is relative to the repository root.

    Never to the working directory: a gate gives the same answer wherever it is started.
    """
    return _load_files([ROOT / p for p in paths])


def glob(pattern: str) -> list[str]:
    """The repository-relative POSIX paths of the files matching ``pattern``, sorted."""
    return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())


def ontology_paths() -> list[str]:
    """Every family file, as a path relative to the repository root."""
    return [Path(p).relative_to(ROOT).as_posix() for p in family_paths(ROOT / "specification")]


def shape_paths() -> list[str]:
    """The shapes are the family itself: every module carries its own SHACL."""
    return ontology_paths()


def _cache_key(paths: list[str]) -> str:
    """The runner's source-manifest digest when it launched us, else a digest of the family bytes."""
    runner = os.environ.get(MANIFEST_ENV)
    if runner:
        return "manifest-" + runner
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.encode("utf-8"))
        digest.update((ROOT / path).read_bytes())
    return "family-" + digest.hexdigest()


def _family_graph(paths: list[str]) -> Graph:
    """The family graph, from the pickle cache when its key matches, else parsed (and cached)."""
    key = _cache_key(paths)
    cache = CACHE_DIR / f"{key}.pickle"
    # Version 2: the namespace bindings travel with the triples (a pickled Graph drops its
    # NamespaceManager, and the range library names cases by the family's own prefixes).
    stamp = (2, key, rdflib.__version__, tuple(paths))
    # The pickle is written by this module alone, under the repository's ignored .gate-results/
    # directory, from Turtle this checkout parsed: it is a local derived file, never an input
    # fetched from elsewhere, which is the condition under which unpickling is safe.
    try:
        with cache.open("rb") as stream:
            stored_stamp, bindings, graph = pickle.load(stream)
        if stored_stamp == stamp and isinstance(graph, Graph):
            for prefix, namespace in bindings:
                graph.bind(prefix, namespace, override=True, replace=True)
            return graph
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError, ValueError, TypeError):
        pass
    graph = load(paths)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_suffix(f".{os.getpid()}.tmp")
        with temporary.open("wb") as stream:
            bindings = [(prefix, str(namespace)) for prefix, namespace in graph.namespace_manager.namespaces()]
            pickle.dump((stamp, bindings, graph), stream, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(cache)
    except OSError:
        pass  # A cache that cannot be written is simply not a cache.
    return graph


def ontologies(extra: Iterable[str] = ()) -> Graph:
    """The family graph plus any ``extra`` Turtle files; a fresh graph on every call."""
    graph = _family_graph(ontology_paths())
    extra = list(extra)
    if extra:
        graph += load(extra)
    return graph


def shapes() -> Graph:
    """The family's shapes graph; a fresh graph on every call."""
    return _family_graph(shape_paths())


def modules_for(namespaces: Iterable[str]) -> list[str]:
    """The family files whose ontologies claim ``namespaces``, plus everything they owl:import.

    A gate validating data that uses only a few aspects loads only those modules' shapes (pySHACL
    pays for every shape in the graph on every call); the import closure keeps the selection
    honest when a module starts depending on another.
    """
    family = _family_graph(ontology_paths())
    wanted = set(namespaces)
    selected = {o for o in family.subjects(RDF.type, OWL.Ontology) if str(family.value(o, VANN_URI) or "") in wanted}
    todo = list(selected)
    while todo:
        for imported in family.objects(todo.pop(), OWL.imports):
            if imported not in selected:
                selected.add(imported)
                todo.append(imported)
    files = []
    for path in ontology_paths():
        declared = set(Graph().parse(ROOT / path, format="turtle").subjects(RDF.type, OWL.Ontology))
        if declared & selected:
            files.append(path)
    return files


def shapes_of(files: Iterable[str]) -> Graph:
    """The shapes graph of the given family files (repository-relative paths); a fresh graph."""
    return load(files)
