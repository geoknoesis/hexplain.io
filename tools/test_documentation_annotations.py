"""Documentation annotations say something, once, in prose.

The generated term documentation (tools/_build_term_reference.py --enrich) used to copy what the
source already said and to fill gaps with templates. A review counted 267 terms whose
skos:definition repeated their rdfs:comment word for word, 140 shape definitions opening "A
reusable validation contract for", 987 templated scope notes, and six definitions that had
copied a SPARQL message with its result variables -- "{?s} declares {?np} parameter(s)" -- into
prose. The block itself was appended as N-Triples in the middle of hand-written Turtle.

This gate holds the family to the rule in specification/ontology-design (Documentation
annotations):

  * no rdfs:label, rdfs:comment, skos:definition or skos:scopeNote of a family term contains a
    SPARQL placeholder ({?x} or {$x});
  * no term has a skos:definition equal to one of its rdfs:comment values;
  * no definition starts with the old template opener, and no scope note is one of the retired
    template sentences;
  * the generated block of every module is Turtle written with prefixed names, not N-Triples.
"""
import json
import re
import sys
from pathlib import Path

from rdflib import RDFS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
MARKER = "\n# BEGIN GENERATED TERM DOCUMENTATION\n"
PLACEHOLDER = re.compile(r"\{[?$][A-Za-z_]\w*\}")
PROSE = (RDFS.label, RDFS.comment, SKOS.definition, SKOS.scopeNote)
TEMPLATE_OPENERS = ("A reusable validation contract",)
TEMPLATE_NOTES = ("Validation activation:", "Use it as a predicate.", "Assert this class on a resource representing the defined entity.",
                  "Use this IRI as a controlled value where the profile or a shape accepts its declared type.",
                  "Use as a controlled value or grouping in this register.")
NTRIPLE = re.compile(r"^<[^>\s]+>\s+<[^>\s]+>\s", re.M)


def problems(g):
    found = []
    for predicate in PROSE:
        for term, text in g.subject_objects(predicate):
            if not isinstance(term, URIRef) or not str(term).startswith("https://hexplain.io/ns/"):
                continue
            where = f"{term} {predicate.n3(g.namespace_manager)}"
            if PLACEHOLDER.search(str(text)):
                found.append(f"{where} contains a SPARQL placeholder: {str(text)[:120]}")
            if predicate == SKOS.definition and str(text).startswith(TEMPLATE_OPENERS):
                found.append(f"{where} is the retired template: {str(text)[:80]}")
            if predicate == SKOS.scopeNote and any(n in str(text) for n in TEMPLATE_NOTES):
                found.append(f"{where} is a retired template sentence: {str(text)[:80]}")
    for term, definition in g.subject_objects(SKOS.definition):
        if isinstance(term, URIRef) and any(str(c).strip() == str(definition).strip() for c in g.objects(term, RDFS.comment)):
            found.append(f"{term}: skos:definition repeats its rdfs:comment verbatim")
    return found


def self_test():
    g = Graph().parse(format="turtle", data="""
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        <https://hexplain.io/ns/x#a> rdfs:comment "Same." ; skos:definition "Same."@en .
        <https://hexplain.io/ns/x#b> skos:definition "{?s} declares {?n} things." .
        <https://hexplain.io/ns/x#c> skos:definition "A reusable validation contract for x." ;
            skos:scopeNote "Use it as a predicate. More." .""")
    assert len(problems(g)) == 4, problems(g)
    assert NTRIPLE.search("<https://hexplain.io/ns/x#a> <http://www.w3.org/2000/01/rdf-schema#label> \"a\" .")


def main():
    self_test()
    files = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))["files"]
    whole, found = Graph(), []
    for rel in files:
        text = (ROOT / "specification" / rel).read_text(encoding="utf-8")
        whole.parse(data=text, format="turtle")
        if MARKER not in text:
            found.append(f"{rel}: no generated documentation block")
        elif NTRIPLE.search(text.split(MARKER, 1)[1]):
            found.append(f"{rel}: the generated documentation block is written as N-Triples; regenerate it")
    found += problems(whole)
    if found:
        print("FAIL:\n  " + "\n  ".join(found[:80]) + (f"\n  ... and {len(found) - 80} more" if len(found) > 80 else ""))
        return 1
    print(f"PASS: documentation annotations of {len(files)} modules hold no placeholder, repeat no comment, "
          "use no retired template and are written as prefixed Turtle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
