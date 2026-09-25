"""HDL Compiler cases: an .hx source compiles to the expected Turtle (compared by isomorphism,
literals by value), or is refused with an ERROR diagnostic, at the stated line when the case gives one.

Each source declares @namespace "https://example.org/<case-id>#", the namespace the expected
Turtle's ex: prefix is bound to.
"""
from suite import Case, dedent, namespace

HDL = "hdl/index.html#"
CASES = []
USE = 'use ex: <{ns}>'


def hc(id, title, intent, reqs, sections, source, expected_ttl=None, line=None, manifest=None, yaml=False, files=None,
       input=None):
    """One HDL Compiler case: `source` is the .hx (or, with yaml, the .hx.yaml) document; `files` are further files of
    the case directory (modules it imports), `input` the source's path within it when not the default."""
    case_id = f"hc-{id}"
    ns = namespace(case_id)
    source = source.replace("{ns}", ns)
    error = None if expected_ttl is not None else ({"severity": "ERROR", "line": line} if line else {"severity": "ERROR"})
    name = input or ("input.hx.yaml" if yaml else "input.hx")
    man = {"input": name}
    man.update(manifest or {})
    extra = {k: (dedent(v.replace("{ns}", ns)) if isinstance(v, str) else v) for k, v in (files or {}).items()}
    if yaml or input:
        extra[name] = dedent(source)
    CASES.append(Case(id=case_id, cls="hdl-compiler", title=title, intent=intent,
                      requirements=["req-hdl-conformance-section-1"] + reqs,
                      sections=[HDL + s if "#" not in s else s for s in sections],
                      hdl=None if (yaml or input) else source, files=extra,
                      expected_ttl=expected_ttl, hdl_error=error, root=None, manifest=man))


def pair(id, title, intent, reqs, sections, text, yaml, expected_ttl, manifest=None):
    """A successful compilation on both surfaces: the text document and its YAML mirror compile to the same graph
    (HDL, Conformance: the two surfaces parse to one abstract model)."""
    hc(id, title, intent, reqs, sections, text, expected_ttl, manifest=manifest)
    hc(id + "-yaml", title + " (YAML surface)",
       intent + " The YAML mirror of the text document compiles to the same graph.",
       reqs + ["req-hdl-conformance-section-2"], sections + ["yaml"], yaml, expected_ttl, manifest=manifest, yaml=True)


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


def err(id, title, intent, reqs, sections, source, line=None, **kw):
    hc(id, title, intent, ["req-hdl-compilation-model-1", "req-hdl-conformance-section-7"] + reqs, sections, source, line=line,
       **kw)


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
    "The root document is src/input.hx, so the import root is src/. The import names ../lib/mod.hx, a module that exists in "
    "the case directory but outside that root: the import is refused for escaping the root, not because the file is missing.",
    ["req-hdl-modules-1", "req-hdl-modules-2", "req-hdl-conformance-section-10"], ["import-resolution", "modules"],
    """
    format t @namespace "{ns}"
    import "../lib/mod.hx" as lib
    struct Root { b : lib:Box }
    """, line=2, input="src/input.hx",
    files={"lib/mod.hx": """
    module lib @namespace "https://example.org/hc-import-outside-root/lib#"
    struct Box { n : u8 }
    """})

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


# ----------------------------------------------------------------- YAML mirrors of the successful compilations
#
# HDL, Conformance: a text document and its YAML mirror compile to isomorphic graphs. Each successful text case
# above has a mirror here with the same expected graph (its ex: prefix bound to the mirror's own namespace).


def twin(id, yaml, note=""):
    original = next(c for c in CASES if c.id == f"hc-{id}")
    hc(id + "-yaml", original.title + " (YAML surface)",
       original.intent + " The YAML mirror compiles to the same graph." + (" " + note if note else ""),
       [r for r in original.requirements if r != "req-hdl-conformance-section-1"] + ["req-hdl-conformance-section-2"],
       [s for s in original.sections] + [HDL + "yaml"], yaml, original.expected_ttl,
       manifest={k: v for k, v in original.manifest.items() if k != "input"}, yaml=True)


twin("struct-and-types", """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: n, type: u16 }
         - { name: tag, type: ascii, size: 4 }
         - { name: k, type: i32le }
         - { name: f, type: f64 }
         - { name: data, type: bytes, size: n }
   """)

