format t @namespace "https://example.org/hc-repeat-index-outside-repeat#"
struct Root {
  n : u8
  d : bytes[repeat.index]
}
