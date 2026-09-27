"""Plain-English statements of what a SHACL shape checks, read from its constraints.

message() states a property shape's whole contract as one sentence -- the text of the sh:message
the family's reported property shapes carry (tools/test_shape_messages.py). value_phrase() says
what a conforming value is; the term reference uses it to define a value shape (IntegerValueShape,
FiniteDoubleShape) whose source gives no rdfs:comment. Both raise Unhandled rather than guess
when a shape uses a construct they cannot state faithfully; such a shape needs editorial text.
"""
import re

from rdflib import BNode, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.collection import Collection

SH = Namespace('http://www.w3.org/ns/shacl#')
SKOS_NS = 'http://www.w3.org/2004/02/skos/core#'
#: A SPARQL result variable in a message template: {?x} or {$x}.
PLACEHOLDER = re.compile(r'\{[?$][A-Za-z_]\w*\}')
IGNORED = {SH.order, SH.description, SH.name, SH.severity, SH.deactivated, SH.message, SH.group,
           SH.defaultValue, RDF.type, RDFS.label, RDFS.comment, RDFS.isDefinedBy, RDFS.seeAlso}
#: What a node shape states besides the value it accepts: its activation, its property shapes and
#: SPARQL constraints (described by their own messages), closure and rules.
NODE_LEVEL = {SH.targetClass, SH.targetSubjectsOf, SH.targetObjectsOf, SH.targetNode, SH.target, SH.property,
              SH.sparql, SH.closed, SH.ignoredProperties, SH.rule, SH.prefixes, SH.declare}


INTS = {'int', 'long', 'short', 'byte', 'unsignedInt', 'unsignedLong', 'unsignedShort', 'unsignedByte'}


#: Shared value shapes whose meaning is better said than named.
NODE_PHRASES = {
    'HelExpressionValueShape': 'a HEL expression (an xsd:string or bddo:HelExpression literal)',
    'FiniteDoubleShape': 'a finite number (an xsd:double or xsd:float literal, not NaN or infinite)',
    'IntegerValueShape': 'an integer (of any XSD integer datatype)',
    'FloatValueShape': 'an xsd:double or xsd:float literal',
}


class Unhandled(Exception):
    pass


def curie(g, node, prefixes):
    if isinstance(node, Literal):
        if node.datatype is None or str(node.datatype).endswith('#string'):
            return f'"{node}"'
        return str(node)
    s = str(node)
    best = None
    for p, ns in prefixes.items():
        if p and s.startswith(ns) and (best is None or len(ns) > len(prefixes[best])):
            best = p
    if best is None:
        return f'<{s}>'
    return f'{best}:{s[len(prefixes[best]):]}'


def article(word):
    return 'an' if word[:1].lower() in 'aeiou' or word.startswith(('xsd:', 'rdf:', 'rdfs:', 'owl:', 'hxf:')) else 'a'


def join(items, conj='or'):
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ', '.join(items[:-1]) + f' {conj} ' + items[-1]


def members(g, node):
    return list(Collection(g, node))


def path_phrase(g, path, prefixes):
    """(phrase, plural_member) -- plural_member True when the path reaches list members."""
    if isinstance(path, URIRef):
        return curie(g, path, prefixes), False
    if (path, RDF.first, None) in g:
        steps = members(g, path)
        # ( P [ sh:zeroOrMorePath rdf:rest ] rdf:first ): the members of the list P points to
        if (len(steps) == 3 and isinstance(steps[0], URIRef) and steps[2] == RDF.first
                and g.value(steps[1], SH.zeroOrMorePath) == RDF.rest):
            return f'the {curie(g, steps[0], prefixes)} list', True
        if (len(steps) == 2 and g.value(steps[0], SH.zeroOrMorePath) == RDF.rest and steps[1] == RDF.first):
            return 'the list', True
        parts = []
        for s in steps:
            if isinstance(s, URIRef):
                parts.append(curie(g, s, prefixes))
            else:
                raise Unhandled('complex sequence step')
        return '/'.join(parts), False
    inv = g.value(path, SH.inversePath)
    if inv is not None:
        return f'the inverse of {curie(g, inv, prefixes)}', False
    alt = g.value(path, SH.alternativePath)
    if alt is not None:
        return join([curie(g, x, prefixes) for x in members(g, alt)]), False
    raise Unhandled('path')


