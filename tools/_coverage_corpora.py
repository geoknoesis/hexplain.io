"""The corpora the constraint ledger is measured over, cut into tasks a process pool can run.

A task is a slice of one corpus. Running it validates the slice's cases with pySHACL's constraint
evaluation traced, and returns which inventoried obligation was evaluated by which case and how.
Tasks share nothing but the read-only canonical graphs each worker is initialised with, so the
ledger is the same whatever order they finish in: :func:`tasks` fixes the order they are listed
in, the caller merges results in that order, and every list in the ledger is sorted.

No case is validated against the whole family. A case that needs ontology context (a class
hierarchy, a register concept) gets the modules its own terms belong to and what they import
(``specgraph.modules_used_by``): those modules' triples are added to the data graph and their
shapes are the shapes graph. The family's other modules never mention the case's terms; with
them in the data graph every call re-evaluated their shapes against their own individuals and
booked the result to whichever case happened to be running, which was most of the ledger's bulk
and most of the forty minutes it took to measure.
"""

from __future__ import annotations

import base64
import json
import runpy
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pyshacl
import specgraph
from pyshacl.constraints import ALL_CONSTRAINT_COMPONENTS
from rdflib import Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "specification/validation"
SH = Namespace("http://www.w3.org/ns/shacl#")
TARGETS = [SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf]
#: How an evaluation is booked: the constraint reported a violation, passed on values, or had none.
FIELDS = ("passed", "failed", "empty_value_passes")
FAMILY_CONTRACTS = "specification/validation/test/family-contracts.json"
SECURITY_PROFILE = "specification/validation/test/security-profile.ttl"
#: Corpora validated against a fixed selection of modules, with the case's own triples as data.
SELECTIONS: dict[str, list[str]] = {
    "layout-competency.tsv": ["specification/dlv/dlv.ttl", "specification/aspect/bundle/bundle.ttl"],
    "security-competency.tsv": [SECURITY_PROFILE],
    "geometry-competency.tsv": ["specification/aspect/geometry/geometry.ttl"],
    "spatialref-competency.tsv": ["specification/aspect/spatialref/spatialref.ttl"],
    "core-mapping-competency.tsv": ["specification/hexplain/core.ttl"],
    "network-competency.tsv": ["specification/npv/net.ttl"],
    "conformance-competency.tsv": [
        "specification/conf/conf.ttl",
        "specification/conf/shapes.ttl",
        "specification/req/req.ttl",
        "specification/req/shapes.ttl",
        "specification/fn/fn.ttl",
    ],
}
#: Procedural semantic gates traced as they run; their own assertions, exact arithmetic included, still hold.
PROCEDURAL = ["tools/test_geospatial_model.py", "tools/test_video_math.py", "tools/test_numeric_boundaries.py"]
#: Cases per task, by corpus: enough to amortise a task's setup, few enough to spread across workers.
CHUNK = {"family-contracts": 60, "selection": 80, "competency": 6, "fixtures": 6}

#: An obligation's identity: the shape node and the constraint component.
Key = tuple[str, str]
#: Evaluations by obligation: for each way of being booked, the cases that did.
Rows = dict[Key, dict[str, list[str]]]
#: One booked evaluation, as a worker returns it: (shape, component, field, case name).
Evaluation = tuple[str, str, str, str]


@dataclass(frozen=True)
class Task:
    """A slice of one corpus: ``items`` are row indices or fixture paths, ``source`` the corpus file or gate."""

    corpus: str
    source: str
    items: tuple[Any, ...] = ()


@dataclass
class Tracer:
    """What one task observed: the case being validated now, and the validation calls made."""

    rows: Rows
    current: list[str] = field(default_factory=lambda: [""])
    cases: int = 0


