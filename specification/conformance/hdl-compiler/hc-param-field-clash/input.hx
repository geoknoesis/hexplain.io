format t @namespace "https://example.org/hc-param-field-clash#"
struct Root {
  r : Row(1)
}
struct Row(n) {
  n : u8
}
