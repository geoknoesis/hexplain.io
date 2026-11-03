format t @namespace "https://example.org/hc-layout-cell-struct#"
struct Pixel { r : u8  g : u8 }
struct Root {
  pixels : bytes[..] layout cell Pixel { dim axis X size 4 }
}
