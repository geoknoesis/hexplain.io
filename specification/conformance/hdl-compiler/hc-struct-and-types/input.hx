format t @namespace "https://example.org/hc-struct-and-types#"
struct Root {
  n : u16
  tag : ascii[4]
  k : i32le
  f : f64
  data : bytes[n]
}
