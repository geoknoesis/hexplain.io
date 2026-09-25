format t @namespace "https://example.org/hc-switch-name-key#"
struct Root {
  kind : ascii[4]
  body : switch kind { IHDR => A }
}
struct A { a : u8 }
