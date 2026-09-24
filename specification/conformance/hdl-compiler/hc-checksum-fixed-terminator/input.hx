format t @namespace "https://example.org/hc-checksum-fixed-terminator#"
struct Root {
  magic : bytes[4] @fixed 0x89504E47
  code : i32 @fixed 9994
  name : ascii @terminator 0x00
  crc : u32 @checksum crc32(magic .. name)
}
