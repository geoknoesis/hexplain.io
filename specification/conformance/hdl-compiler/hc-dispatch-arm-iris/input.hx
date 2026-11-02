format t @namespace "https://example.org/hc-dispatch-arm-iris#"
struct Root {
  kind : ascii[4]
  body : bytes[..] dispatch T on kind default Blob { "ftyp" => A  7 => B  "7" => A }
}
struct A { a : u8 }
struct B { b : u8 }
struct Blob { raw : bytes[..] }
