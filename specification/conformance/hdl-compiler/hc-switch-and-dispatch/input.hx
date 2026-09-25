format t @namespace "https://example.org/hc-switch-and-dispatch#"
struct Root {
  kind : u8
  body : switch kind { 1 => A } dispatch T on kind { 2 => A }
}
struct A { a : u8 }
