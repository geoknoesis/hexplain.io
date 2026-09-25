format t @namespace "https://example.org/hc-element-key#"
struct Root {
  es : E repeat 2
  d : derive es[0].v
}
struct E { v : u8 }
