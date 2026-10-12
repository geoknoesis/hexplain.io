format t @namespace "https://example.org/hc-encoded-with-catalogue-codec#"
struct Root {
  data : bytes[..] @encoded-with menc:BZip2
}
