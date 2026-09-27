"""Shared ontology reference model; no network requests or file mutations on import."""
import re
from pathlib import Path
from collections import defaultdict
from rdflib import Graph,RDF,RDFS,OWL,URIRef,BNode,Namespace
import specgraph
from _term_editorial import DEFINITIONS, SCOPE_NOTES
from _shape_text import PLACEHOLDER, Unhandled, constrains_value, value_phrase
from _shape_text import message as shape_message

ROOT=Path(__file__).resolve().parent.parent
SKOS=Namespace('http://www.w3.org/2004/02/skos/core#')
SH=Namespace('http://www.w3.org/ns/shacl#')
VANN=Namespace('http://purl.org/vocab/vann/')
BDDO=Namespace('https://hexplain.io/ns/bddo#')
ANNOTATION_MARKER='\n# BEGIN GENERATED TERM DOCUMENTATION\n'
ANNOTATIONS={RDFS.label,RDFS.isDefinedBy,SKOS.definition,SKOS.scopeNote}
TARGETS={SH.targetClass:'instances of',SH.targetSubjectsOf:'subjects using',SH.targetObjectsOf:'objects of',SH.targetNode:'the specific node'}

def modules():
    out=defaultdict(list)
    for path in specgraph.ontology_paths():out[Path(path).parent].append(Path(path))
    return dict(sorted(out.items(),key=lambda x:str(x[0])))

def load(paths,base=False):
    g=Graph()
    for p in paths:
        text=(ROOT/p).read_text(encoding='utf-8')
        if base:text=text.split(ANNOTATION_MARKER)[0]
        g.parse(data=text,format='turtle')
    return g

def owned(g):
    return sorted(s for s in set(g.subjects()) if isinstance(s,URIRef) and str(s).startswith('https://hexplain.io/ns/'))

def local(term):return str(term).rsplit('#',1)[-1].rsplit('/',1)[-1]
def owner(term):return URIRef(str(term).split('#')[0])
def label(g,term):
    labels=list(g.objects(term,SKOS.prefLabel))+list(g.objects(term,RDFS.label))
    return str(sorted(labels,key=lambda x:(x.language!='en',str(x)))[0]) if labels else re.sub(r'(?<=[a-z0-9])(?=[A-Z])',' ',local(term)).replace('_',' ').strip()

def compact(g,term):
    if not isinstance(term,URIRef):return str(term)
    ns=str(term).split('#')[0]
    prefix=g.value(URIRef(ns),VANN.preferredNamespacePrefix)
    if prefix and '#' in str(term):return f'{prefix}:{local(term)}'
    return g.namespace_manager.normalizeUri(term)

def kind(g,t):
    types=set(g.objects(t,RDF.type))
    for typ,title in [(OWL.Ontology,'Ontology'),(SH.NodeShape,'Node shape'),(SH.PropertyShape,'Property shape'),(SKOS.ConceptScheme,'Concept scheme'),(SKOS.Collection,'Collection'),(SKOS.Concept,'Concept'),(OWL.Class,'Class'),(OWL.ObjectProperty,'Object property'),(OWL.DatatypeProperty,'Datatype property'),(OWL.AnnotationProperty,'Annotation property'),(RDFS.Datatype,'Datatype')]:
        if typ in types:return title
    if (t,SH.declare,None) in g:return 'SHACL prefix declarations'
    return 'Named individual'

def closure(g,node):
    """Blank-node closure only: named references remain explicit reusable references."""
    seen=set();stack=[node]
    while stack:
        s=stack.pop()
        if s in seen:continue
        seen.add(s)
        for _p,o in g.predicate_objects(s):
            if isinstance(o,BNode):stack.append(o)
    return seen

def shape_targets(g,t):
    parts=[]
    for predicate,phrase in TARGETS.items():
        vals=sorted(g.objects(t,predicate),key=str)
        if vals:parts.append(phrase+' '+', '.join(compact(g,x) for x in vals))
    # A SPARQL-based target (sh:target) is a target too; saying "no automatic target" of
    # hexplain:RegisterBindingShape was false.
    if list(g.objects(t,SH.target)):parts.append('the nodes its SPARQL target selects')
    return '; '.join(parts) or 'No automatic target; applied only when another shape references it or a caller explicitly selects it.'

