format t @namespace "https://example.org/hc-defines#"
struct Root {
  count : u8
  items : u8 repeat 2
  cnt : derive len(items) @defines count
}
