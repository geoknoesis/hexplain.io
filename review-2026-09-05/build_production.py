"""Production-readiness assessment; a separate rubric from implementation quality."""
from pathlib import Path
from html import escape as e
from decimal import Decimal
import json,hashlib,subprocess,xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent
SITE=OUT.parent
ENGINE=SITE.parent/'hexplain-tools'
def read(p):
    b=p.read_bytes();return b.decode('utf-16' if b.startswith((b"\xff\xfe",b"\xfe\xff")) else 'utf-8-sig')
def source(repo,path,needle=None):
    root=ENGINE if repo=='engine' else SITE
    p=root/path;lines=read(p).splitlines()
    line=next((i for i,s in enumerate(lines,1) if needle and needle in s),None)
    if needle:assert line,(path,needle)
    return dict(repo=repo,path=path,line=line,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def counts(module):
    files=list((ENGINE/module/'build/test-results/test').glob('TEST-*.xml'));assert files
    result={k:sum(int(ET.parse(f).getroot().get(k,0)) for f in files) for k in ['tests','failures','errors','skipped']}
    assert not any(result[k] for k in ['failures','errors','skipped']),result
    return result
metrics={m:counts(m) for m in ['core','adapters','hdl']}
assert 'BUILD SUCCESSFUL' in read(OUT/'readiness-engine.log')
assert 'BUILD SUCCESSFUL' in read(OUT/'production-writer-probe.log')
probes=json.loads(read(OUT/'production-spec-probes.json'));assert all(p['confirmed_gap'] for p in probes)
dimensions=[('Correctness and semantic contracts',30,9.0,9.0),('Architecture and capability clarity',20,9.0,8.5),('Validation and independent evidence',20,8.5,8.5),('Release and deployment verification',20,4.5,6.5),('Operational and governance acceptance',10,5.0,6.5)]
scores={name:float(sum(Decimal(str(row[i]))*row[1] for row in dimensions)/100) for name,i in [('spec',2),('engine',3)]}
findings=[]
def add(id,component,severity,title,evidence,impact,action,refs):
    findings.append(dict(id=id,component=component,severity=severity,title=title,evidence=evidence,impact=impact,action=action,sources=[source(*r) for r in refs]))
add('PR01','Engine','High','Fixed terminated fields emit incomplete wire data',
    'A bytes field with fixedValue [65] and terminator [0] writes [65], omitting [0]. The writer returns before appending the terminator. A separate probe confirms its output then fails the parser. The writer source is byte-identical to the current worktree; probe success confirms the defect, not readiness.',
    'A profile can produce output that cannot be parsed using that same profile. The new automatic-length rejection does not cover a fixed field without an automatic length reference.',
    'Either append and validate the terminator for supported fixed payloads, or explicitly reject the combination before producing output. Add exact-byte and parse/write regressions.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt','if (fieldDef.fixedValue != null)'),('spec','review-2026-09-05/ProductionReadinessProbeTest.kt')])
add('PR02','Specification','High','Geometry validation can report conformance for values outside declared ranges',
    'With the geometry module selected and inference disabled, dimensionality -2 and geometryType "Point" both conform. OrdinateShape targets hasZ/hasM and does not enforce those other properties. Both counterexamples are recorded.',
    'Consumers treating module SHACL conformance as complete semantic validation can accept impossible dimensionality or a literal where a controlled concept is declared. OWL range declarations are not executable SHACL validation.',
    'Add explicitly scoped dimensionality and concept constraints, or require a named validation profile that supplies them. Test unknown and absent values separately from invalid ones.',
    [('spec','specification/aspect/geometry/geometry.ttl',':OrdinateShape'),('spec','review-2026-09-05/production-spec-probes.json')])
add('PR03','Specification','High','Live machine-readable publication is broken',
    'Fresh read-only checks still receive HTTP 200 text/html for the security namespace requested as Turtle and for the immutable JSON manifest. The responses have the same SHA-256.',
    'Production consumers cannot reliably resolve the intended vocabulary or release manifest. Local archive correctness does not establish a functioning published contract.',
    'Correct actual hosting routes/content types and rerun the live publication check. Keep this blocked until deployed responses match the canonical RDF and immutable manifest.',
    [('spec','tools/check_live_publication.py'),('spec','review-2026-09-05/live-publication.json')])
add('PR04','Engine','High','Untrusted whole-request execution still requires an external containment contract',
    'Parser limits and current HEL depth/regex protections are implemented. InstanceGraphValidator caps triples and checks interruption before a synchronous SHACL call, but provides no hard query deadline. Native adapter memory also needs OS limits. Terminator scanning retries prefixes and performs inner comparisons without charging each comparison to a work counter; this is a static complexity concern, not a measured exploit.',
    'Core library calls alone do not provide hard wall-time or aggregate process-memory guarantees for arbitrary descriptions/data. A passing local suite is not a hostile-workload or deployed-isolation acceptance test.',
    'Require a tested worker boundary for untrusted inputs; exercise termination during compilation, custom codecs and SHACL. Bound terminator comparison work or use a linear matcher and test worst-case prefixes.',
    [('engine','core/src/main/kotlin/io/hexplain/core/rdf/InstanceGraphValidator.kt','val report = ShaclValidator'),('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt','private fun readUntilTerminator'),('engine','core/src/main/kotlin/io/hexplain/core/metacodec/ParseLimits.kt')])
