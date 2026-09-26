format t @namespace "https://example.org/hc-let-reads-parameter#"
struct Root {
  r : Row(3)
}
struct Row(n) {
  let total = n * 2
  let half = total / 2
  data : bytes[total]
  tail : bytes[half]
}
