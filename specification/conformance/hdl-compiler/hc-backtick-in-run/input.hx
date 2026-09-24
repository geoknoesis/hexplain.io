format t @namespace "https://example.org/hc-backtick-in-run#"
struct Root {
  n : u8
  data : bytes[..] if `instance.n` == 1
}
