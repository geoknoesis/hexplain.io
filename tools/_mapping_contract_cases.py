"""Mapping, language, unit and enumeration contracts with explicit expectations."""
PREFIX='''@prefix ex:<urn:mapping-contract:> . @prefix h:<https://hexplain.io/ns/core#> .
@prefix b:<https://hexplain.io/ns/bddo#> . @prefix rdf:<http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix owl:<http://www.w3.org/2002/07/owl#> . @prefix xsd:<http://www.w3.org/2001/XMLSchema#> .
ex:f a b:Field . ex:other a b:Field . ex:struct a b:Struct . ex:Class a owl:Class . ex:OtherClass a owl:Class .
ex:p a rdf:Property . ex:op a owl:ObjectProperty . ex:dp a owl:DatatypeProperty . ex:ap a owl:AnnotationProperty .
'''
def cases():
    rows=[]
    def add(name,data,expected,path='',module='hexplain/core.ttl'):
        rows.append(dict(name=name,module='specification/'+module,expected=expected,path=('https://hexplain.io/ns/core#'+path) if path else '',data=PREFIX+data.replace(".ex:",". ex:")))
    for name,predicate,valid,invalid in [
        ('object property','mapsToObjectProperty','ex:op','ex:dp'),
        ('expression','valueExpression','"value + 1"','1'),
        ('language','language','"en-US"^^xsd:language','"en-US"'),
        ('dynamic language','languageFromField','ex:other','ex:unknown'),
        ('unit','unit','ex:unit','"metre"')]:
        add(name+' valid',f'ex:f h:{predicate} {valid}.',True)
        add(name+' invalid value',f'ex:f h:{predicate} {invalid}.',False,predicate)
        add(name+' untyped owner',f'ex:untyped h:{predicate} {valid}.',False)
        extra={'mapsToObjectProperty':'ex:p','valueExpression':'"value + 2"','language':'"fr"^^xsd:language','languageFromField':'ex:f','unit':'ex:otherUnit'}[predicate]
        add(name+' duplicate',f'ex:f h:{predicate} {valid},{extra}.',False,predicate)
    add('object generic property','ex:f h:mapsToObjectProperty ex:p.',True)
    add('object literal','ex:f h:mapsToObjectProperty "p".',False,'mapsToObjectProperty')
    add('object untyped property','ex:f h:mapsToObjectProperty ex:unknown.',False,'mapsToObjectProperty')
    add('fixed and dynamic language','ex:f h:language "en"^^xsd:language; h:languageFromField ex:other.',False,'languageFromField')
    for value,ok in [('ex:Class',True),('ex:unknown',False),('"Class"',False)]:
        add('class mapping '+value,'ex:struct h:mapsToClass '+value+'.',ok,'' if ok else 'mapsToClass')
    add('class mapping wrong owner','ex:f h:mapsToClass ex:Class.',False)
    for kind,property_,target in [('MappingRule','semanticProperty','ex:p'),('ClassMappingRule','semanticClass','ex:Class')]:
        base=f'ex:r a h:{kind}; h:condition "true"; h:{property_} {target}.'
        add(kind+' valid',base,True)
        add(kind+' missing condition',base.replace('h:condition "true";',''),False,'condition')
        add(kind+' condition type',base.replace('"true"','1'),False,'condition')
        add(kind+' condition IRI',base.replace('"true"','ex:condition'),False,'condition')
        add(kind+' two conditions',base+'ex:r h:condition "false".',False,'condition')
        add(kind+' missing target',f'ex:r a h:{kind}; h:condition "true".',False,property_)
        add(kind+' untyped target',base.replace(target,'ex:unknown'),False,property_)
        add(kind+' literal target',base.replace(target,'"target"'),False,property_)
        add(kind+' two targets',base+f'ex:r h:{property_} '+('ex:op' if kind=='MappingRule' else 'ex:OtherClass')+'.',False,property_)
        if kind=='MappingRule':
            for typ in ['ex:op','ex:dp','ex:ap']:add('mapping '+typ,base.replace('ex:p',typ),True)
            for prop,good,bad in [('valueExpression','"value * 2"','2'),('valueDatatype','xsd:integer','"integer"')]:
                add('rule '+prop,base+f'ex:r h:{prop} {good}.',True)
                add('rule bad '+prop,base+f'ex:r h:{prop} {bad}.',False,prop)
                add('rule duplicate '+prop,base+f'ex:r h:{prop} {good},'+('"value * 3"' if prop=='valueExpression' else 'xsd:string')+'.',False,prop)
    for prop,owner,kind,rule in [
        ('hasConditionalMapping','ex:f','MappingRule','ex:r a h:MappingRule; h:condition "true"; h:semanticProperty ex:p.'),
        ('hasConditionalClassMapping','ex:struct','ClassMappingRule','ex:r a h:ClassMappingRule; h:condition "true"; h:semanticClass ex:Class.')]:
        add(prop+' valid',rule+f'{owner} h:{prop} (ex:r).',True)
        add(prop+' bad list member',f'{owner} h:{prop} (ex:untyped).',False)
        add(prop+' wrong owner',rule+f'ex:untyped h:{prop} (ex:r).',False)
    add('fixed conditional class conflict','ex:r a h:ClassMappingRule; h:condition "true"; h:semanticClass ex:Class. ex:struct h:mapsToClass ex:Class; h:hasConditionalClassMapping (ex:r).',False,'mapsToClass')
    # Enumeration tests use the full BDDO module, independent from mapping shapes.
    for name,body,ok,path in [
        ('enumeration','ex:e a b:Enumeration; b:hasEnumValue ex:v. ex:v a b:EnumValue; b:enumRawValue 1; b:enumSymbol ex:s.',True,''),
        ('missing member','ex:e a b:Enumeration.',False,'hasEnumValue'),
        ('wrong member','ex:e a b:Enumeration; b:hasEnumValue ex:untyped.',False,'hasEnumValue'),
        ('raw required','ex:v a b:EnumValue.',False,'enumRawValue'),
        ('two raw values','ex:v a b:EnumValue; b:enumRawValue 1,2.',False,'enumRawValue'),
        ('literal symbol','ex:v a b:EnumValue; b:enumRawValue 1; b:enumSymbol "name".',False,'enumSymbol'),
        ('two symbols','ex:v a b:EnumValue; b:enumRawValue 1; b:enumSymbol ex:a,ex:b.',False,'enumSymbol')]:
        # Avoid unrelated bare Field/Struct targets in the module-scoped BDDO data.
        prefix=PREFIX[:PREFIX.index('ex:f a b:Field')]
        rows.append(dict(name=name,module='specification/bddo/bddo.ttl',expected=ok,path='https://hexplain.io/ns/bddo#'+path if path else '',data=prefix+body))
    for label,flags,ok in [('true','true',True),('false','false',True),('literal','"true"',False),('duplicate','true,false',False)]:
        rows.append(dict(name='enumeration flags '+label,module='specification/bddo/bddo.ttl',expected=ok,path='' if ok else 'https://hexplain.io/ns/bddo#enumIsFlags',data=PREFIX[:PREFIX.index('ex:f a b:Field')]+f'ex:e a b:Enumeration; b:hasEnumValue ex:v; b:enumIsFlags {flags}. ex:v a b:EnumValue; b:enumRawValue 1.'))
    from itertools import combinations
    physical=PREFIX[:PREFIX.index('ex:f a b:Field')]+'''b:uint8 a b:DataType . b:bytes a b:DataType .
ex:count a b:Field; b:dataType b:uint8 .'''
    def physical_case(name,body,ok,shape):
        rows.append(dict(name=name,module='specification/bddo/bddo.ttl',expected=ok,path='',expectedShape='' if ok else 'https://hexplain.io/ns/bddo#'+shape,data=physical+body))
    groups=[
        ('FieldSizingShape','ex:f a b:Field; b:dataType b:uint8.', 'ex:f', [('size','1'),('sizeFromField','ex:count'),('sizeFromExpression','"1"'),('sizeToEndOfStream','true'),('terminator','"00"^^xsd:hexBinary')]),
        ('StructSizingShape','ex:s a b:Struct.', 'ex:s', [('size','1'),('sizeFromField','ex:count'),('sizeFromExpression','"1"')]),
        ('FieldOffsetShape','ex:f a b:Field; b:dataType b:uint8.', 'ex:f', [('atOffset','0'),('atOffsetFromField','ex:count'),('atOffsetFromExpression','"0"')]),
        ('FieldRepetitionShape','ex:f a b:Field; b:dataType b:uint8.', 'ex:f', [('repeatCount','1'),('repeatCountFromField','ex:count'),('repeatCountFromExpression','"1"'),('repeatUntil','"false"')]),
    ]
    for shape,base,owner,options in groups:
        for p,v in options:physical_case(shape+' single '+p,base+f' {owner} b:{p} {v}.',True,shape)
        for (p,v),(q,w) in combinations(options,2):physical_case(shape+' conflict '+p+' '+q,base+f' {owner} b:{p} {v}; b:{q} {w}.',False,shape)
    physical_case('derived expression only','ex:f a b:Field; b:valueFromExpression "1".',True,'DerivedFieldShape')
    for p,v in [('dataType','b:uint8'),('size','1'),('sizeFromField','ex:count'),('sizeFromExpression','"1"'),('sizeToEndOfStream','true'),('terminator','"00"^^xsd:hexBinary'),('bitLength','1'),('atOffset','0'),('atOffsetFromField','ex:count'),('atOffsetFromExpression','"0"')]:
        physical_case('derived conflicts '+p,f'ex:f a b:Field; b:valueFromExpression "1"; b:{p} {v}.',False,'DerivedFieldShape')
    physical_case('bytes with extent','ex:f a b:Field; b:dataType b:bytes; b:size 1.',True,'VariableLengthFieldShape')
    physical_case('bytes without extent','ex:f a b:Field; b:dataType b:bytes.',False,'VariableLengthFieldShape')
    physical_case('node path in tree','ex:t a b:TreeDocument; b:treeSyntax b:json; b:hasField (ex:f). ex:f a b:Field; b:dataType b:uint8; b:nodePath "/value".',True,'NodePathShape')
    physical_case('node path outside tree','ex:f a b:Field; b:dataType b:uint8; b:nodePath "/value".',False,'NodePathShape')
    return rows
