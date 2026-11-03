format t @namespace "https://example.org/hc-repeat-index-nested#"
struct Root {
  rows : Row(repeat.index) repeat 2
}
struct Row(r) {
  cells : Cell(r, repeat.index) repeat 3
}
struct Cell(r, c) {
  v : u8 @valid [self == r * 3 + c]
}
