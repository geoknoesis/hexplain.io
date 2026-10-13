format t @namespace "https://example.org/hc-shared-namespace-two-modules#"
import "lib/one.hx" as one
import "lib/two.hx" as two
struct Root { a : one:A  b : two:B }
