format t @namespace "https://example.org/hc-checksum-crc-field-width#"
struct Root {
  data : bytes[4]
  sum : u16 @checksum crc32c(data .. data)
}
