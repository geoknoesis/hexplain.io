format t @namespace "https://example.org/hc-semantic-mapping#"
use ex: <https://example.org/hc-semantic-mapping#>
struct Root means ex:Reading {
  raw : i16 means ex:celsius value raw * 0.5 @datatype xsd:double
}
