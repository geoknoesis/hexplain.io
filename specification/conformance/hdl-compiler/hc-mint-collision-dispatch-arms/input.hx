format t @namespace "https://example.org/hc-mint-collision-dispatch-arms#"
struct Root {
  kind : ascii[5]
  body : bytes[..] dispatch T on kind { "a b" => A  "a%20b" => B }
}
struct A { a : u8 }
struct B { b : u8 }
