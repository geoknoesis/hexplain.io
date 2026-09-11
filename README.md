# Hexplain specification

Canonical RDF vocabularies, SHACL constraints, HDL/HEL documentation, generated references,
and the public site. Format profiles live in the separate `hexplain-profiles` repository.

```
python -m pip install -r requirements.txt
python tools/run_gates.py --strict
```

The runner streams progress, limits each gate, and records `.gate-results/summary.json`.
`specification/family.json` is the complete ontology/shape inventory. Missing and unlisted
modules are errors, including for profile consumers. See [CONTRIBUTING.md](CONTRIBUTING.md).

This is a prerelease specification. The independent review package is reproducible, but
independent reviewer acceptance remains distinct from automated tests. Historical archive
hashes are checked; backwards compatibility with every draft is not promised.

The intended public origin is `https://hexplain.io`. Local routing can be tested with
`python tools/_check_local_publication.py` using Docker. This command starts a disposable
localhost-only Nginx container; it does not deploy the site. Live deployment remains deferred.

For browser acceptance, install `python -m pip install -r requirements-browser.txt`, then
`python -m playwright install chromium` and run `python tools/_check_site_browser.py`.
The dedicated site workflow provisions Chromium's Linux system dependencies and retains
browser screenshots and local publication results.

License declarations and unresolved artifact-class licensing are described in [LICENSING.md](LICENSING.md).
