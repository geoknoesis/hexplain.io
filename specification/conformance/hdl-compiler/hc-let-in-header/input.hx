format t @namespace "https://example.org/hc-let-in-header#"
header Hdr @record-separator 0x0A @separator 0x3D {
  samples : anum
  let twice = samples * 2
}
