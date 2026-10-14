"""Plain-English statements of what a SHACL shape checks, read from its constraints.

message() states a property shape's whole contract as one sentence -- the text of the sh:message
the family's reported property shapes carry (tools/test_shape_messages.py). value_phrase() says
what a conforming value is; the term reference uses it to define a value shape (IntegerValueShape,
FiniteDoubleShape) whose source gives no rdfs:comment. Both raise Unhandled rather than guess
when a shape uses a construct they cannot state faithfully; such a shape needs editorial text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from rdflib import RDF, RDFS, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.term import Node

SH = Namespace("http://www.w3.org/ns/shacl#")
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
#: A SPARQL result variable in a message template: {?x} or {$x}.
PLACEHOLDER = re.compile(r"\{[?$][A-Za-z_]\w*\}")
IGNORED = {
    SH.order,
    SH.description,
    SH.name,
    SH.severity,
    SH.deactivated,
    SH.message,
    SH.group,
    SH.defaultValue,
    RDF.type,
    RDFS.label,
    RDFS.comment,
    RDFS.isDefinedBy,
    RDFS.seeAlso,
}
#: What a node shape states besides the value it accepts: its activation, its property shapes and
#: SPARQL constraints (described by their own messages), closure and rules.
NODE_LEVEL = {
    SH.targetClass,
    SH.targetSubjectsOf,
    SH.targetObjectsOf,
    SH.targetNode,
    SH.target,
    SH.property,
    SH.sparql,
    SH.closed,
    SH.ignoredProperties,
    SH.rule,
    SH.prefixes,
    SH.declare,
}


INTS = {"int", "long", "short", "byte", "unsignedInt", "unsignedLong", "unsignedShort", "unsignedByte"}


#: Shared value shapes whose meaning is better said than named.
NODE_PHRASES = {
    "HelExpressionValueShape": "a HEL expression (an xsd:string or bddo:HelExpression literal)",
    "FiniteDoubleShape": "a finite number (an xsd:double or xsd:float literal, not NaN or infinite)",
    "IntegerValueShape": "an integer (of any XSD integer datatype)",
    "FloatValueShape": "an xsd:double or xsd:float literal",
}


class Unhandled(Exception):
    pass


class Stated(Unhandled):
    """The constraint is best described by the message a nested shape already states."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


#: Prefix -> namespace IRI, the bindings a phrase writes its CURIEs with.
Prefixes = Mapping[str, str]


def curie(g: Graph, node: Node, prefixes: Prefixes) -> str:
    if isinstance(node, Literal):
        if node.datatype is None or str(node.datatype).endswith("#string"):
            return f'"{node}"'
        return str(node)
    s = str(node)
    best = None
    for p, ns in prefixes.items():
        if p and s.startswith(ns) and (best is None or len(ns) > len(prefixes[best])):
            best = p
    if best is None:
        return f"<{s}>"
    return f"{best}:{s[len(prefixes[best]) :]}"


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" or word.startswith(("xsd:", "rdf:", "rdfs:", "owl:", "hxf:")) else "a"


def join(items: Iterable[str], conj: str = "or") -> str:
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {conj} " + items[-1]


def members(g: Graph, node: Node) -> list[Node]:
    return list(Collection(g, node))


def path_phrase(g: Graph, path: Node, prefixes: Prefixes) -> tuple[str, bool]:
    """(phrase, plural_member) -- plural_member True when the path reaches list members."""
    if isinstance(path, URIRef):
        return curie(g, path, prefixes), False
    if (path, RDF.first, None) in g:
        steps = members(g, path)
        # ( P [ sh:zeroOrMorePath rdf:rest ] rdf:first ): the members of the list P points to
        if (
            len(steps) == 3
            and isinstance(steps[0], URIRef)
            and steps[2] == RDF.first
            and g.value(steps[1], SH.zeroOrMorePath) == RDF.rest
        ):
            return f"the {curie(g, steps[0], prefixes)} list", True
        if len(steps) == 2 and g.value(steps[0], SH.zeroOrMorePath) == RDF.rest and steps[1] == RDF.first:
            return "the list", True
        parts = []
        for s in steps:
            if isinstance(s, URIRef):
                parts.append(curie(g, s, prefixes))
            else:
                raise Unhandled("complex sequence step")
        return "/".join(parts), False
    inv = g.value(path, SH.inversePath)
    if inv is not None:
        return f"the inverse of {curie(g, inv, prefixes)}", False
    alt = g.value(path, SH.alternativePath)
    if alt is not None:
        return join([curie(g, x, prefixes) for x in members(g, alt)]), False
    raise Unhandled("path")


