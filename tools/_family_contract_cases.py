"""Authored module contracts; expectations do not come from reading the shapes."""
PREFIX='''@prefix ex:<urn:family-contract:> .
@prefix a:<https://hexplain.io/ns/audio#> . @prefix d:<https://hexplain.io/ns/docfont#> .
@prefix i:<https://hexplain.io/ns/image#> . @prefix ar:<https://hexplain.io/ns/archive#> .
@prefix g:<https://hexplain.io/ns/geo#> . @prefix r:<https://hexplain.io/ns/aspect/raster#> .
@prefix v:<https://hexplain.io/ns/video#> . @prefix net:<https://hexplain.io/ns/aspect/networkflow#> .
@prefix s:<https://hexplain.io/ns/aspect/sampling#> . @prefix sig:<https://hexplain.io/ns/aspect/signal#> .
@prefix t:<https://hexplain.io/ns/aspect/time#> . @prefix enc:<https://hexplain.io/ns/aspect/encoding#> .
@prefix fs:<https://hexplain.io/ns/aspect/fsmeta#> . @prefix integ:<https://hexplain.io/ns/aspect/integrity#> .
@prefix pack:<https://hexplain.io/ns/aspect/packaging#> . @prefix sr:<https://hexplain.io/ns/aspect/spatialref#> .
@prefix pc:<https://hexplain.io/ns/aspect/pointcloud#> . @prefix prov:<https://hexplain.io/ns/aspect/provenance#> .
@prefix geom:<https://hexplain.io/ns/aspect/geometry#> . @prefix col:<https://hexplain.io/ns/aspect/color#> .
@prefix asec:<https://hexplain.io/ns/aspect/security#> .
@prefix b:<https://hexplain.io/ns/bddo#> . @prefix skos:<http://www.w3.org/2004/02/skos/core#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> . @prefix dc:<http://purl.org/dc/terms/> .
ex:c a skos:Concept . ex:c2 a skos:Concept . ex:box a d:BoundingBox . ex:struct a b:Struct .
ex:entry a ar:ArchiveEntry .
'''
# Two distinct conforming values and an independently chosen invalid value.
KINDS={
 'string':('"text"','"other"','1'),
 'date':('"2026-09-08T00:00:00Z"^^xsd:dateTime','"2026-09-09T00:00:00Z"^^xsd:dateTime','"2026-09-08"'),
 # A calendar date, not an instant: a marking decision is dated to a day, and an xsd:dateTime is
 # the wrong datatype for it rather than merely a more precise one.
 'calendarDate':('"2026-09-08"^^xsd:date','"2026-09-09"^^xsd:date','"2026-09-08T00:00:00Z"^^xsd:dateTime'),
 'boolean':('true','false','"true"'),
 'hex':('"00"^^xsd:hexBinary','"FF"^^xsd:hexBinary','"00"'),
 'positive':('1','2','0'),
 'nonnegative':('0','1','-1'),
 'literal':('1','2','ex:untyped'),
 'concept':('ex:c','ex:c2','ex:untyped'),
 'box':('ex:box','ex:box','ex:untyped'),
 'struct':('ex:struct','ex:struct','ex:untyped'),
 'entry':('ex:entry','ex:entry','ex:untyped'),
 'registration':('sr:PixelCorner','sr:PixelCenter','ex:untyped'),
}
# Module, stable target context, property, value contract, maximum one value.
CONTRACTS=[]
def group(module,context,items):
    for prop,kind,unique in items:CONTRACTS.append((module,context,prop,kind,unique))
