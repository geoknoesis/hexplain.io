"""Every executable codec has a well-formed contract and a normative vector suite of the same version.

A register concept is executable when it carries hexplain:codecContract. For each one:
  * the media-encoding register conforms to the family's contract shapes;
  * specification/codecs/<LocalName>/vectors/manifest.json exists, names the concept, and its
    suiteVersion equals the contract's hexplain:vectorSuiteVersion;
  * every source records its provenance (description) and licence, every vector names a source,
    every input file exists, and every step's parameters obey the contract unless the step
    expects a Description error;
  * the suite has at least one decoding vector that succeeds.
No suite may exist for a concept without a contract. Finally the runner is proven end to end:
tools/codecs/_python_reference.py (Store, Deflate, Zlib, Gzip in plain Python) passes those four
suites through tools/codecs/run_vectors.py.
"""
import pathlib
import subprocess
import sys

from pyshacl import validate
from rdflib import Graph

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "codecs"))
sys.path.insert(0, str(ROOT / "tools"))

import specgraph  # noqa: E402
import vectors  # noqa: E402

REGISTER = ROOT / "specification/register/media-encoding/media-encoding.ttl"


def main():
    failures = []
    register = Graph().parse(data=REGISTER.read_text(encoding="utf-8"), format="turtle")
    conforms, _, report = validate(specgraph.ontologies(), shacl_graph=specgraph.shapes(), inference="none",
                                   allow_warnings=True)
    if not conforms:
        failures.append("the specification family, media-encoding register included, does not conform:\n" + report)
    contracts = vectors.contracts(register)
    if not contracts:
        failures.append("no register concept carries hexplain:codecContract")
    for iri, contract in sorted(contracts.items()):
        path = vectors.suite_path(iri)
        if not path.is_file():
            failures.append(f"{iri}: no vector suite at {path.relative_to(ROOT)}")
            continue
        manifest = vectors.load(path)
        failures += [f"{path.relative_to(ROOT)}: {p}" for p in vectors.problems(manifest, contract, path.parent)]
    suites = {p.parent.parent.name for p in (ROOT / "specification/codecs").glob("*/vectors/manifest.json")}
    for name in sorted(suites - {vectors.local_name(iri) for iri in contracts}):
        failures.append(f"specification/codecs/{name} has a vector suite but no register concept with a contract")
    python = pathlib.Path(sys.executable).as_posix()
    script = (ROOT / "tools/codecs/_python_reference.py").as_posix()
    reference = f'"{python}" "{script}" vector --manifest {{manifest}} --id {{id}}'
    run = subprocess.run([sys.executable, str(ROOT / "tools/codecs/run_vectors.py"), "--command", reference,
                          "--codec", "Store", "--codec", "Deflate", "--codec", "Zlib", "--codec", "Gzip"],
                         capture_output=True, text=True)
    if run.returncode != 0:
        failures.append("the Python reference does not pass the minimum-set suites:\n" + run.stdout + run.stderr)
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"PASS: {len(contracts)} executable codecs have a contract and a vector suite; the runner passes "
          f"the Python reference")


if __name__ == "__main__":
    main()