NODEKIND: dict[Node, str] = {
    SH.IRI: "an IRI",
    SH.BlankNode: "a blank node",
    SH.BlankNodeOrIRI: "a resource (an IRI or a blank node)",
    SH.Literal: "a literal",
    SH.IRIOrLiteral: "an IRI or a literal",
    SH.BlankNodeOrLiteral: "a blank node or a literal",
}


def single(g: Graph, shape: Node) -> tuple[Node, Node] | None:
    """The one (predicate, object) of a branch shape, or None."""
    po = [(p, o) for p, o in g.predicate_objects(shape) if p not in IGNORED and not str(p).startswith(SKOS_NS)]
    return po[0] if len(po) == 1 else None


def _integer(node: Node | None) -> int | None:
    """The integer a count or length literal states, or None when the shape states none."""
    if node is None:
        return None
    if not isinstance(node, Literal):
        raise TypeError(f"a count or length is an integer literal, not {node!r}")
    return int(node)


def property_parts(g: Graph, shape: Node, prefixes: Prefixes) -> list[str] | None:
    """What a shape built of property shapes (and sh:and of such shapes) says the focus node states.

    Returns the list of phrases, one per property shape ("bddo:coversFromField", "no bddo:keyPath",
    "bddo:whitespaceSeparated true", "exactly one bddo:key"), or None when the shape is not such a
    shape. A logical branch of this kind used to be rendered as "a value", which made an sh:xone of
    two branches read "either a value or a value".
    """
    parts: list[str] = []
    structural = {SH.property, SH["and"]}
    if any(
        p not in IGNORED and p not in structural and not str(p).startswith(SKOS_NS) for p in g.predicates(shape, None)
    ):
        return None
    pshapes = list(g.objects(shape, SH.property))
    for lst in g.objects(shape, SH["and"]):
        for member in members(g, lst):
            inner = property_parts(g, member, prefixes)
            if inner is None:
                return None
            parts.extend(inner)
    if not pshapes and not parts:
        return None
    for ps in pshapes:
        parts.append(_property_part(g, ps, prefixes))
    return parts


def _property_part(g: Graph, ps: Node, prefixes: Prefixes) -> str:
    """One property shape of a branch as what the focus node states."""
    path = g.value(ps, SH.path)
    if path is None:
        raise Unhandled("branch property without a path")
    name, _listy = path_phrase(g, path, prefixes)
    lo, hi = _integer(g.value(ps, SH.minCount)), _integer(g.value(ps, SH.maxCount))
    hv = g.value(ps, SH.hasValue)
    if any(
        p not in IGNORED and p not in (SH.path, SH.minCount, SH.maxCount, SH.hasValue) for p in g.predicates(ps, None)
    ):
        # The branch also constrains the value: say what it accepts, in parentheses.
        name = f"{name} ({value_phrase(g, ps, prefixes, allow_count=True)})"
    if hv is not None:
        return f"{name} {curie(g, hv, prefixes)}"
    if hi == 0:
        return f"no {name}"
    if lo and hi is not None and lo == hi:
        return f"exactly one {name}" if lo == 1 else f"exactly {lo} {name}"
    if lo:
        return name if lo == 1 else f"at least {lo} {name}"
    if hi is not None:
        return f"at most {hi} {name}"
    return name


def branch_phrase(g: Graph, shape: Node, prefixes: Prefixes) -> str:
    """A logical branch as a noun phrase: by the properties it states, else by its value constraints."""
    parts = property_parts(g, shape, prefixes)
    if parts is not None:
        return "a node that states " + join(parts, "and")
    return value_phrase(g, shape, prefixes)


