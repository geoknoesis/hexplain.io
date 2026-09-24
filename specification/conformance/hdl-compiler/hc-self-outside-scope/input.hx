format t @namespace "https://example.org/hc-self-outside-scope#"
struct Root {
  a : u8 if self == 1
}
