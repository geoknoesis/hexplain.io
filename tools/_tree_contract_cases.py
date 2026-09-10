"""Tree and grouped-record selectors remain scoped to their containers."""
from _physical_property_cases import PREFIX
def cases():
    rows=[]
    def add(name,body,ok,path='',shape=''):
        r=dict(name='tree '+name,module='specification/bddo/bddo.ttl',expected=ok,path='https://hexplain.io/ns/bddo#'+path if path else '',data=PREFIX+body)
        if shape:r['expectedShape']='https://hexplain.io/ns/bddo#'+shape
        rows.append(r)
    tree='ex:t a b:TreeDocument; b:treeSyntax b:xml; b:hasField (ex:f). ex:f a b:Field; b:dataType b:uint8; b:nodePath "/x". '
    for label,value,ok in [('xml','b:xml',True),('json','b:json',True),('unknown','ex:unknown',False),('duplicate','b:xml,b:json',False),('missing',None,False)]:
        add('syntax '+label,tree.replace('b:treeSyntax b:xml; ','')+('ex:t b:treeSyntax '+value+'.' if value else ''),ok,'' if ok else 'treeSyntax')
    add('missing fields','ex:t a b:TreeDocument; b:treeSyntax b:xml.',False,'hasField')
    add('untyped namespace',tree+'ex:t b:hasNamespaceBinding ex:unknown.',False,'hasNamespaceBinding')
    for label,value in [('wrong type','1'),('duplicate','"/x","/y"'),('missing',None)]:
        add('node path '+label,tree.replace('; b:nodePath "/x"','')+('ex:f b:nodePath '+value+'.' if value else ''),False,'' if value is None else 'nodePath')
    grouping='ex:g a b:RecordGrouping; b:groupingStyle b:keyedGroup; b:groupOpenToken "BEGIN"; b:groupCloseToken "END". '
    grouped=grouping+'ex:t a b:KeyValueHeader; b:keyValueSeparator "3D"^^xsd:hexBinary; b:hasField (ex:f); b:hasGrouping ex:g. ex:f a b:Field; b:dataType b:uint8. '
    for prop in ['key','keyPath']:
        add(prop+' valid',grouped+'ex:f b:'+prop+' "x".',True)
        add(prop+' duplicate',grouped+'ex:f b:'+prop+' "x","y".',False)
    add('key path datatype',grouped+'ex:f b:keyPath 1.',False,'keyPath')
    add('table without separator','ex:t a b:DelimitedTable; b:hasField (ex:count).',False)
    add('table with key','ex:t a b:DelimitedTable; b:fieldDelimiter "2C"^^xsd:hexBinary; b:hasField (ex:count). ex:count b:key "x".',False)
    add('records without fields','ex:t a b:DelimitedRecords.',False,'hasField')
    return rows
