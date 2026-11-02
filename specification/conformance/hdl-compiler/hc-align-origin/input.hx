format t @namespace "https://example.org/hc-align-origin#"
struct Root {
  a : u8
  b : u32 @align 4 from struct
  c : u32 @align 8 from stream
  d : u16 @align 2
}
