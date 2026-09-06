"""Packaging competency questions with explicit targets, expected paths and no inference.

These test semantic metadata, not ZIP/TAR parsing or safe filesystem extraction.
"""
from rdflib import Graph, Namespace, RDF, URIRef
from pyshacl import validate
import specgraph

P = Namespace('https://hexplain.io/ns/aspect/packaging#')
SH = Namespace('http://www.w3.org/ns/shacl#')
prefix = '@prefix p:<https://hexplain.io/ns/aspect/packaging#>. @prefix a:<https://hexplain.io/ns/archive#>. @prefix f:<https://hexplain.io/ns/aspect/fsmeta#>. '
ont = specgraph.ontologies()
cases = [
    ('empty container', '<urn:c> a p:Container.', True, None),
    ('unnamed box entry', '<urn:c> p:hasEntry <urn:e>. <urn:e> a p:Entry.', True, None),
    ('duplicate archive paths retain separate identities', '<urn:c> p:hasEntry <urn:e>,<urn:f>. <urn:e> a p:Entry; p:entryPath "same". <urn:f> a p:Entry; p:entryPath "same".', True, None),
    ('verbatim path is not extraction authorization', '<urn:e> a p:Entry; p:entryPath "../outside".', True, None),
    ('literal member', '<urn:c> p:hasEntry "entry".', False, P.hasEntry),
    ('missing member type under no inference', '<urn:c> p:hasEntry <urn:e>.', False, P.hasEntry),
    ('path must be text', '<urn:e> p:entryPath 42.', False, P.entryPath),
    ('one entry cannot have conflicting paths', '<urn:e> a p:Entry; p:entryPath "one", "two".', False, P.entryPath),
    ('archive specialization accepts its own entry subtype', '<urn:c> a a:Archive; p:hasEntry <urn:e>. <urn:e> a a:ArchiveEntry.', True, None),
    ('archive specialization rejects generic entry', '<urn:c> a a:Archive; p:hasEntry <urn:e>. <urn:e> a p:Entry.', False, P.hasEntry),
    ('generic filename does not activate archive cardinality', '<urn:f> f:fileName "alias-one", "alias-two".', True, None),
]
for name, ttl, expected, path in cases:
    data = Graph().parse(data=prefix + ttl, format='turtle')
    actual, report, detail = validate(ont + data, shacl_graph=ont, inference='none', advanced=True)
    assert bool(actual) == expected, (name, detail)
    if path:
        assert path in set(report.objects(None, SH.resultPath)), (name, detail)
print(f'PASS: {len(cases)} packaging competency cases with constraint-path assertions')
