format t @namespace "https://example.org/hc-forward-repeat-until-container#"
struct Root {
  recs : Rec repeat until kind == stop
  stop : u8
}
struct Rec { kind : u8 }
