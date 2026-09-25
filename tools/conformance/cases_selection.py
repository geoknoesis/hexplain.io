"""Physical Parser cases: type selection (conditional data types and dispatch tables) and fixed values."""
from cases_physical import pp

CHUNKS = """
   ex:A a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:B a bddo:Struct ; bddo:hasField ( ex:b ) .
   ex:b a bddo:Field ; bddo:dataType bddo:uint16 .
   ex:C a bddo:Struct ; bddo:hasField ( ex:c ) .
   ex:c a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
"""

pp("cond-type-first-match", "The first DataTypeRule whose condition holds supplies the type",
   "Two rules hold; the earlier one in list order wins.",
   ["req-pm-parsefield-10"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:body ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ;
       bddo:hasConditionalDataType (
           [ a bddo:DataTypeRule ; bddo:condition "kind > 5" ; bddo:ruleDataType ex:B ]
           [ a bddo:DataTypeRule ; bddo:condition "kind == 7" ; bddo:ruleDataType ex:A ] ) .
   """ + CHUNKS,
   b"\x07\x01\x02", {"kind": 7, "body": {"b": 0x0102}})

pp("cond-type-default", "With no rule holding, bddo:dataType is the type",
   "Neither rule holds, so the field is read as its declared bytes.",
   ["req-pm-parsefield-10"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:body ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 2 ;
       bddo:hasConditionalDataType (
           [ a bddo:DataTypeRule ; bddo:condition "kind == 1" ; bddo:ruleDataType ex:A ] ) .
   """ + CHUNKS,
   b"\x09\x01\x02", {"kind": 9, "body": b"\x01\x02"})

pp("cond-type-no-match", "No rule and no default is a dispatch error",
   "A type-less field whose only rule does not hold.",
   ["req-pm-errors-7"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:body ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ;
       bddo:hasConditionalDataType (
           [ a bddo:DataTypeRule ; bddo:condition "kind == 1" ; bddo:ruleDataType ex:A ] ) .
   """ + CHUNKS,
   b"\x09\x01\x02", error="Dispatch")

pp("cond-type-parent-alias", "In a DataTypeRule condition, parent is a deprecated alias of instance",
   "parent.kind reads the containing struct's kind, as descriptions written against the earlier reading expect.",
   ["req-hel-name-binding-1", "req-pm-parsefield-10"], ["context", "hel/index.html#name-binding"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:body ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ;
       bddo:hasConditionalDataType (
           [ a bddo:DataTypeRule ; bddo:condition "parent.kind == 2" ; bddo:ruleDataType ex:B ] ) .
   """ + CHUNKS,
   b"\x02\x01\x02", {"kind": 2, "body": {"b": 0x0102}})

pp("dispatch-string-key", "A dispatch table selects the arm whose key equals the discriminator",
   "String keys compare by code points.",
   ["req-pm-parsefield-9", "req-pm-parsefield-1"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnField ex:tag .
   ex:armA a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey "aa" ; bddo:armDataType ex:A .
   ex:armB a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey "bb" ; bddo:armDataType ex:B .
   """ + CHUNKS,
   b"bb\x01\x02", {"tag": "bb", "body": {"b": 0x0102}})

pp("dispatch-integer-key", "Integer and string keys are distinct arms",
   "An integer discriminator 7 matches the integer key 7, not the string \"7\".",
   ["req-pm-parsefield-9", "req-pm-parsefield-1"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnField ex:tag .
   ex:armText a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey "7" ; bddo:armDataType ex:C .
   ex:armInt a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey 7 ; bddo:armDataType ex:A .
   """ + CHUNKS,
   b"\x07\x05", {"tag": 7, "body": {"a": 5}})

pp("dispatch-expression-and-default", "dispatchOnExpression computes the key; an unmatched key uses the default",
   "The key is tag + 1; the first field has no arm and takes bddo:dispatchDefault.",
   ["req-pm-parsefield-1"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ex:other ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table .
   ex:other a bddo:Field ; bddo:hasDispatchTable ex:Table2 .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnExpression "tag + 1" ; bddo:dispatchDefault ex:C .
   ex:arm2 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey 2 ; bddo:armDataType ex:A .
   ex:Table2 a bddo:DispatchTable ; bddo:dispatchOnExpression "tag + 2" ; bddo:dispatchDefault ex:C .
   ex:arm3 a bddo:DispatchArm ; bddo:armTable ex:Table2 ; bddo:armKey 2 ; bddo:armDataType ex:A .
   """ + CHUNKS,
   b"\x01\x05xy", {"tag": 1, "body": {"a": 5}, "other": {"c": "xy"}})

pp("dispatch-duplicate-key", "Two arms with one key are a description error",
   "Both arms of the table have the key \"aa\".",
   ["req-pm-parsefield-1", "req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnField ex:tag .
   ex:arm1 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey "aa" ; bddo:armDataType ex:A .
   ex:arm2 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey "aa" ; bddo:armDataType ex:B .
   """ + CHUNKS,
   b"aa\x01\x02", error="Description")

pp("dispatch-and-conditional-type", "Both type-selection mechanisms on one field is a description error",
   "A field declaring a dispatch table and conditional data types.",
   ["req-pm-parsefield-23", "req-pm-parsefield-20", "req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table ;
       bddo:hasConditionalDataType ( [ a bddo:DataTypeRule ; bddo:condition "tag == 1" ; bddo:ruleDataType ex:B ] ) .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnField ex:tag .
   ex:arm1 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey 1 ; bddo:armDataType ex:A .
   """ + CHUNKS,
   b"\x01\x05\x06", error="Description")

pp("dispatch-no-arm-no-default", "No arm, no default and no data type is a dispatch error",
   "The key 3 has no arm.",
   ["req-pm-parsefield-10", "req-pm-errors-7"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ex:body ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:body a bddo:Field ; bddo:hasDispatchTable ex:Table .
   ex:Table a bddo:DispatchTable ; bddo:dispatchOnField ex:tag .
   ex:arm1 a bddo:DispatchArm ; bddo:armTable ex:Table ; bddo:armKey 1 ; bddo:armDataType ex:A .
   """ + CHUNKS,
   b"\x03\x05", error="Dispatch")

# ----------------------------------------------------------------- fixed values

pp("fixed-numeric-by-value", "A numeric fixed value is compared by value",
   "\"9994\"^^xsd:int on an int32 matches 9994, and 0 as xsd:integer matches a uint8 zero.",
   ["req-pm-parsefield-2"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:code ex:zero ) .
   ex:code a bddo:Field ; bddo:dataType bddo:int32 ; bddo:hasFixedValue "9994"^^xsd:int .
   ex:zero a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:hasFixedValue 0 .
   """,
   b"\x00\x00\x27\x0a\x00", {"code": 9994, "zero": 0})

pp("fixed-numeric-mismatch", "A fixed value mismatch is a validation error",
   "9995 is read where 9994 is fixed.",
   ["req-pm-parsefield-13", "req-pm-errors-4"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:code ) .
   ex:code a bddo:Field ; bddo:dataType bddo:int32 ; bddo:hasFixedValue "9994"^^xsd:int .
   """,
   b"\x00\x00\x27\x0b", error="Validation")

pp("fixed-hexbinary-in-byte-order", "A hexBinary fixed value is the field's encoding in its byte order",
   "\"0100\"^^xsd:hexBinary on a little-endian uint16 is the value 1.",
   ["req-pm-parsefield-2"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16le ; bddo:hasFixedValue "0100"^^xsd:hexBinary .
   """,
   b"\x01\x00", {"a": 1})

pp("fixed-hexbinary-wrong-width", "A hexBinary fixed value of another width is a description error",
   "Three bytes fixed on a two-byte field.",
   ["req-pm-parsefield-2", "req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint16 ; bddo:hasFixedValue "000001"^^xsd:hexBinary .
   """,
   b"\x00\x01", error="Description")

pp("fixed-fraction-on-integer", "A fraction fixed on an integer field is a description error",
   "\"1.5\"^^xsd:decimal can never equal an integer.",
   ["req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:hasFixedValue 1.5 .
   """,
   b"\x01", error="Description")

pp("fixed-out-of-range", "A fixed value outside the field's range is a description error",
   "300 cannot be a uint8.",
   ["req-pm-errors-8"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:hasFixedValue 300 .
   """,
   b"\x01", error="Description")

pp("fixed-string-and-bytes", "String and bytes fixed values compare by code points and byte for byte",
   "A PNG-style signature and a two-character tag.",
   ["req-pm-parsefield-2", "req-pm-parsefield-12"], ["algorithm"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:sig ex:tag ) .
   ex:sig a bddo:Field ; bddo:dataType bddo:bytes ; bddo:size 4 ; bddo:hasFixedValue "89504E47"^^xsd:hexBinary .
   ex:tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii ; bddo:hasFixedValue "PK" .
   """,
   b"\x89PNGPK", {"sig": b"\x89PNG", "tag": "PK"})

pp("fixed-string-mismatch", "A string fixed value mismatch is a validation error",
   "\"PK\" is fixed and \"PX\" is read.",
   ["req-pm-parsefield-12", "req-pm-errors-4"], ["algorithm", "errors"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:tag ) .
   ex:tag a bddo:Field ; bddo:dataType bddo:string ; bddo:size 2 ; bddo:encoding bddo:ascii ; bddo:hasFixedValue "PK" .
   """,
   b"PX", error="Validation")