twin("field-and-expression-forms", """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: n, type: u8 }
         - { name: a, type: bytes, size: 3 }
         - { name: b, type: bytes, size: "n * 2" }
         - { name: c, type: u8, repeat: { count: n } }
         - { name: d, type: u8, repeat: { count: 2 } }
         - { name: e, type: u8, repeat: { count: "n + 1" } }
         - { name: f, type: u8, at: { offset: n } }
         - { name: g, type: u8, at: { offset: 4 } }
         - { name: h, type: u8, at: { offset: "n - 1" } }
   """)

twin("checksum-fixed-terminator", """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: magic, type: bytes, size: 4, fixed: 0x89504E47 }
         - { name: code, type: i32, fixed: 9994 }
         - { name: name, type: ascii, terminator: 0x00 }
         - { name: crc, type: u32, checksum: { algorithm: crc32, from: magic, to: name } }
   """, "An unquoted 0x89504E47 is a hex byte string, as @fixed 0x89504E47 is in text.")

twin("switch", """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: kind, type: ascii, size: 4 }
         - name: body
           type: switch
           switch: { on: kind, cases: { IHDR: A, PLTE: B } }
     A:
       fields:
         - { name: a, type: u8 }
     B:
       fields:
         - { name: b, type: u16 }
   """, "The cases are taken in document order.")

twin("semantic-mapping", """
   format: t
   namespace: "{ns}"
   use: { ex: "{ns}" }
   structs:
     Root:
       means: ex:Reading
       fields:
         - { name: raw, type: i16, means: ex:celsius, value: { expr: "raw * 0.5", datatype: "xsd:double" } }
   """)

twin("contextual-keywords", """
   hdl: 1.0
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: type, type: u8 }
         - { name: size, type: u8 }
         - { name: value, type: bytes, size: size }
   """)

twin("raw-turtle", """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: a, type: u8 }
       raw-turtle: ':Root rdfs:comment "hand-written note" .'
   """)

twin("bundle-profile", """
   format: t
   namespace: "{ns}"
   use: { araster: "https://hexplain.io/ns/aspect/raster#" }
   bundles:
     Sidecar:
       bound-by: naming-convention
       parts:
         - { extension: ".dat", role: Payload, required: true, primary: true, carries: araster, described-by: Grid }
   structs:
     Grid:
       fields:
         - { name: v, type: u8 }
   """)

twin("raw-hel", """
   format: t
   namespace: "{ns}"
   structs:
     Root:
       fields:
         - { name: n, type: u8 }
         - { name: data, type: bytes, size: "`instance.n*2`" }
   """)

hc("yaml-surface-text", "A field named on compiles on the text surface to the graph its YAML mirror gives",
   "The text mirror of hc-yaml-surface: on is a contextual keyword only in keyword position, so it names a field here.",
   OK + ["req-hdl-conformance-section-2", "req-hdl-form-rule-1"], ["yaml", "grammar-keywords"],
   """
   format t @namespace "{ns}"
   struct Root {
     on : u8
     data : bytes[on]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.on ex:Root.data ) .
   ex:Root.on a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromField ex:Root.on .
   """)

# ----------------------------------------------------------------- new successful compilations, on both surfaces

pair("root-key", "@root-key compiles to bddo:rootKeyFromField, and root.<key> is then accepted for a key only the data names",
     "alpha is no field of the root struct, but Rec declares @root-key, so root.alpha is a key the data may bind.",
     OK + ["req-hdl-expressions-3"], ["clauses", "root-keys"],
     """
     format t @namespace "{ns}"
     struct Root {
       recs : Rec repeat 2
       total : derive root.alpha
     }
     struct Rec {
       name : ascii[5]
       v : u8 @root-key name
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: recs, type: Rec, repeat: { count: 2 } }
           - { name: total, derive: root.alpha }
       Rec:
         fields:
           - { name: name, type: ascii, size: 5 }
           - { name: v, type: u8, root-key: name }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.recs ex:Root.total ) .
     ex:Root.recs a bddo:Field ; bddo:dataType ex:Rec ; bddo:repeatCount 2 .
     ex:Root.total a bddo:Field ; bddo:valueFromExpression "root.alpha" .
     ex:Rec a bddo:Struct ; bddo:hasField ( ex:Rec.name ex:Rec.v ) .
     ex:Rec.name a bddo:Field ; bddo:dataType bddo:string ; bddo:size 5 ; bddo:encoding bddo:ascii .
     ex:Rec.v a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:rootKeyFromField ex:Rec.name .
     """)

