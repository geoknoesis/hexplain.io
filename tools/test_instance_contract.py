"""Shared emitted-instance competency corpus, also executed by Apache Jena in the engine."""

from __future__ import annotations

from pathlib import Path

import specgraph
from _instance_corpus import check_corpus

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "specification/validation/test/competency.tsv"


def main() -> int:
    files = {p: (ROOT / p).read_text(encoding="utf-8") for p in specgraph.ontology_paths()}
    count = check_corpus(files, CORPUS.read_text(encoding="utf-8"))
    print(f"PASS: {count} cross-engine instance contracts, including selected targets and result paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
