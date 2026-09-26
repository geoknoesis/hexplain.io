"""HDL Compiler cases for the language features of the Unreleased section: 24-bit and half-float
types, named and custom CRCs, parameterised structs and local bindings.

The expected Turtle is the mapping the HDL page states (Types, Checksums, Parameters and local
bindings); literals are compared by value, so the integers below may be written in any form.
"""
from cases_hdl import OK, err, hc, pair

HDL_PARAMS = ["req-hdl-parameters-1"]

# ----------------------------------------------------------------- types

pair("types-24-bit-and-half", "u24, i24 and f16 name the 24-bit and half-float BDDO types",
     "Each HDL type name, suffixed or not, is the BDDO data type of the same width, signedness and byte order.",
     OK + ["req-hdl-grammar-1"], ["types", "grammar-fields"],
     """
     format t @namespace "{ns}"
     struct Root {
       a : u24
       b : u24le
       c : u24be
       d : i24
       e : i24le
       f : i24be
       g : f16
       h : f16le
       i : f16be
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: a, type: u24 }
           - { name: b, type: u24le }
           - { name: c, type: u24be }
           - { name: d, type: i24 }
           - { name: e, type: i24le }
           - { name: f, type: i24be }
           - { name: g, type: f16 }
           - { name: h, type: f16le }
           - { name: i, type: f16be }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.a ex:Root.b ex:Root.c ex:Root.d ex:Root.e ex:Root.f ex:Root.g ex:Root.h ex:Root.i ) .
     ex:Root.a a bddo:Field ; bddo:dataType bddo:uint24 .
     ex:Root.b a bddo:Field ; bddo:dataType bddo:uint24le .
     ex:Root.c a bddo:Field ; bddo:dataType bddo:uint24be .
     ex:Root.d a bddo:Field ; bddo:dataType bddo:int24 .
     ex:Root.e a bddo:Field ; bddo:dataType bddo:int24le .
     ex:Root.f a bddo:Field ; bddo:dataType bddo:int24be .
     ex:Root.g a bddo:Field ; bddo:dataType bddo:float16 .
     ex:Root.h a bddo:Field ; bddo:dataType bddo:float16le .
     ex:Root.i a bddo:Field ; bddo:dataType bddo:float16be .
     """)

hc("fixed-24-bit-and-half", "@fixed on 24-bit and half-float fields",
   "A hex @fixed on a u24 is three bytes of xsd:hexBinary; an integer @fixed takes the field's XSD type, xsd:int on an i24 "
   "and xsd:float on an f16.",
   OK + ["req-hdl-clauses-1"], ["clauses", "literal-values"],
   """
   format t @namespace "{ns}"
   struct Root {
     magic : u24 @fixed 0x010203
     code : i24 @fixed -2
     one : f16 @fixed 1
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.magic ex:Root.code ex:Root.one ) .
   ex:Root.magic a bddo:Field ; bddo:dataType bddo:uint24 ; bddo:hasFixedValue "010203"^^xsd:hexBinary .
   ex:Root.code a bddo:Field ; bddo:dataType bddo:int24 ; bddo:hasFixedValue "-2"^^xsd:int .
   ex:Root.one a bddo:Field ; bddo:dataType bddo:float16 ; bddo:hasFixedValue "1"^^xsd:float .
   """)

err("bracket-size-after-u24", "A bracket size after u24 is an ERROR",
    "u24 is a fixed-width numeric type, so u24[4] could only mislead.",
    ["req-hdl-types-1"], ["types"],
    """
    format t @namespace "{ns}"
    struct Root {
      a : u24[4]
    }
    """, line=3)

# ----------------------------------------------------------------- checksums

NAMED = [("c8", "u8", "crc8", "crc8Smbus"), ("c16a", "u16", "crc16arc", "crc16Arc"),
         ("c16x", "u16", "crc16xmodem", "crc16Xmodem"), ("c16m", "u16", "crc16modbus", "crc16Modbus"),
         ("c16s", "u16", "crc16x25", "crc16X25"), ("c32c", "u32", "crc32c", "crc32c"),
         ("c32b", "u32", "crc32bzip2", "crc32Bzip2"), ("c32m", "u32", "crc32mpeg2", "crc32Mpeg2"),
         ("c64e", "u64", "crc64ecma", "crc64Ecma182"), ("c64x", "u64", "crc64xz", "crc64Xz")]
