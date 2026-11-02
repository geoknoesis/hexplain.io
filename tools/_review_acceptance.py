"""Validate acceptance record structure; never authenticate a reviewer or grant approval."""

import re
from datetime import datetime
from typing import Any


def _structure_problems(record: dict[str, Any]) -> list[str]:
    if not isinstance(record, dict):
        return ["review record must be an object"]
    modules = record.get("module_reviews")
    if not isinstance(modules, list) or not modules or any(not isinstance(m, dict) for m in modules):
        return ["module_reviews must be a nonempty array of objects"]
    archive = record.get("archive_sha256")
    if not isinstance(archive, str) or not re.fullmatch(r"[0-9a-f]{64}", archive):
        return ["archive_sha256 must identify the candidate with a lowercase SHA-256 digest"]
    return []


def problems(record: dict[str, Any]) -> list[str]:
    structural = _structure_problems(record)
    if structural:
        return structural
    decision = record.get("decision")
    modules = record["module_reviews"]
    if decision is None:
        return (
            []
            if (
                record.get("status") == "awaiting independent review"
                and record.get("reviewer") is None
                and record.get("reviewed_at") is None
                and all(m.get("status") == "unreviewed" for m in modules)
            )
            else ["inconsistent pending review"]
        )
    out = []
    if decision not in ("accepted", "rejected", "changes requested") or record.get("status") != decision:
        out.append("review status and decision must agree")
    if not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip():
        out.append("reviewer identity is required")
    for key in ("organization", "conflicts", "reviewed_scope"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            out.append(f"{key} must be explicit")
    if record.get("independence_attested") is not True:
        out.append("independence must be explicitly attested by the reviewer")
    if record.get("reviewed_archive_sha256") != record.get("archive_sha256"):
        out.append("decision must identify the exact candidate archive")
    try:
        if not isinstance(record.get("reviewed_at"), str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", record["reviewed_at"]
        ):
            raise ValueError("not a UTC ISO timestamp")
        date = datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
        offset = date.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            out.append("review date must be UTC")
    except (ValueError, TypeError, AttributeError, KeyError):
        out.append("review date must be a UTC ISO timestamp")
    if not modules or any(m.get("status") not in ("accepted", "rejected", "changes requested") for m in modules):
        out.append("every module requires an explicit review decision")
    if decision == "accepted" and any(m.get("status") != "accepted" for m in modules):
        out.append("acceptance requires all module decisions to be accepted")
    if any(not isinstance(m.get("disposition"), str) or not m["disposition"].strip() for m in modules):
        out.append("every module requires a disposition")
    out.extend(finding_problems(record.get("findings"), decision == "accepted"))
    return out


def finding_problems(findings: Any, accepting: bool = False) -> list[str]:
    if not isinstance(findings, list):
        return ["findings must be an explicit list, empty only when none were found"]
    out = []
    identifiers: set[str] = set()
    text_fields = (
        "id",
        "severity",
        "counterexample",
        "expected_result",
        "disposition",
        "regression_evidence",
        "compatibility_impact",
    )
    for finding in findings:
        if not isinstance(finding, dict):
            out.append("each finding must be an object")
            continue
        if any(not isinstance(finding.get(key), str) or not finding[key].strip() for key in text_fields):
            out.append("finding text fields must be nonblank strings")
        identifier = finding.get("id")
        if isinstance(identifier, str):
            if identifier in identifiers:
                out.append("finding identifiers must be unique")
            identifiers.add(identifier)
        iris = finding.get("affected_iris")
        if (
            not isinstance(iris, list)
            or not iris
            or any(not isinstance(iri, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*:[^\s]+", iri) for iri in iris)
        ):
            out.append("affected_iris must be a nonempty list of absolute IRIs")
        status = finding.get("status")
        if status not in ("resolved", "open", "not a defect", "accepted limitation"):
            out.append("each finding requires an explicit resolution status")
        elif accepting and status == "open":
            out.append("an accepted record cannot leave a finding open")
    return out
