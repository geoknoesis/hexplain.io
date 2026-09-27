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


def ce(id, title, intent, reqs, sections, rules, data, report=None, manifest=None, description=PROFILE, error=None,
       report_ttl=None):
    case_id = f"ce-{id}"
    rules = with_messages(rules)
    man = {"rules": "rules.ttl", "parseMode": "lenient"}
    man.update(manifest or {})
    ns = namespace(case_id)
    if report is not None:
        report = {k: ({i.replace("ex:", ns): o for i, o in v.items()} if k == "outcomes" else v) for k, v in report.items()}
        for finding in report.get("findings", []):
            finding["requirements"] = sorted(r.replace("ex:", ns) for r in finding.get("requirements", []))
    CASES.append(Case(id=case_id, cls="conformance-evaluator", title=title, intent=intent, requirements=reqs,
                      sections=[PM + s if "#" not in s else s for s in sections], description=description,
                      input=data, report=report, report_ttl=report_ttl, error=error, manifest=man,
                      files={"rules.ttl": turtle(case_id, rules)}))


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
   "The input stops one byte into blob, the last field: a Bounds error, reported as a Parse finding at sh:Violation citing R3, "
   "whose outcome is Evaluated. The failing read is the last one, so whatever a lenient parse does next, exactly one error is recorded.",
   CE + ["req-ce-conf-conformance-5", "req-pm-errors-13"], [EVAL, "errors"],
   PARSE_RULES, GOOD[:-1],
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Bounds"}]})

ce("parse-unattributed", "A parse error whose category no attribution names cites no requirement",
   "A Bounds error in the last field, with no ParseAttribution in the profile; the failing read is the last, so one error is recorded.",
   CE + ["req-ce-conf-conformance-5"], [EVAL],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD[:-1],
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
   CE + ["req-hel-ext-temporal-3"], [EVAL, "hel/index.html#ext-temporal"],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "datetime(stamp, 'yyyyMMddHHmmss') > evaluationInstant()" ;
       conf:satisfies ex:R1 .
   """,
   b"20240229120000",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R1"]}]},
   manifest={"evaluationInstant": 1709208001, "features": {"requires": ["hel-ext-temporal"]}},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:stamp ) .
   ex:stamp a bddo:Field ; bddo:dataType bddo:string ; bddo:size 14 ; bddo:encoding bddo:ascii .
   """)

ce("lenient-parse-resource-limit", "A lenient parse does not continue past a ResourceLimit",
   "The input exceeds a 4-byte maxInputBytes: the run fails with a ResourceLimit error, or returns a report marked truncated; "
   "it never records the limit as a finding and carries on.",
   CE + ["req-pm-recovery-5", "req-pm-errors-14", "req-pm-conformance-evaluation-6", "req-pm-resource-limits-3"], [EVAL, "errors", "resource-limits"],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD,
   {"verdict": "nonconformant", "truncated": True},
   manifest={"limits": {"maxInputBytes": 4}, "orError": "ResourceLimit"})


# ----------------------------------------------------------------- version scoping is exact string equality

ce("version-trailing-zero", "Version scoping compares strings: \"2.00\" is not \"2.0\"",
   "The caller supplies 2.00 and R2 applies to 2.0. The strings differ, so R2 is NotApplicable and its failing constraint is "
   "not run, although the two spell the same number.",
   CE + ["req-pm-conformance-evaluation-3", "req-ce-conf-conformance-7", "req-ce-req-conformance-3"], [EVAL],
   VERSIONED, GOOD,
   {"verdict": "conformant", "versionScopingApplied": True,
    "outcomes": {"ex:R1": "Evaluated", "ex:R2": "NotApplicable"}, "findings": []},
   manifest={"fileVersion": "2.00"})

# ----------------------------------------------------------------- recovery in a lenient parse (Processing Model, Recovery)

RECOVERY = ["req-pm-recovery-1", "req-pm-errors-13", "req-ce-conf-conformance-5"]

