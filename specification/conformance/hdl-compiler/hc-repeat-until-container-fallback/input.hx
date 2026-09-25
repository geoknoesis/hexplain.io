format t @namespace "https://example.org/hc-repeat-until-container-fallback#"
struct Root {
  stop : u8
  recs : Rec repeat until kind == stop
}
struct Rec { kind : u8 }
