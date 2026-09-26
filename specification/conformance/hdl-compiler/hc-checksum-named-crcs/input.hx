format t @namespace "https://example.org/hc-checksum-named-crcs#"
struct Root {
  text : ascii[9]
  c8 : u8 @checksum crc8(text .. text)
  c16a : u16 @checksum crc16arc(text .. text)
  c16x : u16 @checksum crc16xmodem(text .. text)
  c16m : u16 @checksum crc16modbus(text .. text)
  c16s : u16 @checksum crc16x25(text .. text)
  c32c : u32 @checksum crc32c(text .. text)
  c32b : u32 @checksum crc32bzip2(text .. text)
  c32m : u32 @checksum crc32mpeg2(text .. text)
  c64e : u64 @checksum crc64ecma(text .. text)
  c64x : u64 @checksum crc64xz(text .. text)
}
