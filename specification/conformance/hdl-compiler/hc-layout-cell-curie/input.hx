format t @namespace "https://example.org/hc-layout-cell-curie#"
use t: <https://example.org/types#>
struct Image {
  pixels : bytes[..] layout cell t:half { dim axis X size 4 }
}
