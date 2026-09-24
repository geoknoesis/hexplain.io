format t @namespace "https://example.org/hc-field-and-expression-forms#"
struct Root {
  n : u8
  a : bytes[3]
  b : bytes[n * 2]
  c : u8 repeat n
  d : u8 repeat 2
  e : u8 repeat n + 1
  f : u8 @at n
  g : u8 @at 4
  h : u8 @at n - 1
}
