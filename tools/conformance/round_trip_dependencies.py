"""Prove round-trip exemptions from scoped field identities and encoding dependencies.

Unknown layouts or expressions are compared normally; an unproved dependency never grants
an exemption. Paths use '*' for elements of a repeated struct, rather than matching keys
globally. Encoded child streams have independent stream metadata.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import hel
from rdflib import RDF, Graph, URIRef
from rdflib.term import Node

BDDO = "https://hexplain.io/ns/bddo#"
CORE = "https://hexplain.io/ns/core#"
FieldPath = tuple[str | int, ...]
UNBOUND = object()


def local(term: Node) -> str:
    return str(term).rpartition("#")[2].rpartition("/")[2].rpartition(".")[2]


@dataclass(frozen=True)
class Field:
    term: Node
    path: FieldPath
    scope: FieldPath
    stream: FieldPath
    index: int
    entry_owner: FieldPath | None = None


@dataclass(frozen=True)
class Context:
    lineage: tuple[FieldPath, ...]
    self_path: FieldPath | None = None
    visiting: frozenset[tuple[FieldPath, str]] = frozenset()


class Dependencies:
    def __init__(self, graph: Graph, root: Node, tree: Any = None) -> None:
        self.tree = tree
        self.graph = graph
        self.scopes: dict[FieldPath, list[Field]] = {}
        self.parents: dict[FieldPath, FieldPath] = {}
        self.fields: dict[FieldPath, Field] = {}
        self.positions: dict[FieldPath, int] = {}
        self.arguments: dict[tuple[FieldPath, str], tuple[Field, hel.Node]] = {}
        self.expressions: dict[str, hel.Node | None] = {}
        if isinstance(tree, list):
            for index in range(len(tree)):
                self.walk(root, (index,), (), (), frozenset())
        else:
            self.walk(root, (), (), (), frozenset())
        self.physical = {path for path in self.fields if self.has_byte_extent(path)}
        self.encoded = {p for p, f in self.fields.items() if p in self.physical and self.is_encoded(f.term)}

    def has_byte_extent(self, path: FieldPath) -> bool:
        for length in range(1, len(path) + 1):
            owner = self.fields.get(path[:length])
            if owner is not None and (
                (owner.term, RDF.type, URIRef(BDDO + "LocalBinding")) in self.graph
                or (owner.term, URIRef(BDDO + "valueFromExpression"), None) in self.graph
            ):
                return False
        if self.tree is not None:
            value = self.tree_value(path)
            if value is UNBOUND:
                return False
            if isinstance(value, list) and not value and self.is_repeated(self.fields[path].term):
                return False
        return True

    def is_repeated(self, field: Node) -> bool:
        """Recognize every repetition form, including expression and sentinel bounds."""
        return any(
            (field, URIRef(BDDO + name), None) in self.graph
            for name in ("repeatCount", "repeatCountFromField", "repeatCountFromExpression", "repeatUntil")
        )

    def is_encoded(self, field: Node) -> bool:
        return any(
            (field, URIRef(CORE + name), None) in self.graph
            for name in ("isEncodedWith", "hasEncodingStep", "codecFromExpression")
        )

    def walk(
        self,
        struct: Node,
        scope: FieldPath,
        stream: FieldPath,
        parent: FieldPath,
        ancestors: frozenset[Node],
    ) -> None:
        if struct in ancestors:
            return  # Recursive descriptions are not expanded speculatively.
        heads = list(self.graph.objects(struct, URIRef(BDDO + "hasField")))
        if len(heads) != 1:
            return
        members = list(self.graph.items(heads[0]))
        keys = [local(term) for term in members]
        if len(keys) != len(set(keys)):
            return  # An ambiguous key cannot identify an exempt node.
        self.parents[scope] = parent
        self.positions[scope] = len(self.fields)
        fields = [
            Field(term, scope + (key,), scope, stream, index)
            for index, (term, key) in enumerate(zip(members, keys, strict=True))
        ]
        self.scopes[scope] = fields
        for field in fields:
            self.positions[field.path] = len(self.fields)
            self.fields[field.path] = field
            if self.tree is not None:
                value = self.tree_value(field.path)
                if value is UNBOUND or value is None:
                    continue  # No child struct was parsed for an absent or Null field.
            child = self.graph.value(field.term, URIRef(BDDO + "dataType"))
            if child is not None:
                repeated = self.is_repeated(field.term)
                path = field.path + (("*",) if repeated else ())
                paths = [path]
                if repeated and self.tree is not None:
                    value = self.tree_value(field.path)
                    paths = [field.path + (i,) for i in range(len(value))] if isinstance(value, list) else []
                for instance_path in paths:
                    self.walk(
                        child,
                        instance_path,
                        instance_path if self.is_encoded(field.term) else stream,
                        scope,
                        ancestors | {struct},
                    )
                    if instance_path in self.scopes:
                        self.bind_arguments(child, field, instance_path)

    def bind_arguments(self, struct: Node, caller: Field, scope: FieldPath) -> None:
        parameters = list(self.graph.objects(struct, URIRef(BDDO + "hasParameter")))
        arguments = list(self.graph.objects(caller.term, URIRef(BDDO + "hasArgument")))
        if len(parameters) != 1 or len(arguments) != 1:
            return
        names = [local(term) for term in self.graph.items(parameters[0])]
        expressions = list(self.graph.items(arguments[0]))
        if len(names) != len(expressions) or len(names) != len(set(names)):
            return
        entry = replace(caller, path=scope, entry_owner=caller.path)
        for name, expression in zip(names, expressions, strict=True):
            parsed = self.parse_expression(str(expression))
            if parsed is not None:
                self.arguments[scope, name] = (entry, parsed)

    def parse_expression(self, text: str) -> hel.Node | None:
        """Cache immutable syntax trees, not scope-dependent evaluation results."""
        if text not in self.expressions:
            try:
                self.expressions[text] = hel.parse(text)
            except hel.HelSyntaxError:
                self.expressions[text] = None  # Invalid syntax cannot prove a dependency.
        return self.expressions[text]

    def target(self, field: Field, predicate: str) -> FieldPath | None:
        term = self.graph.value(field.term, URIRef(BDDO + predicate))
        return next((f.path for f in self.scopes[field.scope] if f.term == term), None)

    def variable_length(self, field: Field) -> bool:
        # An expression-bound extent must fit its bound; do not assume the encoder can change it.
        return field.path in self.encoded and not any(
            (field.term, URIRef(BDDO + name), None) in self.graph for name in ("size", "sizeFromExpression")
        )

    def bounded_owners(self, field: Field) -> list[FieldPath]:
        scope = field.scope
        owners = []
        while scope != field.stream and scope in self.parents:
            repeated_entry = bool(scope) and (scope[-1] == "*" or isinstance(scope[-1], int))
            owner = scope[:-1] if repeated_entry else scope
            if owner in self.fields and any(
                (self.fields[owner].term, URIRef(BDDO + name), None) in self.graph
                for name in ("size", "sizeFromField", "sizeFromExpression")
            ):
                # Look up bounds on the field, but retain the individual entry's scope.
                owners.append(scope)
            parent = self.parents[scope]
            if parent == scope:
                break
            scope = parent
        return owners

    def stream_changes(self, field: Field, property_name: str) -> bool:
        for candidate in self.fields.values():
            if candidate.stream != field.stream or not self.variable_length(candidate):
                continue
            if (
                property_name == "position"
                and candidate.path == field.entry_owner
                and field.path != candidate.path
                and field.path[len(candidate.path)] in (0, "*")
            ):
                continue  # The first encoded instance has not been written at its argument evaluation.
            bounds = self.bounded_owners(candidate)
            if property_name == "length" and not bounds:
                return True
            if (
                property_name == "position"
                and self.positions[candidate.path] < self.positions[field.path]
                and all(field.path[: len(owner)] == owner for owner in bounds)
            ):
                return True
        return False

    def context(self, field: Field) -> Context:
        root = (field.path[0],) if isinstance(self.tree, list) and isinstance(field.path[0], int) else ()
        lineage = []
        scope = field.scope
        while scope not in lineage:
            lineage.append(scope)
            if scope == root or scope not in self.parents:
                break
            scope = self.parents[scope]
        return Context(tuple(lineage))

    def parent_scope(self, scope: FieldPath, context: Context) -> FieldPath | None:
        if scope in context.lineage:
            index = context.lineage.index(scope) + 1
            return context.lineage[index] if index < len(context.lineage) else None
        parent = self.parents.get(scope)
        return parent if parent != scope else None

    def access_path(
        self, field: Field, root: str, steps: tuple[tuple[str, object], ...], context: Context
    ) -> FieldPath | None:
        root_scope = (field.path[0],) if isinstance(self.tree, list) and isinstance(field.path[0], int) else ()
        scope = {
            "instance": context.lineage[0] if context.lineage else None,
            "root": root_scope,
            "parent": context.lineage[1] if len(context.lineage) > 1 else None,
            "self": context.self_path,
        }.get(root)
        if scope is None:
            return None
        holders: list[FieldPath] = []
        for kind, value in steps:
            if kind == "key":
                if value == "parent":
                    if root == "self" and not holders:
                        return None
                    binding = self.fields.get(scope)
                    if binding and (binding.term, RDF.type, URIRef(BDDO + "LocalBinding")) in self.graph:
                        return None
                    scope = holders.pop() if holders else self.parent_scope(scope, context)
                    if scope is None:
                        return None
                else:
                    holders.append(scope)
                    scope += (str(value),)
            elif isinstance(value, tuple) and value[:2] == ("lit", "int"):
                scope += (value[2] if self.tree is not None else "*",)
            else:
                return None  # An unproved dynamic index must not grant an exemption.
        return scope

    def parameter_changes(
        self, steps: tuple[tuple[str, object], ...], exempt: set[FieldPath], context: Context
    ) -> bool:
        if not context.lineage or len(steps) != 1 or steps[0][0] != "key":
            return False
        key = (context.lineage[0], str(steps[0][1]))
        if key in context.visiting or key not in self.arguments:
            return False
        caller, expression = self.arguments[key]
        caller_context = replace(self.context(caller), visiting=context.visiting | {key})
        return self.expression_changes(caller, expression, exempt, caller_context)

    def tree_value(self, path: FieldPath) -> object:
        value = self.tree
        try:
            for part in path:
                value = value[part]
        except (KeyError, IndexError, TypeError):
            return UNBOUND
        return value

    def quantifier_changes(self, field: Field, node: hel.Node, exempt: set[FieldPath], context: Context) -> bool:
        collection, predicate = node[2]
        if self.expression_changes(field, collection, exempt, context):
            return True
        if collection[0] != "acc" or self.tree is None:
            return False  # Never borrow the holding scope for an unproved element context.
        path = self.access_path(field, collection[1], collection[2], context)
        value = self.tree_value(path) if path is not None else None
        if path is None or not isinstance(value, list):
            return False
        for index, element in enumerate(value):
            element_path = path + (index,)
            lineage = (element_path,) + context.lineage if isinstance(element, dict) else context.lineage
            nested = replace(context, lineage=lineage, self_path=element_path)
            if self.expression_changes(field, predicate, exempt, nested):
                return True
        return False

    def expression_changes(
        self, field: Field, node: hel.Node, exempt: set[FieldPath], context: Context | None = None
    ) -> bool:
        context = context or self.context(field)
        if node[0] == "acc":
            root, steps = node[1], node[2]
            if root == "stream":
                return len(steps) == 1 and steps[0][0] == "key" and self.stream_changes(field, steps[0][1])
            if root == "param":
                return self.parameter_changes(steps, exempt, context)
            return self.access_path(field, root, steps, context) in exempt
        if node[0] == "call" and node[1] in ("all", "any") and len(node[2]) == 2:
            return self.quantifier_changes(field, node, exempt, context)
        return any(self.expression_changes(field, child, exempt, context) for child in self.children(node))

    @staticmethod
    def children(node: hel.Node) -> Iterator[hel.Node]:
        """Yield AST children lazily so dependency checks can stop at the first match."""
        for value in node[1:]:
            if isinstance(value, tuple) and value:
                if isinstance(value[0], str):
                    yield value
                else:
                    yield from (child for child in value if isinstance(child, tuple) and child)

    def derived_changes(self, field: Field, exempt: set[FieldPath]) -> bool:
        predicate = (
            "localExpression"
            if (field.term, RDF.type, URIRef(BDDO + "LocalBinding")) in self.graph
            else "valueFromExpression"
        )
        expression = self.graph.value(field.term, URIRef(BDDO + predicate))
        if expression is None:
            return False
        parsed = self.parse_expression(str(expression))
        return parsed is not None and self.expression_changes(field, parsed, exempt)

    def checksum_changes(self, field: Field, variable: set[FieldPath]) -> bool:
        if field.path not in self.physical:
            return False  # Derived fields return before the checksum and other byte-processing steps.
        variable = variable & self.physical
        if not variable:
            return False  # A checksum cannot change without changing physical input.
        for checksum in self.graph.objects(field.term, URIRef(BDDO + "checksum")):
            start = self.graph.value(checksum, URIRef(BDDO + "coversFromField"))
            end = self.graph.value(checksum, URIRef(BDDO + "coversToField"))
            siblings = self.scopes[field.scope]
            indices = {f.term: f.index for f in siblings}
            if start not in indices or end not in indices:
                first = self.graph.value(checksum, URIRef(BDDO + "coversFromExpression"))
                last = self.graph.value(checksum, URIRef(BDDO + "coversToExpression"))
                if (
                    str(first).strip() == "0"
                    and str(last).strip() == "stream.length"
                    and any(self.fields[p].stream == field.stream for p in variable)
                ):
                    return True
                continue  # Unproved expression-based coverage is not an exemption.
            covered = siblings[indices[start] : indices[end] + 1]
            if any(path[: len(f.path)] == f.path for f in covered for path in variable):
                return True
        return False

    def exemptions(self) -> set[FieldPath]:
        exempt = {
            target
            for path in self.encoded
            if (target := self.target(self.fields[path], "sizeFromField")) is not None and target in self.physical
        }
        while True:
            # Use one snapshot per iteration so dependency propagation is independent
            # of field order. Already-proved exemptions never need to be revisited.
            variable = exempt | self.encoded
            added = {
                path
                for path, field in self.fields.items()
                if path not in exempt
                and (self.derived_changes(field, exempt) or self.checksum_changes(field, variable))
            }
            if not added:
                return exempt
            exempt |= added


def recomputed_paths(description: Path, root: str | None, tree: Any = None) -> set[FieldPath]:
    graph = Graph().parse(description, format="turtle")
    if root is None:
        roots = set(graph.subjects(RDF.type, URIRef(BDDO + "Struct")))
        referenced = set(graph.objects(None, URIRef(BDDO + "dataType")))
        roots -= referenced
        if len(roots) != 1:
            return set()
        node = roots.pop()
    else:
        node = URIRef(root)
    return Dependencies(graph, node, tree).exemptions()
