format t @namespace "https://example.org/hc-forward-parent-path#"
struct Root {
  hdr : Hdr
  n : u8
}
struct Hdr {
  data : bytes[parent.n]
}
