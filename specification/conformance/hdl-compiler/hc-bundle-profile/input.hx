format t @namespace "https://example.org/hc-bundle-profile#"
use araster: <https://hexplain.io/ns/aspect/raster#>
bundle Sidecar @bound-by naming-convention {
  part ".dat" role Payload required primary carries araster: described-by Grid
}
struct Grid { v : u8 }