ce("recovery-pointer", "A failed pointer read does not move the cursor",
   "ptr is read at offset 50 of a two-byte input: a Bounds error, recorded once. The cursor stays where it was, so next and "
   "tail are read from bytes 0 and 1 and both constraints are evaluated.",
   CE + RECOVERY + ["req-pm-recovery-2"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Bounds" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "next == 17" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "tail == 34" ; conf:satisfies ex:R2 .
   """,
   b"\x11\x22",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Bounds"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:ptr ex:next ex:tail ) .
   ex:ptr a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 50 .
   ex:next a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

ce("recovery-counted-sequence", "A counted sequence of known-width elements that fails is skipped by count times width",
   "Inner is a five-byte region; vals is three uint16s, so its third element crosses the region end: one Bounds error. vals "
   "is skipped (3 x 2 bytes, bounded by the region end) and Inner goes on with its next field, the derived d, so the "
   "constraint on d is evaluated; tail follows the region.",
   CE + RECOVERY + ["req-pm-recovery-3"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Bounds" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Inner ; conf:assertion "d == 7" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "tail == 9" ; conf:satisfies ex:R2 .
   """,
   b"\x00\x01\x00\x02\x00" + b"\x09",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Bounds"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:inner ex:tail ) .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Inner a bddo:Struct ; bddo:size 5 ; bddo:hasField ( ex:vals ex:d ) .
   ex:vals a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:repeatCount 3 .
   ex:d a bddo:Field ; bddo:valueFromExpression "7" .
   """)

ce("recovery-abandon-struct", "Any other read failure abandons the rest of its struct, which ends at its declared size",
   "body has no FF terminator inside Inner's four-byte region: one Bounds error. body and after are left unbound, a keeps "
   "its value, the cursor moves to Inner's declared end and tail is read there.",
   CE + RECOVERY + ["req-pm-recovery-4"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Bounds" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Inner ; conf:assertion "a == 1" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "tail == 9" ; conf:satisfies ex:R2 .
   """,
   b"\x01\x02\x03\x04" + b"\x09",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Bounds"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:inner ex:tail ) .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Inner a bddo:Struct ; bddo:size 4 ; bddo:hasField ( ex:a ex:body ex:after ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:terminator "FF"^^xsd:hexBinary .
   ex:after a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

ce("recovery-check-continues", "A failed check on a value read in full is recorded and parsing continues",
   "a is read in full and fails its bddo:validIf: one Validation error. The cursor is sound, a keeps its value and b is "
   "read next.",
   CE + RECOVERY + ["req-pm-parsefield-17"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Validation" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:a ; conf:assertion "self == 9" ; conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "b == 3" ; conf:satisfies ex:R2 .
   """,
   b"\x09\x03",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Validation"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:validIf "self < 5" .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

ce("recovery-encoded-elements", "A counted sequence of sized elements that fail to decode is skipped as a whole",
   "arr is three elements of two bytes, each a zlib block that does not decode: one Validation error for the field, whose "
   "3 x 2 bytes are skipped, so after reads 2A.",
   CE + RECOVERY + ["req-pm-recovery-3", "req-pm-minimum-codecs-10"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Validation" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "after == 42" ; conf:satisfies ex:R1 .
   """,
   b"\x01\x02\x03\x04\x05\x06\x2a",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Validation"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:arr ex:after ) .
   ex:arr a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ; bddo:repeatCount 3 ; hexplain:isEncodedWith menc:Zlib .
   ex:after a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

ce("recovery-unknown-width", "A failure with no known end below the root abandons the parse, recording one error",
   "Inner's size expression divides by zero once k is read. Inner has no size and Root none either, so no end is known: "
   "the parse is abandoned there, with one Type / HEL error and no further error for tail.",
   CE + RECOVERY + ["req-pm-recovery-4"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Expression" ; conf:satisfies ex:R3 .
   """,
   b"\x05\x09",
   {"verdict": "nonconformant", "outcomes": {"ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Expression"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:inner ex:tail ) .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Inner a bddo:Struct ; bddo:sizeFromExpression "10 / (k - k)" ; bddo:hasField ( ex:k ) .
   ex:k a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

ce("recovery-sized-field", "A failure inside a sized field is recovered at the field's end",
   "The same Inner, held by a field with a three-byte region: the nearest known end is that region's, so tail is read "
   "after it.",
   CE + RECOVERY + ["req-pm-recovery-4"], [EVAL, "recovery"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Expression" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "tail == 9" ; conf:satisfies ex:R1 .
   """,
   b"\x05\x00\x00\x09",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Expression"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:inner ex:tail ) .
   ex:inner a bddo:Field ; bddo:dataType ex:Inner ; bddo:size 3 .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Inner a bddo:Struct ; bddo:sizeFromExpression "10 / (k - k)" ; bddo:hasField ( ex:k ) .
   ex:k a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

ce("parse-dispatch-category", "A dispatch error is reported under its own category, Dispatch",
   "No rule of body's conditional type matches and there is no default: the Parse finding's category is Dispatch, and the "
   "attribution for Dispatch names R3; it is not a Description error.",
   CE + ["req-ce-conf-conformance-5", "req-pm-errors-7"], [EVAL, "errors"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "Dispatch" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "kind == 9" ; conf:satisfies ex:R1 .
   """,
   b"\x09",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R3": "Evaluated"},
    "findings": [{"kind": "Parse", "severity": "Violation", "requirements": ["ex:R3"], "category": "Dispatch"}]},
   description="""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:body ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:hasConditionalDataType (
       [ a bddo:DataTypeRule ; bddo:condition "kind == 1" ; bddo:ruleDataType ex:A ] ) .
   ex:A a bddo:Struct ; bddo:hasField ( ex:x ) .
   ex:x a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

# ----------------------------------------------------------------- the register extension group

SKOS = "http://www.w3.org/2004/02/skos/core#"
ce("register-in-register", "inRegister() is true exactly for a skos:notation of a concept in the scheme",
   "The run's register source is the description, whose scheme has one concept with notation ABC: code1 (ABC) is in the "
   "register, code2 (XYZ) is not.",
   CE + ["req-hel-conformance-4", "req-ce-conf-conformance-3"], [EVAL, "hel/index.html#ext-register"],
   REQS + """
   ex:C1 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "inRegister(code1, 'https://example.org/ce-register-in-register#Scheme')" ;
       conf:satisfies ex:R1 .
   ex:C2 a conf:Constraint ; conf:scope ex:Root ; conf:assertion "inRegister(code2, 'https://example.org/ce-register-in-register#Scheme')" ;
       conf:satisfies ex:R2 .
   """,
   b"ABCXYZ",
   {"verdict": "nonconformant", "outcomes": {"ex:R1": "Evaluated", "ex:R2": "Evaluated"},
    "findings": [{"kind": "Violation", "severity": "Violation", "requirements": ["ex:R2"]}]},
   manifest={"registers": ["description.ttl"], "features": {"requires": ["hel-ext-register"]}},
   description=f"""
   ex:Root a bddo:Struct ; bddo:hasField ( ex:code1 ex:code2 ) .
   ex:code1 a bddo:Field ; bddo:dataType bddo:string ; bddo:size 3 ; bddo:encoding bddo:ascii .
   ex:code2 a bddo:Field ; bddo:dataType bddo:string ; bddo:size 3 ; bddo:encoding bddo:ascii .
   ex:Scheme a <{SKOS}ConceptScheme> .
   ex:abc a <{SKOS}Concept> ; <{SKOS}inScheme> ex:Scheme ; <{SKOS}notation> "ABC" .
   """)

# ----------------------------------------------------------------- an invalid profile is refused

ce("duplicate-requirement-identity", "Two requirements with one (fromStandard, requirementId) pair make the profile invalid",
   "R1 and R2 both carry the identifier R1 of Example Format 1; the standards differ only in case and surrounding space, "
   "which the comparison ignores. The profile is refused as a Description error rather than evaluated.",
   ["req-ce-req-conformance-2", "req-ce-conf-conformance-1", "req-pm-errors-8"], [EVAL, "req/index.html#conformance"],
   """
   ex:R1 a req:Requirement ; req:requirementId "R1" ; req:fromStandard "Example Format 1" ; req:statement "R1 holds." ;
       req:discrepancyType req:Syntactic .
   ex:R2 a req:Requirement ; req:requirementId "R1" ; req:fromStandard " example format 1 " ; req:statement "R1 holds too." ;
       req:discrepancyType req:Syntactic .
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD, error="Description")

ce("requirement-without-statement", "A requirement without its statement makes the profile invalid",
   "R1 carries no req:statement, which every requirement carries exactly once: the profile is refused as a Description error.",
   ["req-ce-req-conformance-1", "req-ce-conf-conformance-1", "req-pm-errors-8"], [EVAL, "req/index.html#conformance"],
   """
   ex:R1 a req:Requirement ; req:requirementId "R1" ; req:fromStandard "Example Format 1" ; req:discrepancyType req:Syntactic .
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD, error="Description")

# ----------------------------------------------------------------- more profile checks made when the profile is loaded

ce("parse-attribution-resource-limit", "A parse attribution for ResourceLimit makes the profile invalid",
   "ResourceLimit is not a category a finding can carry (a limit ends or truncates the run), so an attribution naming it "
   "is a Description error when the profile is loaded.",
   ["req-ce-conf-conformance-5", "req-pm-errors-8"], [EVAL, "conf/index.html#conformance"],
   REQS + """
   ex:PA a conf:ParseAttribution ; conf:errorCategory "ResourceLimit" ; conf:satisfies ex:R3 .
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
   """,
   GOOD, error="Description")

ce("duplicate-requirement-identity-blank", "Two blank-node requirements with one (fromStandard, requirementId) pair make the profile invalid",
   "The identity rule compares the pair, not the resource: two blank-node requirements whose standards differ only in case "
   "and surrounding space and whose identifiers are equal are a Description error.",
   ["req-ce-req-conformance-2", "req-ce-conf-conformance-1", "req-pm-errors-8"], [EVAL, "req/index.html#conformance"],
   """
   ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ;
       conf:satisfies [ a req:Requirement ; req:requirementId "R1" ; req:fromStandard "Example Format 1" ;
                        req:statement "R1 holds." ; req:discrepancyType req:Syntactic ] ,
                      [ a req:Requirement ; req:requirementId "R1" ; req:fromStandard "EXAMPLE FORMAT 1  " ;
                        req:statement "R1 holds again." ; req:discrepancyType req:Syntactic ] .
   """,
   GOOD, error="Description")

# ----------------------------------------------------------------- the run report as RDF (conf run terms)
#
# expected-report.ttl states the conf:Run the evaluator must emit as RDF, in the run terms of the conf vocabulary
# (conf:verdict, conf:truncated, conf:versionScopingApplied, conf:fileVersion, conf:finding, conf:failOn, conf:profile,
# conf:input). The comparison (specification/conformance/index.html#canonicalisation) maps the expected graph into the
# actual one, blank nodes as variables, and requires as many conf:finding values as the expected run has. These cases
# need those terms in the conf vocabulary; until it declares them the generator leaves them out, so that the suite never
# holds data with an undefined term.


def conf_run_terms_declared():
    from suite import ROOT
    conf = (ROOT / "specification/conf/conf.ttl").read_text(encoding="utf-8")
    return all(f":{term} a owl:" in conf for term in ("finding", "verdict", "truncated", "versionScopingApplied",
                                                      "fileVersion", "profile", "input", "failOn"))


RDF_REPORT = {"reportForm": "rdf", "reportConformsToShapes": True}
#: What every RDF report case checks besides its own rule: the run's shape, and that it validates on its own.
REPORT_RULES = ["req-pm-conformance-evaluation-7", "req-pm-conformance-evaluation-8"]

if conf_run_terms_declared():
    ce("report-rdf-conformant", "The RDF report of a conformant run",
       "A conformant run with no finding: conf:verdict conf:Conformant, not truncated, version scoping not applied, and an "
       "outcome per requirement.",
       CE + REPORT_RULES + ["req-pm-conformance-evaluation-4", "req-ce-conf-conformance-10"], [EVAL],
       REQS + """
       ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
       """,
       GOOD, manifest=RDF_REPORT, report_ttl="""
       [] a conf:Run ; conf:verdict conf:Conformant ; conf:truncated false ; conf:versionScopingApplied false ;
          conf:outcome [ conf:outcomeRequirement ex:R1 ; conf:outcomeValue conf:Evaluated ] ,
                       [ conf:outcomeRequirement ex:R2 ; conf:outcomeValue conf:NotExercised ] ,
                       [ conf:outcomeRequirement ex:R3 ; conf:outcomeValue conf:NotExercised ] .
       """)

    ce("report-rdf-violation", "The RDF report of a violation links the finding to its constraint and requirements",
       "One Violation finding citing R1 and R2, linked from the run by conf:finding, at sh:Violation, naming its constraint.",
       CE + REPORT_RULES + ["req-ce-conf-conformance-3", "req-ce-conf-conformance-4"], [EVAL],
       REQS + """
       ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'NOPE'" ; conf:satisfies ex:R1 , ex:R2 ;
           conf:message "wrong magic" .
       """,
       GOOD, manifest=RDF_REPORT, report_ttl="""
       [] a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ;
          conf:outcome [ conf:outcomeRequirement ex:R1 ; conf:outcomeValue conf:Evaluated ] ,
                       [ conf:outcomeRequirement ex:R2 ; conf:outcomeValue conf:Evaluated ] ;
          conf:finding [ a conf:Finding ; conf:findingKind conf:Violation ; conf:severity sh:Violation ;
                         conf:findingConstraint ex:C1 ; conf:findingRequirement ex:R1 , ex:R2 ;
                         conf:findingMessage "wrong magic" ] .
       """)

    ce("report-rdf-version", "The RDF report states the version it was scoped to",
       "The caller supplies 1.0: conf:versionScopingApplied true and conf:fileVersion \"1.0\"; R2, for 2.0 only, is NotApplicable.",
       CE + REPORT_RULES + ["req-pm-conformance-evaluation-3", "req-ce-conf-conformance-7"], [EVAL],
       VERSIONED, GOOD, manifest=dict(RDF_REPORT, fileVersion="1.0"), report_ttl="""
       [] a conf:Run ; conf:verdict conf:Conformant ; conf:truncated false ;
          conf:versionScopingApplied true ; conf:fileVersion "1.0" ;
          conf:outcome [ conf:outcomeRequirement ex:R2 ; conf:outcomeValue conf:NotApplicable ] .
       """)

    ce("report-rdf-truncated", "The RDF report of a run stopped by the findings limit is marked truncated and non-conformant",
       "Three elements fail under a findings limit of 1; R3, cited by nothing, is NotReached. An evaluator may instead fail "
       "with a ResourceLimit error.",
       CE + REPORT_RULES + ["req-pm-conformance-evaluation-6", "req-ce-conf-conformance-9"], [EVAL],
       REQS + """
       ex:C1 a conf:Constraint ; conf:scope ex:vals ; conf:assertion "self > 5" ; conf:satisfies ex:R1 .
       """,
       GOOD, manifest=dict(RDF_REPORT, limits={"maxFindings": 1}, orError="ResourceLimit"), report_ttl="""
       [] a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated true ;
          conf:outcome [ conf:outcomeRequirement ex:R3 ; conf:outcomeValue conf:NotReached ] .
       """)

    ce("report-rdf-fail-on-warning", "With failOn sh:Warning a warning makes the run non-conformant, and the report says so",
       "The only failing constraint is at sh:Warning; the caller sets the failing severity to sh:Warning, which the report "
       "states as conf:failOn.",
       CE + REPORT_RULES + ["req-ce-conf-conformance-3"], [EVAL],
       REQS + """
       ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "flags == 1" ; conf:satisfies ex:R1 ; conf:severity sh:Warning .
       """,
       GOOD, manifest=dict(RDF_REPORT, failOn="Warning"), report_ttl="""
       [] a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ; conf:failOn sh:Warning ;
          conf:finding [ a conf:Finding ; conf:findingKind conf:Violation ; conf:severity sh:Warning ;
                         conf:findingConstraint ex:C1 ; conf:findingRequirement ex:R1 ] .
       """)

    ce("report-rdf-provenance", "The RDF report names the profile and the input it evaluated",
       "The runner gives the evaluator the description's IRI and the input's IRI (manifest profileIri and inputIri); the run "
       "states them as conf:profile and conf:input.",
       CE + REPORT_RULES + ["req-ce-conf-conformance-10"], [EVAL],
       REQS + """
       ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'HXPL'" ; conf:satisfies ex:R1 .
       """,
       GOOD, manifest=dict(RDF_REPORT, profileIri="https://example.org/ce-report-rdf-provenance", inputIri="urn:example:input"),
       report_ttl="""
       [] a conf:Run ; conf:verdict conf:Conformant ; conf:truncated false ;
          conf:profile <https://example.org/ce-report-rdf-provenance> ; conf:input <urn:example:input> .
       """)

    ce("report-rdf-parse-finding", "The RDF report of a Parse finding states its error category",
       "The input stops one byte into blob, the last field: one conf:Parse finding, with no constraint, attributed to R3 "
       "through the Bounds parse attribution.",
       CE + REPORT_RULES + ["req-ce-conf-conformance-5"], [EVAL],
       PARSE_RULES, GOOD[:-1], manifest=RDF_REPORT, report_ttl="""
       [] a conf:Run ; conf:verdict conf:NonConformant ;
          conf:finding [ a conf:Finding ; conf:findingKind conf:Parse ; conf:severity sh:Violation ;
                         conf:findingRequirement ex:R3 ; conf:errorCategory ?category ] .
       """.replace("conf:errorCategory ?category", 'conf:errorCategory conf:BoundsError'))

    ce("report-rdf-warning-conformant", "Under the default failOn a warning-only run is conformant",
       "The only failing constraint is at sh:Warning and the caller sets no failing severity (sh:Violation): the finding is "
       "reported and the verdict is conf:Conformant.",
       CE + REPORT_RULES + ["req-ce-conf-conformance-3"], [EVAL],
       REQS + """
       ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "flags == 1" ; conf:satisfies ex:R1 ; conf:severity sh:Warning .
       """,
       GOOD, manifest=RDF_REPORT, report_ttl="""
       [] a conf:Run ; conf:verdict conf:Conformant ; conf:truncated false ;
          conf:finding [ a conf:Finding ; conf:findingKind conf:Violation ; conf:severity sh:Warning ;
                         conf:findingConstraint ex:C1 ; conf:findingRequirement ex:R1 ] .
       """)

    ce("report-rdf-blank-requirement", "A finding cites a blank-node requirement by its description",
       "The requirement is a blank node of the profile, so the report cannot name it by the profile's IRI. The report "
       "carries a copy of the requirement's description, which the finding cites; the comparison binds the expected "
       "blank node to whatever node the report gives it (a skolem IRI, say) by that description.",
       CE + REPORT_RULES + ["req-ce-conf-conformance-3", "req-ce-conf-conformance-4"], [EVAL],
       """
       ex:C1 a conf:Constraint ; conf:scope ex:Header ; conf:assertion "magic == 'NOPE'" ;
           conf:satisfies [ a req:Requirement ; req:requirementId "B1" ; req:fromStandard "Example Format 1" ;
                            req:statement "B1 holds." ; req:discrepancyType req:Syntactic ] .
       """,
       GOOD, manifest=RDF_REPORT, report_ttl="""
       [] a conf:Run ; conf:verdict conf:NonConformant ; conf:truncated false ;
          conf:finding [ a conf:Finding ; conf:findingKind conf:Violation ; conf:findingConstraint ex:C1 ;
                         conf:findingRequirement [ a req:Requirement ; req:requirementId "B1" ;
                                                   req:fromStandard "Example Format 1" ] ] .
       """)
