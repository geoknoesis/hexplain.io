format t @namespace "https://example.org/hc-forward-checksum-covers#"
struct Root {
  s : u32 @checksum crc32(covers(0, n))
  n : u8
}
struct A { a : u8 }
