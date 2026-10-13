"""Audit the pinned documentation denominator and evidence requirements offline."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "specification/coverage/gdal-drivers.json"


def main() -> int:
    d = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rows = d["drivers"]
    keys = [r["key"] for r in rows]
    assert len(keys) == len(set(keys)) and len(keys) > 200
    counts = Counter(r["kind"] for r in rows)
    for s in d["sources"]:
        kind = s["url"].split("/")[-2]
        assert s["document_pages"] == counts[kind]
    for r in rows:
        assert "/" + d["gdal_release"] + "/" in r["source"]
        assert re.fullmatch("[0-9a-f]{64}", r["sha256"])
        assert r["assessment"] in ["not-runtime-verified", "runtime-verified"]
        if r["assessment"] == "runtime-verified":
            assert r.get("evidence"), r["key"]
            for path in r["evidence"]:
                assert (ROOT / path).is_file(), path
    assert {
        "raster:gtiff",
        "raster:nitf",
        "raster:hdf5",
        "raster:netcdf",
        "raster:zarr",
        "vector:gpkg",
        "vector:parquet",
        "vector:flatgeobuf",
    }.issubset(keys)
    # The profile library is a sibling checkout; its presence is optional.
    profiles_root = ROOT.parent / "hexplain-profiles/profiles"
    catalog = json.loads((ROOT / "specification/coverage/profile-catalog.json").read_text(encoding="utf-8"))
    entries = {p["name"]: p for p in catalog["profiles"]}
    linked = 0
    for r in rows:
        for p in r.get("profiles", []):
            assert set(p) == {"name", "iri", "verification", "scope"}, (r["key"], p)
            assert re.fullmatch("[a-z0-9-]+", p["name"]), p
            assert all(p[k] == entries[p["name"]][k] for k in ("iri", "verification", "scope")), p
            assert p["verification"] in ["parse-verified", "not-parse-verified"], p
            if profiles_root.is_dir():
                assert (profiles_root / p["name"]).is_dir(), f"{p['name']} is not a library profile"
            linked += 1
    assert linked >= 20, linked
    print(
        f"PASS: {len(rows)} uniquely keyed GDAL documentation pages ({dict(counts)}); pinned sources, evidence "
        f"policy and {linked} profile links valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
