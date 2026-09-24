"""Bundle Processor cases: assembly, part ordering, the asset root and the asset graph.

Each case gives the asset's files (manifest `parts`: path relative to the asset root, the file
holding its bytes, and its IRI) and the bundle profile to process them with. The expected graph
leaves out the bundle profile's own triples -- its IRI and the blank nodes reachable from it --
which the asset graph also carries; the runner removes them from the actual graph too.
"""
from suite import Case

PM = "processing#"
CASES = []
ASSET = "urn:example:asset"
ROLES = "@prefix rpr: <https://hexplain.io/ns/register/part-role#> .\n"


def part(path, content):
    return {"path": path, "iri": f"{ASSET}/{path}", "content": content}


def bp(id, title, intent, reqs, sections, description, parts, expected_ttl=None, error=None, manifest=None):
    files, listed = {}, []
    for n, p in enumerate(parts, 1):
        files[f"part-{n}.bin"] = p["content"]
        listed.append({"path": p["path"], "file": f"part-{n}.bin", "iri": p["iri"]})
    man = {"bundleProfile": f"https://example.org/bp-{id}#Profile", "asset": ASSET, "parts": listed}
    man.update(manifest or {})
    CASES.append(Case(id=f"bp-{id}", cls="bundle-processor", title=title, intent=intent, requirements=reqs,
                      sections=[PM + s if "#" not in s else s for s in sections],
                      description=ROLES + description, expected_ttl=None if expected_ttl is None else ROLES + expected_ttl,
                      error=error, root=None, manifest=man, files=files))


SIDECAR = """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".hdr" ; abnd:partRole rpr:Metadata ; abnd:required true ;
         abnd:describedBy ex:Header ; abnd:carriesAspect <https://hexplain.io/ns/aspect/raster> ; abnd:liftsProperty ex:count ] ,
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ; abnd:required true ; abnd:primary true ;
         abnd:describedBy ex:Grid ] .
   ex:Header a bddo:Struct ; hexplain:mapsToClass ex:HeaderClass ; bddo:hasField ( ex:n ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:count .
   ex:Grid a bddo:Struct ; hexplain:mapsToClass ex:GridClass ; bddo:hasField ( ex:size ex:cells ) .
   ex:size a bddo:Field ; bddo:valueFromExpression "asset.Header.n" .
   ex:cells a bddo:Field ; bddo:dataType bddo:uint8 ; bddo:repeatCountFromField ex:size ; hexplain:mapsToProperty ex:cell .
"""

bp("sidecar-order", "A part reading another part's content is parsed after it, whatever the file order",
   "The grid part, listed first, reads asset.Header.n; the header part is parsed first. Each part is minted against its own IRI, "
   "the asset links its parts and its primary part, and the header's lifted property is copied onto the asset.",
   ["req-pm-multi-part-assets-2", "req-hel-reserved-roots-1"], ["multi-part-assets", "hel/index.html#reserved-roots"],
   SIDECAR, [part("a.dat", b"\x07\x08\x09"), part("a.hdr", b"\x03")],
   f"""
   <{ASSET}> a abnd:Asset ; dcterms:conformsTo ex:Profile ;
       abnd:hasPart <{ASSET}/a.hdr#root> , <{ASSET}/a.dat#root> ; abnd:primaryPart <{ASSET}/a.dat#root> ;
       ex:count "3"^^xsd:unsignedByte .
   <{ASSET}/a.hdr#root> a abnd:Part , ex:HeaderClass ; abnd:partRole rpr:Metadata ; ex:count "3"^^xsd:unsignedByte .
   <{ASSET}/a.dat#root> a abnd:Part , ex:GridClass ; abnd:partRole rpr:Payload ;
       ex:cell "7"^^xsd:unsignedByte , "8"^^xsd:unsignedByte , "9"^^xsd:unsignedByte .
   """)

