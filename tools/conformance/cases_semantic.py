"""Semantic Emitter cases: IRI minting, the literal mapping and triple emission.

Every case parses with the base IRI urn:example:input, so the root is <urn:example:input#root>.
Expected graphs are compared by isomorphism, literals by value.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any

from suite import BASE, REPORTED_BASE, Case

PM = "processing#"
CASES = []
ROOT = f"<{BASE}#root>"


def se(
    id: Any,
    title: str,
    intent: Any,
    reqs: Any,
    sections: Any,
    description: str,
    data: Any,
    expected_ttl: Any = None,
    error: Any = None,
    **kw: Any,
) -> None:
    manifest = {"base": BASE}
    manifest.update(kw.pop("manifest", {}))
    CASES.append(
        Case(
            id=f"se-{id}",
            cls="semantic-emitter",
            title=title,
            intent=intent,
            requirements=reqs,
            sections=[PM + s if "#" not in s else s for s in sections],
            description=description,
            input=data,
            expected_ttl=expected_ttl,
            error=error,
            manifest=manifest,
            **kw,
        )
    )


MINT = ["req-pm-iri-minting-1", "req-pm-iri-minting-3"]

se(
    "class-and-literals",
    "A mapped struct is typed and its mapped fields become typed literals",
    "Each literal's datatype is the bddo:xsdType of the field's data type: unsignedInt, unsignedByte, short, "
    "double, string and hexBinary.",
    MINT + ["req-pm-emission-3", "req-pm-emission-4", "req-pm-emission-5"],
    ["emission", "value-mapping", "iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:w ex:depth ex:off ex:scale ex:name \
ex:raw ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint32 ; hexplain:mapsToProperty ex:width .
   ex:depth a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:bitDepth .
   ex:off a bddo:Field ; bddo:dataType bddo:int16 ; hexplain:mapsToProperty ex:offset .
   ex:scale a bddo:Field ; bddo:dataType bddo:float64 ; hexplain:mapsToProperty ex:scale .
   ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii ; \
hexplain:mapsToProperty ex:name .
   ex:raw a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ; hexplain:mapsToProperty ex:raw .
   """,
    struct.pack(">IBhd", 1920, 8, -2, 0.5) + b"hi" + b"\x0a\x0b",
    f"""
   {ROOT} a ex:Image ; ex:width "1920"^^xsd:unsignedInt ; ex:bitDepth "8"^^xsd:unsignedByte ;
       ex:offset "-2"^^xsd:short ; ex:scale "5.0E-1"^^xsd:double ; ex:name "hi" ; ex:raw "0A0B"^^xsd:hexBinary .
   """,
)

