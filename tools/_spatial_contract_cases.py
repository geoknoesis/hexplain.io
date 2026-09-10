"""Independent coordinate-model property and required-value counterexamples."""
PREFIX='''@prefix ex:<urn:spatial-contract:> .
@prefix s:<https://hexplain.io/ns/aspect/spatialref#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
'''
def cases():
    rows=[]
    def add(name,body,ok,path=''):
        rows.append(dict(name='spatial '+name,module='specification/aspect/spatialref/spatialref.ttl',expected=ok,path=('https://hexplain.io/ns/aspect/spatialref#'+path) if path else '',data=PREFIX+body))
    models=[('GeoTransform','originX originY scaleX scaleY skewX skewY',''),
            ('GroundControlPoint','gcpPixelX gcpPixelY gcpX gcpY','gcpZ')]
    offsets='lineOffset sampleOffset latitudeOffset longitudeOffset heightOffset'
    scales='lineScale sampleScale latitudeScale longitudeScale heightScale'
    vectors='lineNumerator lineDenominator sampleNumerator sampleDenominator'
    models.append(('CubicRationalTransform',offsets+' '+scales,''))
    for cls,required,optional in models:
        props=(required+' '+optional).split()
        base={p:'"1"^^xsd:double' for p in props}
        if cls=='CubicRationalTransform':
            base.update({p:'('+' '.join(['"1"^^xsd:double']*20)+')' for p in vectors.split()})
            base['polynomialBasis']='ex:basis'
        def body(values):return 'ex:f a s:'+cls+'. '+''.join('ex:f s:'+p+' '+v+'. ' for p,v in values.items())
        add(cls+' valid',body(base),True)
        for prop in props:
            for label,value in [('wrong type','"1"'),('duplicate','"1"^^xsd:double,"2"^^xsd:double'),('nonfinite','"INF"^^xsd:double')]:
                changed=dict(base);changed[prop]=value
                add(cls+' '+prop+' '+label,body(changed),False,prop)
            if prop in required.split():
                changed=dict(base);del changed[prop]
                add(cls+' '+prop+' missing',body(changed),False,prop)
            if prop in scales.split():
                changed=dict(base);changed[prop]='"0"^^xsd:double'
                add(cls+' '+prop+' zero',body(changed),False,prop)
        if cls=='CubicRationalTransform':
            for prop in vectors.split()+['polynomialBasis']:
                for label,value in [('missing',None),('literal','"bad"'),('duplicate',base[prop]+','+('ex:other' if prop=='polynomialBasis' else '('+' '.join(['"2"^^xsd:double']*20)+')'))]:
                    changed=dict(base)
                    if value is None:del changed[prop]
                    else:changed[prop]=value
                    add(cls+' '+prop+' '+label,body(changed),False,prop)
    for prop,valid,bad in [('wktString','"GEOGCRS[...]"','1'),('crsIdentifier','ex:crs','"EPSG:4326"'),('coordinateEpoch','2026.5','"2026.5"')]:
        add(prop+' valid','ex:f a s:CoordinateReferenceSystem; s:'+prop+' '+valid+'.',True)
        add(prop+' invalid','ex:f a s:CoordinateReferenceSystem; s:'+prop+' '+bad+'.',False,prop)
    return rows