NODEKIND = {SH.IRI: 'an IRI', SH.BlankNode: 'a blank node', SH.BlankNodeOrIRI: 'a resource (an IRI or a blank node)',
            SH.Literal: 'a literal', SH.IRIOrLiteral: 'an IRI or a literal', SH.BlankNodeOrLiteral: 'a blank node or a literal'}


def single(g, shape):
    """The one (predicate, object) of a branch shape, or None."""
    po = [(p, o) for p, o in g.predicate_objects(shape) if p not in IGNORED and not str(p).startswith(SKOS_NS)]
    return po[0] if len(po) == 1 else None


def value_phrase(g, shape, prefixes, allow_count=False):
    """A noun phrase describing an acceptable value; raises Unhandled for what it cannot say."""
    po = {}
    for p, o in g.predicate_objects(shape):
        if p in IGNORED or p in NODE_LEVEL or p == SH.path or str(p).startswith(SKOS_NS):
            continue
        if p in (SH.minCount, SH.maxCount) and allow_count:
            continue
        po.setdefault(p, []).append(o)
    c = lambda x: curie(g, x, prefixes)
    base, quals = None, []
    datatypes = [c(x) for x in po.pop(SH.datatype, [])]
    classes = [c(x) for x in po.pop(SH['class'], [])]
    kinds = po.pop(SH.nodeKind, [])
    ors = po.pop(SH['or'], []) + po.pop(SH.xone, [])
    alternatives = []
    for lst in ors:
        branches = members(g, lst)
        singles = [single(g, b) for b in branches]
        if all(s and s[0] == SH.datatype for s in singles):
            datatypes.append(join([c(s[1]) for s in singles]))
        elif all(s and s[0] == SH['class'] for s in singles):
            classes.append(join([c(s[1]) for s in singles]))
        else:
            alternatives.append(join([value_phrase(g, b, prefixes) for b in branches]))
    if datatypes:
        if len(datatypes) > 1:
            raise Unhandled('several datatypes')
        names = [x.strip() for x in datatypes[0].replace(' or ', ', ').split(',')]
        if sorted(names) == ['bddo:HelExpression', 'xsd:string']:
            base = NODE_PHRASES['HelExpressionValueShape']
        elif len(names) >= 5 and all(n.startswith('xsd:') and ('nteger' in n or n[4:] in INTS) for n in names):
            base = 'an integer (of any XSD integer datatype)'
        else:
            base = f'{article(datatypes[0])} {datatypes[0]} literal'
    if classes:
        if len(classes) > 1:
            raise Unhandled('several classes')
        cl = f'an instance of {classes[0]}'
        if base is None:
            base = cl
        else:
            quals.append(cl)
    for k in kinds:
        if base is None:
            base = NODEKIND[k]
        elif k == SH.IRI and classes:
            base = f'an IRI naming {cl}'
        elif k == SH.Literal and datatypes:
            pass
        elif k == SH.BlankNodeOrIRI and classes:
            base = f'a resource (an IRI or a blank node) that is {cl}'
        else:
            quals.append(NODEKIND[k].split(' ', 1)[1])
    ins = po.pop(SH['in'], [])
    for lst in ins:
        items = members(g, lst)
        vals = join([c(x) for x in items])
        phrase = f'equal to {vals}' if len(items) == 1 else f'one of {vals}'
        if base is None:
            base = phrase
        else:
            quals.append(phrase)
    for hv in po.pop(SH.hasValue, []):
        quals.append(f'including {c(hv)}')
    for alt in alternatives:
        if base is None:
            base = ('either ' + alt) if ' or ' in alt else alt
        else:
            quals.append(f'and {alt}')
    lo_ex = [str(v) for v in po.get(SH.minExclusive, [])]; hi_ex = [str(v) for v in po.get(SH.maxExclusive, [])]
    if lo_ex == ['-INF'] and hi_ex == ['INF']:
        po.pop(SH.minExclusive); po.pop(SH.maxExclusive)
        nots = po.get(SH['not'], [])
        po[SH['not']] = [n for n in nots if not str(g.value(n, SH.pattern) or '').startswith('^(nan')]
        if not po[SH['not']]:
            po.pop(SH['not'])
        quals.append('that is finite (not NaN or infinite)')
    numeric = any(p in po for p in (SH.minInclusive, SH.minExclusive, SH.maxInclusive, SH.maxExclusive))
    for p, word in [(SH.minInclusive, 'at least'), (SH.minExclusive, 'greater than'),
                    (SH.maxInclusive, 'at most'), (SH.maxExclusive, 'less than')]:
        for v in po.pop(p, []):
            quals.append(f'{word} {v}')
    for v in po.pop(SH.minLength, []):
        quals.append(f'at least {v} character{"s" if int(v) != 1 else ""} long')
    for v in po.pop(SH.maxLength, []):
        quals.append(f'at most {v} characters long')
    flags = po.pop(SH.flags, [])
    for v in po.pop(SH.pattern, []):
        quals.append(f'matching the regular expression {v}' + (f' (flags "{flags[0]}")' if flags else ''))
    for v in po.pop(SH.node, []):
        known = NODE_PHRASES.get(str(v).rsplit('#', 1)[-1]) if isinstance(v, URIRef) else None
        if known and base is None:
            base = known
        elif isinstance(v, BNode):
            quals.append('conforming to ' + value_phrase(g, v, prefixes))
        else:
            quals.append(f'conforming to {c(v)}')
    for v in po.pop(SH['not'], []):
        quals.append('not ' + value_phrase(g, v, prefixes))
    for v in po.pop(SH.languageIn, []):
        quals.append('in language ' + join([str(x) for x in members(g, v)]))
    if po.pop(SH.uniqueLang, []):
        quals.append('with at most one value per language')
    if po:
        raise Unhandled(f'components {sorted(c(p) for p in po)}')
    if base is None:
        if numeric:
            base = 'a number'
        elif quals and quals[0].startswith('conforming to '):
            return 'a value ' + ', '.join(quals)
        else:
            base = 'a value'
    sep = ', ' if base.startswith('either ') else ' '
    return base + (sep + ', '.join(quals) if quals else '')


