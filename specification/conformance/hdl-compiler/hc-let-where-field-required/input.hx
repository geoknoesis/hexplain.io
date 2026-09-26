format t @namespace "https://example.org/hc-let-where-field-required#"
struct Root {
  data : bytes[4]
  let start = 0
  sum : u32 @checksum crc32(start .. data)
}