bp("part-extension", "partExtension() reads which alternative extension a part matched, ignoring case",
   "The payload spec lists .bil and .flt; the file A.FLT matches .flt ignoring ASCII case, and partExtension reports '.flt', "
   "lower-cased with its leading dot, for the part asking about itself.",
   ["req-hel-core-functions-4", "req-pm-multi-part-assets-1"], ["multi-part-assets", "hel/index.html#core-functions"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".bil" , ".flt" ; abnd:partRole rpr:Payload ; abnd:required true ; abnd:describedBy ex:Grid ] .
   ex:Grid a bddo:Struct ; hexplain:mapsToClass ex:GridClass ; bddo:hasField ( ex:ext ex:v ) .
   ex:ext a bddo:Field ; bddo:valueFromExpression "partExtension(asset.Grid)" ; hexplain:mapsToProperty ex:extension .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   [part("A.FLT", b"\x01")],
   f"""
   <{ASSET}> a abnd:Asset ; dcterms:conformsTo ex:Profile ; abnd:hasPart <{ASSET}/A.FLT#root> .
   <{ASSET}/A.FLT#root> a abnd:Part , ex:GridClass ; abnd:partRole rpr:Payload ; ex:extension ".flt" .
   """)

bp("carried-part", "A part whose spec has no abnd:describedBy is carried but not parsed",
   "The .prj part is linked and typed but contributes no content.",
   ["req-pm-multi-part-assets-1"], ["multi-part-assets"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ; abnd:required true ; abnd:describedBy ex:Grid ] ,
       [ a abnd:PartSpec ; abnd:extension ".prj" ; abnd:partRole rpr:SpatialReference ] .
   ex:Grid a bddo:Struct ; hexplain:mapsToClass ex:GridClass ; bddo:hasField ( ex:v ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 ; hexplain:mapsToProperty ex:value .
   """,
   [part("a.dat", b"\x05"), part("a.prj", b"not parsed")],
   f"""
   <{ASSET}> a abnd:Asset ; dcterms:conformsTo ex:Profile ; abnd:hasPart <{ASSET}/a.dat#root> , <{ASSET}/a.prj#root> .
   <{ASSET}/a.dat#root> a abnd:Part , ex:GridClass ; abnd:partRole rpr:Payload ; ex:value "5"^^xsd:unsignedByte .
   <{ASSET}/a.prj#root> a abnd:Part ; abnd:partRole rpr:SpatialReference .
   """)

bp("unmatched-file", "A file that matches no part spec is a validation error",
   "a.txt matches neither .hdr nor .dat.",
   ["req-pm-errors-4"], ["multi-part-assets", "errors"],
   SIDECAR, [part("a.hdr", b"\x01"), part("a.dat", b"\x07"), part("a.txt", b"x")], error="Validation")

bp("required-part-missing", "A required part with no file is a validation error",
   "The required .hdr part is absent.",
   ["req-pm-multi-part-assets-1", "req-pm-errors-4"], ["multi-part-assets"],
   SIDECAR, [part("a.dat", b"\x07")], error="Validation")

bp("extension-count", "Two files for a spec located by extension is a validation error",
   "abnd:maxParts defaults to 1 for an extension spec, which names one member.",
   ["req-pm-multi-part-assets-1", "req-pm-errors-4"], ["multi-part-assets"],
   SIDECAR, [part("a.hdr", b"\x01"), part("a.dat", b"\x07"), part("b.dat", b"\x07")], error="Validation")

bp("pattern-count", "A pattern spec's file count must lie within minParts..maxParts",
   "Three files match measurement/*.dat, whose maxParts is 2.",
   ["req-pm-multi-part-assets-1", "req-pm-errors-4"], ["multi-part-assets"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:pathPattern "measurement/*.dat" ; abnd:partRole rpr:Payload ; abnd:minParts 1 ; abnd:maxParts 2 ] .
   """,
   [part("measurement/a.dat", b"1"), part("measurement/b.dat", b"2"), part("measurement/c.dat", b"3")], error="Validation")

bp("ambiguous-file", "A file matching the part specs of more than one part is a validation error",
   "a.dat matches both the .dat extension and the *.dat pattern.",
   ["req-pm-errors-4"], ["multi-part-assets"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ] ,
       [ a abnd:PartSpec ; abnd:pathPattern "*.dat" ; abnd:partRole rpr:Segment ] .
   """,
   [part("a.dat", b"1")], error="Validation")

bp("reference-cycle", "Cross-part references that form a cycle are a description error",
   "The header reads the grid and the grid reads the header; raised before any part is parsed.",
   ["req-pm-multi-part-assets-2", "req-pm-errors-8"], ["multi-part-assets", "errors"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".hdr" ; abnd:partRole rpr:Metadata ; abnd:describedBy ex:Header ] ,
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ; abnd:describedBy ex:Grid ] .
   ex:Header a bddo:Struct ; bddo:hasField ( ex:n ex:peek ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:peek a bddo:Field ; bddo:valueFromExpression "asset.Grid.v" .
   ex:Grid a bddo:Struct ; bddo:hasField ( ex:v ex:m ) .
   ex:v a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:m a bddo:Field ; bddo:valueFromExpression "asset.Header.n" .
   """,
   [part("a.hdr", b"\x01"), part("a.dat", b"\x07")], error="Description")

bp("unknown-part-key", "A key the referenced part's root struct does not declare is a Type / HEL error",
   "asset.Header.typo names no field of Header; it is never Null.",
   ["req-hel-reserved-roots-1", "req-pm-errors-6"], ["multi-part-assets", "hel/index.html#reserved-roots"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".hdr" ; abnd:partRole rpr:Metadata ; abnd:describedBy ex:Header ] ,
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ; abnd:describedBy ex:Grid ] .
   ex:Header a bddo:Struct ; bddo:hasField ( ex:n ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Grid a bddo:Struct ; bddo:hasField ( ex:m ) .
   ex:m a bddo:Field ; bddo:valueFromExpression "asset.Header.typo" .
   """,
   [part("a.hdr", b"\x01"), part("a.dat", b"\x07")], error="Expression")

bp("missing-part-reference", "Naming a part the asset does not have is a Type / HEL error",
   "The grid reads asset.Header, but the optional header part has no file.",
   ["req-hel-reserved-roots-1", "req-pm-errors-6"], ["multi-part-assets", "hel/index.html#reserved-roots"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".hdr" ; abnd:partRole rpr:Metadata ; abnd:describedBy ex:Header ] ,
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ; abnd:describedBy ex:Grid ] .
   ex:Header a bddo:Struct ; bddo:hasField ( ex:n ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   ex:Grid a bddo:Struct ; bddo:hasField ( ex:m ) .
   ex:m a bddo:Field ; bddo:valueFromExpression "asset.Header.n" .
   """,
   [part("a.dat", b"\x07")], error="Expression")

bp("duplicate-part-name", "Two part specs described by structs with one local name are a description error",
   "Both structs are named Header, so asset.Header would be ambiguous.",
   ["req-pm-errors-8"], ["multi-part-assets", "errors"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:extension ".hdr" ; abnd:partRole rpr:Metadata ; abnd:describedBy ex:Header ] ,
       [ a abnd:PartSpec ; abnd:extension ".dat" ; abnd:partRole rpr:Payload ; abnd:describedBy <https://example.org/other#Header> ] .
   ex:Header a bddo:Struct ; bddo:hasField ( ex:n ) .
   ex:n a bddo:Field ; bddo:dataType bddo:uint8 .
   <https://example.org/other#Header> a bddo:Struct ; bddo:hasField ( ex:m ) .
   ex:m a bddo:Field ; bddo:dataType bddo:uint8 .
   """,
   [part("a.hdr", b"\x01"), part("a.dat", b"\x07")], error="Description")

bp("nested-profile-unclaimed", "abnd:nestedProfile is refused with Unsupported feature when not claimed",
   "A Bundle Processor that does not assemble nested profiles rejects a profile that uses one.",
   ["req-pm-conformance-classes-1", "req-pm-errors-10"], ["conformance-classes", "multi-part-assets"],
   """
   ex:Profile a abnd:BundleProfile ; abnd:partSpec
       [ a abnd:PartSpec ; abnd:pathPattern "annotation/**" ; abnd:partRole rpr:Metadata ; abnd:nestedProfile ex:Inner ] .
   ex:Inner a abnd:BundleProfile ; abnd:partSpec [ a abnd:PartSpec ; abnd:pathPattern "*.xml" ; abnd:partRole rpr:Metadata ] .
   """,
   [part("annotation/a.xml", b"<a/>")], error="Unsupported",
   manifest={"features": {"unclaimed": ["abnd:nestedProfile"]}})
