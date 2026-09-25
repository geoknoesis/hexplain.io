format t @namespace "https://example.org/hc-prop-values#"
use ex: <https://example.org/hc-prop-values#>
struct Root {
  a : u8 @prop rdfs:comment "a note" @prop ex:rank 3 @prop ex:kind ex:Primary
}
