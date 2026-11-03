format t @namespace "https://example.org/hc-repeat-previous-accepted#"
struct Root {
  xs : It(repeat.index == 0 ? 0 : repeat.previous.Total) repeat until repeat.index > 0 and repeat.previous.Total > 5
}
struct It(base) {
  n : u8
  Total : derive base + n
}
