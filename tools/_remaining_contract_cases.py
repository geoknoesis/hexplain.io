"""Focused semantic membership, literal-kind and cardinality counterexamples."""
def cases():
    rows=[]
    prefix='''@prefix ex:<urn:remaining-contract:> . @prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
@prefix skos:<http://www.w3.org/2004/02/skos/core#> . @prefix b:<https://hexplain.io/ns/bddo#> .
@prefix enc:<https://hexplain.io/ns/aspect/encoding#> . @prefix color:<https://hexplain.io/ns/aspect/color#> .
ex:a a skos:Concept . ex:b a skos:Concept . ex:s a b:Struct . ex:s2 a b:Struct .
'''
    def add(name,module,ns,body,ok,path=''):
        rows.append(dict(name='remaining '+name,module='specification/'+module,expected=ok,path=path,data=prefix+'@prefix p:<https://hexplain.io/ns/'+ns+'#> . '+body))
    for module,ns,cls,prop in [('adv/audio.ttl','audio','AudioStream','enc:codec'),('vdv/video.ttl','video','VideoStream','enc:codec'),('vdv/video.ttl','video','VideoStream','color:colorSpace'),('idv/image.ttl','image','Image','color:colorSpace'),('axv/archive.ttl','archive','ArchiveEntry','enc:compression')]:
        uri='https://hexplain.io/ns/aspect/'+('encoding#' if prop.startswith('enc:') else 'color#')+prop.split(':')[1]
        context='ex:f a p:'+('ImageHeader' if module=='idv/image.ttl' else cls)+'. '
        if module=='adv/audio.ttl':context+='ex:f <https://hexplain.io/ns/aspect/signal#sampleRate> 1. '
        add(module+' '+prop+' literal',module,ns,context+'ex:f '+prop+' "value".',False,uri)
    for prop in ['geometryType','pointDataLayout']:
        cls='VectorDataset' if prop=='geometryType' else 'PointCloud'
        value='"type"' if prop=='geometryType' else 'ex:s,ex:s2'
        uri='https://hexplain.io/ns/aspect/'+('geometry#' if prop=='geometryType' else 'pointcloud#')+prop
        context='ex:f a p:'+cls+'. '
        if prop=='pointDataLayout':context+='ex:f <https://hexplain.io/ns/aspect/pointcloud#pointCount> 1. '
        add('geo '+prop,'gv/geo.ttl','geo',context+'ex:f <'+uri+'> '+value+'.',False,uri)
    for value,ok in [('"dir/file.bin"',True),('1',False),('"a","b"',False)]:
        add('entry path '+value,'aspect/packaging/packaging.ttl','aspect/packaging','ex:f p:entryPath '+value+'.',ok,'' if ok else 'https://hexplain.io/ns/aspect/packaging#entryPath')
    for prop,value,ok,base in [
        ('boundBy','p:Containment',True,'ex:f a p:Asset.'),
        ('boundBy','p:Containment,p:NamingConvention',False,'ex:f a p:Asset.'),
        ('primaryPart','ex:a,ex:b',False,'ex:f a p:Asset. ex:a a p:Part. ex:b a p:Part.'),
        ('partRole','ex:unknown',False,'ex:f a p:Part.'),
        ('nestedProfile','ex:unknown',False,'ex:f a p:PartSpec.'),
        ('nestedProfile','ex:a,ex:b',False,'ex:f a p:PartSpec. ex:a a p:BundleProfile. ex:b a p:BundleProfile.'),
        ('pathPattern','1',False,'ex:f a p:PartSpec.')]:
        add('bundle '+prop+' '+value,'aspect/bundle/bundle.ttl','aspect/bundle',base+' ex:f p:'+prop+' '+value+'.',ok,'' if ok else 'https://hexplain.io/ns/aspect/bundle#'+prop)
    add('duplicate sample format','aspect/sampling/sampling.ttl','aspect/sampling','ex:f p:sampleFormat ex:a,ex:b.',False,'https://hexplain.io/ns/aspect/sampling#sampleFormat')
    gcp='ex:f a p:GroundControlPoint; p:gcpPixelX "1"^^xsd:double; p:gcpPixelY "1"^^xsd:double; p:gcpX "1"^^xsd:double; p:gcpY "1"^^xsd:double. '
    for value,ok in [('"name"',True),('1',False),('"a","b"',False)]:
        add('gcp identifier '+value,'aspect/spatialref/spatialref.ttl','aspect/spatialref',gcp+'ex:f p:gcpIdentifier '+value+'.',ok,'' if ok else 'https://hexplain.io/ns/aspect/spatialref#gcpIdentifier')
    security='ex:f a <urn:hexplain:security-example:Marked>; p:markingSystem "example"; p:sensitivityLevel ex:a. ex:a skos:inScheme <urn:hexplain:security-example:Levels>. '
    for prop,value in [('markingSystem','1'),('sensitivityLevelText','1'),('markingDate','"2026-01-01"^^xsd:date,"2026-01-02"^^xsd:date')]:
        base=security.replace('p:markingSystem "example"; ','') if prop=='markingSystem' else security
        add('security '+prop,'validation/test/security-profile.ttl','aspect/security',base+'ex:f p:'+prop+' '+value+'.',False,'https://hexplain.io/ns/aspect/security#'+prop)
    return rows