group('adv/audio.ttl','ex:f sig:sampleRate 1.',[(p,k,True) for p,k in [('sig:sampleRate','positive'),('s:componentCount','positive'),('s:bitDepth','positive'),('t:duration','literal'),('enc:bitrate','positive'),('enc:codec','concept')]])
group('adv/audio.ttl','ex:f a:artist "artist".',[(p,k,True) for p,k in [('a:artist','string'),('a:album','string'),('a:trackTitle','string'),('a:trackNumber','positive')]])
group('dfv/docfont.ttl','ex:f a d:Document.',[(p,k,True) for p,k in [('dc:creator','string'),('dc:title','string'),('dc:created','date'),('dc:modified','date'),('d:pageCount','positive')]])
group('dfv/docfont.ttl','', [('d:hasBoundingBox','box',False)])
group('dfv/docfont.ttl','ex:f d:fontFamily "font".',[(p,k,True) for p,k in [('d:fontFamily','string'),('d:fontStyle','string'),('d:glyphCount','positive')]])
group('idv/image.ttl','ex:f a i:ImageHeader.',[(p,k,True) for p,k in [('r:width','positive'),('r:height','positive'),('s:bitDepth','positive'),('col:colorSpace','concept')]])
group('idv/image.ttl','ex:f i:colorType 1.',[(p,'literal',p=='i:colorType') for p in ['i:colorType','i:compressionMethod','i:filterMethod','i:interlaceMethod']])
group('axv/archive.ttl','ex:f a ar:Archive.', [('pack:hasEntry','entry',False)])
group('axv/archive.ttl','ex:f a ar:ArchiveEntry.',[(p,k,True) for p,k in [('fs:fileName','string'),('fs:fileSize','nonnegative'),('ar:compressedSize','nonnegative'),('integ:checksum','hex'),('fs:modificationTime','date'),('fs:isDirectory','boolean'),('enc:compression','concept')]])
group('gv/geo.ttl','ex:f sr:wktString "WKT".', [('sr:wktString','string',True),('sr:epsgCode','positive',True)])
group('gv/geo.ttl','ex:f sr:originLatitude 1.', [('sr:originLatitude','literal',True),('sr:originLongitude','literal',True)])
group('gv/geo.ttl','', [('sr:pixelRegistration','registration',True)])
group('gv/geo.ttl','ex:f a g:VectorDataset.', [('geom:geometryType','concept',True)])
group('gv/geo.ttl','ex:f pc:pointCount 0.', [('pc:pointCount','nonnegative',True),('pc:pointDataLayout','struct',True)])
group('gv/geo.ttl','ex:f prov:acquisitionTime "2026-09-08T00:00:00Z"^^xsd:dateTime.', [('prov:acquisitionTime','date',True),('prov:platformName','string',False),('prov:sensorType','string',False)])
group('npv/net.ttl','', [('net:sourceAddress','string',True),('net:destinationAddress','string',True),('net:tcpFlags','hex',True)])
# The marking spine is flat -- no class of its own -- so every case below is activated by the
# presence of the property itself. A conforming sibling stays in the context so an invalid variant
# fails on exactly the path under test.
# Every property is repeatable on purpose -- a resource marked under two systems carries two of
# most of them -- so none of these cases asserts uniqueness.
group('aspect/security/security.ttl','ex:f asec:markingSystem "US".',[
    (p,k,False) for p,k in [
        ('asec:markingSystem','string'),('asec:sensitivityLevel','concept'),
        ('asec:sensitivityLevelText','string'),('asec:markingText','string'),
        ('asec:markingIdentifier','string'),('asec:markingAuthority','string'),
        ('asec:markingDate','calendarDate'),('asec:expiresOn','calendarDate'),
        ('asec:marking','concept'),('asec:releasableTo','string')]])
# A declared level change must say when it takes effect, so the context carries the date; the
# missing-date counterexample is authored below, where the absence is the point.
group('aspect/security/security.ttl','ex:f asec:levelChangeDate "2026-09-08"^^xsd:date.',[
    ('asec:levelChangesTo','concept',False),('asec:levelChangeDate','calendarDate',False)])
group('vdv/video.ttl','ex:f a v:VideoStream.',[(p,k,True) for p,k in [('r:width','positive'),('r:height','positive'),('enc:bitrate','positive'),('enc:codec','concept'),('col:colorSpace','concept'),('t:duration','nonnegative'),('v:audioChannels','positive')]])

def cases():
    from rdflib import Graph,URIRef
    result=[]
    for module,context,prop,kind,unique in CONTRACTS:
        first,second,bad=KINDS[kind]
        probe=Graph().parse(data=PREFIX+f'ex:f {prop} {first}.',format='turtle')
        predicate=next(probe.predicates(URIRef('urn:family-contract:f'),None))
        base=Graph().parse(data=PREFIX+context,format='turtle')
        base.remove((URIRef('urn:family-contract:f'),predicate,None))
        variants=[('valid',first,True),('invalid',bad,False)]
        if unique and first!=second:variants.append(('duplicate',first+', '+second,False))
        for name,value,expected in variants:
            data=base+Graph().parse(data=PREFIX+f'ex:f {prop} {value}.',format='turtle')
            result.append(dict(name=module+':'+prop+':'+name,module='specification/'+module,expected=expected,path=str(predicate) if not expected else '',data=data.serialize(format='turtle')))
    # A level change with no effective date: the minimum-count obligation's failing witness, which
    # no valid/invalid/duplicate variant of a present property can provide.
    result.append(dict(name='security level change without a date',
                       module='specification/aspect/security/security.ttl', expected=False,
                       path='https://hexplain.io/ns/aspect/security#levelChangeDate',
                       data=PREFIX+'ex:f asec:levelChangesTo ex:c.'))
    result.append(dict(name='security level change with a date',
                       module='specification/aspect/security/security.ttl', expected=True, path='',
                       data=PREFIX+'ex:f asec:levelChangesTo ex:c; asec:levelChangeDate "2026-09-08"^^xsd:date.'))
    for name,body in [('fractional duration','t:duration 0.5'),('integer frame rate','v:frameRate 30'),('positiveInteger audio channels','v:audioChannels "2"^^xsd:positiveInteger'),('uint64 frame count','v:frameCount "18446744073709551615"^^xsd:unsignedLong')]:
        result.append(dict(name='video '+name,module='specification/vdv/video.ttl',expected=True,path='',data=PREFIX+'ex:f a v:VideoStream; '+body+'.'))
    from _mapping_contract_cases import cases as mappings
    from _integer_family_cases import cases as integers
    from _physical_property_cases import cases as physical
    from _spatial_contract_cases import cases as spatial
    from _requirement_contract_cases import cases as requirements
    from _raster_contract_cases import cases as raster
    from _core_contract_cases import cases as core
    from _layout_property_cases import cases as layout_properties
    from _structural_contract_cases import cases as structural
    from _tree_contract_cases import cases as tree
    from _semantic_boundary_cases import cases as semantic
    from _remaining_contract_cases import cases as remaining
    from _closure_contract_cases import cases as closure
    return result+mappings()+integers()+physical()+spatial()+requirements()+raster()+core()+layout_properties()+structural()+tree()+semantic()+remaining()+closure()
