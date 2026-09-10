"""Transport integer boundaries, including RFC 768's absent-source-port encoding."""
from pathlib import Path
import base64, sys
from rdflib import Graph, Namespace, URIRef
from pyshacl import validate
ROOT=Path(__file__).resolve().parents[1]
SH=Namespace('http://www.w3.org/ns/shacl#')
NS='https://hexplain.io/ns/aspect/networkflow#'
shapes=Graph().parse(ROOT/'specification/npv/net.ttl')
rows=['# name\tconforms\texpected-path\tbase64 Turtle']
for field,maximum in [('sourcePort',65535),('destinationPort',65535),('sequenceNumber',4294967295),('acknowledgmentNumber',4294967295)]:
    values=[('zero','0',True),('maximum',str(maximum),True),('overflow',str(maximum+1),False),
            ('negative','-1',False),('fraction','1.5',False),('decimal integer','1.0',False),
            ('string','"1"',False),('typed integer','"1"^^<http://www.w3.org/2001/XMLSchema#unsignedShort>',True),
            ('nonfinite','"INF"^^<http://www.w3.org/2001/XMLSchema#double>',False),('two values','1, 2',False)]
    for label,value,expected in values:
        name=field+' '+label
        source=f'<urn:packet> <{NS+field}> {value} .'
        ok,report,detail=validate(Graph().parse(data=source,format='turtle'),shacl_graph=shapes,inference='none')
        assert bool(ok)==expected,(name,detail)
        if not expected:assert URIRef(NS+field) in report.objects(None,SH.resultPath),(name,detail)
        rows.append('\t'.join([name,str(expected).lower(),NS+field if not expected else '',base64.b64encode(source.encode()).decode()]))
rendered='\n'.join(rows)+'\n'
p=ROOT/'specification/validation/test/network-competency.tsv'
if '--write' in sys.argv:p.write_text(rendered,encoding='utf-8')
else:assert p.read_text(encoding='utf-8')==rendered
print('PASS: 40 transport boundary contracts; each property independently activates validation')
