"""The family's video shapes reject malformed quantities and preserve exact frame rates.

Each case is one statement about ``<urn:video>``, validated in the context of the modules its
terms belong to (video, time and what they import): those modules' triples with the case's own
are the data graph, and their shapes are the shapes graph. The whole family was once both, for
every case, which changed no verdict and took twenty times as long.
"""

from __future__ import annotations

import specgraph
from _cases import prefix_block
from pyshacl import validate
from rdflib import Graph

PREFIX = prefix_block({"v": "video", "t": "time"}, separator=" ")
BAD = [
    "v:frameRate -1",
    'v:frameRate "banana"',
    'v:aspectRatio "16:0"',
    'v:aspectRatio "0:9"',
    "t:duration -10",
    "v:frameCount -1",
    "v:frameCount 2.5",
    "v:scanType <urn:invalid>",
    "v:frameRateNumerator 30000",
    "v:frameRateNumerator 30000 ; v:frameRateDenominator 0",
]
GOOD = [
    "v:frameRate 29.97",
    'v:aspectRatio "16:9"',
    "t:duration 0",
    "v:frameCount 0",
    "v:frameRateNumerator 30000 ; v:frameRateDenominator 1001",
]


def cases() -> list[tuple[str, bool, Graph]]:
    """Every (statement, expected conformance, data graph) case, the rejections first."""
    return [
        (case, expected, Graph().parse(data=PREFIX + "<urn:video> " + case + " .", format="turtle"))
        for expected, group in [(False, BAD), (True, GOOD)]
        for case in group
    ]


def main() -> int:
    rows = cases()
    context, shapes = specgraph.context_and_shapes(specgraph.modules_used_by(*(data for _, _, data in rows)))
    for case, expected, data in rows:
        conforms, _, report = validate(context + data, shacl_graph=shapes, advanced=True)
        assert conforms == expected, (case, report)
    assert "specification/vdv/video.ttl" in specgraph.ontology_paths()
    print(f"PASS: {len(rows)} video numeric/rational cases through the family's video shapes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
