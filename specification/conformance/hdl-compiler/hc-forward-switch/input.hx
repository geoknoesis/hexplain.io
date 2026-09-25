format t @namespace "https://example.org/hc-forward-switch#"
struct Root {
  body : switch { when n == 1 => A }
  n : u8
}
struct A { a : u8 }
