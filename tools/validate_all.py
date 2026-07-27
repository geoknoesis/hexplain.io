"""Parse every .ttl under specification/ — the family-wide regression gate."""
import glob
import sys
import rdflib

failures = []
files = sorted(glob.glob("specification/**/*.ttl", recursive=True))
if not files:
    sys.exit("FAIL: no ttl files found (wrong working directory?)")
for f in files:
    try:
        rdflib.Graph().parse(f, format="turtle")
    except Exception as e:  # noqa: BLE001 — report any parse failure
        failures.append((f, str(e)))

if failures:
    for f, e in failures:
        print("FAIL", f, "->", e)
    sys.exit(1)
print(f"PASS: all {len(files)} ttl files parse")
