"""Build one HyperFrames composition per site card from a storyboard (cards.py), then render each to MP4.

The card is 1400x788: a browser bar with the URL, the real page (stitched captures) scrolled and zoomed
by a camera, a cursor that moves and clicks, neon highlight rings with a spotlight, typed form input,
and explanation callouts timed to Dan's words (HeyGen captions).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
W, H, BAR = 1400, 788, 44
VH = H - BAR

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1400px;height:788px;background:#07080d;overflow:hidden;font-family:Inter,system-ui,sans-serif}
#root{position:relative;width:1400px;height:788px;overflow:hidden;background:#07080d}
.bar{position:absolute;left:0;top:0;width:1400px;height:44px;background:#0c0e15;border-bottom:1px solid rgba(255,255,255,.07);z-index:5}
.dots{position:absolute;left:18px;top:16px;display:flex;gap:8px}.dots i{width:12px;height:12px;border-radius:50%;display:block}
.urlbox{position:absolute;left:110px;top:8px;width:760px;height:28px;border-radius:14px;background:#161925;border:1px solid rgba(255,255,255,.06)}
.lock{position:absolute;left:14px;top:7px;width:12px;height:13px}
.url{position:absolute;left:34px;top:5px;font:500 14px Inter;color:#c9cde0;white-space:nowrap;overflow:hidden;opacity:0}
.url b{color:#fff;font-weight:600}
.vp{position:absolute;left:0;top:44px;width:1400px;height:744px;overflow:hidden}
.page{position:absolute;left:0;top:0;width:1400px;height:744px;opacity:0;overflow:hidden}
.cam{position:absolute;left:0;top:0;transform-origin:0 0}
.cam img{display:block}
.ring{position:absolute;border-radius:14px;border:3px solid #2de2c4;opacity:0;
 box-shadow:0 0 0 3px rgba(124,92,255,.35),0 0 26px 4px rgba(45,226,196,.55),inset 0 0 18px rgba(45,226,196,.25)}
.spot{position:absolute;border-radius:14px;opacity:0;box-shadow:0 0 0 6000px rgba(4,5,10,.55)}
.typed{position:absolute;overflow:hidden;white-space:nowrap;width:0;font:500 15px Inter;color:#eef0f7}
.caret{display:inline-block;width:2px;height:17px;background:#2de2c4;vertical-align:-3px;margin-left:2px}
.cursor{position:absolute;left:0;top:0;width:30px;height:30px;opacity:0;z-index:4}
.ripple{position:absolute;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;border:3px solid #2de2c4;opacity:0}
.call{position:absolute;left:34px;bottom:30px;max-width:900px;padding:16px 26px 18px 24px;border-radius:16px;opacity:0;z-index:6;
 background:linear-gradient(135deg,rgba(10,12,22,.92),rgba(16,14,34,.92));border:1px solid rgba(124,92,255,.45);
 box-shadow:0 18px 50px rgba(0,0,0,.55),0 0 30px rgba(45,226,196,.18)}
.call:before{content:'';position:absolute;left:0;top:14px;bottom:14px;width:4px;border-radius:2px;background:linear-gradient(#2de2c4,#8c64ff)}
.call h3{font:700 34px/1.15 'Inter';color:#fff;letter-spacing:-.01em}
.call p{font:500 19px/1.3 Inter;color:#2de2c4;margin-top:6px}
.chips{position:absolute;left:34px;bottom:30px;display:flex;gap:12px;z-index:6}
.chip{opacity:0;padding:12px 20px;border-radius:14px;font:700 24px Inter;color:#fff;white-space:nowrap;
 background:rgba(10,12,22,.92);border:2px solid #2de2c4;box-shadow:0 0 22px rgba(45,226,196,.45),0 12px 30px rgba(0,0,0,.5)}
.flash{position:absolute;inset:0;background:#fff;opacity:0;z-index:7;pointer-events:none}
"""

CURSOR = ('<svg viewBox="0 0 30 30" width="30" height="30"><path d="M4 2 L4 24 L10 18.5 L14 27 L18 25.3 L14 17 L22 17 Z" '
          'fill="#fff" stroke="#0b0d14" stroke-width="1.8" stroke-linejoin="round"/></svg>')