BDDO_TYPE = {"u8": "uint8", "u16": "uint16", "u32": "uint32", "u64": "uint64"}
hc("checksum-named-crcs", "Every named CRC compiles to its BDDO individual",
   "crc8, crc16arc, crc16xmodem, crc16modbus, crc16x25, crc32c, crc32bzip2, crc32mpeg2, crc64ecma and crc64xz, each over the "
   "same range and stored in a field of its own width.",
   OK + ["req-hdl-grammar-1", "req-bddo-checksum-algorithms-1"], ["checksums", "grammar-fields"],
   'format t @namespace "{ns}"\nstruct Root {\n  text : ascii[9]\n'
   + "".join(f"  {f} : {t} @checksum {h}(text .. text)\n" for f, t, h, _ in NAMED) + "}\n",
   "ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.text " + " ".join(f"ex:Root.{f}" for f, *_ in NAMED) + " ) .\n"
   "ex:Root.text a bddo:Field ; bddo:dataType bddo:string ; bddo:size 9 ; bddo:encoding bddo:ascii .\n"
   + "".join(f"ex:Root.{f} a bddo:Field ; bddo:dataType bddo:{BDDO_TYPE[t]} ; bddo:checksum [ a bddo:Checksum ; "
             f"bddo:checksumAlgorithm bddo:{b} ; bddo:coversFromField ex:Root.text ; bddo:coversToField ex:Root.text ] .\n"
             for f, t, _h, b in NAMED))

CUSTOM_TTL = """
   ex:Frame a bddo:Struct ; bddo:hasField ( ex:Frame.header ex:Frame.payload ex:Frame.crc ) .
   ex:Frame.header a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .
   ex:Frame.payload a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 8 .
   ex:Frame.crc a bddo:Field ; bddo:dataType bddo:uint16le ;
       bddo:checksum [ a bddo:Checksum ; bddo:coversFromField ex:Frame.header ; bddo:coversToField ex:Frame.payload ;
           bddo:checksumAlgorithm [ a bddo:CustomCrc ; bddo:crcWidth 16 ; bddo:crcPolynomial 32773 ; bddo:crcInit 0 ;
               bddo:crcReflectIn true ; bddo:crcReflectOut true ; bddo:crcXorOut 0 ] ] .
"""
pair("checksum-custom-crc", "crc(...) compiles to an inline bddo:CustomCrc",
     "The six parameters in any order, a key joined to its colon (width:) or apart (refin :); a HEX value is the integer "
     "its digits spell (0x8005 is 32773).",
     OK + ["req-hdl-checksums-1"], ["checksums", "grammar-fields"],
     """
     format t @namespace "{ns}"
     struct Frame {
       header : bytes[4]
       payload : bytes[8]
       crc : u16le @checksum crc(poly: 0x8005, width: 16, init: 0x0000, refin : true, refout: true, xorout: 0)(header .. payload)
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Frame:
         fields:
           - { name: header, type: bytes, size: 4 }
           - { name: payload, type: bytes, size: 8 }
           - name: crc
             type: u16le
             checksum: { crc: { width: 16, poly: 0x8005, init: 0, refin: true, refout: true, xorout: 0 }, from: header, to: payload }
     """,
     CUSTOM_TTL)

hc("checksum-custom-crc-64-bit", "A 64-bit custom CRC takes register values up to 2^64 - 1",
   "0xFFFFFFFFFFFFFFFF is below 2^64, so it is a valid init and final XOR for width 64, emitted as an xsd:integer.",
   OK + ["req-hdl-checksums-1"], ["checksums"],
   """
   format t @namespace "{ns}"
   struct Root {
     data : bytes[4]
     sum : u64 @checksum crc(width: 64, poly: 0x42F0E1EBA9EA3693, init: 0xFFFFFFFFFFFFFFFF, refin: true, refout: true, xorout: 0xFFFFFFFFFFFFFFFF)(data .. data)
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.data ex:Root.sum ) .
   ex:Root.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 .
   ex:Root.sum a bddo:Field ; bddo:dataType bddo:uint64 ;
       bddo:checksum [ a bddo:Checksum ; bddo:coversFromField ex:Root.data ; bddo:coversToField ex:Root.data ;
           bddo:checksumAlgorithm [ a bddo:CustomCrc ; bddo:crcWidth 64 ; bddo:crcPolynomial 4823603603198064275 ;
               bddo:crcInit 18446744073709551615 ; bddo:crcReflectIn true ; bddo:crcReflectOut true ;
               bddo:crcXorOut 18446744073709551615 ] ] .
   """)

