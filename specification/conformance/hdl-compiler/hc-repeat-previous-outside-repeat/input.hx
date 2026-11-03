format t @namespace "https://example.org/hc-repeat-previous-outside-repeat#"
struct Root {
  n : u8
  d : bytes[repeat.previous]
}
