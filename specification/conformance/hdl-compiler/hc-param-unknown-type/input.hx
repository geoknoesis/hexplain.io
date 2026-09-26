format t @namespace "https://example.org/hc-param-unknown-type#"
struct Root {
  r : Row(1)
}
struct Row(n: integer) { cells : bytes[n] }
