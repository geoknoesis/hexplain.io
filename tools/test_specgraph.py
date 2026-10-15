"""The family cache stays bounded, and module selection keeps every shape that could report on a case.

tools/specgraph.py caches the parsed family as a pickle per source digest: the cache directory
must not grow without bound and a failed write must leave nothing behind.

tools/_module_selection.py decides which modules a small validation case is validated with.
Leaving a module out is only sound if none of its shapes could have had one of the case's nodes
as a focus node, so the selection is checked against the family itself: for every explicit
target any module declares, a one-triple case that the target would select must bring that
module in; imports and shapes-only companions must follow; and the only custom targets may be
the register-binding ones the selection models. Two real fixtures on which the homes of their
terms alone are not enough are then validated both ways, and the reports must be the same.

A graph given to pySHACL as shapes must not also be the context of a data graph: pySHACL
writes subclass axioms into it that change later verdicts. The check shows the effect on a
shared graph and that ``specgraph.context_and_shapes`` keeps the data side clean.
"""

from __future__ import annotations

import os
import tempfile
from collections import Counter
from pathlib import Path

import _module_selection as selection
import specgraph
from pyshacl import validate
from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.term import Node

SH = Namespace("http://www.w3.org/ns/shacl#")
EX = Namespace("urn:specgraph-test:")
#: Fixtures validated both against their selection and against the whole family.
SAMPLE = 2


def check_prune(directory: Path) -> None:
    """Only the newest pickles survive, and abandoned temporary files go; fresh ones are left alone."""
    now = 1_000_000.0
    for age, name in enumerate(["e", "d", "c", "b", "a"]):  # "e" is the newest
        path = directory / f"family-{name}.pickle"
        path.write_bytes(b"x")
        os.utime(path, (now - age * 60, now - age * 60))
    stale, fresh = directory / "family-old.123.tmp", directory / "family-new.456.tmp"
    for path, age in ((stale, specgraph.STALE_TEMPORARY + 1), (fresh, 5)):
        path.write_bytes(b"x")
        os.utime(path, (now - age, now - age))
    removed = specgraph.prune_cache(directory, now=now)
    assert sorted(p.name for p in removed) == ["family-a.pickle", "family-b.pickle", "family-old.123.tmp"], removed
    left = sorted(p.name for p in directory.iterdir())
    assert left == ["family-c.pickle", "family-d.pickle", "family-e.pickle", "family-new.456.tmp"], left
    assert specgraph.CACHE_KEEP == 3
    assert specgraph.prune_cache(directory, now=now) == [], "a second prune removed something"


def check_store(directory: Path) -> None:
    """A write that cannot complete raises and leaves no temporary file; a good one prunes."""
    blocked = directory / "blocked.pickle"
    blocked.mkdir()  # The atomic replace cannot overwrite a directory.
    try:
        specgraph._store(blocked, ("payload",))
        raise AssertionError("replaced a directory with the cache file")
    except OSError:
        pass
    assert not list(directory.glob("*.tmp")), list(directory.glob("*.tmp"))
    blocked.rmdir()
    for name in ["one", "two", "three", "four"]:
        specgraph._store(directory / f"{name}.pickle", (name,))
    assert len(list(directory.glob("*.pickle"))) == specgraph.CACHE_KEEP, sorted(directory.iterdir())
    assert not list(directory.glob("*.tmp"))


def one_triple(s: Node, p: Node, o: Node) -> Graph:
    graph = Graph()
    graph.add((s, p, o))
    return graph


def about(node: Node) -> Graph:
    """A case that states something of ``node``."""
    return one_triple(node, EX.p, EX.o)


def referring(node: Node) -> Graph:
    """A case in which ``node`` is the value of a statement."""
    return one_triple(EX.s, EX.p, node)


