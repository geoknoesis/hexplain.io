format t @namespace "https://example.org/hc-bit-order-field#"
struct Root @bit-order msb {
  a : bits[3] @bit-order lsb
  b : bits[5]
}
