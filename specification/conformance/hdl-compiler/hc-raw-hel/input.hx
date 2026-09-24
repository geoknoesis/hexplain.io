format t @namespace "https://example.org/hc-raw-hel#"
struct Root {
  n : u8
  data : bytes[`instance.n*2`]
}