CRC_ERRS = ["req-hdl-checksums-1"]
err("checksum-custom-crc-missing-parameter", "A custom CRC without one of its six parameters is an ERROR",
    "xorout is missing.", CRC_ERRS, ["checksums"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[4]
      sum : u16 @checksum crc(width: 16, poly: 0x8005, init: 0, refin: true, refout: true)(data .. data)
    }
    """, line=4)

err("checksum-custom-crc-repeated-parameter", "A custom CRC parameter stated twice is an ERROR",
    "init appears twice.", CRC_ERRS, ["checksums"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[4]
      sum : u16 @checksum crc(width: 16, poly: 0x8005, init: 0, init: 1, refin: true, refout: true, xorout: 0)(data .. data)
    }
    """, line=4)

err("checksum-custom-crc-value-too-wide", "A custom CRC register value that does not fit the width is an ERROR",
    "0x18005 is CRC-16/ARC's polynomial with its top term, which a 16-bit register cannot hold.", CRC_ERRS, ["checksums"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[4]
      sum : u16 @checksum crc(width: 16, poly: 0x18005, init: 0, refin: true, refout: true, xorout: 0)(data .. data)
    }
    """, line=4)

err("checksum-custom-crc-width-out-of-range", "A custom CRC width outside 8..64 is an ERROR",
    "width 65.", CRC_ERRS, ["checksums"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[4]
      sum : u64 @checksum crc(width: 65, poly: 3, init: 0, refin: false, refout: false, xorout: 0)(data .. data)
    }
    """, line=4)

