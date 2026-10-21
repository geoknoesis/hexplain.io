format t @namespace "https://example.org/hc-defines-aggregate#"
struct Root {
  items : u8 repeat 2
  cnt : derive 1 @defines sumOf(items, self)
}
