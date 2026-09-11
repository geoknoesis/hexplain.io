"""Canonical ontology and shape loading through specification/family.json."""
from pathlib import Path
from _family import family_paths, load
ROOT = Path(__file__).resolve().parents[1]
def ontology_paths():
    return [Path(p).relative_to(ROOT).as_posix() for p in family_paths(ROOT / "specification")]
def shape_paths(): return ontology_paths()
def ontologies(extra=()): return load([*ontology_paths(), *extra])
def shapes(): return load(shape_paths())
