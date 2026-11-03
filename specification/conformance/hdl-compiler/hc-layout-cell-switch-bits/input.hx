format t @namespace "https://example.org/hc-layout-cell-switch-bits#"
struct Root {
  n : u8
  pixels : bytes[..] layout { cell switch { when n == 1 => u8  when n == 2 => bits[4] } dim axis X size 4 }
}
