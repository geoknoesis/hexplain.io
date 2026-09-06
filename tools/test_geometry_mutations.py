"""Check that geometry counterexamples actually detect removed property constraints."""
from pathlib import Path
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
root=Path(__file__).resolve().parents[1]
sh=Namespace('http://www.w3.org/ns/shacl#')
g=Namespace('https://hexplain.io/ns/aspect/geometry#')
original=Graph().parse(root/'specification/aspect/geometry/geometry.ttl')
for path,value in [(g.dimensionality,'-2'),(g.geometryType,'"Point"')]:
    data=Graph().parse(data=f'<urn:subject> <{path}> {value}.',format='turtle')
    assert not validate(data,shacl_graph=original,inference='none')[0]
    mutated=Graph()
    for triple in original:mutated.add(triple)
    removed=0
    for property_shape in list(mutated.subjects(sh.path,path)):
        for owner in list(mutated.subjects(sh.property,property_shape)):
            mutated.remove((owner,sh.property,property_shape));removed+=1
    assert removed, f'No property constraint found for {path}'
    assert validate(data,shacl_graph=mutated,inference='none')[0],f'Mutation was not isolated for {path}'
print('PASS: 2 geometry property-constraint mutations detected by independent invalid-data assertions')
