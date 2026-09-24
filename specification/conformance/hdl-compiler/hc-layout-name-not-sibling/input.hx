format t @namespace "https://example.org/hc-layout-name-not-sibling#"
struct Root {
  w : u8
  pixels : bytes[..] layout cell u8 { dim axis X size width }
}