add('PR05','Both','High','Current candidate lacks clean remote release acceptance',
    'The current engine is 7c23153 plus uncommitted follow-ups. Fresh local tests pass. CI and private Maven publishing are now configured, but the latest visible remote run is the earlier 1e54ef7 failure; its recorded reason is account billing/spending restrictions before test execution. No successful remote run for this candidate was found. Default artifact version is 0.1.0-SNAPSHOT.',
    'A tested working tree is not a reproducibly accepted, distributed release. Current billing state was not inferred from the old annotation; successful current-revision CI is the missing evidence.',
    'Commit the complete candidate, run clean current-revision CI, assign an immutable internal release version, verify consumer installation and artifact provenance. Record JVM dependency advisory review and rollback procedures.',
    [('engine','build.gradle.kts','version ='),('engine','.github/workflows/ci.yml'),('spec','review-2026-09-05/remote-ci.json')])
add('PR06','Engine','Medium','DLV expressiveness still exceeds executable array access',
    'Current IR preserves packed-cell, chunk and dynamic-stride declarations, but MultiDimensionalData.requireExecutable rejects them. This is a deliberate safe boundary, not silent corruption. Delimited writer containers and encoded struct repeat-until remain outside the writer subset.',
    'Users can describe layouts that the generic accessor cannot execute. A production feature claim must distinguish ontology/IR representation from decoding and writing.',
    'Publish a versioned compile/read/write capability matrix and keep rejection tests. Extend one executable subset at a time with independent bytes and malformed-input cases.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/MultiDimensionalData.kt','private fun requireExecutable'),('engine','docs/review-boundaries.md')])
add('PR07','Specification','Medium','Independent ontology review is prepared but not completed',
    'The candidate pins 737 resources in 35 modules with a reviewer checklist; reviewer and decision remain null. Generated definitions, paired SHACL engines and an implementing-assistant review do not supply an independent modeling judgment.',
    'Cross-module composition, unknown-value semantics and profile completeness lack external acceptance. The two reproduced geometry gaps illustrate the difference between documented vocabulary and complete constraints.',
    'Obtain a named independent reviewer, complete module coverage and counterexamples, resolve findings and record an explicit decision against hashes. Do not count package preparation as approval.',
    [('spec','specification/ontology-review/review-manifest.json'),('spec','specification/ontology-review/review-instructions.md')])
add('PR08','Both','Medium','Interoperability evidence is substantial but remains scoped',
    'Retained evidence includes 611 raster matches, 112 generated WKB cases and 60 GeoPackage rows. The vector fixture covers seven geometry families and four ordinate layouts, not seven native file drivers. Native Shapefile/FlatGeobuf/GeoParquet, broader CF/HDF variants, reprojection and topology are not established by those counts.',
    'Format-wide or general geospatial-equivalence claims would exceed the measured contracts. Signed-24-bit GDAL divergence remains explicitly excluded from equality passes.',
    'Use a supported-profile allowlist for production; add upstream real-world vector fixtures, semantic metadata, rejection and fuzz evidence before expanding claims.',
    [('spec','specification/coverage/gdal-tests/vector-depth.html'),('spec','review-2026-09-05/vector-depth.json'),('engine','tests/gdal/expected-deviations.json')])
