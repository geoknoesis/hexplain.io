"""Structured record, member and collection-item witnesses for the structure aspect."""

from __future__ import annotations

from typing import Any

from _cases import prefix_block, row, term

PREFIX = prefix_block({"st": "structure", "ex": "urn:structure-contract:", "xsd": "xsd"}, " ")
MODULE = "aspect/structure/structure.ttl"


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(name: str, body: str, ok: bool, path: str = "") -> None:
        rows.append(row("structure " + name, MODULE, PREFIX + body, ok, term("structure", path) if path else ""))

    record = 'ex:r a st:Record; st:recordType "Row"; st:hasMember ex:m. '
    add("record with named member", record + 'ex:m a st:Member; st:name "id"; st:identifier 1; st:value 7.', True)
    add("member activated by its name", 'ex:m st:name "id"; st:value "x".', True)
    add("item with sized identifier", 'ex:c st:hasItem ex:i. ex:i a st:Item; st:identifier "3"^^xsd:unsignedInt.', True)
    add("nested record value", record + 'ex:m a st:Member; st:name "inner"; st:value ex:r2. ex:r2 a st:Record.', True)
    add("enumeration symbol", 'ex:m st:name "kind"; st:symbol "PLAIN"; st:dataType "int32".', True)
    for label, value, ok in [
        ("zero", "0", True),
        ("sized", '"4096"^^xsd:unsignedLong', True),
        ("negative", "-1", False),
        ("decimal", "1.5", False),
        ("string", '"4"', False),
        ("duplicate", "1, 2", False),
    ]:
        add("count " + label, "ex:v st:count " + value + ".", ok, "" if ok else "count")
    add("typed member without a name", "ex:m a st:Member; st:value 1.", False, "name")
    add("member with two names", 'ex:m st:name "a", "b".', False, "name")
    add("name not a string", "ex:m st:name 1.", False, "name")
    add("identifier not an integer", 'ex:i a st:Item; st:identifier "1".', False, "identifier")
    add("two identifiers", "ex:i a st:Item; st:identifier 1, 2.", False, "identifier")
    add("two values", "ex:i a st:Item; st:value 1, 2.", False, "value")
    for prop in ["recordType", "dataType", "symbol"]:
        add(prop + " not a string", "ex:v st:" + prop + " 1.", False, prop)
    return rows