def shape_properties(g,shape):
    return sorted({o for s in closure(g,shape) for o in g.objects(s,SH.path) if isinstance(o,URIRef)},key=str)

def stated_definition(g,t):
    """The definition a term's documentation gives: its skos:definition, else its rdfs:comment.

    One rule for the whole family: rdfs:comment is the author's definition where the source gives
    one; a skos:definition is added only where it says something the comment does not (an
    editorial definition for a term whose source has no comment, or one that replaces an
    inadequate comment). The two never repeat each other (tools/test_documentation_annotations.py).
    """
    return g.value(t,SKOS.definition) or g.value(t,RDFS.comment)

def _prefixes(g):
    out={p:str(n) for p,n in g.namespace_manager.namespaces() if p}
    for ontology in g.subjects(VANN.preferredNamespacePrefix,None):
        prefix=str(g.value(ontology,VANN.preferredNamespacePrefix));uri=g.value(ontology,VANN.preferredNamespaceUri)
        if uri is not None:
            out={k:v for k,v in out.items() if v!=str(uri)};out[prefix]=str(uri)
    return out

def shape_definition(g,t):
    """A definition for a shape whose source gives none, built from what the shape checks.

    Sentences come from the shape's own validation messages and, for a value shape, from its
    constraints. A message that names SPARQL result variables ({?x}) is never copied: it reads
    as a template, not a definition. A shape with nothing to say needs an editorial rdfs:comment.
    """
    if list(g.objects(t,SH.rule)):return 'A SHACL rule-bearing shape that derives additional triples for its selected focus nodes. Its rule is an inference operation, not a validation constraint; see the executable rule and activation scope below.'
    prefixes=_prefixes(g);sentences=[]
    def add(text):
        text=str(text).strip()
        if text and not PLACEHOLDER.search(text) and text not in sentences:sentences.append(text)
    for message in g.objects(t,SH.message):add(message)
    if constrains_value(g,t):
        try:add(('Each focus node is ' if any((t,p,None) in g for p in TARGETS) or (t,SH.target,None) in g else 'A conforming value is ')+value_phrase(g,t,prefixes)+'.')
        except Unhandled:pass
    for pshape in sorted(g.objects(t,SH.property),key=lambda p:str(g.value(p,SH.path))):
        stated=[m for m in g.objects(pshape,SH.message) if not PLACEHOLDER.search(str(m))]
        if stated:
            for m in stated:add(m)
        else:
            try:add(shape_message(g,pshape,prefixes))
            except Unhandled:pass
    for constraint in g.objects(t,SH.sparql):
        for message in g.objects(constraint,SH.message):add(message)
    if not sentences:
        raise ValueError(f'Editorial definition required: {compact(g,t)} (a shape whose constraints cannot be stated and that has no rdfs:comment)')
    targets=shape_targets(g,t)
    opening='Applied through references from other shapes.' if targets.startswith('No automatic target') else 'Applies to '+targets+'.'
    return opening+' '+' '.join(sentences)

def definition(g,t):
    """The skos:definition to generate for [t], or None when the source already defines it."""
    key=compact(g,t);name=label(g,t);k=kind(g,t)
    stated=stated_definition(g,t)
    if key in DEFINITIONS:
        return None if stated is not None and str(stated).strip()==DEFINITIONS[key].strip() else DEFINITIONS[key]
    if stated is not None:return None
    if k in ['Node shape','Property shape']:return shape_definition(g,t)
    if k=='SHACL prefix declarations':return 'Namespace prefix declarations reused by SHACL SPARQL constraints and rules. This is validation infrastructure, not a property of parsed data.'
    if (t,RDF.type,BDDO.DataType) in g and g.value(t,BDDO.bitWidth):
        width=str(g.value(t,BDDO.bitWidth));base=g.value(t,BDDO.baseType);signed=g.value(t,BDDO.isSigned)
        flavor='floating-point' if base==BDDO.baseFloat else ('signed integer' if signed is not None and bool(signed.toPython()) else 'unsigned integer')
        end=g.value(t,BDDO.endianness)
        return f'A {width}-bit {flavor} primitive datatype. '+('Byte order is '+label(g,end)+'.' if end else 'Byte order is not fixed on this datatype; the field and processing context determine it.')
    if k=='Concept scheme':return f'The controlled concept scheme grouping {name.removesuffix(" Register").lower()} values. Membership identifies the applicable value set; raw format codes are defined by profiles rather than by this scheme.'
    if k=='Collection':return f'An editorial grouping of {name.lower()} concepts for navigation and selection. Collection membership does not assert a subclass or broader/narrower hierarchy.'
    if k=='Ontology':return f'The vocabulary module publishing {name} terms, its imports and associated validation declarations.'
    if k=='Concept' and '/us-nato-security#' in str(t):
        scheme=g.value(t,SKOS.inScheme)
        if local(t).startswith('Reason'):
            return f'A legacy classification-reason selector identifying {name}. It preserves the source policy reference rather than asserting that the policy is current.'
        if re.fullmatch('X[0-9]+',local(t)):
            clause=('4-202b('+local(t)[1:]+')' if int(local(t)[1:])<10 else '4-301a('+str(int(local(t)[1:])-250)+')')
            return f'A legacy exemption selector for DOD 5200.1-R paragraph {clause}, represented by the register label {name}. It records the cited exemption category, not an automatic decision to withhold or declassify data.'
        return f'The legacy {label(g,scheme).removesuffix(" Register").lower()} designation “{name}” as an interoperable concept IRI. It records the designation found in a source; it does not determine current handling authority or grant access.'
    raise ValueError(f'Editorial definition required: {key} ({k})')

