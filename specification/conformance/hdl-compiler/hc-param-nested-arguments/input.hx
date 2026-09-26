format t @namespace "https://example.org/hc-param-nested-arguments#"
struct Root {
  hdr : Header
  a : Row(hdr.count)
  b : Row(4)
}
struct Header { count : u8 }
struct Row(w) {
  cell : Cell(w + 1)
}
struct Cell(size: int) {
  data : bytes[size]
}
