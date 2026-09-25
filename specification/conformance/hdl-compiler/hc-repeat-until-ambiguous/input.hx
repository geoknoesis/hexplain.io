format t @namespace "https://example.org/hc-repeat-until-ambiguous#"
struct Root {
  kind : u8
  recs : Rec repeat until kind == 0
}
struct Rec { kind : u8 }
