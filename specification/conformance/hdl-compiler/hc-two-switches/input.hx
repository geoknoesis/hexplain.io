format t @namespace "https://example.org/hc-two-switches#"
struct Root {
  kind : u8
  body : switch kind { 1 => A } switch kind { 2 => A }
}
struct A { a : u8 }
