format t @namespace "https://example.org/hc-checksum-custom-crc-repeated-parameter#"
struct Root {
  data : bytes[4]
  sum : u16 @checksum crc(width: 16, poly: 0x8005, init: 0, init: 1, refin: true, refout: true, xorout: 0)(data .. data)
}
