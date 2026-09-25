format t @namespace "https://example.org/hc-layout-cell#"
struct Image {
  w : u8
  h : u8
  pixels : bytes[..] layout cell u8 {
    dim axis Y size h
    dim axis X size w
  }
}
