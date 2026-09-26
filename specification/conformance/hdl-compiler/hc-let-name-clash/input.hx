format t @namespace "https://example.org/hc-let-name-clash#"
struct Image {
  width : u16
  let width = 2
}
