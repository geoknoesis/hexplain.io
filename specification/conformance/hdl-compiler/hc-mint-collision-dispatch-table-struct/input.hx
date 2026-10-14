format t @namespace "https://example.org/hc-mint-collision-dispatch-table-struct#"
struct Root {
  kind : u8
  body : bytes[..] dispatch Blob on kind { 1 => A }
}
struct A { a : u8 }
struct Blob { raw : bytes[..] }
