"""Every Hexplain term named in specification PROSE must actually exist.

test_html_sync guarantees the Turtle EMBEDDED in each page matches its .ttl. Nothing checked
the prose around it, which is most of what a reader reads — so a term could be renamed in the
ontology, faithfully re-embedded by the sync gate, and left dangling in the paragraph that
explains it.

That is not hypothetical. This check was written after finding three at once: hx-bundle's part
roles had moved to the part-role register, so the HDL document still resolved `role X` to
`abnd:X`; the family index still advertised `gv:platformName` and `gv:acquisitionTime` in its
worked example, two years after both moved to hx-provenance; and a raw-turtle example used
`ageom:crs`, a term that has never existed anywhere. All three read perfectly well. Prose is
where stale names hide, because nothing parses it.

Only the Hexplain namespaces are checked. External CURIEs (dcterms:, skos:, prov:, xsd:) are
someone else's vocabulary and not ours to verify.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import rdflib

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Every namespace this project owns is under this IRI.
HEXPLAIN_NS = "https://hexplain.io/ns/"
#: A Turtle prefix declaration of a Hexplain namespace (the empty prefix names no vocabulary in prose).
PREFIX_DECLARATION = re.compile(r"@prefix\s+([A-Za-z][\w.-]*):\s*<(" + re.escape(HEXPLAIN_NS) + r"[^>]*)>")


def hexplain_prefixes() -> tuple[dict[str, str], list[str]]:
    """Prefix -> namespace for the vocabularies this project owns, and the conflicts found building it.

    The table is not written by hand -- a hand-written one fell behind the family (it missed conf:, req:, hxf:, the
    newer aspects and registers, and kept prefixes no module declares any more), and every reference under a missing
    prefix went unchecked. It is the union of family.json's authoritative namespace table and every @prefix
    declaration bound under https://hexplain.io/ns/ in the family's canonical Turtle (family.json "files"), so a
    prefix a module declares is checked from the day it is declared. A prefix bound to two namespaces is a conflict.
    """
    family = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))
    bindings: dict[str, set[str]] = {}
    for row in family.get("namespaces", []):
        bindings.setdefault(row["prefix"], set()).add(row["namespace"])
    for name in family["files"]:
        text = (ROOT / "specification" / name).read_text(encoding="utf-8")
        for prefix, namespace in PREFIX_DECLARATION.findall(text):
            bindings.setdefault(prefix, set()).add(namespace)
    table = {prefix: min(namespaces) for prefix, namespaces in sorted(bindings.items())}
    conflicts = [
        f"the prefix {prefix}: is bound to {sorted(namespaces)} in the family"
        for prefix, namespaces in sorted(bindings.items())
        if len(namespaces) > 1
    ]
    return table, conflicts


PREFIXES, PREFIX_CONFLICTS = hexplain_prefixes()

#: Names that appear in prose on purpose without being real terms.
ALLOWED = {
    # The neutrality principle needs a counter-example to name what must NOT exist.
    "bddo:nitfSecurityBlock",
}

#: Documents that PROPOSE names rather than reference them. specification/review.html is a
#: point-in-time engineering review arguing for terms later implemented under different names --
#: "properties such as bddo:atAbsoluteOffset / bddo:atRelativeOffset" became bddo:atOffset plus
#: an offset base. Naming what was proposed is correct there; rewriting a review to match what
#: shipped would falsify the record.
SKIP_DOCS = {"specification/review.html"}

#: The embedded normative Turtle is test_html_sync's job, not this one's.
PRE = re.compile(r'<pre class="nohighlight">.*?</pre>', re.S)


def repository_files(pattern: str) -> list[str]:
    """Repository-relative POSIX paths matching ``pattern``, wherever the gate is started from."""
    return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern) if p.is_file())


def defined_terms() -> set[str]:
    """Every subject IRI declared anywhere in the specification, excluding fixtures."""
    out = set()
    for path in repository_files("specification/**/*.ttl"):
        if "/test/" in path:
            continue
        g = rdflib.Graph()
        try:
            g.parse(data=(ROOT / path).read_text(encoding="utf-8"), format="turtle")
        except Exception as exc:  # noqa: BLE001 -- validate_all reports parse errors properly
            print(f"WARN: {path} did not parse ({exc}); its terms will look undefined")
            continue
        out |= {str(s) for s in set(g.subjects()) if isinstance(s, rdflib.URIRef)}
    return out


def table_problems() -> list[str]:
    """Why the prefix table is not the family's Hexplain prefixes, if it is not."""
    if PREFIX_CONFLICTS:
        return PREFIX_CONFLICTS
    # The table is the family's: the vocabularies the hand-written table missed are in it, and the prefixes no
    # module declares (aint:, idv:, superseded by aintg: and img:) are not.
    missed = ("conf", "req", "hxf", "afs", "apkg", "anet", "aintg", "aprot", "rprot", "rgeo", "rcol", "rck", "img")
    problems = [
        f"the family declares {p}:, but the prefix table does not check it" for p in missed if p not in PREFIXES
    ]
    problems += [f"{p}: is in the prefix table, but no module declares it" for p in ("aint", "idv") if p in PREFIXES]
    problems += [
        f"{prefix}: ({ns}) is not a Hexplain prefix"
        for prefix, ns in PREFIXES.items()
        if not ns.startswith(HEXPLAIN_NS) or not prefix
    ]
    if len(PREFIXES) < 30:
        problems.append(f"only {len(PREFIXES)} prefixes collected from the family")
    return problems


