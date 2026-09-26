format t @namespace "https://example.org/hc-fixed-24-bit-and-half#"
struct Root {
  magic : u24 @fixed 0x010203
  code : i24 @fixed -2
  one : f16 @fixed 1
}
