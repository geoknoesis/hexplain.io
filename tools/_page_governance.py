"""Registration and shared-quantity contracts for every published page.

Generated pages are checked against their generators. Pages that are written by
hand were checked by nothing, so counts inside them went stale while the
generated pages stayed correct. Registration makes an unchecked page a failure
rather than an oversight, and the quantity contracts below pin the few numbers
that several pages restate about one shared source.
"""
import html
import json
import re

from _site_inventory import ROOT, pages

REGISTRY = ROOT/'specification/page-governance.json'
MANIFEST = ROOT/'specification/ontology-review/review-manifest.json'
LAYOUT_CORPUS = ROOT/'specification/validation/test/layout-competency.tsv'

# A historical page keeps the numbers that were true when it was written, so it
# is exempt from the quantity contracts and must say so where a reader can see it.
HISTORICAL_MARKERS = ('historical', 'superseded')


def visible_text(page):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', page.read_text(encoding='utf-8'))))


def review_resources():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))['resources']


def review_modules():
    return json.loads(MANIFEST.read_text(encoding='utf-8'))['modules']


def layout_cases():
    lines = LAYOUT_CORPUS.read_text(encoding='utf-8').splitlines()
    return sum(1 for line in lines if line.strip() and not line.startswith('#'))


# Phrase a page uses for a quantity, and the authority that quantity comes from.
QUANTITIES = {
    'review_resources': (r'(\d[\d,]*)\s+resources', review_resources),
    'review_modules': (r'(\d[\d,]*)\s+modules', review_modules),
    'layout_cases': (r'(\d[\d,]*)\s+identical cases', layout_cases),
}


def registry():
    return json.loads(REGISTRY.read_text(encoding='utf-8'))


def registered_pages():
    return {p: entry for p, entry in registry()['pages'].items()}


def problems():
    """Every registration and quantity mismatch, as reportable strings."""
    found = []
    declared = registered_pages()
    published = {page.relative_to(ROOT).as_posix(): page for page in pages()}

    for path in sorted(set(published) - set(declared)):
        found.append(f'{path}: published but not registered in {REGISTRY.name}')
    for path in sorted(set(declared) - set(published)):
        found.append(f'{path}: registered but not published')

    for path, page in sorted(published.items()):
        entry = declared.get(path)
        if entry is None:
            continue
        status = entry.get('status')
        if status not in ('current', 'historical'):
            found.append(f'{path}: unknown status {status!r}')
            continue
        text = visible_text(page)
        if status == 'historical':
            if not any(marker in text.lower() for marker in HISTORICAL_MARKERS):
                found.append(f'{path}: registered historical but says so nowhere a reader can see')
            continue
        for name, (pattern, authority) in QUANTITIES.items():
            expected = authority()
            for match in re.finditer(pattern, text):
                stated = int(match.group(1).replace(',', ''))
                if stated != expected:
                    context = text[max(0, match.start()-60):match.end()+20].strip()
                    found.append(f'{path}: states {stated} for {name}, authority says {expected} — ...{context}')
    return found
