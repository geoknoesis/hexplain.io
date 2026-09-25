format t @namespace "https://example.org/hc-forward-layout-dimension#"
struct Root {
  pixels : bytes[4] layout cell u8 { dim axis X size h }
  h : u8
}
