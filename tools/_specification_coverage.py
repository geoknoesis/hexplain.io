"""Inventory every registered requirement, SHACL obligation and vocabulary declaration.

Case citations and measured component witnesses are distinct evidence. Neither is a
proof of complete semantic coverage. Non-black-box requirements remain explicit.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from _build_conformance_page import (
    BLANKET,
    HEL_VECTOR_EVIDENCE,
    HEL_VECTORS,
    NOT_SUITE_TESTABLE,
    OBSERVED_BY_ROUND_TRIP,
)
from _cases import term
from rdflib import RDF, Graph, Namespace

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "specification/validation/construct-coverage.json"
INPUTS = (
    "specification/conformance/requirements.json",
    "specification/conformance/coverage.json",
    "specification/validation/constraint-coverage.json",
    "specification/validation/competency-trace.json",
    "specification/reference/manifest.json",
)


# Explicit prose-to-property mappings, reviewed against the corresponding source clauses.
# These retain component witnesses, not an inference from matching words in the prose.
DESCRIPTION_PATHS = {
    "req-pm-size-resolution-1": ("bddo", "size sizeFromField sizeFromExpression sizeToEndOfStream"),
    "req-pm-text-decoding-8": ("bddo", "ianaCharset"),
    "req-bddo-core-datatypes-2": (
        "bddo",
        "size sizeFromField sizeFromExpression sizeToEndOfStream terminator bitLength",
    ),
    "req-bddo-data-type-rule-1": ("bddo", "baseType"),
    "req-bddo-field-properties-1": ("bddo", "dataType"),
    "req-bddo-field-properties-2": ("bddo", "dataType hasConditionalDataType"),
    "req-bddo-field-properties-3": ("bddo", "armKey armTable"),
    "req-bddo-field-properties-4": ("bddo", "size sizeFromField sizeFromExpression sizeToEndOfStream terminator"),
    "req-bddo-field-properties-5": ("bddo", "terminator"),
    "req-bddo-field-properties-6": ("bddo", "encoding"),
    "req-bddo-field-properties-7": (
        "bddo",
        "repeatCount repeatCountFromField repeatCountFromExpression repeatUntil",
    ),
    "req-bddo-field-properties-9": ("bddo", "recordDelimiter fieldDelimiter keyValueSeparator"),
    "req-bddo-field-properties-10": ("bddo", "quoteChar escapeChar"),
    "req-bddo-structural-properties-2": ("bddo", "endianness"),
    "req-bddo-structural-properties-3": ("bddo", "bitOrder"),
    "req-bddo-structural-properties-5": ("bddo", "syncOnMarker"),
    "req-dlv-properties-1": ("dlv", "cellDataType"),
    "req-dlv-properties-2": ("dlv", "dimensionSize dimensionSizeFromField"),
    "req-core-static-mapping-properties-1": ("hexplain", "mapsToClass"),
    "req-core-static-mapping-properties-2": ("hexplain", "mapsToProperty"),
    "req-raster-document-1": ("raster", "bandCount hasBand"),
    "req-raster-document-2": ("raster", "dimensions"),
    "req-raster-document-4": ("raster", "sampleScale sampleOffset"),
    "req-raster-document-5": ("raster", "dimensionKind"),
    "req-spatialref-document-1": ("spatialref", "originX originY scaleX scaleY skewX skewY"),
    "req-spatialref-document-5": ("spatialref", "gcpPixelX gcpPixelY gcpX gcpY"),
    "req-spatialref-document-6": ("spatialref", "latitudeScale longitudeScale heightScale sampleScale lineScale"),
}


REVIEW_REQUIRED = {
    "req-pm-context-2": (
        "New-authoring policy: compatibility parsing may accept the deprecated alias. Inspect authoring output."
    ),
    "req-hel-name-binding-2": (
        "New-authoring policy: refusing all legacy alias inputs would violate compatibility behavior."
    ),
    "req-hel-expression-literals-2": (
        "Advisory authoring-tool output policy; xsd:string expressions remain valid inputs."
    ),
    "req-spatialref-document-7": (
        "A basis IRI must identify an externally published mathematical contract; IRI "
        "shape validation cannot establish its content."
    ),
    "req-spatialref-document-8": (
        "Coefficient-order compatibility requires the external basis contract and consumer implementation."
    ),
    "req-spatialref-document-9": (
        "Profile completeness requires the referenced external RPC contract, not merely a basis IRI."
    ),
    "req-geometry-document-2": (
        "Advisory importer emission policy; native importer execution belongs to the "
        "reference engine and format adapters."
    ),
    "req-hdl-yaml-4": (
        "Advisory compiler warning policy; graph comparison does not establish whether "
        "the compiler emitted the warning."
    ),
    "req-pm-privacy-2": (
        "Caller-supplied input identity and report privacy require an explicit caller/runtime contract."
    ),
    "req-spatialref-document-10": (
        "RPC execution is outside every Processing Model conformance class; inspect an optional RPC consumer."
    ),
    "req-spatialref-document-11": (
        "Zero-denominator behavior belongs to an optional RPC consumer; this repository "
        "supplies no RPC execution engine."
    ),
    "req-dlv-conditional-1": (
        "Author ordering rule: whether one arm's condition is more specific than another's is a judgement over "
        "HEL conditions that no shape can decide; inspect the description."
    ),
}


def hel_vector_rows() -> dict[str, str]:
    """Expression -> row name of every row of the HEL vector set."""
    rows = {}
    for line in HEL_VECTORS.read_text(encoding="utf-8").splitlines():
        columns = line.split("\t")
        if line.strip() and not line.startswith("#") and len(columns) > 2:
            rows[columns[1]] = columns[0]
    return rows


def build() -> dict[str, Any]:
    inputs = {name: json.loads((ROOT / name).read_text(encoding="utf-8")) for name in INPUTS}
    registry, coverage, ledger, trace, reference = (inputs[name] for name in INPUTS)
    function_requirements = {"req-spatialref-document-2", "req-spatialref-document-3", "req-spatialref-document-12"}
    requirements = []
    vector_rows = hel_vector_rows()
    for identifier, row in sorted(registry["requirements"].items()):
        if row.get("withdrawn"):
            continue
        cases = coverage["citations"].get(identifier, [])
        reason = ""
        mapped = []
        if identifier in DESCRIPTION_PATHS:
            namespace, properties = DESCRIPTION_PATHS[identifier]
            for prop in properties.split():
                matching = [r["id"] for r in ledger["constraints"] if r["path"] == term(namespace, prop)]
                assert matching, (identifier, prop, "No measured construct for the explicit mapping")
                mapped.extend(matching)
        if identifier in OBSERVED_BY_ROUND_TRIP:
            status = "round-trip-mode"
        elif cases:
            status = "case-cited"
        elif identifier in BLANKET:
            status = "cross-cutting-suite-contract"
        elif identifier in HEL_VECTOR_EVIDENCE:
            missing = [e for e in HEL_VECTOR_EVIDENCE[identifier] if e not in vector_rows]
            assert not missing, (identifier, missing, "No HEL vector row for the explicit mapping")
            status = "hel-vector-cited"
            reason = "HEL vectors: " + "; ".join(vector_rows[e] for e in HEL_VECTOR_EVIDENCE[identifier])
        elif identifier in NOT_SUITE_TESTABLE:
            status, reason = "non-black-box", NOT_SUITE_TESTABLE[identifier]
        elif identifier in function_requirements:
            status = "executable-function-body"
            reason = "test_fn_catalogue executes the published affine bodies against independent boundary fixtures."
        elif mapped:
            status = "constraint-witnessed"
            reason = "Explicit property-contract mapping to two-sided witnesses; combinations still require review."
        elif row.get("audience") == "description":
            status = "description-review-required"
            reason = REVIEW_REQUIRED.get(identifier, "UNCLASSIFIED: add an executable test or reviewed disposition")
        else:
            status = "review-required"
            reason = REVIEW_REQUIRED.get(identifier, "UNCLASSIFIED: add an executable test or reviewed disposition")
        requirements.append(
            dict(
                id=identifier,
                source=row["page"],
                level=row["level"],
                status=status,
                cases=cases,
                reason=reason,
                constraint_evidence=sorted(set(mapped)),
            )
        )
    obligations = []
    names = ledger["case_names"]
    for row in ledger["constraints"]:
        positive = row["passed"] or (
            row["empty_value_passes"]
            if row["component"].endswith(("MinCountConstraintComponent", "MaxCountConstraintComponent"))
            else []
        )
        obligations.append(
            dict(
                id=row["id"],
                source=row["source"],
                shape=row["shape"],
                component=row["component"],
                path=row["path"],
                positive=[names[i] for i in positive[:1]],
                negative=[names[i] for i in row["failed"][:1]],
            )
        )
    declarations = []
    for resource in trace["resources"]:
        references = (
            resource["positive"] + resource["negative"] + resource["contract_positive"] + resource["contract_negative"]
        )
        declarations.append(
            dict(
                iri=resource["iri"],
                module=resource["module"],
                declaration_gate="test_term_reference",
                corpus_references=references[:4],
                corpus_reference_count=len(references),
                semantics="references are discovery evidence, not semantic acceptance",
            )
        )
    function_path = ROOT / "specification/fn/fn.ttl"
    graph = Graph().parse(function_path)
    fn, sh = Namespace("https://hexplain.io/ns/fn#"), Namespace("http://www.w3.org/ns/shacl#")
    functions = [
        dict(
            iri=str(function),
            kind=str(graph.value(function, fn.kind)).removeprefix(str(fn)),
            evidence="test_fn_catalogue"
            if (function, RDF.type, sh.SPARQLFunction) in graph
            else "external runtime required",
        )
        for function in sorted(graph.subjects(RDF.type, fn.Function), key=str)
    ]
    return dict(
        functions=functions,
        function_host_limitations=[
            "RDFLib calibration arithmetic may return xsd:decimal for a double/decimal expression; "
            "exact numeric values are checked and external-host datatype verification remains required."
        ],
        function_source_sha256=hashlib.sha256(function_path.read_text(encoding="utf-8").encode()).hexdigest(),
        schema_version=1,
        scope="Complete inventory of registered constructs, with evidence and remaining review obligations. "
        "Case citations are not execution results. Declaration checks are not behavioral tests. "
        "Non-black-box requirements and unmapped prose are not counted as tested.",
        inputs={
            name: hashlib.sha256((ROOT / name).read_text(encoding="utf-8").encode()).hexdigest() for name in INPUTS
        },
        summary=dict(
            requirements=len(requirements),
            requirement_statuses=dict(sorted(Counter(r["status"] for r in requirements).items())),
            constraint_obligations=len(obligations),
            two_sided=sum(bool(r["positive"] and r["negative"]) for r in obligations),
            declarations=len(declarations),
            modules=len(reference),
        ),
        requirements=requirements,
        constraints=obligations,
        declarations=declarations,
    )


def check() -> None:
    actual = json.loads(TARGET.read_text(encoding="utf-8"))
    assert actual == build(), "Regenerate tools/_specification_coverage.py after changing specification evidence"
    assert all(row["positive"] and row["negative"] for row in actual["constraints"]), (
        "A construct lacks two-sided constraint witnesses"
    )
    assert len({row["id"] for row in actual["requirements"]}) == len(actual["requirements"])
    assert len({row["iri"] for row in actual["declarations"]}) == len(actual["declarations"])
    review_only = {
        row["id"]
        for row in actual["requirements"]
        if row["status"] in ("description-review-required", "review-required")
    }
    assert review_only == set(REVIEW_REQUIRED), (
        "An untested specification clause needs a test or explicit review disposition"
    )
    coverage = json.loads((ROOT / INPUTS[1]).read_text(encoding="utf-8"))
    assert all(not row["uncovered"] for row in coverage["processorMust"].values()), (
        "A processor MUST has no case or documented exception"
    )
    assert all(
        row["cases"] or row["reason"] or row["status"] in ("round-trip-mode", "cross-cutting-suite-contract")
        for row in actual["requirements"]
    ), "A requirement lacks evidence or a disposition"


if __name__ == "__main__":
    result = build()
    TARGET.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(result["summary"])
