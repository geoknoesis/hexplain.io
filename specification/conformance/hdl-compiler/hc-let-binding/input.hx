format t @namespace "https://example.org/hc-let-binding#"
struct Image {
  width : u16
  height : u16
  let area = width * height
  pixels : bytes[area]
}
