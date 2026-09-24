"""Conformance Evaluator cases: a format description, a conformance profile (rules.ttl: conf
constraints, parse attributions and req requirements) and an input, with the run report the
Processing Model's Conformance Evaluation section requires, summarised.

The summary (expected-report.json) states the verdict, whether the run was truncated, whether
version scoping was applied, the outcome of each listed requirement, and the findings -- each by
kind, severity, the requirements it cites and, where the specification fixes it, its message or
error category. A lenient parse ("parseMode": "lenient", the default) records parse errors as
findings, as the Processing Model's lenient mode allows.
"""
import re

from suite import Case, namespace, turtle

PM = "processing#"
CASES = []

PROFILE = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ex:ver ex:vals ex:opt ex:blob ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Header .
   ex:Header a bddo:Struct ; bddo:hasField ( ex:magic ex:flags ) .
   ex:magic a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:flags a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:ver a bddo:Field ; bddo:dataType ex:Version .
   ex:Version a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 3 .
   ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "hdr.flags == 1" .
   ex:blob a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 .
"""
GOOD = b"HXPL" + b"\x00" + b"\x02" + b"\x01\x02\x03" + b"\xab\xcd"


def requirement(name, extra=""):
    return (f'ex:{name} a req:Requirement ; req:requirementId "{name}" ; req:fromStandard "Example Format 1" ; '
            f'req:statement "{name} holds." ; req:discrepancyType req:Syntactic{extra} .\n')


REQS = requirement("R1") + requirement("R2") + requirement("R3")


def with_messages(rules):
    """conf:message is required on every constraint; one that states none reports its focus path."""
    def add(match):
        statement = match.group(0)
        return statement if "conf:message" in statement else statement[:-2] + ' ;\n       conf:message "failed at {field}" .'
    return re.sub(r"ex:C\w* a conf:Constraint ;.*? \.(?=\n|$)", add, rules, flags=re.S)


def ce(id, title, intent, reqs, sections, rules, data, report, manifest=None, description=PROFILE):
    case_id = f"ce-{id}"
    rules = with_messages(rules)
    man = {"rules": "rules.ttl", "parseMode": "lenient"}
    man.update(manifest or {})
    ns = namespace(case_id)
    report = {k: ({i.replace("ex:", ns): o for i, o in v.items()} if k == "outcomes" else v) for k, v in report.items()}
    for finding in report.get("findings", []):
        finding["requirements"] = sorted(r.replace("ex:", ns) for r in finding.get("requirements", []))
    CASES.append(Case(id=case_id, cls="conformance-evaluator", title=title, intent=intent, requirements=reqs,
                      sections=[PM + s if "#" not in s else s for s in sections], description=description,
                      input=data, report=report, manifest=man, files={"rules.ttl": turtle(case_id, rules)}))


EVAL = "conformance-evaluation"
CE = ["req-ce-conf-conformance-1", "req-ce-conf-conformance-10"]

ce("conformant", "Every assertion holds: the run is conformant",
   "A struct-scoped and a field-scoped constraint pass; a requirement no constraint cites is NotExercised.",
   CE + ["req-pm-conformance-evaluation-1", "req-pm-conformance-evaluation-2", "req-ce-conf-conformance-2"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:vals ; conf:assertion "self < 10" ; conf:satisfies ex:R2 .
   """,
   GOOD,
   {"verdict": "conformant", "truncated": False, "versionScopingApplied": False,
    "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated", "ex:R3": "NotExercised"}, "findings": []})

