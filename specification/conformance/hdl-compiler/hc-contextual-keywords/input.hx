hdl 1.0
format t @namespace "https://example.org/hc-contextual-keywords#"
struct Root {
  type : u8
  size : u8
  value : bytes[size]
}
