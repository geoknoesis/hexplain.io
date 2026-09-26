format t @namespace "https://example.org/hc-param-struct#"
struct Table {
  count : u8
  width : u8
  rows : Row(count, width)
}
struct Row(n: int, w) {
  cells : bytes[w] repeat n
}
