format t @namespace "https://example.org/hc-quoted-key-without-alias#"
header H @record-separator 0x0A @separator 0x3D {
  "samples" : anum
  lines : anum if samples > 0
}