pair("repeat-until-container-fallback", "A repeat-until bare name that the element does not declare is the container's field",
     "kind is a field of the element and is emitted instance.kind; stop is not, so it falls back to the struct holding the "
     "repeated field and is emitted parent.stop, which is what HEL binds parent to there.",
     OK + ["req-hdl-expressions-4", "req-hel-name-binding-1"], ["repeat-until-names", "expressions"],
     """
     format t @namespace "{ns}"
     struct Root {
       stop : u8
       recs : Rec repeat until kind == stop
     }
     struct Rec { kind : u8 }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: stop, type: u8 }
           - { name: recs, type: Rec, repeat: { until: "kind == stop" } }
       Rec:
         fields:
           - { name: kind, type: u8 }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.stop ex:Root.recs ) .
     ex:Root.stop a bddo:Field ; bddo:dataType bddo:uint8 .
     ex:Root.recs a bddo:Field ; bddo:dataType ex:Rec ; bddo:repeatUntil "instance.kind == parent.stop" .
     ex:Rec a bddo:Struct ; bddo:hasField ( ex:Rec.kind ) .
     ex:Rec.kind a bddo:Field ; bddo:dataType bddo:uint8 .
     """)

pair("switch-name-key", "A bare name as a switch arm key is a string key",
     "IHDR => A tests kind == 'IHDR', exactly as the quoted \"IHDR\" does.",
     OK + ["req-hdl-clauses-5"], ["literal-values", "clauses"],
     """
     format t @namespace "{ns}"
     struct Root {
       kind : ascii[4]
       body : switch kind { IHDR => A }
     }
     struct A { a : u8 }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: kind, type: ascii, size: 4 }
           - { name: body, type: switch, switch: { on: kind, cases: { IHDR: A } } }
       A:
         fields:
           - { name: a, type: u8 }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.kind ex:Root.body ) .
     ex:Root.kind a bddo:Field ; bddo:dataType bddo:string ; bddo:size 4 ; bddo:encoding bddo:ascii .
     ex:Root.body a bddo:Field ; bddo:hasConditionalDataType (
         [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 'IHDR'" ; bddo:ruleDataType ex:A ] ) .
     ex:A a bddo:Struct ; bddo:hasField ( ex:A.a ) .
     ex:A.a a bddo:Field ; bddo:dataType bddo:uint8 .
     """)

pair("fixed-strings", "A string @fixed stays a string, on a bytes field as on a string field",
     "\"CAFE\" and \"1234\" are strings, not hex digits or a number: they are emitted as xsd:string literals, which the "
     "Processing Model compares with a bytes field as UTF-8 and with a UTF-16 string field by code points.",
     OK + ["req-hdl-clauses-1", "req-hdl-clauses-5", "req-hdl-form-rule-2"], ["clauses", "literal-values"],
     """
     format t @namespace "{ns}"
     struct Root {
       a : bytes[4] @fixed "CAFE"
       b : bytes[4] @fixed "1234"
       c : utf16le[4] @fixed "AB"
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: a, type: bytes, size: 4, fixed: "CAFE" }
           - { name: b, type: bytes, size: 4, fixed: "1234" }
           - { name: c, type: utf16le, size: 4, fixed: "AB" }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ex:Root.b ex:Root.c ) .
     ex:Root.a a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "CAFE" .
     ex:Root.b a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "1234" .
     ex:Root.c a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf16le ; bddo:size 4 ; bddo:hasFixedValue "AB" .
     """)

