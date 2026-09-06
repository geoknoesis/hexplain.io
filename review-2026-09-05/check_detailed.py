"""Verify report links, unique anchors, source hashes and score arithmetic."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json

ROOT = Path(__file__).resolve().parent
class Report(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.cards = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs: self.ids.append(attrs['id'])
        if tag == 'a' and 'href' in attrs: self.links.append(attrs['href'])
        if tag == 'article' and 'data-repo' in attrs: self.cards.append(attrs['id'])

page = Report(); page.feed((ROOT/'index.html').read_text(encoding='utf-8'))
data = json.loads((ROOT/'detailed-findings.json').read_text(encoding='utf-8'))
assert len(page.ids) == len(set(page.ids)), 'Duplicate HTML anchors'
assert set(page.cards) == {f['id'] for f in data['findings']}
for href in page.links:
    url = urlsplit(href)
    if url.scheme or url.netloc: continue
    if not url.path:
        assert not url.fragment or url.fragment in page.ids, href
    else:
        assert (ROOT/unquote(url.path)).exists(), href
for finding in data['findings']:
    for source in finding['sources']:
        path = ROOT/source['href']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'], source['file']
for repo, index in [('spec',2), ('engine',3), ('saas',4)]:
    value = sum(Decimal(str(row[index]))*row[1] for row in data['dimensions'])/100
    assert float(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) == data['scores'][repo]
for name in ['core','adapters','hdl','backend']:
    assert all(data['metrics'][name][key] == 0 for key in ['failures','errors','skipped'])
print(f"PASS: {len(page.cards)} assessments, {len(page.links)} links, unique anchors, source hashes and scores")
