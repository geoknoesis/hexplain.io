# Initial pipeline performance baseline

Three JVM forks, 100 warmup operations and 200 measured samples per workload: 6,600 timed operations across 11 workloads. Java 17, fixed 512 MiB heap, one active JVM processor. These are synthetic diagnostic measurements, not production SLOs.

| Workload | Per-fork p50 range (microseconds) | Median thread allocation range (bytes) |
|---|---:|---:|
| compile-loaded-profile | 8060.0?12957.8 | 2,607,304?2,627,156 |
| parse-scalar | 20.8?41.9 | 1,632?1,632 |
| write-scalar | 68.6?123.0 | 8,656?8,656 |
| lift-scalar | 21.7?44.4 | 4,816?4,816 |
| shacl-scalar-prepared-validator | 7542.2?10127.5 | 1,887,432?1,888,000 |
| conformance-scalar | 10.0?24.2 | 1,600?1,600 |
| generate-scalar | 143.7?179.9 | 204,192?204,192 |
| parse-bytes-1024 | 10.0?15.3 | 2,672?2,672 |
| write-bytes-1024 | 51.1?78.8 | 9,480?9,480 |
| parse-bytes-1048576 | 159.3?230.2 | 1,050,224?1,050,224 |
| write-bytes-1048576 | 440.7?573.6 | 2,236,632?2,236,632 |

Compilation of the loaded profile and prepared-validator SHACL dominate scalar operations in this fixture. They should be profiled before introducing caches or graph-sharing changes. Timings vary substantially between forks; allocation measurements are more consistent. No runtime optimization or regression threshold is justified solely by this first baseline.

The harness checks exact writer bytes and applicable semantic conformance before timing, and retains a volatile result sink. Allocation is current-thread allocation, not peak RSS. Percentiles use nearest rank and remain separate per fork. Generated execution, cold loading, nested/compressed/geometry workloads and concurrent load remain open.

[Structured results](2026-09-12-performance-baseline.json) ? [Raw samples and runtime metadata](2026-09-12-performance-baseline.zip)

Reproduce with `gradlew.bat :codegen-verify:stageAcceptance`, then `python tests/performance/run_pipeline.py --output build/performance/new-run` in hexplain-tools. Existing output directories are rejected. A manually dispatched diagnostic workflow was added; it has not been run remotely. The successful local baseline followed a failed staging attempt retained under build/performance/20260912-stage-baseline; that attempt produced no accepted measurements.
