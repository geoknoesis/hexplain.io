"""The normative vocabularies must stay format-neutral and register-free.

Hexplain's layering only pays off if each layer refuses to know about the one above it.
BDDO/DLV/core describe bytes, layout and mapping for ANY format; the aspect vocabularies
describe a domain; the concept registers carry the controlled values; a profile describes one
format. Every one of those boundaries is easy to cross by accident, in a way that reads as
convenience at the time and as coupling a year later, so each is checked here:

  1. NO FORMAT OR JURISDICTION NAMES in a normative term. The moment `bddo:nitfSecurityBlock`
     exists, BDDO has stopped being a byte vocabulary and started being NITF's; the moment
     `asec:ismDeclassException` exists, hx-security has become one country's policy wearing a
     neutral namespace. The second half of this check was added after the first version missed
     it entirely: it knew 61 format names and nothing about standards bodies or jurisdictions,
     so it would happily have passed hx-security 1.1, whose whole property set was US IC ISM's.
     Exemptions are listed below, each with its reason, so the judgment is visible and can be
     argued with rather than silently absent.

  2. NORMATIVE VOCABULARIES MUST NOT REFERENCE A REGISTER. That absence is precisely what
     makes a register swappable: hx-security defines the properties of a security marking
     while the us-nato-security register supplies one set of values, and a profile using a
     different classification system binds a different register. An aspect that named a
     register concept would nail one set of values to the property forever.

  3. REGISTERS MUST NOT REFERENCE AN ASPECT. The dependency runs one way. A register that
     named the property it serves could not be reused by a second property, and could not be
     published or versioned on its own.

  4. ASPECTS MUST DECLARE NO CONCEPTS. Concepts live in registers. test_register_extraction
     guards the six aspects that were migrated; this generalizes that to every aspect,
     including ones written later, which is where the rule would otherwise quietly lapse.

Profiles are deliberately NOT checked: a profile describing NITF is supposed to say NITF.
"""

import glob
import pathlib
import re
import sys

import rdflib

import specgraph

SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
REGISTER_NS = "https://hexplain.io/ns/register/"
ASPECT_NS = "https://hexplain.io/ns/aspect/"

#: Vocabularies that must be format-neutral: the three foundations plus every aspect.
def normative_files():
    return ["specification/bddo/bddo.ttl", "specification/dlv/dlv.ttl",
            "specification/hexplain/core.ttl"] + sorted(glob.glob("specification/aspect/*/*.ttl"))


#: Names that would betray a bias in a term. Matched against camelCase WORDS rather than as
#: substrings -- "class" contains "las", and "declassification" contains it twice.
#:
#: Two kinds, checked identically. A FORMAT name ties the vocabulary to one file layout; a
#: JURISDICTION or standards-body name ties it to one authority's rules. The second is the
#: subtler failure, because a term like `declassificationExemption` reads as neutral English
#: while naming a category that exists only under one national policy -- which is why the word
#: list cannot be the whole defence, and the aspects themselves have to be designed so that a
#: system's own categories arrive through a register rather than as properties.
FORMAT_WORDS = {
    "nitf", "tiff", "geotiff", "png", "jpeg", "jpg", "gif", "bmp", "webp", "exr", "dds",
    "ktx", "avif", "heif", "jp2", "envi", "ehdr", "esri", "shapefile", "geopackage", "gpkg",
    "mbtiles", "hdf", "hdf4", "hdf5", "netcdf", "grib", "zarr", "pds", "isis", "vicar",
    "dted", "fits", "zip", "pdf", "dwg", "dxf", "gml", "kml", "csv", "geojson", "parquet",
    "arrow", "protobuf", "mvt", "las", "laz", "e57", "sentinel", "landsat", "erdas",
    "idrisi", "saga", "ilwis", "pcidsk", "s57", "bag", "mrsid", "ecw", "shp", "dbf",
    # Jurisdictions, standards bodies and national policy identifiers.
    "ism", "nato", "capco", "fips", "dod", "dni", "nga", "nist", "iso", "ogc", "w3c", "ieee",
    "itu", "gsc", "tlp", "eo", "usa", "us", "uk", "eu", "nsa", "cia", "fbi", "ansi", "din",
    "jis", "milstd", "stanag", "ccitt", "etsi", "oasis", "niso",
}

