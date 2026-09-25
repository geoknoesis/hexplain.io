format t @namespace "https://example.org/hc-root-key#"
struct Root {
  recs : Rec repeat 2
  total : derive root.alpha
}
struct Rec {
  name : ascii[5]
  v : u8 @root-key name
}