err("checksum-crc-field-width", "A CRC whose width differs from its field's is an ERROR",
    "crc32c is 32 bits wide and the field is a u16.", ["req-hdl-checksums-2"], ["checksums"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[4]
      sum : u16 @checksum crc32c(data .. data)
    }
    """, line=4)

# ----------------------------------------------------------------- parameterised structs

PARAM_TTL = """
   ex:Table a bddo:Struct ; bddo:hasField ( ex:Table.count ex:Table.width ex:Table.rows ) .
   ex:Table.count a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Table.width a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Table.rows a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.count" "instance.width" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ex:Row.w ) ; bddo:hasField ( ex:Row.cells ) .
   ex:Row.n a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Row.w a bddo:Parameter .
   ex:Row.cells a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.w" ;
       bddo:repeatCountFromExpression "param.n" .
"""
pair("param-struct", "A parameterised struct and the arguments that instantiate it",
     "struct Row(n: int, w) mints two bddo:Parameters; Row(count, width) passes the caller's fields as HEL strings; inside "
     "Row, the bare names n and w compile to param.n and param.w and take the expression form.",
     OK + HDL_PARAMS + ["req-hdl-grammar-1", "req-hdl-form-rule-1"], ["parameters", "grammar-structs", "form-rule"],
     """
     format t @namespace "{ns}"
     struct Table {
       count : u8
       width : u8
       rows : Row(count, width)
     }
     struct Row(n: int, w) {
       cells : bytes[w] repeat n
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Table:
         fields:
           - { name: count, type: u8 }
           - { name: width, type: u8 }
           - { name: rows, type: { struct: Row, args: [count, width] } }
       Row:
         params: [ { n: int }, w ]
         fields:
           - { name: cells, type: bytes, size: w, repeat: { count: n } }
     """,
     PARAM_TTL)

hc("param-nested-arguments", "Arguments are resolved in the caller's struct and pass parameters on",
   "Row passes param.w + 1 to Cell; the literal argument 4 is the HEL string \"4\"; hdr.count reaches into a sibling struct.",
   OK + HDL_PARAMS, ["parameters", "expressions"],
   """
   format t @namespace "{ns}"
   struct Root {
     hdr : Header
     a : Row(hdr.count)
     b : Row(4)
   }
   struct Header { count : u8 }
   struct Row(w) {
     cell : Cell(w + 1)
   }
   struct Cell(size: int) {
     data : bytes[size]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.hdr ex:Root.a ex:Root.b ) .
   ex:Root.hdr a bddo:Field ; bddo:dataType ex:Header .
   ex:Root.a a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "instance.hdr.count" ) .
   ex:Root.b a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "4" ) .
   ex:Header a bddo:Struct ; bddo:hasField ( ex:Header.count ) .
   ex:Header.count a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.w ) ; bddo:hasField ( ex:Row.cell ) .
   ex:Row.w a bddo:Parameter .
   ex:Row.cell a bddo:Field ; bddo:dataType ex:Cell ; bddo:hasArgument ( "param.w + 1" ) .
   ex:Cell a bddo:Struct ; bddo:hasParameter ( ex:Cell.size ) ; bddo:hasField ( ex:Cell.data ) .
   ex:Cell.size a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Cell.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.size" .
   """)

pair("param-switch-arms", "switch arms name parameterised structs with arguments of their own",
     "Each arm's DataTypeRule carries its own bddo:hasArgument.",
     OK + HDL_PARAMS + ["req-hdl-conformance-section-5"], ["parameters", "clauses"],
     """
     format t @namespace "{ns}"
     struct Root {
       kind : u8
       body : switch kind {
         1 => Blob(2)
         2 => Blob(4)
       }
     }
     struct Blob(size: int) {
       data : bytes[size]
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Root:
         fields:
           - { name: kind, type: u8 }
           - name: body
             type: switch
             switch: { on: kind, cases: { 1: { struct: Blob, args: [2] }, 2: { struct: Blob, args: [4] } } }
       Blob:
         params: [ { size: int } ]
         fields:
           - { name: data, type: bytes, size: size }
     """,
     """
     ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.kind ex:Root.body ) .
     ex:Root.kind a bddo:Field ; bddo:dataType bddo:uint8 .
     ex:Root.body a bddo:Field ; bddo:hasConditionalDataType (
         [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 1" ; bddo:ruleDataType ex:Blob ; bddo:hasArgument ( "2" ) ]
         [ a bddo:DataTypeRule ; bddo:condition "instance.kind == 2" ; bddo:ruleDataType ex:Blob ; bddo:hasArgument ( "4" ) ] ) .
     ex:Blob a bddo:Struct ; bddo:hasParameter ( ex:Blob.size ) ; bddo:hasField ( ex:Blob.data ) .
     ex:Blob.size a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
     ex:Blob.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "param.size" .
     """)

hc("param-recursion", "A struct may pass arguments to itself",
   "Node(depth - 1) inside Node; the presence guard reads the parameter too.",
   OK + HDL_PARAMS, ["parameters"],
   """
   format t @namespace "{ns}"
   struct Root {
     levels : u8
     tree : Node(levels)
   }
   struct Node(depth: int) {
     v : u8
     child : Node(depth - 1) if depth > 1
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.levels ex:Root.tree ) .
   ex:Root.levels a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Root.tree a bddo:Field ; bddo:dataType ex:Node ; bddo:hasArgument ( "instance.levels" ) .
   ex:Node a bddo:Struct ; bddo:hasParameter ( ex:Node.depth ) ; bddo:hasField ( ex:Node.v ex:Node.child ) .
   ex:Node.depth a bddo:Parameter ; bddo:parameterType bddo:IntegerParameter .
   ex:Node.v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Node.child a bddo:Field ; bddo:dataType ex:Node ; bddo:hasArgument ( "param.depth - 1" ) ;
       bddo:isPresentIf "param.depth > 1" .
   """)

err("param-arity-mismatch", "Too few arguments for a parameterised struct is an ERROR",
    "Row declares two parameters and the field passes one.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row(1)
    }
    struct Row(n, w) { cells : bytes[w] repeat n }
    """, line=3)

err("param-missing-arguments", "A parameterised struct named without arguments is an ERROR",
    "Row declares two parameters and the field names it bare.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row
    }
    struct Row(n, w) { cells : bytes[w] repeat n }
    """, line=3)

err("param-arguments-for-plain-struct", "Arguments for a struct without parameters are an ERROR",
    "Plain declares no parameter.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      p : Plain(1)
    }
    struct Plain { v : u8 }
    """, line=3)

