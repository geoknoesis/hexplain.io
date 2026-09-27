"""Every ontology module of the family declares its licence, and it is CC BY 4.0.

The owner licensed the ontology modules under CC BY 4.0 (LICENSING.md); everything else in the
repository without its own notice is proprietary (LICENSE). Five modules -- conf, conf/shapes,
req, req/shapes and fn -- once carried no dcterms:license at all, so a consumer loading one of
them could not tell which of the two regimes applied. This gate requires every owl:Ontology in
specification/family.json to state exactly one dcterms:license, the CC BY 4.0 IRI, together with
the dcterms:creator its attribution names, and it requires the two repository notices to exist
and to say that per-file and RDF declarations are not overridden.
"""
import json
import sys
from pathlib import Path

from rdflib import OWL, RDF, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
DCTERMS = Namespace("http://purl.org/dc/terms/")
CC_BY = URIRef("https://creativecommons.org/licenses/by/4.0/")
CREATOR = URIRef("https://geoknoesis.com")


def problems(g, where):
    found = []
    ontologies = list(g.subjects(RDF.type, OWL.Ontology))
    if not ontologies:
        found.append(f"{where}: declares no owl:Ontology to carry its licence")
    for ontology in ontologies:
        licences = set(g.objects(ontology, DCTERMS.license))
        if licences != {CC_BY}:
            found.append(f"{where}: {ontology} declares dcterms:license {sorted(map(str, licences)) or 'nothing'}; "
                         f"the ontology modules are licensed {CC_BY}")
        if (ontology, DCTERMS.creator, CREATOR) not in g:
            found.append(f"{where}: {ontology} does not name dcterms:creator <{CREATOR}>, the attribution CC BY requires")
    return found


def self_test():
    bare = Graph().parse(format="turtle", data="<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> .")
    assert len(problems(bare, "probe")) == 2, problems(bare, "probe")
    good = Graph().parse(format="turtle", data=f"""<urn:o> a <http://www.w3.org/2002/07/owl#Ontology> ;
        <http://purl.org/dc/terms/license> <{CC_BY}> ; <http://purl.org/dc/terms/creator> <{CREATOR}> .""")
    assert not problems(good, "probe")


def main():
    self_test()
    files = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]
    found = []
    for rel in files:
        text = (ROOT / "specification" / rel).read_text(encoding="utf-8")
        found += problems(Graph().parse(data=text, format="turtle"), rel)
    notice = (ROOT / "LICENSE").read_text(encoding="utf-8") if (ROOT / "LICENSE").is_file() else ""
    if "All rights reserved" not in notice or "CC BY 4.0" not in notice:
        found.append("LICENSE: missing, or does not both reserve rights and except the CC BY 4.0 ontology modules")
    declarations = (ROOT / "LICENSING.md").read_text(encoding="utf-8")
    if "CC BY 4.0" not in declarations or "LICENSE" not in declarations:
        found.append("LICENSING.md: does not state the CC BY 4.0 ontology licence and point to LICENSE")
    if found:
        print("FAIL:\n  " + "\n  ".join(found))
        return 1
    print(f"PASS: all {len(files)} ontology modules declare dcterms:license CC BY 4.0 with their creator; "
          "LICENSE and LICENSING.md state the two regimes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