def count_phrase(lo, hi):
    if hi == 0:
        return 'no value'
    if lo and hi is not None:
        if lo == hi:
            return 'exactly one value' if lo == 1 else f'exactly {lo} values'
        return f'between {lo} and {hi} values'
    if lo:
        return 'at least one value' if lo == 1 else f'at least {lo} values'
    if hi is not None:
        return 'at most one value' if hi == 1 else f'at most {hi} values'
    return None


def message(g, pshape, prefixes):
    path = g.value(pshape, SH.path)
    if path is None:
        raise Unhandled('no path')
    phrase, listy = path_phrase(g, path, prefixes)
    lo = g.value(pshape, SH.minCount); hi = g.value(pshape, SH.maxCount)
    lo = int(lo) if lo is not None else None; hi = int(hi) if hi is not None else None
    extra = [(p, o) for p, o in g.predicate_objects(pshape) if p not in IGNORED and p not in (SH.path, SH.minCount, SH.maxCount)]
    if any(p == SH.qualifiedValueShape for p, _ in extra):
        raise Unhandled('qualified')
    if any(p in (SH.equals, SH.disjoint, SH.lessThan, SH.lessThanOrEquals, SH.property, SH.sparql) for p, _ in extra):
        raise Unhandled('pair/nested')
    value = value_phrase(g, pshape, prefixes, allow_count=True) if extra else None
    count = count_phrase(lo, hi)
    if listy:
        if count:
            raise Unhandled('counted list members')
        return f'Each member of {phrase} is {value}.'
    if hi == 0:
        return f'{phrase} must not be stated here.'
    if count and value:
        if lo == 1 and hi == 1:
            return f'{phrase} takes exactly one value, {value}.'
        return f'{phrase} takes {count}; each is {value}.'
    if count:
        return f'{phrase} takes {count}.'
    return f'Each value of {phrase} is {value}.'


def constrains_value(g, shape):
    """True when a node shape states something about the value itself, beyond activation."""
    return any(p not in IGNORED and p not in NODE_LEVEL and not str(p).startswith(SKOS_NS)
               for p in g.predicates(shape, None))