se(
    "nested-paths",
    "Nested structs and array elements are minted by node path",
    "The i-th element of an array field k under p is p/k/i and a struct under it p/k/i/f; segments are "
    "appended for every struct, and no edge links them unless a property is mapped.",
    MINT,
    ["iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:chunks ) .
   ex:chunks a bddo:Field ; bddo:dataType ex:Chunk ; bddo:repeatCount 2 .
   ex:Chunk a bddo:Struct ; hexplain:mapsToClass ex:ChunkClass ; bddo:hasField ( ex:type ex:data ) .
   ex:type a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii ; \
hexplain:mapsToProperty ex:chunkType .
   ex:data a bddo:Field ; bddo:dataType ex:Data .
   ex:Data a bddo:Struct ; hexplain:mapsToClass ex:DataClass ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   """,
    b"IHDR\x01IEND\x02",
    f"""
   {ROOT} a ex:File .
   <{BASE}#root/chunks/0> a ex:ChunkClass ; ex:chunkType "IHDR" .
   <{BASE}#root/chunks/0/data> a ex:DataClass ; ex:value "1"^^xsd:unsignedByte .
   <{BASE}#root/chunks/1> a ex:ChunkClass ; ex:chunkType "IEND" .
   <{BASE}#root/chunks/1/data> a ex:DataClass ; ex:value "2"^^xsd:unsignedByte .
   """,
)

se(
    "unmapped-struct-literals",
    "The literals of an unmapped struct go to the nearest mapped ancestor",
    "A header struct with no class mapping emits its mapped field on the root's subject.",
    MINT,
    ["iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:hdr ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .
   ex:Hdr a bddo:Struct ; bddo:hasField ( ex:version ) .
   ex:version a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:version .
   """,
    b"\x03",
    f'{ROOT} a ex:File ; ex:version "3"^^xsd:unsignedByte .',
)

se(
    "unmapped-no-ancestor",
    "An unmapped struct with no mapped ancestor emits nothing",
    "Neither the root nor its header is mapped to a class, so the mapped field has no subject.",
    MINT,
    ["iri-minting"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .
   ex:Hdr a bddo:Struct ; bddo:hasField ( ex:version ) .
   ex:version a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:version .
   """,
    b"\x03",
    "",
)

se(
    "unmapped-root-silences-descendants",
    "The descendants of an unmapped struct with no mapped ancestor emit nothing",
    "The root is not mapped to a class, so neither it nor any struct below it emits, mapped or not.",
    MINT,
    ["iri-minting"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:chunk ) .
   ex:chunk a bddo:Field ; bddo:dataType ex:Chunk .
   ex:Chunk a bddo:Struct ; hexplain:mapsToClass ex:ChunkClass ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   """,
    b"\x01",
    "",
)

se(
    "object-property",
    "hexplain:mapsToObjectProperty links a struct to a nested struct's resource",
    "The edge's object is the IRI minted for the nested struct instance.",
    MINT + ["req-pm-emission-6"],
    ["iri-minting", "emission"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:hdr ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr ; hexplain:mapsToObjectProperty ex:header .
   ex:Hdr a bddo:Struct ; hexplain:mapsToClass ex:Header ; bddo:hasField ( ex:version ) .
   ex:version a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:version .
   """,
    b"\x03",
    f"""
   {ROOT} a ex:File ; ex:header <{BASE}#root/hdr> .
   <{BASE}#root/hdr> a ex:Header ; ex:version "3"^^xsd:unsignedByte .
   """,
)

se(
    "value-expression",
    "hexplain:valueExpression emits a computed value in hexplain:valueDatatype",
    "A raw temperature times 0.5, typed xsd:double, is emitted instead of the raw value.",
    MINT + ["req-pm-emission-5"],
    ["emission"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Reading ; bddo:hasField ( ex:raw ) .
   ex:raw a bddo:Field ; bddo:dataType bddo:int16 ; hexplain:mapsToProperty ex:celsius ;
       hexplain:valueExpression "raw * 0.5" ; hexplain:valueDatatype xsd:double .
   """,
    struct.pack(">h", 21),
    f'{ROOT} a ex:Reading ; ex:celsius "1.05E1"^^xsd:double .',
)

se(
    "conditional-mapping",
    "hexplain:hasConditionalMapping emits the property of the first holding rule",
    "Records name their value by a key; each record's value goes to the property its key selects, on the "
    "root's subject.",
    MINT + ["req-pm-emission-7"],
    ["emission", "iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:records ) .
   ex:records a bddo:Field ; bddo:dataType ex:Rec ; bddo:repeatCount 3 .
   ex:Rec a bddo:Struct ; bddo:hasField ( ex:key ex:val ) .
   ex:key a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:val a bddo:Field ; bddo:dataType bddo:uint8 ;
       hexplain:hasConditionalMapping (
           [ a hexplain:MappingRule ; hexplain:condition "key == 'WDTH'" ; hexplain:semanticProperty ex:width ]
           [ a hexplain:MappingRule ; hexplain:condition "key == 'HGHT'" ; hexplain:semanticProperty ex:height ] ) .
   """,
    b"WDTH\x05HGHT\x07XTRA\x09",
    f'{ROOT} a ex:Image ; ex:width "5"^^xsd:unsignedByte ; ex:height "7"^^xsd:unsignedByte .',
)

se(
    "conditional-class-mapping",
    "hexplain:hasConditionalClassMapping types a struct by the first holding rule",
    "A tagged record with kind 2 is typed with the second rule's class.",
    MINT,
    ["emission"],
    """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ) ;
       hexplain:hasConditionalClassMapping (
           [ a hexplain:ClassMappingRule ; hexplain:condition "kind == 1" ; hexplain:semanticClass ex:Point ]
           [ a hexplain:ClassMappingRule ; hexplain:condition "kind == 2" ; hexplain:semanticClass ex:Line ] ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:kind .
   """,
    b"\x02",
    f'{ROOT} a ex:Line ; ex:kind "2"^^xsd:unsignedByte .',
)

se(
    "language-tags",
    "hexplain:language and hexplain:languageFromField tag string literals",
    "A fixed tag and a tag read from a sibling field.",
    MINT,
    ["emission"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Doc ; bddo:hasField ( ex:title ex:lang ex:note ) .
   ex:title a bddo:Field ; bddo:dataType bddo:string ; bddo:size 5 ; bddo:encoding bddo:ascii ;
       hexplain:mapsToProperty ex:title ; hexplain:language "en" .
   ex:lang a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   ex:note a bddo:Field ; bddo:dataType bddo:string ; bddo:size 5 ; bddo:encoding bddo:ascii ;
       hexplain:mapsToProperty ex:note ; hexplain:languageFromField ex:lang .
   """,
    b"hellofrsalut",
    f'{ROOT} a ex:Doc ; ex:title "hello"@en ; ex:note "salut"@fr .',
)

se(
    "root-sequence",
    "A root parsed as a repeatUntil sequence mints root/i for its elements",
    "Each record of a root sequence is minted root/0, root/1, ...",
    MINT + ["req-pm-emission-8"],
    ["iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:repeatUntil "eof()" ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   """,
    b"\x01\x02",
    f"""
   <{BASE}#root/0> a ex:Rec ; ex:value "1"^^xsd:unsignedByte .
   <{BASE}#root/1> a ex:Rec ; ex:value "2"^^xsd:unsignedByte .
   """,
)

se(
    "key-percent-encoding",
    "A '/' in a container field's key is percent-encoded in a minted IRI",
    "The nested document is located by the JSON pointer /meta, the simple key of a field whose IRI is the "
    "container's IRI, '.', and the path; in the minted IRI the '/' of the key becomes %2F.",
    MINT,
    ["iri-minting"],
    """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; hexplain:mapsToClass ex:Doc ; bddo:hasField ( \
<https://example.org/se-key-percent-encoding#Root./meta> ) .
   <https://example.org/se-key-percent-encoding#Root./meta> a bddo:Field ; bddo:dataType ex:Meta ; bddo:nodePath \
"/meta" .
   ex:Meta a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; hexplain:mapsToClass ex:MetaClass ; bddo:hasField ( \
ex:Meta.name ) .
   ex:Meta.name a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/name" ; hexplain:mapsToProperty ex:name .
   """,
    b'{"meta": {"name": "x"}}',
    f"""
   {ROOT} a ex:Doc .
   <{BASE}#root/%2Fmeta> a ex:MetaClass ; ex:name "x" .
   """,
    manifest={"features": {"requires": ["tree-documents"]}},
)

se(
    "enum-symbol-object",
    "An enumeration's symbol IRI is emitted through hexplain:mapsToObjectProperty",
    "Colour type 2 maps to the enumeration's RGB symbol.",
    MINT + ["req-pm-parsefield-15", "req-pm-emission-6"],
    ["emission"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:colour ) .
   ex:colour a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToObjectProperty ex:colourType ;
       bddo:enumeration [ a bddo:Enumeration ;
           bddo:hasEnumValue [ a bddo:EnumValue ; bddo:enumRawValue 0 ; bddo:enumSymbol ex:Grey ] ,
                             [ a bddo:EnumValue ; bddo:enumRawValue 2 ; bddo:enumSymbol ex:RGB ] ] .
   """,
    b"\x02",
    f"{ROOT} a ex:Image ; ex:colourType ex:RGB .",
)

se(
    "encoded-substream",
    "A decoded block re-parsed as a struct is lifted like any other struct",
    "The inflated bytes are re-parsed against the mapped struct and minted under the field's key.",
    MINT + ["req-pm-emission-1", "req-core-static-mapping-properties-3"],
    ["emission", "iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:n ex:block ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:block a bddo:Field ; bddo:dataType ex:Inner ; bddo:sizeFromField ex:n ; hexplain:isEncodedWith menc:Zlib ;
       hexplain:mapsToObjectProperty ex:content .
   ex:Inner a bddo:Struct ; hexplain:mapsToClass ex:Content ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:a .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:c a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:c .
   """,
    bytes([11]) + bytes.fromhex("78da6364620600000d0007"),
    f"""
   {ROOT} a ex:File ; ex:content <{BASE}#root/block> .
   <{BASE}#root/block> a ex:Content ; ex:a "1"^^xsd:unsignedByte ; ex:c "3"^^xsd:unsignedByte .
   """,
)

se(
    "triple-limit",
    "More triples than the emitted-triples limit is a ResourceLimit error",
    "Five triples under maxTriples 3; no partial graph is returned.",
    ["req-pm-resource-limits-1", "req-pm-errors-12"],
    ["resource-limits"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:a .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:b .
   ex:c a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:c .
   ex:d a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:d .
   """,
    b"\x01\x02\x03\x04",
    error="ResourceLimit",
    manifest={"limits": {"maxTriples": 3}},
)

assert zlib.decompress(bytes.fromhex("78da6364620600000d0007")) == b"\x01\x02\x03"

se(
    "base-reported",
    "Without a base IRI the processor chooses one, mints against it and reports it",
    "The manifest gives no base. The processor picks its own base and reports it with the graph; the runner reads the "
    "reported base as the placeholder urn:hexplain:suite:reported-base, so the root is that base's #root. A "
    "processor that "
    "reports no base, or mints against another than the one it reports, fails.",
    MINT + ["req-pm-iri-minting-2"],
    ["iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:w ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:width .
   """,
    b"\x07",
    f"""
   <{REPORTED_BASE}#root> a ex:Image ; ex:width "7"^^xsd:unsignedByte .
   """,
    manifest={"base": None},
)

se(
    "data-layout-array-node",
    "A field with a data layout emits its array node, never a literal or its cells",
    "hexplain:mapsToObjectProperty links the root to the field's array node root/pixels; hexplain:mapsToProperty on a "
    "second layout field emits nothing; no cell of either is emitted.",
    MINT + ["req-pm-emission-9"],
    ["emission", "iri-minting"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:pixels ex:mask ) .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; hexplain:hasDataLayout ex:Layout ;
       hexplain:mapsToObjectProperty ex:samples .
   ex:mask a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; hexplain:hasDataLayout ex:Layout ;
       hexplain:mapsToProperty ex:maskBytes .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:hasDimension ( ex:DimY ex:DimX ) .
   ex:DimY a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSize 2 .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSize 2 .
   """,
    b"\x01\x02\x03\x04\x00\x01\x01\x00",
    f"{ROOT} a ex:Image ; ex:samples <{BASE}#root/pixels> .",
)


# ----------------------------------------------------------------- computed values: the natural datatype

NATURAL = MINT + ["req-pm-emission-5", "req-pm-computed-values-1"]
TYPED = MINT + ["req-pm-emission-5", "req-pm-computed-values-2"]


def computed(expr: str, fields: list[str], datatype: str | None = None, extra: str = "") -> str:
    """A mapped root with the given physical fields (Turtle lines) and a field ex:out, a copy of the first physical
    field's bytes, whose value is computed by `expr` and emitted as ex:value."""
    typed = f" ; hexplain:valueDatatype {datatype}" if datatype else ""
    names = " ".join(line.split()[0] for line in fields)
    return (
        f"ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( {names} ex:out ) .\n"
        + "\n".join(fields)
        + "\nex:out a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value ;\n"
        + f'    hexplain:valueExpression "{expr}"{typed} .\n'
        + extra
    )


RAW = ["ex:raw a bddo:Field ; bddo:dataType bddo:int16 ."]

se(
    "value-natural-integer",
    "A computed Integer with no valueDatatype is an xsd:long literal",
    "raw + 1 is the Integer 22; its natural datatype is xsd:long whatever its magnitude, never xsd:int.",
    NATURAL + ["req-pm-computed-values-3"],
    ["computed-values", "emission"],
    computed("raw + 1", RAW),
    struct.pack(">h", 21) + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "22"^^xsd:long .',
)

se(
    "value-natural-unsigned-beyond-long",
    "A computed uint64 value above 2^63-1 is an xsd:integer literal",
    "The expression passes through a uint64 field holding 2^64-1, a value xsd:long cannot hold.",
    NATURAL + ["req-pm-computed-values-3"],
    ["computed-values"],
    computed("big", ["ex:big a bddo:Field ; bddo:dataType bddo:uint64 ."]),
    b"\xff" * 8 + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "18446744073709551615"^^xsd:integer .',
)

se(
    "value-natural-float",
    "A computed Float with no valueDatatype is an xsd:double literal",
    "raw * 0.5 is the Float 10.5.",
    NATURAL + ["req-pm-computed-values-4"],
    ["computed-values"],
    computed("raw * 0.5", RAW),
    struct.pack(">h", 21) + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "1.05E1"^^xsd:double .',
)

se(
    "value-natural-float-infinity",
    "A computed infinite Float is written INF",
    "1e308 * 10.0 overflows binary64 to +Infinity, whose xsd:double lexical form is INF.",
    NATURAL + ["req-pm-computed-values-4"],
    ["computed-values"],
    computed("1e308 * 10.0", RAW),
    struct.pack(">h", 21) + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "INF"^^xsd:double .',
)

se(
    "value-natural-string",
    "A computed String with no valueDatatype is an xsd:string literal",
    "trim(name) of ' hi ' is the String 'hi'.",
    NATURAL + ["req-pm-computed-values-5"],
    ["computed-values"],
    computed(
        "trim(name)", ["ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii ."]
    ),
    b" hi \x00",
    f'{ROOT} a ex:Rec ; ex:value "hi" .',
)

se(
    "value-natural-boolean",
    "A computed Boolean with no valueDatatype is an xsd:boolean literal",
    "raw > 1 is true.",
    NATURAL + ["req-pm-computed-values-6"],
    ["computed-values"],
    computed("raw > 1", RAW),
    struct.pack(">h", 21) + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "true"^^xsd:boolean .',
)

se(
    "value-natural-bytes",
    "Computed Bytes with no valueDatatype are an xsd:hexBinary literal",
    "The expression passes a two-byte bytes field through.",
    NATURAL + ["req-pm-computed-values-7"],
    ["computed-values"],
    computed("tag", ["ex:tag a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ."]),
    b"\xca\xfe\x00",
    f'{ROOT} a ex:Rec ; ex:value "CAFE"^^xsd:hexBinary .',
)

se(
    "value-natural-null",
    "A computed Null emits nothing",
    "The expression reads an optional field that is absent, so ex:value has no triple, exactly as for an "
    "unbound field.",
    NATURAL + ["req-pm-computed-values-8"],
    ["computed-values"],
    computed(
        "opt",
        [
            "ex:flag a bddo:Field ; bddo:dataType bddo:uint8 .",
            'ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "flag == 1" .',
        ],
    ),
    b"\x00\x07",
    f"{ROOT} a ex:Rec .",
)

se(
    "value-natural-struct-node",
    "A computed struct node is a Type / HEL error",
    "The expression names a struct field; a node has no literal form.",
    NATURAL + ["req-pm-computed-values-9"],
    ["computed-values"],
    computed(
        "hdr",
        ["ex:hdr a bddo:Field ; bddo:dataType ex:Hdr ."],
        extra="ex:Hdr a bddo:Struct ; bddo:hasField ( ex:n ) .\nex:n a bddo:Field ; bddo:dataType bddo:uint8 .\n",
    ),
    b"\x01\x00",
    error="Expression",
)

se(
    "value-natural-array-node",
    "A computed array node is a Type / HEL error",
    "The expression names a repeated field; a repeated field is emitted one triple per element only by its "
    "own mapping.",
    NATURAL + ["req-pm-computed-values-9"],
    ["computed-values"],
    computed("items", ["ex:items a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 ."]),
    b"\x01\x02\x00",
    error="Expression",
)

se(
    "value-datatype-integer-as-double",
    "An Integer result typed xsd:double is emitted as that double",
    "raw + 1 is the Integer 22 and hexplain:valueDatatype is xsd:double: the literal is 22 as an xsd:double.",
    TYPED,
    ["computed-values"],
    computed("raw + 1", RAW, "xsd:double"),
    struct.pack(">h", 21) + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "2.2E1"^^xsd:double .',
)

se(
    "value-datatype-string-as-integer",
    "A String result typed xsd:integer is a Type / HEL error",
    "trim(name) is a String, which has no value in xsd:integer's value space; the datatype is never re-labelled.",
    TYPED + ["req-hel-conformance-6"],
    ["computed-values"],
    computed(
        "trim(name)",
        ["ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii ."],
        "xsd:integer",
    ),
    b"ab\x00",
    error="Expression",
)

se(
    "value-datatype-out-of-range",
    "An Integer outside the valueDatatype's range is a Type / HEL error",
    "raw * 20 is 420, which is not an xsd:unsignedByte.",
    TYPED,
    ["computed-values"],
    computed("raw * 20", RAW, "xsd:unsignedByte"),
    struct.pack(">h", 21) + b"\x00",
    error="Expression",
)

se(
    "value-datatype-fraction-as-integer",
    "A fractional Float typed with an integer datatype is a Type / HEL error",
    "raw * 0.5 is 10.5, which has no value in xsd:integer; the processor does not change the datatype to xsd:decimal.",
    TYPED,
    ["computed-values"],
    computed("raw * 0.5", RAW, "xsd:integer"),
    struct.pack(">h", 21) + b"\x00",
    error="Expression",
)

se(
    "value-datatype-integral-float-as-integer",
    "A Float with no fractional part typed with an integer datatype is a Type / HEL error",
    "raw * 2.0 is the Float 42.0. A Float has no value in an integer datatype even when it is integral, as a Float is "
    "never an Integer in HEL, so typing it xsd:integer is an error, not the integer 42.",
    TYPED + ["req-hel-conformance-6"],
    ["computed-values"],
    computed("raw * 2.0", RAW, "xsd:integer"),
    struct.pack(">h", 21) + b"\x00",
    error="Expression",
)

se(
    "value-datatype-float-as-decimal",
    "A finite Float typed xsd:decimal is emitted as that decimal",
    "raw * 0.5 is the Float 10.5, which has a value in xsd:decimal's value space.",
    TYPED,
    ["computed-values"],
    computed("raw * 0.5", RAW, "xsd:decimal"),
    struct.pack(">h", 21) + b"\x00",
    f'{ROOT} a ex:Rec ; ex:value "10.5"^^xsd:decimal .',
)

se(
    "value-datatype-bytes-as-base64",
    "Bytes typed xsd:base64Binary are emitted in base64",
    "The expression passes the two bytes CA FE through; with hexplain:valueDatatype xsd:base64Binary the "
    "literal is yv4=, "
    "the same bytes as the natural xsd:hexBinary CAFE.",
    TYPED,
    ["computed-values"],
    computed("tag", ["ex:tag a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ."], "xsd:base64Binary"),
    bytes.fromhex("cafe00"),
    f'{ROOT} a ex:Rec ; ex:value "yv4="^^xsd:base64Binary .',
)


se(
    "key-percent-sign",
    "A '%' in a key is always percent-encoded as %25",
    "The nested document's key is the JSON pointer /a%20b, naming the member \"a%20b\". Its '%' is encoded as %25 even "
    "though '%20' looks like an encoded space, so the segment is %2Fa%2520b and cannot collide with the key '/a b'.",
    MINT + ["req-pm-iri-minting-4"],
    ["iri-minting"],
    """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; hexplain:mapsToClass ex:Doc ; bddo:hasField ( \
<https://example.org/se-key-percent-sign#Root./a%20b> ) .
   <https://example.org/se-key-percent-sign#Root./a%20b> a bddo:Field ; bddo:dataType ex:Meta ; bddo:nodePath "/a%20b" .
   ex:Meta a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; hexplain:mapsToClass ex:MetaClass ; bddo:hasField ( \
ex:Meta.name ) .
   ex:Meta.name a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/name" ; hexplain:mapsToProperty ex:name .
   """,
    b'{"a%20b": {"name": "x"}}',
    f"""
   {ROOT} a ex:Doc .
   <{BASE}#root/%2Fa%2520b> a ex:MetaClass ; ex:name "x" .
   """,
    manifest={"features": {"requires": ["tree-documents"]}},
)


# ----------------------------------------------------------------- canonical lexical forms, enumeration symbols

se(
    "lexical-forms-canonical",
    "Emitted literals are in the canonical lexical form of their datatype",
    "100.0 is an xsd:double written 1.0E2, never 100.0 or 1E2; the float32 negative zero is -0.0E0 and 2.5 is 2.5E0; "
    "0.001 is 1.0E-3; the bytes AB CD are the upper-case ABCD; -7 has no sign padding.",
    MINT + ["req-pm-emission-5", "req-pm-emission-12"],
    ["emission", "value-mapping"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:big ex:nz ex:half ex:small ex:raw ex:n ) .
   ex:big a bddo:Field ; bddo:dataType bddo:float64 ; hexplain:mapsToProperty ex:big .
   ex:nz a bddo:Field ; bddo:dataType bddo:float32 ; hexplain:mapsToProperty ex:negativeZero .
   ex:half a bddo:Field ; bddo:dataType bddo:float32 ; hexplain:mapsToProperty ex:half .
   ex:small a bddo:Field ; bddo:dataType bddo:float64 ; hexplain:mapsToProperty ex:small .
   ex:raw a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ; hexplain:mapsToProperty ex:raw .
   ex:n a bddo:Field ; bddo:dataType bddo:int8 ; hexplain:mapsToProperty ex:n .
   """,
    struct.pack(">dffd", 100.0, -0.0, 2.5, 0.001) + b"\xab\xcd" + b"\xf9",
    f"""
   {ROOT} a ex:Rec ; ex:big "1.0E2"^^xsd:double ; ex:negativeZero "-0.0E0"^^xsd:float ; ex:half "2.5E0"^^xsd:float ;
       ex:small "1.0E-3"^^xsd:double ; ex:raw "ABCD"^^xsd:hexBinary ; ex:n "-7"^^xsd:byte .
   """,
)

se(
    "lexical-forms-computed",
    "Computed literals are in canonical lexical form too",
    "raw * 2.0 is the Float 42.0: as an xsd:decimal it is 42, with no point, and as the natural xsd:double 4.2E1; "
    "0.0 * raw is 0.0E0.",
    MINT + ["req-pm-emission-5", "req-pm-emission-12"],
    ["emission", "computed-values"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:raw ex:d ex:f ex:z ) .
   ex:raw a bddo:Field ; bddo:dataType bddo:int16 .
   ex:d a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:decimal ;
       hexplain:valueExpression "raw * 2.0" ; hexplain:valueDatatype xsd:decimal .
   ex:f a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:double ;
       hexplain:valueExpression "raw * 2.0" .
   ex:z a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:zero ;
       hexplain:valueExpression "0.0 * raw" .
   """,
    struct.pack(">h", 21) + b"\x00\x00\x00",
    f'{ROOT} a ex:Rec ; ex:decimal "42"^^xsd:decimal ; ex:double "4.2E1"^^xsd:double ; ex:zero "0.0E0"^^xsd:double .',
)

ENUM = """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:colour ) .
   ex:colour a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:colourType ;
       bddo:enumeration [ a bddo:Enumeration FLAGS;
           bddo:hasEnumValue [ a bddo:EnumValue ; bddo:enumRawValue 1 ; bddo:enumSymbol ex:Palette ] ,
                             [ a bddo:EnumValue ; bddo:enumRawValue 2 ; bddo:enumSymbol ex:Colour ] ,
                             [ a bddo:EnumValue ; bddo:enumRawValue 4 ; rdfs:label "alpha" ] ] .
   """

se(
    "enum-symbol-with-literal",
    "A matched enumeration symbol is emitted alongside the raw literal",
    "Colour type 2 matches the value whose symbol is ex:Colour: the mapped property carries the literal and "
    "the symbol.",
    MINT + ["req-pm-parsefield-15", "req-pm-emission-2", "req-pm-emission-5"],
    ["emission"],
    ENUM.replace("FLAGS", ""),
    b"\x02",
    f'{ROOT} a ex:Image ; ex:colourType "2"^^xsd:unsignedByte , ex:Colour .',
)

se(
    "enum-value-without-symbol",
    "A matched enumeration value without a symbol emits the literal alone",
    "Colour type 4 matches a value that has an rdfs:label and no bddo:enumSymbol, so there is no symbol to emit.",
    MINT + ["req-pm-parsefield-15", "req-pm-emission-2", "req-pm-emission-5"],
    ["emission"],
    ENUM.replace("FLAGS", ""),
    b"\x04",
    f'{ROOT} a ex:Image ; ex:colourType "4"^^xsd:unsignedByte .',
)

se(
    "enum-flags-symbols-with-literal",
    "A flags enumeration emits every matching symbol alongside the raw literal",
    "7 has the bits of all three values; the two that have a symbol are both emitted, with the literal.",
    MINT + ["req-pm-parsefield-15", "req-pm-emission-2", "req-pm-emission-5"],
    ["emission"],
    ENUM.replace("FLAGS", "; bddo:enumIsFlags true "),
    b"\x07",
    f'{ROOT} a ex:Image ; ex:colourType "7"^^xsd:unsignedByte , ex:Palette , ex:Colour .',
)


# ----------------------------------------------------------------- expressions evaluated over the complete tree

LATER = ["req-pm-emission-11", "req-hel-name-binding-3", "req-pm-context-1"]

se(
    "value-expression-later-field",
    "A value expression may name a field declared after its own",
    "raw is scaled by scale, the field after it: the expression is evaluated over the complete tree, so "
    "scale is bound.",
    MINT + ["req-pm-emission-5"] + LATER,
    ["emission", "evaluation-time", "context"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:raw ex:scale ) .
   ex:raw a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value ;
       hexplain:valueExpression "raw * scale" .
   ex:scale a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x03\x04",
    f'{ROOT} a ex:Rec ; ex:value "12"^^xsd:long .',
)

se(
    "map-guard-later-field",
    "A map guard may name a field declared after its own",
    "val is mapped by kind, which follows it: kind is 2, so the second rule's property carries the value.",
    MINT + ["req-pm-emission-7"] + LATER,
    ["emission", "evaluation-time"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:val ex:kind ) .
   ex:val a bddo:Field ; bddo:dataType bddo:uint8 ;
       hexplain:hasConditionalMapping (
           [ a hexplain:MappingRule ; hexplain:condition "kind == 1" ; hexplain:semanticProperty ex:width ]
           [ a hexplain:MappingRule ; hexplain:condition "kind == 2" ; hexplain:semanticProperty ex:height ] ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x05\x02",
    f'{ROOT} a ex:Image ; ex:height "5"^^xsd:unsignedByte .',
)

se(
    "class-guard-later-field",
    "A means-when guard may name a field parsed after its struct",
    "The item is typed by parent.kind, a field of the root that follows the item.",
    MINT + ["req-pm-emission-4"] + LATER,
    ["emission", "evaluation-time"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:item ex:kind ) .
   ex:item a bddo:Field ; bddo:dataType ex:Item .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Item a bddo:Struct ; bddo:hasField ( ex:v ) ;
       hexplain:hasConditionalClassMapping (
           [ a hexplain:ClassMappingRule ; hexplain:condition "parent.kind == 1" ; hexplain:semanticClass ex:Point ]
           [ a hexplain:ClassMappingRule ; hexplain:condition "parent.kind == 2" ; hexplain:semanticClass ex:Line ] ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
    b"\x07\x02",
    f"{ROOT} a ex:File . <{BASE}#root/item> a ex:Line .",
)

se(
    "value-expression-absent-later-field",
    "An absent later field reads as Null in a value expression",
    "raw's value is computed as opt, the optional field after it, which is absent (flag is 0): Null, not a forward "
    "reference, so nothing is emitted for ex:value.",
    MINT + ["req-pm-emission-5", "req-pm-computed-values-8"] + LATER,
    ["emission", "evaluation-time", "computed-values"],
    """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:flag ex:raw ex:opt ) .
   ex:flag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:raw a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value ;
       hexplain:valueExpression "opt" .
   ex:opt a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:isPresentIf "flag == 1" .
   """,
    b"\x00\x03",
    f"{ROOT} a ex:Rec .",
)
