format t @namespace "https://example.org/hc-param-switch-arms#"
struct Root {
  kind : u8
  body : switch kind {
    1 => Blob(2)
    2 => Blob(4)
  }
}
struct Blob(size: int) {
  data : bytes[size]
}
