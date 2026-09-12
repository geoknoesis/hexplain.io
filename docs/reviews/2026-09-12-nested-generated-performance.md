# Nested and generated-code performance evidence

Three independent JVM forks completed 27 workloads, 100 warmups and 200 measured samples per workload: **16,200 timed samples**. The original scalar and byte-buffer workloads remain. Four encoded fixtures add single blocks, counted blocks, recursive frames and propagated length dependencies. Interpreter and generated writers must match fixture bytes before measurement.

| Workload | Per-fork p50 range (microseconds) | Thread allocation median range (bytes) |
|---|---:|---:|
| parse-encoded-single | 15.3?27.7 | 11,144?11,144 |
| write-encoded-single | 101.6?127.3 | 57,648?57,648 |
| generated-reflective-read-encoded-single | 25.0?32.2 | 9,888?9,888 |
| generated-reflective-write-encoded-single | 47.0?58.2 | 25,760?25,760 |
| parse-encoded-counted | 16.9?20.4 | 20,544?20,544 |
| write-encoded-counted | 160.4?271.1 | 95,384?95,384 |
| generated-reflective-read-encoded-counted | 19.1?20.9 | 19,592?19,592 |
| generated-reflective-write-encoded-counted | 64.7?98.5 | 48,064?48,064 |
| parse-encoded-recursive | 31.9?38.7 | 31,328?31,328 |
| write-encoded-recursive | 282.9?760.9 | 153,024?153,024 |
| generated-reflective-read-encoded-recursive | 19.1?25.1 | 28,936?28,936 |
| generated-reflective-write-encoded-recursive | 79.2?155.5 | 71,184?71,184 |
| parse-encoded-propagated | 24.4?85.3 | 37,696?37,696 |
| write-encoded-propagated | 212.0?610.2 | 126,752?126,752 |
| generated-reflective-read-encoded-propagated | 22.5?26.2 | 37,200?37,200 |
| generated-reflective-write-encoded-propagated | 95.7?141.4 | 80,976?81,456 |

Generated classes are compiled against runtime-kotlin alone, then staged in a separate acceptance JAR. Their measurements include reflection and, for reads, construction of the read-limit object. These timings are not equivalent to direct-call benchmarks. The fixtures are small, synthetic, uncompressed-level zlib nested blocks; this does not establish representative real-world compression throughput.

The runner retains requested fork count and completion status, raw samples, percentiles, allocation and GC evidence, platform/JVM metadata and staged artifact hashes. Only complete results count as a baseline. Existing output directories cannot be overwritten.

[Structured results](2026-09-12-nested-generated-performance.json) ? [Raw samples](2026-09-12-nested-generated-performance.zip)

The expanded staging build and standalone generated-code compilation passed. Benchmark correctness prechecks passed in all forks. Python syntax and Git whitespace checks passed. No production-runtime optimization, release deployment, score increase or direct-call performance claim is made. Peak RSS, large geometry, higher-compression data, concurrent load and calibrated regression budgets remain open.