pair("quoted-header-keys", "Header fields: quoted keys, with and without an alias, and an unquoted name",
     "A quoted key is located by that key; an expression reaches it only through its alias, which also replaces its IRI's "
     "local name (\"samples\" as n is <base>n); \"bands\", with no alias, keeps the IRI <base>H.bands; the unquoted lines "
     "is located by its own name, so no bddo:key is emitted for it.",
     OK + ["req-hdl-lexical-2", "req-hdl-conformance-section-5"], ["lexical", "delimited", "iri-minting"],
     """
     format t @namespace "{ns}"
     header H @record-separator 0x0A @separator 0x3D @trim {
       "samples" as n : anum
       "byte order" as order : anum
       "bands" : anum
       lines : anum if n > 0
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       H:
         kind: header
         record-separator: 0x0A
         separator: 0x3D
         trim: true
         fields:
           - { key: samples, as: n, type: anum }
           - { key: "byte order", as: order, type: anum }
           - { key: bands, type: anum }
           - { name: lines, type: anum, if: "n > 0" }
     """,
     """
     ex:H a bddo:KeyValueHeader ; bddo:recordDelimiter "0A"^^xsd:hexBinary ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ;
         bddo:trimWhitespace true ; bddo:hasField ( ex:n ex:order ex:H.bands ex:H.lines ) .
     ex:n a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "samples" .
     ex:order a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "byte order" .
     ex:H.bands a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "bands" .
     ex:H.lines a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:isPresentIf "instance.n > 0" .
     """)

pair("layout-cell", "A layout with a header cell type compiles to a dlv:DataLayout with ordered dimensions",
     "cell u8 is the cell type; the dimensions are listed slowest first, each sized by a sibling. On the YAML surface the "
     "layout is a mapping under the field's layout key, and a scalar cell is the header form.",
     OK + ["req-hdl-expressions-2"], ["layout", "yaml"],
     """
     format t @namespace "{ns}"
     struct Image {
       w : u8
       h : u8
       pixels : bytes[..] layout cell u8 {
         dim axis Y size h
         dim axis X size w
       }
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Image:
         fields:
           - { name: w, type: u8 }
           - { name: h, type: u8 }
           - name: pixels
             type: bytes
             size: ".."
             layout:
               cell: u8
               dims:
                 - { axis: Y, size: h }
                 - { axis: X, size: w }
     """,
     """
     ex:Image a bddo:Struct ; bddo:hasField ( ex:Image.w ex:Image.h ex:Image.pixels ) .
     ex:Image.w a bddo:Field ; bddo:dataType bddo:uint8 .
     ex:Image.h a bddo:Field ; bddo:dataType bddo:uint8 .
     ex:Image.pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ;
         hexplain:hasDataLayout [ a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ;
             dlv:hasDimension ( [ a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSizeFromField ex:Image.h ]
                                [ a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:Image.w ] ) ] .
     """)

pair("prop-values", "@prop takes a string, an integer or a CURIE value",
     "Each @prop emits one triple on the field; the integer is an xsd:integer. On the YAML surface a CURIE value is written "
     "as a { curie: ... } mapping, since a bare scalar there is a string.",
     OK + ["req-hdl-clauses-5", "req-hdl-form-rule-2"], ["escape-hatch", "literal-values", "literal-datatypes"],
     """
     format t @namespace "{ns}"
     use ex: <{ns}>
     struct Root {
       a : u8 @prop rdfs:comment "a note" @prop ex:rank 3 @prop ex:kind ex:Primary
     }
     """,
     """
     format: t
     namespace: "{ns}"
     use: { ex: "{ns}" }
     structs:
       Root:
         fields:
           - name: a
             type: u8
             prop: { "rdfs:comment": "a note", "ex:rank": 3, "ex:kind": { curie: "ex:Primary" } }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ) .
     ex:Root.a a bddo:Field ; bddo:dataType bddo:uint8 ; rdfs:comment "a note" ; ex:rank 3 ; ex:kind ex:Primary .
     """)

hc("prop-iri", "@prop takes an IRIREF value",
   "An angle-bracket IRI after @prop is the object IRI, not a string.",
   OK + ["req-hdl-clauses-5"], ["escape-hatch", "literal-values"],
   """
   format t @namespace "{ns}"
   struct Root {
     a : u8 @prop rdfs:seeAlso <https://example.org/spec>
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:uint8 ; rdfs:seeAlso <https://example.org/spec> .
   """)

hc("import-within-root", "An import inside the import root compiles, and the ontology carries owl:imports",
   "lib/mod.hx lies in the root document's directory tree. The importing document's ontology (its base namespace without "
   "the #) imports the module's; the module's own triples are not re-emitted. The case compares the ontology header.",
   OK + ["req-hdl-modules-1"], ["modules", "import-resolution"],
   """
   format t @namespace "{ns}"
   import "lib/mod.hx" as lib
   struct Root { b : lib:Box }
   """,
   """
   <https://example.org/hc-import-within-root> a <http://www.w3.org/2002/07/owl#Ontology> ;
       <http://www.w3.org/2002/07/owl#imports> <https://example.org/hc-import-within-root/lib> .
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.b ) .
   ex:Root.b a bddo:Field ; bddo:dataType <https://example.org/hc-import-within-root/lib#Box> .
   """,
   manifest={"compareOntologyHeader": True},
   files={"lib/mod.hx": """
   module lib @namespace "https://example.org/hc-import-within-root/lib#"
   struct Box { n : u8 }
   """})

