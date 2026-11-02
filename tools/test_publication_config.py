"""The actual server configuration must cover every ontology/version IRI and annotation graph."""

from _family import documentation_files
from _publication import ROOT, documentation_routes, render, routes


def main() -> int:
    assert (ROOT / "deployment/publication.conf").read_text(encoding="utf-8") == render(), "Regenerate publication.conf"
    assert "/ns/fn" in routes()
    # Every module's generated annotation graph is published, as Turtle, at its own path.
    expected = {"/specification/" + doc for doc in documentation_files(ROOT / "specification").values()}
    assert set(documentation_routes()) == expected, expected ^ set(documentation_routes())
    conf = render()
    assert all(f"location = {route} {{" in conf for route in expected)
    assert not any(file in routes().values() for file in documentation_routes().values())
    print(
        f"PASS: real publication configuration covers {len(routes())} canonical/version routes and "
        f"{len(expected)} annotation-graph paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
