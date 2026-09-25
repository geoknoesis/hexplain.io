format t @namespace "https://example.org/hc-parent-path-several-containers#"
struct Root {
  a : Hdr
  n : u8
  b : Box
}
struct Box {
  n : u8
  h : Hdr
}
struct Hdr {
  data : bytes[parent.n]
}
