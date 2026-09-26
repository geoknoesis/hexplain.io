format t @namespace "https://example.org/hc-param-literal-type-mismatch#"
struct Root {
  r : Row("a")
}
struct Row(n: int) { cells : bytes[n] }
