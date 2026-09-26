format t @namespace "https://example.org/hc-param-element-scope#"
struct Root {
  r : R(3)
}
struct R(lim) {
  es : E(lim) repeat until v == stop
  ok : derive all(es, small)
}
struct E(stop) {
  v : u8
  let small = v < stop
}
