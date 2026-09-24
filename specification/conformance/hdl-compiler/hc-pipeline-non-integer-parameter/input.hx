format t @namespace "https://example.org/hc-pipeline-non-integer-parameter#"
use menc: <https://hexplain.io/ns/register/media-encoding#>
struct Root {
  strip : bytes[..] @pipeline { menc:Delta(elementSize "one") }
}
