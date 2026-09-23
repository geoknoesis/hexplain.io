"""Guard ontology/controlled-vocabulary separation and new module hygiene."""
from rdflib import RDF,RDFS,OWL,Namespace,URIRef
from pyshacl import validate
import specgraph

g=specgraph.ontologies(); SKOS=Namespace('http://www.w3.org/2004/02/skos/core#')
types={OWL.Class,OWL.ObjectProperty,OWL.DatatypeProperty,OWL.AnnotationProperty}
for pred in [SKOS.closeMatch,SKOS.exactMatch,SKOS.broadMatch,SKOS.narrowMatch,SKOS.relatedMatch]:
    for subject,_target in g.subject_objects(pred):
        assert not types.intersection(g.objects(subject,RDF.type)),f'SKOS concept mapping used for ontology entity {subject}'
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
