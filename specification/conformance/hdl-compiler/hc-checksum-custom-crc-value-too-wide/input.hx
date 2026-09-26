format t @namespace "https://example.org/hc-checksum-custom-crc-value-too-wide#"
struct Root {
  data : bytes[4]
  sum : u16 @checksum crc(width: 16, poly: 0x18005, init: 0, refin: true, refout: true, xorout: 0)(data .. data)
}
