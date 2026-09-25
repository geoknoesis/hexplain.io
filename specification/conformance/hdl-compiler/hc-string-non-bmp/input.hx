format t @namespace "https://example.org/hc-string-non-bmp#"
struct Root {
  a : utf8[4] @fixed "😀"
  b : utf8[4] @fixed "\uD83D\uDE00"
}
