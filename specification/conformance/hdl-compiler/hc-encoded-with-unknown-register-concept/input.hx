format t @namespace "https://example.org/hc-encoded-with-unknown-register-concept#"
use menc: <https://hexplain.io/ns/register/media-encoding#>
struct Root {
  data : bytes[..] @encoded-with menc:Zlip
}
