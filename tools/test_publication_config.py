"""The actual server configuration must cover every ontology/version IRI."""
from _publication import ROOT, render, routes
assert (ROOT/"deployment/publication.conf").read_text(encoding="utf-8") == render(), "Regenerate publication.conf"
assert "/ns/fn" in routes()
print(f"PASS: real publication configuration covers {len(routes())} canonical/version routes")
