format t @namespace "https://example.org/hc-param-holding-struct-in-element-scope#"
struct Root {
  r : R(3)
}
struct R(lim) {
  es : E repeat 2
  ok : derive all(es, v < lim)
}
struct E { v : u8 }
