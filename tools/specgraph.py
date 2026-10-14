"""Canonical ontology and shape loading through specification/family.json.

The family graph is parsed by two dozen gates. Parsing it costs well under a second, but a
pickled copy loads several times faster, so :func:`ontologies` keeps one under
``.gate-results/family-cache/`` keyed on the runner's source manifest digest
(``HEXPLAIN_SOURCE_MANIFEST_SHA256``, set by tools/_gate_runner.py for every gate it launches)
or, outside the runner, on the digest of the family files themselves. A key mismatch, a
missing cache or any failure to read it falls back to parsing; the cache is never the source
of truth, only a copy of what the Turtle files say. Every write prunes the directory to the
newest :data:`CACHE_KEEP` pickles and removes temporary files an interrupted write left behind.

A gate that validates small cases does not need the family: :func:`modules_used_by` names the
modules a case involves -- the homes of its terms, the modules aiming a shape at them, and
everything those import (tools/_module_selection.py) -- and :func:`shapes_of` loads just those.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import pickle
import time
from collections.abc import Iterable
from pathlib import Path

import rdflib
from _family import family_paths, is_documentation
from _family import load as _load_files
from _module_selection import family_namespaces as family_namespaces
from _module_selection import modules_for as modules_for
from _module_selection import modules_used_by as modules_used_by
from _module_selection import namespaces_in as namespaces_in
from rdflib import OWL, RDF, RDFS, Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".gate-results/family-cache"
MANIFEST_ENV = "HEXPLAIN_SOURCE_MANIFEST_SHA256"
#: Pickles kept in the cache directory: the current digest and the two before it.
CACHE_KEEP = 3
#: Seconds after which a temporary cache file is taken to be abandoned rather than in progress.
STALE_TEMPORARY = 600
#: What pySHACL adds to any graph it is given as a shapes graph (pyshacl.ShapesGraph.system_triples).
PYSHACL_AXIOMS = ((OWL.Class, RDFS.subClassOf, RDFS.Class), (OWL.DatatypeProperty, RDFS.subClassOf, RDF.Property))


def load(paths: Iterable[str | Path]) -> Graph:
    """One graph from Turtle files; a relative path is relative to the repository root.

    Never to the working directory: a gate gives the same answer wherever it is started.
    """
    return _load_files([ROOT / p for p in paths])


def glob(pattern: str) -> list[str]:
    """The repository-relative POSIX paths of the files matching ``pattern``, sorted."""
    return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())


def family_file_paths() -> list[str]:
    """Every family file, canonical modules and their generated annotation graphs alike."""
    return [Path(p).relative_to(ROOT).as_posix() for p in family_paths(ROOT / "specification")]


def ontology_paths() -> list[str]:
    """Every canonical module of the family, as a path relative to the repository root.

    These are the files that declare terms and shapes. Their generated annotation graphs
    (``<module>-doc.ttl``) are :func:`documentation_paths`; :func:`ontologies` loads both.
    """
    return [p for p in family_file_paths() if not is_documentation(p)]


def documentation_paths() -> list[str]:
    """Every generated annotation graph of the family, as a path relative to the repository root."""
    return [p for p in family_file_paths() if is_documentation(p)]


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


def prune_cache(directory: Path, keep: int = CACHE_KEEP, now: float | None = None) -> list[Path]:
    """Drop all but the newest ``keep`` pickles and every abandoned temporary file; returns what went.

    Each source change makes a new key, so without this the directory grew by one multi-megabyte
    pickle per edit, for ever. A file that cannot be removed (another process has it open) is
    left for the next write to try again.
    """
    now = time.time() if now is None else now
    removed = []

    def modified(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    pickles = sorted(directory.glob("*.pickle"), key=lambda p: (modified(p), p.name), reverse=True)
    stale = [p for p in directory.glob("*.tmp") if now - modified(p) > STALE_TEMPORARY]
    for path in [*pickles[keep:], *stale]:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def _store(cache: Path, payload: object) -> None:
    """Write the pickle atomically; a failure leaves no temporary file behind."""
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(f".{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            pickle.dump(payload, stream, protocol=pickle.HIGHEST_PROTOCOL)
        temporary.replace(cache)
    finally:
        # After a successful replace the temporary name is gone and this is a no-op.
        temporary.unlink(missing_ok=True)
    prune_cache(cache.parent)


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
    bindings = [(prefix, str(namespace)) for prefix, namespace in graph.namespace_manager.namespaces()]
    with contextlib.suppress(OSError):  # A cache that cannot be written is simply not a cache.
        _store(cache, (stamp, bindings, graph))
    return graph


def ontologies(extra: Iterable[str] = ()) -> Graph:
    """The family graph plus any ``extra`` Turtle files; a fresh graph on every call.

    The family graph is every canonical module with its generated annotations, so labels,
    definitions and scope notes are present whichever file states them.
    """
    graph = _family_graph(family_file_paths())
    extra = list(extra)
    if extra:
        graph += load(extra)
    return graph


def shapes() -> Graph:
    """The family's shapes graph; a fresh graph on every call."""
    return _family_graph(family_file_paths())


def shapes_of(files: Iterable[str]) -> Graph:
    """The shapes graph of the given family files (repository-relative paths); a fresh graph."""
    return load(files)


def context_and_shapes(files: Iterable[str]) -> tuple[Graph, Graph]:
    """Two separate graphs of ``files``: one to add a case's triples to, one to give pySHACL as shapes.

    They must not be one object. pySHACL writes :data:`PYSHACL_AXIOMS` into whatever graph it is
    handed as shapes; if that graph is then also the ontology context of the next case's data,
    ``sh:class rdf:Property`` begins to accept an ``owl:DatatypeProperty`` there -- an inference
    nobody asked for, present for every case but the first, so that a verdict could depend on
    the order the cases run in. The first graph is never given to pySHACL as shapes and stays
    what the files say; copy it into each data graph (``context + case``).
    """
    files = list(files)
    return shapes_of(files), shapes_of(files)


def pyshacl_axioms_in(graph: Graph) -> list[tuple[URIRef, URIRef, URIRef]]:
    """The axioms pySHACL adds to shapes graphs that ``graph`` holds (none, for a graph kept as data)."""
    return [axiom for axiom in PYSHACL_AXIOMS if axiom in graph]
