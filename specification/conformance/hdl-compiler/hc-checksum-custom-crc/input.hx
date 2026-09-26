format t @namespace "https://example.org/hc-checksum-custom-crc#"
struct Frame {
  header : bytes[4]
  payload : bytes[8]
  crc : u16le @checksum crc(poly: 0x8005, width: 16, init: 0x0000, refin : true, refout: true, xorout: 0)(header .. payload)
}
