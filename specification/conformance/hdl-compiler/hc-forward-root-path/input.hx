format t @namespace "https://example.org/hc-forward-root-path#"
struct Root {
  hdr : Hdr
  n : u8
}
struct Hdr {
  data : bytes[root.n]
}
