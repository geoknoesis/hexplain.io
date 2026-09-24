"""HDL Compiler cases: an .hx source compiles to the expected Turtle (compared by isomorphism,
literals by value), or is refused with an ERROR diagnostic, at the stated line when the case gives one.

Each source declares @namespace "https://example.org/<case-id>#", the namespace the expected
Turtle's ex: prefix is bound to.
"""
from suite import Case, dedent, namespace

HDL = "hdl/index.html#"
CASES = []
USE = 'use ex: <{ns}>'


def hc(id, title, intent, reqs, sections, source, expected_ttl=None, line=None, manifest=None, yaml=False):
    case_id = f"hc-{id}"
    source = source.replace("{ns}", namespace(case_id))
    error = None if expected_ttl is not None else ({"severity": "ERROR", "line": line} if line else {"severity": "ERROR"})
    man = {"input": "input.hx.yaml" if yaml else "input.hx"}
    man.update(manifest or {})
    CASES.append(Case(id=case_id, cls="hdl-compiler", title=title, intent=intent,
                      requirements=["req-hdl-conformance-section-1"] + reqs,
                      sections=[HDL + s if "#" not in s else s for s in sections], hdl=None if yaml else source,
                      files={"input.hx.yaml": dedent(source)} if yaml else {},
                      expected_ttl=expected_ttl, hdl_error=error, root=None, manifest=man))


OK = ["req-hdl-conformance-section-4", "req-hdl-conformance-section-6"]

# ----------------------------------------------------------------- successful compilations

hc("struct-and-types", "Structs and fields mint IRIs from the base namespace; types map to BDDO",
   "Root and its fields become <base>Root and <base>Root.<field>; u16, i32le and f64 name the BDDO data types, ascii[4] "
   "a 4-byte string in ASCII, and the lone sibling in bytes[n] the bddo:sizeFromField form.",
   OK + ["req-hdl-form-rule-1", "req-pm-conformance-classes-2"], ["iri-minting", "types", "clauses", "form-rule"],
   """
   format t @namespace "{ns}"
   struct Root {
     n : u16
     tag : ascii[4]
     k : i32le
     f : f64
     data : bytes[n]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.tag ex:Root.k ex:Root.f ex:Root.data ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:Root.tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:Root.k a bddo:Field ; bddo:dataType bddo:int32le .
   ex:Root.f a bddo:Field ; bddo:dataType bddo:float64 .
   ex:Root.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:Root.n .
   """)

hc("field-and-expression-forms", "A lone sibling emits the ...FromField form, a literal the plain form, anything else ...FromExpression",
   "Sizes, counts and offsets each in their three forms; a bare name is emitted as instance.<name> in canonical HEL.",
   OK + ["req-hdl-form-rule-1", "req-hdl-conformance-section-5", "req-hdl-grammar-expressions-1"],
   ["form-rule", "expressions", "grammar-expressions"],
   """
   format t @namespace "{ns}"
   struct Root {
     n : u8
     a : bytes[3]
     b : bytes[n * 2]
     c : u8 repeat n
     d : u8 repeat 2
     e : u8 repeat n + 1
     f : u8 @at n
     g : u8 @at 4
     h : u8 @at n - 1
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.a ex:Root.b ex:Root.c ex:Root.d ex:Root.e ex:Root.f ex:Root.g ex:Root.h ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 3 .
   ex:Root.b a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.n * 2" .
   ex:Root.c a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromField ex:Root.n .
   ex:Root.d a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 .
   ex:Root.e a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromExpression "instance.n + 1" .
   ex:Root.f a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffsetFromField ex:Root.n .
   ex:Root.g a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffset 4 .
   ex:Root.h a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:atOffsetFromExpression "instance.n - 1" .
   """)

hc("checksum-fixed-terminator", "Checksums, fixed values and terminators",
   "@checksum crc32(a .. b) covers from field a to field b; an integer @fixed on an i32 is typed xsd:int and a hex @fixed stays "
   "xsd:hexBinary; @terminator gives the terminator bytes.",
   OK + ["req-hdl-clauses-1"], ["clauses"],
   """
   format t @namespace "{ns}"
   struct Root {
     magic : bytes[4] @fixed 0x89504E47
     code : i32 @fixed 9994
     name : ascii @terminator 0x00
     crc : u32 @checksum crc32(magic .. name)
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.magic ex:Root.code ex:Root.name ex:Root.crc ) .
   ex:Root.magic a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "89504E47"^^xsd:hexBinary .
   ex:Root.code a bddo:Field ; bddo:dataType bddo:int32 ; bddo:hasFixedValue "9994"^^xsd:int .
   ex:Root.name a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:ascii ; bddo:terminator "00"^^xsd:hexBinary .
   ex:Root.crc a bddo:Field ; bddo:dataType bddo:uint32 ;
       bddo:checksum [ a bddo:Checksum ; bddo:checksumAlgorithm bddo:crc32 ; bddo:coversFromField ex:Root.magic ; bddo:coversToField ex:Root.name ] .
   """)

