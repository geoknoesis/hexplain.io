"""Physical-description property contracts with independent wrong-value vectors."""
PREFIX='''@prefix ex:<urn:physical-property:> . @prefix b:<https://hexplain.io/ns/bddo#> .
@prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
b:uint8 a b:DataType . ex:count a b:Field; b:dataType b:uint8 .
ex:other a b:Field; b:dataType b:uint8 .
ex:enum a b:Enumeration; b:hasEnumValue ex:v . ex:v a b:EnumValue; b:enumRawValue 1 .
ex:enum2 a b:Enumeration; b:hasEnumValue ex:v .
ex:check a b:Checksum; b:checksumAlgorithm b:crc32 . ex:check2 a b:Checksum; b:checksumAlgorithm b:sha256 .
'''
VALUES={
 'positive':('1','2','0'), 'nonnegative':('0','1','-1'),
 'string':('"value"','"other"','1'), 'boolean':('true','false','"true"'),
 'hex':('"0A"^^xsd:hexBinary','"0D"^^xsd:hexBinary','"0A"'),
 'field':('ex:count','ex:other','ex:untyped'),
 'enum':('ex:enum','ex:enum2','ex:untyped'),
 'checksum':('ex:check','ex:check2','ex:untyped'),
 'seek':('b:regionScope','b:streamScope','ex:unknown'),
 'encoding':('b:utf8','b:ascii','ex:unknown'),
 'offset':('b:streamStart','b:parentStart','ex:unknown'),
 'endian':('b:BigEndian','b:LittleEndian','ex:unknown'),
 'bits':('b:MSBFirst','b:LSBFirst','ex:unknown'),
 'base':('b:baseInteger','b:baseFloat','ex:unknown'),
 'iri':('xsd:integer','xsd:string','"integer"'),
}

def cases():
    rows=[]
    def group(kind,base,properties):
        for prop,contract in properties:
            a,b,bad=VALUES[contract]
            context=base+(' ex:f b:atOffset 0.' if prop=='seekScope' else '')
            for label,value,ok in [('valid',a,True),('invalid',bad,False),('duplicate',a+','+b,False)]:
                rows.append(dict(name=kind+' '+prop+' '+label,module='specification/bddo/bddo.ttl',expected=ok,path='' if ok else 'https://hexplain.io/ns/bddo#'+prop,data=PREFIX+context+f' ex:f b:{prop} {value}.'))
    group('field','ex:f a b:Field; b:dataType b:uint8.',[
        ('seekScope','seek'),('size','positive'),('sizeFromField','field'),('sizeFromExpression','string'),
        ('sizeToEndOfStream','boolean'),('terminator','hex'),('trimNull','boolean'),('encoding','encoding'),
        ('bitLength','positive'),('alignment','positive'),('atOffset','nonnegative'),('atOffsetFromField','field'),
        ('atOffsetFromExpression','string'),('offsetBase','offset'),('enumeration','enum'),('checksum','checksum'),
        ('validIf','string'),('rootKeyFromField','field'),('isPresentIf','string')])
    group('derived','ex:f a b:Field.',[('valueFromExpression','string')])
    group('struct','ex:f a b:Struct.',[('endianness','endian'),('bitOrder','bits'),('syncOnMarker','hex'),('size','positive'),('sizeFromField','field'),('sizeFromExpression','string')])
    group('datatype','ex:f a b:DataType.',[('baseType','base'),('bitWidth','positive'),('isSigned','boolean'),('endianness','endian'),('xsdType','iri')])
    group('records','ex:f a b:DelimitedRecords; b:hasField (ex:count).',[
        ('recordDelimiter','hex'),('fieldDelimiter','hex'),('whitespaceSeparated','boolean'),('keyValueSeparator','hex'),
        ('quoteChar','hex'),('escapeChar','hex'),('commentPrefix','string'),('skipRecords','nonnegative'),('trimWhitespace','boolean')])
    group('checksum','ex:f a b:Checksum; b:checksumAlgorithm b:crc32.',[
        ('coversFromField','field'),('coversToField','field'),('coversExpression','string'),('coversFromExpression','string'),('coversToExpression','string')])
    # bddo:separatedBy is itself the extent of a text-numeric field: the term admits exactly
    # one spelling, "whitespace", states it at most once, and -- being an answer to "where does
    # this element end" -- cannot be combined with any of the five other answers. Expectations
    # are taken from the term definition and the AsciiNumericWidthShape message, not from the
    # shape graph.
    base=PREFIX+'b:asciiInteger a b:DataType. ex:f a b:Field; b:dataType b:asciiInteger. '
    def separated(name,body,ok,path='',shape=''):
        rows.append(dict(name='separated '+name,module='specification/bddo/bddo.ttl',expected=ok,
            path='https://hexplain.io/ns/bddo#'+path if path else '',
            expectedShape='https://hexplain.io/ns/bddo#'+shape if shape else '',data=base+body))
    separated('scalar extent','ex:f b:separatedBy "whitespace".',True)
    separated('repeated extent','ex:f b:separatedBy "whitespace"; b:repeatCount 3.',True)
    separated('non-string separator','ex:f b:separatedBy 1.',False,'separatedBy')
    separated('unlisted separator','ex:f b:separatedBy "comma".',False,'separatedBy')
    separated('two separators','ex:f b:separatedBy "whitespace","comma".',False,'separatedBy')
    for prop,value in [('size','4'),('sizeFromField','ex:count'),('sizeFromExpression','"4"'),
                       ('sizeToEndOfStream','true'),('terminator','"20"^^xsd:hexBinary')]:
        separated('excludes '+prop,f'ex:f b:separatedBy "whitespace"; b:{prop} {value}.',False,shape='FieldShape')
    separated('ascii numeric width accepts a separator','ex:f b:separatedBy "whitespace"; b:encoding b:ascii.',True)
    separated('ascii numeric width rejects no extent','',False,shape='AsciiNumericWidthShape')
    return rows