#: Exempt terms, each with the reason it is not a bias. An ALGORITHM named after its
#: specifying document is not a format leaking in -- bddo already carries crc32, adler32, md5
#: and sha256 on exactly that basis.
EXEMPT = {
    "sqliteVarint":
        "An integer ENCODING, not a format. SQLite specifies it the way DWARF specifies "
        "LEB128, and it is used across GeoPackage, MBTiles and Rasterlite rather than by one "
        "format. Same category as bddo:crc32 / bddo:md5, which are also named for their "
        "specifying documents. A descriptive rename (bigEndianVarint) would be LESS precise: "
        "it would not distinguish this scheme's nine-byte rule from any other big-endian "
        "varint.",
}


def words(local_name):
    """camelCase / PascalCase / kebab split, lowercased."""
    return {w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|\d+", local_name)}


def local_names(graph, ontology_iri):
    out = set()
    for node in set(graph.subjects()):
        if isinstance(node, rdflib.URIRef) and str(node).startswith(ontology_iri + "#"):
            out.add(str(node).split("#", 1)[1])
    return out


def main():
    problems = []
    checked_terms = 0

    for path in normative_files():
        g = rdflib.Graph()
        g.parse(data=pathlib.Path(path).read_text(encoding="utf-8"), format="turtle")
        ont = next((str(s) for s in g.subjects(rdflib.RDF.type, rdflib.OWL.Ontology)), None)
        if ont is None:
            problems.append(f"{path}: no owl:Ontology declaration, cannot scope its terms")
            continue

        # 1 -- format names in term names
        for name in sorted(local_names(g, ont)):
            if name in EXEMPT:
                continue
            checked_terms += 1
            hit = words(name) & FORMAT_WORDS
            if hit:
                problems.append(
                    f"{path}: term '{name}' names a format or jurisdiction "
                    f"({', '.join(sorted(hit))}). A normative vocabulary serves any format and "
                    f"any authority's rules, not one. Either rename it, move it to a profile "
                    f"or register, or add it to EXEMPT with the reason."
                )

        # 2 -- normative vocabularies must not reference a register
        for s, p, o in g:
            for node, role in ((s, "subject"), (o, "object")):
                if isinstance(node, rdflib.URIRef) and str(node).startswith(REGISTER_NS):
                    problems.append(
                        f"{path}: references register term <{node}> as a {role}. Aspects do "
                        f"not import registers -- that absence is what lets a profile bind a "
                        f"different one."
                    )

        # 4 -- aspects declare no concepts
        if "/aspect/" in path.replace("\\", "/"):
            for kind in (SKOS.Concept, SKOS.ConceptScheme, SKOS.Collection):
                for s in g.subjects(rdflib.RDF.type, kind):
                    problems.append(
                        f"{path}: declares {str(kind).split('#')[-1]} <{s}>. Concepts belong "
                        f"in a register under specification/register/, so a profile can bind "
                        f"a different set of values."
                    )

    # 3 -- registers must not reference an aspect
    for path in sorted(glob.glob("specification/register/*/*.ttl")):
        g = rdflib.Graph()
        g.parse(data=pathlib.Path(path).read_text(encoding="utf-8"), format="turtle")
        for s, p, o in g:
            for node in (s, p, o):
                if isinstance(node, rdflib.URIRef) and str(node).startswith(ASPECT_NS):
                    problems.append(
                        f"{path}: references aspect term <{node}>. The dependency runs one "
                        f"way; a register that names the property it serves cannot be reused "
                        f"by another."
                    )

    if checked_terms < 150:
        problems.append(
            f"only {checked_terms} terms checked -- the scan is not reaching the vocabularies"
        )

    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print(f"PASS: {checked_terms} normative terms name no format or jurisdiction; "
          f"{len(EXEMPT)} reasoned exemption(s); register boundary holds both ways")
    return 0


if __name__ == "__main__":
    sys.exit(main())
