"""The processor conformance suite: case model, canonical forms and the writer.

Each case is authored in one of the cases_*.py modules as a `Case`, with its description, its
input bytes (built here, in Python, so every byte is reviewable and reproducible) and the output
the specification text requires. `generate_inputs.py` writes them to
specification/conformance/<class>/<case-id>/; test_conformance_suite.py checks that the tree on
disk is exactly what the modules generate.

The expected outputs are derived from the specification, never recorded from an implementation.
"""
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "specification/conformance"

CLASSES = ("physical-parser", "semantic-emitter", "bundle-processor", "hdl-compiler", "conformance-evaluator")
PREFIX = {"physical-parser": "pp", "semantic-emitter": "se", "bundle-processor": "bp",
          "hdl-compiler": "hc", "conformance-evaluator": "ce"}
#: The Processing Model's error categories, as a case names them (conf:errorCategory spelling,
#: with Dispatch kept apart from Description as the Processing Model's error table does).
CATEGORIES = ("Sync", "Bounds", "Validation", "Checksum", "Expression", "Dispatch", "Description",
              "Unsupported", "ResourceLimit")
#: Artifacts of which a case has exactly one.
EXPECTED = ("expected.json", "expected.ttl", "expected-error.json", "expected-report.json", "expected-report.ttl",
            "expected-claims.json")
#: The error categories a conformance run's Parse finding names (a ResourceLimit is never a finding).
FINDING_CATEGORIES = tuple(c for c in CATEGORIES if c != "ResourceLimit")
#: The requirement identifiers every case of a class may cite without saying anything specific: a case
#: cites at least one identifier outside this set.
BLANKET = ("req-pm-conformance-1", "req-pm-introduction-1", "req-hdl-conformance-section-1", "req-hel-conformance-1",
           "req-ce-conf-conformance-1")
#: The placeholder base of a case whose manifest gives no base (Processing Model, IRI minting): the
#: processor chooses and reports its own base, and the comparator reads that base as this IRI.
REPORTED_BASE = "urn:hexplain:suite:reported-base"


def feature_tokens():
    """The optional-feature tokens of the Processing Model's closed list (processing/index.html)."""
    import re
    page = (ROOT / "specification/processing/index.html").read_text(encoding="utf-8")
    return tuple(re.findall(r'<li data-feature="([^"]+)">', page))
#: Limits a manifest may lower (Processing Model, Resource Limits), plus the evaluator's findings cap.
LIMITS = ("maxInputBytes", "maxDepth", "maxTreeDepth", "maxVisitedNodes", "maxMaterializedBytes",
          "maxDecodedBytes", "maxHelDepth", "maxHelLength", "maxQuantifierEvaluations", "maxRegexSteps", "maxTriples",
          "maxFindings")

PREFIXES = """@prefix bddo: <https://hexplain.io/ns/bddo#> .
@prefix hexplain: <https://hexplain.io/ns/core#> .
@prefix dlv: <https://hexplain.io/ns/dlv#> .
@prefix menc: <https://hexplain.io/ns/register/media-encoding#> .
@prefix abnd: <https://hexplain.io/ns/aspect/bundle#> .
@prefix conf: <https://hexplain.io/ns/conf#> .
@prefix req: <https://hexplain.io/ns/req#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
"""

BASE = "urn:example:input"


def namespace(case_id):
    return f"https://example.org/{case_id}#"


def turtle(case_id, body):
    """A case's Turtle: the shared prefixes, `ex:` bound to the case's own namespace, then `body`."""
    return PREFIXES + f"@prefix ex: <{namespace(case_id)}> .\n\n" + dedent(body)


@dataclass
class Case:
    id: str
    cls: str
    title: str
    intent: str
    requirements: list
    sections: list
    description: str = None          # Turtle body (physical, semantic, bundle, evaluator)
    input: bytes = None              # the input stream
    expected: object = None          # the parsed tree (physical-parser) as Python values
    expected_ttl: str = None         # Turtle body of the expected graph
    error: str = None                # expected Processing Model category
    root: str = "Root"               # local name of the root struct
    manifest: dict = field(default_factory=dict)   # further manifest members
    files: dict = field(default_factory=dict)      # further files: name -> bytes or str
    report: dict = None              # conformance-evaluator expected report summary
    hdl: str = None                  # hdl-compiler source
    hdl_error: dict = None           # hdl-compiler expected diagnostic
    report_ttl: str = None           # conformance-evaluator expected run report, as Turtle (conf: run terms)
    claims: dict = None              # expected-claims.json: what a processor's claims statement must satisfy

    def artifacts(self):
        """{file name: bytes} of the case directory."""
        out = {}
        man = {"id": self.id, "class": self.cls, "title": self.title, "description": self.intent,
               "requirements": list(self.requirements), "sections": list(self.sections)}
        if self.cls != "hdl-compiler":
            man["root"] = namespace(self.id) + self.root if self.root else None
            if man["root"] is None:
                del man["root"]
        if self.input is not None:
            man["input"] = "input.bin"
            out["input.bin"] = bytes(self.input)
        man.update(self.manifest)
        if self.description is not None:
            out["description.ttl"] = turtle(self.id, self.description).encode("utf-8")
        if self.hdl is not None:
            out["input.hx"] = dedent(self.hdl).encode("utf-8")
        for name, content in self.files.items():
            out[name] = content if isinstance(content, bytes) else content.encode("utf-8")
        if self.expected is not None or (self.cls == "physical-parser" and self.error is None and self.expected_ttl is None
                                         and self.claims is None):
            out["expected.json"] = canonical_json(self.expected)
        if self.expected_ttl is not None:
            out["expected.ttl"] = turtle(self.id, self.expected_ttl).encode("utf-8")
        if self.error is not None:
            if self.error not in CATEGORIES:
                raise ValueError(f"{self.id}: unknown error category {self.error}")
            out["expected-error.json"] = dump({"category": self.error})
        if self.hdl_error is not None:
            out["expected-error.json"] = dump(self.hdl_error)
        if self.report is not None:
            out["expected-report.json"] = dump(self.report)
        if self.report_ttl is not None:
            out["expected-report.ttl"] = turtle(self.id, self.report_ttl).encode("utf-8")
        if self.claims is not None:
            out["expected-claims.json"] = dump(self.claims)
        out["manifest.json"] = dump(man)
        return out


def dedent(text):
    return textwrap.dedent(text).strip("\n") + "\n"


def dump(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def canonical(value):
    """The canonical JSON form of a parsed value (see specification/conformance/index.html)."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if isinstance(value, int):
        return value if -(2 ** 53) <= value <= 2 ** 53 else str(value)
    if isinstance(value, float):
        if value != value:
            return "NaN"
        if value in (float("inf"), float("-inf")):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    raise TypeError(f"no canonical form for {type(value).__name__}")


def canonical_json(value):
    return dump(canonical(value))