from production_followup import apply
apply(findings,source)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ENGINE,text=True).strip()
result=dict(date='2026-09-06',scope='Current engine HEAD plus working-tree changes; specifications local working tree; SaaS excluded',engine_head=head,engine_dirty=True,score_kind='production readiness, not historical implementation quality',scores=scores,dimensions=dimensions,metrics=metrics,findings=findings)
(OUT/'production-readiness.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
def links(f):
    result=[]
    for s in f['sources']:
        path=('../../hexplain-tools/' if s['repo']=='engine' else '../')+s['path']
        result.append(f'<li><a href="{e(path)}">{e(s["path"])}</a>'+(' (line '+str(s['line'])+')' if s['line'] else '')+'</li>')
    return ''.join(result)
cards=''.join(f'<article id="{f["id"]}"><p>{f["id"]} &middot; {f["component"]} &middot; <b>{f["severity"]}</b> &middot; {e(f["status"])}</p><h3>{e(f["title"])}</h3><p><b>Evidence:</b> {e(f["evidence"])}</p><p><b>Impact:</b> {e(f["impact"])}</p><p><b>Required action:</b> {e(f["action"])}</p><details><summary>Source evidence</summary><ul>{links(f)}</ul></details></article>' for f in findings)
rows=''.join(f'<tr><th>{e(n)}</th><td>{w}%</td><td>{s:.1f}</td><td>{g:.1f}</td></tr>' for n,w,s,g in dimensions)
page=f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hexplain production-readiness review</title><style>body{{font:17px/1.7 system-ui;color:#18323b;background:#f2f6f3;margin:0}}main{{max-width:1120px;margin:auto;padding:32px 24px}}article,.panel{{background:white;padding:24px;margin:20px 0;border:1px solid #ccdcd6;border-radius:10px}}h1{{line-height:1.15;font-size:42px}}a{{color:#006d60}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #ccd}}.scroll{{overflow:auto}}.verdict{{border-left:5px solid #a56300;padding:20px;background:#fff3de}}:focus-visible{{outline:3px solid #078779}}li{{overflow-wrap:anywhere}}@media print{{article{{break-inside:avoid}}}}</style><main><a href="index.html">Implementation-quality review</a><h1>Production readiness: specifications and engine</h1><p><a href="implementation-progress.html">Current implementation progress and remaining acceptance tasks</a></p><p>6 September 2026 &middot; code review of engine <code>{head[:12]}</code> plus working-tree changes. SaaS excluded. This report includes the verified production-boundary corrections and local release-consumer follow-up.</p><p class="verdict"><b>Not ready for an unrestricted general-purpose production release.</b> Controlled deployments with pinned profiles and tested external containment are a reasonable next acceptance stage. PR01 and PR02 are corrected. Live publication and current-candidate remote release/worker acceptance are still required before wider use.</p><section class="panel"><h2>Scores</h2><p><strong>Specification: {scores['spec']:.2f}/10 &middot; Engine: {scores['engine']:.2f}/10.</strong> These production-readiness scores use the rubric below. Earlier 9.38/9.33 figures assessed implementation quality and scoped improvements; they are not deployment certification. The lower readiness scores are not directly comparable to those values.</p><div class="scroll"><table><thead><tr><th>Dimension</th><th>Weight</th><th>Spec</th><th>Engine</th></tr></thead><tbody>{rows}</tbody></table></div><p>The rubric weights correctness 30%, architecture 20%, evidence 20%, verified release 20% and operational/governance acceptance 10%. These are reviewer judgments, not probabilities or a mathematical proof. Release blockers remain blockers even if a weighted average improves.</p></section><section class="panel"><h2>Verified strengths and test scope</h2><p>Current corrected <code>:core:test :adapters:test :hdl:test</code> checks: <b>{metrics['core']['tests']} core + {metrics['adapters']['tests']} adapters + {metrics['hdl']['tests']} HDL tests</b>, with zero failures/errors/skips. The earlier isolated engine results were not substituted for this run. Current code includes SLF4J integration, HEL depth/regex protections, preserved DLV declarations and explicit runtime capability rejection; earlier descriptions of those features are superseded.</p><p>Canonical references cover 737 resources and 98 shapes. The full specification gate run and new immutable snapshot replay are recorded in the follow-up evidence. Independent GDAL comparisons and both SHACL engines provide useful scoped evidence. Neither suite detects every valid combination: the original review probes reproduced gaps despite a green integration suite; new correctness regressions now cover those gaps.</p><p>Fresh HTTP checks failed. Remote CI history was read without launching or deploying anything. No production load, hostile-workload certification, dependency advisory scan, production-registry installation or external ontology approval was performed. A separate consumer verified locally staged Maven artifacts.</p><ul><li><a href="readiness-engine.log">Corrected engine checks</a> | <a href="production-fixes.json">Follow-up evidence</a> | <a href="production-consumer.log">Isolated Maven consumer</a></li><li><a href="production-spec-probes.json">Geometry validation counterexamples</a></li><li><a href="production-writer-probe.log">Writer defect probe</a></li><li><a href="live-publication.json">Fresh publication checks</a></li><li><a href="production-readiness.json">Scores, findings and source hashes</a></li></ul></section><h2>Findings, highest priority first</h2>{cards}<section class="panel"><h2>Release acceptance order</h2><ol><li>Completed: reject unsupported fixed/terminated framing and validate geometry dimensions/concepts; retain the new regression cases.</li><li>Repair namespace/release publication and pass live media/content checks.</li><li>Freeze and commit the candidate, pass clean current-revision CI, verify a versioned private artifact and document dependency/rollback acceptance.</li><li>Verify worker containment under hostile compilation, decoding and validation loads. Keep unsupported layout and format cases rejected.</li><li>Complete the independent ontology review and broaden real-world vector/semantic fixtures before expanding support claims.</li></ol></section></main></html>"""
(OUT/'production-readiness.html').write_text(page,encoding='utf-8')
print(json.dumps(dict(scores=scores,metrics=metrics,findings=len(findings))))
