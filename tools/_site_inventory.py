"""Generate the public sitemap and check local HTML links without network access."""

from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
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
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])


def pages() -> list[Any]:
    # The snapshot index is public too: it is where a pinned version is downloaded from.
    return [ROOT / "index.html", ROOT / "releases/index.html", *sorted((ROOT / "specification").rglob("*.html"))]


def print_link(page: Path) -> str:
    href = os.path.relpath(ROOT / "specification/print.css", page.parent).replace(os.sep, "/")
    return f'<link rel="stylesheet" href="{href}" media="print">'


def with_print_link(page: Path, source: str) -> Any:
    # Generated pages apply this themselves so their output already carries the link;
    # otherwise the page-equality gates and this sync pass contradict each other.
    link = print_link(page)
    if link in source:
        return source
    if re.search(r"</head>", source, re.I):
        return re.sub(r"</head>", lambda m: link + "\n" + m.group(), source, count=1, flags=re.I)
    if re.search(r"</title>", source, re.I):
        return re.sub(r"</title>", lambda m: m.group() + "\n" + link, source, count=1, flags=re.I)
    raise ValueError(f"No HTML head/title in {page}")


def sync_print_styles() -> None:
    for page in pages():
        source = page.read_text(encoding="utf-8")
        updated = with_print_link(page, source)
        if updated != source:
            page.write_text(updated, encoding="utf-8", newline="\n")


def sitemap() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(
            f"  <url><loc>{escape(ORIGIN + '/' + p.relative_to(ROOT).as_posix())}</loc></url>\n"
            if p.name != "index.html" or p.parent != ROOT
            else f"  <url><loc>{ORIGIN}/</loc></url>\n"
            for p in pages()
        )
        + "</urlset>\n"
    )


def generated_on_demand(target: Path) -> bool:
    """A linked file that is not tracked but is rebuilt from the tree and pinned by a tracked manifest.

    The ontology review archive is 22 MB of files the tree already holds, so only its manifest
    (archive name, SHA-256 and every entry's hash) is tracked; `python tools/_review_candidate.py
    --archive-only` rebuilds it and the validate workflow retains it as an artifact. The link to it
    is live once the archive is built, and tools/test_review_candidate.py proves the manifest pins it.
    """
    manifest = target.parent / "review-manifest.json"
    if target.parent != ROOT / "specification/ontology-review" or not manifest.is_file():
        return False
    record = json.loads(manifest.read_text(encoding="utf-8"))
    return record.get("archive") == target.name and record.get("archive_tracked") is False


def broken_links() -> Any:
    parsed = {p.resolve(): Page(p) for p in pages()}
    broken = []
    for path, page in list(parsed.items()):
        for link in page.links:
            url = urlsplit(link)
            if url.scheme or url.netloc or not link:
                continue
            target = (
                (
                    ROOT / unquote(url.path).lstrip("/")
                    if url.path.startswith("/")
                    else path.parent / unquote(url.path)
                ).resolve()
                if url.path
                else path
            )
            # Links into a sibling private checkout are not public links even if locally present.
            if not target.is_relative_to(ROOT):
                broken.append((path.relative_to(ROOT).as_posix(), link, "outside public site"))
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file() and not generated_on_demand(target):
                broken.append((path.relative_to(ROOT).as_posix(), link, "missing file"))
                continue
            if url.fragment and target.suffix == ".html":
                if target not in parsed:
                    parsed[target] = Page(target)
                if unquote(url.fragment) not in parsed[target].ids:
                    broken.append((path.relative_to(ROOT).as_posix(), link, "missing fragment"))
    return broken


if __name__ == "__main__":
    sync_print_styles()
    (ROOT / "sitemap.xml").write_text(sitemap(), encoding="utf-8", newline="\n")
    print(f"Generated sitemap for {len(pages())} public pages")
