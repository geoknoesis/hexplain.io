format t @namespace "https://example.org/hc-pipeline-and-encoded-with#"
use menc: <https://hexplain.io/ns/register/media-encoding#>
struct Root {
  a : bytes[..] @encoded-with menc:Zlib @pipeline { menc:Zlib }
}
