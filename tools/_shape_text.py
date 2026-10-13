"""Plain-English statements of what a SHACL shape checks, read from its constraints.

message() states a property shape's whole contract as one sentence -- the text of the sh:message
the family's reported property shapes carry (tools/test_shape_messages.py). value_phrase() says
what a conforming value is; the term reference uses it to define a value shape (IntegerValueShape,
FiniteDoubleShape) whose source gives no rdfs:comment. Both raise Unhandled rather than guess
when a shape uses a construct they cannot state faithfully; such a shape needs editorial text.
"""

from __future__ import annotations

import re
from typing import Any

from rdflib import RDF, RDFS, BNode, Literal, Namespace, URIRef
from rdflib.collection import Collection

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


#: How an exclusive choice among property-stating branches opens ("Each focus node is a node that
#: states exactly one of: A; B; C").
EXACTLY_ONE = "a node that states exactly one of: "


class Unhandled(Exception):
    pass


class Stated(Unhandled):
    """The constraint is best described by the message a nested shape already states."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


def curie(g: Any, node: Any, prefixes: Any) -> Any:
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


def article(word: Any) -> Any:
    return "an" if word[:1].lower() in "aeiou" or word.startswith(("xsd:", "rdf:", "rdfs:", "owl:", "hxf:")) else "a"


def join(items: Any, conj: str = "or") -> Any:
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" {conj} " + items[-1]


def members(g: Any, node: Any) -> Any:
    return list(Collection(g, node))


def path_phrase(g: Any, path: Any, prefixes: Any) -> Any:
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


NODEKIND = {
    SH.IRI: "an IRI",
    SH.BlankNode: "a blank node",
    SH.BlankNodeOrIRI: "a resource (an IRI or a blank node)",
    SH.Literal: "a literal",
    SH.IRIOrLiteral: "an IRI or a literal",
    SH.BlankNodeOrLiteral: "a blank node or a literal",
}


def single(g: Any, shape: Any) -> Any:
    """The one (predicate, object) of a branch shape, or None."""
    po = [(p, o) for p, o in g.predicate_objects(shape) if p not in IGNORED and not str(p).startswith(SKOS_NS)]
    return po[0] if len(po) == 1 else None


def property_parts(g: Any, shape: Any, prefixes: Any) -> Any:
    """What a shape built of property shapes (and sh:and of such shapes) says the focus node states.

    Returns the list of phrases, one per property shape ("bddo:coversFromField", "no bddo:keyPath",
    "bddo:whitespaceSeparated true", "exactly one bddo:key"), or None when the shape is not such a
    shape. A logical branch of this kind used to be rendered as "a value", which made an sh:xone of
    two branches read "either a value or a value".
    """
    parts = []
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
        path = g.value(ps, SH.path)
        if path is None:
            raise Unhandled("branch property without a path")
        name, _listy = path_phrase(g, path, prefixes)
        lo = g.value(ps, SH.minCount)
        hi = g.value(ps, SH.maxCount)
        lo = int(lo) if lo is not None else None
        hi = int(hi) if hi is not None else None
        hv = g.value(ps, SH.hasValue)
        if any(
            p not in IGNORED and p not in (SH.path, SH.minCount, SH.maxCount, SH.hasValue)
            for p in g.predicates(ps, None)
        ):
            # The branch also constrains the value: say what it accepts, in parentheses.
            name = f"{name} ({value_phrase(g, ps, prefixes, allow_count=True)})"
        if hv is not None:
            parts.append(f"{name} {curie(g, hv, prefixes)}")
        elif hi == 0:
            parts.append(f"no {name}")
        elif lo and hi is not None and lo == hi:
            parts.append(f"exactly one {name}" if lo == 1 else f"exactly {lo} {name}")
        elif lo:
            parts.append(name if lo == 1 else f"at least {lo} {name}")
        elif hi is not None:
            parts.append(f"at most {hi} {name}")
        else:
            parts.append(name)
    return parts


def branch_phrase(g: Any, shape: Any, prefixes: Any) -> Any:
    """A logical branch as a noun phrase: by the properties it states, else by its value constraints."""
    parts = property_parts(g, shape, prefixes)
    if parts is not None:
        return "a node that states " + join(parts, "and")
    return value_phrase(g, shape, prefixes)


#: Constraint parameters that state one thing together, and are therefore one conjunct of a negation.
CONJUNCT_GROUPS = (
    frozenset({SH.datatype, SH["class"], SH.nodeKind}),
    frozenset({SH.minInclusive, SH.minExclusive, SH.maxInclusive, SH.maxExclusive}),
    frozenset({SH.pattern, SH.flags}),
    frozenset({SH.minLength, SH.maxLength}),
)


def conjuncts(g: Any, shape: Any) -> list[frozenset[Any]]:
    """The constraints of a value shape as the separate things it demands, in a stable order."""
    stated = {
        p
        for p in g.predicates(shape, None)
        if p not in IGNORED and p not in NODE_LEVEL and p != SH.path and not str(p).startswith(SKOS_NS)
    }
    groups = [group & stated for group in CONJUNCT_GROUPS if group & stated]
    grouped = set().union(*groups) if groups else set()
    return groups + [frozenset({p}) for p in sorted(stated - grouped, key=str)]


def negation(g: Any, shape: Any, prefixes: Any) -> str:
    """What sh:not of a value shape demands.

    A shape with several constraints is their conjunction, and its negation forbids only their
    holding TOGETHER: "not both an instance of X and one of A, B or C". Rendering the conjunction
    as one phrase and prefixing "not" read as "not an instance of X one of A, B or C".
    """
    parts = [value_phrase(g, shape, prefixes, only=group) for group in conjuncts(g, shape)]
    if len(parts) < 2:
        return "not " + value_phrase(g, shape, prefixes)
    return "not " + ("both " if len(parts) == 2 else "all of ") + join(parts, "and")


def conjunction(g: Any, shapes: list[Any], prefixes: Any) -> str:
    """sh:and of value shapes: the first says what the value is, the others qualify it.

    ( x:IntegerValueShape [ sh:minExclusive 0 ] ) reads "an integer (of any XSD integer datatype)
    greater than 0". A later member must be a pure qualification ("a number ...", "a value ...").
    """
    phrases = []
    for member in shapes:
        known = NODE_PHRASES.get(str(member).rsplit("#", 1)[-1]) if isinstance(member, URIRef) else None
        phrases.append(known or value_phrase(g, member, prefixes))
    head, rest = phrases[0], []
    for phrase in phrases[1:]:
        for opener in ("a number ", "a value "):
            if phrase.startswith(opener):
                rest.append(phrase[len(opener) :])
                break
        else:
            raise Unhandled("sh:and member that is not a qualification")
    return head + (" " + ", ".join(rest) if rest else "")


def value_phrase(
    g: Any, shape: Any, prefixes: Any, allow_count: bool = False, only: frozenset[Any] | None = None
) -> Any:
    """A noun phrase describing an acceptable value; raises Unhandled for what it cannot say.

    ``only`` restricts the phrase to those constraint parameters of the shape (one conjunct).
    """
    po = {}
    for p, o in g.predicate_objects(shape):
        if p in IGNORED or p in NODE_LEVEL or p == SH.path or str(p).startswith(SKOS_NS):
            continue
        if only is not None and p not in only:
            continue
        if p in (SH.minCount, SH.maxCount) and allow_count:
            continue
        po.setdefault(p, []).append(o)

    def c(x):
        return curie(g, x, prefixes)

    base, quals = None, []
    datatypes = [c(x) for x in po.pop(SH.datatype, [])]
    classes = [c(x) for x in po.pop(SH["class"], [])]
    kinds = po.pop(SH.nodeKind, [])
    ors = [(lst, "or") for lst in po.pop(SH["or"], [])] + [(lst, "xone") for lst in po.pop(SH.xone, [])]
    alternatives, conjunctions = [], []
    for lst, kind in ors:
        branches = members(g, lst)
        singles = [single(g, b) for b in branches]
        if all(s and s[0] == SH.datatype for s in singles):
            datatypes.append(join([c(s[1]) for s in singles]))
        elif all(s and s[0] == SH["class"] for s in singles):
            classes.append(join([c(s[1]) for s in singles]))
        else:
            phrases = [branch_phrase(g, b, prefixes) for b in branches]
            # An exclusive choice among property-stating branches is said as such.
            if kind == "xone" and len(phrases) > 1 and all(p.startswith("a node that states ") for p in phrases):
                stated = "; ".join(p[len("a node that states ") :] for p in phrases)
                alternatives.append(EXACTLY_ONE + stated)
            else:
                alternatives.append(join(phrases))
    # sh:and of property-stating branches: everything they state, together.
    for lst in po.pop(SH["and"], []):
        collected = []
        for member in members(g, lst):
            inner = property_parts(g, member, prefixes)
            if inner is None:
                collected = None
                break
            collected.extend(inner)
        if collected is None:
            conjunctions.append(conjunction(g, members(g, lst), prefixes))
        else:
            alternatives.append("a node that states " + join(collected, "and"))
    if datatypes:
        if len(datatypes) > 1:
            raise Unhandled("several datatypes")
        names = [x.strip() for x in datatypes[0].replace(" or ", ", ").split(",")]
        if sorted(names) == ["bddo:HelExpression", "xsd:string"]:
            base = NODE_PHRASES["HelExpressionValueShape"]
        elif len(names) >= 5 and all(n.startswith("xsd:") and ("nteger" in n or n[4:] in INTS) for n in names):
            base = "an integer (of any XSD integer datatype)"
        else:
            base = f"{article(datatypes[0])} {datatypes[0]} literal"
    if classes:
        if len(classes) > 1:
            raise Unhandled("several classes")
        cl = f"an instance of {classes[0]}"
        if base is None:
            base = cl
        else:
            quals.append(cl)
    for k in kinds:
        if base is None:
            base = NODEKIND[k]
        elif k == SH.IRI and classes:
            base = f"an IRI naming {cl}"
        elif k == SH.Literal and datatypes:
            pass
        elif k == SH.BlankNodeOrIRI and classes:
            base = f"a resource (an IRI or a blank node) that is {cl}"
        else:
            quals.append(NODEKIND[k].split(" ", 1)[1])
    ins = po.pop(SH["in"], [])
    for lst in ins:
        items = members(g, lst)
        vals = join([c(x) for x in items])
        phrase = f"equal to {vals}" if len(items) == 1 else f"either {vals}" if len(items) == 2 else f"one of {vals}"
        if base is None:
            base = phrase
        else:
            quals.append(phrase)
    for hv in po.pop(SH.hasValue, []):
        quals.append(f"including {c(hv)}")
    for alt in alternatives:
        if base is None:
            base = ("either " + alt) if " or " in alt and not alt.startswith(EXACTLY_ONE) else alt
        else:
            quals.append(f"and {alt}")
    for phrase in conjunctions:
        if base is None:
            base = phrase
        else:
            quals.append(f"and {phrase}")
    lo_ex = [str(v).lower() for v in po.get(SH.minExclusive, [])]
    hi_ex = [str(v).lower() for v in po.get(SH.maxExclusive, [])]
    if lo_ex == ["-inf"] and hi_ex == ["inf"]:
        po.pop(SH.minExclusive)
        po.pop(SH.maxExclusive)
        nots = po.get(SH["not"], [])
        po[SH["not"]] = [n for n in nots if not str(g.value(n, SH.pattern) or "").startswith("^(nan")]
        if not po[SH["not"]]:
            po.pop(SH["not"])
        quals.append("that is finite (not NaN or infinite)")
    numeric = any(p in po for p in (SH.minInclusive, SH.minExclusive, SH.maxInclusive, SH.maxExclusive))
    for p, word in [
        (SH.minInclusive, "at least"),
        (SH.minExclusive, "greater than"),
        (SH.maxInclusive, "at most"),
        (SH.maxExclusive, "less than"),
    ]:
        for v in po.pop(p, []):
            quals.append(f"{word} {v}")
    for v in po.pop(SH.minLength, []):
        quals.append(f"at least {v} character{'s' if int(v) != 1 else ''} long")
    for v in po.pop(SH.maxLength, []):
        quals.append(f"at most {v} characters long")
    flags = po.pop(SH.flags, [])
    for v in po.pop(SH.pattern, []):
        quals.append(f"matching the regular expression {v}" + (f' (flags "{flags[0]}")' if flags else ""))
    for v in po.pop(SH.node, []):
        known = NODE_PHRASES.get(str(v).rsplit("#", 1)[-1]) if isinstance(v, URIRef) else None
        if known and base is None:
            base = known
        elif isinstance(v, BNode):
            inner = value_phrase(g, v, prefixes)
            if "a value" in inner:
                # A node shape built of property shapes or alternatives says nothing as a phrase;
                # its own message, when it has one, is what the constraint means.
                stated = g.value(v, SH.message)
                if stated is None:
                    raise Unhandled("nested node shape")
                raise Stated(str(stated))
            quals.append("conforming to " + inner)
        else:
            quals.append(f"conforming to {c(v)}")
    for v in po.pop(SH["not"], []):
        parts = property_parts(g, v, prefixes)
        if parts is not None:
            # "not a node that states A and B" reads as a prohibition on each; say what it is.
            quals.append(
                "that does not state "
                + ("both " if len(parts) == 2 else "all of " if len(parts) > 2 else "")
                + join(parts, "and")
            )
            if base is None:
                base = "a node"
        else:
            quals.append(negation(g, v, prefixes))
    for v in po.pop(SH.languageIn, []):
        quals.append("in language " + join([str(x) for x in members(g, v)]))
    if po.pop(SH.uniqueLang, []):
        quals.append("with at most one value per language")
    if po:
        raise Unhandled(f"components {sorted(c(p) for p in po)}")
    if base is None:
        if numeric:
            base = "a number"
        elif quals and quals[0].startswith("conforming to "):
            return "a value " + ", ".join(quals)
        elif quals and all(q.startswith("not ") for q in quals):
            # Nothing but prohibitions: "is not an instance of X", never "is a value not an instance of X".
            return " and ".join(quals)
        else:
            base = "a value"
    quals = ["that is " + q if q.startswith("not ") else q for q in quals]
    sep = ", " if base.startswith("either ") else " "
    return base + (sep + ", ".join(quals) if quals else "")


def count_phrase(lo: Any, hi: Any) -> Any:
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


def message(g: Any, pshape: Any, prefixes: Any) -> Any:
    path = g.value(pshape, SH.path)
    if path is None:
        raise Unhandled("no path")
    phrase, listy = path_phrase(g, path, prefixes)
    lo = g.value(pshape, SH.minCount)
    hi = g.value(pshape, SH.maxCount)
    lo = int(lo) if lo is not None else None
    hi = int(hi) if hi is not None else None
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


def constrains_value(g: Any, shape: Any) -> Any:
    """True when a node shape states something about the value itself, beyond activation."""
    return any(
        p not in IGNORED and p not in NODE_LEVEL and not str(p).startswith(SKOS_NS) for p in g.predicates(shape, None)
    )
