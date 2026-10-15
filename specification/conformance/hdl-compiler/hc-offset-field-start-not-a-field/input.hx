format t @namespace "https://example.org/hc-offset-field-start-not-a-field#"
struct Root {
  a : u8
  b : u8 @at 2 from field-start missing
}
