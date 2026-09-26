format t @namespace "https://example.org/hc-param-undeclared#"
struct Root {
  r : Row(1)
}
struct Row(w) { cells : bytes[`param.x`] }
