format t @namespace "https://example.org/hc-let-forward-reference#"
struct Image {
  width : u16
  pixels : bytes[area]
  let area = width * 2
}
