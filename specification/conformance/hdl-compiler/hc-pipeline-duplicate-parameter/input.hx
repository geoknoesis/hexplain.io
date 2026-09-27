format t @namespace "https://example.org/hc-pipeline-duplicate-parameter#"
use menc: <https://hexplain.io/ns/register/media-encoding#>
struct Root {
  strip : bytes[..] @pipeline { menc:Delta(elementSize 1, elementSize 2) }
}
