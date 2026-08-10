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

import glob
import pathlib
import re
import sys

import rdflib

#: Prefix -> namespace, for the vocabularies this project owns.
PREFIXES = {
    "bddo": "https://hexplain.io/ns/bddo#",
    "dlv": "https://hexplain.io/ns/dlv#",
    "hexplain": "https://hexplain.io/ns/core#",
    "gv": "https://hexplain.io/ns/geo#",
    "adv": "https://hexplain.io/ns/audio#",
    "idv": "https://hexplain.io/ns/image#",
    "vdv": "https://hexplain.io/ns/video#",
    "npv": "https://hexplain.io/ns/net#",
    "dfv": "https://hexplain.io/ns/docfont#",
    "axv": "https://hexplain.io/ns/archive#",
    "asec": "https://hexplain.io/ns/aspect/security#",
    "araster": "https://hexplain.io/ns/aspect/raster#",
    "asamp": "https://hexplain.io/ns/aspect/sampling#",
    "asref": "https://hexplain.io/ns/aspect/spatialref#",
    "abnd": "https://hexplain.io/ns/aspect/bundle#",
    "aenc": "https://hexplain.io/ns/aspect/encoding#",
    "ageom": "https://hexplain.io/ns/aspect/geometry#",
    "acolor": "https://hexplain.io/ns/aspect/color#",
    "atime": "https://hexplain.io/ns/aspect/time#",
    "aprov": "https://hexplain.io/ns/aspect/provenance#",
    "apc": "https://hexplain.io/ns/aspect/pointcloud#",
    "atab": "https://hexplain.io/ns/aspect/tabular#",
    "asig": "https://hexplain.io/ns/aspect/signal#",
    "aint": "https://hexplain.io/ns/aspect/integrity#",
    "rpr": "https://hexplain.io/ns/register/part-role#",
    "menc": "https://hexplain.io/ns/register/media-encoding#",
    "usnato": "https://hexplain.io/ns/register/us-nato-security#",
}

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


def defined_terms():
    """Every subject IRI declared anywhere in the specification, excluding fixtures."""
    out = set()
    for path in glob.glob("specification/**/*.ttl", recursive=True):
        if "/test/" in path.replace("\\", "/"):
            continue
        g = rdflib.Graph()
        try:
            g.parse(data=pathlib.Path(path).read_text(encoding="utf-8"), format="turtle")
        except Exception as exc:  # noqa: BLE001 -- validate_all reports parse errors properly
            print(f"WARN: {path} did not parse ({exc}); its terms will look undefined")
            continue
        out |= {str(s) for s in set(g.subjects()) if isinstance(s, rdflib.URIRef)}
    return out


def main():
    defined = defined_terms()
    if len(defined) < 300:
        print(f"FAIL: only {len(defined)} terms collected -- wrong working directory?")
        return 1

    problems = []
    checked = 0
    docs = sorted(glob.glob("specification/**/*.html", recursive=True))
    for doc in docs:
        if doc.replace("\\", "/") in SKIP_DOCS:
            continue
        prose = PRE.sub(" ", pathlib.Path(doc).read_text(encoding="utf-8"))
        for prefix, ns in PREFIXES.items():
            for local in sorted(set(re.findall(rf"\b{prefix}:([A-Za-z][A-Za-z0-9_]*)", prose))):
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
