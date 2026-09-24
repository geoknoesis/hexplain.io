format t @namespace "https://example.org/hc-switch#"
struct Root {
  kind : ascii[4]
  body : switch kind {
    "IHDR" => A
    "PLTE" => B
  }
}
struct A { a : u8 }
struct B { b : u16 }
