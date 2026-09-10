"""Encoding, mapping and layout-link contracts with independent fixtures."""
PREFIX='''@prefix c:<https://hexplain.io/ns/core#> . @prefix b:<https://hexplain.io/ns/bddo#> .
@prefix d:<https://hexplain.io/ns/dlv#> . @prefix ex:<urn:core-contract:> .
@prefix skos:<http://www.w3.org/2004/02/skos/core#> . @prefix owl:<http://www.w3.org/2002/07/owl#> .
@prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#> . @prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
ex:codec a skos:Concept . ex:codec2 a skos:Concept . ex:layout a d:DataLayout . ex:layout2 a d:DataLayout .
ex:step a c:EncodingStep; c:codec ex:codec . ex:step2 a c:EncodingStep; c:codec ex:codec2 .
ex:param a c:CodecParameter; c:parameterName "level"; c:parameterValue 1 .
'''
def cases():
    rows=[]
    def add(name,body,ok,path=''):
        rows.append(dict(name='core '+name,module='specification/hexplain/core.ttl',expected=ok,path='https://hexplain.io/ns/core#'+path if path else '',data=PREFIX+body))
    for prop,base,good,second,bad,required in [
        ('isEncodedWith','', 'ex:codec','ex:codec2','ex:untyped',False),
        ('codec','ex:f a c:EncodingStep.', 'ex:codec','ex:codec2','ex:untyped',True),
        ('hasDataLayout','ex:f a b:Field.', 'ex:layout','ex:layout2','ex:untyped',False),
        ('hasEncodingStep','', '(ex:step)','(ex:step2)','"steps"',False),
        ('parameterName','ex:f a c:CodecParameter; c:parameterValue 1.', '"level"','"other"','1',True),
        ('parameterValue','ex:f a c:CodecParameter; c:parameterName "level".', '1','2',None,True),
        ('valueDatatype','ex:f a b:Field; c:valueExpression "value".', 'xsd:integer','xsd:string','"integer"',False)]:
        variants=[('valid',good,True),('duplicate',good+','+second,False)]
        if bad:variants.append(('bad',bad,False))
        if required:variants.append(('missing',None,False))
        if prop in ['codec','isEncodedWith']:variants.append(('literal','"codec"',False))
        for label,value,ok in variants:
            add(prop+' '+label,base+(' ex:f c:'+prop+' '+value+'.' if value is not None else ''),ok,'' if ok else prop)
    add('untyped layout owner','ex:f c:hasDataLayout ex:layout.',False)
    add('invalid pipeline member','ex:f c:hasEncodingStep (ex:untyped).',False)
    add('invalid codec parameter','ex:f a c:EncodingStep; c:codec ex:codec; c:codecParameter ex:untyped.',False,'codecParameter')
    add('typed codec parameter','ex:f a c:EncodingStep; c:codec ex:codec; c:codecParameter ex:param.',True)
    for cls in ['rdf:Property','owl:DatatypeProperty','owl:ObjectProperty','owl:AnnotationProperty']:
        add('mapping '+cls,'ex:f a b:Field; c:mapsToProperty ex:p. ex:p a '+cls+'.',True)
    add('mapping untyped property','ex:f a b:Field; c:mapsToProperty ex:unknown.',False,'mapsToProperty')
    add('mapping literal property','ex:f a b:Field; c:mapsToProperty "p".',False,'mapsToProperty')
    add('mapping untyped owner','ex:f c:mapsToProperty ex:p. ex:p a rdf:Property.',False)
    return rows