def main() -> int:
    # A CURIE inside a longer absolute IRI is not a prose vocabulary reference.
    # In particular, urn:hexplain:security-example:Marked is not hexplain:security.
    # A dotted local name (menc:Cipher.keyRef, a parameter shared by several contracts) is one term;
    # a sentence-ending full stop is not part of the name.
    # A hyphenated local name (reqs:req-shape-bddo-StructShape, a requirement individual) is one term too.
    def names(text: str, prefix: str) -> set[str]:
        local = r"[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z0-9_]+|[.][A-Za-z][A-Za-z0-9_]*)*"
        return set(re.findall(rf"(?<![\w:/#.-]){re.escape(prefix)}:({local})", text))

    assert names("urn:hexplain:security-example:Marked", "hexplain") == set()
    assert names("https://example.org/dlv:Unrelated", "dlv") == set()
    assert names("<code>dlv:MissingTerm</code> (dlv:Dimension)", "dlv") == {"MissingTerm", "Dimension"}
    assert names("menc:Cipher.keyRef and dlv:Dimension. Next", "menc") == {"Cipher.keyRef"}
    assert names("reqs:req-shape-st-CountShape a reqs:ShapeRequirement", "reqs") == {
        "req-shape-st-CountShape",
        "ShapeRequirement",
    }
    assert names("a dlv:Dimension-wide rule; dlv:Dimension- ", "dlv") == {"Dimension-wide", "Dimension"}
    table = table_problems()
    if table:
        print("FAIL:\n  " + "\n  ".join(table))
        return 1
    defined = defined_terms()
    if len(defined) < 300:
        print(f"FAIL: only {len(defined)} terms collected from specification/")
        return 1

    problems = []
    checked = 0
    docs = repository_files("specification/**/*.html")
    for doc in docs:
        if doc in SKIP_DOCS:
            continue
        prose = PRE.sub(" ", (ROOT / doc).read_text(encoding="utf-8"))
        for prefix, ns in PREFIXES.items():
            for local in sorted(names(prose, prefix)):
                curie = f"{prefix}:{local}"
                if curie in ALLOWED:
                    continue
                checked += 1
                if ns + local not in defined:
                    problems.append(
                        f"{doc}: prose names {curie}, which no ontology defines. Either it was "
                        f"renamed and the prose was not updated, or it never existed."
                    )

    if not docs:
        print("FAIL: no specification documents found")
        return 1
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(f"PASS: {checked} Hexplain term references across {len(docs)} document(s) all resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
