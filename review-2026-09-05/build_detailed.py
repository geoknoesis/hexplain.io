"""Evidence-backed, separately scored review of specification, engine and SaaS."""
from pathlib import Path
from html import escape
from decimal import Decimal, ROUND_HALF_UP
import json, os, re, hashlib, subprocess
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
ROOT=OUT.parent
REPOS={'spec':ROOT,'engine':ROOT.parent/'hexplain-tools','saas':ROOT.parent/'hexplain-saas'}
e=escape

def read(path):
    data=Path(path).read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')

def src(repo,path,needle=None):
    file=REPOS[repo]/path
    assert file.is_file(),file
    text=read(file)
    line=next((i for i,s in enumerate(text.splitlines(),1) if needle and needle in s),None)
    assert not needle or line,(file,needle)
    href=os.path.relpath(file,OUT).replace('\\','/')
    return {'file':f'{REPOS[repo].name}/{path}','href':href,'line':line,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}

findings=[]
def add(repo,id,severity,status,title,impact,evidence,action,refs):
    findings.append(dict(repo=repo,id=id,severity=severity,status=status,title=title,impact=impact,evidence=evidence,action=action,sources=[src(*r) for r in refs]))

add('spec','SP01','High','Fixed','Finite-value constraints accepted infinity under another spelling',
    'A calibration literal "1e309"^^xsd:double passed the lexical blacklist although its numeric value is infinite. This can contaminate georeferencing or calibrated values.',
    'Both positive and negative overflow spellings passed before the fix. Nine pySHACL boundary cases now pass; Jena independently verifies nonfinite rejection and finite extremes.',
    'Added numeric bounds excluding both infinities while preserving valid finite extremes and signed zero. No-data NaN remains allowed in its separate contract.',
    [('spec','specification/aspect/raster/raster.ttl','sh:minExclusive "-INF"'),('spec','specification/aspect/spatialref/spatialref.ttl',':FiniteDoubleShape'),('spec','tools/test_numeric_boundaries.py'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/NumericShapeBoundaryTest.kt')])
add('spec','SP02','High','Fixed','Band-index uniqueness confused RDF identity with numeric equality',
    'Two bands could both occupy numeric index 1 when one index was xsd:integer and the other xsd:unsignedInt.',
    'The counterexample conformed before correction. It now fails in pySHACL and Jena.',
    'Join the two index values independently and compare them numerically. Band resources themselves are compared by RDF term identity.',
    [('spec','specification/aspect/raster/raster.ttl','?c a:bandIndex ?j'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/NumericShapeBoundaryTest.kt')])
add('spec','SP03','High','Fixed','Malformed coefficient lists hid duplicate equal-valued literals',
    'Two different lexical double literals with equal numeric value could both be rdf:first on one coefficient cell. The list was not well formed, yet value inequality failed to detect it.',
    'A valid 20-cell vector passes; adding a second equal-valued but distinct rdf:first now fails. Repeated values in separate cells remain legal.',
    'Use sameTerm for list multiplicity checks in raster and spatial-reference constraints. Numeric equality remains appropriate for quantities, not graph cardinality.',
    [('spec','specification/aspect/spatialref/spatialref.ttl','FILTER(!sameTerm(?v, ?w))'),('spec','tools/test_numeric_boundaries.py')])
add('spec','SP04','High','Fixed','Compression framing needed an explicit zlib concept',
    'The documented raw DEFLATE meaning and engine dispatch disagreed. A profile identifier did not reliably identify the byte framing.',
    'The raw RFC 1951 dispatch regression failed before correction. The register now has 24 codec/compression concepts and the PNG resource uses Zlib.',
    'Added menc:Zlib; retained distinct Deflate and Gzip meanings; documented the required migration for profiles relying on the old alias.',
    [('spec','specification/register/media-encoding/media-encoding.ttl','menc:Zlib a'),('spec','specification/reference/boundary-revision.md'),('engine','core/src/main/resources/png-profile.ttl','menc:Zlib')])
add('spec','SP05','Medium','Verified strength','Complete references are synchronized with canonical RDF',
    'Hand-maintained descriptions can drift from the vocabulary and its shapes, especially across imported aspects.',
    '736 named resources, 98 named shapes and 35 modules pass annotation, reference, fragment-link and embedded-RDF checks. There are 20 specification gates.',
    'Keep generation and the completeness gate in CI. Term coverage establishes documentation presence, not independent semantic review of every definition.',
    [('spec','tools/test_term_reference.py'),('spec','tools/test_html_sync.py'),('spec','specification/reference/index.html')])
add('spec','SP06','High','Scoped mitigation','Pinned GDAL samples now have executable interoperability evidence',
    'A vocabulary inventory alone does not establish binary interoperability. Formats, GDAL drivers, documentation pages and sample files remain different denominators.',
    'The complete checked-in raster/vector/core fixture set was downloaded with companions and verified against pinned Git blobs. 5,622 isolated GDAL probes observe 153 drivers. 136 of 246 documentation pages map to sample evidence. Hexplain achieves 611 full-pixel matches across supported variants of six raster drivers; three encoder outputs independently decode in GDAL.',
    'Published every inventory entry with runtime mappings, samples, source hashes and explicit outcomes. Zarr v2 and jHDF-backed HDF5 now add 41 pixel matches. Scoped NetCDF, GeoPackage/WKB, LAS and Parquet adapters have companion-reference tests. GDAL vector/semantic parity, wider variants and metadata extraction remain open. One signed-24-bit datatype discrepancy is documented and is not counted as equality.',
    [('spec','specification/coverage/gdal-tests/index.html'),('spec','specification/coverage/gdal-tests/evidence.json'),('spec','tools/test_gdal_runtime.py'),('spec','specification/coverage/gdal-tests/extended.html'),('spec','specification/coverage/gdal-tests/extended-evidence.json'),('engine','tests/gdal/README.md')])
add('spec','SP07','Medium','Scoped mitigation','Semantic competency evidence remains narrower than vocabulary coverage',
    'Generated definitions and broad module scope notes cannot establish that all combinations of terms model real formats correctly.',
    'Geospatial tests cover 40 semantic cases and 121 exact affine round trips, plus the new numeric cases. Eleven new packaging competency cases establish target scoping, typed membership and path contracts. Equivalent depth is not established for all 736 resources, despite the added shared 36-case corpus.',
    'Packaging now has concrete positive/negative cases with result-path assertions and inference disabled. The shared 36-case corpus adds sampling, signal, time, packaging and raster checks in both Jena and pySHACL. Extend depth across security, bit packing and compound datasets; independent ontology review remains needed.',
    [('spec','tools/test_geospatial_model.py'),('spec','tools/_reference.py'),('spec','specification/ontology-design/index.html')])
add('spec','SP08','Medium','Scoped mitigation','Immutable draft snapshots now replay their original compatibility corpus',
    'A stricter shape can reject previously accepted data even when vocabulary term IRIs are unchanged. Mutable downloads cannot identify the exact historical validation contract.',
    'Snapshot 2026-09-05.1 pins 38 files with archive and per-file SHA-256, ontology versions and the shared 36-case corpus. The gate replays its original cases against archived and current graphs; the snapshot tool refuses overwrite.',
    'Local artifacts and compatibility replay are implemented. Live namespace dereferencing, media types, externally hosted immutable retention and external consumer acceptance remain unverified. Hashes are not signatures and repository review must prevent coordinated manifest/archive edits.',
    [('spec','releases/2026-09-05.1/manifest.json'),('spec','releases/index.html'),('spec','tools/test_release_contract.py'),('spec','tools/_snapshot_release.py')])

add('spec','SP09','High','Fixed','Archive shape scope rejected generic packaging containers',
    'ArchiveShape targeted every use of the shared hasEntry property, requiring non-archive box members to be ArchiveEntry. EntryShape likewise imposed archive constraints on any resource with a filename.',
    'The unnamed box competency case failed before the target fix. Eleven cases now pass, including generic containers, archive subtypes, rejected generic members of an archive, duplicate paths, conflicting paths and literal membership.',
    'Scope archive shapes to archive classes and archive-specific properties. Packaging 1.1 adds documented membership/path shapes without requiring paths or path uniqueness across entries. Preserve verbatim paths; these shapes do not authorize filesystem extraction.',
    [('spec','specification/axv/archive.ttl','sh:targetClass axv:Archive'),('spec','specification/aspect/packaging/packaging.ttl',':ContainerShape a'),('spec','tools/test_packaging_contract.py'),('spec','specification/reference/boundary-revision.md')])

add('engine','EN01','High','Fixed','Sizes and repeat counts narrowed before validation',
    'A fixed size of 4,294,967,297 bytes wrapped to one byte. Fractional counts were truncated, and a large count could trigger a large allocation before reading input.',
    'The fixed-size and count counterexamples failed the new expected-correctness tests before this pass. Exact conversion and uint64/count tests now pass.',
    'Validate integral finite values before narrowing; bound byte/string allocations by remaining input; start repetition storage with a modest capacity. Existing recovery semantics are retained.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt','private fun exactInt'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/ReviewBoundaryTest.kt')])
add('engine','EN02','High','Fixed','Array access could return wrong signed values or aliased cells',
    'Signed -1 decoded as 255; uint32/uint64 values narrowed silently. Missing/extra indices, invalid logical coordinates and overflowing strides could access an unrelated byte.',
    'Pre-fix tests reproduced signedness, index and stride failures. Final tests cover uint64 maximum, float64 precision, bounds, rank and truncated cells.',
    'Added exact getInteger/getLong and getDouble accessors. Narrowing getInt fails outside its range. Checked long arithmetic and complete-cell bounds protect every array access.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/MultiDimensionalData.kt'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/ReviewBoundaryTest.kt')])
add('engine','EN03','High','Fixed','Inflater termination could mean partial success or endless waiting',
    'A truncated compressed block returned partial data; a preset-dictionary request could repeatedly make no progress. Native resources were not released on every failure path.',
    'Every truncated prefix of sample zlib/raw DEFLATE payloads is now rejected. Dictionary, empty-stream, output-budget and trailing-byte cases pass.',
    'Require stream completion, fail on missing dictionaries or stalled progress, and release native resources in finally. Correct RFC 1951 and Deflate dispatch to raw framing.',
    [('engine','core/src/main/kotlin/io/hexplain/core/codec/BuiltInCodecs.kt'),('engine','core/src/main/kotlin/io/hexplain/core/codec/CodecRegistry.kt'),('engine','core/src/test/kotlin/io/hexplain/core/codec/CodecBoundaryTest.kt')])
add('engine','EN04','High','Fixed','Unsupported DLV features disappeared during IR lowering',
    'Chunk addressing, conditional layouts, packed-cell declarations or dynamic strides could be expressed in RDF but were absent from the IR, leaving a misleading ordinary-layout interpretation.',
    'The compiler now rejects the known unsupported declarations with their names. A supported contiguous layout still compiles; the regression tests cover both paths.',
    'Keep this explicit capability gate until the relevant IR, parser, writer and semantic-output support exist. This is safe rejection, not implementation of those formats.',
    [('engine','core/src/main/kotlin/io/hexplain/core/rdf/RdfToIrCompiler.kt','rejectUnsupportedLayout'),('engine','core/src/main/kotlin/io/hexplain/core/ir/Model.kt','data class DataLayoutIR'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/UnsupportedLayoutTest.kt')])
add('engine','EN05','High','Fixed','Unsigned 64-bit output became zero',
    'The writer converted only Number values; Kotlin ULong values produced by the parser were not Numbers and fell back to zero. Small-width integer output also wrapped out-of-range inputs.',
    'The uint64 maximum now survives parse/write exactly. Fractional, nonfinite, nonnumeric, negative unsigned and overflowing integer values are rejected.',
    'Check the exact integer against its signed/unsigned width before writing its bit pattern. Float conversion and bitfield writing have separate contracts and are not certified by these tests.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt','val integer = try'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/WriterIntegerBoundaryTest.kt')])
add('engine','EN06','High','Scoped mitigation','Shared parser budgets stop repeated and cumulative expansion',
    'Per-block limits left zero-byte repetition, recursive structs, many decoded blocks and repeated byte reads unbounded across a parse.',
    'Seven new tests exercise STRICT/COLLECT exhaustion, recursive depth, cumulative and intermediate decoding, per-invocation reset, input/materialization bounds, interruption and delimited records. Limits cannot be swallowed by recovery.',
    'Implemented input, visited-node, depth, materialized-byte and aggregate decoded-byte budgets with cooperative deadlines and thread interruption. Individual HEL/custom-codec calls, compilation, semantic lifting and conformance evaluation still require their own limits and isolated execution.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/ParseLimits.kt'),('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt','private val invocationBudget'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/ParseLimitsTest.kt'),('engine','docs/review-boundaries.md')])
add('engine','EN07','High','Scoped mitigation','Writer now resolves addressed, aligned and bounded layouts',
    'Pointer writes previously lacked supported placement semantics. Detached payload sizing could not faithfully measure nested regions or crossing length dependencies in their actual file positions.',
    'The previous 26 writer tests retain independent expected bytes and parse/write equality, including 100 seeded varied layouts. Nineteen additional tests cover conditional byte order, encoded substreams, counted element sizes and failure boundaries, using literal PackBits vectors and independent JDK inflation. They cover all four offset origins, absolute alignment, sparse growth, aliases, recursive regions, bounded EOF/sentinel sequences, crossing/shared lengths, physically trailing length fields, stream reuse and nonconvergence rejection.',
    'Added bounded layout passes with occurrence-specific inferred lengths, cursor restoration and high-water output preservation. Limits span all passes. Explicit outputSize supports whole-file end-relative placement. Conditional struct byte order and sized encoded nested structs now compose with the layout passes. Delimited containers, encoded struct repeat-until arrays and some inferred-length forms still reject; arbitrary HEL inversion and hard execution isolation remain outside the contract.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt','private fun checkTermination'),('engine','core/src/main/kotlin/io/hexplain/core/metacodec/GrowingWriteBuffer.kt'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/WriterSymmetryTest.kt'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/WriterEncodedStructTest.kt'),('engine','docs/review-boundaries.md'),('spec','specification/coverage/writer-tests/index.html')])

add('engine','EN14','High','Fixed','Reader ignored nested field bounds and narrowed pointer arithmetic',
    'A single nested struct could read into the following field because its enclosing field region was not applied. Scalar byte sequences reused the sequence extent as each cell width. Fractional offsets were truncated before seeking.',
    'Reader/writer vectors now check nested padding and trailers, byte-cell EOF regions, empty regions, fractional and overflowing offsets, and negative addresses before alignment. The complete integration suite and repeated GDAL comparisons pass.',
    'Apply and restore nested field regions, separate sequence extent from scalar cell width, and use exact checked address arithmetic. These are upper-bound parsing contracts; backward references are still allowed. Profiles relying on ignored bounds or truncated offsets must be corrected.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/WriterSymmetryTest.kt'),('engine','docs/review-boundaries.md')])

add('engine','EN08','Medium','Fixed','Emitted-instance validation now has its own API and provenance',
    'Description conformance did not establish that an emitted graph satisfied its semantic constraints, and callers lacked a named stage distinguishing the two results.',
    'InstanceGraphValidator validates explicitly selected bundled modules, retains referenced helper shapes, copies input, and returns the full SHACL report with selected/vocabulary byte hashes, Jena version, source identifier and counts. Five API tests and 36 shared competency cases run in Jena; the same corpus passes pySHACL.',
    'processAndValidateSemanticGraph connects compile/parse/lift to this stage. No RDFS/OWL materialization or network import fetching is performed. A true report may be vacuous; input triple limits are not hard query deadlines. SaaS does not automatically select every shape.',
    [('engine','core/src/main/kotlin/io/hexplain/core/rdf/InstanceGraphValidator.kt'),('engine','core/src/main/kotlin/io/hexplain/core/semantic/SemanticProcessor.kt','fun processAndValidateSemanticGraph'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/InstanceGraphValidatorTest.kt'),('spec','specification/validation/index.html')])

add('engine','EN09','Medium','Scoped mitigation','Independent decoding and encoding comparisons now exercise real fixtures',
    'Round trips can hide shared mistakes. File-count totals can also overstate independent evidence when upstream fixtures duplicate bytes or contain sparse images.',
    '611 files match all pixel bits, dimensions, band counts and datatypes against GDAL 3.13.3; the evidence also records distinct input and output counts. Thirteen GDAL-derived golden vectors run offline, including four HDF5 vectors. Thirty-three scoped cases cover scoped scientific, vector, point-cloud, columnar and mathematical adapters; companion-library tests are not GDAL passes. Reverse tests cover Hexplain zlib, TIFF LZW and PackBits output. 248 unsupported variants and 15 rejected fixtures are not passes.',
    'Added bounded raster adapters, explicitly framed TIFF codecs, a pinned corpus fetcher, isolated GDAL workers, strict differential comparison and a manually triggered CI workflow. Expand vector/semantic/codec coverage and independently investigate rejected files; remote CI has not been run.',
    [('engine','core/src/main/kotlin/io/hexplain/core/raster/RasterDecoder.kt'),('engine','core/src/main/kotlin/io/hexplain/core/raster/TiffRasterDecoder.kt'),('engine','tests/gdal/compare.py'),('engine','core/src/test/kotlin/io/hexplain/core/raster/GdalGoldenVectorTest.kt')])
add('engine','EN10','High','Fixed','TIFF header byte order and empty IFD counts were incorrect',
    'The bundled TIFF profile always read header numbers as little-endian. A zero-entry IFD used repeat-until and attempted a record read despite the declared zero count.',
    'New regression tests verify MM header values and an empty IFD. The semantic TIFF reader propagates the header byte order into independently parsed IFD slices. The pixel adapter separately compares supported classic TIFF and BigTIFF fixtures against GDAL.',
    'Use conditional header types and exact count-based directory arrays. Keep classic-profile semantic extraction distinct from the new first-image pixel adapter.',
    [('engine','core/src/main/resources/tiff-profile.ttl',"instance.parent.ByteOrder == 'MM'"),('engine','core/src/main/kotlin/io/hexplain/core/semantic/TiffSemanticProcessor.kt','val fileOrder'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/TIFFProfileTest.kt')])
add('engine','EN11','Medium','Open','Packed signed 24-bit TIFF has a GDAL datatype discrepancy',
    'Matching pixel bytes do not establish matching numeric interpretation: this fixture is exposed as Int32 by Hexplain and UInt32 by the pinned GDAL build.',
    'The input hash and exact datatype-only difference are pinned in expected-deviations.json. All pixel bits and dimensions agree. A golden test preserves the difference explicitly; it is not counted among the 611 equality cases.',
    'Retain signed TIFF SampleFormat semantics. Pinned GDAL GTiffOddBitsBand explicitly maps signed 17?31-bit integers to UInt32 and has a FIXME naming int24.tif. A separate negative-boundary test now verifies signed Int32 values; compatibility remains a non-pass. Any additional or changed difference fails the comparator instead of falling under a broad exclusion.',
    [('engine','tests/gdal/expected-deviations.json'),('engine','tests/gdal/compare.py'),('engine','core/src/test/kotlin/io/hexplain/core/raster/GdalGoldenVectorTest.kt')])

add('saas','SA01','High','Fixed','Mutable sample bytes invalidated stored digests and cached results',
    'A caller could mutate the original or returned byte array after save, changing content while keeping the stored SHA-256 and run references.',
    'The new repository test failed before correction. It now mutates ingress, save return, single lookup and list lookup arrays without altering storage.',
    'Store and return defensive byte copies, and verify declared length and SHA-256 against the stored snapshot. This protects in-process identity; durable content storage remains open.',
    [('saas','backend/app/src/main/kotlin/io/hexplain/saas/adapter/memory/InMemoryRepositories.kt','val snapshot'),('saas','backend/app/src/test/kotlin/io/hexplain/saas/RepositoryIntegrityTest.kt')])
add('saas','SA02','High','Fixed','File and format identities could be overwritten',
    'Saving an existing file ID replaced the bytes referenced by historical runs; replacing a format could change the workspace owner of existing versions.',
    'Both overwrite counterexamples failed before the fix and now reject replacement while preserving the first resource.',
    'Reject duplicate file/format IDs. A future persistence layer must enforce equivalent unique constraints transactionally.',
    [('saas','backend/app/src/main/kotlin/io/hexplain/saas/adapter/memory/InMemoryRepositories.kt','Format ID already exists'),('saas','backend/app/src/test/kotlin/io/hexplain/saas/RepositoryIntegrityTest.kt')])
add('saas','SA03','High','Scoped mitigation','Validation and viewing share parser-wide resource limits',
    'The interactive input limit alone did not stop compression expansion inside either execution path.',
    'Integration tests reject a compressed payload expanding beyond 8 MiB and a profile requesting over two billion zero-byte repetitions. Validation and COLLECT-mode viewing both fail explicitly.',
    'Both paths enforce the same 8 MiB block cap, 32 MiB aggregate decoding cap, 100,000 nodes, depth 32, byte budgets and cooperative five-second parse deadline. Thread interruption is observed. Whole-request quotas and isolated workers remain open.',
    [('saas','backend/engine/src/main/kotlin/io/hexplain/saas/engine/HexplainFormatEngine.kt','MAX_DECODED_BLOCK_BYTES'),('saas','backend/app/src/test/kotlin/io/hexplain/saas/ExecutionBudgetTest.kt')])
add('saas','SA04','Medium','Fixed','Unexpected HTTP 422 responses could masquerade as successful data',
    'The shared client treated every 422 as a typed success. Error objects could reach screens expecting a compile result or collection, while ordinary errors displayed raw JSON.',
    'New API tests check rejected compile requests, readable error explanations and structured INVALID publication diagnostics. Both .ts and .tsx tests are discovered.',
    'Only publication accepts a structured 422 result. Other failing statuses reject with a readable server explanation; CSRF handling remains in the shared client.',
    [('saas','frontend/lib/api.ts','allowValidationResult'),('saas','frontend/tests/api.test.ts'),('saas','frontend/vitest.config.mts')])
add('saas','SA05','High','Open','In-memory storage cannot provide durable service guarantees',
    'A restart loses stored formats, versions, runs and findings. In-process synchronization does not coordinate multiple service instances.',
    'The repository adapters use in-memory maps. Publish concurrency is protected within one process only.',
    'Introduce durable transactional metadata, immutable object storage, schema migrations, uniqueness constraints, and backup/restore tests. Demonstrate crash recovery before a production readiness claim.',
    [('saas','backend/app/src/main/kotlin/io/hexplain/saas/adapter/memory/InMemoryRepositories.kt'),('saas','backend/app/src/main/kotlin/io/hexplain/saas/service/RegistryService.kt','@Synchronized')])
add('saas','SA06','High','Open','Authentication currently protects one configured workspace',
    'The implemented deployment does not provide tenant-aware authorization, per-project roles or distributed execution isolation.',
    'Authentication, CSRF and foreign-object tests pass. WorkspaceAccess uses a server-configured workspace ID for the deployment.',
    'Retain this supported deployment scope. For a multi-tenant product, derive authorization from authenticated memberships and isolate storage and worker execution by tenant.',
    [('saas','backend/app/src/main/kotlin/io/hexplain/saas/config/SecurityConfig.kt','class WorkspaceAccess'),('saas','backend/app/src/test/kotlin/io/hexplain/saas/SecurityBoundaryTest.kt')])
add('saas','SA07','Medium','Open','Browser accessibility and operational performance need acceptance evidence',
    'Component tests cannot establish real screen-reader behavior, responsive rendering, actual keyboard focus across navigation, or latency under concurrent runs.',
    'The preceding pass verified six frontend tests and the production build; that unchanged-frontend evidence is retained here. The test harness now uses one thread worker after repeat Windows fork startup timeouts. No manual browser, screen-reader, load, restart or distributed deployment test was performed.',
    'Run keyboard and screen-reader walkthroughs, responsive screenshots, realistic corpus timing and concurrent-run load tests. Keep the 1 MiB viewer limit visible until larger-file interaction is implemented.',
    [('saas','frontend/tests/workflows.test.tsx'),('saas','frontend/app/files/[id]/page.tsx'),('saas','REVIEW-FIXES.md')])
add('saas','SA08','Medium','Verified strength','Engine changes are pinned and the patch can be regenerated',
    'An application tested against an edited sibling engine is not reproducible if new files are omitted from its delivery patch.',
    'The refresh tool includes tracked changes plus new source/test files, checks the pinned base, and validates reverse application. npm audit reports zero known npm vulnerabilities at review time; no equivalent JVM advisory audit was performed.',
    'Run the new patch check locally after engine edits and run the existing clean-checkout CI. Upstream the patch into a versioned engine release; remote CI execution is not claimed here.',
    [('saas','tools/refresh_engine_patch.py'),('saas','engine-revision.txt'),('saas','.github/workflows/verify.yml')])

add('spec','SP10','High','Fixed','Sampling values lacked shared constraints and rate range excluded fractions',
    'Range axioms alone did not reject zero, fractional or string-valued sample counts. Restricting rates to integers excluded legitimate sampled signals such as 0.5 Hz.',
    'Sampling/Signal 1.1 add three documented named shapes. The shared 36-case corpus includes integer-family counts, fractional decimal rates, nonfinite values, contradictory counts, controlled sample formats and explicit result paths in two SHACL engines.',
    'Counts remain positive integral values; rates accept positive finite decimals or integer-family values. Raw binary approximations require an explicit profile conversion. The release and migration notes record the stricter validation contract.',
    [('spec','specification/aspect/sampling/sampling.ttl',':SamplingShape'),('spec','specification/aspect/signal/signal.ttl',':SampleRateShape'),('spec','tools/test_instance_contract.py'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/InstanceCompetencyTest.kt')])
add('engine','EN12','High','Fixed','TIFF semantic extraction confused raw storage with resolved tag values',
    'The two TIFF commands had diverged. Big-endian inline SHORT values occupied the high half of a raw four-byte slot, while RATIONAL tags stored a pointer; emitting that slot as a semantic quantity was incorrect.',
    'Both CLIs now share one first-directory processor. Tests cover II/MM scalar agreement, offset zero, large invalid offsets, unsupported BigTIFF, truncation and a RATIONAL pointer retained only as raw storage metadata.',
    'Resolve supported inline integer tags in file byte order and emit canonical raster/sampling properties. Preserve raw ValueOrOffset separately. General rational/vector tags and complete directory chains still require implementation.',
    [('engine','core/src/main/kotlin/io/hexplain/core/semantic/TiffSemanticProcessor.kt'),('engine','core/src/test/kotlin/io/hexplain/core/semantic/TiffSemanticProcessorTest.kt'),('spec','specification/reference/boundary-revision.md')])
add('engine','EN13','High','Fixed','Bundled profiles treated real authoring errors as expected residuals',
    'PNG and TIFF descriptions had unresolved mapping targets and untyped mapping rules. PNG also labeled an unscaled gamma integer as gamma and a timestamp second component as a complete modification date.',
    'Both bundled descriptions now pass description SHACL with zero residual violations. Profile-owned raw terms, declared class/property types, typed mapping rules and Dublin Core title/creator mappings replace the former expected-error assertions.',
    'Raw encoded values have explicit profile-owned properties, while resolved TIFF dimensions use aspect IRIs. These emitted-IRI changes require consumer migration, documented in the boundary revision. Description conformance alone does not certify every ancillary chunk or tag.',
    [('engine','core/src/main/resources/png-profile.ttl','png:gammaEncoded'),('engine','core/src/main/resources/tiff-profile.ttl','tiff:ImageFileDirectory a owl:Class'),('engine','core/src/test/kotlin/io/hexplain/core/rdf/BundledVocabValidationTest.kt','bundled PNG and TIFF descriptions conform'),('spec','specification/reference/boundary-revision.md')])

add('engine','EN15','High','Fixed','Counted writer regions inferred an array extent instead of an element extent',
    'A counted field using sizeFromField wrote the total array length into a field that the parser applies to each element. The result could swallow following elements or a trailer.',
    'New exact-byte vectors assert the per-element length for plain and encoded structs. Unequal encoded extents sharing one length field reject. Recursive block and bounded decoded-sequence tests preserve outer trailers.',
    'Infer the extent after each counted element; shared measurements must agree. Empty arrays contribute no inferred extent. The same invocation retains all layout, depth and node budgets across decoded buffers.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metawriter.kt','private fun isCounted'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/WriterEncodedStructTest.kt')])
add('engine','EN16','High','Fixed','Encoded struct repeat-until parsing bypassed its codec declaration',
    'The nested repeat-until branch called the plain struct-sequence parser directly, silently treating encoded bytes as unencoded records. A successful parse could therefore describe the wrong values.',
    'Reader and writer both reject this unsupported combination in a dedicated counterexample. Supported alternatives have positive tests: counted encoded blocks, and a bounded plain sequence inside one encoded struct.',
    'Fail explicitly until per-block framing semantics are implemented. The new writer supports single and counted encoded structs with separate decoded addresses and exact compressed extents. This does not preserve arbitrary original compressed bytes or unmodeled decoded padding.',
    [('engine','core/src/main/kotlin/io/hexplain/core/metacodec/Metaparser.kt','Encoded struct repeatUntil'),('engine','core/src/test/kotlin/io/hexplain/core/metacodec/WriterEncodedStructTest.kt'),('spec','specification/coverage/writer-tests/index.html')])

dimensions=[
    ('Correctness and mathematical contracts',30,9.5,9.5,8.75),
    ('Architecture and maintainability',20,9.25,9.5,8.5),
    ('Validation and test evidence',20,9.5,9.5,8.25),
    ('Documentation, UX and accessibility',15,9.5,9.5,7.5),
    ('Delivery and operational readiness',15,9,8,4),
]
scores={repo:float((sum(Decimal(str(row[i]))*row[1] for row in dimensions)/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) for repo,i in [('spec',2),('engine',3),('saas',4)]}
titles={'spec':'Specification','engine':'Engine','saas':'SaaS'}
summaries={
 'spec':'A well-documented, layered working specification with stronger numeric constraints. Representative raster interoperability now has independent evidence. Broader format, semantic and vocabulary competency coverage remains incomplete.',
 'engine':'A capable parser/compiler with much stronger boundary handling. Shared parser budgets, addressed writer layouts and bounded dependency resolution are now tested. Full layout symmetry and hard isolation of all processing stages remain substantial limits.',
 'saas':'A stronger authenticated single-workspace application with reproducible engine integration. It remains a prototype operationally because storage is volatile and runs execute in process.'}

def tests(path):
    result={key:0 for key in ['tests','failures','errors','skipped']}
    files=list(path.glob('TEST-*.xml'));assert files,path
    for file in files:
        root=ET.parse(file).getroot()
        for key in result:result[key]+=int(root.get(key,'0'))
    assert result['failures']==result['errors']==result['skipped']==0,result
    return result

metrics={'adapters':tests(REPOS['engine']/'build-root/adapters/test-results/test'),'core':tests(REPOS['engine']/'build-root/core/test-results/test'),'hdl':tests(REPOS['engine']/'build-root/hdl/test-results/test'),'backend':tests(REPOS['saas']/'backend/app/build/test-results/test')}
assert '20/20 gates passed' in read(OUT/'perfect-spec-gates.log')
assert 'BUILD SUCCESSFUL' in read(OUT/'encoded-writer-final.log')
assert '3/3 gates passed' in read(OUT/'encoded-writer-docs.log')
assert 'PASS:' in read(OUT/'perfect-reference-final.log')
assert re.search(r'Tests\s+6 passed',read(OUT/'closure-frontend-final.log'))
buildlog=read(OUT/'deep-frontend-build.log')
assert 'Generating static pages (8/8)' in buildlog or 'Generating static pages (9/9)' in buildlog or 'Finalizing page optimization' in buildlog,buildlog[-1500:]
assert 'PASS:' in read(OUT/'encoded-writer-engine-patch.log')
assert 'PASS:' in read(OUT/'symmetry-gdal-encoded.log')
assert json.loads(read(REPOS['engine']/'tests/gdal/results/comparison.json'))['counts']['equal'] == 611
assert 'BUILD SUCCESSFUL' in read(REPOS['engine']/'tests/gdal/results/remaining-fixes.log')
assert 'BUILD SUCCESSFUL' in read(OUT/'remaining-saas-check.log')
audit=json.loads(read(OUT/'deep-npm-audit.json'));assert audit['metadata']['vulnerabilities']['total']==0
manifest=json.loads((ROOT/'specification/reference/manifest.json').read_text(encoding='utf-8'))
metrics.update(gates=20,frontend=6,npm_vulnerabilities=0,terms=sum(m['terms'] for m in manifest),shapes=sum(m['shapes'] for m in manifest),modules=len(manifest))

def sources(f):
    return ''.join(f'<li><a href="{e(s["href"],quote=True)}">{e(s["file"])}</a>{" — line "+str(s["line"]) if s["line"] else ""}</li>' for s in f['sources'])

def card(f):
    open_item=f['status'] in ['Open','Scoped mitigation']
    return f'''<article id="{f['id']}" data-repo="{f['repo']}" data-open="{str(open_item).lower()}"><p class="meta">{f['id']} · {f['severity']} · <span class="badge {'open' if open_item else ''}">{f['status']}</span></p><h3>{e(f['title'])}</h3><p>{e(f['impact'])}</p><p><b>Evidence:</b> {e(f['evidence'])}</p><p><b>Action / next step:</b> {e(f['action'])}</p><details><summary>Source evidence</summary><ul class="source-list">{sources(f)}</ul></details></article>'''

cards=''.join(f'<section id="{repo}" class="repo-section"><p class="eyebrow">Separate review</p><h2>{titles[repo]} <span class="score-inline">{scores[repo]:.2f}/10</span></h2><p class="lede">{e(summaries[repo])}</p>'+''.join(card(f) for f in findings if f['repo']==repo)+'</section>' for repo in titles)
table=''.join(f'<tr><th scope="row">{e(row[0])}</th><td>{row[1]}%</td>'+''.join(f'<td>{n:g}</td>' for n in row[2:])+'</tr>' for row in dimensions)
stats=''.join(f'<div class="stat"><span>{titles[r]}</span><strong>{scores[r]:.2f}<small>/10</small></strong><p>{"Previously 9.38" if r=="spec" else "Previously 9.23" if r=="engine" else "Previously 7.70"}</p></div>' for r in titles)
fixed=sum(f['status']=='Fixed' for f in findings);remaining=sum(f['status']=='Open' for f in findings)
checks=[('perfect-spec-gates.log','Prior complete 20 specification gates; canonical RDF unchanged'),('encoded-writer-docs.log','Current documentation gates'),('encoded-writer-final.log','Final full JVM integration run'),('closure-frontend-final.log','Prior 6 frontend tests; frontend unchanged'),('deep-frontend-build.log','Production frontend build'),('deep-npm-audit.json','npm audit'),('encoded-writer-engine-patch.log','Pinned engine patch'),('encoded-writer-gdal-comparison.log','GDAL differential outcomes'),('symmetry-gdal-encoded.log','Prior three GDAL encoder checks; current Docker readback unavailable'),('encoded-writer-gdal-verified.log','Current GDAL encoder attempt status'),('gdal-oracle-final.log','Isolated GDAL corpus run'),('deep-engine-before.log','Pre-fix engine counterexamples'),('deep-spec-before.log','Pre-fix RDF counterexamples'),('deep-saas-before.log','Pre-fix repository counterexamples')]
links=''.join(f'<li><a href="{file}">{label}</a></li>' for file,label in checks)
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hexplain — detailed specification, engine and SaaS review</title><style>
:root{{--ink:#18323b;--muted:#536974;--green:#006d60;--line:#ceded8;--paper:#f2f6f3}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.7 system-ui,Segoe UI,sans-serif}}a{{color:var(--green);text-underline-offset:3px}}.skip{{position:absolute;left:12px;top:-60px;background:white;padding:8px}}.skip:focus{{top:10px}}header{{background:#12333d;color:white;padding:60px max(24px,calc((100vw - 1120px)/2)) 45px}}header p{{color:#d5e5e6;max-width:880px}}h1{{font-size:clamp(34px,4.5vw,58px);line-height:1.1;letter-spacing:-1px;max-width:1000px}}h2{{font-size:29px;line-height:1.25}}h3{{font-size:21px;line-height:1.4;margin:10px 0}}main{{max-width:1168px;margin:auto;padding:28px 24px 60px}}nav{{display:flex;gap:20px;flex-wrap:wrap}}section{{margin:42px 0}}.eyebrow,.meta{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;font-weight:750}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.stat,article,.panel{{padding:24px;background:white;border:1px solid var(--line);border-radius:12px}}.stat strong{{display:block;font-size:48px;line-height:1.4}}small{{font-size:20px;color:var(--muted)}}.stat p{{margin:0;color:var(--muted);font-size:14px}}article{{margin:18px 0;scroll-margin-top:20px}}article p{{margin:12px 0}}.lede{{max-width:950px;color:var(--muted)}}.badge{{padding:3px 8px;background:#e0f0e8;border-radius:5px;color:#245541}}.badge.open{{background:#fff1db;color:#835418}}.callout{{border-left:5px solid #b27730;background:#fff5e7;padding:20px 26px}}.score-inline{{white-space:nowrap;color:var(--green)}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid var(--line)}}thead{{background:#e2eee8}}.table-wrap{{overflow:auto}}.source-list{{font-size:12px;overflow-wrap:anywhere}}summary{{cursor:pointer;font-weight:650}}details{{border-top:1px solid var(--line);padding-top:12px}}input,select{{font:inherit;padding:9px 12px;border:1px solid #8aa39c;border-radius:6px;background:white;color:var(--ink)}}input[type=search]{{width:min(100%,650px)}}.filters{{display:flex;flex-wrap:wrap;gap:14px;align-items:center}}.filters label{{display:flex;align-items:center;gap:8px}}:focus-visible{{outline:3px solid #078779;outline-offset:3px}}li{{margin:7px 0}}footer{{border-top:1px solid var(--line);padding-top:22px;font-size:13px;color:var(--muted)}}[hidden]{{display:none!important}}@media(max-width:680px){{.stats{{grid-template-columns:1fr}}header{{padding:36px 24px}}article{{padding:18px}}.stat strong{{font-size:40px}}}}@media print{{body{{background:white;font-size:11px}}header{{background:white;color:var(--ink);padding:20px}}header p{{color:var(--ink)}}main{{padding:0}}nav,.filters,.skip{{display:none}}article{{break-inside:avoid}}h1{{font-size:34px}}h2{{font-size:23px}}.stat strong{{font-size:30px}}}}
</style></head><body><a class="skip" href="#main">Skip to review</a><header><p class="eyebrow">Engineering review · 5 September 2026 · local working tree</p><h1>Three components.<br>Three separate quality assessments.</h1><p>The specification is the strongest component. The engine now handles several important mathematical and decoding boundaries correctly. The SaaS has new durable-storage, tenant and process-isolation work in progress; live deployment and operational acceptance remain unverified.</p></header><main id="main"><nav aria-label="Review sections"><a href="#scores">Scores</a><a href="#spec">Specification</a><a href="#engine">Engine</a><a href="#saas">SaaS</a><a href="#verification">Verification</a><a href="#next">Next priorities</a></nav><p class="callout"><b>Latest interoperability review: <a href="../specification/coverage/gdal-tests/review.html">9.18/10</a>.</b> Four reproduced defects fixed; optional native dependencies, OS worker limits and fresh semantic comparisons added; this is a scoped increment score, not a whole-product rescore.  <a href="../specification/coverage/gdal-tests/extended.html">Read the new scoped contracts, 39 scoped tests, 41 additional GDAL matches and remaining gaps</a>. Overall score values and non-GDAL assessments are retained from the prior review; SaaS changes are not rescored in this interoperability pass. This does not certify full GDAL interoperability or hosted readiness.</p><section class="stats" aria-label="Component scores">{stats}</section>
<p class="callout"><b>Review scope:</b> source inspection, adversarial regressions, a fresh full JVM integration run, documentation gates and repeated GDAL comparisons. The prior complete 20-gate specification result is retained because canonical RDF is unchanged. Earlier frontend/build/audit evidence is retained and labeled. Scores assess the current working trees; they are reviewer judgments, not mathematical proofs, code-coverage percentages or production certification. No deployment or live browser accessibility audit was performed.</p>
<section id="scores"><h2>Scoring rationale</h2><p>The previous weighting is retained and applied separately to all three components. 9–10 requires broad correctness and strong external evidence; 7–8 is solid engineering with material gaps. The previous separate scores were 9.38, 9.23 and 7.70. SaaS remains at 7.70: corpus evidence does not resolve its storage and execution architecture. Engine rises to 9.28: architecture increases from 9.25 to 9.5 for encoded substream composition with shared layout budgets, correct per-element sizing and read-order-aware byte-order resolution. Correctness, validation and documentation remain 9.5; delivery remains 8.0. The new tests strengthen the supported writer subset, but do not broaden independent driver coverage or establish hard isolation. Specification and SaaS scores are unchanged.</p><div class="table-wrap"><table><thead><tr><th>Dimension</th><th>Weight</th><th>Spec</th><th>Engine</th><th>SaaS</th></tr></thead><tbody>{table}<tr><th>Weighted total</th><td>100%</td><th>{scores['spec']:.2f}</th><th>{scores['engine']:.2f}</th><th>{scores['saas']:.2f}</th></tr></tbody></table></div><p><b>Why the deductions remain:</b> the spec still lacks broad vector/semantic interoperability and independent ontology review; the engine still lacks general writer symmetry and preemptive whole-request isolation; the SaaS has volatile state, one configured workspace and in-process execution. Better documentation or more passing tests cannot remove those architectural limits.</p></section>
<section id="verification"><h2>Verification and limits of the evidence</h2><div class="panel"><p><b>Retained 20/20 specification gates and 3/3 documentation gates; current {metrics['core']['tests']} core + {metrics['adapters']['tests']} adapters + {metrics['hdl']['tests']} HDL + {metrics['backend']['tests']} backend JVM tests.</b> No failed or skipped JVM tests. The final integrated run includes 19 new encoded-struct/conditional-byte-order tests and the previous 26 writer symmetry tests with 100 deterministic varied address/alignment cases. Literal PackBits vectors and JDK inflation supplement parse/write equality. No manual browser acceptance was added. The unchanged frontend retains its preceding six-test, production-build and zero-known-npm-vulnerability evidence; those frontend checks were not rerun in this pass. Java dependency advisories were not independently audited.</p><p>This pass implements conditional byte order from fields available in logical read order, including derived/nested lengths and decoded constant/text discriminators. Encoded nested structs use a fresh decoded address space while sharing invocation budgets; compressed sizes are measured in the enclosing stream. Counted fields now infer each element extent. Intermediate codec outputs are checked before reaching the next stage. The reader explicitly rejects encoded struct repeat-until arrays that previously bypassed decoding. A fresh Hexplain corpus run compared against the pinned prior GDAL oracle retains 611 equal files. Fresh JDK inflation checks pass for zlib and PackBits-then-zlib nested output. A fresh three-file GDAL encoder readback could not complete because Docker and its status command were unresponsive; the earlier three passing GDAL encoder checks are retained and labeled. These raster checks do not certify every generic writer layout.</p><p>The reference now covers <b>{metrics['terms']} resources, {metrics['shapes']} named shapes and {metrics['modules']} modules</b>. These are documentation counts. The <a href="../specification/coverage/gdal-tests/index.html">new GDAL differential report</a> covers all 246 inventory entries, 5,622 fixture probes and 611 full-pixel matches. Six raster driver families have Hexplain pixel evidence; file counts do not count formats. The datatype discrepancy, unsupported variants, rejected files and missing drivers remain explicit.</p><ul>{links}</ul><p><a href="detailed-findings.json">Machine-readable findings, scores and source hashes</a> · <a href="../specification/reference/boundary-revision.md">Specification compatibility notes</a></p></div></section>
<section aria-label="Filter review findings"><h2>Detailed component reviews</h2><p>{len(findings)} assessments: {fixed} fixed findings, {remaining} open gaps, plus scoped mitigations and verified strengths. Scope-limited mitigations are not counted as fully fixed.</p><div class="filters"><label for="search">Search <input id="search" type="search" placeholder="Identifier, topic, or evidence"></label><label for="remaining"><input id="remaining" type="checkbox"> Remaining work only</label></div><p id="count" role="status" aria-live="polite">{len(findings)} assessments shown</p></section>{cards}
<section id="target"><h2>What remains before exceeding 9.5</h2><p><b>The current scores remain below the requested threshold.</b> The weighting has not changed. A score is a review judgment supported by evidence, not a test pass rate. Reaching 9.55 under this rubric would require approximately 9.75 correctness, 9.5 architecture, 9.75 validation, 9.5 documentation and 9.0 delivery.</p><ul><li><b>Specification:</b> independently review remaining term semantics, extend competency coverage to compound datasets/bit packing/security, and verify live versioned namespace dereferencing and consumer compatibility. The local snapshot is implemented; deployment is not certified.</li><li><b>Engine:</b> extend the declared writer subset to terminator-inclusive inferred lengths, delimited containers and explicitly framed encoded struct sequences, add hard isolation for untrusted whole-request execution, and expand differential/fuzz evidence to semantic metadata and additional driver families. The signed-24-bit GDAL discrepancy remains a non-pass.</li></ul><p><a href="../specification/validation/index.html">Validation and release contracts</a> · <a href="../releases/index.html">Pinned snapshot artifacts</a></p></section><section id="next"><h2>Next priorities with completion criteria</h2><ol><li><b>Engine: extend the remaining writer subset.</b> Offsets, alignment, bounded regions and crossing backpatch dependencies now have exact-byte round trips. Conditional struct byte order and sized single/counted encoded structs are now tested. Next implement terminator-inclusive inferred lengths and delimited containers, then define per-block framing for encoded struct repeat-until arrays. Require independent vectors, nested boundaries and explicit cycle/overrun rejection. Arbitrary HEL expressions still require a declared solvable contract; a general algebraic solver is not implemented. See the <a href="../specification/coverage/writer-tests/index.html">writer layout contract</a>.</li><li><b>Engine and SaaS: isolate the whole request.</b> Shared parser budgets now cover nodes, nesting, byte work and cumulative decoding with cooperative cancellation. Add preemptive worker isolation and budgets for compilation, individual expressions, custom codecs, semantic lifting and conformance evaluation.</li><li><b>SaaS: make results durable.</b> Use transactional metadata and immutable byte storage; enforce uniqueness across processes; demonstrate restart, concurrency, backup and recovery behavior.</li><li><b>Specification and engine: extend measured GDAL interoperability.</b> Zarr v2 and jHDF-backed HDF5 add 41 full-pixel matches. Scoped NetCDF, GeoPackage/WKB, LAS and Parquet adapters plus georeferencing/mask helpers now have tests. Fresh GDAL 3.9.x semantic comparisons now cover embedded GeoTIFF transforms/masks, a selected CF variable and XYZ features. Extend the explicitly unsupported variants and hosted Linux acceptance. The signed-24-bit cause and retained TIFF rejections are documented in the <a href="../specification/coverage/gdal-tests/extended.html">extended interoperability review</a>.</li><li><b>Cross-component: independent acceptance.</b> Run clean remote CI, external ontology review, fuzz/differential tests and browser/screen-reader workflows before raising scores toward 10/10.</li></ol></section>
<section><h2>Standards behind the corrections</h2><p>Numeric value spaces and lexical mappings follow <a href="https://www.w3.org/TR/xmlschema11-2/#double">W3C XML Schema double</a>. The distinction between RDF term identity and value equality follows <a href="https://www.w3.org/TR/sparql11-query/#func-sameTerm">SPARQL sameTerm</a>. Framing is defined separately by <a href="https://www.rfc-editor.org/rfc/rfc1950">RFC 1950 (zlib)</a> and <a href="https://www.rfc-editor.org/rfc/rfc1951">RFC 1951 (DEFLATE)</a>. Inflater completion, dictionary handling and cleanup are documented in the <a href="https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/zip/Inflater.html">JDK Inflater API</a>.</p></section>
<footer><p>Earlier snapshots: <a href="before-encoded-writer.html">9.38 specification / 9.23 engine review</a> &middot; <a href="before-writer-symmetry.html">9.38 specification / 8.95 engine review</a> &middot; <a href="before-perfection.html">8.98 specification / 8.29 engine review</a> · <a href="before-gdal-review.html">Review before GDAL differential work</a> · <a href="before-gap-closure.html">Review before gap closure</a> · <a href="term-reference-review.html">8.60 specification / 7.48 SaaS review</a> · <a href="post-fixes.html">First fixes review</a> · <a href="original.html">Original review</a>. Source links target local sibling repositories. The reviewed baseline was committed and pushed for the engine/specification; SaaS remains local. No hosted deployment was performed. Remote CI, live namespace publication, manual accessibility, production load and crash recovery were not verified.</p></footer></main><script>
const search=document.getElementById('search'),remaining=document.getElementById('remaining');function filter(){{let n=0;const q=search.value.trim().toLowerCase();document.querySelectorAll('article[data-repo]').forEach(a=>{{a.hidden=!(a.textContent.toLowerCase().includes(q)&&(!remaining.checked||a.dataset.open==='true'));if(!a.hidden)n++}});document.getElementById('count').textContent=n+' assessments shown';}}search.addEventListener('input',filter);remaining.addEventListener('change',filter);
</script></body></html>'''
history=OUT/'term-reference-review.html'
if not history.exists():history.write_bytes((OUT/'index.html').read_bytes())
(OUT/'index.html').write_text(html,encoding='utf-8')
(OUT/'detailed-findings.json').write_text(json.dumps({'date':'2026-09-05','scores':scores,'dimensions':dimensions,'metrics':metrics,'findings':findings},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'scores':scores,'assessments':len(findings),'fixed':fixed,'open':remaining,'metrics':metrics}))
