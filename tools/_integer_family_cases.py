"""Exercise each promised integer datatype alternative with the same exact value."""
def cases():
    from test_layout_competency import PREFIX,layout
    names='integer positiveInteger nonNegativeInteger int long short byte unsignedInt unsignedLong unsignedShort unsignedByte'.split()
    rows=[]
    def add(name,module,data,expected=True,path=''):
        rows.append(dict(name=name,module=module,expected=expected,path=path,data=data))
    for prop in ['cellBitWidth','dimensionSize','dimensionStride','chunkSize']:
        base=layout
        if prop=='dimensionSize':base=base.replace('; dlv:dimensionSize 8','')
        if prop=='chunkSize':base+='ex:l dlv:chunkOffsetsFromField ex:f. '
        owner='ex:l' if prop=='cellBitWidth' else 'ex:d'
        for datatype in names:
            if datatype in ('integer','unsignedByte'):continue # Already exercised by retained layout cases.
            add(prop+' '+datatype,'specification/dlv/dlv.ttl',PREFIX+base+f'{owner} dlv:{prop} "1"^^xsd:{datatype}.')
        if prop in ('dimensionSize','chunkSize'):
            add(prop+' cardinality boundary','specification/dlv/dlv.ttl',PREFIX+base+f'{owner} dlv:{prop} 1,2.',False,'https://hexplain.io/ns/dlv#'+prop)
    for prop in ['minParts','maxParts']:
        for datatype in names:
            if datatype=='integer':continue
            add(prop+' '+datatype,'specification/aspect/bundle/bundle.ttl',PREFIX+f'ex:spec a a:PartSpec; a:{prop} "1"^^xsd:{datatype}.')
        add(prop+' cardinality boundary','specification/aspect/bundle/bundle.ttl',PREFIX+f'ex:spec a a:PartSpec; a:{prop} 1,2.',False,'https://hexplain.io/ns/aspect/bundle#'+prop)
    for prop in ['sourcePort','destinationPort','sequenceNumber','acknowledgmentNumber']:
        for datatype in names:
            if datatype in ('integer','unsignedShort'):continue
            add(prop+' '+datatype,'specification/npv/net.ttl',f'<urn:packet> <https://hexplain.io/ns/aspect/networkflow#{prop}> "1"^^<http://www.w3.org/2001/XMLSchema#{datatype}>.')
    return rows
