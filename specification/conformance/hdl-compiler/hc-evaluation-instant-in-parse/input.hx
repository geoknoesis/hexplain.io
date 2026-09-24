format t @namespace "https://example.org/hc-evaluation-instant-in-parse#"
struct Root {
  a : u8 if evaluationInstant() > 0
}
