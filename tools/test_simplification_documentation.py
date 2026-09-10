"""The editorial overview must match its private source catalogs."""
from _build_simplification_guide import build

assert build(check=True) == 26
print("PASS: shared processing overview and all 26 preset rows match their catalogs")
