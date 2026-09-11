"""Headless browser acceptance for navigation, reflow, reduced motion and print."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.gate-results/browser';OUT.mkdir(parents=True,exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT)))
Thread(target=server.serve_forever,daemon=True).start()
checks=[]
try:
    with sync_playwright() as play:
        browser=play.chromium.launch()
        for width in [375,768,1440]:
            page=browser.new_page(viewport={'width':width,'height':1000},reduced_motion='reduce')
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='networkidle')
            assert not errors,errors
            assert page.locator('main').count()==1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'Horizontal page overflow at {width}'
            assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior === 'auto'")
            page.keyboard.press('Tab')
            assert page.locator('.skip-link').evaluate('(e)=>e===document.activeElement')
            page.keyboard.press('Enter')
            assert page.locator('main').evaluate('(e)=>e===document.activeElement')
            burger=page.locator('#hamburger')
            if burger.is_visible():
                burger.click();assert burger.get_attribute('aria-expanded')=='true'
                page.keyboard.press('Escape');assert burger.get_attribute('aria-expanded')=='false'
                assert burger.get_attribute('aria-label')=='Open menu'
                burger.click();page.locator('#mobileMenu a').first.click()
                assert burger.get_attribute('aria-expanded')=='false'
                assert burger.get_attribute('aria-label')=='Open menu'
            page.evaluate('scrollTo(0,0)')
            page.screenshot(path=str(OUT/f'home-{width}.png'))
            checks.append(f'home {width}px: navigation, skip link, reduced motion, no overflow/errors')
            page.close()
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='networkidle')
        colors=page.evaluate("""() => {
            const s=getComputedStyle(document.documentElement);
            return Object.fromEntries(['--text','--muted','--muted-2','--bg','--bg-2','--surface'].map(k=>[k,s.getPropertyValue(k).trim()]));
        }""")
        def luminance(hexcolor):
            values=[int(hexcolor[i:i+2],16)/255 for i in (1,3,5)]
            linear=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in values]
            return sum(v*w for v,w in zip(linear,[0.2126,0.7152,0.0722]))
        for foreground in ['--text','--muted','--muted-2']:
            for background in ['--bg','--bg-2','--surface']:
                ratio=(luminance(colors[foreground])+0.05)/(luminance(colors[background])+0.05)
                assert ratio>=4.5,(foreground,background,ratio)
        checks.append('Homepage text palette: nine foreground/background pairs meet 4.5:1')
        page.close()
        # 1440 physical pixels / 2: match the CSS viewport and raster scale of 200% browser zoom.
        page=browser.new_page(viewport={'width':720,'height':500},device_scale_factor=2,reduced_motion='reduce')
        page.goto(f'http://127.0.0.1:{server.server_port}/',wait_until='networkidle')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),'Overflow at 200% equivalent reflow'
        page.screenshot(path=str(OUT/'home-zoom-200.png'))
        checks.append('Homepage 200% equivalent CSS viewport/raster scale: no horizontal page overflow')
        page.close()
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.goto(f'http://127.0.0.1:{server.server_port}/specification/bddo/',wait_until='networkidle')
        page.emulate_media(media='print')
        assert page.locator('h1').is_visible()
        assert page.locator('body').evaluate("e=>getComputedStyle(e).backgroundColor")=='rgb(255, 255, 255)'
        assert page.locator('body').evaluate("e=>getComputedStyle(e).color")=='rgb(0, 0, 0)'
        page.screenshot(path=str(OUT/'bddo-print.png'))
        checks.append('BDDO print media: visible title, black text and white paper background')
        browser.close()
    (OUT/'results.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n',encoding='utf-8')
    print('PASS: '+ '; '.join(checks))
finally:
    server.shutdown();server.server_close()
