"""Match diagnostic attributes on one SHACL validation result."""

from rdflib import Graph, Namespace, URIRef

SH = Namespace("http://www.w3.org/ns/shacl#")


def matching_result(report: Graph, path: str = "", shape: str = "", severity: str = "") -> bool:
    wanted = [(SH.resultPath, path), (SH.sourceShape, shape), (SH.resultSeverity, severity)]
    constraints = [(predicate, URIRef(value)) for predicate, value in wanted if value]
    if not constraints:
        return True
    predicate, value = constraints[0]
    return any(all((result, p, v) in report for p, v in constraints) for result in report.subjects(predicate, value))
