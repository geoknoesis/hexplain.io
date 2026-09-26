format t @namespace "https://example.org/hc-param-recursion#"
struct Root {
  levels : u8
  tree : Node(levels)
}
struct Node(depth: int) {
  v : u8
  child : Node(depth - 1) if depth > 1
}
