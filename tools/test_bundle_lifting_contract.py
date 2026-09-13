"""Executable competency cases for the published bundle lifting query (no inference)."""
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal

ROOT = Path(__file__).resolve().parents[1]
B = Namespace("https://hexplain.io/ns/aspect/bundle#")
SH = Namespace("http://www.w3.org/ns/shacl#")
V = Graph().parse(ROOT / "specification/aspect/bundle/bundle.ttl")
rule = V.value(B.LiftByCarriedAspectRule, SH.rule)
query = str(V.value(rule, SH.construct))
prefix = """@prefix b: <https://hexplain.io/ns/aspect/bundle#> .
@prefix d: <http://purl.org/dc/terms/> .
@prefix r: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix e: <urn:test:> .
"""
base = """e:asset d:conformsTo e:profile .
e:profile b:partSpec e:spec .
e:spec b:partRole e:role ; b:carriesAspect e:aspect .
e:value r:isDefinedBy e:aspect .
"""
cases = [
    ("matching role", 'e:asset b:hasPart e:a. e:a b:partRole e:role; e:value 2.', {2}),
    ("wrong role", 'e:asset b:hasPart e:a. e:a b:partRole e:other; e:value 2.', set()),
    ("conflicts preserved", 'e:asset b:hasPart e:a,e:b. e:a b:partRole e:role; e:value 2. e:b b:partRole e:role; e:value 3.', {2,3}),
    ("duplicates coalesce", 'e:asset b:hasPart e:a,e:b. e:a b:partRole e:role; e:value 2. e:b b:partRole e:role; e:value 2.', {2}),
    ("inverse alone is not materialized", 'e:a b:partOf e:asset; b:partRole e:role; e:value 2.', set()),
    ("primary alone is not materialized", 'e:asset b:primaryPart e:a. e:a b:partRole e:role; e:value 2.', set()),
    ("nested properties not copied", 'e:asset b:hasPart e:a. e:a b:partRole e:role; e:child e:c. e:c e:value 2.', set()),
]
for name, extra, expected in cases:
    data = Graph().parse(data=prefix + base + extra, format="turtle")
    before = set(data)
    result = data.query(query, initBindings={"this": URIRef("urn:test:asset")}).graph
    exact = {(URIRef("urn:test:asset"), URIRef("urn:test:value"), Literal(v)) for v in expected}
    assert set(result) == exact, (name, list(result))
    assert set(data) == before, name
print(f"PASS: {len(cases)} bundle lifting competency cases, exact output graphs, no inference")