SCOPE={
 'bddo':'Use in physical binary-format descriptions. Extents and offsets describe bytes unless a term explicitly specifies bits; HEL evaluation and failure behavior follow the processing specification.',
 'dlv':'Use in declarations of physical multi-dimensional storage. Logical axis meaning is distinct from byte strides, chunk order and encoded payload interpretation.',
 'core':'Use when linking a physical format description to semantic RDF output, encoding stages or controlled-value bindings. It does not replace the byte-layout description.',
 'fn':'Use to invoke a SPARQL extension function that reaches the bytes, parsed values, array cells or aspect coordinates of an asset described by a Hexplain profile. Pure functions also run as a SHACL-AF sh:SPARQLFunction body without the Hexplain engine; native functions require it.',
 'geo':'Use for georeferenced datasets. Combine the dataset kind with the appropriate raster, geometry, point-cloud, spatial-reference and provenance aspects.',
 'image':'Use for image resources and their components. The legacy integer method/color codes preserve profile-specific wire values; they are not universal algorithm or color identifiers.',
 'audio':'Use for audio resources, their streams and source metadata. Sampling, encoding and timing aspects carry shared properties.',
 'video':'Use for video containers, streams, tracks and timing metadata. Nominal rate must not be used as an exact variable-rate timeline.',
 'docfont':'Use for documents, pages, fonts and glyph components. Object identity, coordinate units and code interpretation depend on the document/font profile.',
 'net':'Use for protocol data units. Protocol-specific wire interpretation remains in the format profile; networkflow supplies shared endpoint and sequence metadata.',
 'archive':'Use for archive resources and member entries. Distinguish stored compressed bytes from logical member content.',
 'req':'Use for attributable requirements from a named standard or policy, independent of a particular executable validation rule.',
 'conf':'Use for constraints evaluated against a declared structural scope and attributed to requirements. A requirement is not an executable assertion by itself.',
 'raster':'Use for logical raster samples, bands and arrays after parsing. Logical dimensions are independent of physical DLV addressing; partial graphs and complete dimension lists have different completeness contracts.',
 'spatialref':'Use for coordinate references and geolocation metadata. Declare units, reference frame and pixel conventions explicitly; metadata validation does not execute coordinate transformations.',
 'geometry':'Use for explicit geometry semantics across vector graphics, geospatial features and glyph outlines. Spatial coordinates and measure ordinates must remain distinct.',
 'bundle':'Use for compound assets, their members and reusable membership profiles. Discovery/binding, semantic membership and physical byte location are separate concerns.',
 'security':'Use to record source security-marking semantics. Bind controlled values through a selected register; the aspect does not define a jurisdiction-specific authorization policy.',
 'sampling':'Use for quantized sample interpretation shared by raster, signal and point-cloud data. Precision, component organization and numeric interpretation are separate declarations.',
 'color':'Use for color interpretation of sample values. Resolve controlled identifiers through the profile-bound register.',
 'encoding':'Use for the encoding characteristics of data content; a codec identifier alone does not supply all container framing and parameters.',
 'fsmeta':'Use for logical file or directory metadata recorded by a container or filesystem representation; it need not describe the current host filesystem.',
 'integrity':'Use for recorded integrity information about bytes or resources; the presence of a digest is distinct from successful verification.',
 'networkflow':'Use for protocol addressing and transport/flow metadata. A source number or bit pattern has meaning only in its declared protocol context.',
 'packaging':'Use for membership and packaging metadata shared by archive and compound-resource descriptions.',
 'pointcloud':'Use for unstructured sampled-point collections and their per-point record descriptions; no regular grid topology is implied.',
 'provenance':'Use for acquisition and observing-equipment metadata. Keep observation time distinct from file timestamps and reference-frame epochs.',
 'signal':'Use for sampled signals; state channel organization and units separately from sample rate.',
 'tabular':'Use for tabular records and typed column declarations. Source datatype names require interpretation by the relevant format/profile.',
 'time':'Use for temporal metadata of content. Numeric durations and frame/sample counts are not interchangeable without a timing model.',
}

