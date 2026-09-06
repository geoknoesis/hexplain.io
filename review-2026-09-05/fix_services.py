from pathlib import Path
root=Path('D:/work/hexplain-saas')
def edit(rel,fn):
 p=root/rel;s=p.read_text(encoding='utf-8');p.write_text(fn(s),encoding='utf-8')
model='backend/domain/src/main/kotlin/io/hexplain/saas/domain/model/'
service='backend/app/src/main/kotlin/io/hexplain/saas/service/'
edit(model+'ProfileDiff.kt',lambda s:s.replace("val parts = text.trim().split('.')",'if (!Regex("(0|[1-9][0-9]*)\\\\.(0|[1-9][0-9]*)\\\\.(0|[1-9][0-9]*)").matches(text)) return null\n            val parts = text.split(\'.\')').replace('Semver.parse(fromVersion) ?: return true','Semver.parse(fromVersion) ?: return false').replace('Semver.parse(toVersion) ?: return true','Semver.parse(toVersion) ?: return false').replace('val from = Semver.parse(fromVersion) ?: return null','val from = Semver.parse(fromVersion) ?: return "Invalid baseline version"').replace('val to = Semver.parse(toVersion) ?: return null','val to = Semver.parse(toVersion) ?: return "Version must be canonical major.minor.patch"'))
edit(service+'RegistryService.kt',lambda s:s.replace('    fun publish(', '    @Synchronized\n    fun publish(').replace('        val outcome = engine.compile(hdlSource)\n        val id', '''        require(io.hexplain.saas.domain.model.Semver.parse(semver) != null) { "Version must be canonical major.minor.patch" }
        require(versions.findByFormat(formatId).none { it.semver == semver && it.state == ProfileState.PUBLISHED }) { "Version $semver already published" }
        val outcome = engine.compile(hdlSource)
        val id''').replace('UUID.randomUUID().toString().take(8)','UUID.randomUUID().toString()').replace(') ?: return emptyList()',') ?: return listOf(Diagnostic(Severity.ERROR, 1, 1, "Cannot establish compatibility with the previous version"))',1))
edit(model+'Runs.kt',lambda s:s.replace('(coveredCount * 100) / total','((coveredCount.toLong() * 100) / total).toInt()'))
edit(service+'RunService.kt',lambda s:s.replace('UUID.randomUUID().toString().take(8)','UUID.randomUUID().toString()').replace('val startedAt = Instant.now(clock)', '''require(file.workspaceId == workspaceId) { "File does not belong to workspace" }
        val startedAt = Instant.now(clock)''',1).replace('engineVersion = version.engineVersion,','engineVersion = engine.engineVersion,').replace('it.copy(id = newFindingId(), runId = runId)','it.copy(id = newFindingId(), runId = runId, fileName = file.name)').replace('id = runId,\n                        startedAt', 'id = runId,\n                        workspaceId = workspaceId,\n                        fileId = file.id,\n                        fileName = file.name,\n                        startedAt').replace(').copy(id = runId, coverage = outcome.coverage)',').copy(id = runId, tuple = tuple, coverage = outcome.coverage)').replace('tuple = RunTuple(version.id, "", "", version.engineVersion)', 'tuple = RunTuple(version.id, samples.findById(fileId)?.sha256 ?: "", sha256Hex((version.rulesTurtle ?: "").toByteArray()), engine.engineVersion)').replace('        val before = findings.findByRun(from.id)', '''        require(from.workspaceId == to.workspaceId && from.formatId == to.formatId && from.fileId == to.fileId) {
            "Compare runs of the same workspace, format and file"
        }
        require(from.status == RunStatus.SUCCEEDED && to.status == RunStatus.SUCCEEDED) {
            "Cannot compare failed or incomplete runs; no fixes can be inferred"
        }
        val before = findings.findByRun(from.id)'''))
edit('backend/app/src/main/kotlin/io/hexplain/saas/adapter/memory/InMemoryRepositories.kt',lambda s:s.replace('        store[version.id] = version','''        require(!store.containsKey(version.id)) { "Version ID already exists" }
        require(version.state != ProfileState.PUBLISHED || store.values.none { it.formatId == version.formatId && it.semver == version.semver && it.state == ProfileState.PUBLISHED }) { "Version already published" }
        store[version.id] = version''').replace('        store[run.id] = run','        require(!store.containsKey(run.id)) { "Run ID already exists" }\n        store[run.id] = run'))
