"""A HEL 1.0 parser and the canonical serializer, for comparing HEL-bearing literals.

The conformance suite compares a HEL string an implementation emits with the one a case expects by expression
equivalence (specification/hel/index.html#canonical-form): the two parse to the same tree once a bare name is read as
instance.<name>, a hexadecimal literal as its Integer and a float literal as its binary64 value. This module parses the
HEL grammar (specification/hel/index.html#syntax) into a tree of tuples and writes the canonical form; two strings are
equivalent exactly when their canonical forms are equal. It checks syntax only: names, types and arity are the
evaluator's business, and a string that does not parse is compared as written.
"""
import re

ROOTS = ("instance", "parent", "root", "self", "stream", "asset")
RESERVED = ROOTS + ("and", "or", "not", "true", "false")
MAX_INTEGER = 2 ** 63 - 1


class HelSyntaxError(ValueError):
    pass


_TOKEN = re.compile(r"""
    (?P<ws>[ \t\r\n]+)
  | (?P<hex>0[xX][0-9A-Za-z_]*)
  | (?P<float>[0-9]+\.[0-9]+(?:[eE][+-]?[0-9]+)?|[0-9]+[eE][+-]?[0-9]+)
  | (?P<int>[0-9]+)
  | (?P<ident>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op>==|!=|<=|>=|<<|>>|[<>+\-*/%&|^~?:()\[\],.])
""", re.X)


def _string(text, i):
    """The string literal starting at text[i] (a quote): (value, index after it)."""
    out, j = [], i + 1
    while True:
        if j >= len(text):
            raise HelSyntaxError("unterminated string literal")
        c = text[j]
        if c == "'":
            return "".join(out), j + 1
        if c != "\\":
            out.append(c)
            j += 1
            continue
        if j + 1 >= len(text):
            raise HelSyntaxError("unterminated escape")
        e = text[j + 1]
        simple = {"\\": "\\", "'": "'", '"': '"', "n": "\n", "t": "\t", "r": "\r", "0": "\0"}
        if e in simple:
            out.append(simple[e])
            j += 2
        elif e == "x":
            h = text[j + 2:j + 4]
            if not re.fullmatch(r"[0-9A-Fa-f]{2}", h):
                raise HelSyntaxError("\\x needs two hex digits")
            out.append(chr(int(h, 16)))
            j += 4
        elif e == "u":
            h = text[j + 2:j + 6]
            if not re.fullmatch(r"[0-9A-Fa-f]{4}", h):
                raise HelSyntaxError("\\u needs four hex digits")
            unit = int(h, 16)
            j += 6
            if 0xD800 <= unit <= 0xDBFF:
                low = text[j:j + 6]
                if not re.fullmatch(r"\\u[dD][c-fC-F][0-9A-Fa-f]{2}", low):
                    raise HelSyntaxError("a high surrogate must be followed by a low one")
                unit = 0x10000 + ((unit - 0xD800) << 10) + (int(low[2:], 16) - 0xDC00)
                j += 6
            elif 0xDC00 <= unit <= 0xDFFF:
                raise HelSyntaxError("lone low surrogate")
            out.append(chr(unit))
        else:
            raise HelSyntaxError(f"unknown escape \\{e}")


