format t @namespace "https://example.org/hc-mint-collision-asset-bundle#"
bundle Tiles @bound-by naming-convention {
  part ".dat" role Payload required primary
}
asset Tiles conforms Tiles {
  part data role Payload
}
