format t @namespace "https://example.org/hc-param-argument-forward-reference#"
struct Root {
  r : Row(n)
  n : u8
}
struct Row(w) { cells : bytes[w] }
