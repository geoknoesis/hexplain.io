# Contributing to the specification

Use Python 3.12 (the target the hash-pinned locks are compiled for; 3.11 is the floor that
`pyproject.toml` declares and the runner asserts) with
`python -m pip install --require-hashes -r requirements.txt`. Run checks from the repository
root: `python tools/run_gates.py --strict`. Full git history is required by the register
extraction check. Filters such as `python tools/run_gates.py --strict numeric shapes` are
useful during development but are not complete release acceptance.

## Gates

Every gate is declared in `tools/gates.json` (name, class, timeout, process count); an
undeclared `tools/test_*.py` fails the run and `tools/test_gate_manifest.py`. The runner
schedules independent gates concurrently (`--jobs`, default the smaller of the CPU count and
four; `--jobs 1` streams each gate's output live), the longest recorded gate first, and buffers
each gate's output until it finishes. Three bounds hold together: the job count; a process
budget, in which a gate counts for its *effective* process count, the smaller of what it
declares and its share of the machine (`max(1, cpu // jobs)`, and never more than eight); and a
memory budget, in which a gate counts for the peak RSS recorded for it. A gate that fans out
takes its worker count from `_gate_runner.gate_workers()`, which reads `HEXPLAIN_GATE_WORKERS`;
the runner sets that variable per gate to the same effective count the budget used, and the cap
of eight applies however the count arrives. The memory budget is 80 % of the host's free
memory, read again at every scheduling decision against what the running gates hold;
`HEXPLAIN_GATE_MEMORY_MB` fixes it instead, which is what the scheduler's own tests do so that
they decide the same way on any host.

`tools/gate-costs.json` is the tracked record those estimates and that order come from: per
gate, the duration, the sampled peak RSS of its process tree and its peak process count. It is
written only by `python tools/run_gates.py --strict --record-costs`, from a complete,
unfiltered run, and merged by gate, so recording one class keeps the others;
`.gate-results/` is local state that nothing tracked reads. No timeout is chosen by hand:
`python tools/run_gates.py --derive-timeouts` writes each as ten times the recorded duration,
rounded up to five minutes, at least five minutes and at most an hour (a gate not yet recorded
gets five minutes, and runs under the hour's cap while `--record-costs` measures it for the
first time), and `tools/test_gate_manifest.py` asserts the rule for every gate. After
adding a gate, or changing what one costs, record and derive again and commit both files with
the figures under [Gate cost](#gate-cost).

A gate is a script with a `main()` and a `__main__` guard. It passes by exiting 0, fails by
exiting non-zero, and reports that it could not run (an optional dependency absent) by exiting
77: the runner reads exit status only, never the gate's stdout. The docker and browser classes
(`tools/_check_local_publication.py`, `tools/_check_site_browser.py`) run through the same
runner in the site workflow with `--class docker` and `--class browser`. `pytest tools` runs
the offline gates of `tools/gates.json`, each under its declared timeout, through
`tools/conftest.py` (with `-n auto` when pytest-xdist is installed); neither pytest nor xdist is
in the hash-pinned requirements, and the runner remains the acceptance command.

The family graph is cached as a pickle under `.gate-results/family-cache/`, keyed on the
runner's source manifest digest (or, outside the runner, on the family files' own digest); a
stale key falls back to parsing, and each write keeps the three newest pickles and removes
temporary files an interrupted write left. Delete the directory if in doubt.

A gate that validates small cases does not load the family for each of them.
`specgraph.modules_used_by(case)` names the modules a case involves -- the homes of its terms,
every module with a shape aimed at a class, property or node the case states, and what those
import -- and `specgraph.shapes_of(...)` loads just those as data context and as shapes
(`tools/_module_selection.py` states the rule, `tools/test_specgraph.py` checks it against
every target in the family). pySHACL pays for every shape, and every SPARQL constraint for
every triple, on every call: against the whole family a ten-triple case costs seconds.

## Gate cost

What the suite costs is measured, and the measurement is tracked: `tools/gate-costs.json` holds
every gate's duration, sampled peak RSS and process count. The table is that record's offline
run, row for row; `python tools/_gate_cost.py --note` prints the rows, and
`tools/test_gate_manifest.py` fails when this section and the record differ, so a new recording
is committed together with its figures here.

| | |
|---|---|
| Recorded (UTC) | 2026-10-13T18:50:13 |
| Host | Windows-10-10.0.26200-SP0; 20 logical CPUs; 32428 MiB; Python 3.11.4 |
| Host load when the run began | 30.2 % of the CPUs already busy; 1849 MiB free |
| Gates run, at `--jobs` | 81, at 4 |
| Wall clock | 307.4 s |
| Sum of the gates' durations | 1205.3 s |

The command was `python tools/run_gates.py --strict --record-costs` at the default job count.
The reference it is compared with is the sequential strict run of 2026-09-28 on the same host:
724 s for the 75 gates of that day, one after another. Two rows of the table qualify the
comparison. The host was not idle -- the load row says how busy it already was when the run
began, and other builds ran throughout -- so every duration is longer than the gate takes
alone; and the sum of the durations is therefore what running the gates one after another
would have taken under that same load, not on a quiet machine.
The other two classes were recorded on the same host with `--class`: the docker class on
2026-10-13 (`_check_local_publication`, 152.6 s) and the browser class on 2026-10-13
(`_check_site_browser`, 26.3 s).

Because of that load the per-gate durations of the record cannot be set beside those of
2026-09-28. The five gates the review of 2026-10-13 named were therefore each run alone, twice
on the same day on the same loaded host: as they were when they validated every case against
the whole family, and as they are now (the pySHACL outcome of every case is the same in both).

| Gate | Whole family per case | Modules the case involves | In the record (beside three other gates) |
|---|---|---|---|
| `test_conformance_competency` | 799.5 s | 66.7 s | 44.4 s; 79.6 MiB, 2 processes |
| `test_vocab_shapes` | 941.1 s | 232.8 s | 162.0 s; 973.9 MiB, 7 processes |
| `test_video_math` | 315.1 s | 57.3 s | 31.2 s; 72.9 MiB, 1 processes |
| `test_packaging_contract` | 255.5 s | 44.0 s | 23.6 s; 69.3 MiB, 1 processes |
| `test_numeric_boundaries` | 225.9 s | 3.2 s | 3.7 s; 59.9 MiB, 1 processes |

Python 3.12, the target the locks are compiled for, is exercised on the same host as well. On
2026-10-13 `python tools/run_gates.py --strict` under CPython 3.12.12, in an environment
installed from `requirements.txt` with `--require-hashes`, passed all 81 offline gates -- lint,
formatting and the type gate among them -- in 342.4 s of wall clock at four jobs, with 69.5 % of
the CPUs already busy when it began. The record above is from the host's own CPython 3.11.4,
the declared floor.

## Style

`ruff.toml` is the lint and formatting contract (120 columns; E, W, F, B, UP, SIM, I, ANN and
C901 with a complexity bound of 15: a function with more decision points is split);
`python -m ruff format tools && python -m ruff check tools --fix` before committing, and
`tools/test_lint.py` enforces both. Every function is annotated, and `python -m mypy tools`
(the `[tool.mypy]` section of `pyproject.toml`: untyped definitions disallowed, bodies checked,
no implicit `Optional`) is run by `tools/test_types.py`. `Any` is for parsed JSON and for values
from untyped dependencies; as a return type it is counted, and the count is held under a
ceiling. Write files with `newline="\n"` (`tools/test_lint.py` rejects a text write that leaves
the line ending to the platform) and resolve paths from the module's `ROOT`, never from the
working directory.

Every module under `tools/`, the conformance suite (`tools/conformance/`) and the codec vector
tooling (`tools/codecs/`) included, is formatted, linted and type-checked alike, with no
exemption: `ruff.toml` has no per-file entries (`tools/test_lint.py` fails on one), every mypy
finding fails `tools/test_types.py`, and every text write states its line ending. The case
modules hold Turtle, HDL and HTML whose bytes are published, so a data line that would exceed
120 columns is continued rather than rewrapped: a single-line literal is split into adjacent
literals, and a line inside a triple-quoted string ends in a backslash, which joins it to the
next line without changing the string. After touching a case module, confirm with
`python tools/conformance/generate_inputs.py --check` that the suite on disk is unchanged.

## Authoring

Edit shared constraint authoring where a canonical RDF module is generated. Regenerate the
affected module and documentation using its existing builder. Keep `specification/family.json`
complete when adding a vocabulary; coordinate the identical discovery contract with profiles.

A canonical module holds only what its author wrote. Generated labels, definitions and scope
notes are written by `python tools/_build_term_reference.py --enrich` to the module's sibling
annotation graph, `<module>-doc.ttl`, which `family.json` lists under `files` and maps under
`documentation`; never edit one by hand, and never paste generated prose into a canonical file.
State each new term's `rdfs:isDefinedBy` where you declare it: the generator refuses a term
without one. Every module's `owl:Ontology` names its annotation graph with `rdfs:seeAlso`. A
register is the exception to generated definitions: each `skos:Concept` states its own
`skos:definition`, and each codec parameter spec an `rdfs:comment` saying what it means, in the
register file (`tools/test_documentation_annotations.py`).

The builders, in the order a change to a shape needs them (each has a check mode a gate runs):

| Builder | Writes | Check |
|---|---|---|
| `tools/_expand_specification_patterns.py --write` | the templated canonical modules | default mode |
| `tools/_build_authoring_inventory.py` | `authoring/specification/constraint-inventory.json` | `test_specification_patterns.py` |
| `tools/_build_term_reference.py --enrich` | every `<module>-doc.ttl` and the term reference pages | `--check` |
| `tools/_build_shape_requirements.py --write` | `specification/req/requirements.ttl`, one `reqs:ShapeRequirement` per node shape | `--check` (default), `test_shape_requirements.py` |
| `tools/_build_term_reference.py --enrich` (again) | `requirements-doc.ttl` and the req page | `--check` |
| `tools/_build_architecture_catalogue.py` | the aspect catalogue cells of the architecture page | `--check` |

A fixture under `specification/**/test/` is valid when validation reports no `sh:Violation`;
`# expect:` lines name each result it must produce, with `sh:Warning` or `sh:Info` as a last
token for an advisory one (`tools/test_vocab_shapes.py`).
Add positive and negative semantic cases, including activation, result path and numeric edges.
Regenerate changed evidence rather than weakening freshness or coverage assertions.

Authored validation cases live in the `tools/_*_cases.py` libraries and share `tools/_cases.py`
(`row()`, `Case`, `PREFIXES`). A retained file generated from authored cases or from the family
is written by a builder, never by the gate that checks it: `python tools/_build_<name>.py
--write` regenerates it, `--check` reports whether it is current, and the gate only checks and
takes no arguments. The builders are `_build_family_contracts` (`family-contracts.json`);
`_build_layout_competency`, `_build_conformance_competency`, `_build_security_competency` and
`_build_network_competency` (those `*-competency.tsv` corpora; each builder holds its cases); `_build_strict_profile` (`strict-profile-shapes.ttl`); `_build_fn_catalogue` (the
catalogue section of `specification/fn/index.html`); and `_build_lineage`
(`releases/lineage.json`, after a snapshot or a new version IRI). After changing cases run
`python tools/_build_family_contracts.py --write` and the builder of each corpus that changed
(`python tools/_build_layout_competency.py --write` for the layout fragments), then `python
tools/_constraint_coverage.py`, `python tools/_render_constraint_coverage.py` and `python
tools/_capabilities.py`, because the coverage ledger hashes the snapshots and the procedural
gates, and `python tools/_competency_trace.py`, whose traceability matrix hashes the corpora. The ledger is measured across a process pool, corpus by corpus (about eight
minutes for the 2,163 validation calls at eight workers on the recording host under the load
stated under [Gate cost](#gate-cost), where the sequential whole-family measurement took forty);
its content does not depend on the number of workers. The GDAL evidence gates derive their
expected totals from the evidence's own counts blocks; do not retype totals.

Public documentation links are checked by `test_site_links.py`. Run `python
tools/_site_inventory.py` after adding pages; it also links the shared print stylesheet.
Namespace routes are generated by `python tools/_publication.py`; use `python
tools/_check_local_publication.py` to test the actual pinned Nginx image locally (it mounts only
`specification/`, `releases/` and the published root files). Refresh published profile metadata
with `python tools/_sync_profile_catalog.py` after a reviewed profile catalog update. This
copies metadata, not a third set of vocabularies.

After the source and offline checks are complete, rebuild the pending review package with
`python tools/_review_candidate.py`. The archive itself is not tracked: `review-manifest.json`
pins its hash and every entry's hash, `python tools/_review_candidate.py --archive-only`
rebuilds it from the tree, and the validate workflow retains it as an artifact. Do not record
yourself as an independent reviewer of your own implementation. Preserve existing attributable
decisions and obtain a new review for changed artifacts. See
`specification/ontology-review/review-instructions.md`.

`specification/validation/constraint-coverage.json` is retained as text, because the review
package, the coverage page and `test_constraint_coverage.py` read and hash it and the site
serves it as the page's linked source, but compactly: one JSON document with the header on its
first line and one obligation per line, each obligation's cases given as indices into the
header's `case_names` (2.2 MB; the indented form with every name spelled out was 16.5 MB);
`_constraint_coverage.read_ledger()` returns it with the names in place.
`constraint-coverage.html` stays tracked as well: the site is served from the tree as it is
committed (Nginx mounts `specification/`, and there is no build step between a commit and what
is published), so a page that was only rendered at publish time would not exist. `python
tools/_render_constraint_coverage.py` renders it from the ledger; it holds the case names once
and fills a row's list when the row is opened (2.6 MB, from 14.6 MB), and
`test_constraint_coverage.py` fails when the page is not the ledger rendered.

No live publication is implied by these local operations. `tools/check_live_publication.py`
writes its record under `specification/evidence/<date>/`. See `LICENSING.md` for artifact
ownership and license declarations.
