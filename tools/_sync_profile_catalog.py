"""Refresh public profile metadata from the canonical library, without copying vocabularies."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent/"hexplain-profiles/catalog.json"
catalog = json.loads(source.read_text(encoding="utf-8"))
entries = {p["name"]:p for p in catalog["profiles"]}
target = ROOT/"specification/coverage/profile-catalog.json"
target.write_text(json.dumps(catalog, indent=2)+"\n", encoding="utf-8")
inventory = ROOT/"specification/coverage/gdal-drivers.json"
data = json.loads(inventory.read_text(encoding="utf-8"))
for driver in data["drivers"]:
    for link in driver.get("profiles", []):
        profile = entries[link["name"]]
        link.update(iri=profile["iri"], verification=profile["verification"], scope=profile["scope"])
inventory.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
print(f"Synchronized {len(entries)} canonical profile identities and scopes")
