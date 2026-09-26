format t @namespace "https://example.org/hc-checksum-custom-crc-missing-parameter#"
struct Root {
  data : bytes[4]
  sum : u16 @checksum crc(width: 16, poly: 0x8005, init: 0, refin: true, refout: true)(data .. data)
}
