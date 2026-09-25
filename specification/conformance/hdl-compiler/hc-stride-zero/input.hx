format t @namespace "https://example.org/hc-stride-zero#"
struct Root {
  w : u8
  pixels : bytes[..] layout cell u8 { dim axis X size w stride 0 }
}
