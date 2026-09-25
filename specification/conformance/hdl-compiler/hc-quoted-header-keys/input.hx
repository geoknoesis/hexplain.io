format t @namespace "https://example.org/hc-quoted-header-keys#"
header H @record-separator 0x0A @separator 0x3D @trim {
  "samples" as n : anum
  "byte order" as order : anum
  "bands" : anum
  lines : anum if n > 0
}
