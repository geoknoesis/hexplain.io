"""Disposition of reproduced production gaps after verified local corrections."""
import json
from pathlib import Path
def apply(findings,source):
    out=Path(__file__).resolve().parent
    evidence=json.loads((out/'production-fixes.json').read_text(encoding='utf-8'))
    assert evidence['local_consumer']=='passed' and evidence['geometry_cases']==9
    for f in findings:f['status']='Open'
    by={f['id']:f for f in findings}
    by['PR01'].update(status='Fixed by rejection',title='FixedValue plus terminator rejects before output',evidence='The reproduced incomplete-output path now throws an explicit unsupported-framing error. Fixed-value raw-byte semantics are preserved; no incompatible terminator semantics are invented. Regression cases cover nonempty, empty and embedded-sentinel fixed payloads.',impact='The writer no longer returns malformed data for this unsupported combination.',action='Use an ordinary terminated payload or explicit supported fixed-width framing. Supporting this combination in future requires a matching parser/writer contract.')
    by['PR01']['sources'] += [source('engine','core/src/test/kotlin/io/hexplain/core/metacodec/ProductionBoundaryRegressionTest.kt')]
    by['PR02'].update(status='Fixed',title='Geometry 1.2 validates dimensions and concept values',evidence='OrdinateShape activation now includes dimensionality and geometryType. Positive integer-family dimensions and explicitly typed concept IRIs are enforced. Nine Python cases with result-path checks and a Jena regression cover the original counterexamples and valid/unknown values.',impact='Selecting the module no longer accepts the two reproduced out-of-range values. Missing values remain unknown, not implicitly false.',action='Migrate decimal/string dimensions to valid integer-family literals and supply required concept definitions. The stricter contract is documented and included in snapshot 2026-09-06.2.')
    by['PR02']['sources'] += [source('spec','tools/test_geometry_contract.py'),source('spec','releases/2026-09-06.2/manifest.json')]
    by['PR03']['status']='Blocked externally'
    by['PR03']['action'] += ' The actual host/deployment configuration is still unavailable; no guessed deployment was performed.'
    by['PR04'].update(status='Scoped mitigation',evidence='Terminator scanning now uses linear-time KMP, charges the failure table before allocation, and accounts for scanned bytes and the copied result. Empty terminators produce explicit validation diagnostics. Long-prefix and overlap regressions pass. HEL limits and existing worker protections remain; synchronous SHACL/custom-codec/native work still requires externally verified process containment.',action='The repeated-prefix scan gap is corrected for both terminators and synchronization markers; 4,000 deterministic differential cases pass. Complete deployed worker acceptance for compilation, arbitrary codecs and SHACL before treating untrusted whole-request execution as certified.')
    by['PR05'].update(status='Scoped mitigation',evidence=by['PR05']['evidence']+' A local-only Maven repository now stages core/HDL/adapters at a readiness coordinate. A separate consumer resolves the published core API and bundled vocabulary and verifies native adapters are absent from core. No composite sibling-source dependency is used.',action='Local package installation is verified. Clean current-revision remote CI, a production release coordinate, dependency advisory review and deployed rollback acceptance remain outstanding.')
    by['PR05']['sources'] += [source('engine','tests/release/README.md'),source('spec','review-2026-09-05/production-fixes.json')]
    by['PR06']['status']='Documented limitation'
    by['PR06']['action']='The versioned capability matrix now distinguishes IR representation, executable accessors, writer subsets and rejection behavior. Unsupported execution remains rejected; implementing the remaining layouts is future feature work.'
    by['PR06']['sources'] += [source('engine','docs/capability-matrix.md')]
    by['PR07']['status']='Blocked externally'
    by['PR07']['action'] += ' The candidate was refreshed for Geometry 1.2; reviewer and decision remain unset.'
    by['PR08']['status']='Documented limitation'
    by['PR08']['action']='Production capability claims are now explicitly bounded by the capability matrix. Additional native drivers and broader semantic equivalence are not claimed; they remain feature/acceptance work.'
