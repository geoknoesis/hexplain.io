"""The physical and aspect layers name the same checksum algorithms.

Checksum algorithms were modelled three ways that nothing tied together: bddo individuals a
physical description names in bddo:checksumAlgorithm (crc16 .. sha256), concepts of the
checksum register an integrity aspect value comes from, and the aspect property itself. The
register lacked CRC-16 and Adler-32, so a format verified with either could describe its
check physically but not report it semantically. This gate keeps the sets aligned: every
bddo:ChecksumAlgorithm individual is skos:exactMatch of exactly one register concept and
vice versa, and bddo:ChecksumShape accepts exactly those individuals.
"""
import sys
from collections import defaultdict

from rdflib import RDF, Namespace
from rdflib.collection import Collection

import specgraph

BDDO = Namespace("https://hexplain.io/ns/bddo#")
RCK = Namespace("https://hexplain.io/ns/register/checksum#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
SH = Namespace("http://www.w3.org/ns/shacl#")


def main():
    g = specgraph.ontologies()
    algorithms = set(g.subjects(RDF.type, BDDO.ChecksumAlgorithm))
    concepts = set(g.subjects(SKOS.inScheme, RCK.ChecksumAlgorithmScheme))
    matches = defaultdict(set)
    for a, b in g.subject_objects(SKOS.exactMatch):
        matches[a].add(b)
        matches[b].add(a)
    failures = []
    for alg in sorted(algorithms):
        linked = matches[alg] & concepts
        if len(linked) != 1:
            failures.append(f"{alg} matches {len(linked)} checksum-register concepts, expected 1")
    for concept in sorted(concepts):
        linked = matches[concept] & algorithms
        if len(linked) != 1:
            failures.append(f"{concept} matches {len(linked)} bddo checksum algorithms, expected 1")
    accepted = set()
    for pshape in g.objects(BDDO.ChecksumShape, SH.property):
        if g.value(pshape, SH.path) == BDDO.checksumAlgorithm:
            for lst in g.objects(pshape, SH["in"]):
                accepted |= set(Collection(g, lst))
    if accepted != algorithms:
        failures.append(f"bddo:ChecksumShape accepts {sorted(map(str, accepted))} but the individuals are "
                        f"{sorted(map(str, algorithms))}")
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: {len(algorithms)} bddo checksum algorithms and the checksum register match one-to-one")


if __name__ == "__main__":
    main()