err("param-field-clash", "A parameter and a field of one struct sharing a name is an ERROR",
    "Row's parameter n and its field n.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row(1)
    }
    struct Row(n) {
      n : u8
    }
    """)

err("param-reserved-name", "A field named param is an ERROR",
    "param is a reserved HEL root.", ["req-hdl-lexical-1", "req-hdl-grammar-keywords-1"], ["lexical", "grammar-keywords"],
    """
    format t @namespace "{ns}"
    struct Root {
      param : u8
    }
    """, line=3)

err("param-root-struct", "A root struct with parameters is an ERROR",
    "The first struct is the root, and nothing can pass it an argument.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root(n) {
      v : u8
    }
    """, line=2)

err("param-dispatch-default", "A parameterised struct as a dispatch default is an ERROR",
    "A dispatch default cannot state arguments.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      kind : u8
      body : bytes[..] dispatch Bodies on kind default Blob { 1 => Plain }
    }
    struct Blob(size) { data : bytes[size] }
    struct Plain { v : u8 }
    """, line=4)

err("param-unknown-type", "A parameter type other than int, float, string, bytes or bool is an ERROR",
    "integer is not one of the five words.", HDL_PARAMS, ["parameters", "grammar-structs"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row(1)
    }
    struct Row(n: integer) { cells : bytes[n] }
    """, line=5)

err("param-literal-type-mismatch", "A literal argument of the wrong kind for a typed parameter is an ERROR",
    "Row's n is an int and the argument is a string.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row("a")
    }
    struct Row(n: int) { cells : bytes[n] }
    """, line=3)

err("param-argument-forward-reference", "An argument naming a later field is a forward reference and an ERROR",
    "n is declared after the field that passes it.", HDL_PARAMS + ["req-hdl-expressions-1"], ["parameters", "forward-references"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row(n)
      n : u8
    }
    struct Row(w) { cells : bytes[w] }
    """, line=3)

err("param-undeclared", "param.x in a struct with no parameter x is an ERROR",
    "Row declares w, not x.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : Row(1)
    }
    struct Row(w) { cells : bytes[`param.x`] }
    """, line=5)

HDL_ELEMENT = ["req-hdl-parameters-2"]
hc("param-element-scope", "Over struct elements, bare names and param are the element's",
   "In a repeat until and a quantifier predicate over E elements, stop and small are E's parameter and binding: "
   "param.stop and instance.small. The argument lim is resolved in R, the caller.",
   OK + HDL_ELEMENT + HDL_PARAMS, ["parameters"],
   """
   format t @namespace "{ns}"
   struct Root {
     r : R(3)
   }
   struct R(lim) {
     es : E(lim) repeat until v == stop
     ok : derive all(es, small)
   }
   struct E(stop) {
     v : u8
     let small = v < stop
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.r ) .
   ex:Root.r a bddo:Field ; bddo:dataType ex:R ; bddo:hasArgument ( "3" ) .
   ex:R a bddo:Struct ; bddo:hasParameter ( ex:R.lim ) ; bddo:hasField ( ex:R.es ex:R.ok ) .
   ex:R.lim a bddo:Parameter .
   ex:R.es a bddo:Field ; bddo:dataType ex:E ; bddo:hasArgument ( "param.lim" ) ;
       bddo:repeatUntil "instance.v == param.stop" .
   ex:R.ok a bddo:Field ; bddo:valueFromExpression "all(instance.es, instance.small)" .
   ex:E a bddo:Struct ; bddo:hasParameter ( ex:E.stop ) ; bddo:hasField ( ex:E.v ex:E.small ) .
   ex:E.stop a bddo:Parameter .
   ex:E.v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:E.small a bddo:LocalBinding ; bddo:localExpression "instance.v < param.stop" .
   """)

err("param-holding-struct-in-element-scope", "A parameter of the holding struct, read where an element is instance, is an ERROR",
    "Inside the predicate over E elements, param is E's, and E declares no lim.", HDL_ELEMENT, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Root {
      r : R(3)
    }
    struct R(lim) {
      es : E repeat 2
      ok : derive all(es, v < lim)
    }
    struct E { v : u8 }
    """, line=7)

