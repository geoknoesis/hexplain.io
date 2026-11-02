# Hexplain specification

Canonical RDF vocabularies, SHACL constraints, HDL/HEL documentation, generated references,
and the public site. Format profiles live in the separate `hexplain-profiles` repository.

```
python -m pip install --require-hashes -r requirements.txt
python tools/run_gates.py --strict
```

Python 3.12 is the target (3.11 is the floor). The runner takes its gate list from
`tools/gates.json`, schedules independent gates concurrently within process and memory
budgets (`--jobs`, default the smaller of the CPU count and four) from the tracked cost record
`tools/gate-costs.json`, limits each gate by a timeout derived from that record, and writes the
run's own record to `.gate-results/summary.json` (local state; nothing tracked reads it). A gate
reports PASS, SKIP or FAIL by its exit status (0, 77,
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

The processor conformance runner (`tools/conformance/run_suite.py`) requires exit zero for
successful output and a nonzero exit for processing errors. Writing both output and error
artifacts fails the case. Each invocation has a timeout and a combined stdout/stderr limit
of 1,000,000 characters; exceeding either fails the case and terminates the process tree.
Malformed processor artifacts and launch failures are recorded per case so subsequent cases
and the final implementation report are retained. Compiler diagnostics are read from stderr.
CI runs the offline gates on Python 3.11 and 3.12 on both Windows and Linux.

Implementation reports require a complete run: `--case` cannot be combined with `--json`.
A claimed, applicable case without its processor command fails. Report validation uses the
same applicability rules and checks digest syntax, case totals and duplicate case IDs for
both current and historical reports. `--check-report` requires the matching suite (use
`--suite` for an older checkout); archive retention checks of superseded reports verify
structure only, and do not certify historical coverage.

The review archive includes the conformance generators, runner, test cases and their data.
After installing its locked dependencies, an extracted copy supports
`python tools/test_conformance_suite.py` and `python tools/test_implementation_reports.py`.
The review-candidate gate runs both commands from an isolated extraction. The archive is a
scoped semantic review package; full-repository acceptance uses a checkout of this repository.

Report metadata is validated before processor execution, and complete reports are validated
again before writing. Reports require a nonempty runner identity and a valid ISO 8601 UTC
run timestamp. New reports and `report.py --complete` use atomic replacement; invalid
metadata, invalid report contents or a failed replacement preserve the existing file.
Completion accepts `--suite` to select the matching suite for validation.

The conformance comparator distinguishes error artifacts from successful parsed trees.
Alternative errors require an explicit valid `orError` category; absent or null categories
never satisfy that alternative. JSON and RDF evaluator alternatives both honor category maps.

The runner checks required error outcomes against the process status and designated artifact,
not only their contents. Round-trip exemptions are scoped field paths with proved encoding
dependencies and preserve tree shape and value types. Dynamic dependencies the analyzer cannot
prove remain compared normally. Gate evidence includes configuration and binary inputs;
runtime caches and explicitly selected result files are excluded from source-change checks.

Processor conformance runs limit each output/error/base artifact to 16 MiB before reading it.
Parsing and comparison run in a disposable process with a separate `--timeout` deadline
(the same duration used for each processor invocation). Oversized artifacts and comparison
timeouts fail the case and preserve the remaining run. These are harness limits; they do
not impose limits on conforming implementations.

Capability schema 2 reports the authored family-contract corpus separately from competency
TSV references. Every documented module publishing shapes has both positive and negative
authored cases; modules without shapes retain their vocabulary/register checks. Resource
references aid review and do not certify complete semantic coverage. The review package
contains the current evidence and all 39 module rows; independent acceptance remains pending.

The complete registered-construct inventory is
`specification/validation/construct-coverage.json`, regenerated by
`python tools/_specification_coverage.py` and checked by the capability gate. It accounts
for every live normative clause, measured SHACL obligation and documented declaration.
Evidence kinds remain separate; clauses requiring semantic or implementation inspection
are visible and are not represented as tested. Repeated-record round-trip dependencies
are resolved per array element, and diagnostic assertions match one validation result.

The function catalogue gate executes all six pure SPARQL function bodies with 55 boundary
and failure probes. Native functions require the external reference runtime; their declaration
checks are not runtime certification. The construct inventory keeps explicit inspection-only
exceptions and fails if a new normative clause has neither a test nor an audited disposition.
