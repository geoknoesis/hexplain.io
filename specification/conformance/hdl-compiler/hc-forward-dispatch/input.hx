format t @namespace "https://example.org/hc-forward-dispatch#"
struct Root {
  body : bytes[..] dispatch T on n { 1 => A }
  n : u8
}
struct A { a : u8 }