# Modules whose terms each carry their own skos:scopeNote, in the canonical RDF or in
# _term_editorial.SCOPE_NOTES. For them the module sentence above describes the MODULE only:
# prefixing it to a class, an individual or a property said, for example, that conf:Finding was
# "for constraints evaluated against a declared structural scope", and that hexplain:RegisterStatus
# was for "linking a physical format description to semantic RDF output"; both wrong. A term of
# such a module without a note of its own gets only the kind sentence that is true of it.
TERM_SCOPED={'conf','req','core','bundle'}
SUBCLASS_NOTE=' Its subclass links below are the asserted hierarchy, not merely similarity links.'
PATH_NOTE=' Applicable SHACL paths and their focus-node scopes are listed below; no additional global domain is inferred from that usage.'
NO_PATH_NOTE=' No shape of the family constrains it, and no global domain is inferred.'

def has_hierarchy(g,t):
    return (t,RDFS.subClassOf,None) in g or (None,RDFS.subClassOf,t) in g

_FAMILY=[]
def family_graph():
    """Every module of the family without its generated documentation, loaded once."""
    if not _FAMILY:_FAMILY.append(load(specgraph.ontology_paths(),base=True))
    return _FAMILY[0]

def constrained(g,t):
    """True when a shape anywhere in the family uses the property as a path or targets its subjects or objects."""
    f=family_graph()
    return any((None,p,t) in f for p in (SH.path,SH.targetSubjectsOf,SH.targetObjectsOf))

def kind_sentence(g,t,k):
    """The sentence about how a term of kind [k] is used, claiming only what is true of [t]."""
    if k=='Class':return 'Assert this class on a resource representing the defined entity.'+(SUBCLASS_NOTE if has_hierarchy(g,t) else '')
    if 'property' in k.lower():return 'Use it as a predicate.'+(PATH_NOTE if constrained(g,t) else NO_PATH_NOTE)
    if k=='Named individual':return 'Use this IRI as a controlled value where the profile or a shape accepts its declared type.'
    return ''

def scope(g,t):
    """The skos:scopeNote to generate for [t], or None.

    Only notes that say something about the term itself are generated: the module's note on its
    ontology, and a term's editorial note (_term_editorial.SCOPE_NOTES). Generating the module
    sentence, a kind sentence or a shape's activation onto every term repeated, 987 times, what
    the ontology's note and the term reference's own rows (activation, shape usage) already say.
    """
    k=kind(g,t);ns=str(owner(t));module=ns.removesuffix('/shapes').rsplit('/',1)[-1]
    if module=='hexplain':module='core'
    for key in (str(t),compact(g,t)):
        if key in SCOPE_NOTES:return SCOPE_NOTES[key]
    if k!='Ontology':return None
    if '/register/' in ns:
        return 'Load to obtain the concepts of this register. A profile binds its schemes to the properties they supply with hexplain:usesRegister; the aspect the values serve does not import it.'+(
          ' This is a historical interoperability register. Consult the source policy version and current governing authority before interpreting handling effects.' if module=='us-nato-security' else ' Codec/algorithm concepts require any applicable variant, framing and parameter information from the profile.' if module in ['media-encoding','checksum'] else ' Use concept IRIs as values; concept schemes and collections organize those values rather than describing parsed instances.')
    return SCOPE.get(module)