hc("switch", "A switch compiles to an ordered bddo:hasConditionalDataType list",
   "Literal arms test the discriminator; a type-less switch field declares no bddo:dataType of its own.",
   OK + ["req-hdl-conformance-section-5"], ["structure", "types", "clauses"],
   """
   format t @namespace "{ns}"
   struct Root {
     kind : ascii[4]
     body : switch kind {
       "IHDR" => A
       "PLTE" => B
     }
   }
   struct A { a : u8 }
   struct B { b : u16 }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.kind ex:Root.body ) .
   ex:Root.kind a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
   ex:Root.body a bddo:Field ; bddo:hasConditionalDataType (
       [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 'IHDR'" ; bddo:ruleDataType ex:A ]
       [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 'PLTE'" ; bddo:ruleDataType ex:B ] ) .
   ex:A a bddo:Struct ; bddo:hasField ( ex:A.a ) .
   ex:A.a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:B a bddo:Struct ; bddo:hasField ( ex:B.b ) .
   ex:B.b a bddo:Field ; bddo:dataType bddo:uint16 .
   """)

hc("semantic-mapping", "means maps a struct to a class and a field to a property; value and @datatype give a computed value",
   "The prefix ex: is bound with use, since the base namespace has no text-surface spelling.",
   OK + ["req-hdl-conformance-section-4"], ["semantic", "prefixes"],
   """
   format t @namespace "{ns}"
   use ex: <{ns}>
   struct Root means ex:Reading {
     raw : i16 means ex:celsius value raw * 0.5 @datatype xsd:double
   }
   """,
   """
   ex:Root a bddo:Struct ; hexplain:mapsToClass ex:Reading ; bddo:hasField ( ex:Root.raw ) .
   ex:Root.raw a bddo:Field ; bddo:dataType bddo:int16 ; hexplain:mapsToProperty ex:celsius ;
       hexplain:valueExpression "instance.raw * 0.5" ; hexplain:valueDatatype xsd:double .
   """)

hc("contextual-keywords", "Keywords are contextual: a field may be named type, size or value",
   "Only HEL's reserved words are refused as field names.",
   OK + ["req-hdl-grammar-1", "req-hdl-conformance-section-3"], ["lexical", "grammar-keywords"],
   """
   hdl 1.0
   format t @namespace "{ns}"
   struct Root {
     type : u8
     size : u8
     value : bytes[size]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.type ex:Root.size ex:Root.value ) .
   ex:Root.type a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.size a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.value a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:Root.size .
   """)

