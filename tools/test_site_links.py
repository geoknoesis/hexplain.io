"""Published local links and generated discovery metadata cannot drift."""
from _site_inventory import ROOT, ORIGIN, broken_links, sitemap, pages, print_link
broken = broken_links()
assert not broken, '\n'.join(map(str, broken))
assert (ROOT/"sitemap.xml").read_text(encoding="utf-8") == sitemap(), "Regenerate sitemap"
assert f"Sitemap: {ORIGIN}/sitemap.xml" in (ROOT/"robots.txt").read_text(encoding="utf-8")
home = (ROOT/"index.html").read_text(encoding="utf-8")
assert f'<link rel="canonical" href="{ORIGIN}/">' in home
assert 'https://geoknoesis.github.io/hexplain.io' not in home
assert (ROOT/'specification/print.css').is_file()
assert all(print_link(page) in page.read_text(encoding='utf-8') for page in pages()), 'Run tools/_site_inventory.py to link shared print styling'
print(f"PASS: local links across {len(pages())} pages and canonical publication metadata")
