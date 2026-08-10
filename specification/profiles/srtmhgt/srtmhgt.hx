// Hexplain Profile — SRTM HGT (Shuttle Radar Topography Mission height file)
//
// The smallest complete raster description there is: the format has NO HEADER AT ALL. A .hgt
// file is nothing but big-endian int16 elevations in metres, row-major from the NORTH-WEST
// corner, and everything else is carried outside the bytes:
//
//   * the tile's south-west corner is in the FILENAME (N37W123.hgt), not the file;
//   * the grid size is implied by the FILE LENGTH -- 1201x1201 for 3-arc-second data,
//     3601x3601 for 1-arc-second, both squares of an odd number because tiles overlap their
//     neighbours by one row and column;
//   * the CRS is fixed by the mission (WGS 84 / EGM96 heights).
//
// That makes it the reference example of a description that is honest about what it does not
// contain. `derive` computes the side length from stream.length rather than reading it, since
// there is nothing to read, and the georeferencing that a GeoTIFF would carry in tags is
// simply absent here -- a consumer gets it from the filename or not at all.
//
// Source: NASA JPL SRTM documentation; USGS EROS SRTM product description.
// Verification status: NOT parse-verified against a sample file.

format srtmhgt @namespace "https://hexplain.io/ns/profile/srtmhgt#"

use araster: <https://hexplain.io/ns/aspect/raster#>
use asamp:   <https://hexplain.io/ns/aspect/sampling#>
use asref:   <https://hexplain.io/ns/aspect/spatialref#>
use dlv:     <https://hexplain.io/ns/dlv#>
use xsd:     <http://www.w3.org/2001/XMLSchema#>

@root struct HgtTile
  @label "SRTM HGT elevation tile"
  @comment "A headerless square grid of big-endian int16 elevations. Side length is derived from the file size; the tile's position comes from the filename and is not in the file."
{
  // 2 bytes per sample, and the grid is square, so side = sqrt(length / 2). Written as the
  // integer square root of the sample count. There is nothing in the file to read this from --
  // which is exactly why it is derived rather than parsed.
  side : derive [ (stream.length / 2 == 12967201) ? 3601 : 1201 ]
    @label "grid side length in samples"
    @comment "3601 for 1-arc-second (SRTM1, 25,934,402 bytes), else 1201 for 3-arc-second (SRTM3, 2,884,802 bytes). Compared on the sample count rather than the byte count so the intent -- 3601 squared -- is visible."

  samples : bytes[..]
    @label "elevation grid"
    layout cell i16be {
      // Row-major from the north-west corner: Y is the slower axis.
      dim axis Y size side
      dim axis X size side
    }

  // -32768 is the void marker (radar shadow, water, steep terrain). A consumer that treats it
  // as an elevation gets a 32 km deep hole, so it is stated even though nothing in the bytes
  // distinguishes it.
  raw-turtle {
    :HgtTile araster:noDataValue -32768 ;
        asamp:bitDepth 16 ;
        asref:epsgCode 4326 .
  }
}

// ---------- LIMITS OF THIS DESCRIPTION ----------
// 1. THE TILE'S LOCATION IS NOT IN THE FILE. N37W123.hgt means the SW corner is 37N 123W, and
//    that is a filename convention, not data. asref:originLatitude/originLongitude are
//    therefore absent rather than wrong. hx-bundle's abnd:stem can carry the stem, but nothing
//    in Hexplain parses meaning OUT of a filename, and inventing a rule here would put a guess
//    where the format has a convention.
// 2. VERTICAL DATUM. Heights are EGM96 geoid, not WGS 84 ellipsoid. asref: models the
//    horizontal CRS; there is no vertical-datum term yet, so epsgCode 4326 above understates
//    it.
// 3. The 1-arc-second/3-arc-second choice is inferred from file length. A truncated file
//    silently reads as the smaller grid. A processor SHOULD check that the length is exactly
//    one of the two, which `derive` cannot express -- bddo:validIf on a derived field would,
//    and is the natural place for it.
