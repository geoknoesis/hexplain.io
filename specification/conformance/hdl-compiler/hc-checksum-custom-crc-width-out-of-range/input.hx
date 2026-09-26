format t @namespace "https://example.org/hc-checksum-custom-crc-width-out-of-range#"
struct Root {
  data : bytes[4]
  sum : u64 @checksum crc(width: 65, poly: 3, init: 0, refin: false, refout: false, xorout: 0)(data .. data)
}
