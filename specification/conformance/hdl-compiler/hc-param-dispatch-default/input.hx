format t @namespace "https://example.org/hc-param-dispatch-default#"
struct Root {
  kind : u8
  body : bytes[..] dispatch Bodies on kind default Blob { 1 => Plain }
}
struct Blob(size) { data : bytes[size] }
struct Plain { v : u8 }
