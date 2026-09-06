from pathlib import Path
p=Path('D:/work/hexplain-tools/core/src/main/kotlin/io/hexplain/core/hel/HelEvaluator.kt')
s=p.read_text(encoding='utf-8')
s=s.replace('is Number -> -v.toLong()', 'is Number -> checked { Math.negateExact(intOperand(v, "unary -")) }')
s=s.replace('TokenType.OP_NEQ -> !isEqual(left, right, equalityBytesCharset(node.left, node.right))','TokenType.OP_NEQ -> left != null && right != null && !isEqual(left, right, equalityBytesCharset(node.left, node.right))')
s=s.replace('val i = (evaluate(step.expr) as? Number)?.toLong()\n                        ?: throw HelEvaluationException("Array index must be an integer")','val i = intOperand(evaluate(step.expr), "array index")')
s=s.replace('intOperand(left, "<<") shl intOperand(right, "<<").toInt()', 'checked { java.math.BigInteger.valueOf(intOperand(left, "<<")).shiftLeft(shiftCount(right)).longValueExact() }')
s=s.replace('intOperand(left, ">>") shr intOperand(right, ">>").toInt()', 'intOperand(left, ">>") shr shiftCount(right)')
s=s.replace('s.substring(start, minOf(start + length, s.length))','s.substring(start, minOf(start.toLong() + length, s.length.toLong()).toInt())')
s=s.replace('val a = l.toLong(); val b = r.toLong()\n            when (op) {\n                TokenType.OP_PLUS -> a + b\n                TokenType.OP_MINUS -> a - b\n                TokenType.OP_MUL -> a * b\n                TokenType.OP_DIV -> if (b == 0L) throw HelEvaluationException("Division by zero") else a / b', 'val a = intOperand(l, "arithmetic"); val b = intOperand(r, "arithmetic")\n            when (op) {\n                TokenType.OP_PLUS -> checked { Math.addExact(a, b) }\n                TokenType.OP_MINUS -> checked { Math.subtractExact(a, b) }\n                TokenType.OP_MUL -> checked { Math.multiplyExact(a, b) }\n                TokenType.OP_DIV -> if (b == 0L) throw HelEvaluationException("Division by zero") else checked { java.math.BigInteger.valueOf(a).divide(java.math.BigInteger.valueOf(b)).longValueExact() }')
s=s.replace('val n = (value as? Number)?.toLong()\n            ?: throw HelEvaluationException("$fn() $what must be an integer, got ${typeName(value)}")\n        if (n < 0) throw HelEvaluationException("$fn() $what must not be negative (got $n)")', 'val n = intOperand(value, "$fn() $what")\n        if (n < 0 || n > Int.MAX_VALUE) throw HelEvaluationException("$fn() $what must be in [0, ${Int.MAX_VALUE}] (got $n)")')
s=s.replace('left.toDouble().compareTo(right.toDouble())','compareNumbers(left, right) ?: return false')
s=s.replace('left.toDouble() == right.toDouble()','compareNumbers(left, right) == 0')
s=s.replace('left.compareTo(right)','compareValues(left.codePoints().toArray().asList(), right.codePoints().toArray().asList())') if False else s
needle='    private fun boolOperand(value: Any?, op: String): Boolean ='
s=s.replace(needle,'''    private inline fun <T> checked(block: () -> T): T = try { block() } catch (e: ArithmeticException) {
        throw HelEvaluationException("Integer overflow: ${e.message}")
    }

    private fun shiftCount(value: Any?): Int {
        val n = intOperand(value, "shift")
        if (n !in 0L..63L) throw HelEvaluationException("Shift count must be in [0, 63]")
        return n.toInt()
    }

    /** Compare the exact represented values, never round an integer to binary64 first. */
    private fun compareNumbers(left: Number, right: Number): Int? {
        fun floating(n: Number) = n is Double || n is Float
        val l = left.toDouble(); val r = right.toDouble()
        if ((floating(left) && l.isNaN()) || (floating(right) && r.isNaN())) return null
        if ((floating(left) && l.isInfinite()) || (floating(right) && r.isInfinite())) return l.compareTo(r)
        fun exact(n: Number) = if (floating(n)) java.math.BigDecimal(n.toDouble())
            else java.math.BigDecimal.valueOf(intOperand(n, "comparison"))
        return exact(left).compareTo(exact(right))
    }

'''+needle)
p.write_text(s,encoding='utf-8')
p=Path('specification/hel/index.html');s=p.read_text(encoding='utf-8')
s=s.replace("Comparison and arithmetic operator semantics follow their counterparts in [[xpath-functions-31]]. Bitwise operators operate on integer values using two's-complement semantics at the operand's bit width.","HEL uses signed 64-bit Integers and IEEE 754 binary64 Floats. Integer-only arithmetic is exact within the signed 64-bit range; overflow MUST raise a runtime error. Integer <code>/</code> truncates toward zero (thus <code>5 / 2 = 2</code>), and <code>%</code> is the remainder with the dividend's sign. Mixing Integer and Float promotes arithmetic to Float (thus <code>5 / 2.0 = 2.5</code>). This integer division is deliberately different from XPath numeric division. Division and modulo by zero MUST raise an error. Integer comparisons MUST be exact; mixed comparisons compare the exact represented numeric values without first rounding the Integer to Float. NaN is unequal to every value and all ordered comparisons involving NaN are false. Bitwise operators use signed 64-bit two's-complement values. Shift counts MUST be integers in [0, 63]; right shift is arithmetic and left-shift overflow MUST raise an error. Indexes MUST be nonnegative Integers within the addressed collection; fractional or out-of-range indexes MUST raise an error.")
p.write_text(s,encoding='utf-8')
for name in ['specification/dlv/dlv.ttl','specification/dlv/index.html']:
 p=Path(name);s=p.read_text(encoding='utf-8').replace("BMP's row padding is ((width * bitsPerPixel + 31) / 32) * 4", "BMP's row padding is ((width * bitsPerPixel + 31) / 32) * 4 with HEL integer division (nonnegative integer operands; overflow is an error)")
 p.write_text(s,encoding='utf-8')
