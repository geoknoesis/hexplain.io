"""Attribution, expression and requirement identity contracts."""

from __future__ import annotations

from typing import Any

from _cases import row, term

CONF = "conf/shapes.ttl"
CONF_NS = "https://hexplain.io/ns/conf#"
CORE_NS = "https://hexplain.io/ns/core#"


def class_cases() -> list[dict[str, Any]]:
    """Requirement and constraint classes: every property valid, missing, wrong, duplicate."""
    rows: list[dict[str, Any]] = []
    for module, cls, values, invalid in [
        (
            "req",
            "Requirement",
            {
                "requirementId": '"R01"',
                "fromStandard": '"format specification"',
                "statement": '"Must have a header"',
                "discrepancyType": "p:Syntactic",
            },
            {"requirementId": "1", "fromStandard": "1", "statement": "1", "discrepancyType": "ex:unknown"},
        ),
        (
            "conf",
            "Constraint",
            {"scope": "ex:field", "assertion": '"true"', "satisfies": "ex:requirement", "message": '"Header missing"'},
            {"scope": '"field"', "assertion": "1", "satisfies": "ex:untyped", "message": "1"},
        ),
    ]:
        prefix = (
            f"@prefix p:<https://hexplain.io/ns/{module}#> . @prefix ex:<urn:requirement-case:> . "
            "ex:requirement a <https://hexplain.io/ns/req#Requirement> ."
        )
        if module == "req":
            prefix = prefix.split("ex:requirement a")[0]
        # A constraint's scope is a bddo:Struct or bddo:Field; the valid scope is typed as one.
        if module == "conf":
            prefix += " ex:field a <https://hexplain.io/ns/bddo#Field> ."

        def add(name: str, changed: dict[str, str], expected: bool, path: str = "") -> None:
            body = " ex:f a p:" + cls + ". " + "".join("ex:f p:" + p + " " + v + ". " for p, v in changed.items())
            rows.append(
                row(
                    module + " " + name,
                    module + "/shapes.ttl",
                    prefix + body,
                    expected,
                    "https://hexplain.io/ns/" + module + "#" + path if path else "",
                )
            )

        add("valid", values, True)
        for prop in values:
            for label, value in [("missing", None), ("wrong value", invalid[prop])]:
                changed = dict(values)
                if value is None:
                    del changed[prop]
                else:
                    changed[prop] = value
                add(prop + " " + label, changed, False, prop)
            if prop != "satisfies":
                second = (
                    "p:Semantic" if prop == "discrepancyType" else ("ex:other" if prop == "scope" else '"different"')
                )
                changed = dict(values)
                changed[prop] += "," + second
                add(prop + " duplicate", changed, False, prop)
        prop = "requirementId" if module == "req" else "assertion"
        changed = dict(values)
        changed[prop] = '""'
        add(prop + " empty", changed, False, prop)
        if module == "req":
            for val, ok in [('"1.0"', True), ("1", False)]:
                changed = dict(values)
                changed["appliesToVersion"] = val
                add("version " + str(ok), changed, ok, "" if ok else "appliesToVersion")
    return rows


