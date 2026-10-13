# Hexplain specification

Canonical RDF vocabularies, SHACL constraints, HDL/HEL documentation, generated references,
and the public site. Format profiles live in the separate `hexplain-profiles` repository.

```
python -m pip install --require-hashes -r requirements.txt
python tools/run_gates.py --strict
```

Python 3.12 is the target (3.11 is the floor). The runner takes its gate list from
`tools/gates.json`, schedules independent gates concurrently within a memory budget
(`--jobs`, default the smaller of the CPU count and four), limits each gate, and records
`.gate-results/summary.json`. A gate reports PASS, SKIP or FAIL by its exit status (0, 77,
other). `specification/family.json` is the complete ontology/shape inventory. Missing and
unlisted modules are errors, including for profile consumers. Each module has a generated annotation
graph beside it (`<module>-doc.ttl`: labels, definitions and scope notes), listed there too. See
[CONTRIBUTING.md](CONTRIBUTING.md).

This is a prerelease specification. The independent review package is reproducible, but
independent reviewer acceptance remains distinct from automated tests. Historical archive
hashes are checked; backwards compatibility with every draft is not promised. The review
archive is rebuilt from the tree (`python tools/_review_candidate.py --archive-only`) and
pinned by the tracked `review-manifest.json` rather than tracked itself.

The intended public origin is `https://hexplain.io`. Local routing can be tested with
`python tools/run_gates.py --strict --class docker` using Docker. This starts a disposable
localhost-only Nginx container serving only `specification/`, `releases/` and the root pages;
it does not deploy the site. Live deployment remains deferred.

For browser acceptance, install `python -m pip install --require-hashes -r requirements-browser.txt`,
then `python -m playwright install chromium` (the pinned Playwright fetches its own Chromium
build) and run `python tools/run_gates.py --strict --class browser`.
The dedicated site workflow provisions Chromium's Linux system dependencies and retains
browser screenshots and local publication results.

The `requirements*.txt` files are hash-pinned locks compiled from `requirements*.in`; edit the
`.in` pins and regenerate the locks with the `uv pip compile` command in their headers.

License declarations and unresolved artifact-class licensing are described in [LICENSING.md](LICENSING.md).
