"""Range contracts: every XSD rdfs:range, both ways, wherever the property is used.

Expectations come from the ontology's rdfs:range axioms and the XSD value spaces, not from the
shapes: a value of the range's datatype family inside its bounds must conform, and a value of
an unrelated datatype, one below the lower bound or one above the upper bound must not. The
shapes are consulted only to route each case to the module file whose shape activates it.
Each case is a single triple on an otherwise empty subject, so it also proves that activation
does not depend on the subject's type.
"""
import json
from pathlib import Path

from rdflib import RDFS, Graph

ROOT = Path(__file__).resolve().parents[1]
XSD = 'http://www.w3.org/2001/XMLSchema#'
FAMILY = ('integer positiveInteger nonNegativeInteger int long unsignedInt unsignedLong short '
          'unsignedShort byte unsignedByte').split()
INTEGER_RANGES = set(FAMILY) | {'negativeInteger', 'nonPositiveInteger'}
BOUNDS = {'positiveInteger': (1, None), 'nonNegativeInteger': (0, None), 'negativeInteger': (None, -1),
          'nonPositiveInteger': (None, 0), 'unsignedLong': (0, 18446744073709551615),
          'unsignedInt': (0, 4294967295), 'unsignedShort': (0, 65535), 'unsignedByte': (0, 255),
          'long': (-9223372036854775808, 9223372036854775807), 'int': (-2147483648, 2147483647),
          'short': (-32768, 32767), 'byte': (-128, 127)}
# A conforming value and a value of an unrelated datatype, per non-integer range.
LITERALS = {
    'decimal': ('1.5', '"1.5"'), 'double': (f'"1.5"^^<{XSD}double>', '1.5'),
    'float': (f'"1.5"^^<{XSD}float>', '1.5'), 'string': ('"text"', '1'),
    'boolean': ('true', '"true"'), 'hexBinary': (f'"00"^^<{XSD}hexBinary>', '"00"'),
    'dateTime': (f'"2026-09-08T00:00:00Z"^^<{XSD}dateTime>', '"2026-09-08"'),
    'date': (f'"2026-09-08"^^<{XSD}date>', f'"2026-09-08T00:00:00Z"^^<{XSD}dateTime>'),
    'anyURI': (f'"https://example.org/"^^<{XSD}anyURI>', '1'), 'language': (f'"en"^^<{XSD}language>', '1'),
}
SUBJECT = '<urn:range-contract:f>'


def _routes():
    """property -> module file whose subjects-of shape states its datatype."""
    from _range_datatypes import allowed_datatypes, SH
    files = json.loads((ROOT/'specification/family.json').read_text(encoding='utf-8'))['files']
    routes, narrowed = {}, set()
    for rel in files:
        g = Graph().parse(data=(ROOT/'specification'/rel).read_text(encoding='utf-8'), format='turtle')
        for shape, prop in g.subject_objects(SH.targetSubjectsOf):
            # Only the range shapes: properties that other shapes also constrain are witnessed by
            # those shapes' own authored cases, and may legitimately narrow the range further.
            if not str(shape).endswith('#RangeDatatypeShape'):
                continue
            for pshape in g.objects(shape, SH.property):
                if g.value(pshape, SH.path) == prop and allowed_datatypes(g, pshape) is not None:
                    routes.setdefault(prop, 'specification/'+rel)
        # A property another shape restricts to particular values or datatypes may be narrower
        # than its range (bddo:numericBase is one of 8, 10 or 16): the range's rejections still
        # hold for it, but an arbitrary in-range value is not necessarily accepted.
        narrowing = [SH[c] for c in ('in', 'hasValue', 'datatype', 'or', 'xone', 'and', 'node', 'class', 'pattern', 'not')]
        # Only this file's shapes matter: a case is validated against its module alone.
        for pshape in set(g.objects(None, SH.property)):
            if any(str(o).endswith('#RangeDatatypeShape') for o in g.subjects(SH.property, pshape)):
                continue
            if any((pshape, c, None) in g for c in narrowing):
                narrowed.add((g.value(pshape, SH.path), 'specification/'+rel))
    return routes, narrowed


def cases():
    import specgraph
    g = specgraph.ontologies()
    routes, narrowed = _routes()
    rows = []

    def add(name, module, prop, value, expected):
        if expected and (prop, module) in narrowed:
            return
        rows.append(dict(name='range '+name, module=module, expected=expected,
                         path='' if expected else str(prop), data=f'{SUBJECT} <{prop}> {value} .'))
    witnessed = set()
    for prop, range_ in sorted(g.subject_objects(RDFS.range)):
        if not str(range_).startswith(XSD) or prop not in routes:
            continue
        module, kind, label = routes[prop], str(range_)[len(XSD):], g.namespace_manager.normalizeUri(prop)
        if kind in INTEGER_RANGES:
            low, high = BOUNDS.get(kind, (None, None))
            good = 1 if (low is None or low <= 1) and (high is None or high >= 1) else low
            add(f'{label} accepts an integer', module, prop, good, True)
            add(f'{label} rejects a string', module, prop, '"x"', False)
            add(f'{label} rejects a decimal', module, prop, '1.5', False)
            if low is not None:
                add(f'{label} rejects {low - 1}', module, prop, low - 1, False)
            if high is not None:
                add(f'{label} rejects {high + 1}', module, prop, high + 1, False)
            # Each integer-family alternative once per module, on the first integer property.
            if module not in witnessed and (prop, module) not in narrowed and (low is None or low <= 1) and (high is None or high >= 1):
                witnessed.add(module)
                for datatype in FAMILY:
                    add(f'{label} accepts xsd:{datatype}', module, prop, f'"1"^^<{XSD}{datatype}>', True)
        elif kind in LITERALS:
            good, bad = LITERALS[kind]
            add(f'{label} accepts xsd:{kind}', module, prop, good, True)
            add(f'{label} rejects another datatype', module, prop, bad, False)
            if kind == 'decimal':
                add(f'{label} accepts an integer', module, prop, 2, True)
                if module not in witnessed and (prop, module) not in narrowed:
                    witnessed.add(module)
                    for datatype in FAMILY:
                        add(f'{label} accepts xsd:{datatype}', module, prop, f'"1"^^<{XSD}{datatype}>', True)
            if kind == 'double':
                add(f'{label} accepts xsd:float', module, prop, f'"1.5"^^<{XSD}float>', True)
    return rows
