package io.hexplain.core.metacodec
import io.hexplain.core.ir.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
/** Review counterexample: passing this probe confirms a defect, not readiness. */
class ProductionReadinessProbeTest {
    @Test fun `fixed terminated bytes omit the terminator and cannot be parsed back`() {
        val bytes=DataTypeIR("bytes",BaseType.BYTES,8)
        val field=FieldIR("body",bytes,fixedValue=byteArrayOf(65),terminator=byteArrayOf(0))
        val f=FormatIR("counterexample","root",mapOf("root" to StructIR("root",listOf(field))))
        val wire=Metawriter(f).write(emptyMap<String, Any>())
        assertArrayEquals(byteArrayOf(65),wire)
        assertThrows(HexplainParsingException::class.java) { Metaparser(f).parse(wire) }
    }
}
