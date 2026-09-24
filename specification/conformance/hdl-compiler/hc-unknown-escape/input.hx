format t @namespace "https://example.org/hc-unknown-escape#"
struct Root {
  tag : ascii[2] @fixed "\q"
}