LOCK = ('<svg class="lock" viewBox="0 0 12 13"><rect x="1" y="5.5" width="10" height="7" rx="1.6" fill="#2de2c4"/>'
        '<path d="M3.2 5.5V4a2.8 2.8 0 0 1 5.6 0v1.5" stroke="#2de2c4" stroke-width="1.5" fill="none"/></svg>')


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class Comp:
    def __init__(self, cid, dur, pages_dir):
        self.cid, self.dur, self.dir = cid, dur, pages_dir
        self.pages, self.html, self.js, self.calls, self.urls = [], {}, [], [], []
        self.n = 0

    def uid(self, p):
        self.n += 1
        return f'{p}{self.n}'

    # ---------------------------------------------------------------- pages and camera
    def page(self, src, dx=0):
        im = Image.open(self.dir / src)
        k = len(self.pages)
        self.pages.append(dict(src=src, w=im.width, h=im.height, s=W / im.width, dx=dx))
        self.html[k] = []
        return k

    def _cam(self, k, focus=None, y=None, z=1.0, cx=None):
        p = self.pages[k]
        S = p['s'] * z
        if focus is not None:
            fx, fy, fw, fh = focus
            fx -= p['dx']
            x = W / 2 - (fx + fw / 2) * S
            yy = VH / 2 - (fy + fh / 2) * S
        else:
            x = 0 if cx is None else W / 2 - cx * S
            yy = -(y or 0) * S
        x = min(0, max(W - p['w'] * S, x))
        yy = min(0, max(VH - p['h'] * S, yy)) if p['h'] * S > VH else 0
        return x, yy, S

    def cam(self, k, t, d=1.0, focus=None, y=None, z=1.0, ease='power2.inOut'):
        x, yy, S = self._cam(k, focus, y, z)
        if d <= 0:
            self.js.append(f"tl.set('#c{k}',{{x:{x:.1f},y:{yy:.1f},scale:{S:.4f}}},{t:.3f});")
        else:
            self.js.append(f"tl.to('#c{k}',{{x:{x:.1f},y:{yy:.1f},scale:{S:.4f},duration:{d},ease:'{ease}'}},{t:.3f});")

    def show(self, k, t, d=0.4, slide=True):
        """Bring page k in at t (cross-fade over whatever was showing)."""
        if slide:
            self.js.append(f"tl.fromTo('#p{k}',{{opacity:0,y:18}},{{opacity:1,y:0,duration:{d},ease:'power2.out'}},{t:.3f});")
        else:
            self.js.append(f"tl.set('#p{k}',{{opacity:1}},{t:.3f});")
        for j in range(len(self.pages)):
            if j != k:
                self.js.append(f"tl.to('#p{j}',{{opacity:0,duration:{d * 0.6:.2f}}},{t + d * 0.4:.3f});")

    def url(self, t, text, typed=False):
        u = self.uid('u')
        host, _, path = text.partition('/')
        inner = f'<b>{esc(host)}</b>' + (esc('/' + path) if path else '')
        self.urls.append(f'<div class="url" id="{u}">{inner}</div>')
        for o in self.urls[:-1]:
            oid = o.split('id="')[1].split('"')[0]
            self.js.append(f"tl.set('#{oid}',{{opacity:0}},{t:.3f});")
        if typed:
            wpx = int(len(text) * 8.1) + 14
            self.js.append(f"tl.fromTo('#{u}',{{opacity:1,width:0}},{{width:{wpx},duration:{0.035 * len(text):.2f},ease:'none'}},{t:.3f});")
        else:
            self.js.append(f"tl.set('#{u}',{{opacity:1}},{t:.3f});")

    # ---------------------------------------------------------------- overlays in page space
    def ring(self, k, t, end, rect, pad=8, spot=True, r=14):
        x, y, w, h = rect
        x -= self.pages[k]['dx']
        x, y, w, h = x - pad, y - pad, w + 2 * pad, h + 2 * pad
        a = self.uid('r')
        if spot:
            s = self.uid('s')
            self.html[k].append(f'<div class="spot" id="{s}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:{r}px"></div>')
            self.js.append(f"tl.to('#{s}',{{opacity:1,duration:.35}},{t:.3f});tl.to('#{s}',{{opacity:0,duration:.35}},{end - .35:.3f});")
        self.html[k].append(f'<div class="ring" id="{a}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:{r}px"></div>')
        self.js.append(f"tl.fromTo('#{a}',{{opacity:0,scale:1.06}},{{opacity:1,scale:1,duration:.4,ease:'back.out(2)'}},{t:.3f});"
                       f"tl.to('#{a}',{{opacity:0,duration:.3}},{end - .3:.3f});")

    def typed(self, k, t, rect, text, d=None, size=15):
        x, y, w, h = rect
        x -= self.pages[k]['dx']
        a = self.uid('t')
        d = d or max(0.5, 0.05 * len(text))
        self.html[k].append(f'<div class="typed" id="{a}" style="left:{x + 14}px;top:{y + (h - 20) / 2:.0f}px;height:22px;font-size:{size}px">'
                            f'{esc(text)}<span class="caret"></span></div>')
        wpx = int(len(text) * size * 0.56) + 10
        self.js.append(f"tl.to('#{a}',{{width:{wpx},duration:{d:.2f},ease:'steps({max(len(text), 1)})'}},{t:.3f});")

    def cursor(self, k, moves):
        """moves: [(t, x, y, click?)] in page px; first entry places it."""
        a = self.uid('m')
        dx = self.pages[k]['dx']
        moves = [(t, x - dx, y, c) for t, x, y, c in moves]
        self.html[k].append(f'<div class="cursor" id="{a}">{CURSOR}</div>')
        t0, x0, y0, _ = moves[0]
        self.js.append(f"tl.set('#{a}',{{x:{x0},y:{y0}}},0);tl.to('#{a}',{{opacity:1,duration:.25}},{t0:.3f});")
        prev = moves[0]
        for t, x, y, click in moves[1:]:
            d = max(0.25, min(0.9, t - prev[0] - 0.05))
            self.js.append(f"tl.to('#{a}',{{x:{x},y:{y},duration:{d:.2f},ease:'power3.inOut'}},{t - d:.3f});")
            if click:
                rp = self.uid('rp')
                self.html[k].append(f'<div class="ripple" id="{rp}" style="left:{x + 4}px;top:{y + 3}px"></div>')
                self.js.append(f"tl.to('#{a}',{{scale:.82,duration:.08}},{t:.3f});tl.to('#{a}',{{scale:1,duration:.12}},{t + .08:.3f});"
                               f"tl.fromTo('#{rp}',{{opacity:1,scale:.3}},{{opacity:0,scale:2.4,duration:.55,ease:'power2.out',immediateRender:false}},{t:.3f});")
            prev = (t, x, y, click)
        return a

    def cursor_hide(self, cid, t):
        self.js.append(f"tl.to('#{cid}',{{opacity:0,duration:.25}},{t:.3f});")

    # ---------------------------------------------------------------- screen-space explanations
    def call(self, t, end, title, sub=None, top=False):
        a = self.uid('c')
        pos = ' style="top:24px;bottom:auto;left:auto;right:34px"' if top else ''
        self.calls.append(f'<div class="call" id="{a}"{pos}><h3>{esc(title)}</h3>' + (f'<p>{esc(sub)}</p>' if sub else '') + '</div>')
        self.js.append(f"tl.fromTo('#{a}',{{opacity:0,y:24}},{{opacity:1,y:0,duration:.45,ease:'power3.out'}},{t:.3f});"
                       f"tl.to('#{a}',{{opacity:0,y:-10,duration:.3}},{end - .3:.3f});")

    def chips(self, items, end):
        """items: [(t, text)] — pills appearing one by one, all leave at end."""
        a = self.uid('ch')
        inner = ''.join(f'<div class="chip" id="{a}_{i}">{esc(txt)}</div>' for i, (_, txt) in enumerate(items))
        self.calls.append(f'<div class="chips">{inner}</div>')
        for i, (t, _) in enumerate(items):
            self.js.append(f"tl.fromTo('#{a}_{i}',{{opacity:0,y:20,scale:.9}},{{opacity:1,y:0,scale:1,duration:.4,ease:'back.out(1.8)'}},{t:.3f});"
                           f"tl.to('#{a}_{i}',{{opacity:0,duration:.3}},{end - .3:.3f});")

    # ---------------------------------------------------------------- output
    def write(self, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        for p in self.pages:
            shutil.copy(self.dir / p['src'], out_dir / p['src'])
        shutil.copy(HERE / 'node_modules/gsap/dist/gsap.min.js', out_dir / 'gsap.min.js')
        pages = ''.join(
            f'<div class="page" id="p{k}"><div class="cam" id="c{k}" style="width:{p["w"]}px;height:{p["h"]}px">'
            f'<img src="{p["src"]}" width="{p["w"]}" height="{p["h"]}">{"".join(self.html[k])}</div></div>'
            for k, p in enumerate(self.pages))
        html = f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div id="root" data-composition-id="root" data-width="{W}" data-height="{H}" data-start="0" data-duration="{self.dur:.2f}">
<div class="bar"><div class="dots"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>
<div class="urlbox">{LOCK}{''.join(self.urls)}</div></div>
<div class="vp">{pages}</div>
{''.join(self.calls)}
</div>
<script src="gsap.min.js"></script>
<script>
const tl=gsap.timeline({{paused:true}});
{chr(10).join(self.js)}
tl.set({{}},{{}},{self.dur:.2f});
window.__timelines={{root:tl}};
</script></body></html>"""
        (out_dir / 'index.html').write_text(html)


def render(out_dir, mp4, draft=False):
    env = {'HYPERFRAMES_BROWSER_PATH': '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome'}
    import os
    env = {**os.environ, **env}
    cmd = ['npx', 'hyperframes', 'render', str(out_dir), '-o', str(mp4), '-f', '25', '-q', 'draft' if draft else 'delivery',
           '--video-frame-format', 'png', '-w', '4']
    r = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    print(mp4.name, 'OK' if r.returncode == 0 else 'FAILED', *tail, sep='\n  ')
    return r.returncode == 0


if __name__ == '__main__':
    from cards import CARDS
    only = [a for a in sys.argv[1:] if not a.startswith('--')] or list(CARDS)
    for cid in only:
        comp = CARDS[cid](Comp)
        d = HERE / 'comps' / cid
        comp.write(d)
        render(d, HERE / 'out' / f'{cid}.mp4', draft='--draft' in sys.argv)
