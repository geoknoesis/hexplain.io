"""Import the LERC2 vectors written with Esri's reference implementation.

hexplain-tools codecs-image/src/test/resources/lerc/lerc2-vectors.json holds 238 blobs encoded by Esri
lerc 4.0.1 (PyPI, tests/lerc/generate_vectors.py) with the SHA-256 of lerc_decode_4D's samples
(little-endian, band after band) and the masks it returns. Each becomes a blob-layout decoding
vector; a truncation and a checksum corruption of the first version-3-or-later blob are added.
Usage: python tools/codecs/_import_lerc_vectors.py --engine d:/work/hexplain-tools
"""
import argparse
import base64
import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from vectors import step, write_suite  # noqa: E402

ESRI = {"id": "esri-lerc-4.0.1", "url": "https://github.com/Esri/lerc/tree/v4.0.1",
        "description": "Blobs encoded and decoded by Esri lerc 4.0.1 (PyPI) through hexplain-tools tests/lerc/generate_vectors.py "
                       "(codecs-image/src/test/resources/lerc/lerc2-vectors.json); the corruptions are made here.",
        "licence": "Apache-2.0 (Esri LERC); data CC0-1.0"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True)
    engine = pathlib.Path(parser.parse_args().engine)
    source = json.loads((engine / "core/src/test/resources/lerc/lerc2-vectors.json").read_text(encoding="utf-8"))["vectors"]
    vector_list = []
    for v in source:
        expect = {"sha256": v["dataSha256"]}
        if v["masks"]:
            expect["validitySha256"] = hashlib.sha256(base64.b64decode(v["masks"])).hexdigest()
        vector_list.append({"id": v["name"], "steps": [step(base64.b64decode(v["blob"]), expect)]})
    checked = next(base64.b64decode(v["blob"]) for v in source if int(v["version"]) >= 3)
    corrupted = bytearray(checked)
    corrupted[-1] ^= 0x01
    vector_list += [
        {"id": "truncated", "steps": [step(checked[:-8], {"error": "Validation"})]},
        {"id": "checksum-mismatch", "steps": [step(bytes(corrupted), {"error": "Checksum"})]},
        {"id": "tiff-layout-needs-geometry", "steps": [step(checked, {"error": "Description"}, {"layout": "tiff"})]},
    ]
    write_suite("LERC", [ESRI], vector_list)
    print(f"PASS: wrote {len(vector_list)} LERC vectors")


if __name__ == "__main__":
    main()