def tokenize(text):
    tokens, i = [], 0
    while i < len(text):
        if text[i] == "'":
            value, i = _string(text, i)
            tokens.append(("str", value))
            continue
        m = _TOKEN.match(text, i)
        if not m:
            raise HelSyntaxError(f"unexpected character {text[i]!r} at {i}")
        kind = m.lastgroup
        lexeme = m.group(kind)
        i = m.end()
        if kind == "ws":
            continue
        if kind == "hex":
            if not re.fullmatch(r"0[xX][0-9A-Fa-f]+", lexeme):
                raise HelSyntaxError(f"malformed hex literal {lexeme}")
            value = int(lexeme[2:], 16)
            if value > MAX_INTEGER:
                raise HelSyntaxError(f"integer literal {lexeme} out of range")
            tokens.append(("int", value))
        elif kind == "int":
            value = int(lexeme)
            if value > MAX_INTEGER:
                raise HelSyntaxError(f"integer literal {lexeme} out of range")
            tokens.append(("int", value))
        elif kind == "float":
            value = float(lexeme)
            if value in (float("inf"), float("-inf")):
                raise HelSyntaxError(f"float literal {lexeme} is not finite")
            tokens.append(("float", value))
        elif kind == "ident":
            tokens.append(("ident", lexeme))
        else:
            tokens.append(("op", lexeme))
    tokens.append(("end", None))
    return tokens


class _Parser:
    def __init__(self, text):
        self.tokens = tokenize(text)
        self.i = 0

    def peek(self, offset=0):
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def next(self):
        t = self.tokens[self.i]
        self.i += 1
        return t

    def at(self, kind, value=None):
        t = self.peek()
        return t[0] == kind and (value is None or t[1] == value)

    def expect(self, kind, value=None):
        if not self.at(kind, value):
            raise HelSyntaxError(f"expected {value or kind}, found {self.peek()[1]!r}")
        return self.next()

    def parse(self):
        e = self.expression()
        if not self.at("end"):
            raise HelSyntaxError(f"unexpected {self.peek()[1]!r}")
        return e

    def expression(self):
        return self.conditional()

    def conditional(self):
        cond = self.or_expr()
        if self.at("op", "?"):
            self.next()
            then = self.expression()
            self.expect("op", ":")
            other = self.conditional()
            return ("cond", cond, then, other)
        return cond

    def _chain(self, sub, ops, word=False):
        left = sub()
        while (self.at("ident") if word else self.at("op")) and self.peek()[1] in ops:
            op = self.next()[1]
            left = ("bin", op, left, sub())
        return left

    def or_expr(self):
        return self._chain(self.and_expr, ("or",), word=True)

    def and_expr(self):
        return self._chain(self.not_expr, ("and",), word=True)

    def not_expr(self):
        if self.at("ident", "not"):
            self.next()
            return ("un", "not", self.not_expr())
        return self.comparison()

    def comparison(self):
        left = self.bit_or()
        if self.at("op") and self.peek()[1] in ("==", "!=", "<=", ">=", "<", ">"):
            op = self.next()[1]
            left = ("bin", op, left, self.bit_or())
            if self.at("op") and self.peek()[1] in ("==", "!=", "<=", ">=", "<", ">"):
                raise HelSyntaxError("comparisons do not chain")
        return left

    def bit_or(self):
        return self._chain(self.bit_xor, ("|",))

    def bit_xor(self):
        return self._chain(self.bit_and, ("^",))

    def bit_and(self):
        return self._chain(self.shift, ("&",))

    def shift(self):
        return self._chain(self.add, ("<<", ">>"))

    def add(self):
        return self._chain(self.mul, ("+", "-"))

    def mul(self):
        return self._chain(self.unary, ("*", "/", "%"))

    def unary(self):
        if self.at("op", "-") or self.at("op", "~"):
            op = self.next()[1]
            return ("un", op, self.unary())
        return self.primary()

    def primary(self):
        kind, value = self.peek()
        if kind in ("int", "float", "str"):
            self.next()
            return ("lit", kind, value)
        if kind == "op" and value == "(":
            self.next()
            e = self.expression()
            self.expect("op", ")")
            return e
        if kind == "ident":
            if value in ("true", "false"):
                self.next()
                return ("lit", "bool", value == "true")
            if value in ("and", "or", "not"):
                raise HelSyntaxError(f"{value} is not an operand")
            if self.peek(1) == ("op", "(") and value not in ROOTS:
                self.next()
                self.next()
                args = []
                if not self.at("op", ")"):
                    args.append(self.expression())
                    while self.at("op", ","):
                        self.next()
                        args.append(self.expression())
                self.expect("op", ")")
                return ("call", value, tuple(args))
            return self.accessor()
        raise HelSyntaxError(f"unexpected {value!r}")

    def accessor(self):
        first = self.next()[1]
        steps = []
        root = first if first in ROOTS else "instance"
        if first not in ROOTS:
            steps.append(("key", first))
        while True:
            if self.at("op", "."):
                self.next()
                name = self.expect("ident")[1]
                if name in RESERVED and name != "parent":
                    raise HelSyntaxError(f"{name} is a reserved word, not a key")
                steps.append(("key", name))
            elif self.at("op", "["):
                self.next()
                steps.append(("index", self.expression()))
                self.expect("op", "]")
            else:
                return ("acc", root, tuple(steps))


