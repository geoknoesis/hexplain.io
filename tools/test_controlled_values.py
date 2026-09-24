"""Each controlled value follows one of the three documented idioms.

The family used to mix idioms for the same kind of thing: some closed value sets were OWL
individuals checked with sh:in, some were individuals nothing constrained, some were SKOS
concepts inside a vocabulary. specification/ontology-design (Controlled values) now documents
one idiom per category:

  A. CLOSED ENUMERATION inside a vocabulary: an owl:Class, individuals typed with it, and a
     shape that lists every individual in sh:in (bddo:Endianness, conf:FindingKind,
     hexplain:RegisterStatus). Adding a value is a vocabulary change.
  B. OPEN INDIVIDUAL SET inside a vocabulary: an owl:Class whose individuals other modules and
     profiles may extend, constrained with sh:class (bddo:DataType primitives, dlv:Axis, the hxf
     function catalogue). The class is listed in OPEN_CLASSES below with its reason.
  C. SWAPPABLE VALUES: skos:Concept in a register module, reached through a property whose
     range is skos:Concept and bound per profile (codecs, part roles, security markings).

A format's wire codes are none of these: they belong in its profile.

The gate checks every individual of a Hexplain class outside the registers (idiom A or B) and
that every skos:Concept lives in a register (idiom C). Values that predate the policy and do not
fit are listed in LEGACY with the reason they are kept; the list may shrink but must not grow.
"""
import json
import sys
from pathlib import Path

from rdflib import OWL, RDF, Graph, Namespace, URIRef
from rdflib.collection import Collection

ROOT = Path(__file__).resolve().parents[1]
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
SH = Namespace("http://www.w3.org/ns/shacl#")
HX = "https://hexplain.io/ns/"

OPEN_CLASSES = {
    HX + "bddo#DataType": "profiles declare their own primitive data types (nitf:BCSA, ...)",
    HX + "dlv#Axis": "domain vocabularies add axes (audio#axisSample, geo#axisLatitude, ...)",
    HX + "fn#Function": "the function catalogue grows by addition; each function is its own resource",
}
LEGACY = {
    HX + "bddo#integer": "bddo:BaseType values predate the policy; the base-type shape checks by class",
    HX + "bddo#float": "bddo:BaseType values predate the policy; the base-type shape checks by class",
    HX + "dlv#rowMajor": "dlv:ChunkOrder values predate the policy; the Processing Model closes the set",
    HX + "dlv#columnMajor": "dlv:ChunkOrder values predate the policy; the Processing Model closes the set",
    HX + "dlv#morton": "dlv:ChunkOrder values predate the policy; the Processing Model closes the set",
    HX + "dlv#hilbert": "dlv:ChunkOrder values predate the policy; the Processing Model closes the set",
    HX + "fn#Pure": "hxf:Kind is checked with sh:hasValue in NativeFunctionShape",
    HX + "fn#Native": "hxf:Kind is checked with sh:hasValue in NativeFunctionShape",
}


def main():
    files = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]
    graphs = {f: Graph().parse(data=(ROOT / "specification" / f).read_text(encoding="utf-8"), format="turtle")
              for f in files}
    whole = Graph()
    for g in graphs.values():
        whole += g
    closed = set()
    for head in whole.objects(None, SH["in"]):
        closed |= set(Collection(whole, head))
    classes = {c for c in whole.subjects(RDF.type, OWL.Class) if str(c).startswith(HX)}
    failures, seen_legacy, counted = [], set(), 0
    for f, g in sorted(graphs.items()):
        register = f.startswith("register/")
        for concept in set(g.subjects(RDF.type, SKOS.Concept)) | set(g.subjects(SKOS.inScheme, None)):
            if not register:
                failures.append(f"{f}: skos:Concept {concept} outside a register (idiom C puts concepts in registers)")
        if register:
            continue
        for s, cls in g.subject_objects(RDF.type):
            if cls not in classes or not isinstance(s, URIRef) or (s, RDF.type, OWL.Class) in whole:
                continue
            counted += 1
            if s in closed or str(cls) in OPEN_CLASSES:
                continue
            if str(s) in LEGACY:
                seen_legacy.add(str(s))
                continue
            failures.append(f"{f}: {s} is an individual of {cls} but is neither listed in an sh:in "
                            f"(idiom A) nor of a class in OPEN_CLASSES (idiom B)")
    for stale in sorted(set(LEGACY) - seen_legacy):
        failures.append(f"LEGACY lists {stale}, which now follows an idiom or no longer exists (remove it)")
    for cls in sorted(OPEN_CLASSES):
        if URIRef(cls) not in classes:
            failures.append(f"OPEN_CLASSES lists {cls}, which is not a Hexplain class")
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: {counted} vocabulary individuals follow idiom A or B ({len(LEGACY)} legacy exceptions); "
          f"every skos:Concept is in a register")


if __name__ == "__main__":
    main()
