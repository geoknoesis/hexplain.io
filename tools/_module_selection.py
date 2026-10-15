"""Which modules of the family a small validation case needs, and no others.

pySHACL pays for every shape in the shapes graph, and every SPARQL constraint for every triple
of the data graph, on every call. A ten-triple case validated against the forty modules of the
family costs seconds; against the modules it actually involves, milliseconds. "Involves" is
decided from the case's own triples, in three steps, so that every shape which could report on
one of the case's nodes is still there:

1. *Homes*: the modules whose namespace one of the case's IRIs falls in.
2. *Aim*: the modules with a shape aimed at something the case states -- ``sh:targetClass`` of a
   class the case types a node with (or a superclass of it), ``sh:targetSubjectsOf`` /
   ``sh:targetObjectsOf`` of a property the case uses, ``sh:targetNode`` of a node it mentions,
   and an implicit class target likewise. A term of the family that the case mentions (a
   register concept, a class) keeps the types the family gives it, so a shape aimed at one of
   those classes is kept too: the case may be saying something about that term. The family's only
   custom (SPARQL) targets are of two kinds. The register-binding shapes select the subjects of a
   property that some ``hexplain:RegisterBinding`` binds; a case using a bound property therefore
   brings in the module that binds it, the module that holds those shapes, and the home of the
   bound register. A shape in :data:`SUBJECTS_OF_TARGETS` selects a subset of the subjects of one
   property, so it is aimed as ``sh:targetSubjectsOf`` that property would be.
   tools/test_specgraph.py fails if a custom target of another kind appears, because this step
   would not know what it selects, and checks that every branch of a listed shape's selection binds
   ``?this`` through its property.
3. *Imports*: everything those modules ``owl:import``, transitively; and with any vocabulary, a
   shapes-only ontology that imports it and claims no namespace of its own (conf/shapes.ttl for
   conf.ttl): those shapes are that vocabulary's.

What is left out is every module that neither names nor targets anything in the case. With the
whole family in the data graph such a module's shapes were evaluated against its own
individuals on every call; nothing the case said could change their result.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from _family import family_paths, is_documentation
from rdflib import OWL, RDF, RDFS, Graph, Namespace, URIRef
from rdflib.term import Node

ROOT = Path(__file__).resolve().parents[1]
VANN_URI = URIRef("http://purl.org/vocab/vann/preferredNamespaceUri")
SH = Namespace("http://www.w3.org/ns/shacl#")
HEXPLAIN = Namespace("https://hexplain.io/ns/core#")

#: Files by the term a shape of theirs is aimed at.
Aim = dict[Node, set[str]]

#: Shapes whose SPARQL target selects only subjects of the property given (a subset of what
#: sh:targetSubjectsOf would select): req:RequirementIdentityShape narrows the subjects of
#: req:requirementId to those that can have a twin.
SUBJECTS_OF_TARGETS: dict[Node, URIRef] = {
    URIRef("https://hexplain.io/ns/req#RequirementIdentityShape"): URIRef("https://hexplain.io/ns/req#requirementId"),
}


def canonical_paths() -> list[str]:
    """Every canonical module of the family, as a path relative to the repository root."""
    paths = [Path(p).relative_to(ROOT).as_posix() for p in family_paths(ROOT / "specification")]
    return [p for p in paths if not is_documentation(p)]


@dataclass
class Index:
    """What each module declares, imports and aims its shapes at; built once per process."""

    declared: dict[str, frozenset[URIRef]] = field(default_factory=dict)
    namespace: dict[URIRef, str] = field(default_factory=dict)
    imports: dict[URIRef, frozenset[URIRef]] = field(default_factory=dict)
    subjects_of: Aim = field(default_factory=dict)
    objects_of: Aim = field(default_factory=dict)
    classes: Aim = field(default_factory=dict)
    nodes: Aim = field(default_factory=dict)
    #: Bound property -> the files that state a register binding for it.
    binders: Aim = field(default_factory=dict)
    #: Bound property -> the registers bound to it.
    registers: dict[Node, set[URIRef]] = field(default_factory=dict)
    #: Files holding a shape with a custom (SPARQL) target.
    custom: set[str] = field(default_factory=set)
    superclasses: dict[Node, set[Node]] = field(default_factory=dict)
    #: Term -> the classes the family types it with.
    types: dict[Node, set[Node]] = field(default_factory=dict)

    def read(self, path: str, graph: Graph) -> None:
        """Record one module file."""
        ontologies = frozenset(s for s in graph.subjects(RDF.type, OWL.Ontology) if isinstance(s, URIRef))
        self.declared[path] = ontologies
        for ontology in ontologies:
            self.namespace[ontology] = str(graph.value(ontology, VANN_URI) or "")
            self.imports[ontology] = frozenset(o for o in graph.objects(ontology, OWL.imports) if isinstance(o, URIRef))
        for predicate, aim in (
            (SH.targetSubjectsOf, self.subjects_of),
            (SH.targetObjectsOf, self.objects_of),
            (SH.targetClass, self.classes),
            (SH.targetNode, self.nodes),
        ):
            for target in graph.objects(None, predicate):
                aim.setdefault(target, set()).add(path)
        for shape in graph.subjects(RDF.type, SH.NodeShape):
            # A node shape that is also a class is aimed at that class's instances.
            if (shape, RDF.type, RDFS.Class) in graph or (shape, RDF.type, OWL.Class) in graph:
                self.classes.setdefault(shape, set()).add(path)
        for shape in graph.subjects(SH.target, None):
            if shape in SUBJECTS_OF_TARGETS:
                self.subjects_of.setdefault(SUBJECTS_OF_TARGETS[shape], set()).add(path)
            else:
                self.custom.add(path)
        for binding, bound in graph.subject_objects(HEXPLAIN.forProperty):
            self.binders.setdefault(bound, set()).add(path)
            registers = self.registers.setdefault(bound, set())
            registers.update(r for r in graph.objects(binding, HEXPLAIN.register) if isinstance(r, URIRef))
        for sub, sup in graph.subject_objects(RDFS.subClassOf):
            self.superclasses.setdefault(sub, set()).add(sup)
        for instance, cls in graph.subject_objects(RDF.type):
            self.types.setdefault(instance, set()).add(cls)

    def homes(self, namespaces: Iterable[str]) -> set[URIRef]:
        """The ontologies claiming ``namespaces``."""
        wanted = set(namespaces)
        return {ontology for ontology, claimed in self.namespace.items() if claimed and claimed in wanted}

    def namespaces_of(self, terms: Iterable[Node]) -> set[str]:
        """The family namespaces the IRIs among ``terms`` fall in."""
        known = [namespace for namespace in self.namespace.values() if namespace]
        found: set[str] = set()
        for term in terms:
            if isinstance(term, URIRef):
                found.update(namespace for namespace in known if term.startswith(namespace))
        return found

    def closed(self, ontologies: set[URIRef]) -> list[str]:
        """The files of ``ontologies``, their transitive imports and the shapes-only companions."""
        selected = set(ontologies)
        todo = list(selected)
        while todo:
            ontology = todo.pop()
            companions = {o for o, claimed in self.namespace.items() if not claimed and ontology in self.imports[o]}
            for linked in self.imports.get(ontology, frozenset()) | companions:
                if linked not in selected:
                    selected.add(linked)
                    todo.append(linked)
        return [path for path, declared in self.declared.items() if declared & selected]

    def aimed_at(self, graphs: Iterable[Graph]) -> tuple[set[str], set[Node]]:
        """Files with a shape aimed at what ``graphs`` state, and the terms that brings into play."""
        predicates: set[Node] = set()
        types: set[Node] = set()
        terms: set[Node] = set()
        local: dict[Node, set[Node]] = {}
        for graph in graphs:
            for s, p, o in graph:
                predicates.add(p)
                terms.update((s, p, o))
                if p == RDF.type:
                    types.add(o)
                elif p == RDFS.subClassOf:
                    local.setdefault(s, set()).add(o)
        for term in terms:
            types |= self.types.get(term, set())
        todo = list(types)
        while todo:
            cls = todo.pop()
            for sup in self.superclasses.get(cls, set()) | local.get(cls, set()):
                if sup not in types:
                    types.add(sup)
                    todo.append(sup)
        files: set[str] = set()
        bound_registers: set[Node] = set()
        for predicate in predicates:
            files |= self.subjects_of.get(predicate, set()) | self.objects_of.get(predicate, set())
            if predicate in self.binders:
                files |= self.binders[predicate] | self.custom
                bound_registers |= self.registers.get(predicate, set())
        for cls in types:
            files |= self.classes.get(cls, set())
        for term in terms:
            files |= self.nodes.get(term, set())
        return files, terms | bound_registers

    def used_by(self, *graphs: Graph) -> list[str]:
        """The files a case involves: its terms' homes, the modules aiming shapes at it, and their imports."""
        aimed, terms = self.aimed_at(graphs)
        ontologies = self.homes(self.namespaces_of(terms))
        # A bound register is named by its ontology IRI, which no namespace prefix matches.
        ontologies |= {term for term in terms if isinstance(term, URIRef) and term in self.namespace}
        for path in aimed:
            ontologies |= self.declared[path]
        selected = set(self.closed(ontologies)) | aimed
        return [path for path in self.declared if path in selected]