def value_phrase(g: Graph, shape: Node, prefixes: Prefixes, allow_count: bool = False) -> str:
    """A noun phrase describing an acceptable value; raises Unhandled for what it cannot say."""
    return _ValuePhrase(g, shape, prefixes, allow_count).phrase()


class _ValuePhrase:
    """The noun phrase of one shape's value constraints: a base noun phrase and the qualifications after it, built
    constraint by constraint; each component is consumed from [po] as it is said, and one left over is Unhandled."""

    def __init__(self, g: Graph, shape: Node, prefixes: Prefixes, allow_count: bool) -> None:
        self.g, self.prefixes = g, prefixes
        self.po: dict[Node, list[Node]] = {}
        for p, o in g.predicate_objects(shape):
            if p in IGNORED or p in NODE_LEVEL or p == SH.path or str(p).startswith(SKOS_NS):
                continue
            if p in (SH.minCount, SH.maxCount) and allow_count:
                continue
            self.po.setdefault(p, []).append(o)
        self.base: str | None = None
        self.quals: list[str] = []

    def c(self, x: Node) -> str:
        return curie(self.g, x, self.prefixes)

    def offer(self, phrase: str) -> None:
        """[phrase] as the base when there is none yet, else as a qualification."""
        if self.base is None:
            self.base = phrase
        else:
            self.quals.append(phrase)

    def phrase(self) -> str:
        datatypes = [self.c(x) for x in self.po.pop(SH.datatype, [])]
        classes = [self.c(x) for x in self.po.pop(SH["class"], [])]
        kinds = self.po.pop(SH.nodeKind, [])
        alternatives = self.alternatives(datatypes, classes) + self.conjunctions()
        if datatypes:
            self.base = datatype_phrase(datatypes)
        cl = self.classes(classes)
        for k in kinds:
            self.kind(k, cl, datatypes)
        for lst in self.po.pop(SH["in"], []):
            items = members(self.g, lst)
            vals = join([self.c(x) for x in items])
            self.offer(
                f"equal to {vals}" if len(items) == 1 else f"either {vals}" if len(items) == 2 else f"one of {vals}"
            )
        for hv in self.po.pop(SH.hasValue, []):
            self.quals.append(f"including {self.c(hv)}")
        for alt in alternatives:
            if self.base is None:
                self.base = ("either " + alt) if " or " in alt and not alt.startswith("exactly one of") else alt
            else:
                self.quals.append(f"and {alt}")
        self.finite()
        numeric = any(p in self.po for p in (SH.minInclusive, SH.minExclusive, SH.maxInclusive, SH.maxExclusive))
        self.lexical()
        self.nodes()
        self.negations()
        for v in self.po.pop(SH.languageIn, []):
            self.quals.append("in language " + join([str(x) for x in members(self.g, v)]))
        if self.po.pop(SH.uniqueLang, []):
            self.quals.append("with at most one value per language")
        if self.po:
            raise Unhandled(f"components {sorted(self.c(p) for p in self.po)}")
        return self.finish(numeric)

    def alternatives(self, datatypes: list[str], classes: list[str]) -> list[str]:
        """sh:or and sh:xone: a choice of datatypes or classes joins [datatypes] or [classes]; any other is an
        alternative phrase."""
        ors = [(lst, "or") for lst in self.po.pop(SH["or"], [])] + [(lst, "xone") for lst in self.po.pop(SH.xone, [])]
        alternatives = []
        for lst, kind in ors:
            branches = members(self.g, lst)
            singles = [single(self.g, b) for b in branches]
            chosen = [s[1] for s in singles if s is not None]
            if all(s and s[0] == SH.datatype for s in singles):
                datatypes.append(join([self.c(x) for x in chosen]))
            elif all(s and s[0] == SH["class"] for s in singles):
                classes.append(join([self.c(x) for x in chosen]))
            else:
                phrases = [branch_phrase(self.g, b, self.prefixes) for b in branches]
                # An exclusive choice among property-stating branches is said as such.
                if kind == "xone" and len(phrases) > 1 and all(p.startswith("a node that states ") for p in phrases):
                    alternatives.append("exactly one of these: " + "; ".join(p[len("a node that ") :] for p in phrases))
                else:
                    alternatives.append(join(phrases))
        return alternatives

    def conjunctions(self) -> list[str]:
        """sh:and of property-stating branches: everything they state, together."""
        out = []
        for lst in self.po.pop(SH["and"], []):
            collected = []
            for member in members(self.g, lst):
                inner = property_parts(self.g, member, self.prefixes)
                if inner is None:
                    raise Unhandled("sh:and of value shapes")
                collected.extend(inner)
            out.append("a node that states " + join(collected, "and"))
        return out

    def classes(self, classes: list[str]) -> str | None:
        """The sh:class constraint offered as "an instance of" its class; the phrase, or None without one."""
        if not classes:
            return None
        if len(classes) > 1:
            raise Unhandled("several classes")
        cl = f"an instance of {classes[0]}"
        self.offer(cl)
        return cl

    def kind(self, k: Node, cl: str | None, datatypes: list[str]) -> None:
        """One sh:nodeKind, said with the class or datatype it accompanies."""
        if self.base is None:
            self.base = NODEKIND[k]
        elif k == SH.IRI and cl is not None:
            self.base = f"an IRI naming {cl}"
        elif k == SH.Literal and datatypes:
            pass
        elif k == SH.BlankNodeOrIRI and cl is not None:
            self.base = f"a resource (an IRI or a blank node) that is {cl}"
        else:
            self.quals.append(NODEKIND[k].split(" ", 1)[1])

    def finite(self) -> None:
        """The bounds -INF and INF exclusive, with the NaN pattern beside them, said as "finite"."""
        lo_ex = [str(v).lower() for v in self.po.get(SH.minExclusive, [])]
        hi_ex = [str(v).lower() for v in self.po.get(SH.maxExclusive, [])]
        if lo_ex != ["-inf"] or hi_ex != ["inf"]:
            return
        self.po.pop(SH.minExclusive)
        self.po.pop(SH.maxExclusive)
        nots = self.po.get(SH["not"], [])
        self.po[SH["not"]] = [n for n in nots if not str(self.g.value(n, SH.pattern) or "").startswith("^(nan")]
        if not self.po[SH["not"]]:
            self.po.pop(SH["not"])
        self.quals.append("that is finite (not NaN or infinite)")

    def lexical(self) -> None:
        """Numeric bounds, lengths and patterns."""
        for p, word in [
            (SH.minInclusive, "at least"),
            (SH.minExclusive, "greater than"),
            (SH.maxInclusive, "at most"),
            (SH.maxExclusive, "less than"),
        ]:
            for v in self.po.pop(p, []):
                self.quals.append(f"{word} {v}")
        for v in self.po.pop(SH.minLength, []):
            self.quals.append(f"at least {v} character{'s' if _integer(v) != 1 else ''} long")
        for v in self.po.pop(SH.maxLength, []):
            self.quals.append(f"at most {v} characters long")
        flags = self.po.pop(SH.flags, [])
        for v in self.po.pop(SH.pattern, []):
            self.quals.append(f"matching the regular expression {v}" + (f' (flags "{flags[0]}")' if flags else ""))

    def nodes(self) -> None:
        """sh:node: a shared value shape by its phrase, a nested one by what it accepts (or by its own message)."""
        for v in self.po.pop(SH.node, []):
            known = NODE_PHRASES.get(str(v).rsplit("#", 1)[-1]) if isinstance(v, URIRef) else None
            if known and self.base is None:
                self.base = known
            elif isinstance(v, BNode):
                inner = value_phrase(self.g, v, self.prefixes)
                if "a value" in inner:
                    # A node shape built of property shapes or alternatives says nothing as a phrase;
                    # its own message, when it has one, is what the constraint means.
                    stated = self.g.value(v, SH.message)
                    if stated is None:
                        raise Unhandled("nested node shape")
                    raise Stated(str(stated))
                self.quals.append("conforming to " + inner)
            else:
                self.quals.append(f"conforming to {self.c(v)}")

    def negations(self) -> None:
        """sh:not: a prohibition on the properties a branch states, or the value it must not be."""
        for v in self.po.pop(SH["not"], []):
            parts = property_parts(self.g, v, self.prefixes)
            if parts is not None:
                # "not a node that states A and B" reads as a prohibition on each; say what it is.
                self.quals.append(
                    "that does not state "
                    + ("both " if len(parts) == 2 else "all of " if len(parts) > 2 else "")
                    + join(parts, "and")
                )
                if self.base is None:
                    self.base = "a node"
            else:
                self.quals.append("not " + value_phrase(self.g, v, self.prefixes))

    def finish(self, numeric: bool) -> str:
        base = self.base
        if base is None:
            if numeric:
                base = "a number"
            elif self.quals and self.quals[0].startswith("conforming to "):
                return "a value " + ", ".join(self.quals)
            else:
                base = "a value"
        sep = ", " if base.startswith("either ") else " "
        return base + (sep + ", ".join(self.quals) if self.quals else "")


