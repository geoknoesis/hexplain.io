# Branch and worktree integration ? 12 September 2026

All local and fetched remote **branch tips** in the four Hexplain repositories are now ancestors of local `main`. No branches or worktrees were deleted. Accountly was observed during discovery but excluded from this integration; it was not changed. Nothing was pushed.

## Integration results

| Repository | Before | Result |
| --- | --- | --- |
| hexplain.io | `main` at `7c04969`; `prerelease-current-contract` had one unmerged commit (`aa4a931`) | Merged with `ort` as `6d3e20d`, preserving the newer main changes and adding framing-review evidence. |
| hexplain-tools | `main` at `b9dbf0f`; `prerelease-current-contract` had one unmerged commit (`ef06cf9`) | Fast-forwarded to `ef06cf9`: emitted child values propagate through generated writer contexts, with recursive/counting regressions. |
| hexplain-profiles | `main` at `c43b0fd` | Already includes both GDAL branches; no merge was needed. |
| hexplain-saas | No `main`; `master` at `6605df7`, observability branch at `f503b0b` | Established `main` containing both histories. Added integration fixes in `e5fb172` and CI coverage in `538224d`. No remote is configured. |

The inventory report commit follows these integration commits. The [machine-readable inventory](2026-09-12-branch-worktree-inventory.json) retains the exact initial references, working-copy paths, dirty-file hashes and validation results.

There were **no Git merge conflicts**. Combined compilation exposed a SaaS/engine API mismatch: layout cell types can now be conditional and nullable. `ProfileDiffer` now follows both fixed and conditional cell types, dispatch-table arms and defaults when checking struct reachability. Four regressions verify that removing referenced structs is breaking while removing an unreferenced struct remains corrective.

SaaS now pins the integrated engine `ef06cf997674325c031ff1a1bcd8abfc7030640d`. CI no longer applies the historical engine patch on top of fixes already present upstream, and includes the new engine-bridge tests. The old patch is retained with an explicit historical note. Push the engine commit before a future SaaS publication so remote checkout can resolve the pin.

## Branch inventory

- **Specification:** `gdal-wave-2a`, `readiness/acceptance-20260908`, `specification-simplification` were already merged; `prerelease-current-contract` is now merged.
- **Engine:** `gdal-wave-2a`, `hardening/observability-and-engine-fixes`, `readiness/acceptance-20260908` were already merged; `prerelease-current-contract` is now merged. The hardening branch being ahead of its own remote did not represent missing work on main.
- **Profiles:** `gdal-wave-1` and `gdal-wave-2a` were already merged.
- **SaaS:** `master` and `hardening/observability` are both ancestors of the new `main`.

`origin` was fetched for the three repositories with configured GitHub remotes. Every fetched remote branch tip is also contained in its repository's main. Historical backup tags were not treated as active development branches or replayed over their rebased replacements.

## Worktree and checkout inventory

| Checkout | State / disposition |
| --- | --- |
| `D:/work/hexplain.io` | Main; existing specification/tooling edits preserved. |
| `D:/work/hexplain-simplification/hexplain.io` | Clean `prerelease-current-contract`; its tip is now merged. |
| Specification temporary `scratchpad/final` worktree under `C:/Users/steph/AppData/Local/Temp/claude/` | Clean detached `9dcb4c5`, already in main; retained. Exact path is in the JSON inventory. |
| `D:/work/hexplain-tools` | Main; existing profile fixtures, tests and documents preserved. |
| `D:/work/hexplain-simplification/hexplain-tools` | Clean `prerelease-current-contract` at the merged engine tip; retained. |
| `D:/work/hexplain-engine-acceptance-1e54ef7` | Detached old acceptance tree, with uncommitted material; inspected and retained. See below. |
| `D:/work/hexplain-profiles` | Main; existing edits and staged rename preserved. |
| `D:/work/hexplain-saas` | Switched to main without discarding its drafts. |
| `D:/work/hexplain-release-acceptance-75f118e` | Separate clean clone, not a worktree of the primary checkout. Its `75f118e` commit is already an ancestor of engine main. |

The old engine acceptance tree is not a missing feature branch. Eleven changed/untracked files are byte-identical to current equivalents. Its writer/resource variants are superseded by newer main implementations; the 112 old vector cases remain in the 136-case corpus, and layout/security corpora have expanded. Its unique `ProductionReadinessProbeTest` deliberately asserts the old defect (omitting a fixed-field terminator). It was not imported as a passing regression: current `ProductionBoundaryRegressionTest` checks explicit rejection of that unsupported combination. The old tree remains intact as evidence.

## Combined verification

| Check | Result |
| --- | --- |
| Engine `test :codegen-verify:check` | BUILD SUCCESSFUL; 3,019 passed, 8 skipped, zero failures/errors across 3,027 recorded tests. Unchanged modules used Gradle's up-to-date results. Generated Kotlin standalone compilation passed. |
| SaaS `:backend:engine:test :backend:app:test` | 75 passed, no failures/errors/skips, including four new reachability cases. |
| SaaS frontend | Type checking, all 6 component tests, and production build passed. |
| Specification strict gates | 42 passed across the initial run and targeted rechecks. Initially 40 passed and two freshness gates failed; see remediation below. |
| Profiles strict public-contract gates | All 11 passed, no skips, including 13 independent RDF validation units and negative fixtures. |

Engine skips are recorded rather than counted as passes: a parser benchmark, six declared profile fixture exclusions (comma-decimal ASCII grid and five DEM variants), and a query symlink test. The full skip names are available in the engine XML reports. This is local combined-working-copy validation, not a fresh live GDAL oracle run or remote release acceptance.

Two initial specification failures exposed stale generated metadata associated with the pre-existing tooling edits: `test_constraint_coverage` rejected the old video-test hash, and `test_review_candidate` rejected the outdated package inventory. The ledger was **fully remeasured**, producing 1,291 cases with all 1,165 components covered on both sides. The pending 201-file review package was then regenerated. Targeted strict rechecks of coverage, review candidate and page governance all passed. No independent review decision was manufactured.

Logs and XML count summaries are under `D:/work/hexplain-tools/build/merge-20260912/`; their hashes are in the JSON inventory. Initial failures are retained in `spec-initial-summary.json`, `spec-gates.log` and `saas-backend.log`; corrected results are in `spec-rechecks.log`, `coverage-regeneration.log` and `saas-backend-fixed.log`. Gradle reported successful builds; PowerShell wrappers returned 1 where native warnings were present. XML outcomes and Gradle completion are reported separately from wrapper exit status.

## Preserved uncommitted work

This operation merged branch commits; it did **not** blanket-commit existing drafts. Initial dirty-file content hashes are unchanged except for the two deliberate CI command changes in the already-dirty SaaS workflow. Those command changes were staged independently, preserving the user's other workflow edits.

The regenerated coverage JSON, review manifest and pending review ZIP remain uncommitted alongside the tooling changes they describe. Committing those generated files alone would make them inconsistent with the older committed tooling. The main checkouts therefore intentionally remain dirty. No stash, hard reset, branch deletion, worktree removal or force-push was used.
