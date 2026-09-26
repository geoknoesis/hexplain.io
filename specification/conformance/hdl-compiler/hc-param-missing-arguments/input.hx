format t @namespace "https://example.org/hc-param-missing-arguments#"
struct Root {
  r : Row
}
struct Row(n, w) { cells : bytes[w] repeat n }