ce("violation-cites-every-requirement", "A false assertion is one Violation citing every requirement its constraint cites",
   "The constraint cites R1 and R2; the finding cites both and nothing else. {field} is the focus node's path; {value} is left "
   "as written, because the struct has two bound scalar fields.",
   CE + ["req-ce-conf-conformance-3", "req-ce-conf-conformance-4", "req-ce-conf-conformance-6", "req-ce-req-conformance-4"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'NOPE'" ; conf:satisfies ex:R1 , ex:R2 ;
       conf:message "{field} has the wrong magic ({value})" .
   """,
   GOOD,
   {"verdict": "nonconformant", "truncated": False,
    "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated", "ex:R3": "NotExercised"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R1", "ex:R2"],
                  "message": "root/hdr has the wrong magic ({value})"}]})

ce("warning-does-not-fail", "A finding at sh:Warning is reported and does not affect the verdict",
   "The only failing constraint has severity sh:Warning.",
   CE + ["req-ce-conf-conformance-3"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "flags == 1" ; conf:satisfies ex:R1 ; conf:severity sh:Warning .
   """,
   GOOD,
   {"verdict": "conformant", "truncated": False, "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Warning", "requirements": ["ex:R1"]}]})

ce("field-scope-per-element", "A field-scoped constraint fires once per element of a repeated field",
   "self < 3 fails for the third element only; {field} is the element's path and {value} its value.",
   CE + ["req-pm-conformance-evaluation-2", "req-ce-conf-conformance-2", "req-ce-conf-conformance-6"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:vals ; conf:assertion "self < 3" ; conf:satisfies ex:R1 ;
       conf:message "{field} = {value}" .
   """,
   GOOD,
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R1"], "message": "root/vals/2 = 3"}]})

ce("struct-scope-single-value", "Under a Struct scope, {value} is the instance's only bound scalar field",
   "The Version struct has exactly one field, so its value is interpolated.",
   CE + ["req-ce-conf-conformance-6"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Version ; conf:assertion "v == 1" ; conf:satisfies ex:R1 ;
       conf:message "version {value} at {field}" .
   """,
   GOOD,
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R1"], "message": "version 2 at root/ver"}]})

ce("bytes-value-rendering", "A Bytes {value} renders as upper-case hexadecimal",
   "The blob field's value AB CD.",
   CE + ["req-ce-conf-conformance-6"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:blob ; conf:assertion "len(self) == 3" ; conf:satisfies ex:R1 ;
       conf:message "blob {value}" .
   """,
   GOOD,
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R1"], "message": "blob ABCD"}]})

ce("rule-error", "An assertion that fails to evaluate is a RuleError, and its requirement is Errored",
   "The assertion names a field Header does not declare; the finding is a RuleError at sh:Violation and the run is not conformant.",
   CE + ["req-ce-conf-conformance-3"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magik == 'HXPL'" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R2 .
   """,
   GOOD,
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Errored", "ex:R2": "Evaluated"},
    "findings": [{"kind": "RuleError", "severity": "Violation", "requirements": ["ex:R1"]}]})

ce("non-boolean-assertion", "An assertion that yields a non-Boolean is a RuleError",
   "flags + 1 is an Integer.",
   CE + ["req-ce-conf-conformance-3"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "flags + 1" ; conf:satisfies ex:R1 .
   """,
   GOOD,
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Errored"},
    "findings": [{"kind": "RuleError", "severity": "Violation", "requirements": ["ex:R1"]}]})

ce("absent-optional-fires-nothing", "A field-scoped constraint on an absent optional field fires nothing",
   "opt is absent (flags is 0), so its constraint is never evaluated and its requirement is NotExercised.",
   CE + ["req-pm-conformance-evaluation-2"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:opt ; conf:assertion "false" ; conf:satisfies ex:R1 .
   """,
   GOOD,
   {"verdict": "conformant", "outcomes": {"ex:R1": "NotExercised"}, "findings": []})

VERSIONED = requirement("R1") + requirement("R2", ' ; req:appliesToVersion "2.0"') + requirement("R3") + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "flags == 9" ; conf:satisfies ex:R2 .
"""

ce("version-scoping-applied", "A requirement for another version is NotApplicable and its constraints are not evaluated",
   "The caller supplies version 1.0; R2 applies to 2.0 only, so its failing constraint is not run.",
   CE + ["req-pm-conformance-evaluation-3", "req-ce-conf-conformance-7", "req-ce-req-conformance-3"], [EVAL],
   VERSIONED, GOOD,
   {"verdict": "conformant", "versionScopingApplied": True,
    "outcomes": {"ex:R1": "Evaluated", "ex:R2": "NotApplicable", "ex:R3": "NotExercised"}, "findings": []},
   manifest={"fileVersion": "1.0"})

ce("version-exact-match", "Version scoping compares by exact string equality",
   "The caller supplies 2.0 and R2 applies to 2.0: its constraint runs and fails.",
   CE + ["req-ce-conf-conformance-7", "req-ce-req-conformance-3"], [EVAL],
   VERSIONED, GOOD,
   {"verdict": "nonconformant", "versionScopingApplied": True,
    "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R2"]}]},
   manifest={"fileVersion": "2.0"})

ce("version-not-supplied", "Without a version every requirement is evaluated and the report says scoping was not applied",
   "No version is supplied, so R2's constraint runs; the evaluator does not guess the version from the data.",
   CE + ["req-pm-conformance-evaluation-3", "req-pm-conformance-evaluation-4", "req-ce-conf-conformance-8"], [EVAL],
   VERSIONED, GOOD,
   {"verdict": "nonconformant", "versionScopingApplied": False,
    "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R2"]}]})

PARSE_RULES = REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Bounds" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
"""

ce("parse-attribution", "A parse error is a Parse finding attributed through the profile's ParseAttribution",
   "The input stops inside vals: a Bounds error, reported as a Parse finding at sh:Violation citing R3, whose outcome is Evaluated.",
   CE + ["req-ce-conf-conformance-5", "req-pm-errors-13"], [EVAL, "errors"],
   PARSE_RULES, GOOD[:7],
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Bounds"}]})

ce("parse-unattributed", "A parse error whose category no attribution names cites no requirement",
   "A Bounds error with no ParseAttribution in the profile.",
   CE + ["req-ce-conf-conformance-5"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD[:7],
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": [], "category": "Bounds"}]})

ce("truncated-run", "A run stopped by the findings limit is reported as truncated and never conformant",
   "Three elements fail under a findings limit of 1. An evaluator may instead fail with a ResourceLimit error; it may not return an "
   "unmarked partial report. R3, cited by nothing, is NotReached in a truncated run.",
   CE + ["req-pm-conformance-evaluation-5", "req-pm-conformance-evaluation-6", "req-ce-conf-conformance-9"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:vals ; conf:assertion "self > 5" ; conf:satisfies ex:R1 .
   """,
   GOOD,
   {"verdict": "nonconformant", "truncated": True, "outcomes": {"ex:R3": "NotReached"}},
   manifest={"limits": {"maxFindings": 1}, "orError": "ResourceLimit"})

ce("evaluation-instant", "evaluationInstant() is the reference instant the run is given",
   "An expiry date read from the input is compared with the run's instant, supplied in the manifest, never the wall clock.",
   CE + ["req-hel-ext-temporal-1"], [EVAL, "hel/index.html#ext-temporal"],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "datetime(stamp, 'yyyyMMddHHmmss') > evaluationInstant()" ;
       conf:satisfies ex:R1 .
   """,
   b"20240229120000",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R1"]}]},
   manifest={"evaluationInstant": 1709208001, "features": {"requires": ["HEL extension groups"]}},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:stamp ) .
   ex:stamp a bddo:Field ; bddo:dataType bddo:string ; bddo:size 14 ; bddo:encoding bddo:ascii .
   """)

ce("lenient-parse-resource-limit", "A lenient parse does not continue past a ResourceLimit",
   "The input exceeds a 4-byte maxInputBytes: the run fails with a ResourceLimit error, or returns a report marked truncated; "
   "it never records the limit as a finding and carries on.",
   CE + ["req-pm-errors-14", "req-pm-conformance-evaluation-6", "req-pm-resource-limits-3"], [EVAL, "errors", "resource-limits"],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD,
   {"verdict": "nonconformant", "truncated": True},
   manifest={"limits": {"maxInputBytes": 4}, "orError": "ResourceLimit"})
