format t @namespace "https://example.org/hc-mint-collision-parameters#"
struct Root { r : Row(1, 2) }
struct Row(n, n) { data : bytes[1] }
