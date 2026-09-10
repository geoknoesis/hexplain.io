"""Required rule, dispatch and grouping declarations, independently authored."""
from _physical_property_cases import PREFIX
def cases():
    rows=[]
    pre=PREFIX+'ex:struct a b:Struct. ex:table a b:DispatchTable; b:dispatchOnField ex:count. ex:table2 a b:DispatchTable; b:dispatchOnExpression "key". '
    def add(name,body,ok,path=''):
        rows.append(dict(name='structural '+name,module='specification/bddo/bddo.ttl',data=pre+body,expected=ok,path='https://hexplain.io/ns/bddo#'+path if path else ''))
    for cls,values,alternatives,invalid in [
        ('DataTypeRule',{'condition':'"true"','ruleDataType':'b:uint8'},{'condition':'"false"','ruleDataType':'ex:struct'},{'condition':'1','ruleDataType':'ex:unknown'}),
        ('EndiannessRule',{'condition':'"true"','ruleEndianness':'b:BigEndian'},{'condition':'"false"','ruleEndianness':'b:LittleEndian'},{'condition':'1','ruleEndianness':'ex:unknown'}),
        ('DispatchArm',{'armTable':'ex:table','armKey':'1','armDataType':'b:uint8'},{'armTable':'ex:table2','armKey':'2','armDataType':'ex:struct'},{'armTable':'ex:unknown','armKey':'true','armDataType':'ex:unknown'}),
        ('RecordGrouping',{'groupingStyle':'b:keyedGroup','groupOpenToken':'"BEGIN"','groupCloseToken':'"END"'},{'groupingStyle':'b:valuedGroup','groupOpenToken':'"OPEN"','groupCloseToken':'"CLOSE"'},{'groupingStyle':'ex:unknown','groupOpenToken':'1','groupCloseToken':'1'}),
        ('NamespaceBinding',{'namespacePrefix':'"x"','namespaceIRI':'"urn:x:"^^xsd:anyURI'},{'namespacePrefix':'"y"','namespaceIRI':'"urn:y:"^^xsd:anyURI'},{'namespacePrefix':'1','namespaceIRI':'1'}),
        ('Checksum',{'checksumAlgorithm':'b:crc32'},{'checksumAlgorithm':'b:sha256'},{'checksumAlgorithm':'ex:unknown'})]:
        def body(v):return 'ex:f a b:'+cls+'. '+''.join('ex:f b:'+p+' '+value+'. ' for p,value in v.items())
        add(cls+' valid',body(values),True)
        for prop in values:
            for label,value in [('missing',None),('duplicate',values[prop]+','+alternatives[prop]),('invalid',invalid[prop])]:
                changed=dict(values)
                if value is None:del changed[prop]
                else:changed[prop]=value
                add(cls+' '+prop+' '+label,body(changed),False,prop)
        if cls in ['DataTypeRule','DispatchArm']:
            prop='ruleDataType' if cls=='DataTypeRule' else 'armDataType'
            changed=dict(values);changed[prop]='ex:struct';add(cls+' structured branch',body(changed),True)
            changed[prop]='"type"';add(cls+' literal type',body(changed),False,prop)
    for prop,good,second,bad,base in [
        ('dataType','b:uint8','ex:struct','ex:unknown','ex:f a b:Field.'),
        ('hasDispatchTable','ex:table','ex:table2','ex:unknown','ex:f a b:Field.'),
        ('hasField','(ex:count)','(ex:other)','"fields"','ex:f a b:Struct.'),
        ('dispatchDefault','b:uint8','ex:struct','ex:unknown','ex:f a b:DispatchTable; b:dispatchOnField ex:count.'),
        ('dispatchOnField','ex:count','ex:other','ex:unknown','ex:f a b:DispatchTable.'),
        ('dispatchOnExpression','"key"','"other"','1','ex:f a b:DispatchTable.'),
        ('pathSeparator','"/"','"."','1','ex:f a b:DelimitedRecords; b:hasField (ex:count).')]:
        for label,value,ok in [('valid',good,True),('duplicate',good+','+second,False),('invalid',bad,False)]:
            add(prop+' '+label,base+' ex:f b:'+prop+' '+value+'.',ok,'' if ok else prop)
    return rows
