"""Exercise publication acceptance against a controlled HTTP origin."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from tempfile import TemporaryDirectory
import json, subprocess, sys
from rdflib import Graph, OWL, RDF

root=Path(__file__).resolve().parents[1]
routes={}
for module in json.loads((root/'specification/reference/manifest.json').read_text(encoding='utf-8')):
    for file in (root/module['module']).glob('*.ttl'):
        for ontology in Graph().parse(file,format='turtle').subjects(RDF.type,OWL.Ontology):
            iri=str(ontology)
            if iri.startswith('https://hexplain.io/ns/'):
                routes[iri.removeprefix('https://hexplain.io')]=('text/turtle',file.read_bytes())
for file in (root/'releases').glob('*/manifest.json'):
    routes['/'+file.relative_to(root).as_posix()]=('application/json',file.read_bytes())
class Handler(BaseHTTPRequestHandler):
    fallback=False
    def log_message(self,*args): pass
    def do_GET(self):
        media,body=routes.get(self.path,('text/plain',b'missing'))
        if self.fallback:media,body='text/html',b'<html>fallback</html>'
        self.send_response(200);self.send_header('Content-Type',media);self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
Thread(target=server.serve_forever,daemon=True).start()
try:
    with TemporaryDirectory() as temporary:
        output=Path(temporary)/'result.json'
        command=[sys.executable,str(root/'tools/check_live_publication.py'),'--base-url',f'http://127.0.0.1:{server.server_port}','--output',str(output)]
        for fallback in [False,True]:
            Handler.fallback=fallback
            result=subprocess.run(command,capture_output=True,text=True,timeout=90)
            assert result.returncode == (1 if fallback else 0),result.stdout+result.stderr
            checks=json.loads(output.read_text())['checks']
            assert len(checks)==len(routes)
            assert all(row['passed'] != fallback for row in checks)
finally:
    server.shutdown();server.server_close()
print(f'PASS: {len(routes)} namespace/release routes; canonical success and HTTP 200 HTML fallback rejection')