@functools.cache
def index() -> Index:
    """The index of the family's canonical modules; each file is parsed once per process."""
    return index_of({path: Graph().parse(ROOT / path, format="turtle") for path in canonical_paths()})


def index_of(graphs: Mapping[str, Graph]) -> Index:
    """An index of the given module files (path -> parsed graph), such as an archived release's."""
    built = Index()
    for path, graph in graphs.items():
        built.read(path, graph)
    return built


def family_namespaces() -> frozenset[str]:
    """Every namespace an ontology of the family claims (``vann:preferredNamespaceUri``)."""
    return frozenset(namespace for namespace in index().namespace.values() if namespace)


def namespaces_in(*graphs: Graph) -> set[str]:
    """The family namespaces the IRIs of ``graphs`` fall in: what the data is written in terms of."""
    return index().namespaces_of({term for graph in graphs for triple in graph for term in triple})


def modules_for(namespaces: Iterable[str]) -> list[str]:
    """The family files whose ontologies claim ``namespaces``, plus everything they owl:import.

    The import closure keeps the selection honest when a module starts depending on another, and
    a shapes-only ontology is selected with any vocabulary it imports (step 3 of the module's
    description). Use :func:`modules_used_by` when the data is at hand: it also finds the modules
    that aim a shape at the data's terms.
    """
    built = index()
    return built.closed(built.homes(namespaces))


def modules_used_by(*graphs: Graph) -> list[str]:
    """The family files a case involves: its terms' homes, the modules aiming shapes at it, and their imports."""
    return index().used_by(*graphs)
