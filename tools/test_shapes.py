"""Execute the bundle's SHACL (structural shapes + rule + conformance) against the
shapefile fixtures using a real engine. Optional formal gate: if pyshacl is not
installed, SKIP (exit 77, the runner's skip status) so the rdflib-only suite stays green; where pyshacl is
present this genuinely runs AssetShape, PartShape (incl. register membership),
and RequiredPartsShape.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        from pyshacl import validate
    except ImportError:
        print("SKIP: pyshacl not installed (optional formal SHACL gate)")
        return 77  # The runner's SKIP status (tools/_gate_runner.SKIP_EXIT).
    import rdflib

    BUNDLE = "specification/aspect/bundle/bundle.ttl"
    # core.ttl supplies hexplain:RegisterBindingShape, the generic SHACL-SPARQL shape that
    # enforces every hexplain:usesRegister declaration (e.g. the shapefile profile's
    # abnd:partRole -> rpr:PartRoleScheme binding) -- it must be in the shapes graph too.
    SHAPES = [BUNDLE, "specification/hexplain/core.ttl"]
    BASE = [
        "specification/aspect/bundle/example/grid-pair-profile.ttl",
        BUNDLE,
        "specification/aspect/geometry/geometry.ttl",
        "specification/aspect/spatialref/spatialref.ttl",
        "specification/aspect/tabular/tabular.ttl",
        "specification/aspect/fsmeta/fsmeta.ttl",
        # Registers: the concepts the fixtures reference (rpr:GeometryCarrier etc.,
        # rgeo:MultiLineString) were extracted out of their aspects into these standalone
        # register documents; load them so partRole/geometryType values resolve.
        "specification/register/part-role/part-role.ttl",
        "specification/register/geometry-type/geometry-type.ttl",
    ]

    def conforms(instance: str) -> tuple[bool, str]:
        data = rdflib.Graph()
        for f in BASE + [instance]:
            data.parse(ROOT / f, format="turtle")
        shapes = rdflib.Graph()
        for f in SHAPES:
            shapes.parse(ROOT / f, format="turtle")
        ok, _, text = validate(data, shacl_graph=shapes, advanced=True)
        return ok, text

    valid_ok, valid_text = conforms("specification/aspect/bundle/example/bundle-example.ttl")
    invalid_ok, _ = conforms("specification/aspect/bundle/example/bundle-example-invalid.ttl")

    problems = []
    if not valid_ok:
        problems.append("valid example.ttl did NOT conform:\n" + valid_text)
    if invalid_ok:
        problems.append("invalid example-invalid.ttl unexpectedly conformed (required-parts not enforced)")

    if problems:
        print("FAIL:\n" + "\n".join(problems))
        return 1
    print("PASS: valid fixture conforms; invalid fixture fails SHACL (structural + required-parts executed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
