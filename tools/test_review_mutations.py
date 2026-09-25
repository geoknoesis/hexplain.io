"""The shapes reject every defect the 2026-09-24 ontology review found, and accept the fixes.

Each probe in tools/_review_mutation_cases.py is one mutation of a conforming graph and the
verdict the named shapes must reach on it. A probe with a severity expects the graph to be
reported at that severity only (a retired register value is reported as a warning, not
rejected). `--root DIR` runs the probes against the shapes of another checkout and reports
the ones it gets wrong instead of failing, which is how the review's before/after counts were
measured; `--list` prints every probe.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _review_mutation_cases import cases  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SH = Namespace("http://www.w3.org/ns/shacl#")


def load(root, paths):
    g = Graph()
    for p in paths:
        path = root / p
        if path.is_file():
            g.parse(data=path.read_text(encoding="utf-8"), format="turtle")
    return g


def _check(task):
    """Validate one chunk of probes against their shapes; return the wrong ones as (index, report)."""
    root, items = task
    shapes, wrong = {}, []
    for index, row in items:
        key = tuple(row["shapes"])
        if key not in shapes:
            shapes[key] = load(root, row["shapes"])
        data = Graph().parse(data=row["data"], format="turtle")
        ok, report, text = validate(data, shacl_graph=shapes[key], inference="none", advanced=True)
        severities = set(report.objects(None, SH.resultSeverity))
        if row.get("severity"):
            good = not ok and severities == {URIRef(row["severity"])}
        else:
            good = bool(ok) == row["conforms"]
        if not good:
            wrong.append((index, text))
    return wrong


def run(root, chunk=8):
    """Every probe, across worker processes (SPARQL-based shapes are slow in pySHACL)."""
    import os
    from concurrent.futures import ProcessPoolExecutor
    rows = cases()
    indexed = list(enumerate(rows))
    tasks = [(root, indexed[i:i + chunk]) for i in range(0, len(indexed), chunk)]
    workers = max(1, min(os.cpu_count() or 1, int(os.environ.get("HEXPLAIN_GATE_WORKERS", "8"))))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        wrong = sorted(w for result in pool.map(_check, tasks) for w in result)
    return rows, [(rows[i], text) for i, text in wrong]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", help="measure another checkout's shapes instead of this one's")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    root = Path(args.root) if args.root else ROOT
    rows, wrong = run(root)
    groups = Counter(r["group"] for r in rows)
    if args.list or args.root:
        missed = Counter(r["group"] for r, _ in wrong)
        for group, total in groups.items():
            print(f"{group}: {total - missed[group]}/{total} correct")
        for row, _ in wrong:
            print(f"  WRONG [{row['group']}] {row['name']} (expected {'conforms' if row['conforms'] else 'rejected'})")
        print(f"{len(rows) - len(wrong)}/{len(rows)} probes correct against {root}")
        return 0
    if wrong:
        print("FAIL:\n  " + "\n  ".join(f"[{r['group']}] {r['name']}: expected "
                                        f"{'conforms' if r['conforms'] else 'rejected'}\n{t[:1200]}" for r, t in wrong))
        return 1
    print(f"PASS: {len(rows)} review mutation probes ({', '.join(f'{g} {n}' for g, n in groups.items())}) "
          "reach the expected verdict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
