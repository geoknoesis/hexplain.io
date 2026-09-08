# Specification gate checkout contract

Public specification CI checks out this repository with full history because test_register_extraction reads a pinned pre-migration commit. All public gates operate on public data; no private repository token is required. test_gdal_runtime verifies retained corpus counts, contract metadata and hash syntax, and explicitly does not claim current implementation-byte verification.

Private engine release acceptance separately checks out the public specification at the full SHA in its workflow, then runs tests/release/verify_spec_evidence.py. That check verifies all fourteen proprietary implementation hashes and the companion-evidence disclaimer. The split preserves source-byte acceptance without making public PR execution depend on private credentials. A change to the pinned public revision requires reviewing evidence compatibility.

Live publication is deferred by user instruction and excluded from scoring. Local routing configuration under deployment/ is a draft only; no live origin or DNS was changed. Remote CI acceptance still requires a successful run against the final committed candidate.
