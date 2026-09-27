"""Semantic Emitter cases: IRI minting, the literal mapping and triple emission.

Every case parses with the base IRI urn:example:input, so the root is <urn:example:input#root>.
Expected graphs are compared by isomorphism, literals by value.
"""
import struct
import zlib

from suite import BASE, REPORTED_BASE, Case

PM = "processing#"
CASES = []
ROOT = f"<{BASE}#root>"


def se(id, title, intent, reqs, sections, description, data, expected_ttl=None, error=None, **kw):
    manifest = {"base": BASE}
    manifest.update(kw.pop("manifest", {}))
    CASES.append(Case(id=f"se-{id}", cls="semantic-emitter", title=title, intent=intent, requirements=reqs,
                      sections=[PM + s if "#" not in s else s for s in sections], description=description,
                      input=data, expected_ttl=expected_ttl, error=error, manifest=manifest, **kw))


MINT = ["req-pm-iri-minting-1", "req-pm-iri-minting-3"]

se("class-and-literals", "A mapped struct is typed and its mapped fields become typed literals",
   "Each literal's datatype is the bddo:xsdType of the field's data type: unsignedInt, unsignedByte, short, double, string and hexBinary.",
   MINT + ["req-pm-emission-3", "req-pm-emission-4", "req-pm-emission-5"], ["emission", "value-mapping", "iri-minting"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:w ex:depth ex:off ex:scale ex:name ex:raw ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint32 ; hexplain:mapsToProperty ex:width .
   ex:depth a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:bitDepth .
   ex:off a bddo:Field ; bddo:dataType bddo:int16 ; hexplain:mapsToProperty ex:offset .
   ex:scale a bddo:Field ; bddo:dataType bddo:float64 ; hexplain:mapsToProperty ex:scale .
   ex:name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii ; hexplain:mapsToProperty ex:name .
   ex:raw a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ; hexplain:mapsToProperty ex:raw .
   """,
   struct.pack(">IBhd", 1920, 8, -2, 0.5) + b"hi" + b"\x0a\x0b",
   f"""
   {ROOT} a ex:Image ; ex:width "1920"^^xsd:unsignedInt ; ex:bitDepth "8"^^xsd:unsignedByte ;
       ex:offset "-2"^^xsd:short ; ex:scale "0.5"^^xsd:double ; ex:name "hi" ; ex:raw "0A0B"^^xsd:hexBinary .
   """)

se("nested-paths", "Nested structs and array elements are minted by node path",
   "The i-th element of an array field k under p is p/k/i and a struct under it p/k/i/f; segments are appended for every struct, and no edge links them unless a property is mapped.",
   MINT, ["iri-minting"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:chunks ) .
   ex:chunks a bddo:Field ; bddo:dataType ex:Chunk ; bddo:repeatCount 2 .
   ex:Chunk a bddo:Struct ; hexplain:mapsToClass ex:ChunkClass ; bddo:hasField ( ex:type ex:data ) .
   ex:type a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii ; hexplain:mapsToProperty ex:chunkType .
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
   """)

se("unmapped-struct-literals", "The literals of an unmapped struct go to the nearest mapped ancestor",
   "A header struct with no class mapping emits its mapped field on the root's subject.",
   MINT, ["iri-minting"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:File ; bddo:hasField ( ex:hdr ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .
   ex:Hdr a bddo:Struct ; bddo:hasField ( ex:version ) .
   ex:version a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:version .
   """,
   b"\x03", f"{ROOT} a ex:File ; ex:version \"3\"^^xsd:unsignedByte .")

se("unmapped-no-ancestor", "An unmapped struct with no mapped ancestor emits nothing",
   "Neither the root nor its header is mapped to a class, so the mapped field has no subject.",
   MINT, ["iri-minting"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr .
   ex:Hdr a bddo:Struct ; bddo:hasField ( ex:version ) .
   ex:version a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:version .
   """,
   b"\x03", "")

se("unmapped-root-silences-descendants", "The descendants of an unmapped struct with no mapped ancestor emit nothing",
   "The root is not mapped to a class, so neither it nor any struct below it emits, mapped or not.",
   MINT, ["iri-minting"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:chunk ) .
   ex:chunk a bddo:Field ; bddo:dataType ex:Chunk .
   ex:Chunk a bddo:Struct ; hexplain:mapsToClass ex:ChunkClass ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   """,
   b"\x01", "")

se("object-property", "hexplain:mapsToObjectProperty links a struct to a nested struct's resource",
   "The edge's object is the IRI minted for the nested struct instance.",
   MINT + ["req-pm-emission-6"], ["iri-minting", "emission"],
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
   """)

se("value-expression", "hexplain:valueExpression emits a computed value in hexplain:valueDatatype",
   "A raw temperature times 0.5, typed xsd:double, is emitted instead of the raw value.",
   MINT + ["req-pm-emission-5"], ["emission"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Reading ; bddo:hasField ( ex:raw ) .
   ex:raw a bddo:Field ; bddo:dataType bddo:int16 ; hexplain:mapsToProperty ex:celsius ;
       hexplain:valueExpression "raw * 0.5" ; hexplain:valueDatatype xsd:double .
   """,
   struct.pack(">h", 21), f"{ROOT} a ex:Reading ; ex:celsius \"10.5\"^^xsd:double .")

se("conditional-mapping", "hexplain:hasConditionalMapping emits the property of the first holding rule",
   "Records name their value by a key; each record's value goes to the property its key selects, on the root's subject.",
   MINT + ["req-pm-emission-7"], ["emission", "iri-minting"],
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
   f"{ROOT} a ex:Image ; ex:width \"5\"^^xsd:unsignedByte ; ex:height \"7\"^^xsd:unsignedByte .")

se("conditional-class-mapping", "hexplain:hasConditionalClassMapping types a struct by the first holding rule",
   "A tagged record with kind 2 is typed with the second rule's class.",
   MINT, ["emission"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ) ;
       hexplain:hasConditionalClassMapping (
           [ a hexplain:ClassMappingRule ; hexplain:condition "kind == 1" ; hexplain:semanticClass ex:Point ]
           [ a hexplain:ClassMappingRule ; hexplain:condition "kind == 2" ; hexplain:semanticClass ex:Line ] ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:kind .
   """,
   b"\x02", f"{ROOT} a ex:Line ; ex:kind \"2\"^^xsd:unsignedByte .")

se("language-tags", "hexplain:language and hexplain:languageFromField tag string literals",
   "A fixed tag and a tag read from a sibling field.",
   MINT, ["emission"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Doc ; bddo:hasField ( ex:title ex:lang ex:note ) .
   ex:title a bddo:Field ; bddo:dataType bddo:string ; bddo:size 5 ; bddo:encoding bddo:ascii ;
       hexplain:mapsToProperty ex:title ; hexplain:language "en" .
   ex:lang a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   ex:note a bddo:Field ; bddo:dataType bddo:string ; bddo:size 5 ; bddo:encoding bddo:ascii ;
       hexplain:mapsToProperty ex:note ; hexplain:languageFromField ex:lang .
   """,
   b"hellofrsalut", f"{ROOT} a ex:Doc ; ex:title \"hello\"@en ; ex:note \"salut\"@fr .")

se("root-sequence", "A root parsed as a repeatUntil sequence mints root/i for its elements",
   "Each record of a root sequence is minted root/0, root/1, ...",
   MINT + ["req-pm-emission-8"], ["iri-minting"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:repeatUntil "eof()" ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   """,
   b"\x01\x02",
   f"""
   <{BASE}#root/0> a ex:Rec ; ex:value "1"^^xsd:unsignedByte .
   <{BASE}#root/1> a ex:Rec ; ex:value "2"^^xsd:unsignedByte .
   """)

se("key-percent-encoding", "A '/' in a container field's key is percent-encoded in a minted IRI",
   "The nested document is located by the JSON pointer /meta, the simple key of a field whose IRI is the container's IRI, '.', and the path; in the minted IRI the '/' of the key becomes %2F.",
   MINT, ["iri-minting"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; hexplain:mapsToClass ex:Doc ; bddo:hasField ( <https://example.org/se-key-percent-encoding#Root./meta> ) .
   <https://example.org/se-key-percent-encoding#Root./meta> a bddo:Field ; bddo:dataType ex:Meta ; bddo:nodePath "/meta" .
   ex:Meta a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; hexplain:mapsToClass ex:MetaClass ; bddo:hasField ( ex:Meta.name ) .
   ex:Meta.name a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/name" ; hexplain:mapsToProperty ex:name .
   """,
   b'{"meta": {"name": "x"}}',
   f"""
   {ROOT} a ex:Doc .
   <{BASE}#root/%2Fmeta> a ex:MetaClass ; ex:name "x" .
   """, manifest={"features": {"requires": ["tree-documents"]}})

se("enum-symbol-object", "An enumeration's symbol IRI is emitted through hexplain:mapsToObjectProperty",
   "Colour type 2 maps to the enumeration's RGB symbol.",
   MINT + ["req-pm-parsefield-15", "req-pm-emission-6"], ["emission"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:colour ) .
   ex:colour a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToObjectProperty ex:colourType ;
       bddo:enumeration [ a bddo:Enumeration ;
           bddo:hasEnumValue [ a bddo:EnumValue ; bddo:enumRawValue 0 ; bddo:enumSymbol ex:Grey ] ,
                             [ a bddo:EnumValue ; bddo:enumRawValue 2 ; bddo:enumSymbol ex:RGB ] ] .
   """,
   b"\x02", f"{ROOT} a ex:Image ; ex:colourType ex:RGB .")

se("encoded-substream", "A decoded block re-parsed as a struct is lifted like any other struct",
   "The inflated bytes are re-parsed against the mapped struct and minted under the field's key.",
   MINT + ["req-pm-emission-1"], ["emission", "iri-minting"],
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
   """)

se("triple-limit", "More triples than the emitted-triples limit is a ResourceLimit error",
   "Five triples under maxTriples 3; no partial graph is returned.",
   ["req-pm-resource-limits-1", "req-pm-resource-limits-3", "req-pm-errors-12"], ["resource-limits"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Rec ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:a .
   ex:b a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:b .
   ex:c a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:c .
   ex:d a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:d .
   """,
   b"\x01\x02\x03\x04", error="ResourceLimit", manifest={"limits": {"maxTriples": 3}})

assert zlib.decompress(bytes.fromhex("78da6364620600000d0007")) == b"\x01\x02\x03"

se("base-reported", "Without a base IRI the processor chooses one, mints against it and reports it",
   "The manifest gives no base. The processor picks its own base and reports it with the graph; the runner reads the "
   "reported base as the placeholder urn:hexplain:suite:reported-base, so the root is that base's #root. A processor that "
   "reports no base, or mints against another than the one it reports, fails.",
   MINT + ["req-pm-iri-minting-2"], ["iri-minting"],
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Image ; bddo:hasField ( ex:w ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:width .
   """,
   b"\x07",
   f"""
   <{REPORTED_BASE}#root> a ex:Image ; ex:width "7"^^xsd:unsignedByte .
   """, manifest={"base": None})

se("data-layout-array-node", "A field with a data layout emits its array node, never a literal or its cells",
   "hexplain:mapsToObjectProperty links the root to the field's array node root/pixels; hexplain:mapsToProperty on a "
   "second layout field emits nothing; no cell of either is emitted.",
   MINT + ["req-pm-emission-9"], ["emission", "iri-minting"],
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
   f"{ROOT} a ex:Image ; ex:samples <{BASE}#root/pixels> .")