# ----------------------------------------------------------------- new diagnostics (round 3 regressions and rules)

err("root-path-without-root-key", "root.<k> naming no root field is an ERROR when no struct declares @root-key",
    "Without @root-key nothing can bind alpha in the root context, so root.alpha is an undeclared name.",
    ["req-hdl-expressions-1", "req-hdl-expressions-3"], ["root-keys", "expressions"],
    """
    format t @namespace "{ns}"
    struct Root {
      n : u8
      total : derive root.alpha
    }
    """, line=4)

err("bracket-size-on-u32", "A bracket size on a fixed-width numeric type is an ERROR",
    "u32[4] is neither four bytes of something nor four elements; the Processing Model would ignore the size.",
    ["req-hdl-types-1"], ["types"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u32[4]
    }
    """, line=3)

err("two-sizes", "A field with two size clauses is an ERROR", "bytes[2] and then [4].",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[2] [4]
    }
    """, line=3)

err("two-counts", "A field with two repeat clauses is an ERROR", "repeat 2 and repeat 3.",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 repeat 2 repeat 3
    }
    """, line=3)

err("count-and-until", "A field with a repeat count and a repeat-until condition is an ERROR", "repeat 2 and repeat until eof().",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 repeat 2 repeat until eof()
    }
    """, line=3)

err("two-offsets", "A field with two @at clauses is an ERROR", "@at 1 and @at 2.",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @at 1 @at 2
    }
    """, line=3)

err("two-fixed", "A field with two @fixed clauses is an ERROR", "@fixed 1 and @fixed 2.",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @fixed 1 @fixed 2
    }
    """, line=3)

err("two-endian", "A field with two @endian clauses is an ERROR", "@endian big and @endian little.",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u16 @endian big @endian little
    }
    """, line=3)

err("switch-and-dispatch", "A field with both switch and dispatch is an ERROR", "Two type selections on one field.",
    ["req-hdl-clauses-2"], ["clause-multiplicity", "grammar-fields"],
    """
    format t @namespace "{ns}"
    struct Root {
      kind : u8
      body : switch kind { 1 => A } dispatch T on kind { 2 => A }
    }
    struct A { a : u8 }
    """, line=4)

err("derive-with-repeat", "A derived field with a repeat clause is an ERROR", "A derived field reads no bytes and has no elements.",
    ["req-hdl-clauses-3"], ["clause-multiplicity", "types"],
    """
    format t @namespace "{ns}"
    struct Root {
      d : derive 1 repeat 2
    }
    """, line=3)

err("pipeline-and-encoded-with", "@pipeline together with @encoded-with is an ERROR", "The two encoding forms are mutually exclusive.",
    ["req-hdl-clauses-3"], ["clause-multiplicity", "semantic"],
    """
    format t @namespace "{ns}"
    use menc: <https://hexplain.io/ns/register/media-encoding#>
    struct Root {
      a : bytes[..] @encoded-with menc:Zlib @pipeline { menc:Zlib }
    }
    """, line=4)

err("duplicate-struct", "Two struct declarations of one name are an ERROR", "struct A is declared twice.",
    ["req-hdl-clauses-3"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct A { a : u8 }
    struct A { b : u8 }
    """, line=3)

err("negative-size", "A negative literal size is an ERROR", "bytes[-1].",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[-1]
    }
    """, line=3)

err("negative-count", "A negative literal repeat count is an ERROR", "repeat -2.",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 repeat -2
    }
    """, line=3)

err("negative-offset", "A negative literal offset is an ERROR", "@at -4.",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @at -4
    }
    """, line=3)

err("stride-zero", "stride 0 is an ERROR", "A zero stride would address every cell at one place.",
    ["req-hdl-clauses-4"], ["literal-values", "layout"],
    """
    format t @namespace "{ns}"
    struct Root {
      w : u8
      pixels : bytes[..] layout cell u8 { dim axis X size w stride 0 }
    }
    """, line=4)

err("float-count", "A float literal as a repeat count is an ERROR", "repeat 2.0: an integral float is not an integer.",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 repeat 2.0
    }
    """, line=3)

