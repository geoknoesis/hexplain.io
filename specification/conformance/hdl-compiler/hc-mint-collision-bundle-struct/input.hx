format t @namespace "https://example.org/hc-mint-collision-bundle-struct#"
bundle Grid @bound-by naming-convention {
  part ".dat" role Payload required primary described-by Grid
}
struct Grid { v : u8 }
