format t @namespace "https://example.org/hc-offset-field-start-later-field#"
struct Root {
  a : u8 @at 2 from field-start b
  b : u8
}
