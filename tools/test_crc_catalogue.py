"""Every named CRC of BDDO means what its parameters say.

A named CRC individual (bddo:crc16, bddo:crc32c, ...) states its six Rocksoft parameters and its
catalogue check value, the CRC of the ASCII bytes "123456789". This gate recomputes each check
value from the stated parameters, bit by bit, and compares it with the stated one and with the CRC
catalogue values the conformance suite is generated from (tools/conformance/crc.py), so a
transposed polynomial or a flipped reflection flag cannot stand in the ontology unnoticed. It also
checks the model itself against zlib's CRC-32 and that every named CRC is listed.
"""
import sys
import zlib
from pathlib import Path

from rdflib import RDF, Literal, Namespace

import specgraph

sys.path.insert(0, str(Path(__file__).resolve().parent / "conformance"))
import crc  # noqa: E402

BDDO = Namespace("https://hexplain.io/ns/bddo#")
PARAMETERS = ("crcWidth", "crcPolynomial", "crcInit", "crcReflectIn", "crcReflectOut", "crcXorOut", "crcCheck")


def main():
    failures = []
    # The model is the one zlib implements for CRC-32/ISO-HDLC.
    for sample in (b"", b"123456789", bytes(range(256))):
        if crc.named("crc32", sample) != zlib.crc32(sample):
            failures.append(f"the Rocksoft model disagrees with zlib's CRC-32 on {sample[:12]!r}")
    g = specgraph.ontologies()
    stated = {}
    for alg in g.subjects(RDF.type, BDDO.ChecksumAlgorithm):
        values = {p: g.value(alg, BDDO[p]) for p in PARAMETERS}
        if all(v is None for v in values.values()):
            continue
        name = str(alg).split("#")[-1]
        missing = [p for p, v in values.items() if v is None]
        if missing:
            failures.append(f"bddo:{name} states some CRC parameters but not {missing}")
            continue
        if any(not isinstance(v, Literal) for v in values.values()):
            failures.append(f"bddo:{name}: a CRC parameter is not a literal")
            continue
        width, poly, init, refin, refout, xorout, check = (values[p].toPython() for p in PARAMETERS)
        try:
            computed = crc.crc(crc.CHECK_INPUT, width, poly, init, refin, refout, xorout)
        except ValueError as exc:
            failures.append(f"bddo:{name}: {exc}")
            continue
        if computed != check:
            failures.append(f"bddo:{name}: its parameters give check value {computed:#x}, it states {check:#x}")
        stated[name] = (width, poly, init, refin, refout, xorout, check)
    for name, row in crc.NAMED.items():
        if name not in stated:
            failures.append(f"bddo:{name} ({row[1]}) is not a ChecksumAlgorithm with CRC parameters")
        elif stated[name] != tuple(row[2:]):
            failures.append(f"bddo:{name} states {stated[name]}, the catalogue gives {tuple(row[2:])}")
    for name in sorted(set(stated) - set(crc.NAMED)):
        failures.append(f"bddo:{name} is a CRC the catalogue table of tools/conformance/crc.py does not list")
    if failures:
        print("FAIL:\n  " + "\n  ".join(failures))
        return 1
    print(f"PASS: {len(stated)} named CRCs: every stated check value follows from the stated parameters "
          "and matches the CRC catalogue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
