format t @namespace "https://example.org/hc-two-endian#"
struct Root {
  a : u16 @endian big @endian little
}
