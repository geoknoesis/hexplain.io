"""The one shape of an authored validation case, shared by every ``_*_cases.py`` library.

A case is one small data graph, the module file whose shapes it is validated against, the
verdict those shapes must reach and, for a rejection, the result path (and optionally the source
shape or severity) the report must carry. The libraries build cases through :func:`row`, which
returns the plain dictionary that ``specification/validation/test/family-contracts.json``
retains and that Jena consumes, so the serialized contract never changes shape by accident:
optional keys are present only when set.

:data:`PREFIXES` is the single table of namespace bindings the libraries draw their Turtle
prefix declarations and result-path IRIs from; :func:`prefix_block` renders a chosen subset.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Namespace IRIs by the prefix the case libraries bind them to.
PREFIXES: dict[str, str] = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "sh": "http://www.w3.org/ns/shacl#",
    "dct": "http://purl.org/dc/terms/",
    "hexplain": "https://hexplain.io/ns/core#",
    "bddo": "https://hexplain.io/ns/bddo#",
    "dlv": "https://hexplain.io/ns/dlv#",
    "conf": "https://hexplain.io/ns/conf#",
    "req": "https://hexplain.io/ns/req#",
    "hxf": "https://hexplain.io/ns/fn#",
    "audio": "https://hexplain.io/ns/audio#",
    "video": "https://hexplain.io/ns/video#",
    "image": "https://hexplain.io/ns/image#",
    "archive": "https://hexplain.io/ns/archive#",
    "docfont": "https://hexplain.io/ns/docfont#",
    "geo": "https://hexplain.io/ns/geo#",
    "bundle": "https://hexplain.io/ns/aspect/bundle#",
    "color": "https://hexplain.io/ns/aspect/color#",
    "encoding": "https://hexplain.io/ns/aspect/encoding#",
    "fsmeta": "https://hexplain.io/ns/aspect/fsmeta#",
    "geometry": "https://hexplain.io/ns/aspect/geometry#",
    "integrity": "https://hexplain.io/ns/aspect/integrity#",
    "networkflow": "https://hexplain.io/ns/aspect/networkflow#",
    "packaging": "https://hexplain.io/ns/aspect/packaging#",
    "pointcloud": "https://hexplain.io/ns/aspect/pointcloud#",
    "provenance": "https://hexplain.io/ns/aspect/provenance#",
    "raster": "https://hexplain.io/ns/aspect/raster#",
    "sampling": "https://hexplain.io/ns/aspect/sampling#",
    "security": "https://hexplain.io/ns/aspect/security#",
    "signal": "https://hexplain.io/ns/aspect/signal#",
    "spatialref": "https://hexplain.io/ns/aspect/spatialref#",
    "structure": "https://hexplain.io/ns/aspect/structure#",
    "tabular": "https://hexplain.io/ns/aspect/tabular#",
    "time": "https://hexplain.io/ns/aspect/time#",
}


def prefix_block(bindings: dict[str, str], separator: str = "\n") -> str:
    """Turtle ``@prefix`` declarations for ``bindings`` (local prefix -> IRI, or -> PREFIXES key)."""
    lines = []
    for local, target in bindings.items():
        iri = PREFIXES.get(target, target)
        lines.append(f"@prefix {local}:<{iri}> .")
    return separator.join(lines) + separator


def term(namespace: str, local: str) -> str:
    """The full IRI of ``local`` in the namespace bound to ``namespace`` (a PREFIXES key or an IRI)."""
    return PREFIXES.get(namespace, namespace) + local


@dataclass(frozen=True)
class Case:
    """One authored validation case; :meth:`row` is its retained dictionary form."""

    name: str
    module: str
    data: str
    expected: bool = True
    path: str = ""
    expected_shape: str = ""
    target_shape: str = ""
    target_node: str = ""
    severity: str = ""
    allow_warnings: bool | None = None

    def row(self) -> dict[str, Any]:
        """The dictionary that family-contracts.json retains; optional keys only when set."""
        result: dict[str, Any] = dict(
            name=self.name, module=self.module, expected=self.expected, path=self.path, data=self.data
        )
        if self.expected_shape:
            result["expectedShape"] = self.expected_shape
        if self.target_shape:
            result["targetShape"] = self.target_shape
            result["targetNode"] = self.target_node
        if self.severity:
            result["severity"] = self.severity
        if self.allow_warnings is not None:
            result["allowWarnings"] = self.allow_warnings
        return result


def row(
    name: str,
    module: str,
    data: str,
    expected: bool = True,
    path: str = "",
    *,
    expected_shape: str = "",
    target_shape: str = "",
    target_node: str = "",
    severity: str = "",
    allow_warnings: bool | None = None,
) -> dict[str, Any]:
    """Build one case row. ``module`` is given relative to ``specification/`` unless it already starts with it."""
    if not module.startswith("specification/"):
        module = "specification/" + module
    return Case(
        name,
        module,
        data,
        expected,
        path,
        expected_shape=expected_shape,
        target_shape=target_shape,
        target_node=target_node,
        severity=severity,
        allow_warnings=allow_warnings,
    ).row()


def probe(group: str, name: str, shapes: list[str], data: str, conforms: bool, **extra: Any) -> dict[str, Any]:
    """A review mutation probe: a graph, the shape files to validate it with and the expected verdict."""
    return dict(group=group, name=name, shapes=list(shapes), data=data, conforms=conforms, **extra)
