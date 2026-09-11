"""Generate the public sitemap and check local HTML links without network access."""
from html.parser import HTMLParser
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://hexplain.io"


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.ids, self.links = set(), []
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs: self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs: self.links.append(attrs["href"])


def pages():
    return [ROOT/"index.html", *sorted((ROOT/"specification").rglob("*.html"))]


def print_link(page):
    href=os.path.relpath(ROOT/'specification/print.css',page.parent).replace(os.sep,'/')
    return f'<link rel="stylesheet" href="{href}" media="print">'


def with_print_link(page,source):
    # Generated pages apply this themselves so their output already carries the link;
    # otherwise the page-equality gates and this sync pass contradict each other.
    link=print_link(page)
    if link in source: return source
    if re.search(r'</head>',source,re.I):
        return re.sub(r'</head>',lambda m:link+'\n'+m.group(),source,count=1,flags=re.I)
    if re.search(r'</title>',source,re.I):
        return re.sub(r'</title>',lambda m:m.group()+'\n'+link,source,count=1,flags=re.I)
    raise ValueError(f'No HTML head/title in {page}')


def sync_print_styles():
    for page in pages():
        source=page.read_text(encoding='utf-8');updated=with_print_link(page,source)
        if updated!=source: page.write_text(updated,encoding='utf-8')

def sitemap():
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(
        f"  <url><loc>{escape(ORIGIN+'/'+p.relative_to(ROOT).as_posix())}</loc></url>\n" if p.name != "index.html" or p.parent != ROOT else f"  <url><loc>{ORIGIN}/</loc></url>\n" for p in pages()) + '</urlset>\n'


def broken_links():
    parsed = {p.resolve():Page(p) for p in pages()}
    broken = []
    for path, page in list(parsed.items()):
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc or not link: continue
            target = (ROOT/unquote(url.path).lstrip('/') if url.path.startswith('/') else path.parent/unquote(url.path)).resolve() if url.path else path
            # Links into a sibling private checkout are not public links even if locally present.
            if not target.is_relative_to(ROOT):
                broken.append((path.relative_to(ROOT).as_posix(), link, "outside public site")); continue
            if target.is_dir(): target /= "index.html"
            if not target.is_file():
                broken.append((path.relative_to(ROOT).as_posix(), link, "missing file")); continue
            if url.fragment and target.suffix == ".html":
                if target not in parsed: parsed[target] = Page(target)
                if unquote(url.fragment) not in parsed[target].ids:
                    broken.append((path.relative_to(ROOT).as_posix(), link, "missing fragment"))
    return broken


if __name__ == "__main__":
    sync_print_styles()
    (ROOT/"sitemap.xml").write_text(sitemap(), encoding="utf-8")
    print(f"Generated sitemap for {len(pages())} public pages")
