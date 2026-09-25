format t @namespace "https://example.org/hc-lone-surrogate#"
struct Root {
  a : utf16le[2] @fixed "\uD800"
}