err("float-size", "A float literal as a size is an ERROR", "bytes[1.5].",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[1.5]
    }
    """, line=3)

err("non-ascii-digit", "A non-ASCII digit is a lexical ERROR, never a digit", "repeat ٣ (ARABIC-INDIC DIGIT THREE).",
    ["req-hdl-lexical-3"], ["lexical", "grammar-lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 repeat ٣
    }
    """, line=3)

err("lone-surrogate", "A \\u escape naming a lone surrogate is an ERROR", "\\uD800 not followed by a low surrogate.",
    ["req-hdl-lexical-3", "req-hel-formal-grammar-1"], ["lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : utf16le[2] @fixed "\\uD800"
    }
    """, line=3)

err("prop-bare-name", "@prop with a bare name value is an ERROR", "note is neither a string, a CURIE nor an IRI.",
    ["req-hdl-clauses-5"], ["literal-values", "escape-hatch"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @prop rdfs:comment note
    }
    """, line=3)

err("fixed-name", "@fixed with a bare name is an ERROR", "@fixed takes an integer, hex or string literal.",
    ["req-hdl-clauses-5"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : ascii[4] @fixed IHDR
    }
    """, line=3)

err("fixed-curie", "@fixed with a CURIE is an ERROR", "A CURIE is no field value.",
    ["req-hdl-clauses-5"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @fixed xsd:int
    }
    """, line=3)

err("fixed-boolean", "@fixed with a Boolean is an ERROR", "No field type holds a Boolean.",
    ["req-hdl-clauses-5"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @fixed true
    }
    """, line=3)

err("repeat-until-ambiguous", "A repeat-until bare name both the element and the container declare is an ERROR",
    "kind is a field of Rec and of Root: either reading would be a guess.",
    ["req-hdl-expressions-4"], ["repeat-until-names"],
    """
    format t @namespace "{ns}"
    struct Root {
      kind : u8
      recs : Rec repeat until kind == 0
    }
    struct Rec { kind : u8 }
    """, line=4)

# Forward references in each role, and through root. and parent.
FWD = ["req-hdl-expressions-1", "req-hdl-conformance-section-5"]
for role, body, line in [
        ("count", "a : u8 repeat n\n  n : u8", 3),
        ("offset", "a : u8 @at n\n  n : u8", 3),
        ("presence", "a : u8 if n == 1\n  n : u8", 3),
        ("derive", "d : derive n + 1\n  n : u8", 3),
        ("switch", "body : switch { when n == 1 => A }\n  n : u8", 3),
        ("dispatch", "body : bytes[..] dispatch T on n { 1 => A }\n  n : u8", 3),
        ("valid", "a : u8 @valid self < n\n  n : u8", 3),
        ("checksum-covers", "s : u32 @checksum crc32(covers(0, n))\n  n : u8", 3)]:
    err(f"forward-{role}", f"A forward reference in a {role} expression is an ERROR",
        f"The {role} expression names n, which is declared after the field it describes.",
        FWD, ["forward-references", "expressions"],
        'format t @namespace "{ns}"\nstruct Root {\n  %s\n}\nstruct A { a : u8 }\n' % body, line=line)

err("forward-repeat-until-container", "A repeat-until fallback to a container field declared later is a forward reference",
    "stop falls back to Root.stop, which is read after recs.",
    FWD + ["req-hdl-expressions-4"], ["forward-references", "repeat-until-names"],
    """
    format t @namespace "{ns}"
    struct Root {
      recs : Rec repeat until kind == stop
      stop : u8
    }
    struct Rec { kind : u8 }
    """, line=3)

err("forward-root-path", "A root. path to a root field bound after the one leading to the expression is an ERROR",
    "Root.hdr holds Hdr, whose size reads root.n; Root.n is declared after hdr, so it is not bound when Hdr is read.",
    FWD, ["forward-references"],
    """
    format t @namespace "{ns}"
    struct Root {
      hdr : Hdr
      n : u8
    }
    struct Hdr {
      data : bytes[root.n]
    }
    """, line=7)

err("forward-parent-path", "A parent. path from a struct with a single container, to a later container field, is an ERROR",
    "Only Root.hdr holds Hdr, so parent is Root; parent.n is declared after hdr.",
    FWD, ["forward-references"],
    """
    format t @namespace "{ns}"
    struct Root {
      hdr : Hdr
      n : u8
    }
    struct Hdr {
      data : bytes[parent.n]
    }
    """, line=7)

# ----------------------------------------------------------------- YAML loader errors

err("yaml-duplicate-key", "A YAML mapping that repeats a key is an ERROR",
    "The field mapping gives type twice; last-wins would compile u16 and drop u8 silently.",
    ["req-hdl-yaml-2"], ["yaml"],
    """
    format: t
    namespace: "{ns}"
    structs:
      Root:
        fields:
          - name: a
            type: u8
            type: u16
    """, yaml=True)

err("yaml-duplicate-struct-key", "A YAML structs mapping that repeats a struct name is an ERROR",
    "Root is declared twice.",
    ["req-hdl-yaml-2", "req-hdl-clauses-3"], ["yaml", "clause-multiplicity"],
    """
    format: t
    namespace: "{ns}"
    structs:
      Root:
        fields:
          - { name: a, type: u8 }
      Root:
        fields:
          - { name: b, type: u8 }
    """, yaml=True)

err("yaml-null-list-entry", "A null entry in a YAML field list is an ERROR",
    "A stray - in the field list is a null entry, not nothing.",
    ["req-hdl-yaml-2"], ["yaml"],
    """
    format: t
    namespace: "{ns}"
    structs:
      Root:
        fields:
          - { name: a, type: u8 }
          -
    """, yaml=True)


# ----------------------------------------------------------------- further rules settled with the HDL compiler

err("quoted-key-without-alias", "A quoted header key is reached only through its alias",
    "\"samples\" has no alias, so the bare name samples in a later field's condition names no field.",
    ["req-hdl-lexical-2", "req-hdl-expressions-1"], ["lexical", "delimited"],
    """
    format t @namespace "{ns}"
    header H @record-separator 0x0A @separator 0x3D {
      "samples" : anum
      lines : anum if samples > 0
    }
    """, line=4)

err("bytes-without-size", "A bytes field of a binary struct with no size and no terminator is an ERROR",
    "Nothing gives the field an extent.",
    ["req-hdl-clauses-3"], ["clause-multiplicity", "types"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes
    }
    """, line=3)

