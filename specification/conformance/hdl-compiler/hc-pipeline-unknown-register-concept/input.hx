format t @namespace "https://example.org/hc-pipeline-unknown-register-concept#"
use menc: <https://hexplain.io/ns/register/media-encoding#>
struct Root {
  data : bytes[..] @pipeline { menc:Delta(elementSize 1), menc:Deflat }
}