@contextmanager
def trace(rows: Rows, current: list[str]) -> Iterator[None]:
    """Book every constraint evaluation made inside the block to ``rows`` under ``current[0]``."""
    originals = []
    # pySHACL's component classes, as plain objects: their evaluate methods are replaced for the block.
    components: list[Any] = list(ALL_CONSTRAINT_COMPONENTS)
    for cls in components:
        original = cls.evaluate

        def wrapped(
            self: Any,
            executor: Any,
            target_graph: Any,
            focus_value_nodes: Any,
            evaluation_path: Any,
            _original: Callable[..., Any] = original,
        ) -> Any:
            result = _original(self, executor, target_graph, focus_value_nodes, evaluation_path)
            key = (str(self.shape.node), str(self.shacl_constraint_component))
            if key in rows and focus_value_nodes:
                booked = (
                    "failed"
                    if not result[0]
                    else ("passed" if any(focus_value_nodes.values()) else "empty_value_passes")
                )
                rows[key][booked].append(current[0])
            return result

        originals.append((cls, original))
        cls.evaluate = wrapped
    try:
        yield
    finally:
        for cls, original in originals:
            cls.evaluate = original


@contextmanager
def replaced(module: ModuleType, name: str, value: object) -> Iterator[None]:
    """Replace a module-level name for the block, and put the original back whatever happens."""
    namespace = vars(module)
    original = namespace[name]
    namespace[name] = value
    try:
        yield
    finally:
        namespace[name] = original