err("size-zero", "A literal size of 0 is an ERROR", "bytes[0]: a size is at least 1.",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[0]
    }
    """, line=3)

err("float-offset", "A float literal as an offset is an ERROR", "@at 1e0 is the Float 1.0, not the offset 1.",
    ["req-hdl-clauses-4"], ["literal-values"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @at 1e0
    }
    """, line=3)

err("two-switches", "A field with two switch clauses is an ERROR", "Two type selections of the same kind.",
    ["req-hdl-clauses-2"], ["clause-multiplicity"],
    """
    format t @namespace "{ns}"
    struct Root {
      kind : u8
      body : switch kind { 1 => A } switch kind { 2 => A }
    }
    struct A { a : u8 }
    """, line=4)

err("fixed-string-on-numeric", "A string @fixed on a numeric field is an ERROR", "u8 @fixed \"12\": a string is characters.",
    ["req-hdl-clauses-5", "req-pm-parsefield-14"], ["literal-values", "clauses"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @fixed "12"
    }
    """, line=3)

err("fixed-integer-on-bytes", "An integer @fixed on a bytes field is an ERROR", "bytes[1] @fixed 7: an integer names no bytes.",
    ["req-hdl-clauses-5", "req-pm-parsefield-14"], ["literal-values", "clauses"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[1] @fixed 7
    }
    """, line=3)

err("non-ascii-hex-digit", "A non-ASCII digit in a hex literal is a lexical ERROR", "0x１２ uses fullwidth digits.",
    ["req-hdl-lexical-3"], ["lexical", "grammar-lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : bytes[1] @fixed 0x１２
    }
    """, line=3)

err("non-ascii-align", "A non-ASCII digit as an alignment is a lexical ERROR", "@align ٤ (ARABIC-INDIC DIGIT FOUR).",
    ["req-hdl-lexical-3"], ["lexical"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u8 @align ٤
    }
    """, line=3)

