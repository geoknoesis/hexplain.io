"""Register entries have a lifecycle, and no entry a release published ever disappears.

A register concept is a value that data written years ago still carries, so a policy change
must never delete, rename or reuse its IRI. It is deprecated instead: owl:deprecated true, a
hexplain:status of statusDeprecated or statusSuperseded, a skos:historyNote or skos:changeNote
saying what changed, and, when superseded, dcterms:isReplacedBy naming a current entry of the
same register. This gate checks those rules for every register module, that no scheme carries
its own owl:versionInfo (the register ontology's version is the only version; a scheme-level
"1.0" inside a 1.1 register contradicted it), that a current ordered collection lists no
deprecated member, and that every register IRI of the latest snapshot is still defined. A
valid entry is never deprecated, no entry replaces itself, and a deprecated entry is neither a
member of a current skos:Collection nor a top concept of its scheme (it stays skos:inScheme).
The same rules are shapes of the core vocabulary (hexplain:RegisterStatusShape,
hexplain:RegisterLifecycleShape), so a register published elsewhere is checked by SHACL alone.
"""
import json
import sys
import zipfile
from pathlib import Path

from rdflib import OWL, RDF, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection

ROOT = Path(__file__).resolve().parents[1]
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
HEX = Namespace("https://hexplain.io/ns/core#")
DCT = Namespace("http://purl.org/dc/terms/")
RETIRED = {HEX.statusDeprecated, HEX.statusSuperseded}
STATUSES = RETIRED | {HEX.statusValid}


def register_files():
    files = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]
    return [f"specification/{f}" for f in files if f.startswith("register/")]


def is_true(value):
    return isinstance(value, Literal) and value.toPython() is True


def check(path, g, failures):
    ontologies = set(g.subjects(RDF.type, OWL.Ontology))
    for s in set(g.subjects(OWL.versionInfo)) - ontologies:
        failures.append(f"{path}: {s} carries its own owl:versionInfo; only the register ontology is versioned")
    deprecated = {s for s, o in g.subject_objects(OWL.deprecated) if is_true(o)}
    for s, status in g.subject_objects(HEX.status):
        if status not in STATUSES:
            failures.append(f"{path}: {s} has hexplain:status {status}, not one of the closed set")
        if status in RETIRED and s not in deprecated:
            failures.append(f"{path}: {s} is {status.split('#')[-1]} but not owl:deprecated true")
        if status == HEX.statusValid and s in deprecated:
            failures.append(f"{path}: {s} is statusValid but owl:deprecated true")
    defined = {s for s in g.subjects(RDF.type) if isinstance(s, URIRef)}
    for s in sorted(deprecated):
        statuses = set(g.objects(s, HEX.status))
        if not statuses & RETIRED:
            failures.append(f"{path}: deprecated {s} states no hexplain:status statusDeprecated or statusSuperseded")
        if not (list(g.objects(s, SKOS.historyNote)) or list(g.objects(s, SKOS.changeNote))):
            failures.append(f"{path}: deprecated {s} has no skos:historyNote or skos:changeNote")
        successors = list(g.objects(s, DCT.isReplacedBy))
        if HEX.statusSuperseded in statuses and not successors:
            failures.append(f"{path}: superseded {s} names no dcterms:isReplacedBy")
        for n in successors:
            if n == s:
                failures.append(f"{path}: {s} is replaced by itself")
            elif n not in defined:
                failures.append(f"{path}: {s} is replaced by {n}, which this register does not define")
            elif n in deprecated:
                failures.append(f"{path}: {s} is replaced by {n}, which is itself deprecated")
    for coll in g.subjects(RDF.type, SKOS.OrderedCollection):
        if coll in deprecated:
            continue
        for head in g.objects(coll, SKOS.memberList):
            for member in Collection(g, head):
                if member in deprecated:
                    failures.append(f"{path}: current ordered collection {coll} lists deprecated {member}")
    # A current grouping, and a scheme's top level, offer current entries only; a retired entry
    # stays skos:inScheme so data that carries it keeps validating.
    for coll in set(g.subjects(RDF.type, SKOS.Collection)) - deprecated:
        for member in g.objects(coll, SKOS.member):
            if member in deprecated:
                failures.append(f"{path}: current collection {coll} lists deprecated {member}")
    for s in deprecated:
        for scheme in set(g.objects(s, SKOS.topConceptOf)) | set(g.subjects(SKOS.hasTopConcept, s)):
            failures.append(f"{path}: deprecated {s} is still a top concept of {scheme}")
    return defined


def snapshot_terms(paths):
    """Register IRIs defined by the newest pinned snapshot that contains these files."""
    manifests = sorted((ROOT / "releases").glob("*/manifest.json"))
    if not manifests:
        return None, {}
    latest = manifests[-1]
    manifest = json.loads(latest.read_text(encoding="utf-8"))
    out = {}
    with zipfile.ZipFile(latest.parent / manifest["archive"]) as archive:
        for path in paths:
            if path in archive.namelist():
                g = Graph().parse(data=archive.read(path).decode("utf-8"), format="turtle")
                out[path] = {s for s in g.subjects(RDF.type) if isinstance(s, URIRef)}
    return latest.parent.name, out


def _self_test():
    """Each rule must notice its defect, or passing proves nothing."""
    g = Graph().parse(format="turtle", data="""
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
        @prefix h: <https://hexplain.io/ns/core#> . @prefix dct: <http://purl.org/dc/terms/> .
        <urn:S> a skos:ConceptScheme .
        <urn:valid> a skos:Concept ; skos:inScheme <urn:S> ; h:status h:statusValid ; owl:deprecated true .
        <urn:self> a skos:Concept ; skos:inScheme <urn:S> ; skos:topConceptOf <urn:S> ; owl:deprecated true ;
            h:status h:statusSuperseded ; dct:isReplacedBy <urn:self> ; skos:historyNote "x" .
        <urn:C> a skos:Collection ; skos:member <urn:self> .""")
    found = []
    check("probe", g, found)
    for needle in ("statusValid but owl:deprecated", "replaced by itself", "current collection", "still a top concept"):
        assert any(needle in f for f in found), (needle, found)


def main():
    _self_test()
    failures = []
    paths = register_files()
    current = {}
    for path in paths:
        g = Graph().parse(data=(ROOT / path).read_text(encoding="utf-8"), format="turtle")
        current[path] = check(path, g, failures)
    release, published = snapshot_terms(paths)
    for path, terms in published.items():
        for term in sorted(terms - current.get(path, set())):
            failures.append(f"{path}: {term} was published in snapshot {release} and is no longer defined")
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    retired = sum(1 for p in paths for _ in Graph().parse(data=(ROOT / p).read_text(encoding="utf-8"),
                  format="turtle").subject_objects(HEX.status))
    print(f"PASS: {len(paths)} registers; {retired} entries state a lifecycle status; no scheme-level version; "
          f"every register IRI of snapshot {release} is still defined")


if __name__ == "__main__":
    main()