class Corpora:
    """The canonical graphs and the corpus tasks run against them (one instance per worker process)."""

    def __init__(self, graphs: dict[str, Graph], keys: Iterable[Key]) -> None:
        self.graphs = graphs
        self.keys = list(keys)
        # pySHACL writes axioms of its own into any graph it is given as shapes
        # (specgraph.PYSHACL_AXIOMS). As data those axioms change what sh:class accepts, so a graph
        # has one role for life: ``graphs`` and ``_contexts`` are only ever copied into data graphs,
        # ``_shapes`` only ever handed to pySHACL. assert_pristine() checks the first two after every task.
        self._contexts: dict[tuple[str, ...], Graph] = {}
        self._shapes: dict[tuple[str, ...], Graph] = {}
        #: pySHACL's axioms that a measured file states itself (none today); those are not leaks.
        self._stated = {axiom for graph in graphs.values() for axiom in specgraph.pyshacl_axioms_in(graph)}

    def assert_pristine(self) -> None:
        """No shared graph has acquired pySHACL's axioms: every case saw the files as they are written."""
        for name, graph in [*self.graphs.items(), *((" + ".join(k), g) for k, g in self._contexts.items())]:
            leaked = [axiom for axiom in specgraph.pyshacl_axioms_in(graph) if axiom not in self._stated]
            assert not leaked, f"pySHACL's axioms reached the shared graph of {name}: {leaked}"

    def union(self, files: Iterable[str]) -> Graph:
        """One fresh graph of the canonical graphs of ``files``."""
        merged = Graph()
        for path in files:
            merged += self.graphs[path]
        return merged

    def files_for(self, data: Graph, also: Iterable[str] = ()) -> tuple[str, ...]:
        """The modules ``data`` is written in terms of, with their imports, plus the files ``also`` names."""
        return tuple(sorted(set(specgraph.modules_used_by(data)) | set(also)))

    def context(self, files: tuple[str, ...]) -> Graph:
        """``files`` as ontology context for data graphs: one shared graph per selection, never given as shapes."""
        if files not in self._contexts:
            self._contexts[files] = self.union(files)
        return self._contexts[files]

    def shapes(self, files: tuple[str, ...]) -> Graph:
        """``files`` as a shapes graph: one shared graph per selection, never copied into data."""
        if files not in self._shapes:
            self._shapes[files] = self.union(files)
        return self._shapes[files]

    def check(
        self,
        tracer: Tracer,
        name: str,
        data: Graph,
        shapes: Graph,
        expected: bool,
        path: str = "",
        expected_shape: str = "",
        allow_warnings: bool = False,
        severity: str = "",
    ) -> None:
        """Validate one case, traced under ``name``, and hold it to the corpus's retained expectation."""
        tracer.current[0] = name
        # allow_warnings mirrors test_family_contract: a case measures one obligation, so an
        # advisory result from an unrelated shape must not decide it. Cases that are themselves
        # about an advisory result pass allow_warnings=False and assert the severity.
        ok, report, detail = pyshacl.validate(
            data, shacl_graph=shapes, inference="none", advanced=True, allow_warnings=allow_warnings
        )
        assert bool(ok) == expected, (name, detail)
        if path:
            assert URIRef(path) in report.objects(None, SH.resultPath), (name, detail)
        if expected_shape:
            assert URIRef(expected_shape) in report.objects(None, SH.sourceShape), (name, detail)
        if severity:
            assert URIRef(severity) in report.objects(None, SH.resultSeverity), (name, detail)
        tracer.cases += 1

    def family_contracts(self, tracer: Tracer, task: Task) -> None:
        """Authored module contracts: the case's triples against its one module's shapes."""
        rows = json.loads((ROOT / FAMILY_CONTRACTS).read_text(encoding="utf-8"))
        for index in task.items:
            row = rows[index]
            selected = self.shapes((row["module"],))
            if row.get("targetShape"):
                selected = Graph() + selected
                selected.add((URIRef(row["targetShape"]), SH.targetNode, URIRef(row["targetNode"])))
            self.check(
                tracer,
                "family-contracts:" + row["name"],
                Graph().parse(data=row["data"], format="turtle"),
                selected,
                row["expected"],
                row["path"],
                row.get("expectedShape", ""),
                bool(row.get("allowWarnings")),
                row.get("severity", ""),
            )

    def selection(self, tracer: Tracer, task: Task) -> None:
        """A four-column corpus against its fixed module selection."""
        shapes = self.union(SELECTIONS[task.source])
        lines = corpus_lines(task.source)
        for index in task.items:
            name, expected, path, encoded = lines[index].split("\t")
            data = Graph().parse(data=base64.b64decode(encoded), format="turtle")
            self.check(tracer, task.source + ":" + name, data, shapes, expected == "true", path)

    def competency(self, tracer: Tracer, task: Task) -> None:
        """The aspect competency corpus: only the named module's shapes are aimed at the case.

        The context is the modules the case is written in terms of and the named module; the other
        modules' targets are removed from the shapes graph so that only the named module's shapes
        decide the verdict, while the shapes they refer to stay available.
        """
        lines = corpus_lines(task.source)
        for index in task.items:
            name, module, expected, path, encoded = lines[index].split("\t")
            stem = Path(module).stem
            own = f"specification/aspect/{stem}/{stem}.ttl"
            case = Graph().parse(data=base64.b64decode(encoded), format="turtle")
            context = self.context(self.files_for(case, [own]))
            shapes = Graph() + context
            for predicate in TARGETS:
                for s, o in list(shapes.subject_objects(predicate)):
                    if (s, predicate, o) not in self.graphs[own]:
                        shapes.remove((s, predicate, o))
            self.check(tracer, "competency.tsv:" + name, context + case, shapes, expected == "true", path)

    def fixtures(self, tracer: Tracer, task: Task) -> None:
        """Vocabulary fixtures: the fixture in the context of the modules it uses and its own module's files."""
        for relative in task.items:
            file = ROOT / relative
            fixture = Graph().parse(file)
            beside = sorted(p.relative_to(ROOT).as_posix() for p in file.parent.parent.glob("*.ttl"))
            files = self.files_for(fixture, [p for p in beside if p in self.graphs])
            shapes = self.shapes(files)
            foreign = [p for p in beside if p not in self.graphs and not specgraph.is_documentation(p)]
            if foreign:
                shapes = Graph() + shapes
                for extra in foreign:
                    shapes.parse(ROOT / extra)
            # A fixture is valid when no result is a Violation (tools/test_vocab_shapes.py), so a
            # -valid fixture may carry the advisory results it declares.
            self.check(
                tracer,
                relative,
                self.context(files) + fixture,
                shapes,
                file.name.endswith("-valid.ttl"),
                allow_warnings=True,
            )

    def procedural(self, tracer: Tracer, task: Task) -> None:
        """Run one procedural gate with its validation calls traced and its shapes the canonical graphs."""
        original_validate = pyshacl.validate
        invocation = [0]

        def tracked_validate(*args: Any, **kwargs: Any) -> Any:
            invocation[0] += 1
            tracer.cases += 1
            tracer.current[0] = f"{task.source}:validation-{invocation[0]}"
            return original_validate(*args, **kwargs)

        # A gate that selects modules gets their canonical graphs, so traced shape identities match
        # the inventory's (a fresh parse would give property shapes other blank-node labels).
        with replaced(specgraph, "shapes_of", self.union), replaced(pyshacl, "validate", tracked_validate):
            # A gate ends by raising SystemExit(main()); a clean exit must not end this measurement
            # with it (it once did, silently, leaving the ledger unwritten), and a failure must.
            try:
                runpy.run_path(str(ROOT / task.source), run_name="__main__")
            except SystemExit as finished:
                if finished.code not in (0, None):
                    raise RuntimeError(f"{task.source} failed while being traced: exit {finished.code}") from finished

    def run(self, task: Task) -> tuple[list[Evaluation], int]:
        """Run one task; returns its booked evaluations and how many validation calls it made."""
        tracer = Tracer({key: {name: [] for name in FIELDS} for key in self.keys})
        handler: Callable[[Tracer, Task], None] = getattr(self, task.corpus.replace("-", "_"))
        with trace(tracer.rows, tracer.current):
            handler(tracer, task)
        self.assert_pristine()
        booked = [
            (shape, component, name, case)
            for (shape, component), observed in tracer.rows.items()
            for name in FIELDS
            for case in observed[name]
        ]
        return booked, tracer.cases


