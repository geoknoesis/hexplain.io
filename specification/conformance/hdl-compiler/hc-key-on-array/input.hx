format t @namespace "https://example.org/hc-key-on-array#"
struct Root {
  es : E repeat 2
  d : derive es.size
}
struct E { v : u8 }