def check_targets() -> int:
    """Every explicit target of every module selects that module for a case the target would reach."""
    checked = 0
    family = specgraph.shapes_of(specgraph.ontology_paths())
    for path in selection.canonical_paths():
        module = Graph().parse(specgraph.ROOT / path, format="turtle")
        probes: list[tuple[str, Graph]] = []
        for target in module.objects(None, SH.targetSubjectsOf):
            probes.append((f"subject of {target}", one_triple(EX.s, target, EX.o)))
        for target in module.objects(None, SH.targetObjectsOf):
            probes.append((f"object of {target}", one_triple(EX.s, target, EX.o)))
        for target in module.objects(None, SH.targetNode):
            probes.append((f"node {target}", one_triple(target, EX.p, EX.o)))
        for target in module.objects(None, SH.targetClass):
            probes.append((f"instance of {target}", one_triple(EX.s, RDF.type, target)))
            # ... and an instance of a class the family, or the case itself, puts under the target.
            for sub in module.subjects(RDFS.subClassOf, target):
                probes.append((f"instance of {sub}, a subclass of {target}", one_triple(EX.s, RDF.type, sub)))
            local = one_triple(EX.s, RDF.type, EX.Local)
            local.add((EX.Local, RDFS.subClassOf, target))
            probes.append((f"instance of a case-local subclass of {target}", local))
            # ... and a term the family itself types with the target, once a case says anything of it.
            for instance in sorted(family.subjects(RDF.type, target), key=str)[:3]:
                probes.append((f"statement about {instance}, which the family types {target}", about(instance)))
                probes.append((f"reference to {instance}, which the family types {target}", referring(instance)))
        for shape in module.subjects(RDF.type, SH.NodeShape):
            if (shape, RDF.type, RDFS.Class) in module or (shape, RDF.type, OWL.Class) in module:
                probes.append((f"instance of {shape}, a shape that is a class", one_triple(EX.s, RDF.type, shape)))
        for name, case in probes:
            assert path in specgraph.modules_used_by(case), f"{path} aims a shape at a {name} but is not selected"
            checked += 1
    return checked


def check_closure() -> None:
    """Imports follow transitively, shapes-only companions come with their vocabulary, strangers stay out."""
    index = selection.index()
    file_of = {ontology: path for path, declared in index.declared.items() for ontology in declared}
    for ontology, namespace in index.namespace.items():
        if not namespace:
            # A shapes-only ontology: selected with each family vocabulary it imports.
            for imported in index.imports[ontology] & set(file_of):
                if index.namespace[imported]:
                    selected = specgraph.modules_for([index.namespace[imported]])
                    assert file_of[ontology] in selected, f"{file_of[ontology]} does not follow {file_of[imported]}"
            continue
        closure = set(specgraph.modules_for([namespace]))
        assert file_of[ontology] in closure, (namespace, closure)
        for imported in index.imports[ontology] & set(file_of):
            assert file_of[imported] in closure, f"{file_of[ontology]} imports {file_of[imported]}, not selected"
            # Transitively: whatever the import selects, the importer selects.
            if index.namespace[imported]:
                assert set(specgraph.modules_for([index.namespace[imported]])) <= closure, (namespace, imported)
    assert specgraph.modules_used_by(one_triple(EX.s, EX.p, EX.o)) == [], "a case with no family term selected modules"
    assert specgraph.namespaces_in(one_triple(EX.s, EX.p, EX.o)) == set()
    assert specgraph.modules_for(["urn:not-a-family-namespace#"]) == []
    assert specgraph.family_namespaces() == {n for n in index.namespace.values() if n}


def check_custom_targets() -> int:
    """The only custom targets are register-binding selections, which the selection models."""
    count = 0
    for path in selection.canonical_paths():
        module = Graph().parse(specgraph.ROOT / path, format="turtle")
        for shape, target in module.subject_objects(SH.target):
            select = str(module.value(target, SH.select) or "")
            if shape in selection.SUBJECTS_OF_TARGETS:
                # Each UNION branch binds ?this as a subject of the listed property.
                local = str(selection.SUBJECTS_OF_TARGETS[shape]).rsplit("#", 1)[-1]
                branches = select.count("UNION") + 1
                assert select.count(f"?this req:{local} ") == branches, f"{path}: {shape} selects beyond {local}"
                count += 1
                continue
            assert (target, RDF.type, SH.SPARQLTarget) in module and "hexplain:forProperty" in select, (
                f"{path}: {shape} has a custom target tools/_module_selection.py does not model; "
                "teach Index.aimed_at what it selects before relying on module selection"
            )
            assert path in selection.index().custom
            count += 1
    for bound, files in selection.index().binders.items():
        selected = set(specgraph.modules_used_by(one_triple(EX.s, bound, EX.o)))
        assert files | selection.index().custom <= selected, f"a case using bound property {bound} lacks its binding"
    return count


def results(report: Graph) -> Counter[tuple[str, ...]]:
    """A validation report as a multiset of (focus, path, component, severity, named source shape)."""
    rows: Counter[tuple[str, ...]] = Counter()
    for result in report.subjects(SH.resultSeverity, None):
        shape = report.value(result, SH.sourceShape)
        rows[
            (
                str(report.value(result, SH.focusNode)),
                str(report.value(result, SH.resultPath)),
                str(report.value(result, SH.sourceConstraintComponent)),
                str(report.value(result, SH.resultSeverity)),
                str(shape) if isinstance(shape, URIRef) else "blank",
            )
        ] += 1
    return rows


