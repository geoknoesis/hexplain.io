format t @namespace "https://example.org/hc-offset-field-start#"
struct Root {
  header : u16
  len : u8
  body : u8 @at 8 from field-start header
  tail : u8 @at len from field-start header
}
