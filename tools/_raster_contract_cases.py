"""Raster calibration and array-dimension value/cardinality witnesses."""
def cases():
    rows=[]
    prefix='@prefix r:<https://hexplain.io/ns/aspect/raster#> . @prefix ex:<urn:raster-contract:> . @prefix xsd:<http://www.w3.org/2001/XMLSchema#> . '
    def add(name,body,ok,path=''):
        rows.append(dict(name='raster '+name,module='specification/aspect/raster/raster.ttl',expected=ok,path='https://hexplain.io/ns/aspect/raster#'+path if path else '',data=prefix+body))
    for prop in ['sampleScale','sampleOffset']:
        for label,value,ok in [('finite','"-0.5"^^xsd:double',True),('wrong type','"0.5"',False),('positive infinity','"INF"^^xsd:double',False),('negative infinity','"-INF"^^xsd:double',False),('nan','"NaN"^^xsd:double',False),('duplicate','"1"^^xsd:double,"2"^^xsd:double',False)]:
            add(prop+' '+label,'ex:f r:'+prop+' '+value+'.',ok,'' if ok else prop)
    for prop,base,good,second,bad in [
        ('bandIndex','ex:f a r:RasterBand.','1','2','0'),
        # A no-data value is a sample value, so it is numeric; a string is no longer accepted.
        ('noDataValue','ex:f a r:RasterBand.','-9999','0','"missing"'),
        ('sampleUnit','ex:f a r:RasterBand.','ex:metre','ex:foot','"metre"'),
        ('dimensionName','ex:f a r:ArrayDimension; r:dimensionExtent 1.','"x"','"y"','1'),
        ('dimensionKind','ex:f a r:ArrayDimension; r:dimensionExtent 1.','ex:x','ex:y','"x"'),
        ('coordinateArray','ex:f a r:ArrayDimension; r:dimensionExtent 1. ex:x r:dimensions (). ex:y r:dimensions ().','ex:x','ex:y','"x"')]:
        for label,value,ok in [('valid',good,True),('invalid',bad,False),('duplicate',good+','+second,False)]:
            add(prop+' '+label,base+' ex:f r:'+prop+' '+value+'.',ok,'' if ok else prop)
    add('dimension missing extent','ex:f a r:ArrayDimension.',False,'dimensionExtent')
    add('dimension duplicate extent','ex:f a r:ArrayDimension; r:dimensionExtent 1,2.',False,'dimensionExtent')
    add('dimension empty name','ex:f a r:ArrayDimension; r:dimensionExtent 1; r:dimensionName "".',False,'dimensionName')
    # Every numeric datatype a no-data sentinel may carry, including a NaN sentinel.
    for datatype,value in [('double','NaN'),('float','-9999'),('decimal','-9999.5'),('integer','-9999'),
                           ('nonNegativeInteger','0'),('positiveInteger','1'),('nonPositiveInteger','0'),
                           ('negativeInteger','-1'),('long','-1'),('int','-1'),('short','-1'),('byte','-1'),
                           ('unsignedLong','0'),('unsignedInt','0'),('unsignedShort','0'),('unsignedByte','0')]:
        add('noDataValue '+datatype,'ex:f a r:RasterBand; r:noDataValue "'+value+'"^^xsd:'+datatype+'.',True)
    for prop in ['width','height','bandCount']:
        add(prop+' duplicate','ex:f r:'+prop+' 1,2.',False,prop)
    return rows
