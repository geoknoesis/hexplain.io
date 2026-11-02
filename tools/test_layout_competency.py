"""Executable layout and compound-dataset contracts, without inference or rules.

The authored cases (tools/_build_layout_competency.py) are validated against the dlv and bundle
shapes, and the retained corpus (specification/validation/test/layout-competency.tsv) must be
what they render to. The gate only checks; after changing a case, regenerate the corpus with
``python tools/_build_layout_competency.py --write``.
"""

from __future__ import annotations

import sys

from _build_layout_competency import CORPUS, ROOT, cases, render


def main() -> int:
    # The old `--write` habit must not look like a pass that regenerated something.
    assert len(sys.argv) == 1, (
        "this gate takes no arguments and writes nothing; the corpus is written by "
        "`python tools/_build_layout_competency.py --write`"
    )
    rows = cases()
    rendered = render(rows)
    assert CORPUS.read_text(encoding="utf-8") == rendered, (
        f"{CORPUS.relative_to(ROOT).as_posix()} differs from the authored cases; "
        "run `python tools/_build_layout_competency.py --write` after reviewing the change"
    )
    print(f"PASS: {len(rows)} layout/compound cases with inference and rule execution disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
