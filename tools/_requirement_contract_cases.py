"""Attribution, expression and requirement identity contracts."""
def cases():
    rows=[]
    for module,cls,values,invalid in [
        ('req','Requirement',{'requirementId':'"R01"','fromStandard':'"format specification"','statement':'"Must have a header"','discrepancyType':'p:Syntactic'}, {'requirementId':'1','fromStandard':'1','statement':'1','discrepancyType':'ex:unknown'}),
        ('conf','Constraint',{'scope':'ex:field','assertion':'"true"','satisfies':'ex:requirement','message':'"Header missing"'}, {'scope':'"field"','assertion':'1','satisfies':'ex:untyped','message':'1'})]:
        prefix=f'@prefix p:<https://hexplain.io/ns/{module}#> . @prefix ex:<urn:requirement-case:> . ex:requirement a <https://hexplain.io/ns/req#Requirement> .'
        if module=='req':prefix=prefix.split('ex:requirement a')[0]
        def add(name,changed,expected,path=''):
            body=' ex:f a p:'+cls+'. '+''.join('ex:f p:'+p+' '+v+'. ' for p,v in changed.items())
            rows.append(dict(name=module+' '+name,module='specification/'+module+'/shapes.ttl',data=prefix+body,expected=expected,path='https://hexplain.io/ns/'+module+'#'+path if path else ''))
        add('valid',values,True)
        for prop in values:
            for label,value in [('missing',None),('wrong value',invalid[prop])]:
                changed=dict(values)
                if value is None:del changed[prop]
                else:changed[prop]=value
                add(prop+' '+label,changed,False,prop)
            if prop!='satisfies':
                second='p:Semantic' if prop=='discrepancyType' else ('ex:other' if prop=='scope' else '"different"')
                changed=dict(values);changed[prop]+=','+second
                add(prop+' duplicate',changed,False,prop)
        prop='requirementId' if module=='req' else 'assertion'
        changed=dict(values);changed[prop]='""';add(prop+' empty',changed,False,prop)
        if module=='req':
            for val,ok in [('"1.0"',True),('1',False)]:
                changed=dict(values);changed['appliesToVersion']=val
                add('version '+str(ok),changed,ok,'' if ok else 'appliesToVersion')
    return rows