def finding_cases() -> list[dict[str, Any]]:
    """Findings: what an evaluation reports, and each way a malformed one is caught."""
    rows: list[dict[str, Any]] = []
    conf = (
        "@prefix c:<https://hexplain.io/ns/conf#> . @prefix r:<https://hexplain.io/ns/req#> . "
        "@prefix h:<https://hexplain.io/ns/core#> . @prefix sh:<http://www.w3.org/ns/shacl#> . "
        "@prefix ex:<urn:requirement-case:> . ex:req a r:Requirement . ex:req2 a r:Requirement . "
        "ex:field a <https://hexplain.io/ns/bddo#Field> . "
        'ex:con a c:Constraint ; c:scope ex:field ; c:assertion "true" ; c:satisfies ex:req ; c:message "m" . '
        'ex:con2 a c:Constraint ; c:scope ex:field ; c:assertion "true" ; c:satisfies ex:req ; c:message "m" . '
    )
    finding = {
        "findingKind": "c:Violation",
        "findingRequirement": "ex:req",
        "findingConstraint": "ex:con",
        "focusNode": "ex:node",
        "findingMessage": '"Header missing"',
    }
    located = {"h:byteOffset": "0", "h:byteLength": "4"}

    def finding_case(
        name: str, changed: dict[str, str | None], expected: bool, path: str = "", extra: str = ""
    ) -> None:
        body = (
            "ex:fd a c:Finding . "
            + "".join(f"ex:fd {k if ':' in k else 'c:' + k} {v} . " for k, v in changed.items() if v is not None)
            + extra
        )
        full = CORE_NS + path if path in ("byteOffset", "byteLength") else (CONF_NS + path if path else "")
        rows.append(row("conf finding " + name, CONF, conf + body, expected, full))

    finding_case("valid", {**finding, **located}, True)
    for prop, bad in [
        ("findingKind", "ex:other"),
        ("findingRequirement", "ex:untyped"),
        ("findingConstraint", "ex:untyped"),
        ("focusNode", '"node"'),
        ("findingMessage", "1"),
    ]:
        finding_case(prop + " wrong value", {**finding, prop: bad}, False, prop)
    for prop in ["findingKind", "findingMessage"]:
        finding_case(prop + " missing", {**finding, prop: None}, False, prop)
    # A constraint finding needs a requirement; only a Parse finding may have none, so the
    # absence is reported by the kind-dependent alternative (sh:or, no result path).
    finding_case("findingRequirement missing", {**finding, "findingRequirement": None}, False)
    parse = {"findingKind": "c:Parse", "errorCategory": '"Bounds"', "findingMessage": '"Truncated"'}
    finding_case("parse without requirement", parse, True)
    finding_case("severity stated", {**finding, "severity": "sh:Violation"}, True)
    finding_case("severity other than the constraint", {**finding, "severity": "sh:Warning"}, False)
    finding_case("severity unknown", {**finding, "severity": "c:Violation"}, False, "severity")
    finding_case("severity twice", {**finding, "severity": "sh:Warning, sh:Info"}, False, "severity")
    finding_case(
        "parse with requirement",
        {**parse, "findingRequirement": "ex:req"},
        True,
        extra='ex:pa a c:ParseAttribution ; c:errorCategory "Bounds" ; c:satisfies ex:req . ',
    )
    finding_case("parse with an unattributed requirement", {**parse, "findingRequirement": "ex:req"}, False)
    finding_case("parse with constraint", {**parse, "findingConstraint": "ex:con"}, False)
    finding_case("parse without category", {**parse, "errorCategory": None}, False)
    finding_case("parse category wrong value", {**parse, "errorCategory": '"Overflow"'}, False, "errorCategory")
    finding_case("violation without constraint", {**finding, "findingConstraint": None}, False)
    finding_case("requirement not cited by constraint", {**finding, "findingRequirement": "ex:req, ex:req2"}, False)
    for prop, extra in [
        ("findingKind", "c:RuleError"),
        ("findingConstraint", "ex:con2"),
        ("focusNode", "ex:node2"),
        ("findingMessage", '"other"'),
    ]:
        finding_case(prop + " duplicate", {**finding, prop: finding[prop] + ", " + extra}, False, prop)
    finding_case("findingMessage empty", {**finding, "findingMessage": '""'}, False, "findingMessage")
    for prop in ["byteOffset", "byteLength"]:
        finding_case(prop + " duplicate", {**finding, "h:" + prop: "0, 1"}, False, prop)
    finding_case(
        "rule error without constraint", {**finding, "findingKind": "c:RuleError", "findingConstraint": None}, False
    )
    finding_case("rule error with constraint", {**finding, "findingKind": "c:RuleError"}, True)
    second = 'ex:con2 a c:Constraint ; c:scope ex:field ; c:assertion "true" ; c:satisfies ex:req ; c:message "m" . '
    base = conf.replace(second, "")
    for name, body, ok, path in [
        ("empty message", base.replace('c:message "m"', 'c:message ""'), False, "message"),
        ("one severity", base.replace('c:message "m"', 'c:message "m" ; c:severity sh:Warning'), True, ""),
        (
            "two severities",
            base.replace('c:message "m"', 'c:message "m" ; c:severity sh:Warning, sh:Info'),
            False,
            "severity",
        ),
    ]:
        rows.append(row("conf constraint " + name, CONF, body, ok, CONF_NS + path if path else ""))
    # Parse attributions and run outcomes.
    for name, body, ok, path in [
        (
            "attribution valid",
            'ex:pa a c:ParseAttribution ; c:errorCategory "Checksum" ; c:satisfies ex:req . ',
            True,
            "",
        ),
        (
            "attribution without requirement",
            'ex:pa a c:ParseAttribution ; c:errorCategory "Checksum" . ',
            False,
            "satisfies",
        ),
        (
            "attribution two requirements",
            'ex:pa a c:ParseAttribution ; c:errorCategory "Checksum" ; c:satisfies ex:req, ex:req2 . ',
            False,
            "satisfies",
        ),
        ("attribution without category", "ex:pa a c:ParseAttribution ; c:satisfies ex:req . ", False, "errorCategory"),
        (
            "attribution repeated category",
            'ex:pa a c:ParseAttribution ; c:errorCategory "Sync" ; c:satisfies ex:req . '
            'ex:pb a c:ParseAttribution ; c:errorCategory "Sync" ; c:satisfies ex:req2 . ',
            False,
            "",
        ),
        (
            "run valid",
            "ex:run a c:Run ; c:verdict c:NonConformant ; c:truncated false ; c:outcome [ c:outcomeRequirement "
            "ex:req ; "
            "c:outcomeValue c:NotReached ] , [ c:outcomeRequirement ex:req2 ; c:outcomeValue c:NotReached ] . ",
            True,
            "",
        ),
        (
            "outcome without value",
            "ex:run a c:Run ; c:outcome [ c:outcomeRequirement ex:req ] . ",
            False,
            "outcomeValue",
        ),
        (
            "outcome wrong value",
            "ex:run a c:Run ; c:outcome [ c:outcomeRequirement ex:req ; c:outcomeValue c:Parse ] . ",
            False,
            "outcomeValue",
        ),
        (
            "outcome without requirement",
            "ex:run a c:Run ; c:outcome [ c:outcomeValue c:Evaluated ] . ",
            False,
            "outcomeRequirement",
        ),
        (
            "outcome two values",
            "ex:run a c:Run ; c:outcome [ c:outcomeRequirement ex:req ; c:outcomeValue c:Evaluated , c:Errored ] . ",
            False,
            "outcomeValue",
        ),
        (
            "outcome two requirements",
            "ex:run a c:Run ; c:outcome [ c:outcomeRequirement ex:req , ex:req2 ; c:outcomeValue c:Evaluated ] . ",
            False,
            "outcomeRequirement",
        ),
        (
            "outcome untyped requirement",
            "ex:run a c:Run ; c:outcome [ c:outcomeRequirement ex:untyped ; c:outcomeValue c:Evaluated ] . ",
            False,
            "outcomeRequirement",
        ),
        ("run outcome literal", 'ex:run a c:Run ; c:outcome "evaluated" . ', False, "outcome"),
        (
            "attribution untyped requirement",
            'ex:pa a c:ParseAttribution ; c:errorCategory "Sync" ; c:satisfies ex:untyped . ',
            False,
            "satisfies",
        ),
        (
            "attribution two categories",
            'ex:pa a c:ParseAttribution ; c:errorCategory "Sync" , "Bounds" ; c:satisfies ex:req . ',
            False,
            "errorCategory",
        ),
        (
            "run two outcomes for one requirement",
            "ex:run a c:Run ; c:outcome [ c:outcomeRequirement ex:req ; c:outcomeValue c:Evaluated ] , "
            "[ c:outcomeRequirement ex:req ; c:outcomeValue c:Errored ] . ",
            False,
            "",
        ),
    ]:
        rows.append(row("conf " + name, CONF, conf + body, ok, CONF_NS + path if path else ""))
    rq = (
        "@prefix r:<https://hexplain.io/ns/req#> . @prefix ex:<urn:requirement-case:> . "
        'ex:f a r:Requirement ; r:requirementId "R01" ; r:fromStandard "format specification" ; '
        'r:statement "Must have a header" ; r:discrepancyType r:Syntactic ; r:appliesToVersion '
    )
    rows.append(row("req version empty", "req/shapes.ttl", rq + '"" .', False, term("req", "appliesToVersion")))
    return rows


def cases() -> list[dict[str, Any]]:
    return class_cases() + finding_cases()
