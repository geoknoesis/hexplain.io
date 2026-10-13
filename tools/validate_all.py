"""Parse every .ttl under specification/ -- the family-wide regression gate."""

from __future__ import annotations

from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    files = sorted((ROOT / "specification").rglob("*.ttl"))
    if not files:
        print("FAIL: no ttl files found under specification/")
        return 1
    failures = []
    for file in files:
        try:
            rdflib.Graph().parse(file, format="turtle")
        except Exception as error:  # noqa: BLE001 - report any parse failure
            failures.append((file.relative_to(ROOT).as_posix(), str(error)))
    if failures:
        for path, error in failures:
            print("FAIL", path, "->", error)
        return 1
    print(f"PASS: all {len(files)} ttl files parse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
