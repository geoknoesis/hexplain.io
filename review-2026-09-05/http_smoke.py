"""Local, disposable seeded instance only. Credentials supplied by environment."""
import os, json, re, urllib.request as u, urllib.parse as p, urllib.error, http.cookiejar
from pathlib import Path
b=os.environ.get('REVIEW_URL','http://127.0.0.1:13000')
o=u.build_opener(u.HTTPCookieProcessor(http.cookiejar.CookieJar()))
results=[]
def get(path): return json.load(o.open(b+path,timeout=60))
def check(name, ok):
    assert ok, name
    results.append({'check':name,'passed':True})
def status(path, expected, anonymous=False):
    try: (u.urlopen if anonymous else o.open)(b+path,timeout=60)
    except urllib.error.HTTPError as e: check(path,e.code==expected); return
    raise AssertionError(path)
s=o.open(b+'/login',timeout=60).read().decode()
t=re.search(r'name="_csrf"[^>]*value="([^"]+)"',s).group(1)
r=o.open(u.Request(b+'/login',p.urlencode({'username':os.environ['REVIEW_USER'],'password':os.environ['REVIEW_PASSWORD'],'_csrf':t}).encode()))
check('Login stays on frontend origin', r.status==200 and r.url==b+'/')
status('/v1/formats',401,True)
status('/v1/formats?workspaceId=foreign',404)
formats=get('/v1/formats'); files=get('/v1/files'); versions=get('/v1/formats/fmt-png/versions')
check('Authenticated lists',len(formats)>0 and len(files)>0 and len(versions)>0)
v=versions[0]['id'];f=files[0]['id'];token=get('/v1/csrf')
req=u.Request(b+'/v1/runs',json.dumps({'profileVersionId':v,'fileId':f,'force':True}).encode(),headers={'Content-Type':'application/json',token['headerName']:token['token']})
run=json.load(o.open(req)); check('CSRF protected validation run',run['status']=='SUCCEEDED' and run['profileVersionId']==v)
check('Findings load',isinstance(get('/v1/runs/'+run['id']+'/findings'),list))
view=get('/v1/files/'+f+'/view?profileVersionId='+v)
check('Typed viewer returns actual semantic graph',not view.get('error') and bool(view.get('semanticRdf')))
page=get('/v1/files/'+f+'/bytes?offset=4&count=8')
check('Byte API bounds page',page['offset']==4 and len(page['hex'])==16)
status('/v1/files/'+f+'/bytes?count=65537',400)
Path(__file__).with_name('http-smoke-results.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
