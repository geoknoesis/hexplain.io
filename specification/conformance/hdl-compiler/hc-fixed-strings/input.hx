format t @namespace "https://example.org/hc-fixed-strings#"
struct Root {
  a : bytes[4] @fixed "CAFE"
  b : bytes[4] @fixed "1234"
  c : utf16le[4] @fixed "AB"
}