hc("raw-turtle", "raw-turtle bodies are preserved in the output graph",
   "The injected triple appears verbatim.",
   OK + ["req-hdl-conformance-section-8"], ["escape-hatch"],
   """
   format t @namespace "{ns}"
   struct Root {
     a : u8
     raw-turtle { :Root rdfs:comment "hand-written note" . }
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ) ; rdfs:comment "hand-written note" .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

hc("bundle-profile", "A bundle compiles to an abnd:BundleProfile with one abnd:PartSpec per part",
   "role Payload resolves in the part-role register; carries names the aspect's ontology IRI (its namespace without the '#').",
   OK + ["req-hdl-prefixes-1"], ["bundle-profile", "prefixes"],
   """
   format t @namespace "{ns}"
   use araster: <https://hexplain.io/ns/aspect/raster#>
   bundle Sidecar @bound-by naming-convention {
     part ".dat" role Payload required primary carries araster: described-by Grid
   }
   struct Grid { v : u8 }
   """,
   """
   ex:Sidecar a abnd:BundleProfile ; abnd:boundBy abnd:NamingConvention ;
       abnd:partSpec [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole <https://hexplain.io/ns/register/part-role#Payload> ;
                       abnd:required true ; abnd:primary true ; abnd:carriesAspect <https://hexplain.io/ns/aspect/raster> ;
                       abnd:describedBy ex:Grid ] .
   ex:Grid a bddo:Struct ; bddo:hasField ( ex:Grid.v ) .
   ex:Grid.v a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

# ----------------------------------------------------------------- diagnostics


def err(id, title, intent, reqs, sections, source, line=None):
    hc(id, title, intent, ["req-hdl-compilation-model-1", "req-hdl-conformance-section-7"] + reqs, sections, source, line=line)


err("undeclared-prefix", "A CURIE whose prefix is not bound is an ERROR, never an emitted IRI",
    "foo: is neither predeclared nor bound by use.",
    ["req-hdl-prefixes-2", "req-hdl-conformance-section-4"], ["prefixes"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 means foo:bar
    }
    """, line=3)

err("aspect-prefix-not-predeclared", "Aspect prefixes are not predeclared",
    "araster: must be bound with use before a means can name it.",
    ["req-hdl-prefixes-1", "req-hdl-prefixes-2"], ["prefixes"],
    """
    format t @namespace "{ns}"
    struct Root {
      w : u32 means araster:width
    }
    """, line=3)

err("hyphenated-field-name", "A hyphenated field name is an ERROR",
    "byte-order folds to one name token but is not a HEL identifier.",
    ["req-hdl-lexical-1", "req-hdl-lexical-2", "req-hdl-grammar-lexical-1", "req-hdl-conformance-section-9"], ["lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      byte-order : u8
    }
    """, line=3)

err("reserved-field-name", "A field named after a HEL reserved word is an ERROR",
    "asset is HEL's multi-part root, so a field so named could never be read.",
    ["req-hdl-lexical-2", "req-hdl-grammar-keywords-1", "req-hdl-conformance-section-9"], ["lexical", "grammar-keywords"],
    """
    format t @namespace "{ns}"
    struct Root {
      asset : u8
    }
    """, line=3)

err("reserved-alias", "An alias named after a HEL reserved word is an ERROR",
    "as self.",
    ["req-hdl-lexical-1", "req-hdl-grammar-keywords-1"], ["lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a as self : u8
    }
    """, line=3)

err("undeclared-name", "A bare name that is no field of the struct is an ERROR",
    "bytes[lenght] names no field.",
    ["req-hdl-expressions-1", "req-hdl-conformance-section-5"], ["expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      length : u8
      data : bytes[lenght]
    }
    """, line=4)

err("forward-reference", "A size naming a later field is an ERROR",
    "The compiler knows the declaration order, so a forward reference is statically determinable.",
    ["req-hdl-expressions-1", "req-hdl-conformance-section-5"], ["expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[n]
      n : u8
    }
    """, line=3)

err("self-reference", "A field's size naming the field itself is an ERROR outside @valid",
    "bytes[data] refers to itself.",
    ["req-hdl-expressions-1"], ["expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[data]
    }
    """, line=3)

err("self-outside-scope", "self outside repeat until, @valid and a quantifier is an ERROR",
    "A presence condition has no value under test.",
    ["req-hdl-expressions-1"], ["expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 if self == 1
    }
    """, line=3)

err("unknown-stream-key", "A stream key other than length, position and remaining is an ERROR",
    "stream.size.",
    ["req-hdl-expressions-1"], ["expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[stream.size]
    }
    """, line=3)

err("evaluation-instant-in-parse", "evaluationInstant() in an expression evaluated while parsing is an ERROR",
    "It exists only for conformance assertions.",
    ["req-hdl-expressions-1"], ["expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 if evaluationInstant() > 0
    }
    """, line=3)

err("unknown-escape", "An escape outside the HEL escape set is an ERROR",
    "\\q in a string literal.",
    ["req-hdl-grammar-1", "req-hdl-conformance-section-3"], ["lexical", "grammar-lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      tag : ascii[2] @fixed "\\q"
    }
    """, line=3)

err("bad-hex-literal", "A hex literal with a non-hex character is a lexical ERROR",
    "0x12G4 is not a number followed by a name.",
    ["req-hdl-grammar-1"], ["lexical", "grammar-lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[2] @fixed 0x12G4
    }
    """, line=3)

err("unknown-character", "A character that cannot begin a token is a lexical ERROR",
    "A ; outside a string.",
    ["req-hdl-grammar-1"], ["lexical", "grammar-lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8;
    }
    """, line=3)

err("unterminated-comment", "A block comment open at end of input is a lexical ERROR",
    "The comment never closes.",
    ["req-hdl-grammar-1"], ["lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8
    }
    /* never closed
    """)

err("integer-literal-range", "An integer literal outside signed 64 bits is an ERROR",
    "Every INT fits in a signed 64-bit integer.",
    ["req-hdl-grammar-1"], ["lexical", "grammar-common"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u64 @fixed 99999999999999999999
    }
    """, line=3)

err("seek-without-at", "@seek on a field with no @at is an ERROR",
    "Seek scope only bounds an offset-addressed read.",
    ["req-hdl-grammar-1"], ["modules", "grammar-fields"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @seek stream
    }
    """, line=3)

err("min-without-pattern", "min or max on a part without a pattern is an ERROR",
    "An extension names one member.",
    ["req-hdl-grammar-1"], ["bundle-profile"],
    """
    format t @namespace "{ns}"
    bundle B {
      part ".dat" role Payload min 1 max 3
    }
    """, line=3)

err("max-below-min", "A part whose max is below its min is an ERROR",
    "No file count could satisfy it.",
    ["req-hdl-grammar-1"], ["bundle-profile"],
    """
    format t @namespace "{ns}"
    bundle B {
      part pattern "*.dat" role Payload min 3 max 1
    }
    """, line=3)

err("unsupported-version", "A version declaration naming a version the compiler does not implement is an ERROR",
    "hdl 2.0 is not compiled under the rules of 1.0.",
    ["req-hdl-versioning-1", "req-hdl-conformance-section-11"], ["versioning"],
    """
    hdl 2.0
    format t @namespace "{ns}"
    struct Root { a : u8 }
    """, line=1)

err("version-not-first", "A version declaration anywhere but first is an ERROR",
    "hdl 1.0 after the format declaration.",
    ["req-hdl-grammar-1"], ["versioning"],
    """
    format t @namespace "{ns}"
    hdl 1.0
    struct Root { a : u8 }
    """, line=2)

err("backtick-in-run", "A backtick expression inside a longer run is an ERROR",
    "Backticks are all or nothing.",
    ["req-hdl-grammar-expressions-3"], ["grammar-expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      n : u8
      data : bytes[..] if `instance.n` == 1
    }
    """, line=4)

err("layout-name-not-sibling", "A layout name that is not a sibling field is an ERROR",
    "dim axis X size width names no field of the struct.",
    ["req-hdl-expressions-2", "req-hdl-grammar-layout-1", "req-hdl-conformance-section-9"], ["layout", "grammar-layout"],
    """
    format t @namespace "{ns}"
    struct Root {
      w : u8
      pixels : bytes[..] layout cell u8 { dim axis X size width }
    }
    """, line=4)

err("pipeline-non-integer-parameter", "A pipeline step parameter that is not an integer literal is an ERROR",
    "The Processing Model rejects any other parameter value.",
    ["req-hdl-grammar-fields-1"], ["semantic", "grammar-fields"],
    """
    format t @namespace "{ns}"
    use menc: <https://hexplain.io/ns/register/media-encoding#>
    struct Root {
      strip : bytes[..] @pipeline { menc:Delta(elementSize "one") }
    }
    """, line=4)

err("format-without-struct", "A format that declares no struct, container, bundle or asset is an ERROR",
    "There is no root.",
    ["req-hdl-grammar-document-1"], ["grammar-document"],
    """
    format t @namespace "{ns}"
    use ex: <{ns}>
    """)

err("import-outside-root", "An import resolving outside the import root is an ERROR",
    "By default the root is the importing document's directory; ../ escapes it.",
    ["req-hdl-modules-1", "req-hdl-modules-2", "req-hdl-conformance-section-10"], ["import-resolution", "modules"],
    """
    format t @namespace "{ns}"
    import "../../physical-parser/pp-int-default-big-endian/description.ttl" as other
    struct Root { a : u8 }
    """, line=2)

hc("raw-hel", "A backtick expression is emitted verbatim",
   "The raw HEL string reaches bddo:sizeFromExpression unchanged: no rewriting of names, spacing or literals.",
   OK + ["req-hdl-grammar-expressions-2"], ["raw-hel", "grammar-expressions"],
   """
   format t @namespace "{ns}"
   struct Root {
     n : u8
     data : bytes[`instance.n*2`]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.n ex:Root.data ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.n*2" .
   """)

hc("yaml-surface", "The YAML surface compiles to the same graph, and resolves only true and false as Booleans",
   "A field named on stays the name on (YAML 1.1 would read it as a Boolean); the lone sibling in size is the ...FromField form.",
   OK + ["req-hdl-conformance-section-2", "req-hdl-yaml-1", "req-hdl-form-rule-1"], ["yaml"],
   """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: on, type: u8 }
         - { name: data, type: bytes, size: on }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.on ex:Root.data ) .
   ex:Root.on a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:Root.on .
   """, yaml=True)
