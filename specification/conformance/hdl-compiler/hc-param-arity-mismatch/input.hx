format t @namespace "https://example.org/hc-param-arity-mismatch#"
struct Root {
  r : Row(1)
}
struct Row(n, w) { cells : bytes[w] repeat n }