def parse(text):
    """The expression tree of a HEL string; raises HelSyntaxError when the grammar does not generate it."""
    return _Parser(text).parse()


def _float(v):
    """Java's Double.toString spelling, which the canonical form uses: the shortest digits that round-trip, written
    plainly when the magnitude is in [1e-3, 1e7) and as d.dddE<n> otherwise."""
    from decimal import Decimal
    if v == 0:
        return "0.0"
    sign, digits, exponent = Decimal(repr(abs(v))).as_tuple()
    text = "".join(map(str, digits)).rstrip("0") or "0"
    scientific = len("".join(map(str, digits))) - 1 + exponent
    minus = "-" if v < 0 else ""
    if 1e-3 <= abs(v) < 1e7:
        plain = format(Decimal(repr(abs(v))), "f")
        if "." not in plain:
            plain += ".0"
        whole, _, fraction = plain.partition(".")
        return minus + whole + "." + (fraction.rstrip("0") or "0")
    return minus + text[0] + "." + (text[1:] or "0") + "E" + str(scientific)


def _quote(value):
    out = ["'"]
    for c in value:
        if c == "\\":
            out.append("\\\\")
        elif c == "'":
            out.append("\\'")
        elif (ord(c) < 0x20 and c not in "\t\n\r") or c == "\x7f":
            out.append("\\x%02X" % ord(c))
        else:
            out.append(c)
    out.append("'")
    return "".join(out)


def _grouped(node):
    text = serialize(node)
    return f"({text})" if node[0] in ("bin", "cond") else text


def serialize(node):
    """The canonical form of an expression tree (specification/hel/index.html#canonical-form)."""
    kind = node[0]
    if kind == "lit":
        _, t, v = node
        if t == "str":
            return _quote(v)
        if t == "bool":
            return "true" if v else "false"
        if t == "float":
            return _float(v)
        return str(v)
    if kind == "acc":
        _, root, steps = node
        out = [root]
        for step in steps:
            out.append("." + step[1] if step[0] == "key" else "[" + serialize(step[1]) + "]")
        return "".join(out)
    if kind == "un":
        _, op, operand = node
        return ("not " if op == "not" else op) + _grouped(operand)
    if kind == "bin":
        _, op, left, right = node
        return f"{_grouped(left)} {op} {_grouped(right)}"
    if kind == "call":
        _, name, args = node
        return name + "(" + ", ".join(serialize(a) for a in args) + ")"
    if kind == "cond":
        _, c, t, e = node
        cond = f"({serialize(c)})" if c[0] == "cond" else serialize(c)
        return f"{cond} ? {serialize(t)} : {serialize(e)}"
    raise ValueError(f"unknown node {node!r}")


def canonical(text):
    """The canonical form of a HEL string, or None when it does not parse."""
    try:
        return serialize(parse(text))
    except HelSyntaxError:
        return None


def equivalent(a, b):
    """Whether two HEL strings denote the same expression (both parse, to one tree); otherwise, whether they are equal."""
    ca, cb = canonical(a), canonical(b)
    if ca is None or cb is None:
        return a == b
    return ca == cb