err("key-on-scalar", "A key step on a scalar field is an ERROR", "n is a u8; n.foo has no field foo.",
    ["req-hdl-expressions-5"], ["scalar-keys"],
    """
    format t @namespace "{ns}"
    struct Root {
      n : u8
      d : derive n.foo
    }
    """, line=4)

err("key-on-array", "A key step on a repeated field without a subscript is an ERROR", "es.size: the element count is len(es).",
    ["req-hdl-expressions-5"], ["scalar-keys"],
    """
    format t @namespace "{ns}"
    struct Root {
      es : E repeat 2
      d : derive es.size
    }
    struct E { v : u8 }
    """, line=4)

err("forward-layout-dimension", "A layout dimension sized by a later field is a forward reference",
    "The dimension's size names h, declared after the field that carries the layout.",
    FWD + ["req-hdl-expressions-2"], ["forward-references", "layout"],
    """
    format t @namespace "{ns}"
    struct Root {
      pixels : bytes[4] layout cell u8 { dim axis X size h }
      h : u8
    }
    """, line=3)

err("yaml-version-spelling", "hdl: 1.00 is not the version declaration 1.0", "The YAML declaration is spelt exactly 1.0 or \"1.0\".",
    ["req-hdl-versioning-1", "req-hdl-conformance-section-11"], ["yaml", "versioning"],
    """
    hdl: 1.00
    format: t
    namespace: "{ns}"
    structs:
      Root:
        fields:
          - { name: a, type: u8 }
    """, yaml=True)

hc("element-key", "A key step on a subscripted element of a repeated struct field compiles",
   "es[0].v reads the field v of the first element.",
   OK + ["req-hdl-expressions-5"], ["scalar-keys", "expressions"],
   """
   format t @namespace "{ns}"
   struct Root {
     es : E repeat 2
     d : derive es[0].v
   }
   struct E { v : u8 }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.es ex:Root.d ) .
   ex:Root.es a bddo:Field ; bddo:dataType ex:E ; bddo:repeatCount 2 .
   ex:Root.d a bddo:Field ; bddo:valueFromExpression "instance.es[0].v" .
   ex:E a bddo:Struct ; bddo:hasField ( ex:E.v ) .
   ex:E.v a bddo:Field ; bddo:dataType bddo:uint8 .
   """)

hc("parent-path-several-containers", "A parent. path from a struct with several containers is not checked for order",
   "Hdr is held by Root.a (before Root.n) and by Box.h (after Box.n): parent.n is forward in one container and not in the "
   "other, so the compiler makes no claim and the Processing Model decides at run time.",
   OK + ["req-hdl-conformance-section-5"], ["forward-references"],
   """
   format t @namespace "{ns}"
   struct Root {
     a : Hdr
     n : u8
     b : Box
   }
   struct Box {
     n : u8
     h : Hdr
   }
   struct Hdr {
     data : bytes[parent.n]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ex:Root.n ex:Root.b ) .
   ex:Root.a a bddo:Field ; bddo:dataType ex:Hdr .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Box .
   ex:Box a bddo:Struct ; bddo:hasField ( ex:Box.n ex:Box.h ) .
   ex:Box.n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Box.h a bddo:Field ; bddo:dataType ex:Hdr .
   ex:Hdr a bddo:Struct ; bddo:hasField ( ex:Hdr.data ) .
   ex:Hdr.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "parent.n" .
   """)

pair("string-non-bmp", "A string holds a character outside the Basic Multilingual Plane, written or escaped",
     "\U0001F600 written literally and the pair \\uD83D\\uDE00 denote the same one code point.",
     OK + ["req-hel-formal-grammar-1", "req-hdl-lexical-3"], ["lexical"],
     """
     format t @namespace "{ns}"
     struct Root {
       a : utf8[4] @fixed "\U0001F600"
       b : utf8[4] @fixed "\\uD83D\\uDE00"
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: a, type: utf8, size: 4, fixed: "\U0001F600" }
           - { name: b, type: utf8, size: 4, fixed: "\\U0001F600" }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ex:Root.b ) .
     ex:Root.a a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf8 ; bddo:size 4 ; bddo:hasFixedValue "\U0001F600" .
     ex:Root.b a bddo:Field ; bddo:dataType bddo:string ; bddo:encoding bddo:utf8 ; bddo:size 4 ; bddo:hasFixedValue "\U0001F600" .
     """)
