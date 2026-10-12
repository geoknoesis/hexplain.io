"""The emitted-instance competency corpus check, shared by the instance and release-contract gates.

Each corpus row names a case, the aspect module whose targets select the shapes, the expected
verdict, the result path a rejection must report and the base64 Turtle of the instance data.
The same corpus is executed by Apache Jena in the engine.
"""

from __future__ import annotations

import base64
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")
TARGETS = [SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf]


def check_corpus(family: Graph, files: dict[str, str], corpus: str) -> int:
    """Validate every corpus row against ``family`` with only the selected module's targets active.

    ``files`` maps each family file path to its Turtle text, so an archived release can supply
    its own copies. Returns the number of rows checked; raises AssertionError on the first
    disagreement.
    """
    count = 0
    for line in corpus.splitlines():
        if not line or line.startswith("#"):
            continue
        name, module, expected, path, encoded = line.split("\t")
        stem = Path(module).stem
        selected = files[f"specification/aspect/{stem}/{stem}.ttl"]
        selected_graph = Graph().parse(data=selected, format="turtle")
        shapes = Graph() + family
        for pred in TARGETS:
            for s, o in list(shapes.subject_objects(pred)):
                if (s, pred, o) not in selected_graph:
                    shapes.remove((s, pred, o))
        data = Graph().parse(data=base64.b64decode(encoded).decode(), format="turtle")
        actual, report, detail = validate(family + data, shacl_graph=shapes, inference="none", advanced=True)
        assert bool(actual) == (expected == "true"), (name, detail)
        if path:
            assert URIRef(path) in set(report.objects(None, SH.resultPath)), (name, detail)
        count += 1
    return count