def datatype_phrase(datatypes: list[str]) -> str:
    """The base phrase of an sh:datatype constraint (one datatype, or one choice of datatypes)."""
    if len(datatypes) > 1:
        raise Unhandled("several datatypes")
    names = [x.strip() for x in datatypes[0].replace(" or ", ", ").split(",")]
    if sorted(names) == ["bddo:HelExpression", "xsd:string"]:
        return NODE_PHRASES["HelExpressionValueShape"]
    if len(names) >= 5 and all(n.startswith("xsd:") and ("nteger" in n or n[4:] in INTS) for n in names):
        return "an integer (of any XSD integer datatype)"
    return f"{article(datatypes[0])} {datatypes[0]} literal"


def count_phrase(lo: int | None, hi: int | None) -> str | None:
    if hi == 0:
        return "no value"
    if lo and hi is not None:
        if lo == hi:
            return "exactly one value" if lo == 1 else f"exactly {lo} values"
        return f"between {lo} and {hi} values"
    if lo:
        return "at least one value" if lo == 1 else f"at least {lo} values"
    if hi is not None:
        return "at most one value" if hi == 1 else f"at most {hi} values"
    return None


def message(g: Graph, pshape: Node, prefixes: Prefixes) -> str:
    path = g.value(pshape, SH.path)
    if path is None:
        raise Unhandled("no path")
    phrase, listy = path_phrase(g, path, prefixes)
    lo, hi = _integer(g.value(pshape, SH.minCount)), _integer(g.value(pshape, SH.maxCount))
    extra = [
        (p, o)
        for p, o in g.predicate_objects(pshape)
        if p not in IGNORED and p not in (SH.path, SH.minCount, SH.maxCount)
    ]
    if any(p == SH.qualifiedValueShape for p, _ in extra):
        raise Unhandled("qualified")
    if any(p in (SH.equals, SH.disjoint, SH.lessThan, SH.lessThanOrEquals, SH.property, SH.sparql) for p, _ in extra):
        raise Unhandled("pair/nested")
    try:
        value = value_phrase(g, pshape, prefixes, allow_count=True) if extra else None
    except Stated as stated:
        return stated.text
    count = count_phrase(lo, hi)
    if listy:
        if count:
            raise Unhandled("counted list members")
        return f"Each member of {phrase} is {value}."
    if hi == 0:
        return f"{phrase} must not be stated here."
    if count and value:
        if lo == 1 and hi == 1:
            return f"{phrase} takes exactly one value, {value}."
        return f"{phrase} takes {count}; each is {value}."
    if count:
        return f"{phrase} takes {count}."
    return f"Each value of {phrase} is {value}."


def constrains_value(g: Graph, shape: Node) -> bool:
    """True when a node shape states something about the value itself, beyond activation."""
    return any(
        p not in IGNORED and p not in NODE_LEVEL and not str(p).startswith(SKOS_NS) for p in g.predicates(shape, None)
    )
