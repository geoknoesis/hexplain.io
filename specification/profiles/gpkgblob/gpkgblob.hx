// Hexplain Profile — OGC GeoPackage Binary geometry blob (GeoPackage 1.3, clause 2.1.3)
//
// Worth profiling on its own, separately from GeoPackage itself. The container is a SQLite
// database, whose B-tree the coverage survey puts out of reach; but the VALUE in each geometry
// column is a self-contained little binary structure that needs none of that. Anyone who has
// already extracted the blob -- by any means -- can describe it exactly.
//
// That split is the general lesson: "GeoPackage is at container level" is about the SQLite
// pages, not about every byte inside them. A format that embeds a described payload in an
// undescribed container is still worth describing at the payload.
//
// Layout:
//   magic     2  0x47 0x50 ("GP")
//   version   1  8-bit unsigned, 0 for GeoPackage 1.x
//   flags     1  bit 0    byte order of the ENVELOPE and the WKB that follow (1 = little)
//                bits 1-3 envelope contents indicator (0 = absent, 1 = XY, 2 = XYZ, 3 = XYM,
//                         4 = XYZM)
//                bit 4    empty-geometry flag
//                bit 5    ExtendedGeoPackageBinary
//   srs_id    4  int32, byte order per bit 0
//   envelope  0/32/48/48/64 bytes of doubles, per bits 1-3
//   payload      ISO/OGC well-known binary
//
// Source: OGC 12-128r19, GeoPackage Encoding Standard 1.3.1, clause 2.1.3.
// Verification status: NOT parse-verified against a sample file.

format gpkgblob @namespace "https://hexplain.io/ns/profile/gpkgblob#"

use asref:  <https://hexplain.io/ns/aspect/spatialref#>
use xsd:    <http://www.w3.org/2001/XMLSchema#>

@root struct GeoPackageBinary
  @label "GeoPackage Binary geometry blob"
  @comment "The value of a geometry column in a GeoPackage. Self-contained: a header carrying byte order, SRS and an optional envelope, followed by well-known binary."
  // Flags bit 0 declares the byte order of everything after it. A struct-level switch is exact
  // here rather than an approximation, because the three fields that precede the flags are all
  // byte-order-independent -- two magic bytes and two single-byte integers -- so there is no
  // prefix for it to get wrong.
  @endian switch {
    when [(flags & 1) == 1] => little
    when [(flags & 1) == 0] => big
  }
{
  magic : bytes[2] @fixed 0x4750
    @label "GP magic"

  version : u8
    @label "version"
    @comment "0 for GeoPackage 1.x. Not the GeoPackage version -- the binary header's own."

  flags : u8
    @label "flags"
    @comment "bit 0 byte order, bits 1-3 envelope contents, bit 4 empty geometry, bit 5 extended."

  srsId : i32 means asref:epsgCode
    @label "srs_id"
    @comment "Spatial reference identifier. In a GeoPackage this is the gpkg_spatial_ref_sys id, which for the common cases equals the EPSG code -- mapped as such here, with the caveat that a GeoPackage MAY define its own non-EPSG entries."

  // The envelope is 0, 4, 6, 6 or 8 doubles depending on bits 1-3. Expressed as a byte size
  // rather than a struct per case: a consumer that wants the numbers reads them from the
  // envelope's own layout, and a consumer that only wants the WKB needs to know how far to
  // skip. Both are served by the size alone.
  envelope : bytes[ ((flags >> 1) & 7) == 0 ? 0 :
                    (((flags >> 1) & 7) == 1 ? 32 :
                    (((flags >> 1) & 7) == 4 ? 64 : 48)) ]
    @label "envelope"
    @comment "0 bytes when absent, 32 for XY, 48 for XYZ or XYM, 64 for XYZM. Doubles in the declared byte order."

  wkb : bytes[..]
    @label "geometry"
    @comment "ISO/OGC well-known binary. Empty when the empty-geometry flag (bit 4) is set, which is distinct from an absent envelope. Physical-only: see limit 3."
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. THE WKB IS NOT DECOMPOSED. Its own header repeats a byte order and a geometry type, and
//    then recurses through rings and points -- a nested, self-describing structure. It is a
//    payload here, which is the honest level for a profile whose subject is the ENVELOPE.
// 2. ExtendedGeoPackageBinary (flag bit 5) adds an extension header this does not model.
// 3. THE GEOMETRY VALUE IS UNMAPPED. hx-geometry describes properties OF a geometry --
//    geometryType, dimensionality, coordinatePrecision -- but has no property meaning "this
//    field IS the geometry". GeoSPARQL's geo:asWKB is the right target under the architecture's
//    "map to external standards at the leaf" rule, but no profile maps to an external property
//    today and hexplain:MapsToPropertyShape requires the target to be a loaded declaration, so
//    it would be rejected. Left physical-only rather than minting an ageom: term, which would
//    be re-inventing GeoSPARQL inside an aspect to satisfy a shape.
