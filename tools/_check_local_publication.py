"""Exercise the actual Nginx configuration in a disposable local container."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error
from rdflib import Graph
from rdflib.compare import isomorphic
from _publication import ROOT, routes

image = (ROOT/"deployment/nginx-image.txt").read_text(encoding="utf-8").strip()
command = ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::8080", "--mount", f"type=bind,source={ROOT},target=/srv/hexplain,readonly", "--mount", f"type=bind,source={ROOT/'deployment/publication.conf'},target=/etc/nginx/conf.d/default.conf,readonly", image]
container = subprocess.check_output(command, text=True).strip()
checks = []
try:
    binding = subprocess.check_output(["docker","port",container,"8080/tcp"],text=True).strip()
    base = "http://"+binding
    for attempt in range(30):
        try:
            with urllib.request.urlopen(base+"/",timeout=2) as response: response.read(1)
            break
        except (urllib.error.URLError, ConnectionError): time.sleep(.2)
    for route, file in sorted(routes().items()):
        with urllib.request.urlopen(urllib.request.Request(base+route,headers={"Accept":"text/turtle"}),timeout=10) as response:
            assert response.headers.get_content_type()=="text/turtle", route
            assert isomorphic(Graph().parse(data=response.read(),format="turtle"),Graph().parse(data=file.read_bytes(),format="turtle")),route
        checks.append(route)
    for manifest in sorted((ROOT/"releases").glob("*/manifest.json")):
        with urllib.request.urlopen(base+'/'+manifest.relative_to(ROOT).as_posix()) as response:
            assert response.headers.get_content_type()=="application/json"
            assert json.load(response)==json.loads(manifest.read_text(encoding="utf-8"))
        data=json.loads(manifest.read_text(encoding="utf-8"))
        import hashlib
        with urllib.request.urlopen(base+'/'+(manifest.parent/data['archive']).relative_to(ROOT).as_posix()) as response:
            assert hashlib.sha256(response.read()).hexdigest()==data['sha256']
        checks.append(manifest.relative_to(ROOT).as_posix())
    try:
        urllib.request.urlopen(base+"/ns/unknown-review-probe",timeout=5)
        raise AssertionError("Unknown namespace did not return 404")
    except urllib.error.HTTPError as error: assert error.code==404
    out=ROOT/".gate-results/local-publication.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(image=image,passed=True,checks=checks,unknown_namespace_status=404),indent=2)+"\n",encoding="utf-8")
    print(f"PASS: actual Nginx image/config, {len(checks)} ontology/version/release checks, archive bytes and unknown-IRI 404")
finally:
    subprocess.run(["docker","stop",container],check=True,capture_output=True)
