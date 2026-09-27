"""One authoritative table maps each family prefix to its namespace, ontology and directory.

The family's prefixes and namespaces drifted apart as modules were renamed: adv is the audio
namespace (/ns/audio#), the image vocabulary lives in directory idv but declares img
(/ns/image#), gv is /ns/geo#, hexplain /ns/core#, hxf /ns/fn#, and menc and usnato sit among the
r* register prefixes. None of that is renamed -- a published
namespace IRI or prefix is part of every description that uses it -- but a reader should not
have to discover it module by module. specification/family.json carries the table (its
"namespaces" list) and specification/ontology-design shows it (Namespace prefixes). This gate
requires, for every vocabulary module (a shapes document claims no prefix of its own):

  * exactly one row whose ontology, prefix, namespace, directory and file equal the module's
    owl:Ontology, vann:preferredNamespacePrefix, vann:preferredNamespaceUri and location;
  * no two rows sharing a prefix or a namespace, and no row without a module;
  * the ontology-design page listing every row.
"""
import json
import sys
from html import escape
from pathlib import Path

from rdflib import OWL, RDF, Graph, Namespace

ROOT = Path(__file__).resolve().parents[1]
VANN = Namespace("http://purl.org/vocab/vann/")
PAGE = ROOT / "specification/ontology-design/index.html"


def declared(files):
    """(file, ontology, prefix, namespace) for every module that claims a prefix."""
    out = []
    for rel in files:
        g = Graph().parse(data=(ROOT / "specification" / rel).read_text(encoding="utf-8"), format="turtle")
        for ontology in g.subjects(RDF.type, OWL.Ontology):
            prefix, uri = g.value(ontology, VANN.preferredNamespacePrefix), g.value(ontology, VANN.preferredNamespaceUri)
            if prefix is not None or uri is not None:
                out.append((rel, str(ontology), str(prefix), str(uri)))
    return out


def problems(rows, modules, page):
    found = []
    for key in ("prefix", "namespace", "ontology"):
        values = [r[key] for r in rows]
        for dup in sorted({v for v in values if values.count(v) > 1}):
            found.append(f"family.json namespaces: {key} {dup} appears in more than one row")
    by_file = {r["file"]: r for r in rows}
    for rel, ontology, prefix, uri in modules:
        row = by_file.get(rel)
        expected = dict(prefix=prefix, namespace=uri, ontology=ontology, directory=str(Path(rel).parent.as_posix()), file=rel)
        if row is None:
            found.append(f"{rel}: declares {prefix} -> {uri}, but family.json has no namespaces row for it")
        elif {k: row.get(k) for k in expected} != expected:
            found.append(f"{rel}: declares {expected}, but family.json says {row}")
    for rel in sorted(set(by_file) - {m[0] for m in modules}):
        found.append(f"family.json namespaces: row for {rel}, which claims no prefix")
    for r in rows:
        cell = f"<td><code>{escape(r['prefix'])}</code></td><td><code>{escape(r['namespace'])}</code></td>"
        if cell not in page:
            found.append(f"{PAGE.relative_to(ROOT).as_posix()}: the namespace table lacks {r['prefix']} -> {r['namespace']}; "
                         "run python tools/_build_ontology_docs.py")
    return found


def self_test():
    rows = [dict(prefix="x", namespace="urn:x#", ontology="urn:x", directory="x", file="x/x.ttl"),
            dict(prefix="x", namespace="urn:y#", ontology="urn:y", directory="y", file="y/y.ttl")]
    modules = [("x/x.ttl", "urn:x", "x", "urn:x#"), ("y/y.ttl", "urn:y", "y", "urn:y#")]
    found = problems(rows, modules, "")
    assert any("prefix x appears" in f for f in found) and any("y/y.ttl: declares" in f for f in found), found


def main():
    self_test()
    family = json.loads((ROOT / "specification/family.json").read_text(encoding="utf-8"))
    rows = family.get("namespaces")
    if not isinstance(rows, list):
        print("FAIL: specification/family.json has no namespaces table")
        return 1
    found = problems(rows, declared(family["files"]), PAGE.read_text(encoding="utf-8"))
    if found:
        print("FAIL:\n  " + "\n  ".join(found))
        return 1
    print(f"PASS: {len(rows)} prefix/namespace/ontology/directory rows in family.json match every module's "
          "declaration and the ontology-design table")
    return 0


if __name__ == "__main__":
    sys.exit(main())
