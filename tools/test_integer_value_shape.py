"""One integer value shape, spelt once: every module's copy equals the shared template.

Shapes are validated module by module, so each module that ranges a property over integers
carries its own <prefix>:IntegerValueShape. specification/shared-patterns/integer-value-shape.json
lists those modules and integer-value-shape.ttl.template is the one spelling; this gate renders the
template per listed module and requires the result verbatim in the module's canonical Turtle.
A family module that declares an IntegerValueShape
without being listed, or declares it twice, fails.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from _family import canonical_files

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "specification/shared-patterns/integer-value-shape.json"
DECLARATION = re.compile(r"^\S*:IntegerValueShape a sh:NodeShape", re.M)


def rendered(template: str, prefix: str, ontology: str) -> str:
    body = "\n".join(line for line in template.splitlines() if not line.startswith("#")).strip() + "\n"
    if body.count("@PREFIX@") != 1 or body.count("@ONTOLOGY@") != 1:
        raise ValueError("the template names the prefix and the ontology exactly once each")
    return body.replace("@PREFIX@", prefix).replace("@ONTOLOGY@", ontology)


def problems() -> tuple[list[str], int]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    template = (ROOT / contract["template"]).read_text(encoding="utf-8")
    found, listed = [], set()
    for row in contract["copies"]:
        listed.add(row["file"])
        text = (ROOT / row["file"]).read_text(encoding="utf-8")
        if rendered(template, row["prefix"], row["ontology"]) not in text:
            found.append(f"{row['file']}: {row['prefix']}:IntegerValueShape differs from the shared template")
        if len(DECLARATION.findall(text)) != 1:
            found.append(f"{row['file']}: IntegerValueShape is declared {len(DECLARATION.findall(text))} times")
    if contract["master"] not in listed:
        found.append("the master module is not among the copies")
    family = canonical_files(ROOT / "specification")
    for rel in family:
        path = "specification/" + rel
        if path not in listed and DECLARATION.search((ROOT / path).read_text(encoding="utf-8")):
            found.append(f"{path}: declares an IntegerValueShape but is not listed in {CONTRACT.name}")
    return found, len(listed)


def self_test() -> None:
    template = "# comment\n@PREFIX@:IntegerValueShape a sh:NodeShape ;\n    rdfs:isDefinedBy <@ONTOLOGY@> .\n"
    assert rendered(template, "x", "urn:x") == "x:IntegerValueShape a sh:NodeShape ;\n    rdfs:isDefinedBy <urn:x> .\n"
    assert DECLARATION.search("x:IntegerValueShape a sh:NodeShape ;")
    assert not DECLARATION.search("    sh:node x:IntegerValueShape ;")


def main() -> int:
    self_test()
    found, count = problems()
    if found:
        print("FAIL:\n  " + "\n  ".join(found))
        return 1
    print(f"PASS: {count} modules carry the one IntegerValueShape, each equal to the shared template")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
