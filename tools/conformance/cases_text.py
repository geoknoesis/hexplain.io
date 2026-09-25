"""Physical Parser cases: numbers written as text, separated tokens, varints, delimited records,
key/value headers, tables, tree documents and data layouts."""
from cases_physical import pp

TREES = {"features": {"requires": ["tree-documents"]}}
GROUPED = {"features": {"requires": ["grouped-headers"]}}

# ----------------------------------------------------------------- numbers written as text

pp("textnum-integers", "Text integers ignore surrounding whitespace, NUL bytes and a leading plus",
   "\" 42\\0\" reads 42, \"+7 \" reads 7 and a radix of 16 or 8 applies.",
   ["req-pm-text-numbers-3"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 4 .
   ex:b a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 3 .
   ex:c a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 2 ; bddo:numericBase 16 .
   ex:d a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 3 ; bddo:numericBase 8 .
   """,
   b" 42\x00" + b"+7 " + b"ff" + b"017", {"a": 42, "b": 7, "c": 255, "d": 15})

pp("textnum-decimals", "Text decimals accept exponents introduced by E, e, D or d, and nan",
   "\"1.5D2\" is 150.0, \"-2e1\" is -20.0 and \"NaN\" is NaN.",
   ["req-pm-text-numbers-3"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 5 .
   ex:b a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 4 .
   ex:c a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 3 .
   """,
   b"1.5D2" + b"-2e1" + b"NaN", {"a": 150.0, "b": -20.0, "c": float("nan")})

pp("textnum-invalid", "A text number that does not parse is a validation error",
   "\"4x2\" is not an integer; it is never kept as a string.",
   ["req-pm-text-numbers-3", "req-pm-errors-4"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:size 3 .
   """,
   b"4x2", error="Validation")

pp("textnum-infinite", "An infinite text decimal is a validation error",
   "\"inf\" is not a finite number and is not the spelling nan.",
   ["req-pm-text-numbers-3", "req-pm-errors-4"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:size 3 .
   """,
   b"inf", error="Validation")

pp("separated-tokens", "Separated tokens: each element consumes the separator runs around it",
   "Three whitespace-separated integers with mixed separators.",
   ["req-pm-size-resolution-6", "req-pm-text-numbers-2"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:vals ) .
   ex:vals a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" ; bddo:repeatCount 3 .
   """,
   b"  1\t22\r\n333 ", {"vals": [1, 22, 333]})

pp("separated-empty-token", "A separated token in a region of only separators is a bounds error",
   "Nothing but spaces remains.",
   ["req-pm-errors-3"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" .
   """,
   b"   ", error="Bounds")

pp("separated-multibyte-encoding", "Separated tokens in a multi-byte encoding are a validation error",
   "The scan is byte-wise, so UTF-16 is refused.",
   ["req-pm-text-numbers-1"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:separatedBy "whitespace" ; bddo:encoding bddo:utf16le .
   """,
   "1 2".encode("utf-16-le"), error="Validation")

pp("varints", "LEB128, zigzag and SQLite varints",
   "E5 8E 26 is 624485; zigzag 03 is -2 and 04 is 2; SQLite 81 00 is 128.",
   ["req-pm-text-numbers-4", "req-pm-size-resolution-8"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ex:b ex:c ex:d ) .
   ex:a a bddo:Field ; bddo:dataType bddo:varuint .
   ex:b a bddo:Field ; bddo:dataType bddo:varint .
   ex:c a bddo:Field ; bddo:dataType bddo:varint .
   ex:d a bddo:Field ; bddo:dataType bddo:sqliteVarint .
   """,
   b"\xe5\x8e\x26" + b"\x03" + b"\x04" + b"\x81\x00", {"a": 624485, "b": -2, "c": 2, "d": 128})

pp("varint-overflow", "A varint beyond the 64-bit range is a bounds error",
   "Eleven continuation bytes cannot fit in 64 bits.",
   ["req-pm-errors-3"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:varuint .
   """,
   b"\xff" * 10 + b"\x01", error="Bounds")

pp("varint-past-bound", "A varint that runs past its bound is a bounds error",
   "The last byte still has its continuation bit set.",
   ["req-pm-errors-3"], ["text-numbers"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:a ) .
   ex:a a bddo:Field ; bddo:dataType bddo:varuint .
   """,
   b"\x80\x80", error="Bounds")

# ----------------------------------------------------------------- key/value headers

pp("kv-header", "A key/value header binds fields by key; the last record wins",
   "Keys are matched ignoring ASCII case, values are trimmed, CRLF reads as LF, records without the separator are ignored and a missing key leaves its field null.",
   ["req-pm-delimited-records-7", "req-pm-parsestruct-7", "req-pm-key-value-1"], ["key-value", "delimited-records", "typed-cells"],
   """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ;
       bddo:trimWhitespace true ; bddo:keyIsCaseInsensitive true ;
       bddo:hasField ( ex:Root.samples ex:Root.lines ex:Root.bands ex:Root.name ) .
   ex:Root.samples a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "samples" .
   ex:Root.lines a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "lines" .
   ex:Root.bands a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "bands" .
   ex:Root.name a bddo:Field ; bddo:dataType bddo:string ; bddo:key "name" .
   """,
   b"ENVI\r\nsamples = 10\r\nLINES=20\r\nsamples=11\r\nname =  a b \r\n",
   {"samples": 11, "lines": 20, "bands": None, "name": "a b"})

pp("kv-in-bounded-field", "A text container consumes only the region of the field it is parsed through",
   "An 8-byte header field is followed by a binary byte.",
   ["req-pm-key-value-1", "req-pm-size-resolution-9"], ["text-containers", "key-value"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:hdr ex:tail ) .
   ex:hdr a bddo:Field ; bddo:dataType ex:Hdr ; bddo:size 8 .
   ex:Hdr a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:hasField ( ex:Hdr.a ex:Hdr.b ) .
   ex:Hdr.a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "a" .
   ex:Hdr.b a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "b" .
   ex:tail a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   b"a=1\nb=22" + b"\x09", {"hdr": {"a": 1, "b": 22}, "tail": 9})

pp("kv-empty-numeric-value", "An empty value of a numeric field is a validation error",
   "The key is present but its value is empty.",
   ["req-pm-typed-cells-1", "req-pm-errors-4"], ["typed-cells"],
   """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "a" .
   """,
   b"a=\n", error="Validation")

pp("kv-non-number", "A value that does not parse as the declared number is a validation error",
   "It must not be kept as a string.",
   ["req-pm-typed-cells-1", "req-pm-errors-4"], ["typed-cells"],
   """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:key "a" .
   """,
   b"a=twelve\n", error="Validation")

pp("kv-grouped-keyed", "Keyed groups nest records; a field is located by key path",
   "OBJECT = IMAGE ... END_OBJECT = IMAGE; IMAGE/LINES reads inside the group and RECORD_BYTES outside every group.",
   ["req-pm-conformance-classes-6"], ["key-value"],
   """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:trimWhitespace true ;
       bddo:hasGrouping [ a bddo:RecordGrouping ; bddo:groupingStyle bddo:keyedGroup ;
                          bddo:groupOpenToken "OBJECT" ; bddo:groupCloseToken "END_OBJECT" ] ;
       bddo:hasField ( ex:Root.lines ex:Root.recordBytes ex:Root.outerLines ) .
   ex:Root.lines a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:keyPath "IMAGE/LINES" .
   ex:Root.recordBytes a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:keyPath "RECORD_BYTES" .
   ex:Root.outerLines a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:keyPath "LINES" .
   """,
   b"RECORD_BYTES = 512\nOBJECT = IMAGE\n  LINES = 5\nEND_OBJECT = IMAGE\n",
   {"lines": 5, "recordBytes": 512, "outerLines": None}, manifest=GROUPED)

pp("kv-grouped-unclosed", "A keyed group still open at the end is a validation error",
   "OBJECT = IMAGE is never closed.",
   ["req-pm-key-value-1", "req-pm-errors-4"], ["key-value"],
   """
   ex:Root a bddo:KeyValueHeader ; bddo:keyValueSeparator "3D"^^xsd:hexBinary ; bddo:trimWhitespace true ;
       bddo:hasGrouping [ a bddo:RecordGrouping ; bddo:groupingStyle bddo:keyedGroup ;
                          bddo:groupOpenToken "OBJECT" ; bddo:groupCloseToken "END_OBJECT" ] ;
       bddo:hasField ( ex:Root.lines ) .
   ex:Root.lines a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:keyPath "IMAGE/LINES" .
   """,
   b"OBJECT = IMAGE\n  LINES = 5\n", error="Validation", manifest=GROUPED)

# ----------------------------------------------------------------- tables and records

pp("table-csv", "A delimited table yields one row per record, matched to fields by position",
   "A header row is skipped; quoted values may contain the delimiter, and a doubled quote is one quote.",
   ["req-pm-parsestruct-7", "req-pm-delimited-records-1", "req-pm-delimited-tables-2"], ["delimited-tables", "delimited-records"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:quoteChar "22"^^xsd:hexBinary ;
       bddo:skipRecords 1 ; bddo:hasField ( ex:Root.name ex:Root.qty ) .
   ex:Root.name a bddo:Field ; bddo:dataType bddo:string .
   ex:Root.qty a bddo:Field ; bddo:dataType bddo:asciiInteger .
   """,
   b'name,qty\n"a,b",1\n"say ""hi""",2\n',
   [{"name": "a,b", "qty": 1}, {"name": 'say "hi"', "qty": 2}])

pp("table-empty-value-is-a-value", "An empty value is a value",
   "The record a,,c has three values; the middle one is the empty string.",
   ["req-pm-delimited-tables-2"], ["delimited-tables"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:hasField ( ex:Root.a ex:Root.b ex:Root.c ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string .
   ex:Root.b a bddo:Field ; bddo:dataType bddo:string .
   ex:Root.c a bddo:Field ; bddo:dataType bddo:string .
   """,
   b"a,,c\n", [{"a": "a", "b": "", "c": "c"}])

pp("table-column-count", "A record with the wrong number of values is a validation error",
   "The second record has three values for two fields.",
   ["req-pm-delimited-tables-2", "req-pm-errors-4"], ["delimited-tables"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:hasField ( ex:Root.a ex:Root.b ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string .
   ex:Root.b a bddo:Field ; bddo:dataType bddo:string .
   """,
   b"a,b\nc,d,e\n", error="Validation")

pp("records-bom-crlf-comments", "A leading BOM is ignored, CRLF reads as LF, comments and a final delimiter add no records",
   "Records after the BOM: a comment line is discarded and the trailing CR LF yields no empty last record.",
   ["req-pm-delimited-records-1", "req-pm-delimited-records-2", "req-pm-delimited-records-3", "req-pm-delimited-records-4"], ["delimited-records", "delimited-tables"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "3B"^^xsd:hexBinary ; bddo:commentPrefix "#" ;
       bddo:hasField ( ex:Root.k ex:Root.v ) .
   ex:Root.k a bddo:Field ; bddo:dataType bddo:string .
   ex:Root.v a bddo:Field ; bddo:dataType bddo:asciiDecimal .
   """,
   b"\xef\xbb\xbfx;1.5\r\n  # note\r\ny;2\r\n", [{"k": "x", "v": 1.5}, {"k": "y", "v": 2.0}])

pp("records-escape-char", "An escape character strips a delimiter of its meaning",
   "a\\,b,c has two values, a,b and c.",
   ["req-pm-delimited-records-6"], ["delimited-records"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:escapeChar "5C"^^xsd:hexBinary ;
       bddo:hasField ( ex:Root.a ex:Root.b ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string .
   ex:Root.b a bddo:Field ; bddo:dataType bddo:string .
   """,
   b"a\\,b,c\n", [{"a": "a,b", "b": "c"}])

pp("records-malformed-utf8", "A malformed byte sequence in a text container is a validation error",
   "0xFF is not UTF-8; it is never replaced silently.",
   ["req-pm-delimited-records-2", "req-pm-errors-4"], ["delimited-records"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string .
   """,
   b"ok\n\xff\n", error="Validation")

pp("records-unterminated-quote", "A quoted value still open at the end is a validation error",
   "The quote opened on the second record never closes.",
   ["req-pm-delimited-records-6", "req-pm-errors-4"], ["delimited-records"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:fieldDelimiter "2C"^^xsd:hexBinary ; bddo:quoteChar "22"^^xsd:hexBinary ;
       bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string .
   """,
   b'ok\n"open\n', error="Validation")

pp("records-whitespace-separated", "Whitespace-separated records: a run of any length separates two values",
   "Leading and trailing whitespace on a record is ignored.",
   ["req-pm-delimited-records-5"], ["delimited-records", "delimited-tables"],
   """
   ex:Root a bddo:DelimitedTable ; bddo:recordDelimiter "0A"^^xsd:hexBinary ; bddo:whitespaceSeparated true ;
       bddo:hasField ( ex:Root.x ex:Root.y ) .
   ex:Root.x a bddo:Field ; bddo:dataType bddo:asciiInteger .
   ex:Root.y a bddo:Field ; bddo:dataType bddo:asciiInteger .
   """,
   b"  1    2\n3\t4  \n", [{"x": 1, "y": 2}, {"x": 3, "y": 4}])

pp("flat-value-sequence", "A whitespace container with no record delimiter is one flat sequence",
   "The values fill the fields in order, the repeating field taking its repeat count.",
   ["req-pm-delimited-tables-1"], ["delimited-tables", "delimited-records"],
   """
   ex:Root a bddo:DelimitedRecords ; bddo:whitespaceSeparated true ; bddo:hasField ( ex:Root.n ex:Root.v ex:Root.t ) .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:asciiInteger .
   ex:Root.v a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:repeatCountFromField ex:Root.n .
   ex:Root.t a bddo:Field ; bddo:dataType bddo:string .
   """,
   b"3\n 1.0  2.5\t\n-3 end\n", {"n": 3, "v": [1.0, 2.5, -3.0], "t": "end"})

pp("flat-value-sequence-count", "A flat sequence with a different number of values is a validation error",
   "Four values are declared and three are present.",
   ["req-pm-delimited-tables-1", "req-pm-errors-4"], ["delimited-tables"],
   """
   ex:Root a bddo:DelimitedRecords ; bddo:whitespaceSeparated true ; bddo:hasField ( ex:Root.v ) .
   ex:Root.v a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:repeatCount 4 .
   """,
   b"1 2 3", error="Validation")

# ----------------------------------------------------------------- tree documents

pp("tree-json", "JSON pointers locate fields; an absent path or JSON null leaves the field unbound",
   "/shape/0 reads 3, /dtype reads a string, /missing and /fill (null) are unbound.",
   ["req-pm-conformance-classes-6"], ["tree-documents"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ;
       bddo:hasField ( ex:Root.rows ex:Root.dtype ex:Root.missing ex:Root.fill ) .
   ex:Root.rows a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:nodePath "/shape/0" .
   ex:Root.dtype a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/dtype" .
   ex:Root.missing a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/missing" .
   ex:Root.fill a bddo:Field ; bddo:dataType bddo:asciiDecimal ; bddo:nodePath "/fill" .
   """,
   b'{"shape": [3, 4], "dtype": "<f4", "fill": null}',
   {"rows": 3, "dtype": "<f4", "missing": None, "fill": None}, manifest=TREES)

pp("tree-json-array-repeat", "A repeating field over a JSON array repeats over its elements",
   "/vals selects one array; the field's repeat count matches its three elements.",
   ["req-pm-conformance-classes-6"], ["tree-documents"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ex:Root.vals ) .
   ex:Root.vals a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:nodePath "/vals" ; bddo:repeatCount 3 .
   """,
   b'{"vals": [1, 2, 3]}', {"vals": [1, 2, 3]}, manifest=TREES)

pp("tree-json-trailing-value", "JSON with a trailing value is not well-formed",
   "A second top-level value follows the object.",
   ["req-pm-tree-documents-1", "req-pm-errors-4"], ["tree-documents"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/a" .
   """,
   b'{"a": "x"} 1', error="Validation", manifest=TREES)

pp("tree-json-duplicate-member", "A duplicated JSON member selected by a non-repeating field is a validation error",
   "/a selects two nodes.",
   ["req-pm-tree-documents-1", "req-pm-errors-4"], ["tree-documents"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:json ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/a" .
   """,
   b'{"a": "x", "a": "y"}', error="Validation", manifest=TREES)

pp("tree-xml-namespaces", "XML paths match by namespace IRI, not by the document's prefix",
   "The description binds q to the namespace the document calls p; a positional predicate and an attribute step select nodes.",
   ["req-pm-conformance-classes-6"], ["tree-documents"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:xml ;
       bddo:hasNamespaceBinding [ a bddo:NamespaceBinding ; bddo:namespacePrefix "q" ; bddo:namespaceIRI "urn:example:ns"^^xsd:anyURI ] ;
       bddo:hasField ( ex:Root.second ex:Root.n ex:Root.plain ) .
   ex:Root.second a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/q:a/q:b[2]" .
   ex:Root.n a bddo:Field ; bddo:dataType bddo:asciiInteger ; bddo:nodePath "/q:a/q:b[1]/@n" .
   ex:Root.plain a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/a/b" .
   """,
   b'<p:a xmlns:p="urn:example:ns"><p:b n="5">hi</p:b><p:b>there <i>you</i></p:b></p:a>',
   {"second": "there you", "n": 5, "plain": None}, manifest=TREES)

pp("tree-xml-unbound-prefix", "A path prefix the description does not bind is a description error",
   "The path uses r:, which no namespace binding declares.",
   ["req-pm-errors-8"], ["tree-documents"],
   """
   ex:Root a bddo:TreeDocument ; bddo:treeSyntax bddo:xml ; bddo:hasField ( ex:Root.a ) .
   ex:Root.a a bddo:Field ; bddo:dataType bddo:string ; bddo:nodePath "/r:a" .
   """,
   b'<a/>', error="Description", manifest=TREES)

# ----------------------------------------------------------------- data layouts

LAYOUT_HEAD = """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:h ex:kind ex:pixels ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:h a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:kind a bddo:Field ; bddo:dataType bddo:string ; bddo:size 1 ; bddo:encoding bddo:ascii .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
   ex:DimY a dlv:Dimension ; dlv:hasAxis dlv:axisY ; dlv:dimensionSizeFromField ex:h .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:w .
"""

pp("layout-read-as-bytes", "A field with a data layout is read as a byte block",
   "The layout says how cells are addressed; the parsed value is the field's bytes.",
   ["req-pm-data-layouts-1"], ["data-layouts"],
   LAYOUT_HEAD + """
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:hasDimension ( ex:DimY ex:DimX ) .
   """,
   b"\x02\x02B" + b"\x01\x02\x03\x04", {"w": 2, "h": 2, "kind": "B", "pixels": b"\x01\x02\x03\x04"})

pp("layout-conditional-cell-no-arm", "A conditional cell type with no holding arm is a Type / HEL error",
   "Neither arm holds for kind 'Z'; the layout is resolved before any cell is addressed.",
   ["req-pm-data-layouts-1", "req-pm-errors-6"], ["data-layouts"],
   LAYOUT_HEAD + """
   ex:Layout a dlv:DataLayout ;
       dlv:hasConditionalCellDataType (
           [ a dlv:CellDataTypeRule ; bddo:condition "kind == 'B'" ; dlv:ruleCellDataType bddo:uint8 ]
           [ a dlv:CellDataTypeRule ; bddo:condition "kind == 'S'" ; dlv:ruleCellDataType bddo:uint16 ] ) ;
       dlv:hasDimension ( ex:DimY ex:DimX ) .
   """,
   b"\x02\x02Z" + b"\x01\x02\x03\x04", error="Expression")

pp("layout-size-not-integer", "A dimension size that is not an integer is a Type / HEL error",
   "The dimension size is read from a string field.",
   ["req-pm-data-layouts-1", "req-pm-errors-6"], ["data-layouts"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:kind ex:pixels ) .
   ex:kind a bddo:Field ; bddo:dataType bddo:string ; bddo:size 1 ; bddo:encoding bddo:ascii .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:hasDimension ( ex:DimX ) .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:kind .
   """,
   b"B\x01\x02", error="Expression")

pp("layout-packed-float", "A packed width on a non-integer cell type is a description error",
   "cellBitWidth 4 on float32 cells.",
   ["req-pm-errors-8"], ["data-layouts"],
   LAYOUT_HEAD + """
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:float32 ; dlv:cellBitWidth 4 ; dlv:hasDimension ( ex:DimY ex:DimX ) .
   """,
   b"\x02\x02B" + b"\x01\x02", error="Description")

pp("layout-chunked-bytes-read", "A chunked layout is accepted and the field's bytes are read",
   "Every Physical Parser accepts the chunk declarations; only cell access through the chunk table is optional.",
   ["req-pm-conformance-classes-7"], ["conformance-classes", "data-layouts"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:offsets ex:pixels ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:offsets a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:chunkOffsetsFromField ex:offsets ;
       dlv:chunkOffsetBase bddo:streamStart ; dlv:chunkOrder dlv:rowMajor ; dlv:hasDimension ( ex:DimX ) .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:w ; dlv:chunkSize 2 .
   """,
   b"\x04\x03\x05" + b"\x01\x02\x03\x04", {"w": 4, "offsets": [3, 5], "pixels": b"\x01\x02\x03\x04"})

pp("layout-chunk-order-unclaimed", "A chunk order other than row- or column-major is refused when not claimed",
   "dlv:morton is an optional feature; a processor that does not claim it rejects the description when it is loaded.",
   ["req-pm-conformance-classes-8", "req-pm-conformance-classes-4", "req-pm-errors-10"], ["conformance-classes", "refusal"],
   """
   ex:Root a bddo:Struct ; bddo:hasField ( ex:w ex:offsets ex:pixels ) .
   ex:w a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:offsets a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCount 2 .
   ex:pixels a bddo:Field ; bddo:dataType bddo:bytes ; bddo:sizeToEndOfStream true ; hexplain:hasDataLayout ex:Layout .
   ex:Layout a dlv:DataLayout ; dlv:cellDataType bddo:uint8 ; dlv:chunkOffsetsFromField ex:offsets ;
       dlv:chunkOrder dlv:morton ; dlv:hasDimension ( ex:DimX ) .
   ex:DimX a dlv:Dimension ; dlv:hasAxis dlv:axisX ; dlv:dimensionSizeFromField ex:w ; dlv:chunkSize 2 .
   """,
   b"\x04\x03\x05" + b"\x01\x02\x03\x04", error="Unsupported",
   manifest={"features": {"unclaimed": ["chunk-order-other"]}})