def corpus_lines(filename: str) -> list[str]:
    """The case lines of a tab-separated corpus under validation/test/, comments and blanks dropped."""
    text = (OUT / "test" / filename).read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def fixture_paths() -> list[str]:
    """Every vocabulary fixture, at either module depth, as sorted repository-relative paths."""
    return sorted(
        path
        for depth in ("specification/*/test/", "specification/*/*/test/")
        for suffix in ("*-valid.ttl", "*-invalid.ttl")
        for path in specgraph.glob(depth + suffix)
    )


def _chunks(corpus: str, source: str, items: list[Any]) -> Iterator[Task]:
    size = CHUNK[corpus]
    for start in range(0, len(items), size):
        yield Task(corpus, source, tuple(items[start : start + size]))


def tasks() -> list[Task]:
    """Every task of the measurement, in the fixed order the corpora are listed in."""
    planned: list[Task] = []
    contracts = json.loads((ROOT / FAMILY_CONTRACTS).read_text(encoding="utf-8"))
    planned.extend(_chunks("family-contracts", FAMILY_CONTRACTS, list(range(len(contracts)))))
    for filename in SELECTIONS:
        planned.extend(_chunks("selection", filename, list(range(len(corpus_lines(filename))))))
    planned.extend(_chunks("competency", "competency.tsv", list(range(len(corpus_lines("competency.tsv"))))))
    planned.extend(_chunks("fixtures", "fixtures", fixture_paths()))
    planned.extend(Task("procedural", source) for source in PROCEDURAL)
    return planned


_WORKER: Corpora | None = None


def initialise(graphs: dict[str, Graph], keys: list[Key]) -> None:
    """Pool initialiser: give this worker process the canonical graphs and the obligation keys."""
    global _WORKER
    _WORKER = Corpora(graphs, keys)


def run_task(task: Task) -> tuple[list[Evaluation], int]:
    """Run one task in an initialised worker process."""
    assert _WORKER is not None, "the worker was not initialised"
    return _WORKER.run(task)
