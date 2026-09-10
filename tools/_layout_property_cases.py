"""Layout selectors, dynamic dimensions and rule property contracts."""
from test_layout_competency import PREFIX,layout
def cases():
    rows=[]
    prefix=PREFIX+'ex:f2 a b:Field. ex:order a dlv:ChunkOrder. ex:order2 a dlv:ChunkOrder. b:uint16 a b:DataType. '
    def add(name,base,owner,prop,value,ok):
        rows.append(dict(name='layout property '+name,module='specification/dlv/dlv.ttl',expected=ok,path='' if ok else 'https://hexplain.io/ns/'+('bddo#condition' if prop=='b:condition' else 'dlv#'+prop),data=prefix+base+(f' {owner} '+(prop if ':' in prop else 'dlv:'+prop)+f' {value}.' if value is not None else '')))
    for prop,owner,good,second,bad in [
        ('cellDataType','ex:l','b:uint8','b:uint16','ex:unknown'),
        ('cellBitWidthFromField','ex:l','ex:f','ex:f2','ex:unknown'),
        ('dimensionStrideFromField','ex:d','ex:f','ex:f2','ex:unknown'),
        ('dimensionStrideFromExpression','ex:d','"1"','"2"','1'),
        ('dimensionSizeFromField','ex:d','ex:f','ex:f2','ex:unknown'),
        ('chunkSizeFromField','ex:d','ex:f','ex:f2','ex:unknown'),
        ('chunkOffsetsFromField','ex:l','ex:f','ex:f2','ex:unknown'),
        ('chunkLengthsFromField','ex:l','ex:f','ex:f2','ex:unknown'),
        ('chunkOrder','ex:l','ex:order','ex:order2','ex:unknown'),
        ('chunkOffsetBase','ex:l','b:streamStart','b:parentStart','ex:unknown')]:
        base=layout
        if prop=='cellDataType':base=base.replace('; dlv:cellDataType b:uint8','')
        if prop=='dimensionSizeFromField':base=base.replace('; dlv:dimensionSize 8','')
        if prop.startswith('chunk') and prop!='chunkOffsetsFromField':base+='ex:l dlv:chunkOffsetsFromField ex:f. '
        for label,value,ok in [('valid',good,True),('duplicate',good+','+second,False),('bad',bad,False)]:add(prop+' '+label,base,owner,prop,value,ok)
    for cls,prop,good,second,bad in [('CellDataTypeRule','ruleCellDataType','b:uint8','b:uint16','ex:unknown'),('DimensionOrderRule','ruleDimensionOrder','(ex:d)','(ex:d)','"dimension"')]:
        base=layout+'ex:r a dlv:'+cls+'. '
        for label,value,ok in [('valid',good,True),('duplicate',good+','+second,False),('bad',bad,False),('missing',None,False)]:
            add(cls+' '+prop+' '+label,base+'ex:r b:condition "true". ','ex:r',prop,value,ok)
        for label,value,ok in [('bad','1',False),('duplicate','"true","false"',False),('missing',None,False)]:
            add(cls+' condition '+label,base+'ex:r dlv:'+prop+' '+good+'. ','ex:r','b:condition',value,ok)
    add('missing axis',layout.replace('; dlv:hasAxis ex:axis',''),'ex:d','hasAxis',None,False)
    return rows
