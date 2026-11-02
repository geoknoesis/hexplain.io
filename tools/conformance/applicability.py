"""Shared case applicability for execution and implementation-report validation."""

from __future__ import annotations

from typing import Any

from suite import BASE_ENCODINGS, ENCODING_NAMESPACE

Manifest = dict[str, Any]
Claims = dict[str, Any]


def class_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """A class absent from an explicit claims statement does not apply."""
    if claims is None:
        return None
    cls = manifest["class"]
    name = " ".join(word.upper() if word == "hdl" else word.title() for word in cls.split("-"))
    if cls == "writer":
        if "Physical Parser" in claims.get("classes", []) and "writer" in claimed_features(claims):
            return None
        return "the claims statement does not claim the Physical Parser writer feature"
    return None if name in claims.get("classes", []) else f"the claims statement does not claim {name}"


def claimed_features(claims: Claims) -> set[str]:
    value = claims.get("optionalFeatures", {})
    if isinstance(value, dict):
        return {k for k, v in value.items() if (v.get("claimed") if isinstance(v, dict) else v)}
    return set(value)


def claimed_codecs(claims: Claims) -> set[str]:
    """The codec IRIs a claims statement lists: its "codecs" member is an array of IRIs."""
    value = claims.get("codecs", [])
    return set(value) if isinstance(value, list) else set()


def claimed_encodings(claims: Claims) -> set[str]:
    """The text encodings a claims statement states: the five every Physical Parser decodes, and the further ones
    its "encodings" member lists, an array of bddo:Encoding IRIs. A statement without the member lists none."""
    value = claims.get("encodings", [])
    listed = set(value) if isinstance(value, list) else set()
    return listed | {ENCODING_NAMESPACE + name for name in BASE_ENCODINGS}


def skip_reason(manifest: Manifest, claims: Claims | None, template: str) -> str | None:
    """Why a case does not apply to the implementation the claims describe, or None when it does."""
    return (
        class_skip(manifest, claims)
        or _feature_skip(manifest, claims)
        or _codec_skip(manifest, claims)
        or _encoding_skip(manifest, claims)
        or _template_skip(manifest, template)
    )


def _feature_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """Why the optional features the case requires or checks the refusal of rule it out, or None."""
    features = claimed_features(claims) if claims is not None else None
    wanted = manifest.get("features", {})
    if wanted.get("requires"):
        if features is None:
            return f"requires {wanted['requires']}, and no --claims statement says which features are claimed"
        missing = [f for f in wanted["requires"] if f not in features]
        if missing:
            return f"requires unclaimed feature(s) {missing}"
    if wanted.get("unclaimed"):
        if features is None:
            return "checks the refusal of an unclaimed feature, and no --claims statement is given"
        present = [f for f in wanted["unclaimed"] if f in features]
        if present:
            return f"checks the refusal of {present}, which the implementation claims"
    return None


def _codec_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """Why the codecs the case requires or checks the refusal of rule it out, or None."""
    codecs = manifest.get("codecs", {})
    if not codecs:
        return None
    if claims is None:
        return "names codecs, and no --claims statement says which codecs are claimed"
    listed = claimed_codecs(claims)
    missing = [c for c in codecs.get("requires", []) if c not in listed]
    if missing:
        return f"requires codec(s) {missing} the implementation does not list"
    present = [c for c in codecs.get("unclaimed", []) if c in listed]
    if present:
        return f"checks the refusal of codec(s) {present}, which the implementation lists"
    return None


def _encoding_skip(manifest: Manifest, claims: Claims | None) -> str | None:
    """Why the text encodings the case requires or checks the refusal of rule it out, or None."""
    encodings = manifest.get("encodings", {})
    if not encodings:
        return None
    if claims is None:
        return "names text encodings, and no --claims statement says which encodings are supported"
    listed = claimed_encodings(claims)
    missing = [e for e in encodings.get("requires", []) if e not in listed]
    if missing:
        return f"requires text encoding(s) {missing} the implementation does not list"
    present = [e for e in encodings.get("unclaimed", []) if e in listed]
    if present:
        return f"checks the refusal of text encoding(s) {present}, which the implementation lists"
    return None


def _template_skip(manifest: Manifest, template: str) -> str | None:
    """Why the command template lacks a placeholder the case needs, or None."""
    withdraw = manifest.get("claims", {}).get("withdraw", [])
    if withdraw and "{withdraw}" not in template:
        return f"runs without {withdraw}; the command template has no {{withdraw}} placeholder"
    if manifest.get("cells") and "{cells}" not in template:
        return f"asks for the cells of {manifest['cells']}; the command template has no {{cells}} placeholder"
    return None
