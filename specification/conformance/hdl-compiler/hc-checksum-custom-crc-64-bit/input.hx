format t @namespace "https://example.org/hc-checksum-custom-crc-64-bit#"
struct Root {
  data : bytes[4]
  sum : u64 @checksum crc(width: 64, poly: 0x42F0E1EBA9EA3693, init: 0xFFFFFFFFFFFFFFFF, refin: true, refout: true, xorout: 0xFFFFFFFFFFFFFFFF)(data .. data)
}