err("param-on-header", "Parameters on a header are an ERROR",
    "A header locates its members by key, so it has no scope to bind arguments in.", HDL_PARAMS + ["req-hdl-conformance-section-2"],
    ["parameters", "yaml"],
    """
    format: t
    namespace: "{ns}"
    structs:
      Root:
        fields:
          - { name: h, type: { struct: Hdr, args: [ "1" ] }, size: 8 }
      Hdr:
        kind: header
        separator: "="
        params: [ n ]
        fields:
          - { name: samples, type: anum }
    """, yaml=True)

# ----------------------------------------------------------------- local bindings

LET_TTL = """
   ex:Image a bddo:Struct ; bddo:hasField ( ex:Image.width ex:Image.height ex:Image.area ex:Image.pixels ) .
   ex:Image.width a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:Image.height a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:Image.area a bddo:LocalBinding ; bddo:localExpression "instance.width * instance.height" .
   ex:Image.pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.area" .
"""
pair("let-binding", "let compiles to a bddo:LocalBinding in the member list",
     "The binding stands between the fields in bddo:hasField; a reference to it takes the expression form, never "
     "sizeFromField, because a binding is not a field.",
     OK + HDL_PARAMS + ["req-hdl-form-rule-1", "req-hdl-grammar-1"], ["parameters", "form-rule", "grammar-structs"],
     """
     format t @namespace "{ns}"
     struct Image {
       width : u16
       height : u16
       let area = width * height
       pixels : bytes[area]
     }
     """,
     """
     format: t
     namespace: "{ns}"
     structs:
       Image:
         fields:
           - { name: width, type: u16 }
           - { name: height, type: u16 }
           - { let: area, value: "width * height" }
           - { name: pixels, type: bytes, size: area }
     """,
     LET_TTL)

hc("let-reads-parameter", "A let binding may read a parameter, and let ends an unbracketed expression",
   "total = n * 2 reads the parameter n as param.n; the next let starts a new member.",
   OK + HDL_PARAMS, ["parameters", "grammar-keywords"],
   """
   format t @namespace "{ns}"
   struct Root {
     r : Row(3)
   }
   struct Row(n) {
     let total = n * 2
     let half = total / 2
     data : bytes[total]
     tail : bytes[half]
   }
   """,
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:Root.r ) .
   ex:Root.r a bddo:Field ; bddo:dataType ex:Row ; bddo:hasArgument ( "3" ) .
   ex:Row a bddo:Struct ; bddo:hasParameter ( ex:Row.n ) ; bddo:hasField ( ex:Row.total ex:Row.half ex:Row.data ex:Row.tail ) .
   ex:Row.n a bddo:Parameter .
   ex:Row.total a bddo:LocalBinding ; bddo:localExpression "param.n * 2" .
   ex:Row.half a bddo:LocalBinding ; bddo:localExpression "instance.total / 2" .
   ex:Row.data a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.total" .
   ex:Row.tail a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeFromExpression "instance.half" .
   """)

err("let-forward-reference", "Reading a let binding before its position is an ERROR",
    "pixels reads area, which is bound after it.", HDL_PARAMS + ["req-hdl-expressions-1"], ["parameters", "forward-references"],
    """
    format t @namespace "{ns}"
    struct Image {
      width : u16
      pixels : bytes[area]
      let area = width * 2
    }
    """, line=4)

err("let-name-clash", "A let binding sharing a field's name is an ERROR",
    "width is both a field and a binding.", HDL_PARAMS, ["parameters"],
    """
    format t @namespace "{ns}"
    struct Image {
      width : u16
      let width = 2
    }
    """, line=4)

err("let-in-header", "A let binding in a header is an ERROR",
    "A key/value header has no member order to evaluate a binding at.", HDL_PARAMS, ["parameters", "delimited"],
    """
    format t @namespace "{ns}"
    header Hdr @record-separator 0x0A @separator 0x3D {
      samples : anum
      let twice = samples * 2
    }
    """, line=4)

err("let-where-field-required", "A let binding named where a field is required is an ERROR",
    "A checksum range names fields, and a binding has no bytes.", HDL_PARAMS, ["parameters", "checksums"],
    """
    format t @namespace "{ns}"
    struct Root {
      data : bytes[4]
      let start = 0
      sum : u32 @checksum crc32(start .. data)
    }
    """, line=5)
