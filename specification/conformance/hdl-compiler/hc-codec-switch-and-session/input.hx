format t @namespace "https://example.org/hc-codec-switch-and-session#"
use menc: <https://hexplain.io/ns/register/media-encoding#>
struct Root {
  compression : u16
  n : u16
  strip : bytes[..] @codec switch compression { 1 => menc:Store, 8 => menc:Zlib(level: n) } @codec-session layout
}
