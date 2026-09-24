"""The reference implementation's stated capabilities agree with its capability statement.

The Processing Model once said the reference engine did not implement tree documents or
grouped headers for weeks after it did: an informative sentence restating a fact owned
elsewhere drifts silently. specification/reference-engine-claims.json is now the one
machine-readable statement of what the reference implementation claims (classes, optional
features, codecs, default limits); the engine's README mirrors it, which this gate cannot see.
This gate checks the specification side:

  * the informative note in processing/index.html#reference-implementation names exactly the
    claimed classes, the claimed optional features and the unclaimed ones of the file;
  * the file's optional features are exactly the Processing Model's closed list
    (#optional-features), and its classes are conformance classes the page defines;
  * the decoded codecs include the minimum codec set and are concepts of the register named;
  * the default limits are at least the minimums the Processing Model requires.
"""
import html
import json
import re
import sys
from pathlib import Path

from rdflib import Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
MINIMUM_LIMITS = {"maxInputBytes": 268435456, "maxDepth": 64, "maxTreeDepth": 256, "maxVisitedNodes": 1000000,
                  "maxMaterializedBytes": 268435456, "maxDecodedBytes": 134217728, "helNestingDepth": 512,
                  "emittedTriples": 100000}
MINIMUM_CODECS = {"Store", "Deflate", "Zlib", "Gzip", "Delta"}


def split_list(text):
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    parts = re.split(r",\s*|\s+and\s+", text)
    return {p.strip() for p in parts if p.strip()}


def main():
    claims = json.loads((ROOT / "specification/reference-engine-claims.json").read_text(encoding="utf-8"))
    page = (ROOT / "specification/processing/index.html").read_text(encoding="utf-8")
    failures = []

    def span(name):
        m = re.search(rf'<span data-claim="{name}">(.*?)</span>', page, re.S)
        if not m:
            failures.append(f"processing/index.html#reference-implementation has no data-claim=\"{name}\" span")
            return set()
        return split_list(m.group(1))

    classes = set(claims["conformanceClasses"])
    features = claims["optionalFeatures"]
    claimed = {k for k, v in features.items() if v["claimed"]}
    unclaimed = set(features) - claimed
    for name, stated, owned in [("classes", span("classes"), classes), ("features", span("features"), claimed),
                                ("unclaimed", span("unclaimed"), unclaimed)]:
        if stated != owned:
            failures.append(f"the note's {name} {sorted(stated)} differ from reference-engine-claims.json {sorted(owned)}")

    defined = set(re.findall(r"<td><dfn>([^<]+)</dfn></td>", page))
    for c in sorted(classes - defined):
        failures.append(f"claimed class '{c}' is not a conformance class of the Processing Model")
    listed = set(re.findall(r'<li data-feature="([^"]+)">', page))
    if listed != set(features):
        failures.append(f"optional features of the claims file {sorted(features)} differ from the Processing Model's "
                        f"closed list {sorted(listed)}")

    codecs = claims["codecs"]
    decoded = set(codecs["decoded"])
    for c in sorted(MINIMUM_CODECS - decoded):
        failures.append(f"the minimum codec {c} is not decoded")
    register = Graph().parse(data=(ROOT / "specification/register/media-encoding/media-encoding.ttl")
                             .read_text(encoding="utf-8"), format="turtle")
    for c in sorted(decoded):
        if not list(register.predicate_objects(URIRef(codecs["register"] + c))):
            failures.append(f"decoded codec {c} is not a concept of {codecs['register']}")

    for key, minimum in MINIMUM_LIMITS.items():
        value = claims["limits"].get(key)
        if not isinstance(value, int) or value < minimum:
            failures.append(f"default limit {key}={value} is below the Processing Model's minimum {minimum}")

    groups = set(claims["helExtensionGroups"])
    hel = (ROOT / "specification/hel/index.html").read_text(encoding="utf-8")
    for g in sorted(groups):
        if f'id="ext-{g}"' not in hel:
            failures.append(f"HEL extension group '{g}' is not defined by the HEL specification")

    index = (ROOT / "specification/index.html").read_text(encoding="utf-8")
    if "reference-engine-claims.json" not in index:
        failures.append("specification/index.html does not link the capability statement")

    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: the reference-implementation note restates reference-engine-claims.json "
          f"({len(classes)} classes, {len(claimed)} of {len(features)} optional features, {len(decoded)} codecs)")


if __name__ == "__main__":
    main()
