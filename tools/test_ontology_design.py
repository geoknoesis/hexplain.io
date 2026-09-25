"""Guard ontology/controlled-vocabulary separation and new module hygiene."""
import re
from rdflib import RDF,RDFS,OWL,Namespace,URIRef
from pyshacl import validate
import specgraph

g=specgraph.ontologies(); SKOS=Namespace('http://www.w3.org/2004/02/skos/core#')
types={OWL.Class,OWL.ObjectProperty,OWL.DatatypeProperty,OWL.AnnotationProperty}
# A SKOS mapping relates two concepts. Neither end may be an ontology entity: not a class,
# property or OWL individual this family defines, and not a term of an OWL ontology outside it
# (Simple Features, GeoSPARQL, PROV, SOSA/SSN, RDF/RDFS/OWL), whose terms are classes and
# properties -- rgeo:Point skos:closeMatch sf:Point related a concept to a class.
OWL_NAMESPACES=('http://www.opengis.net/ont/sf#','http://www.opengis.net/ont/geosparql#','http://www.w3.org/ns/prov#',
    'http://www.w3.org/ns/sosa/','http://www.w3.org/ns/ssn/','http://www.w3.org/2002/07/owl#',
    'http://www.w3.org/2000/01/rdf-schema#','http://www.w3.org/1999/02/22-rdf-syntax-ns#')
MAPPINGS=[SKOS.closeMatch,SKOS.exactMatch,SKOS.broadMatch,SKOS.narrowMatch,SKOS.relatedMatch]
def mapping_problems(graph):
    found=[]
    for pred in MAPPINGS:
        for subject,target in graph.subject_objects(pred):
            for end in (subject,target):
                typed=set(graph.objects(end,RDF.type))
                if types.intersection(typed) or (OWL.NamedIndividual in typed and SKOS.Concept not in typed):
                    found.append(f'SKOS concept mapping {pred.split("#")[-1]} used for ontology entity {end}')
                elif isinstance(end,URIRef) and str(end).startswith(OWL_NAMESPACES):
                    found.append(f'SKOS concept mapping {pred.split("#")[-1]} targets {end}, a term of an OWL ontology')
    return found
from rdflib import Graph
_probe=Graph().parse(format='turtle',data="""@prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
    <urn:c> a skos:Concept ; skos:closeMatch <http://www.opengis.net/ont/sf#Point> , <urn:k> . <urn:k> a owl:Class .
    <urn:d> a skos:Concept ; skos:exactMatch <urn:e> . <urn:e> a skos:Concept .""")
assert len(mapping_problems(_probe))==2,mapping_problems(_probe)
problems=mapping_problems(g)
assert not problems,problems
for module in ['raster','spatialref','geometry']:
    ns=f'https://hexplain.io/ns/aspect/{module}'
    # Versioned working drafts: the version IRI carries the versionInfo number and names its predecessor.
    version=str(g.value(URIRef(ns),OWL.versionInfo)).split()[0]
    assert (URIRef(ns),OWL.versionIRI,URIRef(ns+'/'+version)) in g,f'{ns}: versionIRI does not match versionInfo {version}'
    assert g.value(URIRef(ns),OWL.priorVersion) is not None,f'{ns}: working draft without owl:priorVersion'
    for subject in set(g.subjects()):
        if not str(subject).startswith(ns+'#') or not types.intersection(g.objects(subject,RDF.type)):continue
        assert g.value(subject,RDFS.label),f'Missing label: {subject}'
        assert (subject,RDFS.isDefinedBy,URIRef(ns)) in g,f'Missing owner: {subject}'
        assert not list(g.objects(subject,RDFS.domain)),f'Use scoped SHACL rather than global domain inference: {subject}'
# Validate shape syntax using the W3C SHACL shapes graph, not just Turtle parsing.
ok,_,report=validate(g,shacl_graph=specgraph.shapes(),meta_shacl=True,advanced=True,inference='none')
assert ok,report
print('PASS: ontology entities are not SKOS mappings; new module metadata and family SHACL meta-validation pass')


# owl:versionInfo is the bare version number, equal to the version IRI's last segment, for every
# ontology of the family; "1.3 working draft" put a status into the version, which is stated
# with its own annotation (schema:creativeWorkStatus) instead.
for _ontology in g.subjects(RDF.type,OWL.Ontology):
    _info=g.value(_ontology,OWL.versionInfo);_viri=g.value(_ontology,OWL.versionIRI)
    if _info is None:continue
    assert re.fullmatch(r'[0-9]+[.][0-9]+',str(_info)),f'{_ontology}: owl:versionInfo {_info!r} is not a bare version number'
    assert _viri is not None and str(_viri).endswith('/'+str(_info)),f'{_ontology}: owl:versionIRI {_viri} does not end with its versionInfo {_info}'
