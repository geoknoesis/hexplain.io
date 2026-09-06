package io.hexplain.saas.review

import io.hexplain.core.hel.*
import io.hexplain.core.rdf.*
import io.hexplain.saas.engine.*
import io.hexplain.saas.domain.model.*
import io.hexplain.saas.adapter.memory.*
import io.hexplain.saas.service.*
import io.hexplain.saas.seed.SeedData
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.*

/** Characterization probes: PASS means the reported defect was reproduced, not fixed. */
class ReviewProbes {
    private fun ast(s: String) = HelParser(Lexer(s).tokenize()).parse()
    private fun eval(s: String) = HelEvaluator(emptyMap()).evaluate(ast(s))
    @Test fun numericCounterexamples() {
        assertEquals(true, eval("9007199254740992 == 9007199254740993"))
        assertEquals(false, eval("9007199254740993 > 9007199254740992"))
        assertEquals(Long.MIN_VALUE, eval("9223372036854775807 + 1"))
        assertEquals(2L, eval("5 / 2"))
        assertEquals(1L, eval("1 << 64"))
        assertEquals("b", eval("substr('abc', 1.9, 1)"))
        assertEquals(true, eval("missing != 1"))
    }
    @Test fun ignoredLayoutExpressionsAndConditions() {
        val engine = HexplainFormatEngine()
        val compiled = engine.compile("format t @namespace \"https://example.org/t#\" @root struct File { A : u8 }")
        assertTrue(compiled.ok, compiled.diagnostics.toString())
        val ir = RdfToIrCompiler(ProfileLoader().loadFromString(compiled.profileTurtle!!)).compile(compiled.rootStructUri!!)
        val root = ir.structs.getValue(ir.rootStruct)
        val changed = root.copy(fields = root.fields.map { it.copy(sizeFromExpression = ast("2")) })
        assertTrue(ProfileDiffer().diff("1.0.0", ir, "1.0.1", ir.copy(structs = mapOf(root.name to changed))).changes.isEmpty())
        val conditional = root.copy(fields = root.fields.map { it.copy(isPresentIf = ast("false")) })
        assertEquals(RequiredBump.MINOR, ProfileDiffer().diff("1.0.0", ir, "1.1.0", ir.copy(structs = mapOf(root.name to conditional))).requiredBump)
    }
    @Test fun invalidVersionBypassesGate() {
        assertTrue(ProfileDiff("1.0.0", "banana", emptyList(), ChangeClass.BREAKING, RequiredBump.MAJOR).versionIsConsistent())
    }
    @Test fun cacheMisattributesAndFailedRunLooksImproved() {
        val engine = HexplainFormatEngine()
        val versions = InMemoryProfileVersionRepository()
        val samples = InMemorySampleFileRepository()
        val registry = RegistryService(InMemoryFormatRepository(), versions, engine)
        val runs = RunService(InMemoryRunRepository(), InMemoryFindingRepository(), versions, samples, engine)
        registry.createFormat("w", "png-basic", "PNG", "")
        val v = registry.publish("fmt-png-basic", "1.0.0", SeedData.PNG_BASIC_HDL, SeedData.PNG_BASIC_RULES)
        assertEquals(ProfileState.PUBLISHED, v.state)
        fun file(id: String, bytes: ByteArray) = SampleFile(id,"w","$id.png",RunService.sha256Hex(bytes),bytes.size,bytes)
        samples.save(file("a", SeedData.PNG_BYTES))
        samples.save(file("b", SeedData.PNG_BYTES))
        val a = runs.startRun("w",v.id,"a")
        val b = runs.startRun("w",v.id,"b")
        assertTrue(b.fromCache)
        assertEquals("a", b.fileId)
        samples.save(file("bad", byteArrayOf()))
        val bad = runs.startRun("w",v.id,"bad")
        assertEquals(RunStatus.FAILED,bad.status)
        val diff = runs.compareRuns(a.id,bad.id)!!
        assertFalse(diff.isRegression)
        assertEquals(1,diff.fixedFindings.size)
    }
}
