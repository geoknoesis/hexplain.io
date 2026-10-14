"""The emitted-instance competency corpus check, shared by the instance and release-contract gates.

Each corpus row names a case, the aspect module whose targets select the shapes, the expected
verdict, the result path a rejection must report and the base64 Turtle of the instance data.
The same corpus is executed by Apache Jena in the engine.

A row is not validated against the whole family. The modules it involves are selected from its
own triples (tools/_module_selection.py; CONTRIBUTING.md, "A gate that validates small cases does
not load the family for each of them"), together with the named aspect module and its imports;
they are the data context and the shapes. Of those shapes, only the targets the aspect module
states stay active, so the row is checked by that module's shapes, which may still reach the
others through ``sh:node`` and the like.
"""

from __future__ import annotations

import base64
from pathlib import Path

from _family import is_documentation
from _module_selection import Index, index_of
from pyshacl import validate
from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")
TARGETS = [SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf]


class Modules:
    """The canonical Turtle modules among ``files`` (path -> text), each parsed once."""

    def __init__(self, files: dict[str, str]) -> None:
        self.graphs = {
            path: Graph().parse(data=text, format="turtle")
            for path, text in files.items()
            if path.endswith(".ttl") and not is_documentation(path)
        }
        self.index: Index = index_of(self.graphs)

    def selected(self, data: Graph, aspect: str) -> list[str]:
        """The modules ``data`` involves, plus ``aspect`` and everything it imports, in index order."""
        wanted = set(self.index.used_by(data)) | set(self.index.closed(set(self.index.declared[aspect])))
        return [path for path in self.index.declared if path in wanted]

    def load(self, paths: list[str]) -> Graph:
        """A fresh graph of ``paths``."""
        graph = Graph()
        for path in paths:
            graph += self.graphs[path]
        return graph


def check_corpus(files: dict[str, str], corpus: str) -> int:
    """Validate every corpus row against the modules it involves, with only the named module's targets active.

    ``files`` maps each family file path to its Turtle text, so an archived release can supply
    its own copies. Returns the number of rows checked; raises AssertionError on the first
    disagreement.
    """
    modules = Modules(files)
    count = 0
    for line in corpus.splitlines():
        if not line or line.startswith("#"):
            continue
        name, module, expected, path, encoded = line.split("\t")
        stem = Path(module).stem
        aspect = f"specification/aspect/{stem}/{stem}.ttl"
        data = Graph().parse(data=base64.b64decode(encoded).decode(), format="turtle")
        selected = modules.selected(data, aspect)
        # Two graphs: pySHACL writes axioms into its shapes graph (specgraph.context_and_shapes).
        context, shapes = modules.load(selected), modules.load(selected)
        for pred in TARGETS:
            for s, o in list(shapes.subject_objects(pred)):
                if (s, pred, o) not in modules.graphs[aspect]:
                    shapes.remove((s, pred, o))
        actual, report, detail = validate(context + data, shacl_graph=shapes, inference="none", advanced=True)
        assert bool(actual) == (expected == "true"), (name, detail)
        if path:
            assert URIRef(path) in set(report.objects(None, SH.resultPath)), (name, detail)
        count += 1
    return count
