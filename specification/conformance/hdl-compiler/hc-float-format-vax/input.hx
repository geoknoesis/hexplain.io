format t @namespace "https://example.org/hc-float-format-vax#"
struct Root {
  f : f32 @prop bddo:floatFormat bddo:vaxF
  d : f64 @prop bddo:floatFormat bddo:vaxD
  g : f64 @prop bddo:floatFormat bddo:vaxG
}