def check_equivalence() -> list[str]:
    """Fixtures whose selection needs more than their terms' homes report the same either way."""
    family, family_shapes = specgraph.context_and_shapes(specgraph.ontology_paths())
    fixtures = sorted(
        path
        for depth in ("specification/*/test/", "specification/*/*/test/")
        for path in specgraph.glob(depth + "*-invalid.ttl")
    )
    sampled = []
    for path in fixtures:
        data = specgraph.load([path])
        files = specgraph.modules_used_by(data)
        if set(files) <= set(specgraph.modules_for(specgraph.namespaces_in(data))):
            continue  # The homes of its terms already select everything: no aimed-in module to prove.
        context, shapes = specgraph.context_and_shapes(files)
        narrow = validate(context + data, shacl_graph=shapes, inference="none", advanced=True)
        whole = validate(family + data, shacl_graph=family_shapes, inference="none", advanced=True)
        assert bool(narrow[0]) == bool(whole[0]), f"{path}: verdict differs between its selection and the family"
        assert results(narrow[1]) == results(whole[1]), (
            f"{path}: validated with its {len(files)} selected modules it reports differently than with the family",
            sorted((results(whole[1]) - results(narrow[1])).elements()),
            sorted((results(narrow[1]) - results(whole[1])).elements()),
        )
        sampled.append(path)
        if len(sampled) == SAMPLE:
            break
    assert len(sampled) == SAMPLE, f"expected {SAMPLE} fixtures whose selection includes an aimed-in module: {sampled}"
    return sampled


def check_shapes_stay_out_of_data() -> None:
    """The graph a case's data is built from never acquires the axioms pySHACL writes into shapes graphs."""
    probe_shapes = Graph().parse(
        data="""@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
<urn:specgraph-test:Shape> a sh:NodeShape ; sh:targetNode <urn:specgraph-test:p> ; sh:class rdf:Property .""",
        format="turtle",
    )
    case = Graph().parse(
        data="""@prefix owl: <http://www.w3.org/2002/07/owl#> .
<urn:specgraph-test:p> a owl:DatatypeProperty .""",
        format="turtle",
    )
    # What goes wrong when one graph is both: after the first call it holds pySHACL's axioms, and
    # as data they make an owl:DatatypeProperty an rdf:Property -- the second verdict differs.
    both = Graph() + probe_shapes
    first = validate(both + case, shacl_graph=both, inference="none")[0]
    second = validate(both + case, shacl_graph=both, inference="none")[0]
    assert (first, second) == (False, True), (
        "pySHACL no longer leaks its axioms through a shared shapes graph; context_and_shapes may be simplified",
        first,
        second,
    )
    assert specgraph.pyshacl_axioms_in(both) == list(specgraph.PYSHACL_AXIOMS)
    # context_and_shapes keeps the two apart, so every call gives the first verdict.
    files = specgraph.modules_for(sorted(specgraph.family_namespaces())[:1])
    context, shapes = specgraph.context_and_shapes(files)
    assert context is not shapes and len(context) == len(shapes) > 0
    verdicts = [validate(context + case, shacl_graph=shapes + probe_shapes, inference="none")[0] for _ in range(2)]
    for _ in range(2):
        validate(context + case, shacl_graph=shapes, inference="none")
    assert specgraph.pyshacl_axioms_in(context) == [], "the data-side context acquired pySHACL's axioms"
    assert specgraph.pyshacl_axioms_in(shapes) == list(specgraph.PYSHACL_AXIOMS)
    assert verdicts == [False, False], verdicts


def main() -> int:
    check_shapes_stay_out_of_data()
    with tempfile.TemporaryDirectory() as temp:
        check_prune(Path(temp))
    with tempfile.TemporaryDirectory() as temp:
        check_store(Path(temp))
    targets = check_targets()
    check_closure()
    custom = check_custom_targets()
    sampled = check_equivalence()
    print(
        f"PASS: the family cache keeps {specgraph.CACHE_KEEP} pickles and no abandoned temporary file; "
        f"{targets} target probes each select the module that aims at them; imports and shapes-only companions "
        f"follow; {custom} custom targets of a modelled kind; {len(sampled)} fixtures report "
        "identically with their selected modules and with the whole family"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
