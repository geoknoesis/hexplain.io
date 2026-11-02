format t @namespace "https://example.org/hc-negative-offset-from-current#"
struct Root {
  a : u8
  b : u8
  p : u8 @at -2 from current
}
